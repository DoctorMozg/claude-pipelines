import os
import shlex
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pytest

COMPRESS_SCRIPT = (
    Path(__file__).resolve().parents[2] / "plugins" / "mz-memory" / "scripts" / "memory-compress.sh"
)
BASH = shutil.which("bash") or "/bin/bash"
# Everything the script runs besides claude; PATH holds only these, so the real CLI never runs.
TOOLS = (
    "dirname",
    "mkdir",
    "rmdir",
    "mktemp",
    "mv",
    "cat",
    "awk",
    "grep",
    "head",
    "tail",
    "timeout",
)
LOG_START = "<!-- mz-log-start -->"
LOG_END = "<!-- mz-log-end -->"
COMPRESSED_MARK = "<!-- mz-compressed -->"
KEEP_RECENT = 100
COMPRESS_THRESHOLD = 300
SUMMARY = "## Recurring decisions\n- [2026-11-01] summarized older work"

type InstallClaude = Callable[[str], None]
type RunCompress = Callable[[], None]


class SeedLog(Protocol):
    def __call__(self, count: int, extra_lines: int = 0) -> list[str]: ...


def _memory_file(project: Path) -> Path:
    return project / ".mz" / "memory" / "MEMORY.md"


def _log_region(project: Path) -> list[str]:
    lines = _memory_file(project).read_text(encoding="utf-8").splitlines()
    return lines[lines.index(LOG_START) + 1 : lines.index(LOG_END)]


@pytest.fixture
def seed_log(tmp_path: Path) -> SeedLog:
    def seed(count: int, extra_lines: int = 0) -> list[str]:
        """Write `count` entries, each trailed by `extra_lines` indented lines; return all lines."""
        entries: list[str] = []
        for index in range(count):
            entries.append(f"- [2026-11-01] task_{index:04d} {'x' * 150}")
            entries.extend(f"  - decision {index}.{line}" for line in range(extra_lines))
        memory = _memory_file(tmp_path)
        memory.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Project Memory", "", "## Activity Log", "", LOG_START, *entries, LOG_END]
        memory.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return entries

    return seed


@pytest.fixture
def bin_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    for tool in TOOLS:
        located = shutil.which(tool)
        assert located is not None, f"{tool} is not installed"
        (directory / tool).symlink_to(located)
    return directory


@pytest.fixture
def claude_env_file(tmp_path: Path) -> Path:
    return tmp_path / "claude_compress_env"


@pytest.fixture
def install_claude(bin_dir: Path, claude_env_file: Path) -> InstallClaude:
    def install(summary: str) -> None:
        stub = bin_dir / "claude"
        record = shlex.quote(str(claude_env_file))
        stub.write_text(
            f"#!{BASH}\ncat >/dev/null\n"
            f"printf '%s' \"${{MZ_MEMORY_COMPRESS-unset}}\" >{record}\n"
            f"printf '%s' {shlex.quote(summary)}\n"
        )
        stub.chmod(0o755)

    return install


@pytest.fixture
def run_compress(tmp_path: Path, bin_dir: Path) -> RunCompress:
    env = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
    env.update({"PATH": str(bin_dir), "MZ_MEMORY_ROOT": str(tmp_path)})

    def run() -> None:
        result = subprocess.run(
            [BASH, str(COMPRESS_SCRIPT)],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    return run


class TestCompression:
    def test_long_log_keeps_recent_entries_and_appends_summary(
        self,
        tmp_path: Path,
        seed_log: SeedLog,
        install_claude: InstallClaude,
        run_compress: RunCompress,
    ) -> None:
        # About 160 KB of log, past the pipe buffer, so an unguarded `| head` would get SIGPIPE.
        entries = seed_log(1_000)
        install_claude(SUMMARY)

        run_compress()

        expected = [*entries[:KEEP_RECENT], "", COMPRESSED_MARK, *SUMMARY.splitlines()]
        assert _log_region(tmp_path) == expected

    def test_lock_is_released_after_a_run(
        self,
        tmp_path: Path,
        seed_log: SeedLog,
        install_claude: InstallClaude,
        run_compress: RunCompress,
    ) -> None:
        seed_log(COMPRESS_THRESHOLD + 1)
        install_claude(SUMMARY)

        run_compress()

        assert not (tmp_path / ".mz" / "memory" / ".compress.lock").exists()

    def test_multi_line_entries_count_toward_the_line_threshold(
        self,
        tmp_path: Path,
        seed_log: SeedLog,
        install_claude: InstallClaude,
        run_compress: RunCompress,
    ) -> None:
        seed_log(110, extra_lines=2)
        install_claude(SUMMARY)

        run_compress()

        assert COMPRESSED_MARK in _log_region(tmp_path)

    def test_recent_block_keeps_whole_entries(
        self,
        tmp_path: Path,
        seed_log: SeedLog,
        install_claude: InstallClaude,
        run_compress: RunCompress,
    ) -> None:
        # Three-line entries put an entry across line 100; the cut moves to that entry's end.
        lines = seed_log(120, extra_lines=2)
        install_claude(SUMMARY)

        run_compress()

        log = _log_region(tmp_path)
        assert log[: log.index(COMPRESSED_MARK) - 1] == lines[:102]

    def test_child_claude_runs_with_compression_off(
        self,
        seed_log: SeedLog,
        install_claude: InstallClaude,
        run_compress: RunCompress,
        claude_env_file: Path,
    ) -> None:
        seed_log(COMPRESS_THRESHOLD + 1)
        install_claude(SUMMARY)

        run_compress()

        assert claude_env_file.read_text(encoding="utf-8") == "0"


class TestSkips:
    def test_log_at_threshold_is_left_alone(
        self,
        tmp_path: Path,
        seed_log: SeedLog,
        install_claude: InstallClaude,
        run_compress: RunCompress,
    ) -> None:
        entries = seed_log(COMPRESS_THRESHOLD)
        install_claude(SUMMARY)

        run_compress()

        assert _log_region(tmp_path) == entries

    def test_missing_claude_leaves_log_alone(
        self, tmp_path: Path, seed_log: SeedLog, run_compress: RunCompress
    ) -> None:
        entries = seed_log(COMPRESS_THRESHOLD + 1)

        run_compress()

        assert _log_region(tmp_path) == entries

    def test_held_lock_leaves_log_alone(
        self,
        tmp_path: Path,
        seed_log: SeedLog,
        install_claude: InstallClaude,
        run_compress: RunCompress,
    ) -> None:
        entries = seed_log(COMPRESS_THRESHOLD + 1)
        install_claude(SUMMARY)
        lock = tmp_path / ".mz" / "memory" / ".compress.lock"
        lock.mkdir()

        run_compress()

        assert _log_region(tmp_path) == entries
        assert lock.is_dir()

    def test_empty_summary_leaves_log_alone(
        self,
        tmp_path: Path,
        seed_log: SeedLog,
        install_claude: InstallClaude,
        run_compress: RunCompress,
    ) -> None:
        entries = seed_log(COMPRESS_THRESHOLD + 1)
        install_claude("")

        run_compress()

        assert _log_region(tmp_path) == entries
