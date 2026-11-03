import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.eval_tools.local_graders import (
    EvalCase,
    Outcome,
    PrecheckError,
    ToolCall,
    Verdict,
    grade,
    hook_line,
    load_cases,
    scaffold,
)


def _regex(pattern: str, **fields: object) -> dict[str, Any]:
    return {"name": "g", "type": "regex", "pattern": pattern, "target": "trace", **fields}


def _tool(tool: str, **fields: object) -> dict[str, Any]:
    return {"name": "g", "type": "tool_used", "tool": tool, **fields}


def _one(grader: dict[str, Any], outcome: Outcome) -> Verdict:
    [verdict] = grade([grader], outcome)
    return verdict


def _case(directory: Path, fixture: str | None, **spec: object) -> EvalCase:
    context = {"scaffold_script": fixture} if fixture else {}
    return EvalCase(directory, {"name": "c", "context": context, **spec})


@pytest.fixture
def outcome(tmp_path: Path) -> Outcome:
    (tmp_path / "notes.md").write_text("alpha\nBeta\nalpha\n")
    return Outcome(tmp_path, (hook_line("injected: alpha"),), tool_calls=(), reply="Done.")


class TestRegexMatch:
    @pytest.mark.parametrize(
        ("match", "pattern", "passed"),
        [
            pytest.param("contains", "alpha", True, id="contains-hit"),
            pytest.param("contains", "gamma", False, id="contains-miss"),
            pytest.param("not_contains", "gamma", True, id="not-contains-miss"),
            pytest.param("not_contains", "alpha", False, id="not-contains-hit"),
            pytest.param("count:2", "alpha", True, id="count-exact"),
            pytest.param("count:1", "alpha", False, id="count-off"),
        ],
    )
    def test_match_modes(self, outcome: Outcome, match: str, pattern: str, passed: bool) -> None:
        target = {"source": "file", "path": "notes.md"}

        assert _one(_regex(pattern, match=match, target=target), outcome).passed is passed

    @pytest.mark.parametrize("match", ["regex", "count:", "count:x"])
    def test_unknown_match_is_an_error(self, outcome: Outcome, match: str) -> None:
        with pytest.raises(PrecheckError, match="no local rule for match"):
            grade([_regex("alpha", match=match)], outcome)


class TestFlags:
    def test_case_is_kept_without_i(self, outcome: Outcome) -> None:
        target = {"source": "file", "path": "notes.md"}

        assert _one(_regex("beta", target=target), outcome).hits == 0
        assert _one(_regex("beta", target=target, flags="i"), outcome).hits == 1

    def test_m_anchors_each_line(self, outcome: Outcome) -> None:
        target = {"source": "file", "path": "notes.md"}

        assert _one(_regex("^Beta$", target=target), outcome).hits == 0
        assert _one(_regex("^Beta$", target=target, flags="m"), outcome).hits == 1

    def test_unknown_flag_is_an_error(self, outcome: Outcome) -> None:
        with pytest.raises(PrecheckError, match="regex flag 'x'"):
            grade([_regex("alpha", flags="ix")], outcome)


class TestTargets:
    def test_missing_file_grades_as_empty_text(self, outcome: Outcome) -> None:
        target = {"source": "file", "path": "absent.md"}

        absent = _one(_regex("alpha", target=target), outcome)
        assert (absent.passed, absent.note) == (False, "file missing")
        assert _one(_regex("alpha", target=target, match="not_contains"), outcome).passed

    def test_trace_holds_hook_lines_then_tool_calls(self, tmp_path: Path) -> None:
        calls = (ToolCall("Bash", {"command": "ls"}),)
        outcome = Outcome(tmp_path, (hook_line("ctx"),), tool_calls=calls)

        first, second = outcome.trace.splitlines()
        assert json.loads(first)["subtype"] == "hook_response"
        assert json.loads(second) == {
            "type": "tool_use",
            "name": "Bash",
            "input": {"command": "ls"},
        }

    def test_reply_grader_runs_only_on_an_acted_out_reply(
        self, outcome: Outcome, tmp_path: Path
    ) -> None:
        grader = _regex("Done", target="last_message")

        assert _one(grader, outcome).passed
        assert grade([grader], Outcome(tmp_path)) == []

    def test_default_target_is_the_reply(self, tmp_path: Path) -> None:
        grader = {"name": "g", "type": "regex", "pattern": "approve", "flags": "i"}

        assert grade([grader], Outcome(tmp_path)) == []
        assert _one(grader, Outcome(tmp_path, reply="Approve?")).passed

    @pytest.mark.parametrize(
        "target",
        [pytest.param("files", id="named-target"), pytest.param({"source": "url"}, id="source")],
    )
    def test_unknown_target_is_an_error(self, outcome: Outcome, target: object) -> None:
        with pytest.raises(PrecheckError, match="no local rule for target"):
            grade([_regex("alpha", target=target)], outcome)


class TestToolUsed:
    def test_skipped_when_no_tool_use_was_acted_out(self, tmp_path: Path) -> None:
        assert grade([_tool("Bash")], Outcome(tmp_path)) == []

    def test_anchored_input_match_skips_content_and_other_tools(self, tmp_path: Path) -> None:
        calls = (
            ToolCall("Write", {"file_path": "/w/.mz/task/x/state.md", "content": "CLAUDE.md"}),
            ToolCall("Edit", {"file_path": "/w/CLAUDE.md"}),
        )
        grader = _tool("Write", input_match=r'"file_path":"[^"]*CLAUDE\.md"')

        assert _one(grader, Outcome(tmp_path, tool_calls=calls)).hits == 0

    @pytest.mark.parametrize(
        ("bounds", "calls", "passed"),
        [
            pytest.param({}, 0, False, id="default-min-one-unmet"),
            pytest.param({}, 2, True, id="default-no-max"),
            pytest.param({"min": 0, "max": 0}, 0, True, id="forbidden-and-absent"),
            pytest.param({"min": 0, "max": 0}, 1, False, id="forbidden-and-present"),
        ],
    )
    def test_min_and_max_bound_the_count(
        self, tmp_path: Path, bounds: dict[str, int], calls: int, passed: bool
    ) -> None:
        made = tuple(ToolCall("Bash", {"command": "ls"}) for _ in range(calls))

        assert _one(_tool("Bash", **bounds), Outcome(tmp_path, tool_calls=made)).passed is passed

    def test_non_ascii_input_is_matched_as_written(self, tmp_path: Path) -> None:
        call = ToolCall("Bash", {"command": "note 'WHEN a → b'"})

        assert _one(
            _tool("Bash", input_match="a → b"), Outcome(tmp_path, tool_calls=(call,))
        ).passed


class TestGraderShape:
    def test_unknown_type_is_an_error(self, outcome: Outcome) -> None:
        with pytest.raises(PrecheckError, match="grader type 'file_exists'"):
            grade([{"name": "g", "type": "file_exists"}], outcome)

    def test_grader_without_a_name_is_an_error(self, outcome: Outcome) -> None:
        with pytest.raises(PrecheckError, match="without a name or type"):
            grade([{"type": "regex", "pattern": "x"}], outcome)


class TestScaffold:
    def test_fixture_runs_in_the_cwd_under_a_git_repo_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MZ_MEMORY_ROOT", "/elsewhere")
        (tmp_path / "case").mkdir()
        (tmp_path / "case/fixture.sh").write_text(
            'printf "%s|%s|%s" "$PWD" "$HOME" "${MZ_MEMORY_ROOT-unset}" > seen\n'
        )

        workspace = scaffold(_case(tmp_path / "case", "fixture.sh"), tmp_path / "run")

        seen = (workspace.cwd / "seen").read_text().split("|")
        assert seen == [str(workspace.cwd), str(workspace.home), "unset"]
        top = subprocess.run(
            ["git", "-C", str(workspace.cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert top.stdout.strip() == str(workspace.home)

    def test_failing_fixture_is_a_precheck_error(self, tmp_path: Path) -> None:
        (tmp_path / "fixture.sh").write_text("echo broken seed >&2\nexit 3\n")

        with pytest.raises(PrecheckError, match=r"fixture\.sh exited 3: broken seed"):
            scaffold(_case(tmp_path, "fixture.sh"), tmp_path / "run")

    def test_case_without_a_fixture_is_a_precheck_error(self, tmp_path: Path) -> None:
        with pytest.raises(PrecheckError, match="has no scaffold_script"):
            scaffold(_case(tmp_path, None), tmp_path / "run")


class TestHooks:
    def test_hook_gets_the_payload_and_the_project_dir(self, tmp_path: Path) -> None:
        (tmp_path / "fixture.sh").write_text(":\n")
        hook = tmp_path / "hook.sh"
        hook.write_text('printf "%s %s %s" "$(cat)" "$CLAUDE_PROJECT_DIR" "$EXTRA"\n')
        workspace = scaffold(_case(tmp_path, "fixture.sh"), tmp_path / "run")

        output = workspace.run_hook(hook, {"source": "startup"}, EXTRA="x")

        assert output == f'{{"source": "startup"}} {workspace.cwd} x'

    def test_failing_hook_names_the_script(self, tmp_path: Path) -> None:
        (tmp_path / "fixture.sh").write_text(":\n")
        hook = tmp_path / "hook.sh"
        hook.write_text("echo nope >&2\nexit 1\n")
        workspace = scaffold(_case(tmp_path, "fixture.sh"), tmp_path / "run")

        with pytest.raises(PrecheckError, match=r"hook\.sh exited 1: nope"):
            workspace.run_hook(hook, {})


class TestLoadCases:
    def test_cases_are_keyed_by_their_yaml_name(self, tmp_path: Path) -> None:
        (tmp_path / "dir-a").mkdir()
        (tmp_path / "dir-a/case.yaml").write_text("name: alpha\ntags: [hooks]\n")

        cases = load_cases(tmp_path)

        assert list(cases) == ["alpha"]
        assert (cases["alpha"].directory, cases["alpha"].tags) == (
            tmp_path / "dir-a",
            frozenset({"hooks"}),
        )

    def test_missing_evals_dir_is_an_error(self, tmp_path: Path) -> None:
        with pytest.raises(PrecheckError, match="is not an evals directory"):
            load_cases(tmp_path / "nope")
