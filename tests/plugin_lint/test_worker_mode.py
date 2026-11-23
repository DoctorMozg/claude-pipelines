import re
from pathlib import Path

import pytest

from .conftest import PLUGINS_DIR
from .dispatch_scan import find_dispatches

ORCHESTRATE = PLUGINS_DIR / "mz-orchestrate"
WORKER_MODE = PLUGINS_DIR / "mz-base/shared/worker-mode.md"
UNIT_RUNNER = ORCHESTRATE / "agents/orchestrate-unit-runner.md"
AGENTS = frozenset(path.stem for path in PLUGINS_DIR.glob("*/agents/*.md"))
SKILL_REF = re.compile(r"\b(?P<plugin>mz-[a-z-]+):(?P<skill>[a-z][a-z0-9-]+)")


def _unit_skills() -> dict[str, Path]:
    """Every other plugin's skill that mz-orchestrate names, which a unit may therefore run."""
    found: dict[str, Path] = {}
    for path in ORCHESTRATE.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".sh", ".json"}:
            continue
        for match in SKILL_REF.finditer(path.read_text("utf-8")):
            skill_md = PLUGINS_DIR / match["plugin"] / "skills" / match["skill"] / "SKILL.md"
            if match["plugin"] != "mz-orchestrate" and skill_md.is_file():
                found[match[0]] = skill_md
    return found


UNIT_SKILLS = _unit_skills()


def test_mz_orchestrate_names_unit_skills() -> None:
    # Guards the scan itself: an empty set would pass every check below.
    assert {"mz-dev-pipe:build", "mz-dev-git:review-branch"} <= UNIT_SKILLS.keys()


@pytest.mark.parametrize("ref", sorted(UNIT_SKILLS))
def test_every_unit_skill_supports_worker_mode(ref: str) -> None:
    body = UNIT_SKILLS[ref].read_text("utf-8")
    skill = ref.split(":", 1)[1]

    assert "`unit:<path>`" in body, f"{ref} is a unit skill but takes no `unit:<path>` argument"
    assert "shared/worker-mode.md" in body, f"{ref} doesn't point to shared/worker-mode.md"
    assert f"`{skill}`" in WORKER_MODE.read_text("utf-8"), (
        f"{ref} is missing from the skill list in {WORKER_MODE.name}"
    )


def _runner_allowlist() -> set[str]:
    match = re.search(r"Agent\((?P<names>[^)]*)\)", UNIT_RUNNER.read_text("utf-8"))
    assert match, f"{UNIT_RUNNER.name} has no Agent(...) allowlist"
    return {name.strip() for name in match["names"].split(",")}


@pytest.mark.parametrize("ref", sorted(UNIT_SKILLS))
def test_the_unit_runner_may_dispatch_every_agent_of_a_unit_skill(ref: str) -> None:
    # A skill runs inside the runner's context, so it can dispatch only what the runner allows.
    skill_dir = UNIT_SKILLS[ref].parent
    dispatched = {
        found.name
        for path in skill_dir.rglob("*.md")
        for found in find_dispatches(path.read_text("utf-8"))
        if found.name in AGENTS
    }

    assert dispatched <= _runner_allowlist(), (
        f"{ref} dispatches {sorted(dispatched - _runner_allowlist())}, "
        f"missing from the Agent(...) allowlist in {UNIT_RUNNER.name}"
    )
