import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins" / "mz-memory" / "scripts"
BASH = shutil.which("bash") or "/bin/bash"

PIN_START = "<!-- mz-pinned-start -->"
PIN_END = "<!-- mz-pinned-end -->"
DIGEST_START = "<!-- mz-digest-start -->"
DIGEST_END = "<!-- mz-digest-end -->"
LOG_START = "<!-- mz-log-start -->"
LOG_END = "<!-- mz-log-end -->"
LESSONS_START = "<!-- mz-lessons-start -->"
LESSONS_END = "<!-- mz-lessons-end -->"
INBOX_START = "<!-- mz-inbox-start -->"
INBOX_END = "<!-- mz-inbox-end -->"
# Mirrors MZ_LESSON_MAX_CHARS in lib/lessons.sh.
LESSON_MAX_CHARS = 400
COMPACT_INPUT = json.dumps({"hook_event_name": "SessionStart", "source": "compact"})
HINT_START = "Promotion candidates (seen 3+ times): "
TRUNCATION_MARK = "\n...[memory truncated]"

# A background run's PATH holds only these and the claude stub, so the real CLI never runs.
SANDBOX_TOOLS = (
    "bash",
    "dirname",
    "mkdir",
    "rmdir",
    "mktemp",
    "mv",
    "cp",
    "rm",
    "cat",
    "awk",
    "grep",
    "head",
    "tail",
    "wc",
    "sort",
    "cut",
    "find",
    "date",
    "jq",
)
# The scripts degrade without these, so a host that lacks them still runs the suite.
OPTIONAL_TOOLS = ("flock", "timeout")
# Every setting the scripts take from their caller; a test sets the ones it needs itself.
CALLER_VARS = frozenset(
    {
        "CLAUDE_PROJECT_DIR",
        "CLAUDE_PLUGIN_ROOT",
        "MZ_MEMORY_ROOT",
        "MZ_MEMORY_COMPRESS",
        "MZ_MEMORY_CURATOR",
        "MZ_MEMORY_CURATOR_MODEL",
    }
)

CLAUDE_STUB = """#!{bash}
rec={record}
cat >"$rec/prompt"
printf '%s\\n' "$@" >"$rec/args"
printf '%s\\n' "MZ_MEMORY_CURATOR=${{MZ_MEMORY_CURATOR-unset}}" \\
  "MZ_MEMORY_COMPRESS=${{MZ_MEMORY_COMPRESS-unset}}" "PWD=$PWD" >"$rec/env"
if [ -f "$rec/during.sh" ]; then . "$rec/during.sh"; fi
cat "$rec/response"
exit "$(cat "$rec/exit_code")"
"""


type CaptureRunner = Callable[[dict[str, str]], None]
type MarkChanged = Callable[[Path], None]


class TaskWriter(Protocol):
    def __call__(self, name: str, status: str, extra: str = "") -> Path: ...


class RawTaskWriter(Protocol):
    def __call__(self, name: str, text: str) -> Path: ...


class SeedLessons(Protocol):
    def __call__(self, curated: Sequence[str], inbox: Sequence[str] = ()) -> Path: ...


@dataclass(frozen=True)
class FakeCurator:
    """The stub claude on PATH: replies with a canned result and records how it was called."""

    record: Path

    def respond(self, *operations: dict[str, object]) -> None:
        envelope = {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "structured_output": {"operations": list(operations)},
        }
        self.respond_raw(json.dumps(envelope))

    def respond_raw(self, text: str, exit_code: int = 0) -> None:
        (self.record / "response").write_text(text, encoding="utf-8")
        (self.record / "exit_code").write_text(str(exit_code), encoding="utf-8")

    def during_call(self, script: str) -> None:
        (self.record / "during.sh").write_text(script, encoding="utf-8")

    @property
    def called(self) -> bool:
        return (self.record / "prompt").exists()

    def prompt(self) -> str:
        return (self.record / "prompt").read_text(encoding="utf-8")

    def args(self) -> list[str]:
        return (self.record / "args").read_text(encoding="utf-8").split("\n")[:-1]

    def arg(self, flag: str) -> str:
        args = self.args()
        return args[args.index(flag) + 1]

    def env(self) -> dict[str, str]:
        lines = (self.record / "env").read_text(encoding="utf-8").splitlines()
        return {key: value for key, _, value in (line.partition("=") for line in lines)}


def clean_env() -> dict[str, str]:
    """os.environ without CALLER_VARS, plus the CLAUDE_PLUGIN_ROOT Claude Code gives every hook."""
    env = {key: value for key, value in os.environ.items() if key not in CALLER_VARS}
    return {**env, "CLAUDE_PLUGIN_ROOT": str(SCRIPTS.parent)}


def op(kind: str, **fields: object) -> dict[str, object]:
    """One curator operation, with every field the schema requires."""
    return {"op": kind, "inbox": [], "lessons": [], "text": "", "tags": [], "reason": "", **fields}


def memory_dir(project: Path) -> Path:
    return project / ".mz" / "memory"


def memory_file(project: Path) -> Path:
    return memory_dir(project) / "MEMORY.md"


def lessons_file(project: Path) -> Path:
    return memory_dir(project) / "lessons.md"


def region(path: Path, start: str, end: str) -> list[str]:
    """The lines between two markers; empty when the file has no such region."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if start not in lines:
        return []
    return lines[lines.index(start) + 1 : lines.index(end)]


def curated_lines(project: Path) -> list[str]:
    return region(lessons_file(project), LESSONS_START, LESSONS_END)


def inbox_lines(project: Path) -> list[str]:
    return region(lessons_file(project), INBOX_START, INBOX_END)


def line_ids(lines: list[str]) -> list[str]:
    return [line.split()[1] for line in lines]


def line_text(line: str) -> str:
    return line.split(" :: ", 1)[1]


def line_texts(lines: list[str]) -> list[str]:
    return [line_text(line) for line in lines]


def line_field(line: str, name: str) -> str:
    match = re.search(rf"\b{name}=(\S+)", line.split(" :: ", 1)[0])
    assert match is not None, f"{name}= missing from {line!r}"
    return match.group(1)


def ok(result: subprocess.CompletedProcess[str]) -> subprocess.CompletedProcess[str]:
    assert result.returncode == 0, result.stderr
    return result


needs_non_root = pytest.mark.skipif(os.geteuid() == 0, reason="root writes whatever the mode")


@contextmanager
def read_only(directory: Path) -> Iterator[None]:
    """Make `directory` unwritable for the block, then writable again even if the block fails."""
    directory.chmod(0o555)
    try:
        yield
    finally:
        directory.chmod(0o755)


def section_lines(context: str, heading: str) -> list[str]:
    """The lines under `heading` in injected context, up to the blank line that ends the section."""
    lines = context.splitlines()
    if heading not in lines:
        return []
    body = lines[lines.index(heading) + 1 :]
    return body[: body.index("")] if "" in body else body


def log_entries(context: str) -> list[str]:
    """The activity log lines of injected context; each starts with its date."""
    return [line for line in context.splitlines() if line.startswith("- [2")]


def lessons_layout(curated: Sequence[str], inbox: Sequence[str]) -> str:
    """lessons.md as the scripts create it, holding the given lines."""
    lines = [
        "# Project Lessons",
        "",
        "<!-- Auto-managed by mz-memory. Curated lessons first; new lessons wait in the Inbox. -->",
        "",
        "## Lessons",
        "",
        LESSONS_START,
        *curated,
        LESSONS_END,
        "",
        "## Inbox",
        "",
        INBOX_START,
        *inbox,
        INBOX_END,
    ]
    return "\n".join(lines) + "\n"
