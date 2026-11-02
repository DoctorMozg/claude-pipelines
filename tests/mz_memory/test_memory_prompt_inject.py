import json
import os
import shutil
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "mz-memory"
    / "scripts"
    / "memory-prompt-inject.sh"
)
BASH = shutil.which("bash") or "/bin/bash"
# Everything the script runs except jq, so a PATH built from these hides jq only.
TOOLS_WITHOUT_JQ = ("dirname", "cat", "tr", "awk", "head", "sed", "paste", "grep")
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
HEADER = "Project memory matches for this prompt (.mz/memory/MEMORY.md):\n"
LESSONS_HEADING = "## Matched lessons (.mz/memory/lessons.md)"
NUDGE = (
    "If this corrects something you did, fix it, then save the lesson with "
    '/memory-note --lesson "WHEN … → … — WHY …".'
)
TRUNCATION_MARK = "\n...[memory truncated]"
MAX_MATCHES = 15
MAX_LESSONS = 5
LESSONS_CHARS = 1500
MAX_CHARS = 4000
CORRECTION_SCAN_CHARS = 500
PINNED = "- [2026-11-01] migrate forward only"

type RunHook = Callable[..., str]
type SeedLessons = Callable[[list[str], list[str]], None]
type PathWithoutJq = Callable[[Iterable[str]], str]


class SeedMemory(Protocol):
    def __call__(
        self, pinned: list[str], log: list[str], digest: list[str] | None = None
    ) -> None: ...


def lesson(number: int, text: str, n: int = 1, src: str = "", tags: str = "jq") -> str:
    source = src or f"task{number}@abc1234"
    return (
        f"- [L-{number:04d}] n={n} last=2026-10-01 trig=review src={source} tags={tags} :: {text}"
    )


def inbox_item(number: int, text: str) -> str:
    return f"- [I-{number:04d}] 2026-11-02 trig=failure src=task{number} status=failed :: {text}"


def digest_item(number: int, text: str, src: str = "mz-compressed") -> str:
    return f"- [D-{number:04d}] n=1 last=2026-10-01 trig=migrated src={src} tags=auth :: {text}"


def _event(prompt: str) -> str:
    return json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": prompt})


def _context(stdout: str) -> str:
    output = json.loads(stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    context: str = output["hookSpecificOutput"]["additionalContext"]
    return context


def _nudged(stdout: str) -> bool:
    # The raw JSON escapes the nudge's quotes, so it is only found in the parsed context.
    return stdout != "" and NUDGE in _context(stdout)


def _log_lines(context: str) -> list[str]:
    return [line for line in context.splitlines() if line.startswith("- [2")]


def _section(context: str, heading: str) -> list[str]:
    """The lines under `heading`, up to the blank line that ends the section."""
    lines = context.splitlines()
    if heading not in lines:
        return []
    body = lines[lines.index(heading) + 1 :]
    return body[: body.index("")] if "" in body else body


@pytest.fixture
def run_hook(tmp_path: Path) -> RunHook:
    base_env = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
    base_env["MZ_MEMORY_ROOT"] = str(tmp_path)

    def run(stdin: str, path: str = "") -> str:
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
        assert result.stderr == ""
        return result.stdout

    return run


@pytest.fixture
def seed_memory(tmp_path: Path) -> SeedMemory:
    def seed(pinned: list[str], log: list[str], digest: list[str] | None = None) -> None:
        memory = tmp_path / ".mz" / "memory" / "MEMORY.md"
        memory.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Project Memory", "", "<!-- mz-memory:v2 -->", "", "## Pinned", "", PIN_START]
        lines += [*pinned, PIN_END, ""]
        if digest is not None:
            lines += ["## Digest", "", DIGEST_START, *digest, DIGEST_END, ""]
        lines += ["## Activity Log", "", LOG_START, *log, LOG_END]
        memory.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return seed


@pytest.fixture
def seed_lessons(tmp_path: Path) -> SeedLessons:
    def seed(curated: list[str], inbox: list[str]) -> None:
        lines = ["# Project Lessons", "", "## Lessons", "", LESSONS_START, *curated, LESSONS_END]
        lines += ["", "## Inbox", "", INBOX_START, *inbox, INBOX_END]
        path = tmp_path / ".mz" / "memory" / "lessons.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return seed


class TestSilentExits:
    def test_missing_memory_file_prints_nothing(self, run_hook: RunHook) -> None:
        assert run_hook(_event("rotate oauth tokens")) == ""

    @pytest.mark.parametrize(
        "stdin",
        ["", '{"hook_event_name": "UserPromptSubmit"}', "{not json"],
        ids=["empty", "no-prompt", "malformed"],
    )
    def test_unusable_input_prints_nothing(
        self, run_hook: RunHook, seed_memory: SeedMemory, stdin: str
    ) -> None:
        seed_memory([PINNED], ["- [2026-11-01] rotate oauth tokens"])

        assert run_hook(stdin) == ""

    @pytest.mark.parametrize(
        "prompt", ["fix the bug", "what about these tests"], ids=["short-words", "stopwords"]
    )
    def test_prompt_without_keywords_prints_nothing(
        self, run_hook: RunHook, seed_memory: SeedMemory, prompt: str
    ) -> None:
        seed_memory([PINNED], ["- [2026-11-01] fix the bug: what about these tests"])

        assert run_hook(_event(prompt)) == ""

    def test_unmatched_prompt_without_pinned_prints_nothing(
        self, run_hook: RunHook, seed_memory: SeedMemory, seed_lessons: SeedLessons
    ) -> None:
        seed_memory([], ["- [2026-11-01] build_auth"])
        seed_lessons([lesson(1, "WHEN jq parses → wrap values")], [])

        assert run_hook(_event("deploy kubernetes cluster")) == ""

    def test_missing_jq_prints_nothing(
        self, run_hook: RunHook, seed_memory: SeedMemory, path_without_jq: PathWithoutJq
    ) -> None:
        seed_memory([PINNED], ["- [2026-11-01] rotate oauth tokens"])

        assert run_hook(_event("rotate oauth tokens"), path_without_jq(TOOLS_WITHOUT_JQ)) == ""


class TestMatching:
    def test_pinned_section_precedes_matched_entries(
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        seed_memory([PINNED], ["- [2026-11-02] rotate oauth tokens", "- [2026-11-01] build_ui"])

        context = _context(run_hook(_event("why did the oauth refresh break?")))

        assert context == (
            f"{HEADER}\n## Pinned\n{PINNED}\n"
            "\n## Matched activity entries\n- [2026-11-02] rotate oauth tokens\n"
        )

    def test_pinned_section_is_sent_without_matching_entries(
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        seed_memory([PINNED], ["- [2026-11-01] build_ui"])

        context = _context(run_hook(_event("deploy kubernetes cluster")))

        assert context == f"{HEADER}\n## Pinned\n{PINNED}\n"

    def test_keyword_match_ignores_case(self, run_hook: RunHook, seed_memory: SeedMemory) -> None:
        seed_memory([], ["- [2026-11-01] Migrated OAuth tokens"])

        context = _context(run_hook(_event("OAUTH is broken again")))

        assert _log_lines(context) == ["- [2026-11-01] Migrated OAuth tokens"]

    def test_matches_are_capped_at_the_most_recent_fifteen(
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        seed_memory([], [f"- [2026-11-01] oauth task_{index:02d}" for index in range(20)])

        logged = _log_lines(_context(run_hook(_event("oauth"))))

        assert len(logged) == MAX_MATCHES
        assert logged[0].endswith("task_00")
        assert logged[-1].endswith("task_14")

    def test_shell_and_json_metacharacters_pass_through_verbatim(
        self, run_hook: RunHook, seed_memory: SeedMemory, seed_lessons: SeedLessons
    ) -> None:
        text = 'oauth quote " backslash \\ $HOME `whoami` $(id)'
        seed_memory([], [f"- [2026-11-01] {text}"])
        seed_lessons([lesson(1, text)], [])

        context = _context(run_hook(_event("oauth")))

        assert f"- [2026-11-01] {text}" in context.splitlines()
        assert f"- [L-0001] {text}" in context.splitlines()


class TestDigestMatching:
    def test_digest_items_match_on_their_text_ahead_of_log_entries(
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        seed_memory(
            [], ["- [2026-11-01] rotate oauth tokens"], [digest_item(1, "Tokens rotate on use")]
        )

        context = _context(run_hook(_event("when do tokens rotate")))

        assert _section(context, "## Matched activity entries") == [
            "- [D-0001] Tokens rotate on use",
            "- [2026-11-01] rotate oauth tokens",
        ]

    def test_digest_metadata_never_matches(
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        seed_memory([], [], [digest_item(1, "Tokens rotate on use")])

        assert run_hook(_event("why was the log compressed or migrated")) == ""

    def test_digest_items_share_the_match_cap_with_the_log(
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        seed_memory(
            [],
            [f"- [2026-11-01] oauth task_{index:02d}" for index in range(10)],
            [digest_item(number, f"oauth decision {number}") for number in range(1, 11)],
        )

        entries = _section(_context(run_hook(_event("oauth"))), "## Matched activity entries")

        assert len(entries) == MAX_MATCHES
        assert entries[:10] == [
            f"- [D-{number:04d}] oauth decision {number}" for number in range(1, 11)
        ]


class TestLessonMatching:
    def test_lessons_sit_between_pinned_and_activity_entries(
        self, run_hook: RunHook, seed_memory: SeedMemory, seed_lessons: SeedLessons
    ) -> None:
        seed_memory([PINNED], ["- [2026-11-02] rotate oauth tokens"])
        seed_lessons([lesson(1, "WHEN oauth refresh fails → check the clock")], [])

        context = _context(run_hook(_event("oauth refresh is broken")))

        assert context == (
            f"{HEADER}\n## Pinned\n{PINNED}\n"
            f"\n{LESSONS_HEADING}\n- [L-0001] WHEN oauth refresh fails → check the clock\n"
            "\n## Matched activity entries\n- [2026-11-02] rotate oauth tokens\n"
        )

    def test_more_distinct_keywords_outrank_a_higher_count(
        self, run_hook: RunHook, seed_memory: SeedMemory, seed_lessons: SeedLessons
    ) -> None:
        seed_memory([], [])
        seed_lessons(
            [
                lesson(1, "WHEN oauth fails → retry", n=9),
                lesson(2, "WHEN oauth refresh fails → check the clock", n=1),
                lesson(3, "WHEN kubernetes deploys → pin the image", n=20),
            ],
            [],
        )

        context = _context(run_hook(_event("oauth refresh is broken")))

        assert [line.split()[1] for line in _section(context, LESSONS_HEADING)] == [
            "[L-0002]",
            "[L-0001]",
        ]

    def test_equal_hits_go_to_the_lesson_seen_more_often(
        self, run_hook: RunHook, seed_memory: SeedMemory, seed_lessons: SeedLessons
    ) -> None:
        seed_memory([], [])
        seed_lessons(
            [
                lesson(1, "WHEN oauth fails → retry", n=1),
                lesson(2, "WHEN oauth expires → renew", n=4),
            ],
            [inbox_item(3, "WHEN oauth breaks → log it")],
        )

        context = _context(run_hook(_event("oauth")))

        assert [line.split()[1] for line in _section(context, LESSONS_HEADING)] == [
            "[L-0002]",
            "[L-0001]",
            "[I-0003]",
        ]

    def test_tags_match_but_other_metadata_does_not(
        self, run_hook: RunHook, seed_memory: SeedMemory, seed_lessons: SeedLessons
    ) -> None:
        seed_memory([], [])
        seed_lessons(
            [
                lesson(1, "WHEN a token expires → renew it", tags="oauth"),
                lesson(2, "WHEN a cache misses → warm it", src="build_oauth@abc1234"),
            ],
            [],
        )

        context = _context(run_hook(_event("oauth")))

        assert _section(context, LESSONS_HEADING) == ["- [L-0001] WHEN a token expires → renew it"]

    def test_lessons_are_capped_at_five(
        self, run_hook: RunHook, seed_memory: SeedMemory, seed_lessons: SeedLessons
    ) -> None:
        seed_memory([], [])
        seed_lessons(
            [lesson(number, f"WHEN oauth case {number} → handle it") for number in range(1, 9)], []
        )

        context = _context(run_hook(_event("oauth")))

        assert len(_section(context, LESSONS_HEADING)) == MAX_LESSONS

    def test_lessons_stay_within_their_budget_in_whole_lines(
        self, run_hook: RunHook, seed_memory: SeedMemory, seed_lessons: SeedLessons
    ) -> None:
        text = "WHEN oauth " + "step " * 70 + "→ stop"
        seed_memory([], [])
        seed_lessons([lesson(number, text) for number in range(1, 6)], [])

        injected = _section(_context(run_hook(_event("oauth"))), LESSONS_HEADING)

        assert len(injected) == LESSONS_CHARS // (len(f"- [L-0001] {text}") + 1)
        assert all(line.endswith("→ stop") for line in injected)


CORRECTIONS = {
    "no-comma": "no, that's the wrong file",
    "nope": "Nope. Use uv instead",
    "wrong-first": "Wrong, the config lives in pyproject",
    "broke": "you broke the build",
    "forgot": "Looks fine, but you forgot the tests",
    "told-you": "I told you to use uv",
    "should-have": "you should have used the helper",
    "not-what-i-asked": "That's not what I asked for",
    "curly-apostrophe": "that\u2019s wrong, revert it",
    "why-did-you": "why did you delete the fixtures",
    "stop-doing": "stop adding comments everywhere",
    "revert": "revert that change",
    "later-line": "Thanks for the summary.\nno, the other module",
}
NOT_CORRECTIONS = {
    "dont-search": "don't search the files, just answer",
    "must-never": "this hook must never call the network",
    "wrong-later": "fix the wrong import in auth.py",
    "no-op": "no-op handling for the oauth refresh",
    "no-problem": "no problem, now rotate the oauth tokens",
    "know": "I know the oauth flow is slow",
    "why-is": "why is the oauth build slow",
}


class TestCorrectionNudge:
    @pytest.mark.parametrize("prompt", CORRECTIONS.values(), ids=CORRECTIONS.keys())
    def test_a_correction_gets_the_nudge_right_after_the_header(
        self, run_hook: RunHook, seed_memory: SeedMemory, prompt: str
    ) -> None:
        seed_memory([PINNED], [])

        context = _context(run_hook(_event(prompt)))

        assert context.startswith(f"{HEADER}\n{NUDGE}\n")

    @pytest.mark.parametrize("prompt", NOT_CORRECTIONS.values(), ids=NOT_CORRECTIONS.keys())
    def test_instructions_and_questions_get_no_nudge(
        self, run_hook: RunHook, seed_memory: SeedMemory, prompt: str
    ) -> None:
        seed_memory([PINNED], [])

        assert not _nudged(run_hook(_event(prompt)))

    def test_slash_commands_get_no_nudge(self, run_hook: RunHook, seed_memory: SeedMemory) -> None:
        seed_memory([PINNED], [])

        assert not _nudged(run_hook(_event('/memory-note --lesson "you broke the build"')))

    def test_only_the_opening_of_a_prompt_is_checked(
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        seed_memory([PINNED], [])
        pasted = "summarize this log: " + "trace " * (CORRECTION_SCAN_CHARS // 6)

        assert not _nudged(run_hook(_event(f"{pasted}\nERROR: you forgot the token")))

    def test_a_bare_correction_needs_no_keywords_or_memory(
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        seed_memory([], [])

        assert _context(run_hook(_event("no, not that"))) == f"{HEADER}\n{NUDGE}\n"

    def test_the_nudge_survives_the_character_cap(
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        seed_memory(
            [PINNED], [f"- [2026-11-01] oauth task_{index:02d} {'x' * 300}" for index in range(15)]
        )

        context = _context(run_hook(_event("you broke the oauth flow")))

        assert context.endswith(TRUNCATION_MARK)
        assert context.startswith(f"{HEADER}\n{NUDGE}\n")


class TestLimits:
    def test_oversized_payload_is_truncated_at_max_chars(
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        seed_memory(
            [PINNED],
            [f"- [2026-11-01] oauth task_{index:02d} {'x' * 300}" for index in range(MAX_MATCHES)],
        )

        context = _context(run_hook(_event("oauth")))

        assert context.startswith(f"{HEADER}\n## Pinned\n{PINNED}\n")
        assert context.endswith(TRUNCATION_MARK)
        assert len(context) == MAX_CHARS + len(TRUNCATION_MARK)

    def test_long_prompt_still_matches_on_its_first_keywords(
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        # Enough distinct words that head closes the pipe early, so awk gets SIGPIPE.
        filler = " ".join(f"word{index:05d}" for index in range(20_000))
        seed_memory([], ["- [2026-11-01] oauth rotation"])

        context = _context(run_hook(_event(f"oauth {filler}")))

        assert _log_lines(context) == ["- [2026-11-01] oauth rotation"]
