import json
import os
import shutil
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path

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
LOG_START = "<!-- mz-log-start -->"
LOG_END = "<!-- mz-log-end -->"
HEADER = "Project memory matches for this prompt (.mz/memory/MEMORY.md):\n"
TRUNCATION_MARK = "\n...[memory truncated]"
MAX_MATCHES = 15
MAX_CHARS = 2000
PINNED = "- [2026-11-01] migrate forward only"

type RunHook = Callable[..., str]
type SeedMemory = Callable[[list[str], list[str]], None]
type PathWithoutJq = Callable[[Iterable[str]], str]


def _event(prompt: str) -> str:
    return json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": prompt})


def _context(stdout: str) -> str:
    output = json.loads(stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    context: str = output["hookSpecificOutput"]["additionalContext"]
    return context


def _log_lines(context: str) -> list[str]:
    return [line for line in context.splitlines() if line.startswith("- [")]


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
        return result.stdout

    return run


@pytest.fixture
def seed_memory(tmp_path: Path) -> SeedMemory:
    def seed(pinned: list[str], log: list[str]) -> None:
        memory = tmp_path / ".mz" / "memory" / "MEMORY.md"
        memory.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Project Memory",
            "",
            "<!-- mz-memory:v2 -->",
            "",
            "## Pinned",
            "",
            PIN_START,
            *pinned,
            PIN_END,
            "",
            "## Activity Log",
            "",
            LOG_START,
            *log,
            LOG_END,
        ]
        memory.write_text("\n".join(lines) + "\n", encoding="utf-8")

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
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        seed_memory([], ["- [2026-11-01] build_auth"])

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
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        entry = '- [2026-11-01] oauth quote " backslash \\ $HOME `whoami` $(id)'
        seed_memory([], [entry])

        assert entry in _context(run_hook(_event("oauth")))


class TestLimits:
    def test_oversized_payload_is_truncated_at_max_chars(
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        seed_memory(
            [PINNED],
            [f"- [2026-11-01] oauth task_{index:02d} {'x' * 200}" for index in range(MAX_MATCHES)],
        )

        context = _context(run_hook(_event("oauth")))

        assert context.startswith(f"{HEADER}\n## Pinned\n{PINNED}\n")
        assert context.endswith(TRUNCATION_MARK)

    def test_long_prompt_still_matches_on_its_first_keywords(
        self, run_hook: RunHook, seed_memory: SeedMemory
    ) -> None:
        # Enough distinct words that head closes the pipe early, so awk gets SIGPIPE.
        filler = " ".join(f"word{index:05d}" for index in range(20_000))
        seed_memory([], ["- [2026-11-01] oauth rotation"])

        context = _context(run_hook(_event(f"oauth {filler}")))

        assert _log_lines(context) == ["- [2026-11-01] oauth rotation"]
