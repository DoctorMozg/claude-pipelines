import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = REPO_ROOT / "plugins/mz-biz-outreach"
STRATEGIST = PLUGIN / "agents/outreach-strategist.md"
ENRICH_SKILL_DIR = PLUGIN / "skills/outreach-enrich-company"
RESEARCH_DISCOVERY = PLUGIN / "skills/outreach-research/phases/discovery.md"
BRIEF_INTAKE = PLUGIN / "skills/outreach-brief/phases/intake.md"

FENCE = re.compile(r"^(`{3,}|~{3,})([^\n]*)\n(.*?)^\1[ \t]*$", re.S | re.M)
FIELD = r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*"
# A backticked field, optionally followed by "(or `other.path`)" naming where else it may live.
FIELD_WITH_ALTERNATIVE = re.compile(rf"`({FIELD})`(?:\s*\(or\s+`({FIELD})`\))?")
DOTTED_STRATEGY_READ = re.compile(r"\bstrategy\.([a-z_][a-z0-9_]*)")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

type ReadGroup = tuple[str, ...]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _fences(text: str) -> list[tuple[str, str]]:
    return [(match.group(2).strip(), match.group(3)) for match in FENCE.finditer(text)]


def _section(text: str, heading: str) -> str:
    """Body under `heading` up to the next heading of the same or a higher level."""
    match = re.search(rf"^(#+) {re.escape(heading)}\s*$", text, re.M)
    assert match is not None, f"heading {heading!r} not found"
    level = len(match.group(1))
    rest = text[match.end() :]
    end = re.search(rf"^#{{1,{level}}} ", rest, re.M)
    return rest[: end.start()] if end else rest


def _first_json_fence(text: str) -> object:
    for info, body in _fences(text):
        if info == "json":
            parsed: object = json.loads(body)
            return parsed
    raise AssertionError("no json fence found")


def _key_paths(node: object, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}{key}"
            paths.add(path)
            paths |= _key_paths(value, f"{path}.")
    elif isinstance(node, list):
        for item in node:
            paths |= _key_paths(item, prefix)
    return paths


def _is_file_name(field: str) -> bool:
    return field.endswith((".json", ".md"))


def _strategy_reads(text: str) -> set[ReadGroup]:
    """Fields a markdown file says it reads from strategy.json, each with its alternative paths."""
    reads: set[ReadGroup] = set()
    reads |= {(field,) for field in DOTTED_STRATEGY_READ.findall(text) if field != "json"}
    prose = FENCE.sub("", text)
    for line in prose.splitlines():
        if "strategy.json" not in line:
            continue
        for sentence in SENTENCE_END.split(line):
            if not re.search(r"\bfields?\b", sentence):
                continue
            for match in FIELD_WITH_ALTERNATIVE.finditer(sentence):
                group = tuple(field for field in match.groups() if field)
                if not any(_is_file_name(field) for field in group):
                    reads.add(group)
    return reads


def _merge_overlapping(groups: set[ReadGroup]) -> list[ReadGroup]:
    """One group per field, so a path named as an alternative in one file counts for all files."""
    merged: list[set[str]] = []
    for group in groups:
        overlapping = [known for known in merged if known & set(group)]
        combined = set(group).union(*overlapping)
        merged = [known for known in merged if not known & set(group)] + [combined]
    return sorted(tuple(sorted(group)) for group in merged)


def _enrich_company_strategy_reads() -> list[ReadGroup]:
    reads: set[ReadGroup] = set()
    for path in sorted(ENRICH_SKILL_DIR.rglob("*.md")):
        reads |= _strategy_reads(_read(path))
    return _merge_overlapping(reads)


def _strategist_schema_paths() -> set[str]:
    return _key_paths(_first_json_fence(_section(_read(STRATEGIST), "Output Format")))


def _brief_voice_path() -> str:
    schema = _first_json_fence(_section(_read(BRIEF_INTAKE), "Assemble the artifacts"))
    voices = [path for path in _key_paths(schema) if path.rsplit(".", 1)[-1] == "voice"]
    assert len(voices) == 1, f"expected one voice field in brief.json, found {voices}"
    return voices[0]


ENRICH_READS = _enrich_company_strategy_reads()


class TestStrategyJsonContract:
    def test_enrich_company_reads_are_found(self) -> None:
        assert ENRICH_READS, "parsed no strategy.json reads from outreach-enrich-company"

    @pytest.mark.parametrize("alternatives", ENRICH_READS, ids="|".join)
    def test_read_field_is_in_strategist_schema(self, alternatives: ReadGroup) -> None:
        schema = _strategist_schema_paths()
        top_level = sorted(path for path in schema if "." not in path)
        assert any(path in schema for path in alternatives), (
            f"outreach-enrich-company reads {' or '.join(alternatives)} from strategy.json, "
            f"but the outreach-strategist Output Format has only {top_level}"
        )


@pytest.fixture(scope="module")
def brief_voice_path() -> str:
    return _brief_voice_path()


@pytest.fixture(scope="module")
def voice_read(brief_voice_path: str) -> ReadGroup:
    """The strategy.json read that sets the sender voice, matched on the brief field's leaf name."""
    leaf = brief_voice_path.rsplit(".", 1)[-1]
    matches = [group for group in ENRICH_READS if any(leaf in field for field in group)]
    assert len(matches) == 1, f"expected one voice read in enrich-company, found {matches}"
    return matches[0]


class TestBriefVoiceHandoff:
    def test_strategist_dispatch_with_brief_maps_voice(
        self, brief_voice_path: str, voice_read: ReadGroup
    ) -> None:
        phase = _section(_read(RESEARCH_DISCOVERY), "Phase 1: Strategy")
        brief_blocks = [body for _, body in _fences(phase) if "brief.json" in body]
        assert len(brief_blocks) == 1, "expected one dispatch block that embeds brief.json"
        block = brief_blocks[0]
        assert brief_voice_path in block, f"brief dispatch never names {brief_voice_path}"
        assert any(field in block for field in voice_read), (
            f"brief dispatch never asks for {' or '.join(voice_read)}"
        )

    def test_strategist_reads_voice_from_brief(self, brief_voice_path: str) -> None:
        assert brief_voice_path in _read(STRATEGIST), (
            f"outreach-strategist never says to build the sender voice from {brief_voice_path}"
        )
