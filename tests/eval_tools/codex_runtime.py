"""Isolated, inspectable Codex execution for the canonical eval cases."""

import copy
import hashlib
import inspect
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from time import monotonic
from typing import Any, Literal

from mozg_pipelines.hooks_install import HookInstaller
from mozg_pipelines.hooks_probe import ProbeResult, probe_hooks
from mozg_pipelines.inventory import (
    build_codex_package_spec,
    discover_packages,
    load_migration_plan,
)
from mozg_pipelines.models import PackageDisposition
from mozg_pipelines.process_groups import terminate_process_group
from mozg_pipelines.rendering import render_codex_package
from tests.eval_tools.codex_process import _environment as _environment
from tests.eval_tools.codex_process import _process as _process
from tests.eval_tools.codex_process import _require_success as _require_success
from tests.eval_tools.codex_skill_evidence import (
    EvidenceContext,
    SkillCatalog,
    SkillEvidence,
    analyze_skill_evidence,
)
from tests.eval_tools.local_graders import EvalCase

LOGGER = logging.getLogger(__name__)
ExecutionStatus = Literal["completed", "error", "timeout"]
_PYTHON = str(Path(sys.executable).resolve())
_HOOK_TRUST_NOTICE = (
    "`--dangerously-bypass-hook-trust` is enabled. "
    "Enabled hooks may run without review for this invocation."
)
_CAPTURE = """import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

event, key = sys.argv[1:]
root = Path(__file__).resolve().parent
commands = json.loads((root / ".eval-hook-commands.json").read_text())
payload = sys.stdin.buffer.read()
started = time.monotonic()
process = subprocess.run(commands[key], shell=True, input=payload, capture_output=True, check=False)
record = {"type": "hook_execution", "event": event, "handler": key,
          "plugin": json.loads((root / "plugin.json").read_text())["name"],
          "package_root": str(root), "command": commands[key],
          "stdin": payload.decode("utf-8", errors="replace"),
          "stdout": process.stdout.decode("utf-8", errors="replace"),
          "stderr": process.stderr.decode("utf-8", errors="replace"),
          "exit_code": process.returncode, "duration_seconds": time.monotonic() - started}
log = os.environ.get("MZ_EVAL_HOOK_LOG")
if log:
    with open(log, "a", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(json.dumps(record, ensure_ascii=False) + "\\n")
        stream.flush()
sys.stdout.buffer.write(process.stdout)
sys.stderr.buffer.write(process.stderr)
sys.exit(process.returncode if process.returncode >= 0 else 128 - process.returncode)
"""


@dataclass(frozen=True)
class RuntimeConfig:
    repository: Path
    artifact_root: Path
    model: str
    codex_home: Path | None = None
    retain_sessions: bool = False


@dataclass(frozen=True)
class PreparedRuntime:
    config: RuntimeConfig
    packages: dict[str, Path]
    marketplace: Path
    probe: ProbeResult
    provenance: dict[str, object]
    cancelled: Event = field(default_factory=Event, compare=False, repr=False)
    skill_catalog: SkillCatalog | None = None


@dataclass(frozen=True)
class CaseRequest:
    case: EvalCase
    artifact_root: Path
    prompt: str


@dataclass(frozen=True)
class FrozenCase(EvalCase):
    source_sha256: str
    input_hashes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CaseExecution:
    workspace: Path
    events: list[dict[str, Any]]
    last_message: str
    created_files: frozenset[str]
    execution_status: ExecutionStatus
    error: str = ""
    limitations: tuple[str, ...] = ()
    hook_records: tuple[dict[str, Any], ...] = ()
    skill_evidence: SkillEvidence | None = None


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def workspace_files(workspace: Path) -> frozenset[str]:
    return frozenset(
        path.relative_to(workspace).as_posix()
        for path in workspace.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(workspace).parts
    )


def codex_command(
    workspace: Path,
    model: str,
    max_turns: int,
    *,
    retain_sessions: bool = False,
) -> list[str]:
    if not isinstance(retain_sessions, bool):
        raise ValueError("retain_sessions must be a boolean")
    _ = max_turns
    return [
        "codex",
        "exec",
        "--json",
        "-c",
        'project_doc_fallback_filenames=["CLAUDE.md"]',
        *([] if retain_sessions else ["--ephemeral"]),
        "--dangerously-bypass-hook-trust",
        "--sandbox",
        "workspace-write",
        "--model",
        model,
        "--cd",
        str(workspace),
        "-",
    ]


def _render_packages(repository: Path, destination: Path) -> dict[str, Path]:
    plan = load_migration_plan(repository / "data/codex_migration.toml")
    rendered: dict[str, Path] = {}
    for package in discover_packages(plan, repository):
        if package.plan.disposition is PackageDisposition.BLOCKED:
            continue
        name = package.plan.name
        target = destination / "packages" / name
        render_codex_package(build_codex_package_spec(package, repository, target))
        rendered[name] = target
    return rendered


def _instrument(package: Path) -> None:
    config_path = package / "hooks/hooks.json"
    if not config_path.is_file():
        return
    config = json.loads(config_path.read_text(encoding="utf-8"))
    commands: dict[str, str] = {}
    for event, groups in config["hooks"].items():
        for group_index, group in enumerate(groups):
            for handler_index, handler in enumerate(group["hooks"]):
                if handler.get("type") != "command":
                    raise ValueError("Rendered eval hooks must be command handlers")
                key = f"{event}:{group_index}:{handler_index}"
                commands[key] = handler["command"]
                handler["command"] = (
                    shlex.quote(_PYTHON)
                    + ' "${PLUGIN_ROOT}/.eval-hook-capture.py" '
                    + shlex.join([event, key])
                )
    (package / ".eval-hook-capture.py").write_text(_CAPTURE, encoding="utf-8")
    write_json(package / ".eval-hook-commands.json", commands)
    write_json(config_path, config)


def _marketplace(destination: Path, packages: dict[str, Path]) -> Path:
    root = destination / "marketplace"
    manifest_dir = root / ".agents/plugins"
    manifest_dir.mkdir(parents=True)
    (root / "packages").mkdir()
    for name, source in packages.items():
        (root / "packages" / name).symlink_to(source, target_is_directory=True)
    write_json(
        manifest_dir / "marketplace.json",
        {
            "name": "mozg-eval",
            "owner": {"name": "Mozg eval runner"},
            "metadata": {"description": "Isolated Codex eval packages", "version": "0.0.0"},
            "plugins": [{"name": name, "source": f"./packages/{name}"} for name in packages],
        },
    )
    return root


def _auth_source(config: RuntimeConfig) -> Path:
    return (
        config.codex_home or Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    ).resolve()


def prepare_runtime(config: RuntimeConfig) -> PreparedRuntime:
    if not config.model.strip():
        raise ValueError("Eval model must not be empty")
    if not isinstance(config.retain_sessions, bool):
        raise ValueError("retain_sessions must be a boolean")
    root = config.artifact_root / "runtime"
    root.mkdir(parents=True)
    packages = _render_packages(config.repository, root / "rendered")
    frozen: dict[str, Path] = {}
    package_info: dict[str, object] = {}
    for name, package in packages.items():
        target = root / "frozen" / name
        shutil.copytree(package, target)
        _instrument(target)
        frozen[name] = target
        manifest = json.loads((target / "plugin.json").read_text(encoding="utf-8"))
        hashes = {
            str(path.relative_to(target)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(target.rglob("*"))
            if path.is_file()
        }
        package_info[name] = {"version": manifest["version"], "files": hashes}
    skill_catalog = SkillCatalog.from_packages(frozen)
    helper = root / "probe-home"
    helper.mkdir()
    with _environment(helper, _auth_source(config), helper) as environment:
        probe = probe_hooks(codex_home=Path(environment["CODEX_HOME"]), model=config.model)
        write_json(root / "probe.json", asdict(probe))
        version = _process(
            ["codex", "--version"],
            environment=environment,
            workspace=helper,
            prefix=root / "version",
            timeout=15,
        )
        _require_success(version, "Codex runtime version check")
    if probe.native_hooks is None:
        raise RuntimeError("Codex hook capability probe was inconclusive; see runtime/probe.json")
    if not probe.runtime_version:
        raise RuntimeError("Codex hook capability probe did not provide a runtime version")
    if version.stdout.strip() != probe.runtime_version:
        raise RuntimeError("Codex runtime version differs from the successful hook probe")
    git_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=config.repository,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        env=environment,
    )
    git_status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=config.repository,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        env=environment,
    )
    provenance: dict[str, object] = {
        "git_head": git_head.stdout.strip() if git_head.returncode == 0 else None,
        "git_status": git_status.stdout if git_status.returncode == 0 else None,
        "packages": package_info,
        "probe": asdict(probe),
        "runtime_sources": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                Path(__file__),
                Path(__file__).with_name("codex_runner.py"),
                Path(__file__).with_name("codex_process.py"),
                Path(__file__).with_name("codex_skill_evidence.py"),
                Path(inspect.getfile(HookInstaller)),
                Path(inspect.getfile(probe_hooks)),
                Path(inspect.getfile(terminate_process_group)),
            )
        },
    }
    write_json(root / "provenance.json", provenance)
    return PreparedRuntime(
        config,
        frozen,
        _marketplace(root, frozen),
        probe,
        provenance,
        skill_catalog=skill_catalog,
    )


def _is_hook_trust_notice(event: dict[str, Any]) -> bool:
    item = event.get("item")
    return (
        event.get("type") == "item.completed"
        and isinstance(item, dict)
        and item.get("type") == "error"
        and item.get("message") == _HOOK_TRUST_NOTICE
    )


def _parse_session(stdout: str) -> tuple[list[dict[str, Any]], str, str]:
    events: list[dict[str, Any]] = []
    try:
        for line in stdout.splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                raise ValueError("Expected a Codex JSON event object")
            events.append(event)
    except ValueError:
        return events, "", "Invalid JSON in Codex session output"
    completed = any(event["type"] == "turn.completed" for event in events)
    if any(
        event["type"] in {"error", "turn.failed"}
        or (
            isinstance(event.get("item"), dict)
            and event["item"].get("type") == "error"
            and not (completed and _is_hook_trust_notice(event))
        )
        for event in events
    ):
        return events, "", "Codex emitted a runtime error or failed turn"
    if not completed:
        return events, "", "Codex session has no completed turn"
    messages = [
        event["item"].get("text", "")
        for event in events
        if event["type"] == "item.completed"
        and isinstance(event.get("item"), dict)
        and event["item"].get("type") == "agent_message"
    ]
    if not messages:
        return events, "", "Codex session has no final assistant message"
    return events, str(messages[-1]), ""


def _usage(events: list[dict[str, Any]]) -> dict[str, object]:
    turns = [
        event["usage"]
        for event in events
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict)
    ]
    total: dict[str, int] = {}
    for turn in turns:
        for key, value in turn.items():
            if isinstance(value, int):
                total[key] = total.get(key, 0) + value
    return {"turns": turns, "total": total}


def execute_case(request: CaseRequest, runtime: PreparedRuntime) -> CaseExecution:
    started, started_at = monotonic(), datetime.now(UTC).isoformat()
    root, case = request.artifact_root, request.case
    root.mkdir(parents=True)
    home = root / "home"
    workspace = home / "cwd"
    workspace.mkdir(parents=True)
    log = root / "hook-records.jsonl"
    log.touch()
    (root / "stdout.jsonl").touch()
    (root / "stderr.txt").touch()
    (root / "trace.jsonl").symlink_to("stdout.jsonl")
    initial = frozenset[str]()
    events: list[dict[str, Any]] = []
    message, error = "", ""
    execution_status: ExecutionStatus = "completed"
    limitations = ("Memory compression and curation disabled; maintenance tested separately",)
    source = case.directory / "case.yaml"
    inputs = case.input_hashes if isinstance(case, FrozenCase) else {}
    metadata: dict[str, object] = {
        "source_path": str(source.resolve()),
        "source_sha256": case.source_sha256
        if isinstance(case, FrozenCase)
        else hashlib.sha256(source.read_bytes()).hexdigest(),
        "input_hashes": inputs,
        "started_at": started_at,
        "retain_sessions": runtime.config.retain_sessions,
        "spec": copy.deepcopy(case.spec),
        "prompt": request.prompt,
        "plugins": list(
            dict.fromkeys(Path(str(plugin)).name for plugin in case.spec.get("plugins", []))
        ),
    }
    if case.fixture is not None:
        metadata["fixture"] = {
            "path": str(case.fixture.resolve()),
            "sha256": inputs.get(str(case.fixture.resolve())),
        }
    try:
        for filename, expected_hash in inputs.items():
            path = Path(filename)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                raise RuntimeError(f"Canonical eval input changed after discovery: {path}")
        with _environment(home, _auth_source(runtime.config), workspace) as environment:
            environment["MZ_EVAL_HOOK_LOG"] = str(log)
            _require_success(
                _process(
                    ["git", "init", "-q"],
                    environment=environment,
                    cancelled=runtime.cancelled,
                    workspace=workspace,
                    prefix=root / "git-init",
                    timeout=30,
                ),
                "Git fixture setup",
            )
            if case.fixture is not None:
                _require_success(
                    _process(
                        ["bash", str(case.fixture.resolve())],
                        environment=environment,
                        cancelled=runtime.cancelled,
                        workspace=workspace,
                        prefix=root / "fixture",
                        timeout=60,
                    ),
                    "Fixture",
                )
            initial = workspace_files(workspace)
            write_json(root / "initial-files.json", sorted(initial))
            shutil.copytree(
                workspace,
                root / "initial-workspace",
                symlinks=True,
                ignore=shutil.ignore_patterns(".git"),
            )
            dependencies = list(
                dict.fromkeys(Path(str(plugin)).name for plugin in case.spec.get("plugins", []))
            )
            missing = [name for name in dependencies if name not in runtime.packages]
            if missing:
                raise RuntimeError("Unavailable Codex package dependencies: " + ", ".join(missing))
            _require_success(
                _process(
                    ["codex", "plugin", "marketplace", "add", str(runtime.marketplace)],
                    environment=environment,
                    cancelled=runtime.cancelled,
                    workspace=workspace,
                    prefix=root / "marketplace",
                    timeout=60,
                ),
                "Codex marketplace setup",
            )
            for name in dependencies:
                _require_success(
                    _process(
                        ["codex", "plugin", "add", f"{name}@mozg-eval"],
                        environment=environment,
                        cancelled=runtime.cancelled,
                        workspace=workspace,
                        prefix=root / f"plugin-{name}",
                        timeout=60,
                    ),
                    f"Codex plugin install for {name}",
                )
                package = runtime.packages[name]
                if runtime.probe.native_hooks is False and (package / "hooks/hooks.json").is_file():
                    HookInstaller(
                        Path(environment["CODEX_HOME"]), runtime.probe.runtime_version
                    ).install(
                        package, native_hooks=False, probed_version=runtime.probe.runtime_version
                    )
            execution = case.spec["execution"]
            process = _process(
                codex_command(
                    workspace,
                    runtime.config.model,
                    int(execution.get("max_turns", 0)),
                    retain_sessions=runtime.config.retain_sessions,
                ),
                environment=environment,
                cancelled=runtime.cancelled,
                workspace=workspace,
                prefix=root / "session",
                timeout=int(execution.get("timeout_seconds", 600)),
                stdin=request.prompt,
            )
            (root / "stdout.jsonl").write_text(process.stdout, encoding="utf-8")
            (root / "stderr.txt").write_text(process.stderr, encoding="utf-8")
            events, message, error = _parse_session(process.stdout)
            if process.cancelled:
                execution_status, error = (
                    "error",
                    "Codex session cancelled; process group terminated",
                )
            elif process.timed_out:
                execution_status, error = (
                    "timeout",
                    "Codex session timeout; process group terminated",
                )
            elif process.returncode:
                execution_status, error = "error", f"Codex session exited {process.returncode}"
            elif error:
                execution_status = "error"
    except (OSError, RuntimeError, ValueError) as failure:
        execution_status = "timeout" if isinstance(failure, TimeoutError) else "error"
        error = str(failure)
        LOGGER.warning("Eval execution failed for %s: %s", case.name, error)
    except BaseException as failure:
        execution_status, error = "error", f"Execution interrupted by {type(failure).__name__}"
        raise
    finally:
        # Keep partial session output even when interrupted while communicate() was pending.
        for stage, destination in (
            ("session.stdout.txt", "stdout.jsonl"),
            ("session.stderr.txt", "stderr.txt"),
        ):
            if (root / stage).is_file():
                shutil.copyfile(root / stage, root / destination)
        if not events:
            events, _, _ = _parse_session((root / "stdout.jsonl").read_text(encoding="utf-8"))
        try:
            skill_evidence = analyze_skill_evidence(
                runtime.skill_catalog or SkillCatalog(),
                EvidenceContext(home / ".codex/plugins/cache", workspace, events),
            )
        except (OSError, ValueError) as failure:
            LOGGER.warning("Skill evidence unavailable for %s: %s", case.name, failure)
            skill_evidence = SkillEvidence(
                limitations=(*SkillEvidence().limitations, f"Skill evidence unavailable: {failure}")
            )
        write_json(root / "skill-evidence.json", asdict(skill_evidence))
        final = workspace_files(workspace)
        write_json(root / "initial-files.json", sorted(initial))
        write_json(root / "final-files.json", sorted(final))
        write_json(root / "created-files.json", sorted(final - initial))
        write_json(root / "usage.json", _usage(events))
        metadata.update(
            execution_status=execution_status,
            error=error,
            limitations=limitations,
            completed_at=datetime.now(UTC).isoformat(),
            duration_seconds=monotonic() - started,
            nonfatal_notices=[_HOOK_TRUST_NOTICE]
            if any(event.get("type") == "turn.completed" for event in events)
            and any(_is_hook_trust_notice(event) for event in events)
            else [],
        )
        write_json(root / "case.json", metadata)
    records = tuple(
        json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    return CaseExecution(
        workspace,
        events,
        message,
        final - initial,
        execution_status,
        error,
        limitations,
        records,
        skill_evidence,
    )
