import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "plugins" / "mz-orchestrate" / "scripts" / "codex.sh"
BASH = shutil.which("bash") or "/bin/bash"

# Answers `plugin list` from env; for `exec`, logs its arguments, copies the brief, writes
# FAKE_FILES (space-separated paths) into the worktree and FAKE_LAST to the -o file.
FAKE_CODEX = """#!/usr/bin/env bash
if [ "$1 $2" = "plugin list" ]; then printf '%s\\n' "${FAKE_PLUGINS:-}"; exit 0; fi
printf '%s\\n' "$@" > "$FAKE_LOG.args"
dir= last=
while [ $# -gt 0 ]; do
  case $1 in -C) dir=$2; shift ;; -o) last=$2; shift ;; esac
  shift
done
cp "$dir/.mz/orchestrate/unit.md" "$FAKE_LOG.brief"
cd "$dir"
for f in ${FAKE_FILES:-}; do mkdir -p "$(dirname "$f")"; echo changed > "$f"; done
printf '%s' "${FAKE_LAST:-}" > "$last"
exit "${FAKE_EXIT:-0}"
"""
INSTALLED = "mz-dev-pipe@mozg-pipelines       installed, enabled  0.59.0   /x/mz-dev-pipe"
DONE = "Added calc/mul.py.\nSTATUS: DONE"

type Run = Callable[..., subprocess.CompletedProcess[str]]


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "app"
    (path / "calc").mkdir(parents=True)
    (path / "calc" / "ops.py").write_text("def add(a, b):\n    return a + b\n")
    git(path.parent, "init", "-q", str(path))
    git(path, "config", "user.name", "t")
    git(path, "config", "user.email", "t@example.invalid")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "base")
    return path


@pytest.fixture
def envelope(tmp_path: Path, repo: Path) -> Callable[..., Path]:
    def _envelope(
        kind: str = "change", skill: str = "mz-dev-pipe:build", verify: str = "true"
    ) -> Path:
        path = tmp_path / "unit.envelope"
        path.write_text(
            "ORCH-UNIT v1 (handle with mz-orchestrate:orchestrate-worker)\n"
            f"task: t1\nunit: WU-1\ntitle: mul module\nkind: {kind}\nskill: {skill}\n"
            f"repo: {repo}\nbase-commit: {git(repo, 'rev-parse', 'HEAD')}\n"
            f"branch: orch/t1/WU-1\nowns: calc/mul.py, tests/test_mul.py\nverify: {verify}\n"
            "deadline: 2026-11-23T12:00:00Z\n--- spec ---\nAdd mul(a, b).\nEND ORCH-UNIT\n"
        )
        return path

    return _envelope


@pytest.fixture
def run(tmp_path: Path, repo: Path) -> Run:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "codex"
    fake.write_text(FAKE_CODEX)
    fake.chmod(0o755)

    def _run(
        envelope: Path, code: int = 0, env: dict[str, str] | None = None, name: str = "orch-t1-WU-1"
    ) -> subprocess.CompletedProcess[str]:
        full_env = os.environ | {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "FAKE_LOG": str(tmp_path / "codex"),
            "FAKE_PLUGINS": INSTALLED,
            "FAKE_LAST": DONE,
            "FAKE_FILES": "calc/mul.py",
        }
        result = subprocess.run(
            [BASH, str(SCRIPT), str(repo), name, str(envelope), str(tmp_path / "out")],
            env=full_env | (env or {}),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == code, result.stderr
        return result

    return _run


def fields(stdout: str) -> dict[str, str]:
    head = stdout.split("--- notes ---")[0]
    return dict(line.split(": ", 1) for line in head.splitlines()[1:] if ": " in line)


def notes(stdout: str) -> str:
    return stdout.split("--- notes ---\n")[1].split("\n--- report ---")[0]


class TestDispatch:
    def test_runs_the_skill_in_a_sandboxed_worktree_on_the_unit_branch(
        self, run: Run, envelope: Callable[..., Path], repo: Path, tmp_path: Path
    ) -> None:
        run(envelope())
        worktree = repo / ".claude" / "worktrees" / "orch-t1-WU-1"
        args = (tmp_path / "codex.args").read_text().splitlines()
        assert args[:7] == ["exec", "-C", str(worktree), "-s", "workspace-write", "--json", "-o"]
        assert "--ephemeral" not in args
        assert (
            "Use the mz-dev-pipe:build skill with the argument unit:.mz/orchestrate/unit.md"
            in args[-1]
        )
        assert git(worktree, "branch", "--show-current") == "orch/t1/WU-1"
        brief = (tmp_path / "codex.brief").read_text()
        assert "- owns: calc/mul.py, tests/test_mul.py" in brief
        assert brief.rstrip().endswith("## Spec\n\nAdd mul(a, b).")

    def test_a_direct_unit_gets_the_work_itself_without_a_plugin_check(
        self, run: Run, envelope: Callable[..., Path], tmp_path: Path
    ) -> None:
        out = run(envelope(skill="direct"), env={"FAKE_PLUGINS": ""})
        assert fields(out.stdout)["status"] == "DONE"
        assert (
            (tmp_path / "codex.args").read_text().splitlines()[-1].startswith("Carry out the unit")
        )

    def test_passes_extra_arguments_through(
        self, run: Run, envelope: Callable[..., Path], tmp_path: Path
    ) -> None:
        run(envelope(), env={"MZ_ORCHESTRATE_CODEX_ARGS": "-m gpt-test"})
        assert "-m\ngpt-test\n" in (tmp_path / "codex.args").read_text()


class TestChangeResult:
    def test_commits_only_owned_paths_and_reports_the_commit(
        self, run: Run, envelope: Callable[..., Path], repo: Path
    ) -> None:
        out = run(envelope(), env={"FAKE_FILES": "calc/mul.py stray.txt"})
        result = fields(out.stdout)
        worktree = repo / ".claude" / "worktrees" / "orch-t1-WU-1"
        assert result["status"] == "DONE"
        assert result["verify"] == "pass"
        assert result["files"] == "calc/mul.py"
        assert result["head-commit"] == git(worktree, "rev-parse", "HEAD")
        assert git(worktree, "log", "-1", "--format=%s") == "orch WU-1: mul module"
        assert git(worktree, "status", "--porcelain", "--untracked-files=all", "--", "stray.txt")

    def test_a_failing_verify_is_reported_not_hidden(
        self, run: Run, envelope: Callable[..., Path]
    ) -> None:
        assert fields(run(envelope(verify="exit 1")).stdout)["verify"] == "fail"

    def test_no_changes_downgrades_done(self, run: Run, envelope: Callable[..., Path]) -> None:
        out = run(envelope(), env={"FAKE_FILES": ""})
        assert fields(out.stdout)["status"] == "DONE_WITH_CONCERNS"
        assert notes(out.stdout).startswith("no changes")

    @pytest.mark.parametrize(
        "env",
        [{"FAKE_LAST": "I gave up."}, {"FAKE_EXIT": "1", "FAKE_LAST": ""}],
        ids=["no-status-line", "codex-failed"],
    )
    def test_a_run_without_a_status_line_fails(
        self, run: Run, envelope: Callable[..., Path], env: dict[str, str]
    ) -> None:
        out = run(envelope(), env=env)
        assert fields(out.stdout)["status"] == "FAILED"
        assert "without a STATUS line" in notes(out.stdout)


class TestReviewResult:
    def test_returns_the_findings_without_committing(
        self, run: Run, envelope: Callable[..., Path], repo: Path
    ) -> None:
        last = "Critical: calc/ops.py:2 add ignores overflow.\nSTATUS: DONE_WITH_CONCERNS"
        out = run(
            envelope(kind="review", skill="mz-dev-git:review-branch"),
            env={
                "FAKE_LAST": last,
                "FAKE_FILES": "",
                "FAKE_PLUGINS": "mz-dev-git@m  installed, enabled  1 /x",
            },
        )
        result = fields(out.stdout)
        assert (result["status"], result["verify"], result["head-commit"]) == (
            "DONE_WITH_CONCERNS",
            "not-run",
            "none",
        )
        assert notes(out.stdout) == "Critical: calc/ops.py:2 add ignores overflow."


class TestContextResult:
    @pytest.mark.parametrize("named", [".mz/research/r.md", "`{wt}/.mz/research/r.md`"])
    def test_hands_back_the_named_report_in_full(
        self, run: Run, envelope: Callable[..., Path], repo: Path, named: str
    ) -> None:
        wt = repo / ".claude" / "worktrees" / "orch-t1-WU-1"
        last = f"Retry-After applies.\n## Report\n{named.format(wt=wt)}\nSTATUS: DONE"
        out = run(
            envelope(kind="context", skill="mz-research-pipe:deep-research"),
            env={
                "FAKE_LAST": last,
                "FAKE_FILES": ".mz/research/r.md",
                "FAKE_PLUGINS": "mz-research-pipe@m  installed, enabled  1 /x",
            },
        )
        result = fields(out.stdout)
        assert (result["status"], result["report"]) == ("DONE", f"{wt}/.mz/research/r.md")
        assert out.stdout.split("--- report ---\n")[1].startswith("changed\nEND ORCH-RESULT")

    def test_a_missing_report_file_sends_none(
        self, run: Run, envelope: Callable[..., Path]
    ) -> None:
        out = run(
            envelope(kind="context", skill="mz-research-pipe:explain"),
            env={
                "FAKE_LAST": "## Report\n.mz/nowhere.md\nSTATUS: DONE",
                "FAKE_FILES": "",
                "FAKE_PLUGINS": "mz-research-pipe@m  installed, enabled  1 /x",
            },
        )
        assert fields(out.stdout)["report"] == "none"


class TestRefusal:
    def test_a_skill_missing_from_codex_is_refused_before_any_worktree(
        self, run: Run, envelope: Callable[..., Path], repo: Path, tmp_path: Path
    ) -> None:
        out = run(envelope(), env={"FAKE_PLUGINS": "mz-dev-pipe@m  not installed  /x"})
        result = fields(out.stdout)
        assert (result["status"], result["worktree"]) == ("REFUSED", "none")
        assert "skill not installed" in notes(out.stdout)
        assert not (tmp_path / "codex.args").exists()
        assert not (repo / ".claude").exists()

    def test_refuses_an_unsafe_worktree_name(self, run: Run, envelope: Callable[..., Path]) -> None:
        assert "worktree name" in run(envelope(), code=1, name="../x").stderr

    def test_fails_loudly_without_the_codex_cli(
        self, envelope: Callable[..., Path], repo: Path, tmp_path: Path
    ) -> None:
        git_dir = Path(shutil.which("git") or "/usr/bin/git").parent
        path = os.pathsep.join([str(git_dir), "/usr/bin", "/bin"])
        if shutil.which("codex", path=path):
            pytest.skip("a codex CLI is installed system-wide")
        result = subprocess.run(
            [BASH, str(SCRIPT), str(repo), "n", str(envelope()), str(tmp_path / "out")],
            env=os.environ | {"PATH": path},
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        assert "codex CLI is not on PATH" in result.stderr
