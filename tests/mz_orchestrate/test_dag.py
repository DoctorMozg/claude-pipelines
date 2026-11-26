import json
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest

DAG = Path(__file__).resolve().parents[2] / "plugins" / "mz-orchestrate" / "scripts" / "dag.sh"
BASH = shutil.which("bash") or "/bin/bash"
REPO = "/work/app"

type Unit = dict[str, object]
type Run = Callable[..., subprocess.CompletedProcess[str]]


def unit(uid: str, *deps: str, **over: object) -> Unit:
    base: Unit = {
        "id": uid,
        "title": f"Unit {uid}",
        "kind": "change",
        "repo": REPO,
        "skill": "mz-dev-pipe:build",
        "spec": "do it",
        "owns": [f"src/{uid.split('_')[0].lower()}/*"],
        "verify": "make test",
        "depends_on": list(deps),
    }
    return base | over


def diamond() -> list[Unit]:
    return [
        unit("A_Unit"),
        unit("B_Unit", "A_Unit"),
        unit("C_Unit", "A_Unit"),
        unit(
            "D_Unit", "B_Unit", "C_Unit", kind="review", skill="mz-dev-git:review-branch", owns=[]
        ),
    ]


@pytest.fixture
def dag_path(tmp_path: Path) -> Path:
    return tmp_path / "dag.json"


@pytest.fixture
def write(dag_path: Path) -> Callable[[list[Unit]], None]:
    def _write(units: list[Unit]) -> None:
        dag_path.write_text(json.dumps({"task": "t", "project": REPO, "units": units}))

    return _write


@pytest.fixture
def run(dag_path: Path) -> Run:
    def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [BASH, str(DAG), str(dag_path), *args], capture_output=True, text=True, check=False
        )
        if check:
            assert result.returncode == 0, result.stderr
        return result

    return _run


def status(dag_path: Path) -> dict[str, str]:
    units = json.loads(dag_path.read_text())["units"]
    return {u["id"]: u.get("status", "pending") for u in units}


class TestLint:
    def test_a_diamond_passes(self, write: Callable[[list[Unit]], None], run: Run) -> None:
        write(diamond())

        assert run("lint").stdout == "lint: ok (4 units)\n"

    def test_a_codex_unit_may_work_in_another_repo(
        self, write: Callable[[list[Unit]], None], run: Run
    ) -> None:
        write([unit("A_Unit", repo="/other", backend="codex")])

        assert run("lint").stdout == "lint: ok (1 units)\n"

    @pytest.mark.parametrize(
        ("units", "message"),
        [
            ([unit("A_Unit", "B_Unit"), unit("B_Unit", "A_Unit")], "cycle through: A_Unit, B_Unit"),
            ([unit("A_Unit", "Z_Unit")], "A_Unit: depends on unknown unit Z_Unit"),
            ([unit("A_Unit", "A_Unit")], "A_Unit: depends on itself"),
            ([unit("A_Unit"), unit("A_Unit", owns=["x/*"])], "A_Unit: duplicate id"),
            ([unit("A_Unit", owns=[])], "A_Unit: a change unit needs owns globs"),
            ([unit("A_Unit", verify="")], "A_Unit: a change unit needs a verify command"),
            ([unit("A_Unit", kind="refactor")], "A_Unit: kind must be change, review or context"),
            (
                [unit("C_Unit", kind="context", owns=["x/*"]), unit("A_Unit", "C_Unit")],
                "C_Unit: a context unit owns nothing",
            ),
            (
                [unit("C_Unit", kind="context", owns=[])],
                "C_Unit: no unit depends on this context unit",
            ),
            (
                [unit("A_Unit", skill="mz-dev-pipe:optimize")],
                "A_Unit: an optimize unit needs exclusive: true",
            ),
            ([unit("A_Unit", repo="app")], "A_Unit: repo must be an absolute path"),
            ([unit("A_Unit", backend="cloud")], "A_Unit: unknown backend cloud"),
            (
                [unit("A_Unit", repo="/other", backend="subagent")],
                "A_Unit: a subagent can only work",
            ),
            ([unit("Q3a")], "Q3a: id must be a plan reference and a name"),
            ([unit("Q3a_Vector Lookup")], "Q3a_Vector Lookup: id must be"),
            ([unit("Q3a_" + "Long" * 8)], f"Q3a_{'Long' * 8}: id must be"),
        ],
    )
    def test_bad_dags_fail_with_the_reason(
        self, write: Callable[[list[Unit]], None], run: Run, units: list[Unit], message: str
    ) -> None:
        write(units)
        result = run("lint", check=False)

        assert result.returncode == 1
        assert message in result.stderr

    def test_parallel_units_owning_one_path_clash(
        self, write: Callable[[list[Unit]], None], run: Run
    ) -> None:
        write([unit("A_Unit"), unit("B_Unit", owns=["src/a/models.py"])])
        result = run("lint", check=False)

        assert result.returncode == 1
        assert (
            "A_Unit, B_Unit: can run in parallel but both own src/a/* ~ src/a/models.py"
            in result.stderr
        )

    @pytest.mark.parametrize(
        "second",
        [
            unit("B_Unit", "A_Unit", owns=["src/a/models.py"]),
            unit("B_Unit", owns=["src/a/*"], repo="/work/other"),
            unit("B_Unit", owns=["src/ab/*"]),
        ],
        ids=["ordered-by-a-dependency", "other-repo", "sibling-directory"],
    )
    def test_shared_paths_are_fine_when_units_cannot_collide(
        self, write: Callable[[list[Unit]], None], run: Run, second: Unit
    ) -> None:
        write([unit("A_Unit", owns=["src/a/*"]), second])

        assert run("lint").returncode == 0


class TestLintPeerRoles:
    @pytest.fixture
    def peers(self, tmp_path: Path) -> Path:
        role = {"kinds": ["review"], "repos": "any", "paths": ["web/**"], "skills": "any"}
        registry = tmp_path / "peers.json"
        registry.write_text(json.dumps({"peers": [{"name": "rev", "role": role}]}))
        return registry

    def test_a_unit_inside_the_role_passes(
        self, write: Callable[[list[Unit]], None], run: Run, peers: Path
    ) -> None:
        write([unit("A_Unit", kind="review", owns=["web/app.ts"], backend="peer:rev")])

        assert run("lint", str(peers)).returncode == 0

    @pytest.mark.parametrize(
        ("over", "message"),
        [
            ({"backend": "peer:ghost"}, "names peer ghost, which is not attached"),
            ({"owns": ["web/*"]}, "kind change is outside the role of rev"),
            ({"kind": "review", "owns": ["src/x.py"]}, "owns src/x.py, outside the paths of rev"),
        ],
    )
    def test_a_pinned_unit_outside_the_role_fails(
        self,
        write: Callable[[list[Unit]], None],
        run: Run,
        peers: Path,
        over: Unit,
        message: str,
    ) -> None:
        write([unit("A_Unit", **({"backend": "peer:rev"} | over))])
        result = run("lint", str(peers), check=False)

        assert result.returncode == 1
        assert message in result.stderr


class TestFits:
    @pytest.fixture
    def peers(self, tmp_path: Path) -> Path:
        anything = {"kinds": "any", "repos": "any", "paths": "any", "skills": "any"}
        review = anything | {"kinds": ["review"]}
        registry = tmp_path / "peers.json"
        registry.write_text(
            json.dumps(
                {
                    "peers": [
                        {"name": "any", "status": "attached", "role": anything},
                        {"name": "rev", "status": "attached", "role": review},
                        {"name": "gone", "status": "detached", "role": anything},
                    ]
                }
            )
        )
        return registry

    @pytest.mark.parametrize(
        ("over", "expected"),
        [({}, ["any"]), ({"kind": "review", "owns": []}, ["any", "rev"])],
        ids=["change", "review"],
    )
    def test_lists_attached_peers_whose_role_covers_the_unit(
        self,
        write: Callable[[list[Unit]], None],
        run: Run,
        peers: Path,
        over: Unit,
        expected: list[str],
    ) -> None:
        write([unit("A_Unit", **over)])

        assert run("fits", "A_Unit", str(peers)).stdout.split() == expected

    def test_a_peer_running_a_unit_is_not_free(
        self, write: Callable[[list[Unit]], None], run: Run, peers: Path
    ) -> None:
        write([unit("A_Unit"), unit("B_Unit", owns=["src/other/*"])])
        run("mark", "B_Unit", "running", "backend_used=peer:any")

        assert run("fits", "A_Unit", str(peers)).stdout.split() == []


class TestExclusive:
    @pytest.fixture(autouse=True)
    def _units(self, write: Callable[[list[Unit]], None]) -> None:
        write([unit("A_Unit"), unit("O_Unit", exclusive=True), unit("B_Unit")])

    def test_a_ready_exclusive_unit_holds_back_the_rest(self, run: Run) -> None:
        assert run("ready").stdout.split() == ["O_Unit"]

    def test_it_waits_until_nothing_runs(self, run: Run) -> None:
        run("mark", "A_Unit", "running")

        assert run("ready").stdout.split() == []

    def test_nothing_starts_beside_it(self, run: Run) -> None:
        run("mark", "O_Unit", "running")

        assert run("ready").stdout.split() == []

    def test_the_rest_go_once_it_has_run(self, run: Run) -> None:
        run("mark", "O_Unit", "merged")

        assert run("ready").stdout.split() == ["A_Unit", "B_Unit"]


class TestScheduling:
    @pytest.fixture(autouse=True)
    def _diamond(self, write: Callable[[list[Unit]], None]) -> None:
        write(diamond())

    def test_only_roots_are_ready_at_the_start(self, run: Run) -> None:
        assert run("ready").stdout.split() == ["A_Unit"]

    def test_merging_a_unit_releases_its_dependents(self, run: Run) -> None:
        run("mark", "A_Unit", "merged")

        assert run("ready").stdout.split() == ["B_Unit", "C_Unit"]

    def test_a_failed_dependency_holds_its_dependents(self, run: Run) -> None:
        run("mark", "A_Unit", "merged")
        run("mark", "B_Unit", "failed")
        run("mark", "C_Unit", "merged")

        assert run("ready").stdout.split() == []

    def test_a_finished_review_counts_as_satisfied(
        self, write: Callable[[list[Unit]], None], run: Run
    ) -> None:
        write([unit("R_Unit", kind="review", owns=[]), unit("F_Unit", "R_Unit")])
        run("mark", "R_Unit", "done")

        assert run("ready").stdout.split() == ["F_Unit"]

    def test_a_finished_context_unit_counts_as_satisfied(
        self, write: Callable[[list[Unit]], None], run: Run
    ) -> None:
        write([unit("C_Unit", kind="context", owns=[]), unit("F_Unit", "C_Unit")])
        run("mark", "C_Unit", "done")

        assert run("ready").stdout.split() == ["F_Unit"]

    def test_list_prints_the_units_in_one_status(self, run: Run) -> None:
        run("mark", "A_Unit", "running")

        assert run("list", "running").stdout.split() == ["A_Unit"]
        assert run("list", "pending").stdout.split() == ["B_Unit", "C_Unit", "D_Unit"]

    def test_requeue_does_not_count_the_lost_attempt(self, run: Run, dag_path: Path) -> None:
        run("mark", "A_Unit", "running")
        run("requeue", "A_Unit")
        run("mark", "A_Unit", "running")

        a = json.loads(dag_path.read_text())["units"][0]
        assert (a["status"], a["attempts"]) == ("running", 1)

    def test_mark_running_records_fields_and_counts_attempts(
        self, run: Run, dag_path: Path
    ) -> None:
        run("mark", "A_Unit", "running", "base_commit=abc", "branch=orch/t/A_Unit")
        run("mark", "A_Unit", "running", "note=verifying")
        assert json.loads(dag_path.read_text())["units"][0]["attempts"] == 1

        run("mark", "A_Unit", "pending")
        run("mark", "A_Unit", "running")
        a = json.loads(dag_path.read_text())["units"][0]
        assert (a["status"], a["base_commit"], a["note"], a["attempts"]) == (
            "running",
            "abc",
            "verifying",
            2,
        )

    def test_mark_times_each_attempt(self, run: Run, dag_path: Path) -> None:
        run("mark", "A_Unit", "running")
        run("mark", "A_Unit", "running", "note=verifying")
        a = json.loads(dag_path.read_text())["units"][0]
        assert "ended_at" not in a

        run("mark", "A_Unit", "done")
        a = json.loads(dag_path.read_text())["units"][0]
        assert 0 <= a["ended_at"] - a["started_at"] <= 5

        run("mark", "A_Unit", "running")
        assert "ended_at" not in json.loads(dag_path.read_text())["units"][0]

    def test_mark_extended_leaves_the_session_note_alone(self, run: Run, dag_path: Path) -> None:
        run(
            "mark",
            "A_Unit",
            "running",
            "note=ab12cd34 uds:/x.sock",
            "deadline=2026-01-01T00:00:00Z",
        )
        run("mark", "A_Unit", "running", "deadline=2026-01-01T00:22:30Z", "extended=yes")

        a = json.loads(dag_path.read_text())["units"][0]
        assert (a["note"], a["deadline"], a["extended"]) == (
            "ab12cd34 uds:/x.sock",
            "2026-01-01T00:22:30Z",
            "yes",
        )

    @pytest.mark.parametrize(
        ("args", "message"),
        [
            (("A_Unit", "busy"), "unknown status 'busy'"),
            (("A_Unit", "merged", "status=done"), "mark cannot set 'status'"),
            (("Z_Unit", "merged"), "no unit 'Z_Unit'"),
        ],
    )
    def test_mark_rejects_bad_input_and_keeps_the_dag(
        self, run: Run, dag_path: Path, args: tuple[str, ...], message: str
    ) -> None:
        before = dag_path.read_text()
        result = run("mark", *args, check=False)

        assert result.returncode != 0
        assert message in result.stderr
        assert dag_path.read_text() == before

    def test_skip_drops_the_unit_and_everything_downstream(self, run: Run, dag_path: Path) -> None:
        run("skip", "B_Unit")

        assert status(dag_path) == {
            "A_Unit": "pending",
            "B_Unit": "skipped",
            "C_Unit": "pending",
            "D_Unit": "skipped",
        }


class TestAdd:
    @pytest.fixture(autouse=True)
    def _diamond(self, write: Callable[[list[Unit]], None]) -> None:
        write(diamond())

    def add(self, tmp_path: Path, run: Run, new: Unit) -> subprocess.CompletedProcess[str]:
        path = tmp_path / "unit.json"
        path.write_text(json.dumps(new))
        return run("add", str(path), check=False)

    def test_appends_a_pending_unit_that_becomes_ready(
        self, tmp_path: Path, run: Run, dag_path: Path
    ) -> None:
        for uid in ("A_Unit", "B_Unit", "C_Unit"):
            run("mark", uid, "merged")
        run("mark", "D_Unit", "done")
        review = unit(
            "FR-1_Final_Review",
            kind="review",
            skill="mz-dev-git:review-branch",
            owns=[],
            verify="true",
        )

        assert self.add(tmp_path, run, review).stdout == "lint: ok (5 units)\n"
        assert status(dag_path)["FR-1_Final_Review"] == "pending"
        assert run("ready").stdout == "FR-1_Final_Review\n"

    @pytest.mark.parametrize(
        ("new", "message"),
        [
            (unit("A_Unit"), "A_Unit: duplicate id"),
            (unit("E_Unit", "Z_Unit"), "E_Unit: depends on unknown unit Z_Unit"),
            (unit("E_Unit", owns=["src/a/x.py"]), "A_Unit, E_Unit: can run in parallel"),
        ],
        ids=["duplicate", "unknown-dep", "overlap"],
    )
    def test_a_unit_that_breaks_lint_leaves_the_dag_alone(
        self, tmp_path: Path, run: Run, dag_path: Path, new: Unit, message: str
    ) -> None:
        before = dag_path.read_text()
        result = self.add(tmp_path, run, new)

        assert result.returncode == 1
        assert message in result.stderr
        assert dag_path.read_text() == before
        assert not list(tmp_path.glob("dag.json.*"))


class TestRender:
    def test_prints_a_table_counts_and_a_mermaid_graph(
        self, write: Callable[[list[Unit]], None], run: Run
    ) -> None:
        write([unit("WU-1_Add", title='Add "x" | y'), unit("WU-2_Use", "WU-1_Add")])
        run("mark", "WU-1_Add", "merged")
        out = run("render").stdout

        assert (
            '| WU-1_Add | Add "x" \\| y | change | mz-dev-pipe:build | app | auto | - | merged |'
            in out
        )
        assert "merged: 1, pending: 1" in out
        assert "  WU_1_Add[\"WU-1_Add: Add 'x' | y\"]" in out
        assert "  WU_1_Add --> WU_2_Use" in out


class TestSummary:
    def timed(self, uid: str, *deps: str, took: int, **over: object) -> Unit:
        end = int(time.time()) - 60
        return unit(uid, *deps, status="merged", started_at=end - took, ended_at=end, **over)

    def test_counts_waves_and_time_left_from_the_finished_units(
        self, write: Callable[[list[Unit]], None], run: Run
    ) -> None:
        # B has run 10 of the 30 minutes A took; C and D wait on B and share one round.
        started = int(time.time()) - 600 + 30
        write(
            [
                self.timed("A_Unit", took=1800),
                unit("B_Unit", "A_Unit", status="running", started_at=started),
                unit("C_Unit", "B_Unit"),
                unit("D_Unit", "B_Unit", owns=["src/other/*"]),
                unit("E_Unit", "C_Unit", status="blocked"),
            ]
        )

        assert run("summary", "45", "3").stdout == (
            "Run: 1 of 5 units done, 1 running, 2 waiting, 1 blocked; 2 waves left, "
            "about 50m to go (a unit has taken 30m on average over 1)\n"
        )
        assert "about 1h20m to go" in run("summary", "45", "1").stdout

    def test_an_exclusive_unit_takes_a_round_alone(
        self, write: Callable[[list[Unit]], None], run: Run
    ) -> None:
        write([unit("A_Unit"), unit("O_Unit", exclusive=True), unit("B_Unit")])

        assert run("summary", "45", "3").stdout == (
            "Run: 0 of 3 units done, 0 running, 3 waiting; 1 wave left, "
            "about 1h30m to go (no unit has finished yet, so 45m each)\n"
        )

    def test_a_finished_run_has_nothing_left(
        self, write: Callable[[list[Unit]], None], run: Run
    ) -> None:
        write([self.timed("A_Unit", took=600), unit("B_Unit", "A_Unit", status="skipped")])

        assert run("summary", "45", "3").stdout == (
            "Run: 1 of 2 units done, 0 running, 0 waiting, 1 skipped; nothing left to run\n"
        )

    def test_rejects_counts_that_are_not_whole_numbers(
        self, write: Callable[[list[Unit]], None], run: Run
    ) -> None:
        write([unit("A_Unit")])
        result = run("summary", "45m", "3", check=False)

        assert result.returncode == 2
        assert "whole numbers" in result.stderr
