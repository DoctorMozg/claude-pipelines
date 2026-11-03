import filecmp
from pathlib import Path

import pytest

from .conftest import PLUGINS_DIR

SOURCE = PLUGINS_DIR / "mz-base" / "shared"
COPIES = sorted(path for path in PLUGINS_DIR.glob("*/shared") if path != SOURCE)


def _relative_files(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


class TestSharedCopies:
    def test_plugin_folders_hold_no_symlinks(self) -> None:
        # Anthropic's directory blocks a plugin that loads a symlink, so consumers get real copies.
        links = sorted(path.relative_to(PLUGINS_DIR).as_posix() for path in PLUGINS_DIR.rglob("*") if path.is_symlink())
        assert links == [], "replace each link with `make vendor-shared`"

    def test_some_plugin_consumes_shared(self) -> None:
        assert COPIES, "no plugin carries a copy of mz-base/shared"

    @pytest.mark.parametrize("copy", COPIES, ids=lambda path: path.parent.name)
    def test_copy_matches_mz_base(self, copy: Path) -> None:
        source_files = _relative_files(SOURCE)
        assert _relative_files(copy) == source_files, "run `make vendor-shared`"
        drifted = sorted(name for name in source_files if not filecmp.cmp(SOURCE / name, copy / name, shallow=False))
        assert drifted == [], f"{copy.parent.name} has stale copies; run `make vendor-shared`"
