import json
import shutil
import subprocess
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
        "owns": [f"src/{uid.lower()}/*"],
        "verify": "make test",
        "depends_on": list(deps),
    }
    return base | over


def diamond() -> list[Unit]:
    return [
        unit("A"),
        unit("B", "A"),
        unit("C", "A"),
        unit("D", "B", "C", kind="review", skill="mz-dev-git:review-branch", owns=[]),
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

    @pytest.mark.parametrize(
        ("units", "message"),
        [
            ([unit("A", "B"), unit("B", "A")], "cycle through: A, B"),
            ([unit("A", "Z")], "A: depends on unknown unit Z"),
            ([unit("A", "A")], "A: depends on itself"),
            ([unit("A"), unit("A", owns=["x/*"])], "A: duplicate id"),
            ([unit("A", owns=[])], "A: a change unit needs owns globs"),
            ([unit("A", verify="")], "A: a change unit needs a verify command"),
            ([unit("A", kind="refactor")], "A: kind must be change or review"),
            ([unit("A", repo="app")], "A: repo must be an absolute path"),
            ([unit("A", backend="cloud")], "A: unknown backend cloud"),
            ([unit("A", repo="/other", backend="subagent")], "A: a subagent can only work"),
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
        write([unit("A"), unit("B", owns=["src/a/models.py"])])
        result = run("lint", check=False)

        assert result.returncode == 1
        assert "A, B: can run in parallel but both own src/a/* ~ src/a/models.py" in result.stderr

    @pytest.mark.parametrize(
        "second",
        [
            unit("B", "A", owns=["src/a/models.py"]),
            unit("B", owns=["src/a/*"], repo="/work/other"),
            unit("B", owns=["src/ab/*"]),
        ],
        ids=["ordered-by-a-dependency", "other-repo", "sibling-directory"],
    )
    def test_shared_paths_are_fine_when_units_cannot_collide(
        self, write: Callable[[list[Unit]], None], run: Run, second: Unit
    ) -> None:
        write([unit("A", owns=["src/a/*"]), second])

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
        write([unit("A", kind="review", owns=["web/app.ts"], backend="peer:rev")])

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
        write([unit("A", **({"backend": "peer:rev"} | over))])
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
        write([unit("A", **over)])

        assert run("fits", "A", str(peers)).stdout.split() == expected

    def test_a_peer_running_a_unit_is_not_free(
        self, write: Callable[[list[Unit]], None], run: Run, peers: Path
    ) -> None:
        write([unit("A"), unit("B", owns=["src/other/*"])])
        run("mark", "B", "running", "backend_used=peer:any")

        assert run("fits", "A", str(peers)).stdout.split() == []


class TestScheduling:
    @pytest.fixture(autouse=True)
    def _diamond(self, write: Callable[[list[Unit]], None]) -> None:
        write(diamond())

    def test_only_roots_are_ready_at_the_start(self, run: Run) -> None:
        assert run("ready").stdout.split() == ["A"]

    def test_merging_a_unit_releases_its_dependents(self, run: Run) -> None:
        run("mark", "A", "merged")

        assert run("ready").stdout.split() == ["B", "C"]

    def test_a_failed_dependency_holds_its_dependents(self, run: Run) -> None:
        run("mark", "A", "merged")
        run("mark", "B", "failed")
        run("mark", "C", "merged")

        assert run("ready").stdout.split() == []

    def test_a_finished_review_counts_as_satisfied(
        self, write: Callable[[list[Unit]], None], run: Run
    ) -> None:
        write([unit("R", kind="review", owns=[]), unit("F", "R")])
        run("mark", "R", "done")

        assert run("ready").stdout.split() == ["F"]

    def test_list_prints_the_units_in_one_status(self, run: Run) -> None:
        run("mark", "A", "running")

        assert run("list", "running").stdout.split() == ["A"]
        assert run("list", "pending").stdout.split() == ["B", "C", "D"]

    def test_requeue_does_not_count_the_lost_attempt(self, run: Run, dag_path: Path) -> None:
        run("mark", "A", "running")
        run("requeue", "A")
        run("mark", "A", "running")

        a = json.loads(dag_path.read_text())["units"][0]
        assert (a["status"], a["attempts"]) == ("running", 1)

    def test_mark_running_records_fields_and_counts_attempts(
        self, run: Run, dag_path: Path
    ) -> None:
        run("mark", "A", "running", "base_commit=abc", "branch=orch/t/A")
        run("mark", "A", "running", "note=verifying")
        assert json.loads(dag_path.read_text())["units"][0]["attempts"] == 1

        run("mark", "A", "pending")
        run("mark", "A", "running")
        a = json.loads(dag_path.read_text())["units"][0]
        assert (a["status"], a["base_commit"], a["note"], a["attempts"]) == (
            "running",
            "abc",
            "verifying",
            2,
        )

    @pytest.mark.parametrize(
        ("args", "message"),
        [
            (("A", "busy"), "unknown status 'busy'"),
            (("A", "merged", "status=done"), "mark cannot set 'status'"),
            (("Z", "merged"), "no unit 'Z'"),
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
        run("skip", "B")

        assert status(dag_path) == {"A": "pending", "B": "skipped", "C": "pending", "D": "skipped"}


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
        for uid in "ABC":
            run("mark", uid, "merged")
        run("mark", "D", "done")
        review = unit(
            "FR-1", kind="review", skill="mz-dev-git:review-branch", owns=[], verify="true"
        )

        assert self.add(tmp_path, run, review).stdout == "lint: ok (5 units)\n"
        assert status(dag_path)["FR-1"] == "pending"
        assert run("ready").stdout == "FR-1\n"

    @pytest.mark.parametrize(
        ("new", "message"),
        [
            (unit("A"), "A: duplicate id"),
            (unit("E", "Z"), "E: depends on unknown unit Z"),
            (unit("E", owns=["src/a/x.py"]), "A, E: can run in parallel"),
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
        write([unit("WU-1", title='Add "x" | y'), unit("WU-2", "WU-1")])
        run("mark", "WU-1", "merged")
        out = run("render").stdout

        assert (
            '| WU-1 | Add "x" \\| y | change | mz-dev-pipe:build | app | auto | - | merged |' in out
        )
        assert "merged: 1, pending: 1" in out
        assert "  WU_1[\"WU-1: Add 'x' | y\"]" in out
        assert "  WU_1 --> WU_2" in out
