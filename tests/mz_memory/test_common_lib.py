import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

COMMON_LIB = (
    Path(__file__).resolve().parents[2] / "plugins" / "mz-memory" / "scripts" / "lib" / "common.sh"
)
BASH = shutil.which("bash") or "/bin/bash"
LOG_START = "<!-- mz-log-start -->"
LOG_END = "<!-- mz-log-end -->"

type CallHelper = Callable[[str, Path], subprocess.CompletedProcess[str]]


@pytest.fixture
def memory_file(tmp_path: Path) -> Path:
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
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    return call


class TestExtractLog:
    def test_cap_far_below_log_size_still_succeeds(
        self, call_helper: CallHelper, memory_file: Path
    ) -> None:
        # head stops after 200 lines while awk still has ~500 KB to write, so awk gets SIGPIPE.
        result = call_helper('extract_log "$2" 200', memory_file)

        assert result.returncode == 0, result.stderr
        lines = result.stdout.splitlines()
        assert len(lines) == 200
        assert lines[0].startswith("- [2026-11-01] task_00000 ")

    def test_cap_above_log_size_returns_every_entry(
        self, call_helper: CallHelper, memory_file: Path
    ) -> None:
        result = call_helper('extract_log "$2" 9999', memory_file)

        assert result.returncode == 0, result.stderr
        assert len(result.stdout.splitlines()) == 5_000
