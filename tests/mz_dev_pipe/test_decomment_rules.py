"""The decomment proposer's line-window rules match the skill's scan constants."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_PIPE = REPO_ROOT / "plugins" / "mz-dev-pipe"
SKILL = DEV_PIPE / "skills" / "decomment" / "SKILL.md"
PROPOSER = DEV_PIPE / "agents" / "pipeline-decomment-proposer.md"
# Each scan constant bounds one kind of marker; a window rule must name its marker right after it.
WINDOW_MARKERS = {"LICENSE_HEADER_SCAN_LINES": "license", "CODEGEN_CONTENT_SCAN_LINES": "generated"}
WINDOW = re.compile(r"first (?P<lines>\d+) lines", re.IGNORECASE)
MARKER_REACH = 100


def skill_constant(name: str) -> int:
    match = re.search(rf"^\| `{name}`\s*\|\s*(\d+)\s*\|", SKILL.read_text(encoding="utf-8"), re.M)
    assert match is not None, f"{SKILL.name} has no {name} row in its constants table"
    return int(match.group(1))


@pytest.fixture(scope="module")
def marker_by_window() -> dict[int, str]:
    return {skill_constant(name): marker for name, marker in WINDOW_MARKERS.items()}


@pytest.fixture(scope="module")
def windows() -> list[tuple[int, str]]:
    """Each 'first N lines' rule in the proposer, with the text that follows it."""
    text = PROPOSER.read_text(encoding="utf-8")
    return [
        (int(m["lines"]), text[m.end() : m.end() + MARKER_REACH].lower())
        for m in WINDOW.finditer(text)
    ]


class TestScanWindows:
    def test_every_window_is_a_skill_constant(
        self, windows: list[tuple[int, str]], marker_by_window: dict[int, str]
    ) -> None:
        assert {lines for lines, _ in windows} <= set(marker_by_window)

    def test_every_window_names_its_marker(
        self, windows: list[tuple[int, str]], marker_by_window: dict[int, str]
    ) -> None:
        # A bare "first 30 lines" rule would preserve every comment in a short file.
        stray = [
            f"first {lines} lines{after[:60]}"
            for lines, after in windows
            if marker_by_window.get(lines, "") not in after
        ]
        assert stray == []

    def test_both_scans_are_still_described(
        self, windows: list[tuple[int, str]], marker_by_window: dict[int, str]
    ) -> None:
        assert {lines for lines, _ in windows} == set(marker_by_window)
