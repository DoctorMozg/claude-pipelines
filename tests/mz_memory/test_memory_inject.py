import json
import os
import shutil
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest

INJECT_SCRIPT = (
    Path(__file__).resolve().parents[2] / "plugins" / "mz-memory" / "scripts" / "memory-inject.sh"
)
BASH = shutil.which("bash") or "/bin/bash"
# Everything the script runs except jq, so a PATH built from these hides jq only.
TOOLS_WITHOUT_JQ = ("dirname", "mkdir", "mktemp", "mv", "cat", "grep", "awk", "head", "sed")
PIN_START = "<!-- mz-pinned-start -->"
LOG_START = "<!-- mz-log-start -->"
HEADER = "Project memory (.mz/memory/MEMORY.md):\n"
TRUNCATION_MARK = "\n...[memory truncated]"
MAX_CHARS = 8000
COMPACT_INPUT = json.dumps({"hook_event_name": "SessionStart", "source": "compact"})

type RunHook = Callable[..., str]
type Inject = Callable[[], str]
type SeedMemory = Callable[[list[str], list[str]], None]
type PathWithoutJq = Callable[[Iterable[str]], str]


def _memory_file(project: Path) -> Path:
    return project / ".mz" / "memory" / "MEMORY.md"


def _log_lines(context: str) -> list[str]:
    return [line for line in context.splitlines() if line.startswith("- [")]


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
    def seed(pinned: list[str], log: list[str]) -> None:
        inject()
        memory = _memory_file(tmp_path)
        text = memory.read_text(encoding="utf-8")
        text = text.replace(f"{PIN_START}\n", PIN_START + "\n" + "".join(f"{p}\n" for p in pinned))
        text = text.replace(f"{LOG_START}\n", LOG_START + "\n" + "".join(f"{e}\n" for e in log))
        memory.write_text(text, encoding="utf-8")

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

    def test_shell_and_json_metacharacters_pass_through_verbatim(
        self, inject: Inject, seed_memory: SeedMemory
    ) -> None:
        entry = '- [2026-11-01] quote " backslash \\ $HOME `whoami` $(id)'
        seed_memory([], [entry])

        assert entry in inject()


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
