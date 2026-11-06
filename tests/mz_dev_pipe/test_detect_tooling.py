import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins/mz-dev-pipe/scripts/detect-tooling.sh"
COMMON_LIB = REPO_ROOT / "plugins/mz-memory/scripts/lib/common.sh"
HANDOFF_LIB = REPO_ROOT / "plugins/mz-handoff/scripts/lib/handoff.sh"
BASH = shutil.which("bash") or "/bin/bash"
FIND_ROOT_BODY = re.compile(r"^find_project_root\(\) \{\n.*?^\}$", re.S | re.M)

type RunHook = Callable[..., str]


def _tooling(root: Path) -> dict[str, object]:
    text = (root / ".mz" / "tooling.json").read_text(encoding="utf-8")
    data: dict[str, object] = json.loads(text)
    return data


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (root / "sub").mkdir()
    return root


@pytest.fixture
def run_hook() -> RunHook:
    base_env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"MZ_MEMORY_ROOT", "CLAUDE_PROJECT_DIR"}
    }

    def run(start: Path, **env: str) -> str:
        result = subprocess.run(
            [BASH, str(SCRIPT)],
            input='{"hook_event_name":"SessionStart","source":"startup"}',
            env={**base_env, "CLAUDE_PROJECT_DIR": str(start), **env},
            cwd=start,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout

    return run


class TestProjectRoot:
    def test_memory_root_override_wins(self, run_hook: RunHook, repo: Path, tmp_path: Path) -> None:
        override = tmp_path / "override"
        override.mkdir()

        run_hook(repo / "sub", MZ_MEMORY_ROOT=str(override))

        assert (override / ".mz" / "tooling.json").is_file()
        assert not (repo / ".mz").exists()

    def test_subdirectory_launch_writes_at_repo_root(self, run_hook: RunHook, repo: Path) -> None:
        run_hook(repo / "sub")

        assert (repo / ".mz" / "tooling.json").is_file()
        assert not (repo / "sub" / ".mz").exists()

    def test_no_git_falls_back_to_start_directory(self, run_hook: RunHook, tmp_path: Path) -> None:
        plain = tmp_path / "plain" / "deeper"
        plain.mkdir(parents=True)

        run_hook(plain)

        assert (plain / ".mz" / "tooling.json").is_file()

    def test_git_file_of_a_worktree_counts(self, run_hook: RunHook, tmp_path: Path) -> None:
        worktree = tmp_path / "worktree"
        (worktree / "nested").mkdir(parents=True)
        (worktree / ".git").write_text("gitdir: /elsewhere/.git/worktrees/wt\n", encoding="utf-8")

        run_hook(worktree / "nested")

        assert (worktree / ".mz" / "tooling.json").is_file()


class TestOutput:
    def test_tooling_json_parses_and_finds_python(self, run_hook: RunHook, repo: Path) -> None:
        run_hook(repo)

        ecosystems = _tooling(repo)["ecosystems"]
        assert isinstance(ecosystems, dict)
        assert "python" in ecosystems

    def test_context_names_the_absolute_cache_path(self, run_hook: RunHook, repo: Path) -> None:
        output = json.loads(run_hook(repo / "sub"))

        context = output["hookSpecificOutput"]["additionalContext"]
        assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        assert context.endswith(f"Full details in {repo / '.mz' / 'tooling.json'}")


@contextmanager
def read_only(*paths: Path) -> Iterator[None]:
    """Strip write permission from `paths` for the block and restore it even if the block fails."""
    modes = {path: path.stat().st_mode for path in paths}
    for path in paths:
        path.chmod(0o555 if path.is_dir() else 0o444)
    try:
        yield
    finally:
        for path, mode in modes.items():
            path.chmod(mode)


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes whatever the mode")
class TestUnwritableProject:
    def test_uncreatable_cache_dir_exits_zero_without_context(
        self, run_hook: RunHook, repo: Path
    ) -> None:
        with read_only(repo):
            output = run_hook(repo)

        assert output == ""
        assert not (repo / ".mz").exists()

    def test_read_only_cache_is_left_as_it_was(self, run_hook: RunHook, repo: Path) -> None:
        run_hook(repo)
        cache = repo / ".mz" / "tooling.json"
        before = cache.read_text(encoding="utf-8")

        with read_only(cache, cache.parent):
            output = run_hook(repo)

        assert output == ""
        assert cache.read_text(encoding="utf-8") == before


class TestCopyStaysInSync:
    # mz-memory's copy is the original; the others must resolve the same .mz/ root.
    @pytest.mark.parametrize("copy", [SCRIPT, HANDOFF_LIB], ids=["mz-dev-pipe", "mz-handoff"])
    def test_find_project_root_matches_mz_memory_copy(self, copy: Path) -> None:
        other_copy = FIND_ROOT_BODY.search(copy.read_text(encoding="utf-8"))
        library_copy = FIND_ROOT_BODY.search(COMMON_LIB.read_text(encoding="utf-8"))

        assert other_copy is not None
        assert library_copy is not None
        assert other_copy.group(0) == library_copy.group(0)
