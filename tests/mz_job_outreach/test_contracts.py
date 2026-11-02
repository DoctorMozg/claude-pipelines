import fnmatch
import re
import shlex
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = REPO_ROOT / "plugins/mz-job-outreach"
AGENTS = PLUGIN / "agents"
SEARCH_SKILL = PLUGIN / "skills/freelance-search"
PITCH_SKILL = PLUGIN / "skills/freelance-pitch"
SCORER = AGENTS / "freelance-scorer.md"

FENCE = re.compile(r"^(`{3,})([^\n]*)\n(.*?)^\1[ \t]*$", re.S | re.M)
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
PLACEHOLDER = re.compile(r"<([A-Za-z_][\w-]*)>")
# A path under the project's .mz folder, as prose or a shell command spells it.
MZ_PATH = re.compile(r'"?<PROJECT_ROOT>"?(/\.mz/[^\s`"\')\]]*)')
# `dir/file.json` where dir is a variable ($x, ${x}, <x>) or a bare folder name.
DIR_REF = re.compile(
    r"(?<![\w/.\-$<{])(?P<dir>\$\{?[a-z_]\w*\}?|<[A-Za-z_]\w*>|[a-z_]\w*)"
    r"/(?P<file>[\w.\-]+\.(?:json|md))\b"
)
# `name = value`, `name=$(...)` or "set `name` to `value`"; the value is one span or token.
BINDING = re.compile(
    r"(?<![\w-])\$?`?(?P<name>[a-z_]\w*)`?\s*(?:=|\bto\b)\s*"
    r"(?P<rhs>`[^`\n]*`|\$\([^)\n]*\)|[^\s,;]+)"
)
OUTPUT_LINE = re.compile(r"^Output\b[^:\n]*:\s*(?P<value>\S+.*)$", re.M)
PARALLEL = re.compile(r"(?<!\bno )\b(?:parallel|waves?)\b", re.I)
# "the `CV path` key": a state key freelance-pitch reads from the search run.
STATE_KEY_READ = re.compile(r"`([^`]+)` key\b")
APPEND = re.compile(r"\bappend(?:s|ed|ing)?\b", re.I)
BASH_GRANT = re.compile(r"Bash\((\S+) \*\)")
SHELL_SEPARATORS = {"|", "||", "&&", ";"}
SAMPLE_VALUES = {"PROJECT_ROOT": "/project", "YYYY_MM_DD": "2026_11_03"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _texts(root: Path) -> dict[Path, str]:
    return {path: _read(path) for path in sorted(root.rglob("*.md"))}


def _where(path: Path) -> str:
    return str(path.relative_to(PLUGIN))


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


def _phase_sections(text: str) -> Iterator[tuple[str, str]]:
    for chunk in re.split(r"^(?=## )", text, flags=re.M):
        if chunk.startswith("## "):
            yield chunk.splitlines()[0].removeprefix("## "), chunk


def _segments(path: str) -> set[str]:
    return {part for part in path.replace('"', "").split("/") if part}


def _bash_grants(skill_md: Path) -> set[str]:
    match = re.search(r"^allowed-tools:(.*)$", _read(skill_md), re.M)
    assert match is not None, f"{_where(skill_md)} has no allowed-tools line"
    return set(BASH_GRANT.findall(match.group(1)))


def _commands(script: str) -> Iterator[str]:
    """First word of every command in a shell snippet, quote-aware."""
    for line in script.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        expect_command = True
        for token in lexer:
            if token in SHELL_SEPARATORS:
                expect_command = True
            elif expect_command:
                expect_command = False
                yield token


@dataclass(frozen=True)
class SearchRun:
    """Where freelance-search writes a run, with placeholders filled by sample values."""

    state_path: str
    run_dir: str
    artifacts: frozenset[str]
    state_keys: frozenset[str]
    layout_placeholders: frozenset[str]

    @property
    def written_paths(self) -> set[str]:
        return {self.state_path, self.run_dir} | {f"{self.run_dir}/{a}" for a in self.artifacts}

    def writes(self, pattern: str) -> bool:
        return any(fnmatch.fnmatchcase(path, pattern) for path in self.written_paths)


def _sample(template: str) -> str:
    def fill(match: re.Match[str]) -> str:
        return SAMPLE_VALUES.get(match.group(1), match.group(1).lower())

    return PLACEHOLDER.sub(fill, template).rstrip("/")


def _glob(template: str) -> str:
    """A freelance-pitch path or glob as an fnmatch pattern over the sample paths."""

    def widen(match: re.Match[str]) -> str:
        name = match.group(1)
        return SAMPLE_VALUES[name] if name == "PROJECT_ROOT" else "*"

    return PLACEHOLDER.sub(widen, template.replace('"', "")).rstrip("/")


def _parse_search_run() -> SearchRun:
    skill = _read(SEARCH_SKILL / "SKILL.md")
    layout = _section(skill, "Directory Structure")
    state = re.search(r"`([^`]*/\.mz/task/[^`]*/state\.md)`", layout)
    run = re.search(r"`([^`]*/\.mz/outreach/[^`]*)` \(called `(<\w+>)`", layout)
    assert state, "freelance-search Directory Structure no longer names its state file"
    assert run, "freelance-search Directory Structure no longer names its run folder"
    state_template, run_template, run_alias = state.group(1), run.group(1), run.group(2)
    for name in {*PLACEHOLDER.findall(state_template), *PLACEHOLDER.findall(run_template)}:
        pattern = re.search(rf"`{name}`[^`]*`([^`]+)`", layout)
        if pattern:
            state_template = state_template.replace(f"<{name}>", pattern.group(1))
            run_template = run_template.replace(f"<{name}>", pattern.group(1))
    search_text = "\n".join(_texts(SEARCH_SKILL).values())
    artifacts = set(re.findall(rf"{re.escape(run_alias)}/([\w.]+\.json)\b", search_text))
    state_yaml = [body for info, body in _fences(_section(skill, "State file")) if info == "yaml"]
    assert state_yaml, "freelance-search no longer shows its state.md template"
    keys = re.findall(r"^([A-Za-z][\w ]*):", state_yaml[0], re.M)
    return SearchRun(
        state_path=_sample(state_template),
        run_dir=_sample(run_template),
        artifacts=frozenset(artifacts),
        state_keys=frozenset(keys),
        layout_placeholders=frozenset(PLACEHOLDER.findall(layout)),
    )


def _bindings(texts: Iterable[str]) -> dict[str, list[str]]:
    """Every .mz path each freelance-pitch variable is set to, following aliases."""
    raw: defaultdict[str, list[str]] = defaultdict(list)
    for text in texts:
        for match in BINDING.finditer(text):
            raw[match.group("name")].append(match.group("rhs"))

    def resolve(name: str, seen: frozenset[str]) -> list[str]:
        paths: list[str] = []
        for rhs in raw.get(name, []):
            path = MZ_PATH.search(rhs)
            alias = rhs.strip("`$<>{}()")
            if path:
                paths.append("<PROJECT_ROOT>" + path.group(1))
            elif alias in raw and alias not in seen:
                paths += resolve(alias, seen | {name})
        return paths

    return {name: resolve(name, frozenset({name})) for name in raw}


@dataclass(frozen=True)
class PitchRead:
    where: str
    written: str
    resolved: str | None


def _pitch_reads(search: SearchRun) -> list[PitchRead]:
    """Each freelance-search path freelance-pitch names, resolved to a full template."""
    texts = _texts(PITCH_SKILL)
    bindings = _bindings(texts.values())
    state_name = search.state_path.rsplit("/", 1)[-1]
    reads: list[PitchRead] = []
    for path, text in texts.items():
        for match in MZ_PATH.finditer(text):
            template = "<PROJECT_ROOT>" + match.group(1).rstrip(".,;:")
            if "freelance_search" in template or template.rsplit("/", 1)[-1] in search.artifacts:
                reads.append(PitchRead(_where(path), match.group(0), template))
        for match in DIR_REF.finditer(text):
            file = match.group("file")
            if file not in search.artifacts and file != state_name:
                continue
            bases = bindings.get(match.group("dir").strip("$<>{}"), [])
            reads += [PitchRead(_where(path), match.group(0), f"{b}/{file}") for b in bases]
            if not bases:
                reads.append(PitchRead(_where(path), match.group(0), None))
    return reads


@dataclass(frozen=True)
class ParallelDispatch:
    where: str
    agents: frozenset[str]
    output: str


def _parallel_dispatches() -> list[ParallelDispatch]:
    """Output lines of dispatch prompts in phases that run agents in parallel waves."""
    agent_names = {path.stem for path in AGENTS.glob("*.md")}
    found: list[ParallelDispatch] = []
    for path, text in _texts(PLUGIN / "skills").items():
        for heading, section in _phase_sections(text):
            prose = FENCE.sub("", section)
            if not PARALLEL.search(prose):
                continue
            agents = frozenset(re.findall(r"`([a-z0-9-]+)`", prose)) & agent_names
            for _info, body in _fences(section):
                for match in OUTPUT_LINE.finditer(body):
                    where = f"{_where(path)} / {heading}"
                    found.append(ParallelDispatch(where, agents, match.group("value")))
    return found


def _output_path(value: str) -> str:
    return next(token for token in value.split() if "/" in token)


@pytest.fixture(scope="module")
def search_run() -> SearchRun:
    return _parse_search_run()


@pytest.fixture(scope="module")
def pitch_reads(search_run: SearchRun) -> list[PitchRead]:
    reads = _pitch_reads(search_run)
    assert reads, "freelance-pitch names no freelance-search path at all"
    return reads


@pytest.fixture(scope="module")
def parallel_dispatches() -> list[ParallelDispatch]:
    dispatches = _parallel_dispatches()
    assert dispatches, "no parallel dispatch prompt with an Output line was found"
    return dispatches


@pytest.fixture(scope="module")
def scorer_dispatch(parallel_dispatches: list[ParallelDispatch]) -> ParallelDispatch:
    matches = [d for d in parallel_dispatches if SCORER.stem in d.agents]
    assert len(matches) == 1, f"expected one parallel {SCORER.stem} dispatch, got {matches}"
    return matches[0]


class TestNoPhantomFolders:
    def test_bare_folders_read_are_shipped_or_created(self) -> None:
        texts = _texts(PLUGIN)
        shipped = {path.name for path in PLUGIN.rglob("*") if path.is_dir()}
        created: set[str] = set()
        for text in texts.values():
            for match in re.finditer(r"\bmkdir -p (.+)$", text, re.M):
                created |= _segments(match.group(1))
            for _info, body in _fences(text):
                for match in OUTPUT_LINE.finditer(body):
                    created |= _segments(_output_path(match.group("value")))
        phantom = sorted(
            f"{_where(path)}: {match.group(0)}"
            for path, text in texts.items()
            for match in DIR_REF.finditer(text)
            if match.group("dir")[0] not in "$<{" and match.group("dir") not in shipped | created
        )
        assert not phantom, f"read from a folder nothing ships or creates: {phantom}"


class TestPitchFindsSearchRun:
    def test_search_paths_pitch_reads_are_written_by_search(
        self, search_run: SearchRun, pitch_reads: list[PitchRead]
    ) -> None:
        wrong = [
            f"{read.where}: {read.written} -> {read.resolved or 'unbound variable'}"
            for read in pitch_reads
            if read.resolved is None or not search_run.writes(_glob(read.resolved))
        ]
        assert not wrong, (
            f"freelance-pitch reads paths freelance-search never writes "
            f"(it writes {sorted(search_run.written_paths)}): {wrong}"
        )

    def test_pitch_reaches_each_search_input_it_names(
        self, search_run: SearchRun, pitch_reads: list[PitchRead]
    ) -> None:
        pitch_text = "\n".join(_texts(PITCH_SKILL).values())
        state_name = search_run.state_path.rsplit("/", 1)[-1]
        needed = {a for a in search_run.artifacts if f"`{a}`" in pitch_text} | {state_name}
        reachable = {
            read.resolved.rsplit("/", 1)[-1]
            for read in pitch_reads
            if read.resolved and search_run.writes(_glob(read.resolved))
        }
        assert needed - reachable == set(), (
            f"freelance-pitch has no valid path to {sorted(needed - reachable)}"
        )

    def test_pitch_takes_only_values_search_records(
        self, search_run: SearchRun, pitch_reads: list[PitchRead]
    ) -> None:
        keys_read = set(STATE_KEY_READ.findall("\n".join(_texts(PITCH_SKILL).values())))
        assert keys_read, "freelance-pitch names no key it reads from the search state"
        path_values = {
            name
            for read in pitch_reads
            if read.resolved
            for name in PLACEHOLDER.findall(read.resolved)
        }
        unknown = sorted(keys_read - search_run.state_keys) + sorted(
            path_values - search_run.state_keys - search_run.layout_placeholders
        )
        assert not unknown, f"freelance-search never records these values: {unknown}"


class TestParallelOutputs:
    def test_parallel_dispatches_write_one_file_per_agent(
        self, parallel_dispatches: list[ParallelDispatch]
    ) -> None:
        shared = [
            f"{d.where}: Output {d.output}"
            for d in parallel_dispatches
            if APPEND.search(d.output)
            or not PLACEHOLDER.search(_output_path(d.output).rsplit("/", 1)[-1])
        ]
        assert not shared, f"parallel agents share one output file: {shared}"

    def test_parallel_agents_are_not_told_to_append(
        self, parallel_dispatches: list[ParallelDispatch]
    ) -> None:
        agents = sorted({name for d in parallel_dispatches for name in d.agents})
        offending = [
            f"{name}: {line.strip()}"
            for name in agents
            for line in FRONTMATTER.sub("", _read(AGENTS / f"{name}.md")).splitlines()
            if APPEND.search(line) and re.search(r"\.json\b|\boutput\b", line, re.I)
        ]
        assert agents, "no agent is dispatched in parallel"
        assert not offending, f"agents run in parallel but append to a file: {offending}"

    def test_scorer_output_names_its_gig(self, scorer_dispatch: ParallelDispatch) -> None:
        file_name = _output_path(scorer_dispatch.output).rsplit("/", 1)[-1]
        keys = set(PLACEHOLDER.findall(file_name))
        assert keys, f"{scorer_dispatch.where}: scorer output {file_name} is not per gig"
        agent_line = re.search(r"^1\. \*\*Output file path\*\*.*$", _read(SCORER), re.M)
        assert agent_line, f"{SCORER.name} no longer lists its output file path"
        assert keys <= set(PLACEHOLDER.findall(agent_line.group(0))), (
            f"{SCORER.name} output path disagrees with the dispatch: {agent_line.group(0)}"
        )
        phase = FENCE.sub("", _read(PLUGIN / scorer_dispatch.where.split(" / ")[0]))
        unassigned = {key for key in keys if f"`{key}`" not in phase}
        assert not unassigned, f"no step gives each gig its {sorted(unassigned)}"

    def test_scorer_files_are_merged_with_a_granted_command(
        self, scorer_dispatch: ParallelDispatch
    ) -> None:
        phase_file, heading = scorer_dispatch.where.split(" / ")
        section = dict(_phase_sections(_read(PLUGIN / phase_file)))[heading]
        per_gig_dir = _output_path(scorer_dispatch.output).rsplit("/", 2)[-2]
        merges = [
            body for info, body in _fences(section) if info == "bash" and f"{per_gig_dir}/" in body
        ]
        assert merges, f"{scorer_dispatch.where}: nothing merges the {per_gig_dir}/ files"
        granted = _bash_grants(SEARCH_SKILL / "SKILL.md")
        ungranted = {cmd for body in merges for cmd in _commands(body)} - granted
        assert not ungranted, f"merge runs commands with no Bash grant: {sorted(ungranted)}"
