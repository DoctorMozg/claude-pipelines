import fnmatch
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.eval_tools.local_graders import EvalCase, load_cases
from tests.eval_tools.mutant_catalog import MUTANTS, Edit, Mutant
from tests.eval_tools.mutants import REPO_ROOT, MutantError, build_snapshot, judge, plan_edits

type Suite = dict[str, EvalCase]
type CaseResult = dict[str, Any]

BY_ID = [pytest.param(mutant, id=mutant.id) for mutant in MUTANTS]


def _selected(select: tuple[str, ...], suite: Suite) -> set[str]:
    chosen = set(suite)
    for flag, value in zip(select[::2], select[1::2], strict=True):
        if flag == "--case":
            chosen = {name for name in chosen if fnmatch.fnmatchcase(name, value)}
        elif flag == "--tag":
            chosen = {name for name in chosen if value in suite[name].tags}
        else:
            pytest.fail(f"no selection rule for eval flag {flag}")
    return chosen


@pytest.fixture(scope="module")
def suites() -> dict[str, Suite]:
    plugins = sorted({mutant.plugin for mutant in MUTANTS})
    return {plugin: load_cases(REPO_ROOT / "evals" / plugin) for plugin in plugins}


@pytest.fixture
def mutant_factory() -> Callable[..., Mutant]:
    def build(
        must_fail: tuple[tuple[str, str], ...] = (), must_pass: tuple[str, ...] = ()
    ) -> Mutant:
        return Mutant("probe", (), "mz-memory", ("--case", "*"), must_fail, must_pass)

    return build


def _case(
    name: str, graders: dict[str, bool], score: float = 1.0, error: str | None = None
) -> CaseResult:
    arm = {
        "score": score,
        "error": error,
        "graders": [{"name": grader, "passed": passed} for grader, passed in graders.items()],
    }
    return {"name": name, "arms": {"with": [arm]}}


def _doc(*cases: CaseResult, cost: float = 0.25) -> dict[str, Any]:
    return {"cases": list(cases), "costUsd": cost}


class TestAnchors:
    @pytest.mark.parametrize("mutant", BY_ID)
    def test_every_edit_matches_and_changes_the_working_tree_file(self, mutant: Mutant) -> None:
        planned = plan_edits(REPO_ROOT, mutant)

        assert planned, f"{mutant.id} edits nothing"
        unchanged = [
            path.relative_to(REPO_ROOT).as_posix()
            for path, text in planned.items()
            if text == path.read_text(encoding="utf-8")
        ]
        assert not unchanged, f"{mutant.id} leaves these files as they were: {unchanged}"


class TestReferences:
    @pytest.mark.parametrize("mutant", BY_ID)
    def test_selection_runs_every_case_the_mutant_names(
        self, mutant: Mutant, suites: dict[str, Suite]
    ) -> None:
        selected = _selected(mutant.select, suites[mutant.plugin])
        named = {case for case, _ in mutant.must_fail} | set(mutant.must_pass)

        assert named, f"{mutant.id} expects nothing to fail or pass"
        assert named <= selected, f"{mutant.id} never runs {sorted(named - selected)}"

    @pytest.mark.parametrize("mutant", BY_ID)
    def test_every_must_fail_grader_exists(self, mutant: Mutant, suites: dict[str, Suite]) -> None:
        suite = suites[mutant.plugin]
        missing = [
            f"{case}/{grader}"
            for case, grader in mutant.must_fail
            if case not in suite or grader not in {g["name"] for g in suite[case].graders}
        ]

        assert not missing, f"{mutant.id} names graders its cases don't have: {missing}"


class TestPlanEdits:
    def test_missing_anchor_is_an_error(self, tmp_path: Path) -> None:
        (tmp_path / "a.sh").write_text("echo hi\n")
        mutant = Mutant("m", (Edit("a.sh", "exit 0", "exit 1"),), "p", (), ())

        with pytest.raises(MutantError, match=r"anchor found 0 times in a\.sh"):
            plan_edits(tmp_path, mutant)

    def test_repeated_anchor_is_an_error(self, tmp_path: Path) -> None:
        (tmp_path / "a.sh").write_text("exit 0\nexit 0\n")
        mutant = Mutant("m", (Edit("a.sh", "exit 0", "exit 1"),), "p", (), ())

        with pytest.raises(MutantError, match="anchor found 2 times"):
            plan_edits(tmp_path, mutant)

    def test_glob_matching_no_file_is_an_error(self, tmp_path: Path) -> None:
        mutant = Mutant("m", (Edit("evals/*/case.yaml", "x", "y"),), "p", (), ())

        with pytest.raises(MutantError, match="no file matches"):
            plan_edits(tmp_path, mutant)

    def test_brace_group_needs_the_anchor_in_every_match(self, tmp_path: Path) -> None:
        for name, body in (("inject-a", "x"), ("inject-b", "x"), ("prompt", "x"), ("other", "")):
            (tmp_path / name).mkdir()
            (tmp_path / name / "case.yaml").write_text(body)
        mutant = Mutant("m", (Edit("{inject-*,prompt}/case.yaml", "x", "y"),), "p", (), ())

        planned = plan_edits(tmp_path, mutant)

        assert sorted(path.parent.name for path in planned) == ["inject-a", "inject-b", "prompt"]

    def test_later_edit_sees_the_earlier_one(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("one\n")
        edits = (Edit("a.md", "one", "two"), Edit("a.md", "two", "three"))

        planned = plan_edits(tmp_path, Mutant("m", edits, "p", (), ()))

        assert planned == {tmp_path / "a.md": "three\n"}

    def test_planning_leaves_the_files_untouched(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("one\n")

        plan_edits(tmp_path, Mutant("m", (Edit("a.md", "one", "two"),), "p", (), ()))

        assert (tmp_path / "a.md").read_text() == "one\n"


class TestJudge:
    def test_every_must_fail_grader_failing_is_ok(
        self, mutant_factory: Callable[..., Mutant]
    ) -> None:
        mutant = mutant_factory(must_fail=(("a", "g1"), ("b", "g2")))
        doc = _doc(_case("a", {"g1": False, "g0": True}, 0.5), _case("b", {"g2": False}, 0.0))

        result = judge(mutant, doc)

        assert result.ok
        assert result.detail == "failed: a/g1, b/g2"
        assert result.cost_usd == 0.25

    def test_a_must_fail_grader_still_passing_is_not_caught(
        self, mutant_factory: Callable[..., Mutant]
    ) -> None:
        result = judge(mutant_factory(must_fail=(("a", "g1"),)), _doc(_case("a", {"g1": True})))

        assert not result.ok
        assert "NOT CAUGHT: ['a/g1']" in result.detail

    def test_a_grader_absent_from_the_result_is_not_caught(
        self, mutant_factory: Callable[..., Mutant]
    ) -> None:
        result = judge(mutant_factory(must_fail=(("a", "gone"),)), _doc(_case("a", {"g1": False})))

        assert not result.ok
        assert "NOT CAUGHT: ['a/gone']" in result.detail

    @pytest.mark.parametrize(
        "cases",
        [
            pytest.param((_case("a", {"g1": False}, 0.5),), id="scored-below-one"),
            pytest.param((), id="case-missing"),
        ],
    )
    def test_must_pass_case_not_scoring_one_is_a_problem(
        self, mutant_factory: Callable[..., Mutant], cases: tuple[CaseResult, ...]
    ) -> None:
        result = judge(mutant_factory(must_pass=("a",)), _doc(*cases))

        assert not result.ok
        assert "SHOULD HAVE PASSED: ['a']" in result.detail

    def test_turn_limit_error_is_expected(self, mutant_factory: Callable[..., Mutant]) -> None:
        case = _case("a", {"g1": True}, error="Reached maximum number of turns (2)")

        assert judge(mutant_factory(must_pass=("a",)), _doc(case)).ok

    def test_any_other_run_error_voids_the_run(self, mutant_factory: Callable[..., Mutant]) -> None:
        case = _case("a", {"g1": False}, 0.0, error="API Error: 529 overloaded")

        result = judge(mutant_factory(must_fail=(("a", "g1"),)), _doc(case))

        assert not result.ok
        assert "run errors: ['API Error: 529 overloaded']" in result.detail

    def test_missing_cost_reads_as_zero(self, mutant_factory: Callable[..., Mutant]) -> None:
        doc = {"cases": [_case("a", {"g1": True})]}

        assert judge(mutant_factory(must_pass=("a",)), doc).cost_usd == 0.0


class TestSnapshot:
    def test_committed_plugin_code_with_working_tree_evals(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        evals = repo / "evals/p"
        (evals / "old").mkdir(parents=True)
        (repo / "plugins/p").mkdir(parents=True)
        (repo / "plugins/p/hook.sh").write_text("committed\n")
        (evals / "old/case.yaml").write_text("name: old\n")
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "seed"], check=True)
        (repo / "plugins/p/hook.sh").write_text("peer edit in progress\n")
        (evals / "new").mkdir()
        (evals / "new/case.yaml").write_text("name: new\n")
        (evals / "results").mkdir()
        (evals / "results/last-sonnet.json").write_text("{}")

        build_snapshot(tmp_path / "snap", repo)

        snap = tmp_path / "snap"
        assert (snap / "plugins/p/hook.sh").read_text() == "committed\n"
        assert sorted(p.name for p in (snap / "evals/p").iterdir()) == ["new", "old"]

    def test_failed_archive_is_a_mutant_error(self, tmp_path: Path) -> None:
        with pytest.raises(MutantError, match="git archive HEAD plugins failed"):
            build_snapshot(tmp_path / "snap", tmp_path)
