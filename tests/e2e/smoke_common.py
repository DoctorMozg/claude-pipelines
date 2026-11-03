"""Helpers shared by the live smoke harnesses: headless claude runs, their events, check reports."""

import json
import logging
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("smoke")

Event = dict[str, Any]


class SmokeError(RuntimeError):
    """A precondition or tool failure that stops the run before any verdict."""


@dataclass(frozen=True)
class Session:
    label: str
    events: list[Event]
    cost_usd: float

    def hook_outputs(self, hook_name: str) -> list[str]:
        return [
            str(event.get("output") or "")
            for event in self.events
            if event.get("subtype") == "hook_response" and event.get("hook_name") == hook_name
        ]

    def failed_hooks(self) -> list[object]:
        return [
            event.get("hook_name")
            for event in self.events
            if event.get("subtype") == "hook_response" and event.get("outcome") != "success"
        ]

    def tool_inputs(self, tool: str) -> list[dict[str, Any]]:
        return [
            block.get("input") or {}
            for event in self.events
            if event.get("type") == "assistant"
            for block in (event.get("message") or {}).get("content") or []
            if isinstance(block, dict)
            and block.get("type") == "tool_use"
            and block.get("name") == tool
        ]

    def init(self) -> Event:
        return next(
            (e for e in self.events if e.get("type") == "system" and e.get("subtype") == "init"), {}
        )


def plugin_free_env(extra: Mapping[str, str]) -> dict[str, str]:
    """The caller's environment minus plugin settings, which would skew what runs check."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("MZ_") and key != "OBSIDIAN_VAULT_PATH"
    }
    return env | dict(extra)


@dataclass(frozen=True)
class HeadlessClaude:
    """Runs `claude -p` sessions in `cwd` with stream-json output, one transcript per label."""

    workdir: Path
    cwd: Path
    model: str
    max_usd: float
    timeout_s: int
    extra_env: Mapping[str, str] = field(default_factory=dict)

    def run(
        self, label: str, prompt: str, plugins: Sequence[Path], args: Sequence[str] = ()
    ) -> Session:
        plugin_dirs = [arg for path in plugins for arg in ("--plugin-dir", str(path))]
        command = [
            "claude",
            "-p",
            prompt,
            "--model",
            self.model,
            # Only local settings: the user's own installed plugins and hooks would add noise.
            "--setting-sources",
            "local",
            *plugin_dirs,
            *args,
            "--max-budget-usd",
            f"{self.max_usd:.2f}",
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-hook-events",
        ]
        transcript = self.workdir / f"{label}.jsonl"
        log.info("starting %s", label)
        if not run_claude(
            command, self.cwd, transcript, self.timeout_s, plugin_free_env(self.extra_env)
        ):
            raise SmokeError(f"{label} timed out; see {transcript}")
        events = stream_events(transcript)
        result = result_event(events)
        if result is None:
            raise SmokeError(f"{label} left no result event; see {transcript}")
        return Session(label, events, float(result.get("total_cost_usd", 0.0)))


def forget_session(session_id: str, repo: Path) -> None:
    """Delete the transcript a run left in the claude config dir, which `--resume` needed."""
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    # Claude Code names a project's transcript folder after its path, every other character a dash.
    project_name = re.sub(r"[^A-Za-z0-9]", "-", str(repo.resolve()))
    for transcript in config.glob(f"projects/*/{session_id}.jsonl"):
        if transcript.parent.name == project_name:
            shutil.rmtree(transcript.parent)
        else:
            transcript.unlink()
        log.info("removed %s", transcript)


def run_seed(repo: Path, script: str, *args: str) -> None:
    """Run a bash seeding script in `repo`, passing `args` as $1, $2, ..."""
    try:
        subprocess.run(
            ["bash", "-c", script, "seed", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise SmokeError(f"seeding {repo} failed: {error.stderr.strip()}") from error


@dataclass(frozen=True)
class Check:
    label: str
    expected: object
    actual: object

    @property
    def passed(self) -> bool:
        return self.expected == self.actual


def run_claude(
    command: Sequence[str],
    cwd: Path,
    transcript: Path,
    timeout_s: int,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Run a headless claude command into `transcript`; False when it timed out."""
    with transcript.open("w", encoding="utf-8") as out:
        try:
            # stdin is closed so `claude -p` doesn't wait 3 s for piped input.
            subprocess.run(
                list(command),
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.STDOUT,
                timeout=timeout_s,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired:
            log.error("%s timed out after %ds", transcript.stem, timeout_s)
            return False
    return True


def stream_events(transcript: Path) -> list[Event]:
    """The JSON events of a stream-json transcript, skipping the CLI warnings mixed into it."""
    events: list[Event] = []
    for line in transcript.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def result_event(events: Sequence[Event]) -> Event | None:
    return next((event for event in reversed(events) if event.get("type") == "result"), None)


def print_checks(title: str, checks: Sequence[Check]) -> bool:
    print(f"\n{title}")
    all_passed = True
    for check in checks:
        all_passed &= check.passed
        mark = "PASS" if check.passed else "FAIL"
        detail = "" if check.passed else f"  expected {check.expected!r}, got {check.actual!r}"
        print(f"  {mark}  {check.label}{detail}")
    return all_passed
