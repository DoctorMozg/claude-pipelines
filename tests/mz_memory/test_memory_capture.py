import os
import shlex
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pytest

LOG_START = "<!-- mz-log-start -->"
LOG_END = "<!-- mz-log-end -->"
COMPRESSED_MARK = "<!-- mz-compressed -->"
MAX_LOG_LINES = 400
COMPRESS_THRESHOLD = 300

type CaptureRunner = Callable[[dict[str, str]], None]
type MarkChanged = Callable[[Path], None]


class TaskWriter(Protocol):
    def __call__(self, name: str, status: str, extra: str = "") -> Path: ...


class RawTaskWriter(Protocol):
    def __call__(self, name: str, text: str) -> Path: ...


def _memory_file(project: Path) -> Path:
    return project / ".mz" / "memory" / "MEMORY.md"


def _logged_tasks(project: Path) -> list[str]:
    lines = _memory_file(project).read_text(encoding="utf-8").splitlines()
    return [line.split()[2] for line in lines if line.startswith("- [")]


def _log_region(project: Path) -> list[str]:
    lines = _memory_file(project).read_text(encoding="utf-8").splitlines()
    return lines[lines.index(LOG_START) + 1 : lines.index(LOG_END)]


def _entries(count: int, extra_lines: int = 0) -> list[str]:
    lines: list[str] = []
    for index in range(count):
        lines.append(f"- [2026-10-01] task_{index:04d} (phase=done)")
        lines.extend(f"  - decision {index}.{line}" for line in range(extra_lines))
    return lines


def _seed_log(project: Path, runner: CaptureRunner, env: dict[str, str], lines: list[str]) -> None:
    """Create a current-layout memory file through capture itself, then fill its Activity Log."""
    runner({**env, "MZ_MEMORY_COMPRESS": "0"})
    memory = _memory_file(project)
    text = memory.read_text(encoding="utf-8")
    memory.write_text(
        text.replace(f"{LOG_START}\n", f"{LOG_START}\n" + "".join(f"{line}\n" for line in lines)),
        encoding="utf-8",
    )


def _wait_until(condition: Callable[[], bool], seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return condition()


class TestStatusFilter:
    def test_schema_complete_status_is_captured_with_decisions(
        self, project: Path, write_task: TaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_task("2026_11_01_build_auth", "complete", "\n## Decisions\n\n- use JWT\n")

        run_capture()

        assert _logged_tasks(project) == ["2026_11_01_build_auth"]
        assert "use JWT" in _memory_file(project).read_text(encoding="utf-8")

    def test_legacy_completed_status_is_captured(
        self, project: Path, write_task: TaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_task("2026_11_01_debug_crash", "completed")

        run_capture()

        assert _logged_tasks(project) == ["2026_11_01_debug_crash"]

    @pytest.mark.parametrize("status", ["pending", "running", "failed", "aborted_by_user"])
    def test_unfinished_statuses_are_ignored(
        self,
        project: Path,
        write_task: TaskWriter,
        run_capture: Callable[[], None],
        status: str,
    ) -> None:
        write_task("2026_11_01_audit_api", status)

        run_capture()

        assert _logged_tasks(project) == []


class TestDedup:
    def test_second_run_does_not_duplicate(
        self, project: Path, write_task: TaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_task("2026_11_01_build_auth", "complete")

        run_capture()
        run_capture()

        assert _logged_tasks(project) == ["2026_11_01_build_auth"]

    def test_finished_task_is_not_relogged_when_another_completes(
        self,
        project: Path,
        write_task: TaskWriter,
        run_capture: Callable[[], None],
        mark_changed_since_capture: MarkChanged,
    ) -> None:
        write_task("2026_11_01_build_auth", "complete")
        run_capture()
        newer = write_task("2026_11_02_debug_crash", "complete")
        mark_changed_since_capture(newer)

        run_capture()

        assert sorted(_logged_tasks(project)) == ["2026_11_01_build_auth", "2026_11_02_debug_crash"]

    def test_task_that_finishes_later_is_captured(
        self,
        project: Path,
        write_task: TaskWriter,
        run_capture: Callable[[], None],
        mark_changed_since_capture: MarkChanged,
    ) -> None:
        write_task("2026_11_01_build_auth", "running")
        run_capture()
        finished = write_task("2026_11_01_build_auth", "complete")
        mark_changed_since_capture(finished)

        run_capture()

        assert _logged_tasks(project) == ["2026_11_01_build_auth"]

    def test_edited_state_is_logged_again(
        self,
        project: Path,
        write_task: TaskWriter,
        run_capture: Callable[[], None],
        mark_changed_since_capture: MarkChanged,
    ) -> None:
        write_task("2026_11_01_build_auth", "complete")
        run_capture()
        rerun = write_task("2026_11_01_build_auth", "complete", "\n## Notes\n\n- reran phase 3\n")
        mark_changed_since_capture(rerun)

        run_capture()

        assert _logged_tasks(project) == ["2026_11_01_build_auth", "2026_11_01_build_auth"]


class TestUpgradeFromDateKeyedDedup:
    @pytest.fixture
    def seeded_log(self, project: Path, run_capture: Callable[[], None]) -> None:
        run_capture()
        (project / ".mz" / "memory" / ".last-capture").unlink()
        memory = _memory_file(project)
        text = memory.read_text(encoding="utf-8")
        memory.write_text(
            text.replace(f"{LOG_START}\n", f"{LOG_START}\n- [2026-10-01] task_a (phase=done)\n"),
            encoding="utf-8",
        )

    @pytest.mark.usefixtures("seeded_log")
    def test_first_run_skips_tasks_already_logged(
        self, project: Path, write_task: TaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_task("task_a", "complete")

        run_capture()

        assert _logged_tasks(project) == ["task_a"]

    def test_first_run_only_parses_most_recent_tasks(
        self, project: Path, write_task: TaskWriter, run_capture: Callable[[], None]
    ) -> None:
        for index in range(60):
            state_file = write_task(f"task_{index:03d}", "complete")
            os.utime(state_file, (1_700_000_000 + index, 1_700_000_000 + index))

        run_capture()

        logged = _logged_tasks(project)
        assert len(logged) == 50
        assert "task_059" in logged
        assert "task_009" not in logged

    @pytest.mark.usefixtures("seeded_log")
    def test_name_prefix_match_does_not_count_as_logged(
        self, project: Path, write_task: TaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_task("task_a_v2", "complete")

        run_capture()

        assert sorted(_logged_tasks(project)) == ["task_a", "task_a_v2"]


class TestMalformedState:
    def test_file_without_status_does_not_stop_other_captures(
        self,
        project: Path,
        write_task: TaskWriter,
        write_raw_task: RawTaskWriter,
        run_capture: Callable[[], None],
    ) -> None:
        write_raw_task("2026_11_01_build_draft", "schema_version: 2\nPhase: 1\n")
        write_task("2026_11_01_debug_crash", "complete")

        run_capture()

        assert _logged_tasks(project) == ["2026_11_01_debug_crash"]

    def test_complete_file_without_phase_is_logged_without_phase(
        self, project: Path, write_raw_task: RawTaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_raw_task("2026_11_01_audit_api", "schema_version: 2\nStatus: complete\n")

        run_capture()

        assert _logged_tasks(project) == ["2026_11_01_audit_api"]
        assert "(phase=" not in _memory_file(project).read_text(encoding="utf-8")

    def test_bold_status_line_is_skipped(
        self,
        project: Path,
        write_task: TaskWriter,
        write_raw_task: RawTaskWriter,
        run_capture: Callable[[], None],
    ) -> None:
        write_raw_task("2026_11_01_polish_ui", "**Status:** complete\n**Phase:** 4\n")
        write_task("2026_11_01_debug_crash", "complete")

        run_capture()

        assert _logged_tasks(project) == ["2026_11_01_debug_crash"]

    def test_marker_advances_past_a_malformed_file(
        self,
        project: Path,
        write_task: TaskWriter,
        write_raw_task: RawTaskWriter,
        run_capture: Callable[[], None],
        mark_changed_since_capture: MarkChanged,
    ) -> None:
        write_raw_task("2026_11_01_build_draft", "schema_version: 2\nPhase: 1\n")
        run_capture()
        finished = write_task("2026_11_02_debug_crash", "complete")
        mark_changed_since_capture(finished)

        run_capture()

        assert _logged_tasks(project) == ["2026_11_02_debug_crash"]

    def test_long_decisions_section_is_cut_to_ten_lines(
        self, project: Path, write_task: TaskWriter, run_capture: Callable[[], None]
    ) -> None:
        # Enough output to overflow the pipe buffer after head exits, so awk gets SIGPIPE.
        decisions = "".join(f"- decision number {index}\n" for index in range(20_000))
        write_task("2026_11_01_build_auth", "complete", f"\n## Decisions\n\n{decisions}")

        run_capture()

        memory_text = _memory_file(project).read_text(encoding="utf-8")
        assert "decision number 9\n" in memory_text
        assert "decision number 10\n" not in memory_text


class TestPrivacy:
    def test_private_regions_are_stripped(
        self, project: Path, write_task: TaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_task(
            "2026_11_01_outreach_acme",
            "complete",
            "\n## Decisions\n\n- contact <private>jane@acme.test</private> first\n",
        )

        run_capture()

        memory_text = _memory_file(project).read_text(encoding="utf-8")
        assert "jane@acme.test" not in memory_text
        assert "contact first" in memory_text


class TestPruning:
    def test_log_is_pruned_to_its_line_cap(
        self,
        project: Path,
        capture_env: dict[str, str],
        write_task: TaskWriter,
        run_capture: Callable[[], None],
        capture_runner: CaptureRunner,
    ) -> None:
        _seed_log(project, capture_runner, capture_env, _entries(MAX_LOG_LINES + 50))
        write_task("2026_11_02_build_auth", "complete")

        run_capture()

        log = _log_region(project)
        assert len(log) == MAX_LOG_LINES
        assert "2026_11_02_build_auth" in log[0]


class TestBackgroundCompression:
    @pytest.fixture
    def compress_env(self, project: Path, capture_env: dict[str, str]) -> dict[str, str]:
        """Capture env with a stub `claude` first on PATH, so the compressor never calls the CLI."""
        bin_dir = project / "bin"
        bin_dir.mkdir()
        stub = bin_dir / "claude"
        summary = "## Recurring decisions\n- [2026-10-01] summarized older work"
        stub.write_text(
            f"#!/usr/bin/env bash\ncat >/dev/null\nprintf '%s' {shlex.quote(summary)}\n"
        )
        stub.chmod(0o755)
        return {**capture_env, "PATH": f"{bin_dir}{os.pathsep}{capture_env['PATH']}"}

    @staticmethod
    def _compression_finished(project: Path) -> bool:
        lock = project / ".mz" / "memory" / ".compress.lock"
        return COMPRESSED_MARK in _log_region(project) and not lock.exists()

    def test_log_past_the_threshold_is_compressed_by_default(
        self,
        project: Path,
        write_task: TaskWriter,
        compress_env: dict[str, str],
        capture_runner: CaptureRunner,
    ) -> None:
        # Entries with Decisions span several lines, so 120 entries already pass the line threshold.
        _seed_log(project, capture_runner, compress_env, _entries(120, extra_lines=2))
        write_task("2026_11_02_build_auth", "complete")

        capture_runner(compress_env)

        assert _wait_until(lambda: self._compression_finished(project), seconds=15)
        assert len(_log_region(project)) <= COMPRESS_THRESHOLD

    def test_opt_out_leaves_a_long_log_uncompressed(
        self,
        project: Path,
        write_task: TaskWriter,
        compress_env: dict[str, str],
        capture_runner: CaptureRunner,
    ) -> None:
        _seed_log(project, capture_runner, compress_env, _entries(COMPRESS_THRESHOLD + 50))
        write_task("2026_11_02_build_auth", "complete")

        capture_runner({**compress_env, "MZ_MEMORY_COMPRESS": "0"})

        assert not _wait_until(lambda: self._compression_finished(project), seconds=1.5)
        assert COMPRESSED_MARK not in _log_region(project)
