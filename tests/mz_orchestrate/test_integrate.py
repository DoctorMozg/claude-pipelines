import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2] / "plugins" / "mz-orchestrate" / "scripts" / "integrate.sh"
)
BASH = shutil.which("bash") or "/bin/bash"
ENV = os.environ | {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
}

type Run = Callable[..., subprocess.CompletedProcess[str]]


def git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=cwd, env=ENV, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def fields(stdout: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in stdout.splitlines())


@pytest.fixture
def run() -> Run:
    def _run(
        *args: str | Path, code: int = 0, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [BASH, str(SCRIPT), *map(str, args)], env=ENV, cwd=cwd, capture_output=True, text=True
        )
        assert result.returncode == code, result.stderr
        return result

    return _run


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "app"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    (path / "shared.txt").write_text("one\ntwo\n")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "base")
    return path


@pytest.fixture
def integration(repo: Path, tmp_path: Path, run: Run) -> Path:
    worktree = tmp_path / "integration"
    run("init", repo, "t", worktree)
    return worktree


@pytest.fixture
def session_worktree(repo: Path) -> Path:
    """The worktree a `claude --bg` session isolates into, locked the way Claude Code locks it."""
    path = repo / ".claude" / "worktrees" / "s"
    git(repo, "worktree", "add", "-q", "-b", "worktree-s", str(path))
    git(repo, "worktree", "lock", "--reason", "claude session s (pid 1 start 2)", str(path))
    return path


def unit_branch(repo: Path, tmp_path: Path, name: str, files: dict[str, str]) -> Path:
    """Commits files on orch/t/<name> in its own worktree, branched from the integration tip."""
    worktree = tmp_path / f"unit-{name}"
    git(repo, "worktree", "add", "-q", "-b", f"orch/t/{name}", str(worktree), "orchestrate/t")
    for rel, text in files.items():
        (worktree / rel).parent.mkdir(parents=True, exist_ok=True)
        (worktree / rel).write_text(text)
    git(worktree, "add", "-A")
    git(worktree, "commit", "-q", "-m", f"orch {name}")
    return worktree


class TestInit:
    def test_creates_the_integration_worktree_from_head(
        self, repo: Path, tmp_path: Path, run: Run
    ) -> None:
        out = fields(run("init", repo, "t", tmp_path / "integration").stdout)

        assert out["start_branch"] == "main"
        assert out["start_checkout"] == str(repo)
        assert out["integration_branch"] == "orchestrate/t"
        assert out["tip"] == git(repo, "rev-parse", "HEAD")
        assert out["dirty"] == "no"
        assert git(tmp_path / "integration", "branch", "--show-current") == "orchestrate/t"

    def test_running_again_reuses_it(self, repo: Path, integration: Path, run: Run) -> None:
        out = fields(run("init", repo, "t", integration).stdout)

        assert out["worktree"] == str(integration)

    def test_reports_uncommitted_edits_it_leaves_behind(
        self, repo: Path, tmp_path: Path, run: Run
    ) -> None:
        (repo / "shared.txt").write_text("edited\n")
        out = fields(run("init", repo, "t", tmp_path / "integration").stdout)

        assert out["dirty"] == "yes"
        assert (tmp_path / "integration" / "shared.txt").read_text() == "one\ntwo\n"

    def test_a_claude_session_worktree_starts_from_the_checkout_it_left(
        self, repo: Path, session_worktree: Path, tmp_path: Path, run: Run
    ) -> None:
        (repo / "later.txt").write_text("later\n")
        git(repo, "add", "later.txt")
        git(repo, "commit", "-q", "-m", "later")
        out = fields(run("init", session_worktree, "t", tmp_path / "integration").stdout)

        assert out["start_branch"] == "main"
        assert out["start_checkout"] == str(repo)
        assert out["tip"] == git(repo, "rev-parse", "main")
        assert out["dirty"] == "unknown"

    def test_a_worktree_without_a_session_lock_keeps_its_own_branch(
        self, repo: Path, tmp_path: Path, run: Run
    ) -> None:
        own = repo / ".claude" / "worktrees" / "mine"
        git(repo, "worktree", "add", "-q", "-b", "feature", str(own))
        out = fields(run("init", own, "t", tmp_path / "integration").stdout)

        assert out["start_branch"] == "feature"
        assert out["start_checkout"] == str(own)


class TestMerge:
    def test_a_clean_merge_is_staged_until_concluded(
        self, repo: Path, tmp_path: Path, integration: Path, run: Run
    ) -> None:
        unit_branch(repo, tmp_path, "A", {"a.txt": "a\n"})
        before = git(integration, "rev-parse", "HEAD")

        assert run("merge", integration, "orch/t/A", "orch merge A").stdout == "state=staged\n"
        assert git(integration, "rev-parse", "HEAD") == before
        assert (integration / "a.txt").read_text() == "a\n"

        tip = fields(run("conclude", integration).stdout)["tip"]
        assert tip == git(integration, "rev-parse", "HEAD")
        assert len(git(integration, "rev-list", "--parents", "-n1", "HEAD").split()) == 3
        assert git(integration, "log", "-1", "--format=%s") == "orch merge A"

    def test_a_branch_with_nothing_new_is_up_to_date(
        self, repo: Path, tmp_path: Path, integration: Path, run: Run
    ) -> None:
        git(repo, "branch", "orch/t/R", "orchestrate/t")
        out = fields(run("merge", integration, "orch/t/R", "orch merge R").stdout)

        assert out == {"state": "up-to-date", "tip": git(integration, "rev-parse", "HEAD")}

    def test_a_conflict_exits_3_and_leaves_the_merge_open(
        self, repo: Path, tmp_path: Path, integration: Path, run: Run
    ) -> None:
        unit_branch(repo, tmp_path, "A", {"shared.txt": "one\nA\n"})
        unit_branch(repo, tmp_path, "B", {"shared.txt": "one\nB\n"})
        run("merge", integration, "orch/t/A", "orch merge A")
        run("conclude", integration)
        result = run("merge", integration, "orch/t/B", "orch merge B", code=3)

        assert result.stdout == "conflicted=shared.txt\n"
        blocked = run("merge", integration, "orch/t/C", "again", code=1)
        assert "already in progress" in blocked.stderr

    def test_a_merge_git_refuses_reports_why(
        self, repo: Path, tmp_path: Path, integration: Path, run: Run
    ) -> None:
        unit_branch(repo, tmp_path, "A", {"a.txt": "a\n"})
        (integration / "a.txt").write_text("in the way\n")
        result = run("merge", integration, "orch/t/A", "orch merge A", code=1)

        assert "untracked working tree files would be overwritten" in result.stderr
        assert (integration / "a.txt").read_text() == "in the way\n"

    def test_abort_restores_the_tip(
        self, repo: Path, tmp_path: Path, integration: Path, run: Run
    ) -> None:
        unit_branch(repo, tmp_path, "A", {"shared.txt": "one\nA\n"})
        unit_branch(repo, tmp_path, "B", {"shared.txt": "one\nB\n"})
        run("merge", integration, "orch/t/A", "orch merge A")
        run("conclude", integration)
        tip = git(integration, "rev-parse", "HEAD")
        run("merge", integration, "orch/t/B", "orch merge B", code=3)
        run("abort", integration)

        assert git(integration, "rev-parse", "HEAD") == tip
        assert git(integration, "status", "--porcelain") == ""

    def test_conclude_commits_a_resolved_merge(
        self, repo: Path, tmp_path: Path, integration: Path, run: Run
    ) -> None:
        unit_branch(repo, tmp_path, "A", {"shared.txt": "one\nA\n"})
        unit_branch(repo, tmp_path, "B", {"shared.txt": "one\nB\n"})
        run("merge", integration, "orch/t/A", "orch merge A")
        run("conclude", integration)
        run("merge", integration, "orch/t/B", "orch merge B", code=3)
        (integration / "shared.txt").write_text("one\nA\nB\n")
        git(integration, "add", "shared.txt")
        tip = fields(run("conclude", integration).stdout)["tip"]

        assert tip == git(integration, "rev-parse", "HEAD")
        assert git(integration, "log", "-1", "--format=%s") == "orch merge B"

    @pytest.mark.parametrize(
        ("resolution", "stage", "message"),
        [
            ("one\n<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> orch/t/B\n", True, "conflict markers"),
            ("one\nA\nB\n", False, "still unmerged: shared.txt"),
        ],
        ids=["markers-left", "not-staged"],
    )
    def test_conclude_refuses_an_unfinished_resolution(
        self,
        repo: Path,
        tmp_path: Path,
        integration: Path,
        run: Run,
        resolution: str,
        stage: bool,
        message: str,
    ) -> None:
        unit_branch(repo, tmp_path, "A", {"shared.txt": "one\nA\n"})
        unit_branch(repo, tmp_path, "B", {"shared.txt": "one\nB\n"})
        run("merge", integration, "orch/t/A", "orch merge A")
        run("conclude", integration)
        run("merge", integration, "orch/t/B", "orch merge B", code=3)
        (integration / "shared.txt").write_text(resolution)
        if stage:
            git(integration, "add", "shared.txt")

        assert message in run("conclude", integration, code=1).stderr


class TestLand:
    def test_fast_forwards_the_start_branch_to_the_integration_tip(
        self, repo: Path, tmp_path: Path, integration: Path, run: Run
    ) -> None:
        unit_branch(repo, tmp_path, "A", {"a.txt": "a\n"})
        run("merge", integration, "orch/t/A", "orch merge A")
        tip = fields(run("conclude", integration).stdout)["tip"]

        assert fields(run("land", repo, "main", "orchestrate/t").stdout) == {"tip": tip}
        assert (repo / "a.txt").read_text() == "a\n"

    def test_refuses_until_the_start_branch_is_merged_in(
        self, repo: Path, integration: Path, run: Run
    ) -> None:
        (repo / "later.txt").write_text("later\n")
        git(repo, "add", "later.txt")
        git(repo, "commit", "-q", "-m", "later")
        main = git(repo, "rev-parse", "main")

        assert (
            "merge main into orchestrate/t first"
            in run("land", repo, "main", "orchestrate/t", code=1).stderr
        )
        assert git(repo, "rev-parse", "main") == main

    def test_refuses_a_checkout_on_another_branch(
        self, repo: Path, integration: Path, run: Run
    ) -> None:
        git(repo, "checkout", "-q", "-b", "other")

        assert "is on other, not main" in run("land", repo, "main", "orchestrate/t", code=1).stderr

    def test_keeps_uncommitted_edits_it_would_overwrite(
        self, repo: Path, tmp_path: Path, integration: Path, run: Run
    ) -> None:
        unit_branch(repo, tmp_path, "A", {"shared.txt": "one\nA\n"})
        run("merge", integration, "orch/t/A", "orch merge A")
        run("conclude", integration)
        (repo / "shared.txt").write_text("mine\n")
        main = git(repo, "rev-parse", "main")

        run("land", repo, "main", "orchestrate/t", code=1)
        assert git(repo, "rev-parse", "main") == main
        assert (repo / "shared.txt").read_text() == "mine\n"

    def test_a_session_worktree_may_not_land_in_the_checkout_it_left(
        self, repo: Path, session_worktree: Path, tmp_path: Path, run: Run
    ) -> None:
        integration = tmp_path / "integration"
        run("init", session_worktree, "t", integration)
        unit_branch(repo, tmp_path, "A", {"a.txt": "a\n"})
        run("merge", integration, "orch/t/A", "orch merge A")
        run("conclude", integration)
        main = git(repo, "rev-parse", "main")

        result = run("land", repo, "main", "orchestrate/t", code=1, cwd=session_worktree)
        assert f"git -C {repo} merge --ff-only orchestrate/t" in result.stderr
        assert git(repo, "rev-parse", "main") == main


class TestScope:
    def test_lists_only_files_outside_owns(
        self, repo: Path, tmp_path: Path, integration: Path, run: Run
    ) -> None:
        base = git(integration, "rev-parse", "HEAD")
        files = {"src/api/v1/routes.py": "", "src/api.py": "", "shared.txt": "x\n"}
        unit_branch(repo, tmp_path, "A", files)
        out = run("scope", repo, base, "orch/t/A", "src/api/*", "tests/*").stdout

        assert out.split() == ["shared.txt", "src/api.py"]


class TestCleanup:
    def test_removes_a_merged_unit(
        self, repo: Path, tmp_path: Path, integration: Path, run: Run
    ) -> None:
        worktree = unit_branch(repo, tmp_path, "A", {"a.txt": "a\n"})
        git(repo, "worktree", "lock", str(worktree))
        run("merge", integration, "orch/t/A", "orch merge A")
        run("conclude", integration)
        run("cleanup", repo, worktree, "orch/t/A", "orchestrate/t")

        assert not worktree.exists()
        assert git(repo, "branch", "--list", "orch/t/A") == ""

    def test_keeps_an_unmerged_unit(
        self, repo: Path, tmp_path: Path, integration: Path, run: Run
    ) -> None:
        worktree = unit_branch(repo, tmp_path, "A", {"a.txt": "a\n"})
        result = run("cleanup", repo, worktree, "orch/t/A", "orchestrate/t", code=1)

        assert "not merged" in result.stderr
        assert worktree.exists()
        assert git(repo, "branch", "--list", "orch/t/A") != ""
