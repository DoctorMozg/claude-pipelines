import re

import pytest

from .conftest import PLUGINS_DIR, REPO_ROOT, PluginFile, assert_no_violations

STATE_SCHEMA = REPO_ROOT / "guidelines" / "STATE_SCHEMA.md"
SHARED_SCHEMA = PLUGINS_DIR / "mz-base" / "shared" / "state-schema.md"
CONTRACT_START = "State persists to `.mz/task/"
LESSONS_SENTENCE = re.compile(
    r"Under a heading that reads exactly `## Lessons`.*?whatever the `Status`\."
)
SYNC_HINT = "copy the matching block from guidelines/STATE_SCHEMA.md §9 in the same commit"


def _contract_lines(text: str) -> list[str]:
    lines = (line.removeprefix("> ") for line in text.splitlines())
    return [line for line in lines if line.startswith(CONTRACT_START)]


@pytest.fixture(scope="module")
def canonical_blocks() -> tuple[str, ...]:
    blocks = tuple(_contract_lines(STATE_SCHEMA.read_text(encoding="utf-8")))
    assert len(blocks) == 2, (
        f"{STATE_SCHEMA}: expected the multi-phase and single-dispatch blocks, found {len(blocks)}"
    )
    return blocks


@pytest.fixture(scope="module")
def lessons_sentences(canonical_blocks: tuple[str, ...]) -> frozenset[str]:
    found = [LESSONS_SENTENCE.search(block) for block in canonical_blocks]
    assert all(found), f"{STATE_SCHEMA}: every §9 block must carry a `## Lessons` sentence"
    return frozenset(match[0] for match in found if match)


class TestStateContract:
    def test_shared_copy_matches_the_guideline(self, canonical_blocks: tuple[str, ...]) -> None:
        shared = tuple(_contract_lines(SHARED_SCHEMA.read_text(encoding="utf-8")))
        assert shared == canonical_blocks, (
            f"{SHARED_SCHEMA.relative_to(REPO_ROOT)}: §9 blocks drifted; {SYNC_HINT}"
        )

    def test_inline_contracts_start_with_a_canonical_block(
        self, plugin_files: tuple[PluginFile, ...], canonical_blocks: tuple[str, ...]
    ) -> None:
        # Skill-specific sentences may follow the block, never replace or interrupt it.
        violations = [
            f"{source.relative}: contract paragraph drifted; {SYNC_HINT}"
            for source in plugin_files
            for line in _contract_lines(source.text)
            if not any(line == block or line.startswith(block + " ") for block in canonical_blocks)
        ]
        assert_no_violations(violations)

    def test_state_keeping_skills_ask_for_lessons(
        self, plugin_files: tuple[PluginFile, ...], lessons_sentences: frozenset[str]
    ) -> None:
        # Skills that point to shared/state-schema.md still need the sentence in SKILL.md itself.
        violations = [
            f"{source.relative}: writes state.md without a `## Lessons` sentence from §9"
            for source in plugin_files
            if source.path.name == "SKILL.md"
            and "schema_version: 2" in source.text
            and not any(sentence in source.text for sentence in lessons_sentences)
        ]
        assert_no_violations(violations)


class TestHelpers:
    def test_contract_lines_strip_quote_markers(self) -> None:
        text = f"> {CONTRACT_START}x.\n{CONTRACT_START}y.\nState persists elsewhere.\n"
        assert _contract_lines(text) == [f"{CONTRACT_START}x.", f"{CONTRACT_START}y."]

    def test_lessons_pattern_stops_at_the_first_status_clause(self) -> None:
        text = (
            "a. Under a heading that reads exactly `## Lessons`, add one line; "
            "mz-memory harvests lessons whatever the `Status`. Then whatever the `Status`."
        )
        match = LESSONS_SENTENCE.search(text)
        assert match is not None
        assert match[0].endswith("harvests lessons whatever the `Status`.")
