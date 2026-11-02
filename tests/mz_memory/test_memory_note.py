import os
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pytest

from .memory_helpers import (
    BASH,
    LESSON_MAX_CHARS,
    LOG_END,
    LOG_START,
    PIN_END,
    PIN_START,
    SCRIPTS,
    TaskWriter,
    clean_env,
    inbox_lines,
    lessons_file,
    line_field,
    line_ids,
    line_text,
    line_texts,
    memory_dir,
    memory_file,
    ok,
    region,
)

NOTE_SCRIPT = SCRIPTS / "memory-note.sh"
TODAY = "2026-11-02"
TOMORROW = "2026-11-03"

# Text the shell or awk would rewrite if it ever reached them unquoted or through awk -v.
VERBATIM_TEXTS = {
    "backslashes": r"keep C:\new\table and \1 as written",
    "shell": "run `make test` with $HOME/.venv and $(pwd)",
    "awk_replacement": "50% of & matches",
    "quotes": "say \"yes\" and 'no'",
    "unicode": "WHEN a hook emits JSON → use jq — WHY “quotes” broke it",
}


class NoteRunner(Protocol):
    def __call__(self, *args: str, today: str = TODAY) -> subprocess.CompletedProcess[str]: ...


@pytest.fixture
def run_note(project: Path, date_shim: Path) -> NoteRunner:
    """Run memory-note.sh with `date` pinned, so day-keyed dedup is testable."""
    base_env = clean_env()
    base_env["MZ_MEMORY_ROOT"] = str(project)
    base_env["PATH"] = f"{date_shim}{os.pathsep}{os.environ['PATH']}"

    def run(*args: str, today: str = TODAY) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [BASH, str(NOTE_SCRIPT), *args],
            env={**base_env, "MZ_TEST_TODAY": today},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    return run


def _pinned(project: Path) -> list[str]:
    return region(memory_file(project), PIN_START, PIN_END)


def _log(project: Path) -> list[str]:
    return region(memory_file(project), LOG_START, LOG_END)


class TestNote:
    def test_note_is_pinned_under_todays_date(self, project: Path, run_note: NoteRunner) -> None:
        result = ok(run_note("always run migrations forward-compatible"))

        entry = f"- [{TODAY}] always run migrations forward-compatible"
        assert _pinned(project) == [entry]
        assert result.stdout == f"Wrote to pinned section: {entry}\n"

    def test_log_flag_writes_to_the_activity_log(self, project: Path, run_note: NoteRunner) -> None:
        ok(run_note("--log", "ad-hoc activity entry"))

        assert _log(project) == [f"- [{TODAY}] ad-hoc activity entry"]
        assert _pinned(project) == []

    @pytest.mark.parametrize("text", VERBATIM_TEXTS.values(), ids=VERBATIM_TEXTS.keys())
    def test_text_reaches_the_file_verbatim(
        self, project: Path, run_note: NoteRunner, text: str
    ) -> None:
        ok(run_note(text))

        assert _pinned(project) == [f"- [{TODAY}] {text}"]

    def test_identical_note_on_the_same_day_is_skipped(
        self, project: Path, run_note: NoteRunner
    ) -> None:
        ok(run_note("pin me"))
        result = ok(run_note("pin me"))

        assert _pinned(project) == [f"- [{TODAY}] pin me"]
        assert "already present" in result.stderr
        assert result.stdout == ""

    def test_same_note_on_another_day_is_written_again(
        self, project: Path, run_note: NoteRunner
    ) -> None:
        ok(run_note("pin me"))
        ok(run_note("pin me", today=TOMORROW))

        assert _pinned(project) == [f"- [{TOMORROW}] pin me", f"- [{TODAY}] pin me"]

    def test_note_contained_in_an_earlier_one_is_still_written(
        self, project: Path, run_note: NoteRunner
    ) -> None:
        ok(run_note("use the v2 endpoint for uploads"))
        ok(run_note("use the v2 endpoint"))

        assert _pinned(project) == [
            f"- [{TODAY}] use the v2 endpoint",
            f"- [{TODAY}] use the v2 endpoint for uploads",
        ]

    def test_multiline_note_becomes_one_line(self, project: Path, run_note: NoteRunner) -> None:
        ok(run_note("first line\nsecond line"))

        assert _pinned(project) == [f"- [{TODAY}] first line second line"]

    def test_private_regions_are_stripped(self, project: Path, run_note: NoteRunner) -> None:
        ok(run_note("the key is <private>abc123</private> in the vault"))

        assert _pinned(project) == [f"- [{TODAY}] the key is in the vault"]


class TestLesson:
    def test_lesson_lands_in_the_inbox_as_a_correction(
        self, project: Path, run_note: NoteRunner
    ) -> None:
        result = ok(run_note("--lesson", "WHEN tests run → use .venv/bin/pytest — WHY no uv"))

        [line] = inbox_lines(project)
        assert re.match(r"^- \[I-0001\] 2026-11-02 ", line)
        assert line_field(line, "trig") == "correction"
        assert line_field(line, "src") == "2026_11_02_memory-note"
        assert line_field(line, "status") == "noted"
        assert line_text(line) == "WHEN tests run → use .venv/bin/pytest — WHY no uv"
        assert result.stdout == f"Wrote to lessons inbox: {line}\n"
        assert not memory_file(project).exists()

    @pytest.mark.parametrize("trigger", ["review", "failure", "change", "correction"])
    def test_leading_tag_sets_the_trigger(
        self, project: Path, run_note: NoteRunner, trigger: str
    ) -> None:
        ok(run_note("--lesson", f"({trigger}) WHEN x → y — WHY z"))

        [line] = inbox_lines(project)
        assert line_field(line, "trig") == trigger
        assert line_text(line) == "WHEN x → y — WHY z"

    def test_unknown_tag_stays_in_the_text(self, project: Path, run_note: NoteRunner) -> None:
        ok(run_note("--lesson", "(note) WHEN x → y — WHY z"))

        [line] = inbox_lines(project)
        assert line_field(line, "trig") == "correction"
        assert line_text(line) == "(note) WHEN x → y — WHY z"

    def test_src_names_the_head_commit(self, project: Path, run_note: NoteRunner) -> None:
        git = ["git", "-C", str(project), "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        sha = subprocess.run(
            [*git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()

        ok(run_note("--lesson", "WHEN x → y — WHY z"))

        [line] = inbox_lines(project)
        assert line_field(line, "src") == f"2026_11_02_memory-note@{sha}"

    @pytest.mark.parametrize("text", VERBATIM_TEXTS.values(), ids=VERBATIM_TEXTS.keys())
    def test_text_reaches_the_inbox_verbatim(
        self, project: Path, run_note: NoteRunner, text: str
    ) -> None:
        ok(run_note("--lesson", text))

        assert line_texts(inbox_lines(project)) == [text]

    @pytest.mark.parametrize(
        "again",
        ["WHEN x → y — WHY z", "when x: y, why z!"],
        ids=["identical", "case_and_punctuation"],
    )
    def test_same_lesson_twice_a_day_is_saved_once(
        self, project: Path, run_note: NoteRunner, again: str
    ) -> None:
        ok(run_note("--lesson", "WHEN x → y — WHY z"))
        result = ok(run_note("--lesson", again))

        assert len(inbox_lines(project)) == 1
        assert "already saved today" in result.stderr
        assert result.stdout == ""

    def test_same_lesson_on_another_day_is_a_recurrence(
        self, project: Path, run_note: NoteRunner
    ) -> None:
        ok(run_note("--lesson", "WHEN x → y — WHY z"))
        ok(run_note("--lesson", "WHEN x → y — WHY z", today=TOMORROW))

        assert [line_field(line, "src") for line in inbox_lines(project)] == [
            "2026_11_03_memory-note",
            "2026_11_02_memory-note",
        ]

    def test_lesson_also_harvested_from_a_task_counts_twice(
        self,
        project: Path,
        run_note: NoteRunner,
        write_task: TaskWriter,
        run_capture: Callable[[], None],
    ) -> None:
        write_task("2026_11_01_debug_x", "failed", "\n## Lessons\n\n- WHEN x → y — WHY z\n")
        run_capture()

        ok(run_note("--lesson", "WHEN x → y — WHY z"))

        assert line_texts(inbox_lines(project)) == ["WHEN x → y — WHY z"] * 2

    def test_new_lessons_go_on_top_with_the_next_id(
        self, project: Path, run_note: NoteRunner
    ) -> None:
        ok(run_note("--lesson", "WHEN a → b — WHY c"))
        ok(run_note("--lesson", "WHEN d → e — WHY f"))

        assert line_ids(inbox_lines(project)) == ["[I-0002]", "[I-0001]"]

    def test_lesson_at_the_cap_is_kept_whole(self, project: Path, run_note: NoteRunner) -> None:
        text = "a" * LESSON_MAX_CHARS

        ok(run_note("--lesson", text))

        assert line_texts(inbox_lines(project)) == [text]

    def test_lesson_over_the_cap_is_refused(self, project: Path, run_note: NoteRunner) -> None:
        result = run_note("--lesson", "a" * (LESSON_MAX_CHARS + 1))

        assert result.returncode == 2
        assert f"over {LESSON_MAX_CHARS} characters" in result.stderr
        assert not lessons_file(project).exists()

    def test_multiline_lesson_is_one_inbox_line(self, project: Path, run_note: NoteRunner) -> None:
        ok(run_note("--lesson", "WHEN x →\ny — WHY z"))

        assert line_texts(inbox_lines(project)) == ["WHEN x → y — WHY z"]

    def test_fully_private_lesson_is_refused(self, project: Path, run_note: NoteRunner) -> None:
        result = run_note("--lesson", "<private>token abc</private>")

        assert result.returncode == 2
        assert "<private>" in result.stderr
        assert not lessons_file(project).exists()

    @pytest.mark.skipif(os.geteuid() == 0, reason="root writes whatever the mode")
    def test_failed_write_is_reported_and_retried(
        self, project: Path, run_note: NoteRunner
    ) -> None:
        ok(run_note("--lesson", "WHEN a → b — WHY c"))
        directory = memory_dir(project)
        directory.chmod(0o555)
        try:
            failed = run_note("--lesson", "WHEN d → e — WHY f")
        finally:
            directory.chmod(0o755)

        assert failed.returncode != 0
        assert failed.stdout == ""
        assert "already saved" not in failed.stderr
        ok(run_note("--lesson", "WHEN d → e — WHY f"))
        assert line_texts(inbox_lines(project)) == [
            "WHEN d → e — WHY f",
            "WHEN a → b — WHY c",
        ]


class TestArguments:
    @pytest.mark.parametrize(
        "args",
        [(), ("--log",), ("--lesson",), ("--lesson", " \n\t ")],
        ids=["nothing", "log_only", "lesson_only", "blank_lesson"],
    )
    def test_missing_body_is_refused(
        self, project: Path, run_note: NoteRunner, args: tuple[str, ...]
    ) -> None:
        result = run_note(*args)

        assert result.returncode == 2
        assert "missing note body" in result.stderr
        assert not memory_dir(project).exists()

    @pytest.mark.parametrize("flags", [("--log", "--lesson"), ("--lesson", "--log")])
    def test_log_and_lesson_together_are_refused(
        self, project: Path, run_note: NoteRunner, flags: tuple[str, str]
    ) -> None:
        result = run_note(*flags, "WHEN x → y — WHY z")

        assert result.returncode == 2
        assert "not both" in result.stderr
        assert not memory_dir(project).exists()
