import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = REPO_ROOT / "plugins/mz-job-outreach"
RESEARCHER = PLUGIN / "agents/job-source-researcher.md"
SKILLS = ("job-search", "freelance-search")
# User-locked exclusion: open marketplaces with no vetting.
BANNED_DOMAINS = ("upwork.com", "fiverr.com", "peopleperhour.com", "freelancer.com", "guru.com")
KIND_OF_ARRAY = {"scrape_sources": "scrape", "guidance_sources": "guidance"}

CANONICAL_FILE = re.compile(r"^Canonical file: <SKILL_DIR>/(\S+)$", re.M)
# Prose writes ranges with a hyphen or an en dash.
SCRAPE_ADDITIONS = re.compile(r"\bAdd (\d+)[-\u2013](\d+) (?:scrape )?boards\b")
GUIDANCE_ADDITIONS = re.compile(r"\bup to (\d+) guidance entries\b")
RESEARCHER_RANGE = re.compile(
    r"\b(\d+)[-\u2013](\d+) (?:additional |verified )?(?:boards|entries)\b"
)
# A fixed total: "must not exceed 10", "cap of 10", or a check bound such as "Total entries: 5-10".
TOTAL_CAP = re.compile(
    r"must\s+not\s+exceed\s+(\d+)|\bcap\s+of\s+(\d+)|\bentries\b[^.]*?:\s*\d+[-\u2013](\d+)\b"
)
# "lists 10 boards", "(12 entries": a count of a list, not a bound such as "fewer than 2 boards".
STATED_COUNT = re.compile(
    r"(?<![\d.\u2013-])(?<!than )(?<!most )(?<!least )(?<!up to )\b(\d+) "
    r"(?:canonical |scrape |guidance )?(?:boards|entries)\b"
)
ARRAY_NAME = re.compile("|".join(rf"`{name}`" for name in KIND_OF_ARRAY))
REQUIRED_KEYS = re.compile(r"Every entry has ((?:`\w+`,? ?)+)")
COUNT_BINDING = re.compile(
    r'^(?P<var>\w+)=\$\(jq (?P<expr>.+?) "<SKILL_DIR>/(?P<file>[\w./-]+)"\)\s*$', re.M
)
CHECK_START = re.compile(r"^After the researcher completes\b", re.M)
REMOVAL = re.compile(r"\b(?:drop|trim|remove|cut)\w*\b", re.I)
NEVER_REMOVE_CANONICAL = re.compile(r"\bnever (?:drop|trim|remove|cut)\b[^.]*\bcanonical\b", re.I)
RECHECK = re.compile(r"\b(?:check|validate)\w* again\b|\bre-?(?:check|validate)", re.I)
STATUS_LINE = re.compile(r"^- `(?P<token>[A-Z_]+)` \u2014 (?P<meaning>.*)$", re.M)


@dataclass(frozen=True)
class Additions:
    low: int
    high: int


@dataclass(frozen=True)
class Cap:
    kind: str
    value: int
    sentence: str


@dataclass(frozen=True)
class SourceSkill:
    """One search skill's phase-2 text next to the canonical lists it copies."""

    name: str
    phase: str
    canonical_ref: str
    canonical_file: Path
    canonical: object
    lists: dict[str, list[dict[str, Any]]]
    additions: dict[str, Additions]

    def floor(self, kind: str) -> int:
        """Smallest legal total: every canonical entry plus the fewest additions."""
        return len(self.lists.get(kind, [])) + self.additions.get(kind, Additions(0, 0)).low

    @property
    def entries(self) -> Iterator[tuple[str, dict[str, Any]]]:
        return ((kind, entry) for kind, items in self.lists.items() for entry in items)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _blocks(text: str) -> list[str]:
    """Paragraphs and list items, each flattened onto one line."""
    parts = re.split(r"\n\s*\n|\n(?=\s*(?:[-*]|\d+\.) )", text)
    return [" ".join(part.split()) for part in parts if part.strip()]


def _sentences(text: str) -> list[str]:
    return [s for block in _blocks(text) for s in re.split(r"(?<=\.)\s+(?=[A-Z`*-])", block)]


def _total_caps(text: str) -> list[Cap]:
    caps: list[Cap] = []
    for sentence in _sentences(text):
        lowered = sentence.lower()
        # A limit on additions alone ("6 augmented entries") is not a total.
        if "augmented" in lowered and not re.search(r"canonical\b|combined|total", lowered):
            continue
        kind = "guidance" if "guidance" in lowered else "scrape"
        for match in TOTAL_CAP.finditer(sentence):
            value = next(group for group in match.groups() if group)
            caps.append(Cap(kind, int(value), sentence))
    return caps


def _check_section(phase: str) -> str:
    """The source check after the researcher returns, up to the next heading."""
    start = CHECK_START.search(phase)
    assert start, "phase 2 has no check after the researcher returns"
    rest = phase[start.start() :]
    end = re.search(r"^#{2,6} ", rest, re.M)
    return rest[: end.start()] if end else rest


def _jq_count(expr: str, data: object) -> int:
    """Evaluate the `length` or `.key | length` filter a phase file counts entries with."""
    path, _, last = expr.strip("'\"").rpartition("|")
    assert last.strip() == "length", f"unsupported jq filter {expr!r}"
    for key in filter(None, path.strip().split(".")):
        assert isinstance(data, dict), f"jq filter {expr!r} indexes a non-object"
        data = data[key]
    assert isinstance(data, list | dict), f"jq filter {expr!r} counts a scalar"
    return len(data)


def _researcher_status_for_shortfall(low: int) -> str:
    statuses = re.search(r"^## Status Protocol\n(.*?)(?=^## |\Z)", _read(RESEARCHER), re.S | re.M)
    assert statuses, f"{RESEARCHER.name} has no Status Protocol section"
    tokens = [
        match["token"]
        for match in STATUS_LINE.finditer(statuses.group(1))
        if f"fewer than {low}" in match["meaning"]
    ]
    assert len(tokens) == 1, f"{RESEARCHER.name} names no status for fewer than {low} additions"
    return tokens[0]


def _load_skill(name: str) -> SourceSkill:
    skill_dir = PLUGIN / "skills" / name
    phase = _read(skill_dir / "phases/strategy_and_sources.md")
    canonical_ref = CANONICAL_FILE.search(phase)
    assert canonical_ref, f"{name}: the researcher dispatch names no canonical file"
    canonical_file = skill_dir / canonical_ref.group(1)
    canonical = json.loads(_read(canonical_file))
    if isinstance(canonical, list):
        lists = {"scrape": canonical}
    else:
        lists = {KIND_OF_ARRAY[key]: items for key, items in canonical.items()}
    scrape = SCRAPE_ADDITIONS.findall(phase)
    assert len(scrape) == 1, f"{name}: expected one 'Add N-M boards' order, got {scrape}"
    additions = {"scrape": Additions(int(scrape[0][0]), int(scrape[0][1]))}
    guidance = GUIDANCE_ADDITIONS.findall(phase)
    if guidance:
        additions["guidance"] = Additions(0, int(guidance[0]))
    return SourceSkill(
        name, phase, canonical_ref.group(1), canonical_file, canonical, lists, additions
    )


@pytest.fixture(scope="module")
def skills() -> dict[str, SourceSkill]:
    return {name: _load_skill(name) for name in SKILLS}


@pytest.fixture(params=SKILLS)
def skill(request: pytest.FixtureRequest, skills: dict[str, SourceSkill]) -> SourceSkill:
    name: str = request.param
    return skills[name]


class TestCanonicalFiles:
    def test_entries_carry_the_keys_the_check_requires(self, skill: SourceSkill) -> None:
        listed = REQUIRED_KEYS.search(_check_section(skill.phase))
        assert listed, f"{skill.name}: the source check lists no required keys"
        required = set(re.findall(r"`(\w+)`", listed.group(1)))
        missing = [
            f"{entry.get('name')}: {sorted(required - entry.keys())}"
            for _, entry in skill.entries
            if required - entry.keys()
        ]
        assert not missing, f"{skill.canonical_file.name} entries lack keys: {missing}"

    def test_entries_are_tagged_canonical(self, skill: SourceSkill) -> None:
        wrong = [entry.get("name") for _, entry in skill.entries if entry["tier"] != "canonical"]
        assert not wrong, f"{skill.canonical_file.name} entries not tagged canonical: {wrong}"

    def test_no_entry_points_at_a_banned_marketplace(self, skill: SourceSkill) -> None:
        banned = [
            entry["url"]
            for _, entry in skill.entries
            for domain in BANNED_DOMAINS
            if (host := urlparse(entry["url"]).hostname or "") == domain
            or host.endswith(f".{domain}")
        ]
        assert not banned, f"{skill.canonical_file.name} lists banned marketplaces: {banned}"

    def test_only_guidance_entries_skip_scraping(self, skill: SourceSkill) -> None:
        wrong = [
            f"{kind}: {entry.get('name')}"
            for kind, entry in skill.entries
            if entry["scrape_allowed"] is not (kind == "scrape")
        ]
        assert not wrong, f"{skill.canonical_file.name} has the wrong scrape_allowed: {wrong}"


class TestSourceCaps:
    def test_canonical_list_plus_minimum_additions_fits_every_cap(self, skill: SourceSkill) -> None:
        broken = [
            f"{cap.sentence!r} (floor {skill.floor(cap.kind)})"
            for cap in _total_caps(skill.phase)
            if skill.floor(cap.kind) > cap.value
        ]
        assert not broken, f"{skill.name}: canonical list plus fewest additions breaks {broken}"

    def test_researcher_caps_fit_every_canonical_list(self, skills: dict[str, SourceSkill]) -> None:
        body = _read(RESEARCHER)
        broken = [
            f"{cap.sentence!r} < {s.name} floor {s.floor(cap.kind)}"
            for cap in _total_caps(body)
            for s in skills.values()
            if s.floor(cap.kind) > cap.value
        ]
        assert not broken, f"{RESEARCHER.name} caps break a canonical list: {broken}"

    def test_researcher_range_matches_the_dispatches(self, skills: dict[str, SourceSkill]) -> None:
        stated = {Additions(int(a), int(b)) for a, b in RESEARCHER_RANGE.findall(_read(RESEARCHER))}
        ordered = {s.additions["scrape"] for s in skills.values()}
        assert stated, f"{RESEARCHER.name} states no augmentation range"
        assert stated == ordered, f"{RESEARCHER.name} says {stated}, dispatches say {ordered}"

    def test_check_bounds_follow_the_canonical_file(self, skill: SourceSkill) -> None:
        check = _check_section(skill.phase)
        bindings = list(COUNT_BINDING.finditer(check))
        assert len(bindings) == 1, f"{skill.name}: the check doesn't count canonical entries"
        binding = bindings[0]
        assert binding["file"] == skill.canonical_ref, f"{skill.name}: counts {binding['file']}"
        counted = _jq_count(binding["expr"], skill.canonical)
        assert counted == len(skill.lists["scrape"]), f"{skill.name}: jq counts {counted}"
        offsets = {int(n) for n in re.findall(rf"`{binding['var']} \+ (\d+)`", check)}
        span = skill.additions["scrape"]
        assert offsets == {span.low, span.high}, (
            f"{skill.name}: check bounds {binding['var']} + {sorted(offsets)} "
            f"disagree with the {span.low}-{span.high} boards the researcher adds"
        )

    def test_prose_counts_match_the_canonical_file(self, skill: SourceSkill) -> None:
        wrong: list[str] = []
        for sentence in _sentences(skill.phase):
            for match in STATED_COUNT.finditer(sentence):
                before = sentence[: match.start()]
                arrays = ARRAY_NAME.findall(before)
                if arrays:
                    kind = KIND_OF_ARRAY[arrays[-1].strip("`")]
                else:
                    kind = "guidance" if "guidance" in match.group(0) else "scrape"
                if int(match.group(1)) != len(skill.lists[kind]):
                    wrong.append(f"{match.group(0)!r} vs {len(skill.lists[kind])} {kind}")
        assert not wrong, f"{skill.name}: prose contradicts {skill.canonical_file.name}: {wrong}"


class TestCheckFailureBranch:
    def test_overflow_trims_lowest_relevance_additions_only(self, skill: SourceSkill) -> None:
        blocks = _blocks(_check_section(skill.phase))
        trims = [b for b in blocks if REMOVAL.search(b) and "augmented" in b and "relevance" in b]
        assert trims, f"{skill.name}: the check never trims low-relevance augmented entries"
        assert any(NEVER_REMOVE_CANONICAL.search(b) for b in blocks), (
            f"{skill.name}: the check doesn't protect canonical entries from trimming"
        )
        assert any(RECHECK.search(b) for b in blocks), f"{skill.name}: no re-check after trimming"

    def test_shortfall_continues_with_the_researcher_concern(self, skill: SourceSkill) -> None:
        low = skill.additions["scrape"].low
        status = _researcher_status_for_shortfall(low)
        branches = [
            b
            for b in _blocks(_check_section(skill.phase))
            if f"fewer than {low}" in b and status in b and re.search(r"\bcontinue\b", b, re.I)
        ]
        assert branches, f"{skill.name}: no branch continues on fewer than {low} with {status}"
