import json
from pathlib import Path

import pytest
import yaml

from .conftest import PLUGINS_DIR, REPO_ROOT

CASES = sorted((REPO_ROOT / "evals").glob("*/*/case.yaml"))


@pytest.fixture(scope="module")
def deps() -> dict[str, list[str]]:
    manifests = PLUGINS_DIR.glob("*/.claude-plugin/plugin.json")
    return {p.parents[1].name: json.loads(p.read_text()).get("dependencies", []) for p in manifests}


def _closure(plugin: str, deps: dict[str, list[str]]) -> set[str]:
    found: set[str] = set()
    todo = list(deps.get(plugin, []))
    while todo:
        name = todo.pop()
        if name not in found:
            found.add(name)
            todo.extend(deps.get(name, []))
    return found


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.parent.name)
def test_a_case_loads_every_dependency_of_its_plugins(
    case: Path, deps: dict[str, list[str]]
) -> None:
    # Claude Code drops a plugin whose dependency isn't loaded, so its skills never appear.
    loaded = {Path(p).name for p in yaml.safe_load(case.read_text()).get("plugins", [])}
    missing = set().union(*(_closure(p, deps) for p in loaded)) - loaded

    assert not missing, (
        f"{case.relative_to(REPO_ROOT)} loads {sorted(loaded)} but not {sorted(missing)}"
    )
