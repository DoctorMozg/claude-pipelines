import os
import shlex
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from .memory_helpers import (
    BASH,
    CLAUDE_STUB,
    OPTIONAL_TOOLS,
    SANDBOX_TOOLS,
    SCRIPTS,
    FakeCurator,
    RawTaskWriter,
    SeedLessons,
    TaskWriter,
    lessons_file,
    lessons_layout,
)

CAPTURE_SCRIPT = SCRIPTS / "memory-capture.sh"

type CaptureRunner = Callable[[dict[str, str]], None]


def _state_text(status: str, extra: str) -> str:
    return (
        "schema_version: 2\n"
        f"Status: {status}\n"
        "Phase: 3\n"
        "Started: 2026-11-01\n"
        "FilesWritten: []\n"
        "phase_complete: true\n"
        "what_remains: []\n"
        f"{extra}"
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".mz" / "task").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def write_raw_task(project: Path) -> RawTaskWriter:
    def write(name: str, text: str) -> Path:
        state_file = project / ".mz" / "task" / name / "state.md"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(text, encoding="utf-8")
        return state_file

    return write


@pytest.fixture
def write_task(write_raw_task: RawTaskWriter) -> TaskWriter:
    def write(name: str, status: str, extra: str = "") -> Path:
        return write_raw_task(name, _state_text(status, extra))

    return write


@pytest.fixture
def mark_changed_since_capture(project: Path) -> Callable[[Path], None]:
    """Push a state file's mtime past the capture marker, so the next capture reads it again."""

    def mark(state_file: Path) -> None:
        marker_mtime = (project / ".mz" / "memory" / ".last-capture").stat().st_mtime
        os.utime(state_file, (marker_mtime + 5, marker_mtime + 5))

    return mark


@pytest.fixture
def capture_env(project: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"MZ_MEMORY_COMPRESS", "CLAUDE_PROJECT_DIR"}
    }
    env["MZ_MEMORY_ROOT"] = str(project)
    return env


@pytest.fixture
def capture_runner() -> CaptureRunner:
    def run(env: dict[str, str]) -> None:
        result = subprocess.run(
            ["bash", str(CAPTURE_SCRIPT)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    return run


@pytest.fixture
def run_capture(capture_env: dict[str, str], capture_runner: CaptureRunner) -> Callable[[], None]:
    # Compression is on by default; switching it off keeps these tests from starting the real CLI.
    env = {**capture_env, "MZ_MEMORY_COMPRESS": "0"}
    return lambda: capture_runner(env)


@pytest.fixture
def seed_lessons(project: Path) -> SeedLessons:
    def write(curated: Sequence[str], inbox: Sequence[str] = ()) -> Path:
        path = lessons_file(project)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(lessons_layout(curated, inbox), encoding="utf-8")
        return path

    return write


@pytest.fixture
def bin_dir(tmp_path: Path) -> Path:
    """A PATH directory holding only the tools a background run needs."""
    directory = tmp_path / "bin"
    directory.mkdir()
    for tool in SANDBOX_TOOLS:
        located = shutil.which(tool)
        assert located is not None, f"{tool} is not installed"
        (directory / tool).symlink_to(located)
    for tool in OPTIONAL_TOOLS:
        located = shutil.which(tool)
        if located is not None:
            (directory / tool).symlink_to(located)
    return directory


@pytest.fixture
def curator(tmp_path: Path, bin_dir: Path) -> FakeCurator:
    record = tmp_path / "claude_record"
    record.mkdir()
    stub = bin_dir / "claude"
    stub.write_text(
        CLAUDE_STUB.format(bash=BASH, record=shlex.quote(str(record))), encoding="utf-8"
    )
    stub.chmod(0o755)
    fake = FakeCurator(record)
    fake.respond()
    return fake


@pytest.fixture
def date_shim(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A directory whose `date` prints $MZ_TEST_TODAY; put it first on PATH to pin the day."""
    directory = tmp_path_factory.mktemp("date_shim")
    shim = directory / "date"
    shim.write_text('#!/bin/sh\nprintf "%s\\n" "$MZ_TEST_TODAY"\n', encoding="utf-8")
    shim.chmod(0o755)
    return directory
