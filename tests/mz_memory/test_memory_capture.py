import json
import os
import shlex
import shutil
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pytest

LOG_START = "<!-- mz-log-start -->"
LOG_END = "<!-- mz-log-end -->"
MAX_LOG_LINES = 400
COMPRESS_THRESHOLD = 300
# Every external command capture may run; each gets a counting shim on an otherwise empty PATH.
COUNTED_TOOLS = (
    "awk",
    "basename",
    "cat",
    "cp",
    "cut",
    "date",
    "dirname",
    "find",
    "flock",
    "git",
    "grep",
    "head",
    "ls",
    "mkdir",
    "mktemp",
    "mv",
    "perl",
    "rm",
    "rmdir",
    "sed",
    "sort",
    "tail",
    "touch",
    "tr",
    "wc",
)

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

    @pytest.mark.skipif(os.geteuid() == 0, reason="root reads files whatever their mode")
    def test_unreadable_file_is_skipped(
        self, project: Path, write_task: TaskWriter, run_capture: Callable[[], None]
    ) -> None:
        write_task("2026_11_01_a_locked", "complete").chmod(0)
        write_task("2026_11_01_b_done", "complete")

        run_capture()

        assert _logged_tasks(project) == ["2026_11_01_b_done"]

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
        reply = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "structured_output": {"operations": []},
            }
        )
        stub.write_text(f"#!/usr/bin/env bash\ncat >/dev/null\nprintf '%s' {shlex.quote(reply)}\n")
        stub.chmod(0o755)
        return {**capture_env, "PATH": f"{bin_dir}{os.pathsep}{capture_env['PATH']}"}

    @staticmethod
    def _compression_finished(project: Path) -> bool:
        memory_dir = project / ".mz" / "memory"
        return (memory_dir / "activity.archive.md").exists() and not (
            memory_dir / ".compress.lock"
        ).exists()

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
        assert len(_log_region(project)) > COMPRESS_THRESHOLD


class TestOnePass:
    def test_status_and_phase_stay_with_their_own_file(
        self,
        project: Path,
        write_task: TaskWriter,
        write_raw_task: RawTaskWriter,
        run_capture: Callable[[], None],
    ) -> None:
        write_task("2026_11_01_a_done", "complete")
        write_raw_task("2026_11_01_b_draft", "schema_version: 2\n")
        write_raw_task("2026_11_01_c_done", "Status: complete\n")

        run_capture()

        assert _logged_tasks(project) == ["2026_11_01_a_done", "2026_11_01_c_done"]
        # A phase carried over from a_done would end the line with "(phase=3)".
        assert _log_region(project)[-1].endswith(" 2026_11_01_c_done")

    def test_a_decisions_section_open_at_the_end_of_one_file_stops_there(
        self,
        project: Path,
        write_task: TaskWriter,
        write_raw_task: RawTaskWriter,
        run_capture: Callable[[], None],
    ) -> None:
        write_task("2026_11_01_a_done", "complete", "\n## Decisions\n- the last line of a")
        write_raw_task("2026_11_01_b_done", "- a bullet before any heading\nStatus: complete\n")

        run_capture()

        log = _log_region(project)
        assert " - the last line of a" in log
        assert not any("a bullet before any heading" in line for line in log)


class TestAgentBridge:
    @pytest.fixture
    def agent_memory(self, project: Path) -> Path:
        agents = project / ".claude" / "agent-memory"
        (agents / "reviewer").mkdir(parents=True)
        (agents / "planner").mkdir()
        return agents

    def test_a_finished_task_reaches_each_agent_it_mentions(
        self,
        agent_memory: Path,
        write_task: TaskWriter,
        run_capture: Callable[[], None],
    ) -> None:
        write_task("2026_11_01_build_auth", "complete", "\nReviewed by [Reviewer].\n")

        run_capture()

        reviewer = (agent_memory / "reviewer" / "MEMORY.md").read_text(encoding="utf-8")
        assert reviewer.startswith("# reviewer memory\n\n- [")
        assert reviewer.rstrip().endswith(" 2026_11_01_build_auth (phase=3)")
        assert not (agent_memory / "planner" / "MEMORY.md").exists()

    def test_an_unfinished_task_reaches_no_agent(
        self,
        agent_memory: Path,
        write_task: TaskWriter,
        run_capture: Callable[[], None],
    ) -> None:
        write_task("2026_11_01_build_auth", "running", "\nReviewed by [reviewer].\n")

        run_capture()

        assert not (agent_memory / "reviewer" / "MEMORY.md").exists()


class TestCaptureCost:
    @pytest.fixture
    def counted_capture(
        self, tmp_path: Path, capture_env: dict[str, str], capture_runner: CaptureRunner
    ) -> Callable[[], Counter[str]]:
        """Run capture with every external command behind a shim that records its name."""
        bin_dir = tmp_path / "counting-bin"
        bin_dir.mkdir()
        calls = tmp_path / "calls.log"
        bash = shutil.which("bash")
        assert bash is not None
        (bin_dir / "bash").symlink_to(bash)
        for tool in COUNTED_TOOLS:
            real = shutil.which(tool)
            if real is None:
                continue
            shim = bin_dir / tool
            shim.write_text(
                f"#!{bash}\nprintf '%s\\n' {tool} >>{shlex.quote(str(calls))}\n"
                f'exec {shlex.quote(real)} "$@"\n',
                encoding="utf-8",
            )
            shim.chmod(0o755)
        env = {**capture_env, "PATH": str(bin_dir), "MZ_MEMORY_COMPRESS": "0"}

        def run() -> Counter[str]:
            calls.write_text("", encoding="utf-8")
            capture_runner(env)
            return Counter(calls.read_text(encoding="utf-8").split())

        return run

    def test_external_commands_do_not_grow_with_the_number_of_tasks(
        self,
        project: Path,
        write_task: TaskWriter,
        counted_capture: Callable[[], Counter[str]],
    ) -> None:
        # SessionEnd hooks share 1.5 s; a few forks per task pushed a 50-task first run past it.
        (project / ".claude" / "agent-memory" / "reviewer").mkdir(parents=True)
        body = (
            "\n## Decisions\n- chose A\n\n## Lessons\n- (review) WHEN x → y — WHY z\n[reviewer]\n"
        )

        def first_run_with(count: int) -> Counter[str]:
            shutil.rmtree(project / ".mz" / "memory", ignore_errors=True)
            for index in range(count):
                write_task(f"2026_11_01_build_{index:03d}", "complete", body)
            return counted_capture()

        few, many = first_run_with(5), first_run_with(40)

        assert len(_logged_tasks(project)) == 40
        assert many == few
