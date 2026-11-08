import importlib
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

import pytest

from mozg_pipelines.hooks_probe import codex_version, probe_hooks

_FAKE_CODEX = """
import json
import os
import pathlib
import subprocess
import sys
import time

args = sys.argv[1:]
home = pathlib.Path(os.environ["CODEX_HOME"])
mode = os.environ.get("FAKE_CODEX_MODE", "native")
audit = pathlib.Path(os.environ["FAKE_CODEX_AUDIT"])
with audit.open("a") as stream:
    stream.write(json.dumps({"args": args, "home": str(home),
        "auth_link": (home / "auth.json").is_symlink(),
        "inherited_codex": "CODEX_UNSAFE_TEST" in os.environ,
        "inherited_roots": [key for key in os.environ
            if key.startswith(("GIT_", "MZ_", "CLAUDE_", "EVAL_"))]}) + "\\n")
if args == ["--version"]:
    print("codex-cli 0.165.0")
    raise SystemExit(0)
if args[:3] == ["plugin", "marketplace", "add"]:
    if mode == "install-failure":
        print("sensitive-server-details", file=sys.stderr)
        raise SystemExit(1)
    (home / "fake-marketplace").write_text(args[3])
    raise SystemExit(0)
if args[:2] == ["plugin", "add"]:
    marketplace = pathlib.Path((home / "fake-marketplace").read_text())
    manifest = json.loads((marketplace / "packages/probe/plugin.json").read_text())
    if mode == "missing-manifest" or manifest.get("$schema") != (
        "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    ):
        print("Error: missing plugin.json; private-details", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(0)
if args[0] != "exec":
    raise SystemExit(2)
if mode == "timeout":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    audit.with_suffix(".child-pid").write_text(str(child.pid))
    time.sleep(30)
is_control = (home / "hooks.json").exists()
if mode == "network-failure" or (mode == "control-failure" and is_control):
    print("credentials-and-network-private-details", file=sys.stderr)
    raise SystemExit(1)
workspace = pathlib.Path(args[args.index("--cd") + 1])
if is_control:
    hooks = json.loads((home / "hooks.json").read_text())["hooks"]
else:
    marketplace = pathlib.Path((home / "fake-marketplace").read_text())
    hooks = json.loads((marketplace / "packages/probe/hooks/hooks.json").read_text())["hooks"]
enabled = is_control or mode in {
    "native", "partial", "missing-tool", "missing-stop", "malformed-markers"
}
nonce = "UNKNOWN"
if enabled:
    for event in ("SessionStart", "UserPromptSubmit", "PostToolUse", "Stop", "SessionEnd"):
        if mode == "partial" and not is_control and event != "SessionStart":
            continue
        if mode == "missing-tool" and event == "PostToolUse":
            continue
        if mode == "missing-stop" and event == "Stop":
            continue
        command = hooks[event][0]["hooks"][0]["command"]
        result = subprocess.run(command, shell=True, input=json.dumps({
            "hook_event_name": event}), text=True, capture_output=True, check=True)
        if event == "SessionStart":
            nonce = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"].split()[-1]
        if mode == "malformed-markers":
            marker = pathlib.Path(command.split()[-1].strip("'"))
            marker.write_text("malformed\\n")
(workspace / "probe.txt").write_text("probe-ok\\n")
print(json.dumps({"type": "item.completed", "item": {"type": "file_change",
    "changes": [{"path": "probe.txt", "kind": "add"}]}}))
if mode == "malformed":
    print("not JSON")
elif mode == "malformed-type":
    print(json.dumps({"type": []}))
elif mode == "malformed-object":
    print(json.dumps([]))
elif mode == "failed-turn":
    print(json.dumps({"type": "turn.failed", "error": {"message": "private-details"}}))
else:
    print(json.dumps({"type": "item.completed", "item": {"type": "agent_message",
        "text": "UNKNOWN" if mode == "wrong-nonce" else nonce}}))
    print(json.dumps({"type": "turn.completed", "usage": {}}))
"""


@pytest.fixture
def fake_codex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], Path]:
    binary = tmp_path / "bin" / "codex"
    binary.parent.mkdir()
    binary.write_text(f"#!{sys.executable}\n" + _FAKE_CODEX, encoding="utf-8")
    binary.chmod(0o755)
    source_home = tmp_path / "source-home"
    source_home.mkdir()
    (source_home / "auth.json").write_text('{"token":"private-auth"}', encoding="utf-8")
    (source_home / "config.toml").write_text("# untouched\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(binary.parent) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_CODEX_AUDIT", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("CODEX_UNSAFE_TEST", "must-not-inherit")

    def configure(mode: str) -> Path:
        monkeypatch.setenv("FAKE_CODEX_MODE", mode)
        return source_home

    return configure


def test_native_hooks_require_events_context_and_file_change(
    fake_codex: Callable[[str], Path],
    tmp_path: Path,
) -> None:
    source_home = fake_codex("native")
    result = probe_hooks(codex_home=source_home)
    assert result.native_hooks is True
    assert result.runtime_version == "codex-cli 0.165.0"
    assert result.events == (
        "SessionStart",
        "UserPromptSubmit",
        "PostToolUse",
        "Stop",
        "SessionEnd",
    )
    assert result.errors == ()
    assert (source_home / "config.toml").read_text() == "# untouched\n"
    audit = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert all(not record["inherited_codex"] for record in audit)
    assert all(record["home"] != str(source_home) for record in audit)
    sessions = [record for record in audit if record["args"][0] == "exec"]
    assert len(sessions) == 1
    assert sessions[0]["auth_link"] is True
    assert "--dangerously-bypass-hook-trust" in sessions[0]["args"]
    assert all(not Path(record["home"]).exists() for record in audit)


def test_absent_native_hooks_require_successful_user_control(
    fake_codex: Callable[[str], Path],
    tmp_path: Path,
) -> None:
    result = probe_hooks(codex_home=fake_codex("absent"))
    assert result.native_hooks is False
    assert "SessionStart" in result.events
    assert result.errors == ()
    audit = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    sessions = [record for record in audit if record["args"][0] == "exec"]
    assert len(sessions) == 2
    assert any("enabled=false" in arg for arg in sessions[1]["args"])


@pytest.mark.parametrize(
    "mode",
    [
        "network-failure",
        "control-failure",
        "install-failure",
        "partial",
        "missing-tool",
        "missing-stop",
        "malformed",
        "malformed-type",
        "malformed-object",
        "failed-turn",
        "wrong-nonce",
        "malformed-markers",
    ],
)
def test_inconclusive_probes_never_claim_native_is_unsupported(
    fake_codex: Callable[[str], Path],
    mode: str,
) -> None:
    result = probe_hooks(codex_home=fake_codex(mode))
    assert result.native_hooks is None
    assert result.errors
    assert "private" not in str(result.errors)
    assert "sensitive" not in str(result.errors)


def test_codex_version_uses_isolated_home(fake_codex: Callable[[str], Path]) -> None:
    fake_codex("native")
    assert codex_version() == "codex-cli 0.165.0"


def test_install_failure_identifies_stage_and_known_error_without_exposing_stderr(
    fake_codex: Callable[[str], Path],
) -> None:
    result = probe_hooks(codex_home=fake_codex("missing-manifest"))
    assert result.native_hooks is None
    assert "plugin add" in str(result.errors)
    assert "missing plugin.json" in str(result.errors)
    assert "private-details" not in str(result.errors)


def test_timeout_terminates_hook_and_tool_process_group(
    fake_codex: Callable[[str], Path],
    tmp_path: Path,
) -> None:
    result = probe_hooks(codex_home=fake_codex("timeout"), timeout=1)
    assert result.native_hooks is None
    assert "timed out" in str(result.errors)
    child_pid = (tmp_path / "audit.child-pid").read_text()
    status = Path("/proc") / child_pid / "stat"
    assert not status.exists() or status.read_text().split()[2] == "Z"


def test_missing_cli_is_inconclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "nonexistent"))
    result = probe_hooks(codex_home=tmp_path)
    assert result.native_hooks is None
    assert result.runtime_version == ""
    assert result.errors == ("Could not start the Codex executable",)


@pytest.mark.parametrize("timeout", [0, -1])
def test_rejects_invalid_timeout(tmp_path: Path, timeout: int) -> None:
    with pytest.raises(ValueError, match="timeout"):
        probe_hooks(codex_home=tmp_path, timeout=timeout)


def test_interrupted_probe_terminates_children_and_removes_temporary_auth(
    fake_codex: Callable[[str], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_home = fake_codex("timeout")
    original = subprocess.Popen.communicate
    active_pid = 0
    child_file = tmp_path / "audit.child-pid"
    interrupted = False

    def communicate(
        process: subprocess.Popen[str],
        input: str | None = None,
        timeout: float | None = None,
    ) -> tuple[str, str]:
        nonlocal active_pid, interrupted
        arguments = process.args
        if not interrupted and isinstance(arguments, list) and arguments[1] == "exec":
            active_pid = process.pid
            interrupted = True
            deadline = time.monotonic() + 5
            while not child_file.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert child_file.exists(), "probe did not start its diagnostic subprocess"
            raise KeyboardInterrupt
        return original(process, input=input, timeout=timeout)

    monkeypatch.setattr(subprocess.Popen, "communicate", communicate)
    try:
        with pytest.raises(KeyboardInterrupt):
            probe_hooks(codex_home=source_home)
        status = Path("/proc") / child_file.read_text() / "stat"
        assert not status.exists() or status.read_text().split()[2] == "Z"
        audit = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
        assert all(not Path(record["home"]).exists() for record in audit)
        assert (source_home / "auth.json").read_text() == '{"token":"private-auth"}'
    finally:
        if active_pid:
            with suppress(ProcessLookupError):
                os.killpg(active_pid, signal.SIGKILL)


def test_shared_group_termination_waits_for_children_after_parent_exit(tmp_path: Path) -> None:
    groups = importlib.import_module("mozg_pipelines.process_groups")
    script = (
        "import subprocess, sys; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        "print(child.pid, flush=True)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0
        assert stderr == ""
        groups.terminate_process_group(process.pid)
        status = Path("/proc") / stdout.strip() / "stat"
        assert not status.exists() or status.read_text().split()[2] == "Z"
        groups.terminate_process_group(process.pid)
    finally:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


@pytest.mark.parametrize("pid", [0, -1, False, True])
def test_shared_group_termination_rejects_nonpositive_pids(
    pid: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    groups = importlib.import_module("mozg_pipelines.process_groups")

    def unexpected_signal(_pid: int, _signal: int) -> None:
        pytest.fail("invalid PID reached process-group signaling")

    monkeypatch.setattr(os, "killpg", unexpected_signal)
    with pytest.raises(ValueError, match="positive"):
        groups.terminate_process_group(pid)


def test_probe_strips_hostile_runtime_roots_before_git_and_session(
    fake_codex: Callable[[str], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_home = fake_codex("native")
    foreign = {
        "GIT_DIR": tmp_path / "foreign.git",
        "GIT_WORK_TREE": tmp_path / "foreign-worktree",
        "GIT_INDEX_FILE": tmp_path / "foreign-index",
    }
    for key, path in foreign.items():
        monkeypatch.setenv(key, str(path))
    for key in ("MZ_MEMORY_ROOT", "CLAUDE_PROJECT_DIR", "EVAL_SOURCE_ROOT"):
        monkeypatch.setenv(key, str(tmp_path / "foreign-memory"))
    result = probe_hooks(codex_home=source_home)
    assert result.native_hooks is True
    records = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert all(not record["inherited_roots"] for record in records)
    assert all(not path.exists() for path in foreign.values())
    assert not (tmp_path / "foreign-memory").exists()
    sessions = [record for record in records if record["args"][0] == "exec"]
    assert sessions[0]["auth_link"] is True
    assert (source_home / "config.toml").read_text() == "# untouched\n"
