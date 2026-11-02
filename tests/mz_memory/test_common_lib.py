import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from .memory_helpers import BASH, LOG_END, LOG_START, SCRIPTS, clean_env, region

COMMON_LIB = SCRIPTS / "lib" / "common.sh"

type CallHelper = Callable[[str, Path], subprocess.CompletedProcess[str]]


@pytest.fixture
def large_memory(tmp_path: Path) -> Path:
    entries = [f"- [2026-11-01] task_{index:05d} {'x' * 100}" for index in range(5_000)]
    path = tmp_path / "MEMORY.md"
    path.write_text("\n".join([LOG_START, *entries, LOG_END]) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def call_helper() -> CallHelper:
    """Call a common.sh helper the way the hook scripts do: under set -euo pipefail."""

    def call(command: str, memory: Path) -> subprocess.CompletedProcess[str]:
        script = f'set -euo pipefail; source "$1"; {command}'
        return subprocess.run(
            [BASH, "-c", script, "_", str(COMMON_LIB), str(memory)],
            env=clean_env(),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    return call


class TestExtractLog:
    def test_cap_far_below_log_size_still_succeeds(
        self, call_helper: CallHelper, large_memory: Path
    ) -> None:
        # head stops after 200 lines while awk still has ~500 KB to write, so awk gets SIGPIPE.
        result = call_helper('extract_log "$2" 200', large_memory)

        assert result.returncode == 0, result.stderr
        lines = result.stdout.splitlines()
        assert len(lines) == 200
        assert lines[0].startswith("- [2026-11-01] task_00000 ")

    def test_cap_above_log_size_returns_every_entry(
        self, call_helper: CallHelper, large_memory: Path
    ) -> None:
        result = call_helper('extract_log "$2" 9999', large_memory)

        assert result.returncode == 0, result.stderr
        assert len(result.stdout.splitlines()) == 5_000


def _log_lines(memory: Path) -> list[str]:
    return region(memory, LOG_START, LOG_END)


class TestPrependToLog:
    def test_default_cap_counts_the_new_block(
        self, call_helper: CallHelper, large_memory: Path
    ) -> None:
        command = "printf '%s\\n' '- new one' '- new two' | prepend_to_log \"$2\""
        result = call_helper(command, large_memory)

        assert result.returncode == 0, result.stderr
        log = _log_lines(large_memory)
        assert len(log) == 400
        assert log[:3] == ["- new one", "- new two", log[2]]
        assert log[2].startswith("- [2026-11-01] task_00000 ")

    def test_backslashes_in_entries_are_kept(
        self, call_helper: CallHelper, large_memory: Path
    ) -> None:
        entry = r"- [2026-11-02] moved C:\new\tools to D:\temp"

        result = call_helper(f"printf '%s\\n' '{entry}' | prepend_to_log \"$2\" 10", large_memory)

        assert result.returncode == 0, result.stderr
        assert _log_lines(large_memory)[0] == entry

    def test_new_block_longer_than_the_cap_is_cut_to_it(
        self, call_helper: CallHelper, large_memory: Path
    ) -> None:
        result = call_helper("seq -f '- new %g' 1 30 | prepend_to_log \"$2\" 10", large_memory)

        assert result.returncode == 0, result.stderr
        assert _log_lines(large_memory) == [f"- new {index}" for index in range(1, 11)]
