"""Exercise Codex orchestration with real isolated homes and a deterministic CLI."""

import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Never

import pytest
import yaml

from mozg_pipelines.hooks_probe import ProbeResult
from tests.eval_tools import codex_runner, codex_runtime

_HOOK_TRUST_NOTICE = (
    "`--dangerously-bypass-hook-trust` is enabled. "
    "Enabled hooks may run without review for this invocation."
)

_CLI = """
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import time
import tomllib

args = sys.argv[1:]
home = pathlib.Path(os.environ["CODEX_HOME"])
record = {"args": args, "home": str(home), "env": {
    key: value for key, value in os.environ.items()
    if key in {"CODEX_UNSAFE_TEST", "MZ_MEMORY_ROOT", "CLAUDE_PROJECT_DIR",
        "MZ_MEMORY_COMPRESS", "MZ_MEMORY_CURATOR", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"}},
    "auth_link": (home / "auth.json").is_symlink(), "bridge_hooks": (home / "hooks.json").exists()}
with pathlib.Path(AUDIT).open("a") as stream:
    stream.write(json.dumps(record) + "\\n")
if args == ["--version"]:
    print("codex-cli 0.165.0")
    raise SystemExit(0)
if args[:3] == ["plugin", "marketplace", "add"]:
    (home / "fake-marketplace").write_text(args[3])
    raise SystemExit(0)
if args[:2] == ["plugin", "add"]:
    if pathlib.Path(AUDIT).with_suffix(".install-failure").exists():
        print("installation failed", file=sys.stderr)
        raise SystemExit(6)
    with (home / "fake-installed").open("a") as stream:
        stream.write(args[2] + "\\n")
    name = args[2].split("@")[0]
    marketplace = pathlib.Path((home / "fake-marketplace").read_text())
    package = marketplace / "packages" / name
    version = json.loads((package / "plugin.json").read_text())["version"]
    shutil.copytree(package, home / "plugins/cache/mozg-eval" / name / version)
    raise SystemExit(0)
if args[0] != "exec":
    raise SystemExit(3)
if "--ephemeral" not in args:
    rollout = home / "sessions/2026/rollout-fake.jsonl"
    rollout.parent.mkdir(parents=True)
    rollout.write_text(json.dumps({"type": "session_meta", "payload": {"id": "fake-session"}}))
prompt = sys.stdin.read()
workspace = pathlib.Path(args[args.index("--cd") + 1])
mode = prompt.split()[0]
message = "OK"
if mode == "document-context":
    fallbacks = []
    for index, argument in enumerate(args[:-1]):
        if argument in ("-c", "--config"):
            override = tomllib.loads(args[index + 1])
            if "project_doc_fallback_filenames" in override:
                fallbacks = override["project_doc_fallback_filenames"]
    message = "NO_PROJECT_INSTRUCTIONS"
    for filename in ["AGENTS.override.md", "AGENTS.md", *fallbacks]:
        document = workspace / filename
        if document.is_file():
            # Observed 0.165 behavior: an empty provider file still shadows the fallback.
            message = document.read_text().strip() or "NO_PROJECT_INSTRUCTIONS"
            break
print("diagnostic stderr", file=sys.stderr, flush=True)
print(json.dumps({"type": "thread.started", "thread_id": "fake-thread"}), flush=True)
if "--dangerously-bypass-hook-trust" in args:
    for index in range(2):
        print(json.dumps({"type": "item.completed", "item": {"id": f"notice_{index}",
            "type": "error", "message": HOOK_TRUST_NOTICE}}), flush=True)
if mode == "modified-notice":
    print(json.dumps({"type": "item.completed", "item": {
        "type": "error", "message": HOOK_TRUST_NOTICE + " additional details"}}))
config = home / "hooks.json"
sources = []
if config.exists():
    sources.append((json.loads(config.read_text()).get("hooks", {}), os.environ.copy()))
else:
    marketplace = pathlib.Path((home / "fake-marketplace").read_text())
    for selector in (home / "fake-installed").read_text().splitlines():
        plugin = marketplace / "packages" / selector.split("@")[0]
        environment = {**os.environ, "PLUGIN_ROOT": str(plugin),
            "CLAUDE_PLUGIN_ROOT": str(plugin), "PLUGIN_DATA": str(home / "plugin-data")}
        hooks = json.loads((plugin / "hooks/hooks.json").read_text()).get("hooks", {})
        sources.append((hooks, environment))
for hooks, environment in sources:
    for event in ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"):
        for group in hooks.get(event, []):
            for hook in group.get("hooks", []):
                payload = {"hook_event_name": event, "session_id": "fake-session", "prompt": prompt}
                completed = subprocess.run(hook["command"], shell=True,
                    input=json.dumps(payload), cwd=workspace, env=environment,
                    capture_output=True, text=True)
                if completed.returncode:
                    print("hook command failed", file=sys.stderr, flush=True)
                    raise SystemExit(completed.returncode)
                context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
                assert context == "canonical synthetic hook context", "hook stdout was altered"
                assert completed.stderr == "canonical hook stderr\\n", "hook stderr was altered"
if mode.startswith("skill-evidence"):
    package = home / "plugins/cache/mozg-eval/alpha/1.0.0"
    commands = [["cat", str(package / "skills/check/SKILL.md")]]
    if mode != "skill-evidence-error":
        commands.append(["bash", str(package / "scripts/check.sh")])
    for index, command in enumerate(commands):
        completed = subprocess.run(command, cwd=workspace, capture_output=True, text=True)
        print(json.dumps({"type": "item.completed", "item": {
            "id": f"skill_{index}", "type": "command_execution",
            "command": shlex.join(command), "aggregated_output": completed.stdout,
            "exit_code": completed.returncode, "status": "completed"}}), flush=True)
    if mode == "skill-evidence-error":
        print(json.dumps({"type": "turn.failed", "error": {"message": "after skill read"}}))
        raise SystemExit(0)
if mode == "timeout":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    pathlib.Path(AUDIT).with_suffix(".child-pid").write_text(str(child.pid))
    time.sleep(30)
if mode == "exit-error":
    raise SystemExit(5)
if mode == "malformed":
    print("broken JSON", flush=True)
    raise SystemExit(0)
if mode == "failed-turn":
    print(json.dumps({"type": "turn.failed", "error": {"message": "fake failure"}}))
    raise SystemExit(0)
if mode == "error-event":
    print(json.dumps({"type": "error", "message": "fake runtime error"}))
    raise SystemExit(0)
if mode == "item-error":
    print(json.dumps({"type": "item.completed", "item": {"type": "error"}}))
    print(json.dumps({"type": "turn.completed", "usage": {}}))
    raise SystemExit(0)
if mode == "malformed-object":
    print(json.dumps([]))
    print(json.dumps({"type": "turn.completed", "usage": {}}))
    raise SystemExit(0)
if mode == "missing-completion":
    raise SystemExit(0)
(workspace / "answer.txt").write_text("OK\\n")
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": message}}))
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 12,
    "cached_input_tokens": 3, "output_tokens": 4}}))
"""

_HOOK = """
import json
import pathlib
import sys

payload = json.load(sys.stdin)
pathlib.Path("hook-ran.txt").write_text(payload["hook_event_name"])
print(json.dumps({"hookSpecificOutput": {"hookEventName": payload["hook_event_name"],
    "additionalContext": "canonical synthetic hook context"}}))
print("canonical hook stderr", file=sys.stderr)
if payload.get("prompt") == "hook-error":
    raise SystemExit(7)
"""


@dataclass
class Harness:
    repository: Path
    packages: dict[str, Path]
    auth_home: Path
    audit: Path
    probe_calls: list[dict[str, object]]
    native_hooks: bool | None = False
    probe_version: str = "codex-cli 0.165.0"

    def case(
        self,
        suite: str,
        path: str,
        *,
        name: str = "same",
        mode: str = "success",
        dependencies: tuple[str, ...] = ("alpha",),
        runs: int = 1,
    ) -> Path:
        directory = self.repository / "evals" / suite / path
        directory.mkdir(parents=True)
        specification = {
            "name": name,
            "plugins": [f"../../../plugins/{plugin}" for plugin in dependencies],
            "runs": runs,
            "context": {"scaffold_script": "scaffold.sh"},
            "execution": {"prompt": mode, "timeout_seconds": 1 if mode == "timeout" else 20},
            "graders": [
                {"name": "answer", "type": "regex", "pattern": "OK"},
                {"name": "output", "type": "file_exists", "path": "answer.txt"},
                {
                    "name": "runtime-outside-workspace",
                    "type": "file_exists",
                    "path": "*json*",
                    "exists": False,
                },
            ],
        }
        (directory / "case.yaml").write_text(yaml.safe_dump(specification))
        (directory / "scaffold.sh").write_text("printf fixture >fixture.txt\n")
        return directory

    def run(self, suite: str, output: Path, *arguments: str) -> int:
        return codex_runner.main([suite, "--output-dir", str(output), *arguments])

    def calls(self) -> list[dict[str, Any]]:
        if not self.audit.exists():
            return []
        return [json.loads(line) for line in self.audit.read_text().splitlines()]


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    repository = tmp_path / "repository"
    repository.mkdir()
    packages: dict[str, Path] = {}
    for name in ("alpha", "beta", "unused"):
        package = tmp_path / "canonical-rendered" / name
        (package / "scripts").mkdir(parents=True)
        (package / "hooks").mkdir()
        (package / "plugin.json").write_text(json.dumps({"name": name, "version": "1.0.0"}))
        if name == "alpha":
            skill = package / "skills/check/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: check\ndescription: Record a verified workflow step.\n---\n"
                "Run `${PLUGIN_ROOT}/scripts/check.sh`.\n"
            )
            (package / "scripts/check.sh").write_text("#!/bin/sh\nprintf observed >skill-ran.txt\n")
        script = package / "scripts/hook.py"
        script.write_text(_HOOK)
        hook_command = shlex.quote(sys.executable) + ' "${PLUGIN_ROOT}/scripts/hook.py"'
        (package / "hooks/hooks.json").write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [{"hooks": [{"type": "command", "command": hook_command}]}],
                    }
                }
            )
        )
        packages[name] = package
    auth_home = tmp_path / "source-codex"
    auth_home.mkdir()
    (auth_home / "auth.json").write_text('{"token":"do-not-copy-or-print"}')
    (auth_home / "hooks.json").write_text('{"hooks": {"Stop": []}}')
    audit = tmp_path / "audit.jsonl"
    binary = tmp_path / "bin/codex"
    binary.parent.mkdir()
    binary.write_text(
        f"#!{sys.executable}\nAUDIT = {str(audit)!r}\n"
        f"HOOK_TRUST_NOTICE = {_HOOK_TRUST_NOTICE!r}\n" + _CLI
    )
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", str(binary.parent) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("CODEX_HOME", str(auth_home))
    monkeypatch.setenv("CODEX_UNSAFE_TEST", "strip-this")
    monkeypatch.setenv("MZ_MEMORY_ROOT", "/must-not-use-in-eval")
    monkeypatch.setenv("MZ_MEMORY_CURATOR", "1")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/must-not-use-in-eval")
    fake = Harness(repository, packages, auth_home, audit, [])

    def probe(**kwargs: object) -> ProbeResult:
        fake.probe_calls.append(kwargs)
        return ProbeResult(fake.probe_version, fake.native_hooks, ("SessionStart",), ())

    monkeypatch.setattr(codex_runtime, "probe_hooks", probe)
    monkeypatch.setattr(
        codex_runtime, "_render_packages", lambda _repository, _destination: packages
    )
    monkeypatch.setattr(codex_runner, "ROOT", repository)
    return fake


def _case_results(output: Path) -> list[dict[str, Any]]:
    paths = list(output.rglob("result.json"))
    return [json.loads(path.read_text()) for path in paths]


def test_single_suite_executes_real_bridge_once_and_retains_diagnostics(
    harness: Harness,
    tmp_path: Path,
) -> None:
    source = harness.case("suite-a", "nested/case", dependencies=("alpha", "alpha", "beta"))
    specification = yaml.safe_load((source / "case.yaml").read_text())
    specification["graders"].append(
        {
            "name": "actual-hook-output",
            "type": "regex",
            "target": "trace",
            "pattern": '"subtype":"hook_response"[^\\n]*canonical synthetic hook context',
        }
    )
    (source / "case.yaml").write_text(yaml.safe_dump(specification))
    output = tmp_path / "saved"
    assert harness.run("suite-a", output) == 0
    assert len(harness.probe_calls) == 1
    calls = harness.calls()
    installed = [call["args"][2] for call in calls if call["args"][:2] == ["plugin", "add"]]
    assert sorted(installed) == ["alpha@mozg-eval", "beta@mozg-eval"]
    sessions = [call for call in calls if call["args"][0] == "exec"]
    assert len(sessions) == 1
    assert sessions[0]["auth_link"] is True
    assert "CODEX_UNSAFE_TEST" not in sessions[0]["env"]
    assert sessions[0]["env"]["MZ_MEMORY_COMPRESS"] == "0"
    assert sessions[0]["env"].get("MZ_MEMORY_CURATOR") != "1"
    assert sessions[0]["env"].get("MZ_MEMORY_ROOT") != "/must-not-use-in-eval"
    assert sessions[0]["env"].get("CLAUDE_PROJECT_DIR") != "/must-not-use-in-eval"
    result = _case_results(output)[0]
    assert result["status"] == "pass"
    assert any(
        "maintenance tested separately" in limitation for limitation in result["limitations"]
    )
    assert not list(output.rglob("auth.json"))
    for filename in (
        "stdout.jsonl",
        "stderr.txt",
        "trace.jsonl",
        "hook-records.jsonl",
        "usage.json",
        "initial-files.json",
        "case.json",
    ):
        assert list(output.rglob(filename)), filename
    records = [
        json.loads(line)
        for path in output.rglob("hook-records.jsonl")
        for line in path.read_text().splitlines()
    ]
    assert len(records) == 2
    assert "canonical synthetic hook context" in json.dumps(records)
    assert "canonical hook stderr" in json.dumps(records)
    normalized = [
        json.loads(line)
        for line in next(output.rglob("normalized-hook-responses.jsonl")).read_text().splitlines()
    ]
    assert len(normalized) == 2
    assert all(record["subtype"] == "hook_response" for record in normalized)
    assert normalized[0]["output"] == records[0]["stdout"]
    trace = next(output.rglob("trace.jsonl")).read_text()
    assert "hook_response" not in trace
    provenance = json.loads(next(output.rglob("case.json")).read_text())
    assert provenance["source_path"] == str(source / "case.yaml")
    assert isinstance(provenance["started_at"], str)
    assert isinstance(provenance["completed_at"], str)
    assert isinstance(provenance["duration_seconds"], (int, float))
    assert provenance["duration_seconds"] >= 0
    assert (
        provenance["source_sha256"]
        == hashlib.sha256((source / "case.yaml").read_bytes()).hexdigest()
    )
    usage = json.loads(next(output.rglob("usage.json")).read_text())
    assert usage["total"] == {"input_tokens": 12, "cached_input_tokens": 3, "output_tokens": 4}
    initial = json.loads(next(output.rglob("initial-files.json")).read_text())
    assert "fixture.txt" in initial
    assert "answer.txt" not in initial
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata["completed"] is True
    package = metadata["provenance"]["packages"]["alpha"]
    assert package["version"] == "1.0.0"
    assert (
        package["files"]["plugin.json"]
        == hashlib.sha256((harness.packages["alpha"] / "plugin.json").read_bytes()).hexdigest()
    )
    receipt = json.loads(next(output.rglob("session.command.json")).read_text())
    assert receipt["argv"][:2] == ["codex", "exec"]
    assert receipt["returncode"] == 0
    assert receipt["timed_out"] is False
    assert receipt["timeout"] == 20
    assert isinstance(receipt["duration_seconds"], (int, float))
    assert "environment" not in receipt
    assert "stdin" not in receipt


@pytest.mark.parametrize(
    "mode",
    [
        "failed-turn",
        "error-event",
        "item-error",
        "modified-notice",
        "missing-completion",
        "malformed",
        "malformed-object",
        "exit-error",
    ],
)
def test_zero_exit_and_runtime_errors_cannot_become_passing_evals(
    harness: Harness,
    tmp_path: Path,
    mode: str,
) -> None:
    harness.case("suite", "case", mode=mode)
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 1
    result = _case_results(output)[0]
    assert result["status"] == "error"
    assert result["error"]
    assert next(output.rglob("stderr.txt")).read_text() == "diagnostic stderr\n"
    assert "thread.started" in next(output.rglob("stdout.jsonl")).read_text()
    assert not list(output.rglob("auth.json"))


def test_all_suites_parallel_cases_keep_duplicate_names_isolated(
    harness: Harness, tmp_path: Path
) -> None:
    for suite in ("suite-a", "suite-b"):
        for path in ("one", "nested/two"):
            harness.case(suite, path)
    output = tmp_path / "saved"
    assert harness.run("all", output, "--jobs", "4") == 0
    assert len(harness.probe_calls) == 1
    assert len(_case_results(output)) == 4
    homes = [call["home"] for call in harness.calls() if call["args"][0] == "exec"]
    assert len(set(homes)) == 4
    assert len(list(output.rglob("case.json"))) == 4


def test_unknown_probe_refuses_all_cases(harness: Harness, tmp_path: Path) -> None:
    harness.native_hooks = None
    harness.case("suite", "case")
    assert harness.run("suite", tmp_path / "saved") != 0
    assert len(harness.probe_calls) == 1
    assert not [call for call in harness.calls() if call["args"][0] == "exec"]


def test_completed_run_is_not_overwritten_or_reexecuted(harness: Harness, tmp_path: Path) -> None:
    harness.case("suite", "case")
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 0
    before = {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()
    }
    calls = len(harness.calls())
    assert harness.run("suite", output) != 0
    assert len(harness.calls()) == calls
    assert before == {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()
    }


def test_timeout_keeps_partial_outputs_and_terminates_children(
    harness: Harness, tmp_path: Path
) -> None:
    harness.case("suite", "case", mode="timeout")
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 1
    assert "timeout" in json.dumps(_case_results(output)).lower()
    assert "thread.started" in next(output.rglob("stdout.jsonl")).read_text()
    assert next(output.rglob("stderr.txt")).read_text() == "diagnostic stderr\n"
    child_pid = harness.audit.with_suffix(".child-pid").read_text()
    status = Path("/proc") / child_pid / "stat"
    assert not status.exists() or status.read_text().split()[2] == "Z"
    assert not list(output.rglob("auth.json"))


def test_native_delivery_never_registers_duplicate_bridge(harness: Harness, tmp_path: Path) -> None:
    harness.native_hooks = True
    harness.case("suite", "case")
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 0
    sessions = [call for call in harness.calls() if call["args"][0] == "exec"]
    assert len(sessions) == 1
    assert sessions[0]["bridge_hooks"] is False
    records = next(output.rglob("hook-records.jsonl")).read_text().splitlines()
    assert len(records) == 1


@pytest.mark.parametrize(("override", "expected"), [(None, 2), ("1", 1)])
def test_declared_runs_and_override_have_unique_trial_artifacts(
    harness: Harness,
    tmp_path: Path,
    override: str | None,
    expected: int,
) -> None:
    harness.case("suite", "case", runs=2)
    output = tmp_path / "saved"
    extra = () if override is None else ("--runs", override)
    assert harness.run("suite", output, *extra) == 0
    results = _case_results(output)
    assert len(results) == expected
    assert len({result["run_index"] for result in results}) == expected
    assert len(harness.probe_calls) == 1


def test_fixture_failure_keeps_diagnostics_without_starting_model(
    harness: Harness, tmp_path: Path
) -> None:
    case = harness.case("suite", "case")
    (case / "scaffold.sh").write_text("printf fixture-output; printf fixture-error >&2; exit 9\n")
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 1
    assert _case_results(output)[0]["status"] == "error"
    assert next(output.rglob("fixture.stdout.txt")).read_text() == "fixture-output"
    assert next(output.rglob("fixture.stderr.txt")).read_text() == "fixture-error"
    assert not [call for call in harness.calls() if call["args"][0] == "exec"]
    assert not list(output.rglob("auth.json"))


def test_install_failure_cleans_auth_and_cannot_run_case(harness: Harness, tmp_path: Path) -> None:
    harness.case("suite", "case")
    harness.audit.with_suffix(".install-failure").touch()
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 1
    assert _case_results(output)[0]["status"] == "error"
    assert not [call for call in harness.calls() if call["args"][0] == "exec"]
    assert not list(output.rglob("auth.json"))


def test_hook_observer_preserves_nonzero_exit_and_actual_io(
    harness: Harness, tmp_path: Path
) -> None:
    harness.case("suite", "case", mode="hook-error")
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 1
    record = json.loads(next(output.rglob("hook-records.jsonl")).read_text().splitlines()[0])
    assert record["exit_code"] == 7
    assert json.loads(record["stdin"])["hook_event_name"] == "SessionStart"
    assert "canonical synthetic hook context" in record["stdout"]
    assert record["stderr"] == "canonical hook stderr\n"


def test_probe_version_mismatch_refuses_execution(harness: Harness, tmp_path: Path) -> None:
    harness.probe_version = "codex-cli 0.166.0"
    harness.case("suite", "case")
    assert harness.run("suite", tmp_path / "saved") != 0
    assert not [call for call in harness.calls() if call["args"][0] == "exec"]


def test_interrupted_command_kills_children_retains_output_and_cleans_auth(
    harness: Harness,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "interrupted-workspace"
    workspace.mkdir()
    home = tmp_path / "interrupted-home"
    child_pid = tmp_path / "interrupted.child-pid"
    script = (
        "import pathlib, subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        "print('partial stdout', flush=True); "
        "print('partial stderr', file=sys.stderr, flush=True); "
        f"pathlib.Path({str(child_pid)!r}).write_text(str(child.pid)); time.sleep(30)"
    )
    original = subprocess.Popen.communicate
    interrupted = False

    def communicate(
        process: subprocess.Popen[str],
        input: str | None = None,
        timeout: float | None = None,
    ) -> tuple[str, str]:
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            deadline = time.monotonic() + 5
            while not child_pid.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert child_pid.exists()
            raise KeyboardInterrupt
        return original(process, input=input, timeout=timeout)

    monkeypatch.setattr(subprocess.Popen, "communicate", communicate)
    prefix = tmp_path / "interrupted-command"
    with (
        pytest.raises(KeyboardInterrupt),
        codex_runtime._environment(
            home,
            harness.auth_home,
            workspace,
        ) as environment,
    ):
        codex_runtime._process(
            [sys.executable, "-c", script],
            environment=environment,
            workspace=workspace,
            prefix=prefix,
            timeout=20,
        )
    assert (tmp_path / "interrupted-command.stdout.txt").read_text() == "partial stdout\n"
    assert (tmp_path / "interrupted-command.stderr.txt").read_text() == "partial stderr\n"
    status = Path("/proc") / child_pid.read_text() / "stat"
    assert not status.exists() or status.read_text().split()[2] == "Z"
    assert not (home / ".codex/auth.json").exists()


def test_successful_command_terminates_detached_stdio_children(tmp_path: Path) -> None:
    script = (
        "import subprocess, sys; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        "print(child.pid, flush=True)"
    )
    process = codex_runtime._process(
        [sys.executable, "-c", script],
        environment=os.environ.copy(),
        workspace=tmp_path,
        prefix=tmp_path / "success",
        timeout=5,
    )
    assert process.returncode == 0
    status = Path("/proc") / process.stdout.strip() / "stat"
    try:
        assert not status.exists() or status.read_text().split()[2] == "Z"
        assert (tmp_path / "success.stdout.txt").read_text() == process.stdout
    finally:
        if status.exists() and status.read_text().split()[2] != "Z":
            os.kill(int(process.stdout.strip()), 9)


def test_batch_interrupt_cancels_queued_cases_and_active_children(
    harness: Harness,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = harness.case("suite", "first", mode="timeout")
    specification = yaml.safe_load((first / "case.yaml").read_text())
    specification["execution"]["timeout_seconds"] = 30
    (first / "case.yaml").write_text(yaml.safe_dump(specification))
    harness.case("suite", "second", name="second")
    child_pid = harness.audit.with_suffix(".child-pid")

    def interrupt_after_first_session(_futures: object) -> Never:
        deadline = time.monotonic() + 5
        while not child_pid.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert child_pid.exists(), "first case never reached its model subprocess"
        raise KeyboardInterrupt

    monkeypatch.setattr(codex_runner, "as_completed", interrupt_after_first_session)
    output = tmp_path / "saved"
    started = time.monotonic()
    try:
        exit_code = harness.run("suite", output, "--jobs", "1")
    except KeyboardInterrupt:
        pytest.fail("batch interruption escaped before cancelling queued cases")
    assert exit_code != 0
    assert time.monotonic() - started < 5
    assert len([call for call in harness.calls() if call["args"][0] == "exec"]) == 1
    status = Path("/proc") / child_pid.read_text() / "stat"
    assert not status.exists() or status.read_text().split()[2] == "Z"
    assert not list(output.rglob("auth.json"))
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata["completed"] is False
    assert metadata["interrupted"] is True


def test_invalid_grader_is_contained_and_other_case_still_reports(
    harness: Harness, tmp_path: Path
) -> None:
    invalid = harness.case("suite", "invalid", name="invalid")
    specification = yaml.safe_load((invalid / "case.yaml").read_text())
    specification["graders"][0]["pattern"] = "["
    (invalid / "case.yaml").write_text(yaml.safe_dump(specification))
    harness.case("suite", "valid", name="valid")
    output = tmp_path / "saved"
    assert harness.run("suite", output, "--jobs", "2") == 1
    results = _case_results(output)
    assert {result["name"]: result["status"] for result in results} == {
        "invalid": "error",
        "valid": "pass",
    }
    assert len(json.loads((output / "results.json").read_text())) == 2
    assert len([call for call in harness.calls() if call["args"][0] == "exec"]) == 2


@pytest.mark.parametrize(
    "mutation",
    [
        "case-change",
        "case-delete",
        "fixture-change",
        "fixture-delete",
        "helper-change",
    ],
)
def test_canonical_inputs_changed_after_discovery_fail_before_execution(
    harness: Harness,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    directory = harness.case("suite", "case")
    source = directory / "case.yaml"
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    helper = directory.parent / "_lib/helper.sh"
    helper.parent.mkdir()
    helper.write_text("printf fixture >fixture.txt\n")
    (directory / "scaffold.sh").write_text('. "$(dirname "$0")/../_lib/helper.sh"\n')
    prepare = codex_runtime.prepare_runtime

    def mutate(config: codex_runtime.RuntimeConfig) -> codex_runtime.PreparedRuntime:
        runtime = prepare(config)
        target = (
            source
            if mutation.startswith("case")
            else (helper if mutation.startswith("helper") else directory / "scaffold.sh")
        )
        if mutation.endswith("delete"):
            target.unlink()
        else:
            target.write_text("changed after discovery\n")
        return runtime

    monkeypatch.setattr(codex_runner, "prepare_runtime", mutate)
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 1
    result = _case_results(output)[0]
    assert result["status"] == "error"
    assert "changed" in result["error"].lower()
    assert not [call for call in harness.calls() if call["args"][0] == "exec"]
    provenance = json.loads(next(output.rglob("case.json")).read_text())
    assert provenance["source_sha256"] == original_hash


def test_hostile_git_context_cannot_modify_foreign_paths(
    harness: Harness,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = harness.case("suite", "case")
    (directory / "scaffold.sh").write_text(
        '[[ -z "${GIT_DIR+x}${GIT_WORK_TREE+x}${GIT_INDEX_FILE+x}" ]] || exit 8\n'
        "printf fixture >fixture.txt\n"
    )
    foreign = {
        "GIT_DIR": tmp_path / "foreign.git",
        "GIT_WORK_TREE": tmp_path / "foreign-worktree",
        "GIT_INDEX_FILE": tmp_path / "foreign-index",
    }
    for key, path in foreign.items():
        monkeypatch.setenv(key, str(path))
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 0
    session = next(call for call in harness.calls() if call["args"][0] == "exec")
    assert not set(foreign).intersection(session["env"])
    assert all(not path.exists() for path in foreign.values())


@pytest.mark.parametrize("retain", [False, True])
def test_session_retention_is_explicit_and_does_not_retain_credentials(
    harness: Harness,
    tmp_path: Path,
    retain: bool,
) -> None:
    harness.case("suite", "case")
    output = tmp_path / "saved"
    extra = ("--retain-sessions",) if retain else ()
    assert harness.run("suite", output, *extra) == 0
    receipt = json.loads(next(output.rglob("session.command.json")).read_text())
    assert ("--ephemeral" not in receipt["argv"]) is retain
    rollouts = list(output.rglob("rollout-fake.jsonl"))
    assert bool(rollouts) is retain
    if retain:
        assert json.loads(rollouts[0].read_text())["type"] == "session_meta"
    assert not list(output.rglob("auth.json"))
    assert json.loads((output / "metadata.json").read_text())["retain_sessions"] is retain


def test_provenance_hashes_the_shared_process_group_implementation(
    harness: Harness, tmp_path: Path
) -> None:
    harness.case("suite", "case")
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 0
    source = Path(__file__).parents[2] / "src/mozg_pipelines/process_groups.py"
    metadata = json.loads((output / "metadata.json").read_text())
    assert (
        metadata["provenance"]["runtime_sources"][str(source)]
        == hashlib.sha256(source.read_bytes()).hexdigest()
    )


@pytest.mark.parametrize("suite", ["suite", "all"])
def test_discovery_ignores_retained_result_workspaces(
    harness: Harness, tmp_path: Path, suite: str
) -> None:
    harness.case("suite", "canonical", name="canonical")
    harness.case("suite", "results/retained/home/cwd", name="retained-suite-artifact")
    harness.case("results", "retained/home/cwd", name="retained-all-artifact")
    output = tmp_path / "saved"
    assert harness.run(suite, output) == 0
    assert [result["name"] for result in _case_results(output)] == ["canonical"]
    assert len([call for call in harness.calls() if call["args"][0] == "exec"]) == 1


def test_known_hook_trust_notice_keeps_completed_run_and_original_events(
    harness: Harness,
    tmp_path: Path,
) -> None:
    harness.case("suite", "case")
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 0
    result = _case_results(output)[0]
    assert result["execution_status"] == "completed"
    assert result["status"] == "pass"
    events = [
        json.loads(line) for line in next(output.rglob("trace.jsonl")).read_text().splitlines()
    ]
    notices = [
        event for event in events if event.get("item", {}).get("message") == _HOOK_TRUST_NOTICE
    ]
    assert len(notices) == 2
    assert all(event["item"]["type"] == "error" for event in notices)
    metadata = json.loads(next(output.rglob("case.json")).read_text())
    assert metadata["error"] == ""
    assert metadata["nonfatal_notices"] == [_HOOK_TRUST_NOTICE]


@pytest.mark.parametrize(
    "variant",
    [
        "trailing-space",
        "leading-text",
        "top-level-error",
        "started-item",
        "actual-item-error",
        "failed-turn",
        "missing-completion",
        "missing-message",
    ],
)
def test_notice_exception_does_not_hide_real_failures_or_incomplete_turns(variant: str) -> None:
    notice: dict[str, Any] = {
        "type": "item.completed",
        "item": {
            "type": "error",
            "message": _HOOK_TRUST_NOTICE,
        },
    }
    message = {"type": "item.completed", "item": {"type": "agent_message", "text": "OK"}}
    completed = {"type": "turn.completed", "usage": {}}
    events = [notice, message, completed]
    if variant == "trailing-space":
        notice["item"]["message"] += " "
    elif variant == "leading-text":
        notice["item"]["message"] = "Warning: " + _HOOK_TRUST_NOTICE
    elif variant == "top-level-error":
        events[0] = {"type": "error", "message": _HOOK_TRUST_NOTICE}
    elif variant == "started-item":
        notice["type"] = "item.started"
    elif variant == "actual-item-error":
        events.insert(
            1,
            {
                "type": "item.completed",
                "item": {
                    "type": "error",
                    "message": "genuine model failure",
                },
            },
        )
    elif variant == "failed-turn":
        events[-1] = {"type": "turn.failed", "error": {"message": _HOOK_TRUST_NOTICE}}
    elif variant == "missing-completion":
        events.pop()
    elif variant == "missing-message":
        events.pop(1)
    _parsed, _message, error = codex_runtime._parse_session(
        "\n".join(json.dumps(event) for event in events)
    )
    assert error


@pytest.mark.parametrize("agents_state", ["absent", "present", "empty"])
def test_project_instruction_fallback_preserves_canonical_fixture_inventory(
    harness: Harness,
    tmp_path: Path,
    agents_state: str,
) -> None:
    directory = harness.case("suite", "case", mode="document-context")
    expected_files = {
        "fixture.txt": "fixture",
        "CLAUDE.md": "CANONICAL-CLAUDE-FACT\n",
        "nested/CLAUDE.md": "NESTED-CANONICAL-FACT\n",
    }
    if agents_state != "absent":
        expected_files["AGENTS.md"] = "EXISTING-AGENTS-FACT\n" if agents_state == "present" else ""
    fixture = ["mkdir nested"]
    fixture.extend(
        f"printf %s {shlex.quote(body)} >{shlex.quote(name)}"
        for name, body in expected_files.items()
    )
    (directory / "scaffold.sh").write_text("\n".join(fixture) + "\n")
    expected_answer = {
        "absent": "CANONICAL-CLAUDE-FACT",
        "present": "EXISTING-AGENTS-FACT",
        "empty": "NO_PROJECT_INSTRUCTIONS",
    }[agents_state]
    specification = yaml.safe_load((directory / "case.yaml").read_text())
    specification["graders"][0]["pattern"] = expected_answer
    (directory / "case.yaml").write_text(yaml.safe_dump(specification))
    output = tmp_path / "saved"

    assert harness.run("suite", output) == 0

    baseline = next(output.rglob("initial-files.json"))
    assert set(json.loads(baseline.read_text())) == set(expected_files)
    workspace = baseline.parent / "home/cwd"
    for name, contents in expected_files.items():
        path = workspace / name
        assert path.read_text() == contents
        assert not path.is_symlink()
    expected_agents = {"AGENTS.md"} if agents_state != "absent" else set()
    assert {
        str(path.relative_to(workspace)) for path in workspace.rglob("AGENTS.md")
    } == expected_agents
    events = [
        json.loads(line) for line in next(output.rglob("trace.jsonl")).read_text().splitlines()
    ]
    messages = [
        event["item"]["text"]
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") == "agent_message"
    ]
    assert messages[-1] == expected_answer


def _add_skill_assertions(directory: Path) -> None:
    source = directory / "case.yaml"
    specification = yaml.safe_load(source.read_text())
    specification["graders"].extend(
        [
            {
                "name": "skill-positive",
                "type": "tool_used",
                "tool": "Skill",
                "input_match": r'"skill"\s*:\s*"(?:[\w-]+:)?check"',
            },
            {"name": "skill-negative", "type": "tool_used", "tool": "Skill", "min": 0, "max": 0},
        ]
    )
    source.write_text(yaml.safe_dump(specification))


def test_runtime_records_skill_evidence_without_changing_native_trace_or_workspace(
    harness: Harness, tmp_path: Path
) -> None:
    directory = harness.case("suite", "case", mode="skill-evidence")
    _add_skill_assertions(directory)
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 1
    result = _case_results(output)[0]
    assert result["status"] == "unsupported"
    assert {
        grade["name"]: grade["status"]
        for grade in result["graders"]
        if grade["name"].startswith("skill-")
    } == {
        "skill-positive": "unsupported",
        "skill-negative": "unsupported",
    }
    assert {item["grader_name"]: item["state"] for item in result["skill_assessments"]} == {
        "skill-positive": "workflow-observed",
        "skill-negative": "unknown",
    }
    sidecar = next(output.rglob("skill-evidence.json"))
    evidence = json.loads(sidecar.read_text())
    assert evidence == result["skill_evidence"]
    assert evidence["scope"] == "root-cli-events"
    assert evidence["observations"][0]["state"] == "workflow-observed"
    workspace = sidecar.parent / "home/cwd"
    assert (workspace / "skill-ran.txt").read_text() == "observed"
    assert not list(workspace.rglob("skill-evidence.json"))
    raw = sidecar.with_name("trace.jsonl").read_text()
    assert "command_execution" in raw
    assert "workflow-observed" not in raw
    assert '"type":"tool_use"' not in raw
    source = Path(__file__).with_name("codex_skill_evidence.py")
    metadata = json.loads((output / "metadata.json").read_text())
    assert (
        metadata["provenance"]["runtime_sources"][str(source)]
        == hashlib.sha256(source.read_bytes()).hexdigest()
    )


def test_partial_execution_retains_loaded_evidence_but_no_grades(
    harness: Harness, tmp_path: Path
) -> None:
    directory = harness.case("suite", "case", mode="skill-evidence-error")
    _add_skill_assertions(directory)
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 1
    result = _case_results(output)[0]
    assert result["status"] == "error"
    assert "failed turn" in result["error"]
    assert result["graders"] == []
    assert result["skill_assessments"] == []
    assert result["skill_evidence"]["observations"][0]["state"] == "loaded"
    assert (
        json.loads(next(output.rglob("skill-evidence.json")).read_text())
        == result["skill_evidence"]
    )


def test_prepared_skill_catalog_is_frozen_before_model_execution(
    harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.case("suite", "case", mode="skill-evidence")
    prepare = codex_runtime.prepare_runtime

    def mutate_after_preparation(
        config: codex_runtime.RuntimeConfig,
    ) -> codex_runtime.PreparedRuntime:
        runtime = prepare(config)
        assert runtime.skill_catalog is not None
        body = runtime.packages["alpha"] / "skills/check/SKILL.md"
        body.write_text(body.read_text() + "changed after preparation\n")
        return runtime

    monkeypatch.setattr(codex_runner, "prepare_runtime", mutate_after_preparation)
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 0
    evidence = json.loads(next(output.rglob("skill-evidence.json")).read_text())
    assert all(item["state"] == "unknown" for item in evidence["observations"])


def test_early_install_failure_keeps_original_error_and_unknown_skill_evidence(
    harness: Harness, tmp_path: Path
) -> None:
    harness.case("suite", "case", mode="skill-evidence")
    harness.audit.with_suffix(".install-failure").touch()
    output = tmp_path / "saved"
    assert harness.run("suite", output) == 1
    result = _case_results(output)[0]
    assert result["status"] == "error"
    assert "install" in result["error"].lower()
    assert result["graders"] == []
    assert result["skill_assessments"] == []
    evidence = json.loads(next(output.rglob("skill-evidence.json")).read_text())
    assert evidence == result["skill_evidence"]
    assert all(item["state"] == "unknown" for item in evidence["observations"])
    assert not list(output.rglob("auth.json"))
