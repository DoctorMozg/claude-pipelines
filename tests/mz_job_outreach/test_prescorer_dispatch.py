import json
import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from .test_contracts import (
    AGENTS,
    FENCE,
    FRONTMATTER,
    OUTPUT_LINE,
    PITCH_SKILL,
    PLUGIN,
    SCORER,
    SEARCH_SKILL,
    _fences,
    _phase_sections,
    _read,
    _section,
    _texts,
    _where,
)

PRESCORER = AGENTS / "job-prescorer.md"
SCOUT = AGENTS / "freelance-scout.md"
SKILLS = PLUGIN / "skills"
SCOUT_NOTES = "_scout_notes"

INPUT_LABEL = re.compile(r"^\d+\. \*\*(?P<label>[^*]+)\*\*(?P<rest>.*)$", re.M)
# A file name with something before its extension, so a bare `.md` is not a path.
DOC_PATH = re.compile(r"`(?P<path>[\w<>/-]+\.\w+)`")
PROMPT_FIELD = re.compile(r"^(?P<key>[A-Z][^:\n]*?):[ \t]*(?P<value>\S.*)$", re.M)
PLACEHOLDER = re.compile(r"<[^>\s]+>")
DISPATCH = re.compile(
    r"\b(?:[Dd]ispatch|[Ss]pawn|[Ll]aunch)\w*\b[^`\n]{0,30}`(?P<name>[a-z0-9-]+)`"
)
HARD_GATE_HEADING = re.compile(r"^#+ (?P<title>.*hard gate.*)$", re.M | re.I)
# A backticked concatenation of the fields an agent matches skills against.
SCAN_EXPRESSION = re.compile(r"`(?P<expr>[^`\n]*\+[^`\n]*)`")
IDENTIFIER = re.compile(r"[a-z_][a-z0-9_]*")
GIG_FIELD = re.compile(r"(?<![\w/.])gig\.(?P<field>[a-z_]\w*)")
JQ_CALL = re.compile(r"\bjq\b[^']*'(?P<program>[^']*)'(?P<args>(?:\\\n|[^\n])*)")
JQ_FIELD = re.compile(r"\.([A-Za-z_]\w*)\b")
# A field read with a `//` default is optional: the record may lack it.
JQ_REQUIRED_FIELD = re.compile(r"\.([A-Za-z_]\w*)\b(?!\s*//)")
REDIRECT = re.compile(r'(?<!\S)>\s*"?(?P<path>[^"\s]+)')
RUN_ARTIFACT = re.compile(r"<RUN_DIR>/(\w+\.json)")
BACKTICKED_FIELD = re.compile(r"`([a-z_][a-z0-9_]*)(?=[`:])")
STEP = re.compile(r"^1\. .*$", re.M)


def _body(path: Path) -> str:
    return FRONTMATTER.sub("", _read(path))


def _prose(text: str) -> str:
    return FENCE.sub("", text)


def _label_key(label: str) -> str:
    # Agents list `Strategy file path` where prompts write `Strategy file:`; both name one input.
    return label.strip().lower().removesuffix(" path")


def _shape(path: str) -> str:
    return PLACEHOLDER.sub("<>", path)


@dataclass(frozen=True)
class InputLabel:
    name: str
    path: str | None


def _input_labels(agent: Path) -> list[InputLabel]:
    """Bold labels in the agent's Input list, with the file each one documents."""
    labels: list[InputLabel] = []
    for match in INPUT_LABEL.finditer(_section(_body(agent), "Input")):
        documented = DOC_PATH.search(match["rest"])
        labels.append(
            InputLabel(match["label"].strip(), documented["path"] if documented else None)
        )
    return labels


@dataclass(frozen=True)
class DispatchPrompt:
    skill: str
    where: str
    fields: dict[str, str]


def _dispatch_prompts(agent: str) -> list[DispatchPrompt]:
    """Fenced prompts with an Output line in each skill section that dispatches `agent`."""
    prompts: list[DispatchPrompt] = []
    for path, text in _texts(SKILLS).items():
        for heading, section in _phase_sections(text):
            if agent not in {m["name"] for m in DISPATCH.finditer(_prose(section))}:
                continue
            for _info, body in _fences(section):
                if not OUTPUT_LINE.search(body):
                    continue
                fields = {_label_key(m["key"]): m["value"] for m in PROMPT_FIELD.finditer(body)}
                skill = path.relative_to(SKILLS).parts[0]
                prompts.append(DispatchPrompt(skill, f"{_where(path)} / {heading}", fields))
    return prompts


def _scan_fields(text: str) -> set[str]:
    fields: set[str] = set()
    for match in SCAN_EXPRESSION.finditer(_prose(text)):
        terms = (term.strip().removeprefix("gig.") for term in match["expr"].split("+"))
        fields |= {term for term in terms if IDENTIFIER.fullmatch(term)}
    return fields


def _hard_gate_fields(agent: Path) -> set[str]:
    body = _body(agent)
    return {
        field
        for heading in HARD_GATE_HEADING.finditer(body)
        for field in _scan_fields(_section(body, heading["title"]))
    }


def _example_keys(agent: Path) -> set[str]:
    """Top-level keys of the records in the agent's JSON output examples."""
    keys: set[str] = set()
    for info, body in _fences(_body(agent)):
        if info != "json":
            continue
        data = json.loads(body)
        for record in data if isinstance(data, list) else [data]:
            if isinstance(record, dict) and record.get("title") != SCOUT_NOTES:
                keys |= set(record)
    return keys


@dataclass(frozen=True)
class Merge:
    path: Path
    heading: str
    program: str
    output: str
    joined: frozenset[str]

    @property
    def where(self) -> str:
        return f"{_where(self.path)} / {self.heading}"


def _merge() -> Merge:
    """The jq command that folds the per-gig scorer files into one file."""
    documented = [
        label.path
        for label in _input_labels(SCORER)
        if _label_key(label.name).startswith("output") and label.path
    ]
    assert documented, f"{SCORER.name} no longer documents its output file"
    per_gig_dir = documented[0].rsplit("/", 1)[0] + "/"
    found: list[Merge] = []
    for path, text in _texts(SEARCH_SKILL / "phases").items():
        for heading, section in _phase_sections(text):
            for info, body in _fences(section):
                call = JQ_CALL.search(body)
                redirect = REDIRECT.search(body)
                if info != "bash" or per_gig_dir not in body or not call or not redirect:
                    continue
                output = redirect["path"].rsplit("/", 1)[-1]
                joined = frozenset(RUN_ARTIFACT.findall(body)) - {output}
                found.append(Merge(path, heading, call["program"], output, joined))
    assert len(found) == 1, f"expected one jq merge of {per_gig_dir} files, got {found}"
    return found[0]


def _writer_fields(artifact: str) -> set[str]:
    """Fields named in the numbered steps of the freelance-search section that writes `artifact`."""
    writes = re.compile(rf"\bWrite\b[^\n]*`<RUN_DIR>/{re.escape(artifact)}`")
    sections = [
        section
        for text in _texts(SEARCH_SKILL / "phases").values()
        for _heading, section in _phase_sections(text)
        if writes.search(_prose(section))
    ]
    assert sections, f"no freelance-search step writes {artifact}"
    steps = (match[0] for section in sections for match in STEP.finditer(section))
    return {field for step in steps for field in BACKTICKED_FIELD.findall(step)} - {SCOUT_NOTES}


def _reader_texts(merge: Merge) -> Iterator[tuple[str, str]]:
    """The phase file after the merge, freelance-pitch, and the agents it dispatches."""
    sections = list(_phase_sections(_read(merge.path)))
    after = [heading for heading, _ in sections].index(merge.heading) + 1
    # Rejoined, because a fenced report template holds `## ` lines that split it into sections.
    yield f"{_where(merge.path)} after {merge.heading}", "".join(s for _, s in sections[after:])
    pitch = _texts(PITCH_SKILL)
    yield from ((_where(path), text) for path, text in pitch.items())
    agent_names = {path.stem for path in AGENTS.glob("*.md")}
    dispatched = {m["name"] for text in pitch.values() for m in DISPATCH.finditer(text)}
    for name in sorted(dispatched & agent_names):
        yield _where(AGENTS / f"{name}.md"), _body(AGENTS / f"{name}.md")


def _fields_read(merge: Merge) -> dict[str, set[str]]:
    """Each gig field read from the merged file, mapped to where it is read."""
    reads_output = re.compile(rf"(?<![\w.-]){re.escape(merge.output)}\b")
    reads: defaultdict[str, set[str]] = defaultdict(set)
    for where, text in _reader_texts(merge):
        for match in GIG_FIELD.finditer(text):
            reads[match["field"]].add(where)
        for _info, body in _fences(text):
            for call in JQ_CALL.finditer(body):
                if reads_output.search(call["args"]):
                    for field in JQ_REQUIRED_FIELD.findall(call["program"]):
                        reads[field].add(where)
    return reads


@pytest.fixture(scope="module")
def prescorer_labels() -> list[InputLabel]:
    labels = _input_labels(PRESCORER)
    assert labels, f"{PRESCORER.name} lists no bold Input labels"
    return labels


@pytest.fixture(scope="module")
def prescorer_prompts() -> list[DispatchPrompt]:
    prompts = _dispatch_prompts(PRESCORER.stem)
    assert prompts, f"no skill gives {PRESCORER.stem} a dispatch prompt"
    return prompts


@pytest.fixture(scope="module")
def merge() -> Merge:
    return _merge()


@pytest.fixture(scope="module")
def scorer_fields() -> set[str]:
    fields = _example_keys(SCORER)
    assert fields, f"{SCORER.name} shows no JSON record"
    return fields


@pytest.fixture(scope="module")
def gig_fields(merge: Merge) -> set[str]:
    scouted = _example_keys(SCOUT)
    assert scouted, f"{SCOUT.name} shows no JSON gig record"
    return scouted.union(*(_writer_fields(artifact) for artifact in merge.joined))


class TestPrescorerDispatch:
    def test_every_skill_naming_the_prescorer_has_a_dispatch_prompt(
        self, prescorer_prompts: list[DispatchPrompt]
    ) -> None:
        naming = {
            path.relative_to(SKILLS).parts[0]
            for path, text in _texts(SKILLS).items()
            if f"`{PRESCORER.stem}`" in text
        }
        unprompted = naming - {prompt.skill for prompt in prescorer_prompts}
        assert not unprompted, f"skills use {PRESCORER.stem} with no dispatch prompt: {unprompted}"

    def test_prompts_name_every_input_label(
        self, prescorer_labels: list[InputLabel], prescorer_prompts: list[DispatchPrompt]
    ) -> None:
        missing = [
            f"{prompt.where}: {label.name}"
            for prompt in prescorer_prompts
            for label in prescorer_labels
            if _label_key(label.name) not in prompt.fields
        ]
        assert not missing, f"{PRESCORER.stem} prompts leave out Input labels: {missing}"

    def test_prompt_paths_match_the_agent_input_paths(
        self, prescorer_labels: list[InputLabel], prescorer_prompts: list[DispatchPrompt]
    ) -> None:
        wrong: list[str] = []
        for prompt in prescorer_prompts:
            for label in prescorer_labels:
                value = prompt.fields.get(_label_key(label.name))
                if label.path is None or value is None:
                    continue
                given, expected = _shape(value.split()[0]), _shape(label.path)
                if given != expected and not given.endswith(f"/{expected}"):
                    wrong.append(f"{prompt.where}: {label.name} {value}, agent reads {label.path}")
        assert not wrong, f"prompts pass files the agent does not read: {wrong}"


class TestPrescorerScan:
    def test_prescorer_reads_every_field_a_hard_gate_reads(self) -> None:
        scanned = _scan_fields(_body(PRESCORER))
        assert scanned, f"{PRESCORER.name} no longer lists the fields it scans"
        gates = {path.stem: _hard_gate_fields(path) for path in sorted(AGENTS.glob("*.md"))}
        gates = {name: fields for name, fields in gates.items() if fields}
        assert gates, "no agent in the plugin scans fields in a must-have hard gate"
        # A gig the prescorer rates 0 never reaches the full scorer, so it must read as much.
        unread = {
            name: sorted(fields - scanned) for name, fields in gates.items() if fields - scanned
        }
        assert not unread, f"{PRESCORER.stem} skips fields a full scorer gates on: {unread}"


class TestScoredRecord:
    def test_merge_joins_gigs_on_a_key_both_records_carry(
        self, merge: Merge, scorer_fields: set[str], gig_fields: set[str]
    ) -> None:
        assert merge.joined, f"{merge.where}: {merge.output} gets the scorer records alone"
        keys = set(JQ_FIELD.findall(merge.program)) & scorer_fields & gig_fields
        assert keys, (
            f"{merge.where}: no field in the merge sits on both the scorer record "
            f"{sorted(scorer_fields)} and the gigs of {sorted(merge.joined)}"
        )

    def test_fields_read_from_the_merged_file_are_produced(
        self, merge: Merge, scorer_fields: set[str], gig_fields: set[str]
    ) -> None:
        reads = _fields_read(merge)
        assert reads, f"nothing reads gig fields from {merge.output}"
        produced = scorer_fields | (gig_fields if merge.joined else set())
        missing = {field: sorted(where) for field, where in reads.items() if field not in produced}
        assert not missing, f"read from {merge.output} but never written there: {missing}"
