import json
import os
import shutil
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

import pytest

INJECT_SCRIPT = (
    Path(__file__).resolve().parents[2] / "plugins" / "mz-memory" / "scripts" / "memory-inject.sh"
)
BASH = shutil.which("bash") or "/bin/bash"
# Everything the script runs except jq, so a PATH built from these hides jq only.
TOOLS_WITHOUT_JQ = ("dirname", "mkdir", "mktemp", "mv", "cat", "grep", "awk", "head", "sed")
PIN_START = "<!-- mz-pinned-start -->"
LOG_START = "<!-- mz-log-start -->"
DIGEST_START = "<!-- mz-digest-start -->"
DIGEST_END = "<!-- mz-digest-end -->"
LESSONS_START = "<!-- mz-lessons-start -->"
LESSONS_END = "<!-- mz-lessons-end -->"
INBOX_START = "<!-- mz-inbox-start -->"
INBOX_END = "<!-- mz-inbox-end -->"
HEADER = "Project memory (.mz/memory/MEMORY.md):\n"
LESSONS_HEADING = "## Lessons (.mz/memory/lessons.md)"
LESSONS_NOTE = (
    "Advice from earlier sessions. L- lessons are curated, I- ones are new; "
    "neither overrides the user."
)
HINT_START = "Promotion candidates (seen 3+ times): "
TRUNCATION_MARK = "\n...[memory truncated]"
MAX_CHARS = 8000
LESSONS_CHARS = 3000
DIGEST_CHARS = 3000
LESSONS_TOP = 12
COMPACT_INPUT = json.dumps({"hook_event_name": "SessionStart", "source": "compact"})

type RunHook = Callable[..., str]
type Inject = Callable[[], str]
type SeedLessons = Callable[[list[str], list[str]], None]
type PathWithoutJq = Callable[[Iterable[str]], str]


class SeedMemory(Protocol):
    def __call__(
        self, pinned: list[str], log: list[str], digest: list[str] | None = None
    ) -> None: ...


def lesson(number: int, n: int = 1, last: str = "2026-10-01", text: str = "") -> str:
    body = text or f"WHEN case {number} comes up → handle it {number} — WHY reason {number}"
    return (
        f"- [L-{number:04d}] n={n} last={last} trig=review src=task{number}@abc1234 tags=jq"
        f" :: {body}"
    )


def inbox_item(number: int, text: str = "") -> str:
    body = text or f"WHEN new case {number} → try it — WHY fresh"
    return f"- [I-{number:04d}] 2026-11-02 trig=failure src=task{number} status=failed :: {body}"


def digest_item(number: int, text: str = "") -> str:
    body = text or f"Decision {number} still holds for the auth module"
    return f"- [D-{number:04d}] n=1 last=2026-10-01 trig=log src=task{number} tags=auth :: {body}"


def _memory_file(project: Path) -> Path:
    return project / ".mz" / "memory" / "MEMORY.md"


def _lessons_file(project: Path) -> Path:
    return project / ".mz" / "memory" / "lessons.md"


def _log_lines(context: str) -> list[str]:
    return [line for line in context.splitlines() if line.startswith("- [2")]


def _section(context: str, heading: str) -> list[str]:
    """The lines under `heading`, up to the blank line that ends the section."""
    lines = context.splitlines()
    if heading not in lines:
        return []
    body = lines[lines.index(heading) + 1 :]
    return body[: body.index("")] if "" in body else body


def _items(context: str, heading: str) -> list[str]:
    return [line for line in _section(context, heading) if line.startswith("- [")]


@pytest.fixture
def run_hook(tmp_path: Path) -> RunHook:
    base_env = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
    base_env["MZ_MEMORY_ROOT"] = str(tmp_path)

    def run(path: str = "") -> str:
        result = subprocess.run(
            [BASH, str(INJECT_SCRIPT)],
            input=COMPACT_INPUT,
            env={**base_env, **({"PATH": path} if path else {})},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stderr == ""
        return result.stdout

    return run


@pytest.fixture
def inject(run_hook: RunHook) -> Inject:
    def run() -> str:
        output = json.loads(run_hook())
        assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        context: str = output["hookSpecificOutput"]["additionalContext"]
        return context

    return run


@pytest.fixture
def seed_memory(tmp_path: Path, inject: Inject) -> SeedMemory:
    def seed(pinned: list[str], log: list[str], digest: list[str] | None = None) -> None:
        inject()
        memory = _memory_file(tmp_path)
        text = memory.read_text(encoding="utf-8")
        text = text.replace(f"{PIN_START}\n", PIN_START + "\n" + "".join(f"{p}\n" for p in pinned))
        text = text.replace(f"{LOG_START}\n", LOG_START + "\n" + "".join(f"{e}\n" for e in log))
        if digest is not None:
            section = "\n".join(["## Digest", "", DIGEST_START, *digest, DIGEST_END, "", ""])
            text = text.replace("## Activity Log\n", section + "## Activity Log\n")
        memory.write_text(text, encoding="utf-8")

    return seed


@pytest.fixture
def seed_lessons(tmp_path: Path) -> SeedLessons:
    def seed(curated: list[str], inbox: list[str]) -> None:
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
            *inbox,
            INBOX_END,
        ]
        path = _lessons_file(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return seed


class TestEmptyMemory:
    def test_missing_file_is_created_and_reported_empty(
        self, tmp_path: Path, inject: Inject
    ) -> None:
        context = inject()

        assert _memory_file(tmp_path).is_file()
        assert "initialized" in context

    def test_template_without_entries_is_reported_empty(self, inject: Inject) -> None:
        inject()

        assert "initialized" in inject()

    def test_lessons_alone_are_worth_injecting(
        self, inject: Inject, seed_lessons: SeedLessons
    ) -> None:
        seed_lessons([lesson(1)], [])

        context = inject()

        assert "initialized" not in context
        assert _items(context, LESSONS_HEADING) == [
            "- [L-0001] WHEN case 1 comes up → handle it 1 — WHY reason 1"
        ]


class TestSilentExits:
    def test_missing_jq_prints_nothing(
        self, run_hook: RunHook, seed_memory: SeedMemory, path_without_jq: PathWithoutJq
    ) -> None:
        seed_memory(["- [2026-11-01] migrate forward only"], ["- [2026-11-01] build_auth"])

        assert run_hook(path_without_jq(TOOLS_WITHOUT_JQ)) == ""


class TestPayload:
    def test_pinned_section_precedes_activity_log(
        self, inject: Inject, seed_memory: SeedMemory
    ) -> None:
        seed_memory(["- [2026-11-01] migrate forward only"], ["- [2026-11-01] build_auth"])

        context = inject()

        assert context.startswith(f"{HEADER}## Pinned\n- [2026-11-01] migrate forward only\n")
        assert context.endswith("## Activity Log\n- [2026-11-01] build_auth")

    def test_sections_run_from_rules_to_recent_history(
        self, inject: Inject, seed_memory: SeedMemory, seed_lessons: SeedLessons
    ) -> None:
        seed_memory(
            ["- [2026-11-01] migrate forward only"], ["- [2026-11-01] build_auth"], [digest_item(1)]
        )
        seed_lessons([lesson(1)], [])

        context = inject()

        headings = [line for line in context.splitlines() if line.startswith("## ")]
        assert headings == ["## Pinned", LESSONS_HEADING, "## Digest", "## Activity Log"]

    def test_pinned_only_memory_omits_log_section(
        self, inject: Inject, seed_memory: SeedMemory
    ) -> None:
        seed_memory(["- [2026-11-01] migrate forward only"], [])

        context = inject()

        assert "## Pinned" in context
        assert "## Activity Log" not in context

    def test_log_only_memory_omits_pinned_section(
        self, inject: Inject, seed_memory: SeedMemory
    ) -> None:
        seed_memory([], ["- [2026-11-01] build_auth"])

        context = inject()

        assert context == f"{HEADER}## Activity Log\n- [2026-11-01] build_auth"

    @pytest.mark.parametrize("where", ["log", "lesson", "digest"])
    def test_shell_and_json_metacharacters_pass_through_verbatim(
        self, inject: Inject, seed_memory: SeedMemory, seed_lessons: SeedLessons, where: str
    ) -> None:
        text = "quote \" backslash \\ $HOME `whoami` $(id) $'\\n'"
        seed_memory([], [f"- [2026-11-01] {text}"], [digest_item(1, text)])
        seed_lessons([lesson(1, text=text)], [])

        expected = {
            "log": f"- [2026-11-01] {text}",
            "lesson": f"- [L-0001] {text}",
            "digest": f"- [D-0001] {text}",
        }
        assert expected[where] in inject().splitlines()


class TestLessons:
    def test_curated_lessons_rank_by_count_then_recency(
        self, inject: Inject, seed_lessons: SeedLessons
    ) -> None:
        seed_lessons(
            [
                lesson(1, n=1, last="2026-10-05"),
                lesson(2, n=3, last="2026-10-01"),
                lesson(3, n=3, last="2026-10-09"),
                lesson(4, n=2, last="2026-10-20"),
            ],
            [],
        )

        injected = _items(inject(), LESSONS_HEADING)

        assert [line.split()[1] for line in injected] == [
            "[L-0003]",
            "[L-0002]",
            "[L-0004]",
            "[L-0001]",
        ]

    def test_only_the_top_twelve_curated_lessons_are_injected(
        self, inject: Inject, seed_lessons: SeedLessons
    ) -> None:
        # File order is weakest first, so the ranking has to come from the counts.
        seed_lessons([lesson(number, n=number) for number in range(1, 16)], [])

        injected = _items(inject(), LESSONS_HEADING)

        assert [line.split()[1] for line in injected] == [
            f"[L-{number:04d}]" for number in range(15, 15 - LESSONS_TOP, -1)
        ]

    def test_the_three_newest_inbox_items_follow_the_curated_lessons(
        self, inject: Inject, seed_lessons: SeedLessons
    ) -> None:
        seed_lessons([lesson(1)], [inbox_item(number) for number in range(5, 0, -1)])

        injected = _items(inject(), LESSONS_HEADING)

        assert [line.split()[1] for line in injected] == [
            "[L-0001]",
            "[I-0005]",
            "[I-0004]",
            "[I-0003]",
        ]

    def test_lessons_carry_their_standing_and_no_metadata(
        self, inject: Inject, seed_lessons: SeedLessons
    ) -> None:
        seed_lessons([lesson(1)], [inbox_item(2)])

        assert _section(inject(), LESSONS_HEADING) == [
            LESSONS_NOTE,
            "- [L-0001] WHEN case 1 comes up → handle it 1 — WHY reason 1",
            "- [I-0002] WHEN new case 2 → try it — WHY fresh",
        ]

    def test_lessons_stay_within_their_budget_in_whole_lines(
        self, inject: Inject, seed_lessons: SeedLessons
    ) -> None:
        texts = [f"WHEN long case {number} → {'step ' * 75}— WHY detail" for number in range(1, 13)]
        seed_lessons([lesson(number, text=text) for number, text in enumerate(texts, 1)], [])

        injected = _items(inject(), LESSONS_HEADING)

        line_chars = len(f"- [L-0001] {texts[0]}") + 1
        assert len(injected) == LESSONS_CHARS // line_chars
        assert injected == [
            f"- [L-{number:04d}] {texts[number - 1]}" for number in range(1, len(injected) + 1)
        ]

    def test_missing_lessons_file_adds_no_section_and_is_not_created(
        self, tmp_path: Path, inject: Inject, seed_memory: SeedMemory
    ) -> None:
        seed_memory([], ["- [2026-11-01] build_auth"])

        context = inject()

        assert LESSONS_HEADING not in context
        assert not _lessons_file(tmp_path).exists()


class TestPromotionHint:
    def test_lessons_seen_three_times_are_named_most_seen_first(
        self, inject: Inject, seed_lessons: SeedLessons
    ) -> None:
        seed_lessons([lesson(1, n=3), lesson(2, n=5), lesson(3, n=2)], [inbox_item(4)])

        hint = _section(inject(), LESSONS_HEADING)[-1]

        assert hint == (
            f"{HINT_START}L-0002, L-0001. At a natural pause, offer /lessons-promote"
            " to turn them into project rules."
        )

    def test_no_hint_while_every_lesson_is_below_three(
        self, inject: Inject, seed_lessons: SeedLessons
    ) -> None:
        seed_lessons([lesson(1, n=2), lesson(2, n=1)], [inbox_item(3)])

        assert HINT_START not in inject()

    def test_a_long_candidate_list_names_five_and_counts_the_rest(
        self, inject: Inject, seed_lessons: SeedLessons
    ) -> None:
        seed_lessons([lesson(number, n=number + 2) for number in range(1, 8)], [])

        hint = _section(inject(), LESSONS_HEADING)[-1]

        assert hint.startswith(f"{HINT_START}L-0007, L-0006, L-0005, L-0004, L-0003 and 2 more. ")


class TestDigest:
    def test_digest_items_are_injected_without_metadata(
        self, inject: Inject, seed_memory: SeedMemory
    ) -> None:
        seed_memory([], [], [digest_item(2), digest_item(1)])

        assert _section(inject(), "## Digest") == [
            "- [D-0002] Decision 2 still holds for the auth module",
            "- [D-0001] Decision 1 still holds for the auth module",
        ]

    def test_digest_stays_within_its_budget_in_whole_lines(
        self, inject: Inject, seed_memory: SeedMemory
    ) -> None:
        text = "Decision " + "detail " * 40
        seed_memory([], [], [digest_item(number, text.strip()) for number in range(1, 41)])

        injected = _items(inject(), "## Digest")

        assert len(injected) == DIGEST_CHARS // (len(f"- [D-0001] {text.strip()}") + 1)

    def test_memory_without_a_digest_has_no_digest_section(
        self, inject: Inject, seed_memory: SeedMemory
    ) -> None:
        seed_memory([], ["- [2026-11-01] build_auth"])

        assert "## Digest" not in inject()


class TestLimits:
    def test_log_keeps_the_200_most_recent_lines(
        self, inject: Inject, seed_memory: SeedMemory
    ) -> None:
        seed_memory([], [f"- [2026-11-01] task_{index:03d}" for index in range(1, 251)])

        logged = _log_lines(inject())

        assert len(logged) == 200
        assert logged[0].endswith("task_001")
        assert logged[-1].endswith("task_200")

    def test_oversized_payload_is_truncated_and_keeps_pinned(
        self, inject: Inject, seed_memory: SeedMemory
    ) -> None:
        seed_memory(
            ["- [2026-11-01] keep this invariant"],
            [f"- [2026-11-01] task_{index:03d} {'x' * 70}" for index in range(150)],
        )

        context = inject()

        assert context.endswith(TRUNCATION_MARK)
        assert len(context) == len(HEADER) + MAX_CHARS + len(TRUNCATION_MARK)
        assert "keep this invariant" in context

    def test_full_lessons_and_digest_still_leave_the_newest_log_lines(
        self, inject: Inject, seed_memory: SeedMemory, seed_lessons: SeedLessons
    ) -> None:
        seed_memory(
            ["- [2026-11-01] keep this invariant"],
            [f"- [2026-11-01] task_{index:03d}" for index in range(200)],
            [digest_item(number, "Decision " + "detail " * 40) for number in range(1, 41)],
        )
        seed_lessons([lesson(number, text="WHEN x → " + "y " * 180) for number in range(1, 13)], [])

        context = inject()

        assert len(context) == len(HEADER) + MAX_CHARS + len(TRUNCATION_MARK)
        assert _section(context, "## Activity Log")[0] == "- [2026-11-01] task_000"
