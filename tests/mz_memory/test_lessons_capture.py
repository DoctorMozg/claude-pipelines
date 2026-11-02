import os
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pytest

from .memory_helpers import (
    LESSON_MAX_CHARS,
    MarkChanged,
    RawTaskWriter,
    TaskWriter,
    curated_lines,
    inbox_lines,
    lessons_file,
    line_field,
    line_ids,
    line_texts,
    memory_dir,
    memory_file,
)

LESSONS_PER_TASK = 10
SEEN_MAX = 2000


class LessonTaskWriter(Protocol):
    def __call__(self, name: str, lessons: list[str], status: str = "complete") -> Path: ...


@pytest.fixture
def write_lessons(write_task: TaskWriter) -> LessonTaskWriter:
    def write(name: str, lessons: list[str], status: str = "complete") -> Path:
        bullets = "".join(f"- {lesson}\n" for lesson in lessons)
        return write_task(name, status, f"\n## Lessons\n\n{bullets}")

    return write


class TestHarvest:
    def test_lesson_lands_in_the_inbox_with_its_metadata(
        self, project: Path, write_lessons: LessonTaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_lessons("t1", ["(review) WHEN a hook emits JSON → use jq — WHY quotes broke it"])

        run_capture()

        assert re.fullmatch(
            r"- \[I-0001\] \d{4}-\d{2}-\d{2} trig=review src=t1 status=complete"
            r" :: WHEN a hook emits JSON → use jq — WHY quotes broke it",
            inbox_lines(project)[0],
        )
        assert curated_lines(project) == []

    @pytest.mark.parametrize(
        "status", ["pending", "running", "blocked", "failed", "aborted_by_user"]
    )
    def test_lessons_are_harvested_from_every_status(
        self,
        project: Path,
        write_lessons: LessonTaskWriter,
        run_capture: Callable[[], None],
        status: str,
    ) -> None:
        write_lessons("t1", ["(failure) WHEN x → y — WHY z"], status=status)

        run_capture()

        assert [line_field(line, "status") for line in inbox_lines(project)] == [status]

    def test_state_without_a_status_line_is_harvested_as_unknown(
        self, project: Path, write_raw_task: RawTaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_raw_task("t1", "schema_version: 2\n\n## Lessons\n\n- keep the marker\n")

        run_capture()

        assert [line_field(line, "status") for line in inbox_lines(project)] == ["unknown"]

    def test_lessons_are_no_longer_copied_into_the_activity_log(
        self, project: Path, write_task: TaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_task(
            "t1", "complete", "\n## Decisions\n\n- use JWT\n\n## Lessons\n\n- pin the jq version\n"
        )

        run_capture()

        memory = memory_file(project).read_text(encoding="utf-8")
        assert "use JWT" in memory
        assert "pin the jq version" not in memory
        assert line_texts(inbox_lines(project)) == ["pin the jq version"]

    def test_untagged_and_unknown_tags_are_kept_as_other(
        self, project: Path, write_lessons: LessonTaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_lessons("t1", ["plain lesson", "(weird) odd tag stays in the text"])

        run_capture()

        inbox = inbox_lines(project)
        assert [line_field(line, "trig") for line in inbox] == ["other", "other"]
        assert "(weird) odd tag stays in the text" in line_texts(inbox)

    def test_only_bullet_lines_are_harvested(
        self, project: Path, write_task: TaskWriter, run_capture: Callable[[], None]
    ) -> None:
        section = "\n## Lessons\n\nprose line\n### sub heading\n* star bullet\n1. numbered bullet\n"
        write_task("t1", "running", section)

        run_capture()

        assert sorted(line_texts(inbox_lines(project))) == ["numbered bullet", "star bullet"]

    def test_section_ends_at_the_next_level_two_heading(
        self, project: Path, write_task: TaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_task("t1", "complete", "\n## Lessons\n\n- a lesson\n\n## Notes\n\n- a note\n")

        run_capture()

        assert line_texts(inbox_lines(project)) == ["a lesson"]

    def test_a_repeated_heading_extends_the_section_only_right_after_it(
        self, project: Path, write_task: TaskWriter, run_capture: Callable[[], None]
    ) -> None:
        sections = "\n## Lessons\n- one\n## Lessons\n- two\n## Notes\n## Lessons\n- three\n"
        write_task("t1", "complete", sections)

        run_capture()

        assert sorted(line_texts(inbox_lines(project))) == ["one", "two"]

    def test_a_section_open_at_the_end_of_one_task_stops_there(
        self,
        project: Path,
        write_task: TaskWriter,
        write_raw_task: RawTaskWriter,
        run_capture: Callable[[], None],
    ) -> None:
        write_task("t1", "complete", "\n## Lessons\n- the last line of t1")
        write_raw_task("t2", "- a bullet before any heading\nStatus: running\n")

        run_capture()

        assert line_texts(inbox_lines(project)) == ["the last line of t1"]

    def test_at_most_ten_lessons_are_taken_per_task(
        self, project: Path, write_lessons: LessonTaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_lessons("t1", [f"lesson number {index}" for index in range(15)])

        run_capture()

        texts = line_texts(inbox_lines(project))
        assert len(texts) == LESSONS_PER_TASK
        assert "lesson number 9" in texts
        assert "lesson number 10" not in texts

    @pytest.mark.parametrize("heading", ["## Lessons learned", "### Lessons", "## lessons"])
    def test_inexact_headings_are_skipped(
        self,
        project: Path,
        write_task: TaskWriter,
        run_capture: Callable[[], None],
        heading: str,
    ) -> None:
        write_task("t1", "complete", f"\n{heading}\n\n- a lesson\n")

        run_capture()

        assert not lessons_file(project).exists()

    def test_tasks_without_lessons_create_no_lessons_file(
        self, project: Path, write_task: TaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_task("t1", "complete", "\n## Decisions\n\n- use JWT\n")

        run_capture()

        assert not lessons_file(project).exists()


class TestDedup:
    def test_unchanged_state_is_not_harvested_twice(
        self, project: Path, write_lessons: LessonTaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_lessons("t1", ["a lesson"])

        run_capture()
        run_capture()

        assert line_texts(inbox_lines(project)) == ["a lesson"]

    def test_edited_state_adds_only_its_new_lessons(
        self,
        project: Path,
        write_lessons: LessonTaskWriter,
        run_capture: Callable[[], None],
        mark_changed_since_capture: MarkChanged,
    ) -> None:
        write_lessons("t1", ["first lesson"])
        run_capture()
        mark_changed_since_capture(write_lessons("t1", ["first lesson", "second lesson"]))

        run_capture()

        assert line_texts(inbox_lines(project)) == ["second lesson", "first lesson"]

    def test_case_and_punctuation_edits_are_not_a_new_lesson(
        self,
        project: Path,
        write_lessons: LessonTaskWriter,
        run_capture: Callable[[], None],
        mark_changed_since_capture: MarkChanged,
    ) -> None:
        write_lessons("t1", ["WHEN a hook emits JSON, use jq"])
        run_capture()
        mark_changed_since_capture(write_lessons("t1", ["when a hook emits json — use jq!"]))

        run_capture()

        assert len(inbox_lines(project)) == 1

    def test_same_lesson_from_two_tasks_is_kept_as_a_recurrence(
        self, project: Path, write_lessons: LessonTaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_lessons("t1", ["pin the jq version"])
        write_lessons("t2", ["pin the jq version"])

        run_capture()

        assert sorted(line_field(line, "src") for line in inbox_lines(project)) == ["t1", "t2"]

    def test_non_ascii_lessons_are_told_apart(
        self, project: Path, write_lessons: LessonTaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_lessons("t1", ["не трогать маркер до записи", "проверять статус задачи"])

        run_capture()

        assert len(inbox_lines(project)) == 2

    def test_seen_list_is_capped(
        self, project: Path, write_lessons: LessonTaskWriter, run_capture: Callable[[], None]
    ) -> None:
        seen = memory_dir(project) / ".lessons-seen"
        seen.parent.mkdir(parents=True)
        seen.write_text("".join(f"old\tkey {index}\n" for index in range(SEEN_MAX + 100)))
        write_lessons("t1", ["a fresh lesson"])

        run_capture()

        lines = seen.read_text(encoding="utf-8").splitlines()
        assert len(lines) == SEEN_MAX
        assert lines[-1] == "t1\ta fresh lesson"


class TestIdsAndOrder:
    def test_newest_lessons_come_first(
        self,
        project: Path,
        write_lessons: LessonTaskWriter,
        run_capture: Callable[[], None],
        mark_changed_since_capture: MarkChanged,
    ) -> None:
        write_lessons("t1", ["older lesson"])
        run_capture()
        mark_changed_since_capture(write_lessons("t2", ["newer lesson"]))

        run_capture()

        inbox = inbox_lines(project)
        assert line_ids(inbox) == ["[I-0002]", "[I-0001]"]
        assert line_texts(inbox) == ["newer lesson", "older lesson"]

    def test_ids_continue_past_archived_lessons(
        self, project: Path, write_lessons: LessonTaskWriter, run_capture: Callable[[], None]
    ) -> None:
        archive = memory_dir(project) / "lessons.archive.md"
        archive.parent.mkdir(parents=True)
        archive.write_text("- [I-0041] 2026-10-01 trig=other src=t0 status=complete :: gone\n")
        write_lessons("t1", ["a lesson"])

        run_capture()

        assert line_ids(inbox_lines(project)) == ["[I-0042]"]


class TestContent:
    def test_private_spans_never_reach_the_inbox_or_seen_list(
        self, project: Path, write_lessons: LessonTaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_lessons("t1", ["mail <private>jane@acme.test</private> before deploys"])

        run_capture()

        assert line_texts(inbox_lines(project)) == ["mail before deploys"]
        seen = (memory_dir(project) / ".lessons-seen").read_text(encoding="utf-8")
        assert "jane" not in seen

    def test_overlong_lesson_is_cut_at_a_word_boundary(
        self, project: Path, write_lessons: LessonTaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_lessons("t1", ["word " * 200])

        run_capture()

        text = line_texts(inbox_lines(project))[0]
        assert text.endswith("word...")
        assert len(text) <= LESSON_MAX_CHARS + len("...")

    def test_src_carries_the_commit_inside_a_git_repo(
        self, project: Path, write_lessons: LessonTaskWriter, run_capture: Callable[[], None]
    ) -> None:
        git_env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        }
        for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "seed"]):
            subprocess.run(["git", *args], cwd=project, env=git_env, check=True)
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        write_lessons("t1", ["a lesson"])

        run_capture()

        assert line_field(inbox_lines(project)[0], "src") == f"t1@{sha}"


class TestRecovery:
    def test_file_that_lost_a_marker_is_rebuilt_around_its_ids(
        self, project: Path, write_lessons: LessonTaskWriter, run_capture: Callable[[], None]
    ) -> None:
        lessons = lessons_file(project)
        lessons.parent.mkdir(parents=True)
        curated = "- [L-0007] n=2 last=2026-10-01 trig=review src=t0 tags=x :: keep me"
        queued = "- [I-0003] 2026-10-01 trig=other src=t0 status=complete :: still queued"
        lessons.write_text(f"hand-edited junk\n{curated}\n{queued}\n", encoding="utf-8")
        write_lessons("t1", ["a new lesson"])

        run_capture()

        assert curated_lines(project) == [curated]
        assert line_ids(inbox_lines(project)) == ["[I-0004]", "[I-0003]"]
        assert "hand-edited junk" in (lessons.parent / "lessons.md.bak").read_text(encoding="utf-8")
