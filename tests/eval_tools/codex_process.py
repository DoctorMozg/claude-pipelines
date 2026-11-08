"""Own isolated eval environments and subprocess lifetimes."""

import json
import os
import signal
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from time import monotonic

from mozg_pipelines.process_groups import terminate_process_group as _terminate_group


@dataclass(frozen=True)
class _ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    cancelled: bool = False


@contextmanager
def _environment(home: Path, source_home: Path, workspace: Path) -> Iterator[dict[str, str]]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("CODEX_", "CLAUDE_", "MZ_", "EVAL_", "GIT_"))
        or key == "CODEX_API_KEY"
    }
    codex_home = home / ".codex"
    codex_home.mkdir(parents=True, exist_ok=True)
    auth = codex_home / "auth.json"
    source_auth = source_home / "auth.json"
    try:
        if source_auth.is_file():
            auth.symlink_to(source_auth.resolve())
        environment.update(
            HOME=str(home),
            CODEX_HOME=str(codex_home),
            XDG_CONFIG_HOME=str(home / ".config"),
            CLAUDE_PROJECT_DIR=str(workspace),
            MZ_MEMORY_COMPRESS="0",
        )
        yield environment
    finally:
        # Codex may refresh credentials by replacing the link; retain neither form in artifacts.
        auth.unlink(missing_ok=True)


def _process(
    command: list[str],
    *,
    environment: dict[str, str],
    workspace: Path,
    prefix: Path,
    timeout: int,
    stdin: str = "",
    cancelled: Event | None = None,
) -> _ProcessResult:
    if timeout <= 0:
        raise ValueError("Command timeout must be positive")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    stdout_path = prefix.with_name(prefix.name + ".stdout.txt")
    stderr_path = prefix.with_name(prefix.name + ".stderr.txt")
    process: subprocess.Popen[str] | None = None
    stdout, stderr = "", ""
    timed_out = False
    was_cancelled = False
    started, started_at = monotonic(), datetime.now(UTC).isoformat()
    try:
        if cancelled is not None and cancelled.is_set():
            was_cancelled = True
            return _ProcessResult(-signal.SIGKILL, "", "", cancelled=True)
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=workspace,
            env=environment,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        )
        pending_input: str | None = stdin
        deadline = monotonic() + timeout
        while True:
            was_cancelled = cancelled is not None and cancelled.is_set()
            remaining = deadline - monotonic()
            if was_cancelled or remaining <= 0:
                timed_out = not was_cancelled
                _terminate_group(process.pid)
                stdout, stderr = process.communicate()
                break
            try:
                stdout, stderr = process.communicate(
                    input=pending_input, timeout=min(0.2, remaining)
                )
                break
            except subprocess.TimeoutExpired:
                pending_input = None
        return _ProcessResult(process.returncode, stdout, stderr, timed_out, was_cancelled)
    except BaseException:
        if process is not None:
            _terminate_group(process.pid)
            stdout, stderr = process.communicate()
        raise
    finally:
        if process is not None:
            _terminate_group(process.pid)
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        receipt = {
            "argv": command,
            "workspace": str(workspace),
            "timeout": timeout,
            "returncode": process.returncode if process is not None else None,
            "timed_out": timed_out,
            "started_at": started_at,
            "cancelled": was_cancelled,
            "duration_seconds": monotonic() - started,
        }
        prefix.with_name(prefix.name + ".command.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
        )


def _require_success(result: _ProcessResult, stage: str) -> None:
    if result.cancelled:
        raise RuntimeError(f"{stage} cancelled; see retained command diagnostics")
    if result.timed_out:
        raise TimeoutError(f"{stage} timeout; see retained command diagnostics")
    if result.returncode:
        raise RuntimeError(
            f"{stage} failed with exit {result.returncode}; see retained diagnostics"
        )
