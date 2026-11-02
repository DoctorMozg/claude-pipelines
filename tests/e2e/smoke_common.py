"""Helpers shared by the live smoke harnesses: headless claude runs, their events, check reports."""

import json
import logging
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("smoke")

Event = dict[str, Any]


class SmokeError(RuntimeError):
    """A precondition or tool failure that stops the run before any verdict."""


@dataclass(frozen=True)
class Check:
    label: str
    expected: object
    actual: object

    @property
    def passed(self) -> bool:
        return self.expected == self.actual


def run_claude(command: Sequence[str], cwd: Path, transcript: Path, timeout_s: int) -> bool:
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
