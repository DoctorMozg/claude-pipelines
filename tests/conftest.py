import shutil
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest

type PathWithoutJq = Callable[[Iterable[str]], str]


@pytest.fixture
def path_without_jq(tmp_path: Path) -> PathWithoutJq:
    """Build a PATH holding only the named tools, so a hook sees no jq."""

    def build(tools: Iterable[str]) -> str:
        bin_dir = tmp_path / "bin-without-jq"
        bin_dir.mkdir(exist_ok=True)
        for tool in tools:
            if tool == "jq":
                raise ValueError("path_without_jq must not be given jq")
            located = shutil.which(tool)
            assert located is not None, f"{tool} is not installed"
            link = bin_dir / tool
            if not link.exists():
                link.symlink_to(located)
        return str(bin_dir)

    return build
