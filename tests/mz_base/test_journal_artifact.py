import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins/mz-base/shared/journal-artifact.sh"
SH = shutil.which("sh") or "/bin/sh"

type Run = Callable[..., subprocess.CompletedProcess[str]]

pytestmark = pytest.mark.skipif(shutil.which("perl") is None, reason="perl is not installed")


@pytest.fixture
def run(tmp_path: Path) -> Run:
    def run_script(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [SH, str(SCRIPT), *args],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    return run_script


@pytest.fixture
def journal(tmp_path: Path) -> Path:
    path = tmp_path / ".mz" / "journal.md"
    path.parent.mkdir()
    path.write_text("- artifact: plan.md, verbatim:\n\n", encoding="utf-8")
    return path


class TestAppend:
    def test_redacts_private_spans_and_indents_under_the_bullet(
        self, run: Run, tmp_path: Path, journal: Path
    ) -> None:
        artifact = tmp_path / "plan.md"
        artifact.write_text(
            "# Plan\n\nkey <private>sk-1</private> and <private>multi\nline</private> end\n",
            encoding="utf-8",
        )

        result = run(str(artifact), str(journal))

        assert result.returncode == 0, result.stderr
        assert journal.read_text(encoding="utf-8") == (
            "- artifact: plan.md, verbatim:\n\n  # Plan\n\n  key [redacted] and [redacted] end\n\n"
        )

    def test_keeps_percent_and_backslash_verbatim(
        self, run: Run, tmp_path: Path, journal: Path
    ) -> None:
        artifact = tmp_path / "plan.md"
        artifact.write_text("100% done\\n\n", encoding="utf-8")

        run(str(artifact), str(journal))

        assert journal.read_text(encoding="utf-8").endswith("  100% done\\n\n\n")


class TestUsageErrors:
    @pytest.mark.parametrize(
        "args",
        [
            pytest.param(("only-one",), id="missing-journal-argument"),
            pytest.param(("missing.md", "journal.md"), id="unreadable-artifact"),
            pytest.param((".", "journal.md"), id="artifact-is-a-folder"),
        ],
    )
    def test_exits_2_and_writes_nothing(
        self, run: Run, tmp_path: Path, args: tuple[str, ...]
    ) -> None:
        result = run(*args)

        assert result.returncode == 2
        assert result.stderr
        assert not (tmp_path / "journal.md").exists()

    def test_refuses_a_journal_folder_that_does_not_exist(self, run: Run, tmp_path: Path) -> None:
        artifact = tmp_path / "plan.md"
        artifact.write_text("text\n", encoding="utf-8")

        result = run(str(artifact), str(tmp_path / "absent" / "journal.md"))

        assert result.returncode == 2
        assert "mkdir -p" in result.stderr
