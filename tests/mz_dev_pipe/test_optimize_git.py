import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "plugins/mz-dev-pipe/scripts/optimize-git.sh"
BASH = shutil.which("bash") or "/bin/bash"
ENV = os.environ | {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
}
REF = "refs/mz/optimize/t/iter1-H1"

type Run = Callable[..., subprocess.CompletedProcess[str]]


def git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=cwd, env=ENV, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "app"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    (path / ".gitignore").write_text("*.log\n")
    (path / "app.py").write_text("slow\n")
    (path / "kept.log").write_text("tracked despite the ignore rule\n")
    git(path, "add", "-A")
    git(path, "add", "-f", "kept.log")
    git(path, "commit", "-q", "-m", "base")
    return path


@pytest.fixture
def run(repo: Path) -> Run:
    def _run(*args: str | Path, code: int = 0) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [BASH, str(SCRIPT), *map(str, args)], cwd=repo, env=ENV, capture_output=True, text=True
        )
        assert result.returncode == code, result.stderr
        return result

    return _run


def base_sha(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout.strip().removeprefix("BASE_SHA=")


class TestSnapshot:
    def test_records_the_working_tree_without_touching_index_or_head(
        self, repo: Path, run: Run
    ) -> None:
        head = git(repo, "rev-parse", "HEAD")
        (repo / "app.py").write_text("edited, not staged\n")
        (repo / "new.py").write_text("untracked\n")
        (repo / "noise.log").write_text("ignored\n")

        base = base_sha(run("snapshot", REF, "mz optimize t iter1 H1 base"))

        assert git(repo, "rev-parse", REF) == base
        assert git(repo, "rev-parse", f"{base}^") == head
        assert git(repo, "show", f"{base}:app.py") == "edited, not staged"
        assert git(repo, "show", f"{base}:new.py") == "untracked"
        assert git(repo, "show", f"{base}:kept.log") == "tracked despite the ignore rule"
        assert "noise.log" not in git(repo, "ls-tree", "--name-only", base)
        assert git(repo, "rev-parse", "HEAD") == head
        assert git(repo, "diff", "--cached", "--name-only") == ""


@dataclass(frozen=True)
class Candidate:
    base: str
    head: str


@pytest.fixture
def candidate(repo: Path, tmp_path: Path, run: Run) -> Candidate:
    """A snapshot, and one candidate commit on it that speeds up app.py."""
    base = base_sha(run("snapshot", REF, "base"))
    worktree = tmp_path / "candidate"
    git(repo, "worktree", "add", "-q", "--detach", str(worktree), base)
    (worktree / "app.py").write_text("fast\n")
    git(worktree, "commit", "-q", "-am", "candidate")
    return Candidate(base=base, head=git(worktree, "rev-parse", "HEAD"))


class TestPromote:
    def test_applies_the_candidate_diff_to_the_working_tree_unstaged(
        self, repo: Path, tmp_path: Path, run: Run, candidate: Candidate
    ) -> None:
        patch = tmp_path / "task" / "patches" / "iter1_H1.patch"

        run("promote", candidate.base, candidate.head, patch)

        assert (repo / "app.py").read_text() == "fast\n"
        assert patch.is_file()
        assert git(repo, "diff", "--cached", "--name-only") == ""

    def test_a_patch_that_no_longer_applies_changes_nothing(
        self, repo: Path, tmp_path: Path, run: Run, candidate: Candidate
    ) -> None:
        (repo / "app.py").write_text("changed meanwhile\n")

        run("promote", candidate.base, candidate.head, tmp_path / "p.patch", code=1)

        assert (repo / "app.py").read_text() == "changed meanwhile\n"


class TestSweep:
    def test_removes_candidate_worktrees_branches_and_refs(
        self, repo: Path, tmp_path: Path, run: Run
    ) -> None:
        run("snapshot", REF, "base")
        candidate = tmp_path / "candidate"
        git(repo, "worktree", "add", "-q", "-b", "cand-1", str(candidate))
        git(repo, "worktree", "lock", str(candidate))

        result = run("sweep", "t", "cand-1", candidate, "cand-gone", tmp_path / "missing")

        assert not candidate.exists()
        assert git(repo, "branch", "--list", "cand-1") == ""
        assert git(repo, "for-each-ref", "refs/mz/optimize/t/") == ""
        assert result.stdout.strip().endswith("remaining=0")

    def test_leaves_other_tasks_refs(self, repo: Path, run: Run) -> None:
        run("snapshot", "refs/mz/optimize/other/iter1-H1", "base")
        run("sweep", "t")

        assert git(repo, "for-each-ref", "refs/mz/optimize/other/") != ""
