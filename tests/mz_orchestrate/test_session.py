import json
import os
import shutil
import socket
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2] / "plugins" / "mz-orchestrate" / "scripts" / "session.sh"
)
BASH = shutil.which("bash") or "/bin/bash"

# Records a run's arguments, working directory and stdin; answers agents, stop and purge from env.
FAKE_CLAUDE = """#!/usr/bin/env bash
case $1 in
agents) printf '%s' "${FAKE_AGENTS:-[]}"; exit 0 ;;
stop) echo "$2" >> "$FAKE_LOG.stopped"; exit "${FAKE_STOP_EXIT:-0}" ;;
purge) echo "$*" >> "$FAKE_LOG.purged"; echo "${FAKE_PURGE_OUT:-}"; exit "${FAKE_PURGE_EXIT:-0}" ;;
esac
printf '%s\\n' "$@" > "$FAKE_LOG.args"
pwd > "$FAKE_LOG.cwd"
[ "$1" = --bg ] || cat > "$FAKE_LOG.stdin"
printf '%s' "$FAKE_OUTPUT"
exit "${FAKE_EXIT:-0}"
"""
SELF_PID = "100"
WORKER_PID = "200"

type Run = Callable[..., subprocess.CompletedProcess[str]]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "app"
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


@pytest.fixture
def envelope(tmp_path: Path) -> Path:
    path = tmp_path / "unit.txt"
    path.write_text("ORCH-UNIT v1\nunit: WU-1\nEND ORCH-UNIT\n")
    return path


@pytest.fixture
def log(tmp_path: Path) -> Path:
    return tmp_path / "claude"


@pytest.fixture
def run(tmp_path: Path, log: Path) -> Run:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(FAKE_CLAUDE)
    fake.chmod(0o755)

    def _run(
        *args: str | Path, code: int = 0, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        full_env = os.environ | {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "FAKE_LOG": str(log),
            "FAKE_OUTPUT": json.dumps({"is_error": False, "result": "ORCH-RESULT v1"}),
        }
        result = subprocess.run(
            [BASH, str(SCRIPT), *map(str, args)],
            env=full_env | (env or {}),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == code, result.stderr
        return result

    return _run


@pytest.fixture
def runtime() -> Iterator[Path]:
    # AF_UNIX paths are capped near 108 bytes, so the sockets live in a short temp dir.
    with tempfile.TemporaryDirectory(prefix="cc") as tmp:
        socks = Path(tmp) / "cc-socks"
        socks.mkdir()
        bound = []
        for pid in (SELF_PID, WORKER_PID):
            sock = socket.socket(socket.AF_UNIX)
            sock.bind(str(socks / f"{pid}.sock"))
            bound.append(sock)
        yield Path(tmp)
        for sock in bound:
            sock.close()


def agents(*rows: tuple[str, str, str, str]) -> str:
    keys = ("id", "sessionId", "pid", "status")
    return json.dumps([dict(zip(keys, row, strict=True)) for row in rows])


BG_ENV = {
    "CLAUDE_CODE_SESSION_ID": "self-sid",
    "FAKE_OUTPUT": "backgrounded · ab12cd34 · orch-t-WU-1\n  claude logs ab12cd34\n",
    "FAKE_AGENTS": agents(
        ("me", "self-sid", SELF_PID, "busy"), ("ab12cd34", "w-sid", WORKER_PID, "busy")
    ),
}


def fields(stdout: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in stdout.splitlines())


class TestRun:
    def test_starts_a_headless_worktree_session_with_the_envelope(
        self, run: Run, repo: Path, envelope: Path, log: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "out.json"
        result = fields(run("run", repo, "orch-t-WU-1", "mz-dev-pipe:build", envelope, out).stdout)

        args = log.with_suffix(".args").read_text().splitlines()
        assert args[:3] == ["-p", "-w", "orch-t-WU-1"]
        assert args[args.index("--permission-prompts") + 1] == "none"
        assert "Skill(mz-orchestrate:orchestrate-worker)" in args
        assert "Skill(mz-dev-pipe:build)" in args
        assert log.with_suffix(".cwd").read_text().strip() == str(repo)
        assert log.with_suffix(".stdin").read_text() == envelope.read_text()
        assert json.loads(out.read_text())["result"] == "ORCH-RESULT v1"
        assert result == {
            "worktree": f"{repo}/.claude/worktrees/orch-t-WU-1",
            "worktree_branch": "worktree-orch-t-WU-1",
            "exit": "0",
        }

    def test_a_direct_unit_approves_only_the_worker_skill(
        self, run: Run, repo: Path, envelope: Path, log: Path, tmp_path: Path
    ) -> None:
        run("run", repo, "orch-t-WU-1", "direct", envelope, tmp_path / "out.json")

        args = log.with_suffix(".args").read_text().splitlines()
        assert [a for a in args if a.startswith("Skill(")] == [
            "Skill(mz-orchestrate:orchestrate-worker)"
        ]

    def test_passes_development_arguments_through(
        self, run: Run, repo: Path, envelope: Path, log: Path, tmp_path: Path
    ) -> None:
        env = {"MZ_ORCHESTRATE_WORKER_ARGS": "--plugin-dir /p/a --model sonnet"}
        run("run", repo, "n", "direct", envelope, tmp_path / "out.json", env=env)

        args = log.with_suffix(".args").read_text().splitlines()
        assert args[-4:] == ["--plugin-dir", "/p/a", "--model", "sonnet"]

    def test_reports_the_session_exit_code_without_failing(
        self, run: Run, repo: Path, envelope: Path, tmp_path: Path
    ) -> None:
        out = run("run", repo, "n", "direct", envelope, tmp_path / "o.json", env={"FAKE_EXIT": "1"})

        assert fields(out.stdout)["exit"] == "1"

    @pytest.mark.parametrize(
        ("name", "message"),
        [("a b", "may hold only"), ("../x", "may hold only")],
    )
    def test_refuses_an_unsafe_worktree_name(
        self, run: Run, repo: Path, envelope: Path, tmp_path: Path, name: str, message: str
    ) -> None:
        result = run("run", repo, name, "direct", envelope, tmp_path / "o.json", code=1)

        assert message in result.stderr


class TestBg:
    def test_starts_a_bg_worktree_session_that_replies_to_this_one(
        self, run: Run, repo: Path, envelope: Path, log: Path, runtime: Path
    ) -> None:
        env = BG_ENV | {"XDG_RUNTIME_DIR": str(runtime)}
        result = fields(
            run("bg", repo, "orch-t-WU-1", "mz-dev-pipe:build", envelope, env=env).stdout
        )

        args = log.with_suffix(".args").read_text().splitlines()
        assert args[:5] == ["--bg", "--name", "orch-t-WU-1", "--worktree", "orch-t-WU-1"]
        assert args[args.index("--permission-prompts") + 1] == "none"
        assert "Skill(mz-dev-pipe:build)" in args
        reply_to = f"uds:{runtime}/cc-socks/{SELF_PID}.sock"
        # The fake logs one argument per line, so the multi-line prompt spans the rest of the log.
        assert "\n".join(args[args.index("--") + 1 :]) == (
            f"ORCH-UNIT v1\nreply-to: {reply_to}\nunit: WU-1\nEND ORCH-UNIT"
        )
        assert log.with_suffix(".cwd").read_text().strip() == str(repo)
        assert result == {
            "id": "ab12cd34",
            "address": f"uds:{runtime}/cc-socks/{WORKER_PID}.sock",
            "reply_to": reply_to,
            "worktree": f"{repo}/.claude/worktrees/orch-t-WU-1",
            "worktree_branch": "worktree-orch-t-WU-1",
        }

    def test_an_untrusted_repo_falls_back_with_exit_3(
        self, run: Run, repo: Path, envelope: Path, runtime: Path
    ) -> None:
        env = BG_ENV | {
            "XDG_RUNTIME_DIR": str(runtime),
            "FAKE_OUTPUT": "Workspace not trusted. Run `claude` in /x once.",
            "FAKE_EXIT": "1",
        }
        result = run("bg", repo, "n", "direct", envelope, code=3, env=env)

        assert "not a trusted workspace" in result.stderr

    def test_no_reply_address_falls_back_before_starting_anything(
        self, run: Run, repo: Path, envelope: Path, log: Path, runtime: Path
    ) -> None:
        env = BG_ENV | {"XDG_RUNTIME_DIR": str(runtime / "missing")}
        result = run("bg", repo, "n", "direct", envelope, code=3, env=env)

        assert "no socket for this session" in result.stderr
        assert not log.with_suffix(".args").exists()

    def test_any_other_start_failure_is_loud(
        self, run: Run, repo: Path, envelope: Path, runtime: Path
    ) -> None:
        env = BG_ENV | {
            "XDG_RUNTIME_DIR": str(runtime),
            "FAKE_OUTPUT": "daemon unreachable",
            "FAKE_EXIT": "1",
        }
        result = run("bg", repo, "n", "direct", envelope, code=1, env=env)

        assert "claude --bg failed: daemon unreachable" in result.stderr


class TestStateAndStop:
    @pytest.mark.parametrize(("sid", "expected"), [("ab12cd34", "busy"), ("zz", "gone")])
    def test_state_reports_the_listed_status_or_gone(
        self, run: Run, sid: str, expected: str
    ) -> None:
        assert run("state", sid, env=BG_ENV).stdout == f"{expected}\n"

    def test_stop_tolerates_a_session_that_already_ended(self, run: Run, log: Path) -> None:
        env = {"FAKE_STOP_EXIT": "1", "FAKE_AGENTS": "[]"}

        assert run("stop", "ab12cd34", env=env).stdout == "stopped ab12cd34\n"
        assert log.with_suffix(".stopped").read_text() == "ab12cd34\n"

    def test_stop_fails_when_the_session_keeps_running(self, run: Run) -> None:
        env = BG_ENV | {"FAKE_STOP_EXIT": "1"}

        assert "could not stop session ab12cd34" in run("stop", "ab12cd34", code=1, env=env).stderr


class TestForget:
    WORKTREE = "/r/app/.claude/worktrees/orch-t-WU-1_Add.2"

    def test_purges_the_sessions_of_a_worker_worktree(self, run: Run, log: Path) -> None:
        assert run("forget", f"{self.WORKTREE}/").stdout == f"forgot {self.WORKTREE}\n"
        assert log.with_suffix(".purged").read_text() == f"purge -y {self.WORKTREE}\n"

    def test_a_worktree_with_no_sessions_is_not_an_error(self, run: Run) -> None:
        env = {"FAKE_PURGE_EXIT": "1", "FAKE_PURGE_OUT": "No Claude Code project data found for x"}

        assert run("forget", self.WORKTREE, env=env).stdout.startswith("nothing to forget")

    def test_any_other_purge_failure_is_loud(self, run: Run) -> None:
        env = {"FAKE_PURGE_EXIT": "1", "FAKE_PURGE_OUT": "permission denied"}

        assert "permission denied" in run("forget", self.WORKTREE, code=1, env=env).stderr

    @pytest.mark.parametrize(
        "path",
        [
            "/r/app",
            "/r/app/.claude/worktrees/feature",
            "/r/app/.claude/worktrees/orch-t-WU-1/..",
            "/r/app/.claude/worktrees/orch-t-WU-1/sub",
        ],
    )
    def test_refuses_any_path_but_a_worker_worktree(self, run: Run, log: Path, path: str) -> None:
        assert "is not a worker worktree" in run("forget", path, code=1).stderr
        assert not log.with_suffix(".purged").exists()


class TestClaudeBinary:
    @pytest.fixture
    def wrapper(self, tmp_path: Path, log: Path) -> Path:
        path = tmp_path / "gnai-claude"
        path.write_text(f'#!/usr/bin/env bash\necho "$1" >> "{log}.wrapped"\nexec claude "$@"\n')
        path.chmod(0o755)
        return path

    def test_every_call_goes_through_the_named_wrapper(
        self, run: Run, repo: Path, envelope: Path, log: Path, tmp_path: Path, wrapper: Path
    ) -> None:
        env = {"MZ_ORCHESTRATE_CLAUDE": str(wrapper), "FAKE_AGENTS": "[]"}
        run("run", repo, "n", "direct", envelope, tmp_path / "out.json", env=env)
        run("stop", "ab12cd34", env=env)
        run("forget", "/r/app/.claude/worktrees/orch-t-WU-1", env=env)

        assert log.with_suffix(".wrapped").read_text().splitlines() == ["-p", "stop", "purge"]

    def test_a_missing_wrapper_fails_before_starting_anything(
        self, run: Run, repo: Path, envelope: Path, log: Path, tmp_path: Path
    ) -> None:
        env = {"MZ_ORCHESTRATE_CLAUDE": "no-such-claude"}
        result = run("run", repo, "n", "direct", envelope, tmp_path / "o.json", code=1, env=env)

        assert "'no-such-claude' is not on PATH" in result.stderr
        assert not log.with_suffix(".args").exists()


class TestResult:
    def test_prints_the_final_text(self, run: Run, tmp_path: Path) -> None:
        out = tmp_path / "out.json"
        out.write_text(json.dumps({"is_error": False, "result": "ORCH-RESULT v1\nEND"}))

        assert run("result", out).stdout == "ORCH-RESULT v1\nEND\n"

    @pytest.mark.parametrize(
        ("body", "message"),
        [
            ("", "no session output"),
            ("not json", "is not the JSON"),
            (
                json.dumps({"is_error": True, "subtype": "error_max_turns"}),
                "ended without a result: error_max_turns",
            ),
        ],
        ids=["empty", "garbage", "error"],
    )
    def test_fails_loudly_without_a_result(
        self, run: Run, tmp_path: Path, body: str, message: str
    ) -> None:
        out = tmp_path / "out.json"
        out.write_text(body)

        assert message in run("result", out, code=1).stderr


GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
UNIT_STATE = """schema_version: 2
Status: running
Phase: 3
PhaseName: implementation
worker_unit: .mz/orchestrate/units/WU-1.md
phase_complete: false
what_remains:
  - write the tests
  - run the review
"""


def write_state(worktree: Path, name: str, body: str) -> Path:
    path = worktree / ".mz" / "task" / name / "state.md"
    path.parent.mkdir(parents=True)
    path.write_text(body)
    return path


class TestProgress:
    @pytest.fixture
    def worktree(self, repo: Path) -> Path:
        (repo / "a.txt").write_text("a\n")
        (repo / ".gitignore").write_text(".mz/\n")
        subprocess.run([*GIT, "-C", str(repo), "add", "a.txt", ".gitignore"], check=True)
        subprocess.run([*GIT, "-C", str(repo), "commit", "-qm", "base"], check=True)
        return repo

    @pytest.fixture
    def base(self, worktree: Path) -> str:
        return subprocess.run(
            ["git", "-C", str(worktree), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    def progress(self, run: Run, worktree: Path, base: str) -> dict[str, str]:
        lines = run("progress", worktree, base).stdout.splitlines()
        return dict(line.split(": ", 1) for line in lines)

    def test_reads_the_skill_state_that_names_a_worker_unit(
        self, run: Run, worktree: Path, base: str
    ) -> None:
        state = write_state(worktree, "2026_11_25_build_wu_1", UNIT_STATE)
        # The worker's own state has no worker_unit line and must not be picked.
        write_state(worktree, "2026_11_25_orchestrate_worker_wu_1", "Status: running\nPhase: x\n")
        os.utime(state, (1, 1))

        got = self.progress(run, worktree, base)

        assert got["state"] == str(state)
        assert got["phase"] == "3 implementation"
        assert got["what_remains"] == "write the tests; run the review"
        assert int(got["state_age"]) > 1_000_000

    def test_a_worktree_without_a_unit_state_reports_none(
        self, run: Run, worktree: Path, base: str
    ) -> None:
        write_state(worktree, "2026_11_25_orchestrate_worker_wu_1", "Status: running\n")

        got = self.progress(run, worktree, base)

        assert got == {"state": "none", "changed": "0", "last_commit": "none"}

    def test_counts_changed_files(self, run: Run, worktree: Path, base: str) -> None:
        (worktree / "a.txt").write_text("edited\n")
        (worktree / "b.txt").write_text("new\n")

        assert self.progress(run, worktree, base)["changed"] == "2"

    def test_names_the_head_commit_once_it_moves_past_the_base(
        self, run: Run, worktree: Path, base: str
    ) -> None:
        (worktree / "a.txt").write_text("edited\n")
        subprocess.run([*GIT, "-C", str(worktree), "commit", "-qam", "unit: edit a"], check=True)

        last = self.progress(run, worktree, base)["last_commit"]

        assert last.split(" ", 1)[1] == "unit: edit a"

    def test_a_missing_worktree_fails_loudly(self, run: Run, tmp_path: Path) -> None:
        result = run("progress", tmp_path / "gone", "abc", code=1)

        assert "no worktree at" in result.stderr
