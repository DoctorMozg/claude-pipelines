import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins" / "mz-memory" / "scripts"
PROMOTE_SCRIPT = SCRIPTS / "lessons-promote.sh"
INJECT_SCRIPT = SCRIPTS / "memory-inject.sh"
TODAY = "2026-11-02"
LESSONS_START = "<!-- mz-lessons-start -->"
LESSONS_END = "<!-- mz-lessons-end -->"
INBOX_START = "<!-- mz-inbox-start -->"
INBOX_END = "<!-- mz-inbox-end -->"
HINT_START = "Promotion candidates (seen 3+ times): "
COMPACT_INPUT = json.dumps({"hook_event_name": "SessionStart", "source": "compact"})

type HintReader = Callable[[], str]


class Runner(Protocol):
    def __call__(self, *args: str) -> subprocess.CompletedProcess[str]: ...


class SeedLessons(Protocol):
    def __call__(self, curated: list[str], inbox: list[str] | None = None) -> None: ...


def lesson(number: int, n: int, last: str = "2026-10-01") -> str:
    return (
        f"- [L-{number:04d}] n={n} last={last} trig=review src=task{number}@abc1234 tags=jq"
        f" :: WHEN case {number} → handle it — WHY reason {number}"
    )


def inbox_item(number: int) -> str:
    return (
        f"- [I-{number:04d}] 2026-11-01 trig=failure src=task{number} status=failed"
        f" :: WHEN new case {number} → try it — WHY fresh"
    )


def _memory_dir(project: Path) -> Path:
    return project / ".mz" / "memory"


def _lessons_text(project: Path) -> str:
    return (_memory_dir(project) / "lessons.md").read_text(encoding="utf-8")


@pytest.fixture
def env(project: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """Environment with `date` pinned, so archive lines and events carry a known date."""
    shim_dir = tmp_path_factory.mktemp("shims")
    date_shim = shim_dir / "date"
    date_shim.write_text(f'#!/bin/sh\nprintf "%s\\n" "{TODAY}"\n', encoding="utf-8")
    date_shim.chmod(0o755)
    base = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
    return {**base, "MZ_MEMORY_ROOT": str(project), "PATH": f"{shim_dir}{os.pathsep}{base['PATH']}"}


@pytest.fixture
def promote(env: dict[str, str]) -> Runner:
    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(PROMOTE_SCRIPT), *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    return run


@pytest.fixture
def hint(env: dict[str, str]) -> HintReader:
    """The promotion hint line from a real SessionStart run, or "" when there is none."""

    def read() -> str:
        result = subprocess.run(
            ["bash", str(INJECT_SCRIPT)],
            input=COMPACT_INPUT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        return "\n".join(line for line in context.splitlines() if line.startswith(HINT_START))

    return read


@pytest.fixture
def seed(project: Path) -> SeedLessons:
    def write(curated: list[str], inbox: list[str] | None = None) -> None:
        lines = [
            "# Project Lessons",
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
            *(inbox or []),
            INBOX_END,
        ]
        _memory_dir(project).mkdir(parents=True, exist_ok=True)
        (_memory_dir(project) / "lessons.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return write


def _ok(result: subprocess.CompletedProcess[str]) -> subprocess.CompletedProcess[str]:
    assert result.returncode == 0, result.stderr
    return result


def _refused(result: subprocess.CompletedProcess[str], fragment: str) -> None:
    assert result.returncode == 2
    assert fragment in result.stderr
    assert result.stdout == ""


class TestList:
    def test_candidates_are_curated_lessons_seen_three_times_most_seen_first(
        self, promote: Runner, seed: SeedLessons
    ) -> None:
        seed(
            [lesson(1, n=3), lesson(2, n=5), lesson(3, n=2), lesson(4, n=3, last="2026-10-20")],
            [inbox_item(5)],
        )

        assert _ok(promote("list")).stdout.splitlines() == [
            lesson(2, n=5),
            lesson(4, n=3, last="2026-10-20"),
            lesson(1, n=3),
        ]

    def test_nothing_to_list_prints_nothing(self, promote: Runner, seed: SeedLessons) -> None:
        seed([lesson(1, n=2)], [inbox_item(2)])

        assert _ok(promote("list")).stdout == ""

    def test_missing_lessons_file_prints_nothing(self, promote: Runner) -> None:
        assert _ok(promote("list")).stdout == ""

    def test_named_ids_are_listed_in_the_given_order_whatever_their_count(
        self, promote: Runner, seed: SeedLessons
    ) -> None:
        seed([lesson(1, n=1), lesson(2, n=5)], [inbox_item(3)])

        assert _ok(promote("list", "I-0003", "L-0001")).stdout.splitlines() == [
            inbox_item(3),
            lesson(1, n=1),
        ]

    def test_unknown_id_fails_without_a_partial_list(
        self, promote: Runner, seed: SeedLessons
    ) -> None:
        seed([lesson(1, n=4)])

        _refused(promote("list", "L-0001", "L-0009"), "L-0009 is not in")

    @pytest.mark.parametrize("bad_id", ["L42", "l-0001", "X-0001", "L-0001;rm"])
    def test_malformed_id_is_refused(self, promote: Runner, seed: SeedLessons, bad_id: str) -> None:
        seed([lesson(1, n=4)])

        _refused(promote("list", bad_id), "not a lesson id")


class TestArchive:
    def test_archived_lesson_moves_to_the_archive_as_promoted(
        self, project: Path, promote: Runner, seed: SeedLessons
    ) -> None:
        seed([lesson(1, n=4), lesson(2, n=3)], [inbox_item(3)])

        result = _ok(promote("archive", "L-0001", ".claude/rules/jq.md"))

        assert result.stdout == "Archived L-0001 as promoted to .claude/rules/jq.md\n"
        archive = (_memory_dir(project) / "lessons.archive.md").read_text(encoding="utf-8")
        assert archive == f"{TODAY} promoted_to=.claude/rules/jq.md: {lesson(1, n=4)}\n"
        text = _lessons_text(project)
        assert lesson(1, n=4) not in text
        assert lesson(2, n=3) in text
        assert inbox_item(3) in text

    def test_only_the_lesson_line_leaves_the_file(
        self, project: Path, promote: Runner, seed: SeedLessons
    ) -> None:
        seed([lesson(1, n=4), lesson(2, n=3)], [inbox_item(3)])
        before = _lessons_text(project)

        _ok(promote("archive", "L-0002", "CLAUDE.md"))

        assert _lessons_text(project) == before.replace(lesson(2, n=3) + "\n", "")

    def test_an_inbox_item_can_be_promoted(
        self, project: Path, promote: Runner, seed: SeedLessons
    ) -> None:
        seed([lesson(1, n=4)], [inbox_item(3)])

        _ok(promote("archive", "I-0003", "CLAUDE.md"))

        assert inbox_item(3) not in _lessons_text(project)

    def test_earlier_archive_lines_are_kept(
        self, project: Path, promote: Runner, seed: SeedLessons
    ) -> None:
        seed([lesson(1, n=4)])
        archive = _memory_dir(project) / "lessons.archive.md"
        archive.write_text("2026-10-01 evicted: - [L-0000] old\n", encoding="utf-8")

        _ok(promote("archive", "L-0001", "CLAUDE.md"))

        assert archive.read_text(encoding="utf-8").splitlines()[0] == (
            "2026-10-01 evicted: - [L-0000] old"
        )

    def test_promotion_is_logged_with_the_curator_events(
        self, project: Path, promote: Runner, seed: SeedLessons
    ) -> None:
        seed([lesson(1, n=4)])

        _ok(promote("archive", "L-0001", "CLAUDE.md"))

        events = (_memory_dir(project) / "lessons.ops.jsonl").read_text(encoding="utf-8")
        assert json.loads(events) == {
            "date": TODAY,
            "event": "promoted",
            "why": "L-0001 to CLAUDE.md",
        }

    def test_missing_lesson_is_refused_and_nothing_changes(
        self, project: Path, promote: Runner, seed: SeedLessons
    ) -> None:
        seed([lesson(1, n=4)])
        before = _lessons_text(project)

        _refused(promote("archive", "L-0009", "CLAUDE.md"), "may have merged or archived")

        assert _lessons_text(project) == before
        assert not (_memory_dir(project) / "lessons.archive.md").exists()

    @pytest.mark.parametrize("target", ["", "CLAUDE", "my rules.md", ".claude/rules/x.txt"])
    def test_target_must_be_a_markdown_path_without_spaces(
        self, project: Path, promote: Runner, seed: SeedLessons, target: str
    ) -> None:
        seed([lesson(1, n=4)])
        before = _lessons_text(project)

        _refused(promote("archive", "L-0001", target), "must be a .md path")

        assert _lessons_text(project) == before


class TestDecline:
    def test_declined_lesson_is_no_longer_a_candidate(
        self, promote: Runner, seed: SeedLessons
    ) -> None:
        seed([lesson(1, n=4), lesson(2, n=3)])

        result = _ok(promote("decline", "L-0001"))

        assert result.stdout == "Declined L-0001 at n=4; it is offered again once it recurs\n"
        assert _ok(promote("list")).stdout.splitlines() == [lesson(2, n=3)]

    def test_declined_lesson_returns_once_it_recurs(
        self, promote: Runner, seed: SeedLessons
    ) -> None:
        seed([lesson(1, n=4)])
        _ok(promote("decline", "L-0001"))

        seed([lesson(1, n=5, last="2026-11-02")])

        assert _ok(promote("list")).stdout.splitlines() == [lesson(1, n=5, last="2026-11-02")]

    def test_declining_again_replaces_the_earlier_record(
        self, project: Path, promote: Runner, seed: SeedLessons
    ) -> None:
        seed([lesson(1, n=4)])
        _ok(promote("decline", "L-0001"))
        seed([lesson(1, n=6)])

        _ok(promote("decline", "L-0001"))

        declined = (_memory_dir(project) / ".promote-declined").read_text(encoding="utf-8")
        assert declined == "L-0001 6\n"

    def test_named_ids_are_listed_even_when_declined(
        self, promote: Runner, seed: SeedLessons
    ) -> None:
        seed([lesson(1, n=4)])
        _ok(promote("decline", "L-0001"))

        assert _ok(promote("list", "L-0001")).stdout.splitlines() == [lesson(1, n=4)]

    def test_session_start_hint_leaves_out_declined_lessons(
        self, promote: Runner, hint: HintReader, seed: SeedLessons
    ) -> None:
        seed([lesson(1, n=4), lesson(2, n=3)])
        assert hint() == f"{HINT_START}L-0001, L-0002. At a natural pause, offer" + (
            " /lessons-promote to turn them into project rules."
        )

        _ok(promote("decline", "L-0001"))
        _ok(promote("decline", "L-0002"))

        assert hint() == ""

    def test_missing_lesson_cannot_be_declined(self, promote: Runner, seed: SeedLessons) -> None:
        seed([lesson(1, n=4)])

        _refused(promote("decline", "L-0009"), "L-0009 is not in")


class TestArguments:
    @pytest.mark.parametrize(
        "args",
        [(), ("promote",), ("archive", "L-0001"), ("decline",), ("decline", "L-0001", "x")],
        ids=["nothing", "unknown", "archive_short", "decline_short", "decline_long"],
    )
    def test_bad_usage_is_refused(
        self, promote: Runner, seed: SeedLessons, args: tuple[str, ...]
    ) -> None:
        seed([lesson(1, n=4)])

        _refused(promote(*args), "usage:")
