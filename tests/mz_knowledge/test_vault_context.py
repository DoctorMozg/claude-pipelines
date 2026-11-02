import json
import os
import shutil
import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "plugins/mz-knowledge/scripts/vault-context.sh"
BASH = shutil.which("bash") or "/bin/bash"
MOC_DIR = "00 - MOCs"
# Everything the script runs except jq, so a PATH built from these hides jq only.
TOOLS_WITHOUT_JQ = ("date", "find", "sort", "head", "xargs", "ls")

type RunHook = Callable[..., str]


def _note(path: Path, mtime: float | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# note\n", encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _context(stdout: str) -> str:
    output = json.loads(stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    context: str = output["hookSpecificOutput"]["additionalContext"]
    return context


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    root.mkdir()
    return root


@pytest.fixture
def run_hook(tmp_path: Path, vault: Path) -> RunHook:
    base_env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"OBSIDIAN_VAULT_PATH", "MZ_VAULT_PATH"}
    }
    workdir = tmp_path / "cwd"
    workdir.mkdir()

    def run(path: str = "", env: dict[str, str] | None = None) -> str:
        overrides = {"OBSIDIAN_VAULT_PATH": str(vault)} if env is None else env
        result = subprocess.run(
            [BASH, str(SCRIPT)],
            input='{"hook_event_name":"SessionStart","source":"startup"}',
            env={**base_env, **overrides, **({"PATH": path} if path else {})},
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout

    return run


class TestSilentExits:
    def test_unset_vault_prints_nothing(self, run_hook: RunHook) -> None:
        assert run_hook(env={}) == ""

    def test_missing_vault_directory_prints_nothing(self, run_hook: RunHook, vault: Path) -> None:
        assert run_hook(env={"OBSIDIAN_VAULT_PATH": str(vault / "absent")}) == ""

    def test_vault_without_notes_prints_nothing(self, run_hook: RunHook, tmp_path: Path) -> None:
        # An empty find result must not make xargs list the working directory instead.
        _note(tmp_path / "cwd" / "stray.md")

        assert run_hook() == ""

    def test_missing_jq_prints_nothing(
        self, run_hook: RunHook, vault: Path, tmp_path: Path
    ) -> None:
        _note(vault / "daily" / f"{date.today():%Y-%m-%d}.md")
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        for tool in TOOLS_WITHOUT_JQ:
            located = shutil.which(tool)
            assert located is not None, tool
            (bin_dir / tool).symlink_to(located)

        assert run_hook(path=str(bin_dir)) == ""


class TestContext:
    def test_sections_are_separate_lines_in_order(self, run_hook: RunHook, vault: Path) -> None:
        today = f"{date.today():%Y-%m-%d}"
        _note(vault / "daily" / f"{today}.md", mtime=1_000)
        _note(vault / MOC_DIR / "Projects.md", mtime=2_000)
        _note(vault / MOC_DIR / "Areas.md", mtime=3_000)

        assert _context(run_hook()) == (
            f"Today's daily note: {today}.md\n"
            "Vault MOCs: Areas, Projects\n"
            f"Recently modified: Areas, Projects, {today}"
        )

    def test_names_with_shell_and_json_metacharacters_pass_through(
        self, run_hook: RunHook, vault: Path
    ) -> None:
        name = 'Q3 "plan" \\ $HOME `id`'
        _note(vault / MOC_DIR / f"{name}.md")

        assert f"Vault MOCs: {name}" in _context(run_hook())

    def test_moc_list_is_sorted_and_capped_at_twenty(self, run_hook: RunHook, vault: Path) -> None:
        for index in range(25, 0, -1):
            _note(vault / MOC_DIR / f"moc-{index:02d}.md")

        moc_line = _context(run_hook()).splitlines()[0]

        assert moc_line == "Vault MOCs: " + ", ".join(f"moc-{i:02d}" for i in range(1, 21))

    def test_recent_notes_are_newest_three_without_hidden_or_obsidian_files(
        self, run_hook: RunHook, vault: Path
    ) -> None:
        for index in range(1, 6):
            _note(vault / "notes" / f"note-{index}.md", mtime=1_000 * index)
        _note(vault / ".obsidian" / "workspace.md", mtime=9_000)
        _note(vault / "notes" / ".draft.md", mtime=9_000)

        assert _context(run_hook()) == "Recently modified: note-5, note-4, note-3"

    def test_mz_vault_path_is_the_fallback(self, run_hook: RunHook, vault: Path) -> None:
        _note(vault / "notes" / "only.md")

        assert _context(run_hook(env={"MZ_VAULT_PATH": str(vault)})) == "Recently modified: only"

    def test_obsidian_vault_path_wins_over_fallback(
        self, run_hook: RunHook, vault: Path, tmp_path: Path
    ) -> None:
        _note(vault / "notes" / "primary.md")
        other = tmp_path / "other"
        _note(other / "notes" / "secondary.md")

        context = _context(
            run_hook(env={"OBSIDIAN_VAULT_PATH": str(vault), "MZ_VAULT_PATH": str(other)})
        )

        assert context == "Recently modified: primary"
