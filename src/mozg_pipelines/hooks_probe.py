"""Check hook delivery against an isolated native plugin and user-hook control."""

import json
import logging
import os
import secrets
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from mozg_pipelines.process_groups import terminate_process_group

logger = logging.getLogger(__name__)
_EVENTS = ("SessionStart", "UserPromptSubmit", "PostToolUse", "Stop", "SessionEnd")
_SELECTOR = "probe@hook-probe-market"
_PROMPT = (
    "Use apply_patch to create probe.txt containing exactly probe-ok followed by a newline. "
    "Then reply with only the nonce supplied in startup hook context, or UNKNOWN if none was "
    "supplied. Do not inspect other files or use tools to discover the nonce."
)


@dataclass(frozen=True)
class ProbeResult:
    runtime_version: str
    native_hooks: bool | None
    events: tuple[str, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class _CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class _SessionResult:
    events: tuple[str, ...]
    errors: tuple[str, ...]
    context_received: bool


class _ProbeFailure(RuntimeError):
    pass


def _environment(home: Path) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("CODEX_", "CLAUDE_", "MZ_", "EVAL_", "GIT_"))
        or key == "CODEX_API_KEY"
    }
    environment.update(
        HOME=str(home.parent), CODEX_HOME=str(home), XDG_CONFIG_HOME=str(home.parent / ".config")
    )
    return environment


def _command(
    arguments: list[str],
    *,
    environment: dict[str, str],
    timeout: int,
    prompt: str | None = None,
    executable: str = "codex",
) -> _CommandResult:
    try:
        process = subprocess.Popen(
            [executable, *arguments],
            env=environment,
            cwd=environment["HOME"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as error:
        raise _ProbeFailure(f"Could not start the {executable.capitalize()} executable") from error
    try:
        stdout, stderr = process.communicate(input=prompt, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        terminate_process_group(process.pid)
        process.communicate()
        raise _ProbeFailure(
            "Codex diagnostic timed out; its process group was terminated"
        ) from error
    except BaseException:
        terminate_process_group(process.pid)
        process.communicate()
        raise
    finally:
        terminate_process_group(process.pid)
    return _CommandResult(process.returncode, stdout, stderr)


def _version(environment: dict[str, str]) -> str:
    result = _command(["--version"], environment=environment, timeout=15)
    if result.returncode != 0 or not result.stdout.strip().startswith("codex-cli "):
        raise _ProbeFailure("Could not determine the Codex runtime version")
    return result.stdout.strip().splitlines()[0]


def codex_version() -> str:
    """Read the installed runtime version without loading the user's Codex home."""
    with TemporaryDirectory(prefix="mozg-codex-version-") as directory:
        home = Path(directory) / ".codex"
        home.mkdir()
        return _version(_environment(home))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _write_plugin(root: Path, markers: Path, nonce: str) -> dict[str, object]:
    plugin = root / "packages" / "probe"
    plugin.mkdir(parents=True)
    handler = plugin / "handler.py"
    handler.write_text(
        "import json, pathlib, sys\n"
        "payload = json.load(sys.stdin)\n"
        "event = payload.get('hook_event_name', '')\n"
        "with pathlib.Path(sys.argv[1]).open('a') as stream:\n"
        "    stream.write(json.dumps({'event': event}) + '\\n')\n"
        "if event == 'SessionStart':\n"
        "    print(json.dumps({'hookSpecificOutput': {'hookEventName': event,\n"
        f"        'additionalContext': 'Diagnostic startup nonce: {nonce}'}}}}))\n",
        encoding="utf-8",
    )
    command = shlex.join([sys.executable, str(handler), str(markers)])
    hooks: dict[str, object] = {
        "hooks": {
            event: [{"hooks": [{"type": "command", "command": command}]}] for event in _EVENTS
        }
    }
    _write_json(plugin / "hooks" / "hooks.json", hooks)
    _write_json(
        plugin / "plugin.json",
        {
            "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
            "name": "probe",
            "version": "0.0.0",
            "description": "Isolated hook delivery diagnostic",
            "author": {"name": "Mozg diagnostic"},
            "extensions": {"com.openai": {"hooks": "./hooks/hooks.json"}},
        },
    )
    _write_json(
        root / ".agents" / "plugins" / "marketplace.json",
        {
            "name": "hook-probe-market",
            "owner": {"name": "Mozg diagnostic"},
            "plugins": [{"name": "probe", "source": "./packages/probe"}],
        },
    )
    return hooks


def _object(line: str) -> dict[str, object]:
    value: object = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return cast(dict[str, object], value)


def _read_events(markers: Path) -> tuple[str, ...]:
    if not markers.exists():
        return ()
    events: list[str] = []
    for line in markers.read_text(encoding="utf-8").splitlines():
        event = _object(line).get("event")
        if not isinstance(event, str) or event not in _EVENTS:
            raise ValueError("Invalid hook marker")
        if event not in events:
            events.append(event)
    return tuple(events)


def _session(
    workspace: Path,
    *,
    markers: Path,
    nonce: str,
    arguments: list[str],
    environment: dict[str, str],
    timeout: int,
) -> _SessionResult:
    workspace.mkdir()
    initialized = _command(
        ["init", "--quiet", str(workspace)],
        environment=environment,
        timeout=timeout,
        executable="git",
    )
    if initialized.returncode != 0:
        raise _ProbeFailure("Could not initialize the isolated diagnostic workspace")
    result = _command(
        [
            "exec",
            "--json",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--dangerously-bypass-hook-trust",
            "--cd",
            str(workspace),
            *arguments,
            "-",
        ],
        environment=environment,
        timeout=timeout,
        prompt=_PROMPT,
    )
    try:
        events = _read_events(markers)
    except (ValueError, OSError):
        return _SessionResult((), ("Hook marker output was malformed or unreadable",), False)
    if result.returncode != 0:
        return _SessionResult(
            events, (f"Codex diagnostic exited with code {result.returncode}",), False
        )
    try:
        output = [_object(line) for line in result.stdout.splitlines() if line.strip()]
    except ValueError:
        return _SessionResult(events, ("Codex diagnostic output was not valid JSONL",), False)
    if any(not isinstance(event.get("type"), str) for event in output):
        return _SessionResult(events, ("Codex diagnostic events had invalid types",), False)
    if any(event.get("type") in ("turn.failed", "error") for event in output):
        return _SessionResult(events, ("Codex diagnostic reported a runtime failure",), False)
    if not any(event.get("type") == "turn.completed" for event in output):
        return _SessionResult(events, ("Codex diagnostic did not complete its turn",), False)
    items = [event.get("item") for event in output if event.get("type") == "item.completed"]
    context_received = any(
        isinstance(item, dict)
        and item.get("type") == "agent_message"
        and nonce in str(item.get("text", ""))
        for item in items
    )
    file_changed = any(
        isinstance(item, dict) and item.get("type") == "file_change" for item in items
    )
    probe_file = workspace / "probe.txt"
    if not file_changed or not probe_file.is_file() or probe_file.read_text() != "probe-ok\n":
        return _SessionResult(
            events, ("Codex diagnostic did not perform the requested file edit",), False
        )
    return _SessionResult(events, (), context_received)


def _delivery_errors(session: _SessionResult) -> tuple[str, ...]:
    missing = [event for event in _EVENTS if event not in session.events]
    errors = session.errors
    if missing:
        errors += ("Hooks did not deliver required events: " + ", ".join(missing),)
    if not session.context_received:
        errors += ("Startup hook context was not confirmed by the model",)
    return errors


def probe_hooks(*, codex_home: Path, model: str = "gpt-6.1-sol", timeout: int = 90) -> ProbeResult:
    """Prove native hook delivery, falling back to an isolated user-hook control.

    ``False`` means the control passed while native hooks emitted no events. ``None``
    means delivery was inconclusive, including runtime, auth, network, and partial-event failures.
    The hook trust bypass is restricted to these self-authored temporary diagnostic sessions.
    """
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if not model.strip():
        raise ValueError("model must not be empty")
    if not codex_home.is_dir():
        raise ValueError("codex_home must be an existing directory")
    version = ""
    events: tuple[str, ...] = ()
    try:
        with TemporaryDirectory(prefix="mozg-hook-probe-") as directory:
            root = Path(directory)
            home = root / "home" / ".codex"
            home.mkdir(parents=True)
            auth = codex_home.resolve() / "auth.json"
            if auth.is_file():
                (home / "auth.json").symlink_to(auth)
            environment = _environment(home)
            version = _version(environment)
            markers = root / "events.jsonl"
            nonce = secrets.token_hex(24)
            marketplace = root / "marketplace"
            hooks = _write_plugin(marketplace, markers, nonce)
            for arguments in (
                ["plugin", "marketplace", "add", str(marketplace)],
                ["plugin", "add", _SELECTOR],
            ):
                installed = _command(arguments, environment=environment, timeout=timeout)
                if installed.returncode != 0:
                    stage = " ".join(arguments[:-1])
                    # Report known error categories, never arbitrary credential-bearing CLI output.
                    reason = next(
                        (
                            category
                            for category in (
                                "missing plugin.json",
                                "permission denied",
                                "not found",
                            )
                            if category in installed.stderr.lower()
                        ),
                        "unclassified CLI error",
                    )
                    raise _ProbeFailure(
                        f"Could not install the isolated diagnostic plugin "
                        f"({stage}, exit {installed.returncode}: {reason})"
                    )
            logger.info("Checking native hook delivery with Codex %s", version)
            native = _session(
                root / "native-workspace",
                markers=markers,
                nonce=nonce,
                arguments=["--model", model],
                environment=environment,
                timeout=timeout,
            )
            events = native.events
            errors = _delivery_errors(native)
            if not errors:
                return ProbeResult(version, True, events, ())
            if native.errors or native.events:
                return ProbeResult(version, None, events, errors)
            logger.info("Native hooks emitted no events; checking the user-hook control")
            markers.unlink(missing_ok=True)
            _write_json(home / "hooks.json", hooks)
            control = _session(
                root / "control-workspace",
                markers=markers,
                nonce=nonce,
                arguments=["--model", model, "-c", f'plugins."{_SELECTOR}".enabled=false'],
                environment=environment,
                timeout=timeout,
            )
            events = control.events
            control_errors = _delivery_errors(control)
            if control_errors:
                return ProbeResult(
                    version, None, events, ("User-hook control failed", *control_errors)
                )
            return ProbeResult(version, False, events, ())
    except (_ProbeFailure, OSError, UnicodeError) as error:
        message = (
            str(error) if isinstance(error, _ProbeFailure) else "Could not prepare hook diagnostic"
        )
        logger.warning("Hook diagnostic was inconclusive: %s", message)
        return ProbeResult(version, None, events, (message,))
