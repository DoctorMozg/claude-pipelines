from pathlib import Path

import pytest


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".mz" / "task").mkdir(parents=True)
    return tmp_path
