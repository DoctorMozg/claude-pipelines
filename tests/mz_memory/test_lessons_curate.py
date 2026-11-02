import json
import os
import shlex
import subprocess
import time
from collections.abc import Callable, Mapping
from datetime import date, timedelta
from pathlib import Path

import pytest

from .memory_helpers import (
    BASH,
    CALLER_VARS,
    INBOX_START,
    LESSON_MAX_CHARS,
    SCRIPTS,
    FakeCurator,
    SeedLessons,
    TaskWriter,
    curated_lines,
    inbox_lines,
    lessons_file,
    line_field,
    line_ids,
    line_texts,
    memory_dir,
    op,
)

CURATE_SCRIPT = SCRIPTS / "lessons-curate.sh"

# Header, section headings, blank lines and the four markers of an empty lessons.md.
FIXED_LINES = 13
MAX_LINES = 500
EVICT_TO = 480
MAX_OPS = 30
MAX_REMOVED = 10
OPS_LOG_MAX = 1000
HOOK_SCRIPTS = (
    "memory-capture.sh",
    "memory-inject.sh",
    "memory-prompt-inject.sh",
    "journal-capture.sh",
)
HOOK_INPUT = json.dumps(
    {
        "session_id": "s1",
        # "build" matches the logged task name, so prompt-inject has something to print.
        "prompt": "what did the build decide",
        "tool_name": "AskUserQuestion",
        "tool_input": {"questions": []},
        "tool_response": {},
    }
)

type RunCurate = Callable[..., None]


def lesson(
    number: int, n: int = 1, last: str = "2026-10-01", tags: str = "git", text: str = ""
) -> str:
    body = text or f"WHEN case {number} happens → handle it — WHY reason {number}"
    return (
        f"- [L-{number:04d}] n={n} last={last} trig=review src=t{number}@abc tags={tags} :: {body}"
    )


def item(number: int, trig: str = "failure", text: str = "") -> str:
    body = text or f"WHEN inbox case {number} → do it — WHY cause {number}"
    return f"- [I-{number:04d}] 2026-11-01 trig={trig} src=task{number}@def status=failed :: {body}"


def _today() -> str:
    return date.today().isoformat()


def _day(offset: int) -> str:
    return (date(2026, 1, 1) + timedelta(days=offset)).isoformat()


def _archive(project: Path) -> list[str]:
    archive = memory_dir(project) / "lessons.archive.md"
    return archive.read_text(encoding="utf-8").splitlines() if archive.exists() else []


def _ops(project: Path) -> list[dict[str, object]]:
    log = memory_dir(project) / "lessons.ops.jsonl"
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def _mark(project: Path) -> str:
    return (memory_dir(project) / ".lessons-curated").read_text(encoding="utf-8").strip()


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _snapshot(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _wait_for(condition: Callable[[], bool], timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("the background curator did not finish in time")
        time.sleep(0.05)


def _needs_curation(store: Path) -> bool:
    script = (
        'source "$1/lib/common.sh"; source "$1/lib/lessons.sh"; source "$1/lib/curator.sh"; '
        'lessons_need_curation "$2"'
    )
    env = {key: value for key, value in os.environ.items() if key not in CALLER_VARS}
    result = subprocess.run(
        [BASH, "-c", script, "needs-curation", str(SCRIPTS), str(store)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    return result.returncode == 0


@pytest.fixture
def run_curate(project: Path, bin_dir: Path) -> RunCurate:
    env = {key: value for key, value in os.environ.items() if key not in CALLER_VARS}
    env.update({"PATH": str(bin_dir), "MZ_MEMORY_ROOT": str(project)})

    def run(extra: Mapping[str, str] | None = None) -> None:
        result = subprocess.run(
            [BASH, str(CURATE_SCRIPT)],
            env={**env, **(extra or {})},
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        # A jq error in the apply step would otherwise pass as an ordinary failed run.
        assert result.stderr == ""

    return run


class TestOperations:
    def test_add_turns_inbox_items_into_one_lesson(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([], [item(2, trig="review"), item(1)])
        curator.respond(
            op("ADD", inbox=["I-0002", "I-0001"], text="WHEN x → y — WHY z", tags=["git"])
        )

        run_curate()

        expected = (
            f"- [L-0001] n=2 last={_today()} trig=failure src=task1@def tags=git"
            " :: WHEN x → y — WHY z"
        )
        assert curated_lines(project) == [expected]
        assert inbox_lines(project) == []
        assert [line.split(": ", 1)[0] for line in _archive(project)] == [
            f"{_today()} into=L-0001"
        ] * 2

    def test_merge_counts_the_recurrence_and_keeps_the_wording(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        original = lesson(1, n=2, last="2026-10-01")
        seed_lessons([original], [item(1)])
        curator.respond(op("MERGE", inbox=["I-0001"], lessons=["L-0001"]))

        run_curate()

        assert curated_lines(project) == [
            original.replace("n=2 last=2026-10-01", f"n=3 last={_today()}")
        ]
        assert inbox_lines(project) == []

    @pytest.mark.parametrize(
        ("rewrite", "replaced"),
        [
            ("WHEN case one happens → handle it at once — WHY reason one", True),
            ("WHEN case one → fix", False),
        ],
        ids=["keeps-most-of-the-text", "much-shorter"],
    )
    def test_merge_takes_a_rewrite_only_when_it_keeps_most_of_the_text(
        self,
        project: Path,
        seed_lessons: SeedLessons,
        curator: FakeCurator,
        run_curate: RunCurate,
        rewrite: str,
        replaced: bool,
    ) -> None:
        original = "WHEN case one happens → handle it — WHY reason one"
        seed_lessons([lesson(1, text=original)], [item(1)])
        curator.respond(op("MERGE", inbox=["I-0001"], lessons=["L-0001"], text=rewrite))

        run_curate()

        assert line_texts(curated_lines(project)) == [rewrite if replaced else original]

    def test_supersede_archives_the_old_lesson_and_keeps_its_tags(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        old = lesson(1, n=4, tags="hooks")
        seed_lessons([old], [item(1)])
        curator.respond(
            op(
                "SUPERSEDE",
                inbox=["I-0001"],
                lessons=["L-0001"],
                text="WHEN new → better — WHY changed",
            )
        )

        run_curate()

        expected = (
            f"- [L-0002] n=1 last={_today()} trig=failure src=task1@def tags=hooks"
            " :: WHEN new → better — WHY changed"
        )
        assert curated_lines(project) == [expected]
        assert f"{_today()} superseded_by=L-0002: {old}" in _archive(project)

    def test_drop_archives_the_item_with_its_reason(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        dropped = item(1)
        seed_lessons([], [item(2), dropped])
        curator.respond(op("DROP", inbox=["I-0001"], reason="one-off typo"))

        run_curate()

        assert inbox_lines(project) == [item(2)]
        assert _archive(project) == [f"{_today()} dropped (one-off typo): {dropped}"]

    def test_combine_sums_counts_and_keeps_the_latest_date_and_all_tags(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        first = lesson(1, n=1, last="2026-10-01", tags="git")
        second = lesson(2, n=2, last="2026-10-05", tags="git,safety")
        seed_lessons([first, second, lesson(3, n=5)], [])
        curator.respond(
            op(
                "COMBINE",
                lessons=["L-0001", "L-0002"],
                text="WHEN rebasing → stash — WHY lost work",
            )
        )

        run_curate()

        combined = (
            "- [L-0004] n=3 last=2026-10-05 trig=review src=t1@abc tags=git,safety"
            " :: WHEN rebasing → stash — WHY lost work"
        )
        assert curated_lines(project) == [lesson(3, n=5), combined]
        assert [line.split(": ", 1)[1] for line in _archive(project)] == [first, second]

    def test_curated_lessons_are_ordered_by_count_then_recency(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons(
            [
                lesson(1, n=1, last="2026-10-05"),
                lesson(2, n=4, last="2026-10-01"),
                lesson(3, n=1, last="2026-10-09"),
                lesson(4, n=1, last="2026-10-09"),
            ],
            [],
        )

        run_curate()

        assert line_ids(curated_lines(project)) == ["[L-0002]", "[L-0003]", "[L-0004]", "[L-0001]"]

    def test_unreadable_lines_and_untouched_items_keep_their_place(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons(
            [lesson(1), "a hand-written note"], [item(3), "stray inbox text", item(2), item(1)]
        )
        curator.respond(op("DROP", inbox=["I-0002"], reason="noise"))

        run_curate()

        assert curated_lines(project) == [lesson(1), "a hand-written note"]
        assert inbox_lines(project) == [item(3), "stray inbox text", item(1)]

    def test_model_text_and_tags_are_cleaned_before_they_are_written(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([], [item(1)])
        text = "WHEN\tsomething\nbreaks → " + "word " * 120
        curator.respond(op("ADD", inbox=["I-0001"], text=text, tags=["Hooks", "JQ!", "hooks", ""]))

        run_curate()

        [line] = curated_lines(project)
        [written] = line_texts([line])
        assert line_field(line, "tags") == "hooks,jq"
        assert written.startswith("WHEN something breaks → word word")
        assert written.endswith(" word...")
        assert len(written) <= LESSON_MAX_CHARS + len("...")


class TestGuards:
    def test_unknown_ids_are_rejected_and_logged(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([lesson(1)], [item(1)])
        curator.respond(
            op("ADD", inbox=["I-0099"], text="WHEN a → b — WHY c"),
            op("MERGE", inbox=["I-0001"], lessons=["L-0042"]),
        )

        run_curate()

        assert inbox_lines(project) == [item(1)]
        assert [(entry["event"], entry["why"]) for entry in _ops(project)] == [
            ("rejected", "unknown or already covered inbox id"),
            ("rejected", "unknown or already used lesson id"),
        ]

    def test_each_inbox_item_serves_one_operation(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([], [item(1)])
        curator.respond(
            op("ADD", inbox=["I-0001"], text="WHEN a → b — WHY c"),
            op("DROP", inbox=["I-0001"], reason="duplicate"),
        )

        run_curate()

        assert line_ids(curated_lines(project)) == ["[L-0001]"]
        assert [entry["event"] for entry in _ops(project)] == ["applied", "rejected"]
        assert not any("dropped" in line for line in _archive(project))

    def test_each_lesson_serves_one_operation(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([lesson(1)], [item(2), item(1)])
        curator.respond(
            op("MERGE", inbox=["I-0001"], lessons=["L-0001"]),
            op("MERGE", inbox=["I-0002"], lessons=["L-0001"]),
        )

        run_curate()

        assert line_field(curated_lines(project)[0], "n") == "2"
        assert inbox_lines(project) == [item(2)]

    def test_a_lesson_made_in_this_run_is_not_touched_again(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([], [item(2), item(1)])
        curator.respond(
            op("ADD", inbox=["I-0001"], text="WHEN a → b — WHY c"),
            op("MERGE", inbox=["I-0002"], lessons=["L-0001"]),
        )

        run_curate()

        assert line_field(curated_lines(project)[0], "n") == "1"
        assert inbox_lines(project) == [item(2)]

    @pytest.mark.parametrize(
        "bad",
        [
            op("ADD", inbox=["I-0001"]),
            op("MERGE", inbox=["I-0001"], lessons=["L-0001", "L-0002"]),
            op("COMBINE", lessons=["L-0001"], text="WHEN a → b — WHY c"),
            op("DROP", inbox=["I-0001"], lessons=["L-0001"]),
            op("RENAME", inbox=["I-0001"], text="WHEN a → b — WHY c"),
        ],
        ids=["add-without-text", "merge-into-two", "combine-one", "drop-a-lesson", "unknown-op"],
    )
    def test_malformed_operations_change_nothing(
        self,
        project: Path,
        seed_lessons: SeedLessons,
        curator: FakeCurator,
        run_curate: RunCurate,
        bad: dict[str, object],
    ) -> None:
        before = seed_lessons([lesson(1), lesson(2)], [item(1)]).read_text(encoding="utf-8")
        curator.respond(bad)

        run_curate()

        assert lessons_file(project).read_text(encoding="utf-8") == before
        assert _ops(project)[-1]["why"] == "malformed, or over the removal cap"

    def test_operations_past_the_cap_are_ignored(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([], [item(number) for number in range(MAX_OPS + 1, 0, -1)])
        curator.respond(
            *(
                op("DROP", inbox=[f"I-{number:04d}"], reason="noise")
                for number in range(1, MAX_OPS + 2)
            )
        )

        run_curate()

        assert inbox_lines(project) == [item(MAX_OPS + 1)]
        assert _ops(project)[0] == {
            "date": _today(),
            "event": "rejected",
            "why": f"ignored 1 operation(s) past the cap of {MAX_OPS}",
        }

    def test_removals_past_the_cap_are_rejected(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        count = MAX_REMOVED + 1
        seed_lessons(
            [lesson(number) for number in range(1, count + 1)],
            [item(number) for number in range(count, 0, -1)],
        )
        curator.respond(
            *(
                op(
                    "SUPERSEDE",
                    inbox=[f"I-{number:04d}"],
                    lessons=[f"L-{number:04d}"],
                    text=f"WHEN fixed case {number} → act — WHY corrected",
                )
                for number in range(1, count + 1)
            )
        )

        run_curate()

        assert [entry["event"] for entry in _ops(project)] == ["applied"] * MAX_REMOVED + [
            "rejected"
        ]
        assert inbox_lines(project) == [item(count)]

    def test_a_combine_past_the_removal_cap_is_rejected_even_under_the_shrink_limit(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([lesson(number) for number in range(1, 61)], [])
        ids = [f"L-{number:04d}" for number in range(1, MAX_REMOVED + 2)]
        curator.respond(op("COMBINE", lessons=ids, text="WHEN all → one — WHY duplicates"))

        run_curate()

        assert len(curated_lines(project)) == 60
        assert _ops(project)[-1]["event"] == "rejected"

    def test_a_large_shrink_aborts_the_whole_run(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        store = seed_lessons([lesson(number) for number in range(1, 6)], [item(1)])
        before = store.read_text(encoding="utf-8")
        curator.respond(
            op("ADD", inbox=["I-0001"], text="WHEN a → b — WHY c"),
            op(
                "COMBINE",
                lessons=[f"L-{number:04d}" for number in range(1, 6)],
                text="WHEN all → one — WHY dup",
            ),
        )

        run_curate()

        assert store.read_text(encoding="utf-8") == before
        assert _ops(project) == [
            {
                "date": _today(),
                "event": "aborted",
                "why": "curated lessons would shrink from 5 to 2",
            }
        ]
        assert _archive(project) == []
        assert not (memory_dir(project) / "lessons.md.bak").exists()


class TestRecords:
    def test_items_added_during_the_call_survive_and_wait_for_the_next_run(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        store = seed_lessons([], [item(2), item(1)])
        late = item(9, text="WHEN late → keep — WHY arrived mid-run")
        tmp = f"{store}.tmp"
        curator.during_call(
            f"awk -v start={shlex.quote(INBOX_START)} -v line={shlex.quote(late)} "
            f"'{{ print }} $0 == start {{ print line }}' {shlex.quote(str(store))} "
            f">{shlex.quote(tmp)} && mv {shlex.quote(tmp)} {shlex.quote(str(store))}\n"
        )
        curator.respond(op("ADD", inbox=["I-0001"], text="WHEN a → b — WHY c"))

        run_curate()

        assert inbox_lines(project) == [late, item(2)]
        assert _mark(project) == "2"

    def test_new_ids_continue_past_archived_lessons(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([], [item(1)])
        (memory_dir(project) / "lessons.archive.md").write_text(
            f"2026-10-01 evicted: {lesson(7)}\n", encoding="utf-8"
        )
        curator.respond(op("ADD", inbox=["I-0001"], text="WHEN a → b — WHY c"))

        run_curate()

        assert line_ids(curated_lines(project)) == ["[L-0008]"]

    def test_a_full_file_of_long_lessons_is_still_curated(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        # About 200 KB of regions, past the 128 KiB Linux limit on a single command-line argument.
        long_text = "WHEN a long lesson → keep every detail — WHY " + "detail " * 50
        seed_lessons([lesson(number, text=long_text) for number in range(1, 461)], [item(1)])
        curator.respond(op("DROP", inbox=["I-0001"], reason="noise"))

        run_curate()

        assert inbox_lines(project) == []
        assert len(curated_lines(project)) == 460

    def test_backup_holds_the_file_as_it_was_before_the_rewrite(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        before = seed_lessons([], [item(1)]).read_text(encoding="utf-8")
        curator.respond(op("DROP", inbox=["I-0001"], reason="noise"))

        run_curate()

        assert (memory_dir(project) / "lessons.md.bak").read_text(encoding="utf-8") == before

    def test_ops_log_keeps_the_last_thousand_entries(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([], [item(1)])
        log = memory_dir(project) / "lessons.ops.jsonl"
        log.write_text(
            "".join(f'{{"n": {index}}}\n' for index in range(OPS_LOG_MAX)), encoding="utf-8"
        )
        curator.respond(op("DROP", inbox=["I-0001"], reason="noise"))

        run_curate()

        entries = _ops(project)
        assert len(entries) == OPS_LOG_MAX
        assert entries[0] == {"n": 1}
        assert entries[-1]["event"] == "applied"


FAILED_REPLIES = {
    "error-result": (
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": True,
                "structured_output": {"operations": [op("DROP", inbox=["I-0001"], reason="x")]},
            }
        ),
        0,
    ),
    "over-budget": (
        json.dumps({"type": "result", "subtype": "error_max_budget_usd", "is_error": True}),
        0,
    ),
    "not-json": ("Sorry, I cannot help with that.", 0),
    "empty": ("", 0),
    "no-structured-output": (
        json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "done"}),
        0,
    ),
    "non-zero-exit": (
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "structured_output": {"operations": [op("DROP", inbox=["I-0001"], reason="x")]},
            }
        ),
        1,
    ),
}


class TestFallbacks:
    @pytest.mark.parametrize(
        ("reply", "exit_code"), FAILED_REPLIES.values(), ids=FAILED_REPLIES.keys()
    )
    def test_failed_call_leaves_the_file_and_still_advances_the_mark(
        self,
        project: Path,
        seed_lessons: SeedLessons,
        curator: FakeCurator,
        run_curate: RunCurate,
        reply: str,
        exit_code: int,
    ) -> None:
        store = seed_lessons([lesson(1)], [item(2), item(1)])
        before = store.read_text(encoding="utf-8")
        curator.respond_raw(reply, exit_code)

        run_curate()

        assert store.read_text(encoding="utf-8") == before
        assert _ops(project)[-1]["event"] == "failed"
        assert _mark(project) == "2"

    def test_missing_claude_skips_curation(
        self, project: Path, seed_lessons: SeedLessons, run_curate: RunCurate
    ) -> None:
        store = seed_lessons([lesson(1)], [item(1)])
        before = store.read_text(encoding="utf-8")

        run_curate()

        assert store.read_text(encoding="utf-8") == before
        assert not (memory_dir(project) / "lessons.ops.jsonl").exists()
        assert not (memory_dir(project) / ".lessons-curated").exists()

    def test_missing_jq_skips_the_call(
        self, seed_lessons: SeedLessons, curator: FakeCurator, bin_dir: Path, run_curate: RunCurate
    ) -> None:
        seed_lessons([], [item(1)])
        (bin_dir / "jq").unlink()

        run_curate()

        assert not curator.called

    def test_compression_off_skips_the_call(
        self, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([], [item(1)])

        run_curate({"MZ_MEMORY_COMPRESS": "0"})

        assert not curator.called

    def test_missing_lessons_file_is_left_alone(
        self, project: Path, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        run_curate()

        assert not curator.called
        assert not lessons_file(project).exists()

    def test_a_run_in_progress_is_not_started_twice(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([], [item(1)])
        lock = memory_dir(project) / ".curate.lock"
        lock.mkdir()

        run_curate()

        assert not curator.called
        assert lock.is_dir()

    def test_lock_left_by_a_killed_run_is_cleared(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([], [item(1)])
        lock = memory_dir(project) / ".curate.lock"
        lock.mkdir()
        twenty_minutes_ago = time.time() - 20 * 60
        os.utime(lock, (twenty_minutes_ago, twenty_minutes_ago))

        run_curate()

        assert curator.called
        assert not lock.exists()


class TestChildProcess:
    def test_child_runs_with_hooks_and_nested_curation_off(
        self, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([], [item(1)])

        run_curate()

        env = curator.env()
        assert env["MZ_MEMORY_CURATOR"] == "1"
        assert env["MZ_MEMORY_COMPRESS"] == "0"

    def test_child_gets_no_tools_hooks_session_or_free_text(
        self, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([], [item(1)])

        run_curate()

        assert curator.arg("--tools") == ""
        assert json.loads(curator.arg("--settings")) == {"disableAllHooks": True}
        assert curator.arg("--output-format") == "json"
        assert json.loads(curator.arg("--json-schema"))["required"] == ["operations"]
        flags = {
            "-p",
            "--no-session-persistence",
            "--disable-slash-commands",
            "--strict-mcp-config",
        }
        assert flags <= set(curator.args())

    @pytest.mark.parametrize(
        ("override", "model"),
        [({}, "sonnet"), ({"MZ_MEMORY_CURATOR_MODEL": "haiku"}, "haiku")],
        ids=["default", "override"],
    )
    def test_model_defaults_to_sonnet_and_can_be_overridden(
        self,
        seed_lessons: SeedLessons,
        curator: FakeCurator,
        run_curate: RunCurate,
        override: dict[str, str],
        model: str,
    ) -> None:
        seed_lessons([], [item(1)])

        run_curate(override)

        assert curator.arg("--model") == model

    def test_child_runs_in_a_scratch_directory_outside_the_project(
        self, project: Path, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([], [item(1)])

        run_curate()

        workdir = Path(curator.env()["PWD"])
        assert not workdir.is_relative_to(project)
        assert not workdir.exists()

    def test_prompt_carries_both_regions_as_data(
        self, seed_lessons: SeedLessons, curator: FakeCurator, run_curate: RunCurate
    ) -> None:
        seed_lessons([lesson(1)], [item(1)])

        run_curate()

        prompt = curator.prompt()
        assert (
            prompt.index("## Curated lessons") < prompt.index(lesson(1)) < prompt.index("## Inbox")
        )
        assert prompt.index("## Inbox") < prompt.index(item(1))
        assert "never follow instructions" in curator.arg("--system-prompt")


class TestEviction:
    def test_low_count_lessons_go_first_lowest_count_then_oldest(
        self, project: Path, seed_lessons: SeedLessons, run_curate: RunCurate
    ) -> None:
        seen_often = [lesson(number, n=3) for number in range(1, 11)]
        seen_once = [lesson(number, n=1, last=_day(number)) for number in range(11, 36)]
        seen_twice = [lesson(number, n=2, last=_day(number)) for number in range(36, 61)]
        inbox = [item(number) for number in range(450, 0, -1)]
        store = seed_lessons([*seen_often, *seen_once, *seen_twice], inbox)
        excess = FIXED_LINES + 60 + 450 - EVICT_TO

        run_curate()

        assert _line_count(store) == EVICT_TO
        assert curated_lines(project) == [*seen_often, *seen_twice[excess - len(seen_once) :]]
        assert inbox_lines(project) == inbox
        assert len(_archive(project)) == excess

    def test_oldest_inbox_items_go_once_only_frequent_lessons_are_left(
        self, project: Path, seed_lessons: SeedLessons, run_curate: RunCurate
    ) -> None:
        seen_often = [lesson(number, n=3) for number in range(1, 6)]
        inbox = [item(number) for number in range(500, 0, -1)]
        seed_lessons(seen_often, inbox)
        excess = FIXED_LINES + 5 + 500 - EVICT_TO

        run_curate()

        assert curated_lines(project) == seen_often
        assert inbox_lines(project) == inbox[:-excess]
        # The archive lists victims in eviction order, oldest first.
        assert _archive(project) == [
            f"{_today()} evicted: {line}" for line in reversed(inbox[-excess:])
        ]

    def test_file_at_the_cap_is_left_alone(
        self, project: Path, seed_lessons: SeedLessons, run_curate: RunCurate
    ) -> None:
        store = seed_lessons([], [item(number) for number in range(MAX_LINES - FIXED_LINES, 0, -1)])
        before = store.read_text(encoding="utf-8")

        run_curate()

        assert store.read_text(encoding="utf-8") == before
        assert _archive(project) == []

    def test_session_end_evicts_without_the_model(
        self, project: Path, seed_lessons: SeedLessons, run_capture: Callable[[], None]
    ) -> None:
        store = seed_lessons([], [item(number) for number in range(600, 0, -1)])

        run_capture()

        assert _line_count(store) == EVICT_TO


NEED_CASES = {
    "four-new-items": (range(4, 0, -1), None, 0, False),
    "five-new-items": (range(5, 0, -1), None, 0, True),
    "four-past-the-mark": (range(7, 0, -1), "3", 0, False),
    "five-past-the-mark": (range(7, 0, -1), "2", 0, True),
    "unreadable-mark-counts-from-zero": (range(5, 0, -1), "garbage", 0, True),
    "near-the-cap-with-one-new-item": (range(1, 0, -1), None, 440, True),
    "near-the-cap-with-nothing-new": (range(1, 0, -1), "1", 440, False),
}


class TestTrigger:
    @pytest.mark.parametrize(
        ("inbox_numbers", "mark", "curated_count", "expected"),
        NEED_CASES.values(),
        ids=NEED_CASES.keys(),
    )
    def test_curation_waits_for_enough_new_items(
        self,
        project: Path,
        seed_lessons: SeedLessons,
        inbox_numbers: range,
        mark: str | None,
        curated_count: int,
        expected: bool,
    ) -> None:
        store = seed_lessons(
            [lesson(number) for number in range(1, curated_count + 1)],
            [item(number) for number in inbox_numbers],
        )
        if mark is not None:
            (memory_dir(project) / ".lessons-curated").write_text(f"{mark}\n", encoding="utf-8")

        assert _needs_curation(store) is expected

    def test_session_end_starts_the_curator_in_the_background(
        self,
        project: Path,
        seed_lessons: SeedLessons,
        curator: FakeCurator,
        bin_dir: Path,
        capture_env: dict[str, str],
        capture_runner: Callable[[dict[str, str]], None],
    ) -> None:
        seed_lessons([], [item(number) for number in range(5, 0, -1)])
        memory = memory_dir(project)

        capture_runner({**capture_env, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"})

        _wait_for(
            lambda: (memory / ".lessons-curated").exists()
            and not (memory / ".curate.lock").exists()
        )
        assert curator.called
        assert _mark(project) == "5"


class TestHookGuard:
    @pytest.mark.parametrize("script", HOOK_SCRIPTS)
    def test_hooks_do_nothing_inside_the_curator_child(
        self,
        project: Path,
        write_task: TaskWriter,
        run_capture: Callable[[], None],
        mark_changed_since_capture: Callable[[Path], None],
        capture_env: dict[str, str],
        script: str,
    ) -> None:
        write_task("2026_11_01_build_a", "complete", "\n## Lessons\n\n- WHEN a → b — WHY c\n")
        run_capture()
        mark_changed_since_capture(
            write_task("2026_11_02_build_b", "complete", "\n## Lessons\n\n- WHEN d → e — WHY f\n")
        )
        before = _snapshot(project / ".mz")

        result = subprocess.run(
            [BASH, str(SCRIPTS / script)],
            input=HOOK_INPUT,
            env={**capture_env, "MZ_MEMORY_CURATOR": "1", "MZ_MEMORY_COMPRESS": "0"},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout == ""
        assert _snapshot(project / ".mz") == before
