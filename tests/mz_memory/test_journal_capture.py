import json
import os
import re
import subprocess
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from .memory_helpers import BASH, SCRIPTS

SCRIPT = SCRIPTS / "journal-capture.sh"
# Everything the script runs except jq, so a PATH built from these hides jq only.
TOOLS_WITHOUT_JQ = ("dirname", "cat", "date", "mkdir", "perl", "sed", "flock")
SESSION = "3f2b6c1e-8a4d-4f7e-9c2a-1b5d7e9f0a12"
ENTRY_HEADER = re.compile(r"^### (\S+) · session (\S+) · AskUserQuestion$", re.M)

type Capture = Callable[..., None]
type PathWithoutJq = Callable[[Iterable[str]], str]


def _questions(question: str) -> list[dict[str, object]]:
    return [{"question": question, "options": [{"label": "Approve"}, {"label": "Reject"}]}]


def _event(question: str = "Approve the plan?", **overrides: object) -> str:
    event: dict[str, object] = {
        "session_id": SESSION,
        "hook_event_name": "PostToolUse",
        "tool_name": "AskUserQuestion",
        "tool_input": {"questions": _questions(question)},
        "tool_response": {"answers": {question: "Approve"}},
    }
    event.update(overrides)
    return json.dumps(event)


def _compact(value: object) -> str:
    return json.dumps(value, separators=(",", ":"))


@pytest.fixture
def journal(tmp_path: Path) -> Path:
    return tmp_path / ".mz" / "journal.md"


@pytest.fixture
def capture(tmp_path: Path) -> Capture:
    base_env = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
    base_env["MZ_MEMORY_ROOT"] = str(tmp_path)

    def run(stdin: str, path: str = "") -> None:
        result = subprocess.run(
            [BASH, str(SCRIPT)],
            input=stdin,
            env={**base_env, **({"PATH": path} if path else {})},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == ""

    return run


class TestEntry:
    def test_question_and_response_are_recorded_verbatim(
        self, capture: Capture, journal: Path
    ) -> None:
        capture(_event())

        text = journal.read_text(encoding="utf-8")
        header = ENTRY_HEADER.search(text)
        assert header is not None, text
        assert header.group(2) == SESSION
        assert text[header.end() :] == (
            f"\n\nquestions (verbatim):\n{_compact(_questions('Approve the plan?'))}"
            f"\n\nresponse (verbatim):\n{_compact({'answers': {'Approve the plan?': 'Approve'}})}"
            "\n\n"
        )

    def test_header_timestamp_is_current_utc(self, capture: Capture, journal: Path) -> None:
        capture(_event())

        header = ENTRY_HEADER.search(journal.read_text(encoding="utf-8"))
        assert header is not None
        stamp = datetime.strptime(header.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        assert abs(datetime.now(UTC) - stamp) < timedelta(minutes=5)

    def test_missing_session_id_is_recorded_as_unknown(
        self, capture: Capture, journal: Path
    ) -> None:
        event = json.loads(_event())
        del event["session_id"]

        capture(json.dumps(event))

        header = ENTRY_HEADER.search(journal.read_text(encoding="utf-8"))
        assert header is not None
        assert header.group(2) == "unknown"

    def test_tool_input_without_questions_is_recorded_whole(
        self, capture: Capture, journal: Path
    ) -> None:
        capture(_event(tool_input={"prompt": "Pick one"}))

        assert '\nquestions (verbatim):\n{"prompt":"Pick one"}\n' in journal.read_text(
            encoding="utf-8"
        )


class TestJournalFile:
    def test_first_write_creates_the_file_with_its_header(
        self, capture: Capture, journal: Path
    ) -> None:
        capture(_event())

        assert journal.read_text(encoding="utf-8").startswith("# Interaction Journal\n\n")

    def test_later_calls_append_after_earlier_entries(
        self, capture: Capture, journal: Path
    ) -> None:
        capture(_event("First question?"))
        capture(_event("Second question?"))

        text = journal.read_text(encoding="utf-8")
        assert text.count("# Interaction Journal") == 1
        assert len(ENTRY_HEADER.findall(text)) == 2
        assert text.index("First question?") < text.index("Second question?")


class TestPrivacy:
    def test_private_span_is_written_as_redacted(self, capture: Capture, journal: Path) -> None:
        capture(_event("Email <private>jane@acme.test</private> today?"))

        text = journal.read_text(encoding="utf-8")
        assert "jane@acme.test" not in text
        assert "Email [redacted] today?" in text


class TestSilentExits:
    @pytest.mark.parametrize(
        "stdin",
        [_event(tool_name="Bash"), "{not json", ""],
        ids=["other-tool", "malformed", "empty"],
    )
    def test_unusable_input_writes_nothing(
        self, capture: Capture, journal: Path, stdin: str
    ) -> None:
        capture(stdin)

        assert not journal.parent.exists()

    def test_missing_jq_writes_nothing(
        self, capture: Capture, journal: Path, path_without_jq: PathWithoutJq
    ) -> None:
        capture(_event(), path_without_jq(TOOLS_WITHOUT_JQ))

        assert not journal.parent.exists()
