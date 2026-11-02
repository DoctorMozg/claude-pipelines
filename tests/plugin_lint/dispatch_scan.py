"""Find which agents a plugin's skill, agent and shared files dispatch, by text pattern."""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .conftest import PluginFile

# Two or more kebab-case words, the shape of every agent name; keeps prose like "Agent(s)" out.
AGENT_NAME = r"[a-z0-9]+(?:-[a-z0-9]+)+"
BUILT_IN_AGENTS = frozenset({"general-purpose", "Explore", "Plan"})
_AGENT_CALL = re.compile(rf"Agent\((?P<names>{AGENT_NAME}(?:,\s*{AGENT_NAME})*)\)")
_SUBAGENT_TYPE = re.compile(r"subagent_type[:=]\s*[`\"]?(?P<names>[A-Za-z0-9-]+)")
_DISPATCH_VERB = re.compile(
    rf"\b(?:[Dd]ispatch|[Ss]pawn|[Ll]aunch)(?:es|ed|ing|s)?\b(?P<gap>[^`\n]{{0,30}})"
    rf"`(?P<names>{AGENT_NAME})`"
)
# "the dispatch prompt from `x`" names the dispatcher, not the agent being dispatched.
_INVERTING_GAP = re.compile(r"\b(?:from|by|prompt)\b")
_NEGATED = re.compile(
    r"\b(?:do not|don't|never|not)\s+(?:\w+\s+)?dispatch|\bdispatched by\b", re.IGNORECASE
)
_SHARED_REFERENCE = re.compile(r"\bshared/(?P<file>[A-Za-z0-9_-]+\.md)")


@dataclass(frozen=True)
class Dispatch:
    name: str
    # True when the name sits in Agent(...) or subagent_type, where only an agent type can appear.
    typed: bool
    line: int


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    evidence: str


def find_dispatches(text: str) -> list[Dispatch]:
    """Dispatches named in text, skipping descriptions and lines that negate a dispatch."""
    found: list[Dispatch] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("description:") or _NEGATED.search(line):
            continue
        for pattern, typed in (
            (_AGENT_CALL, True),
            (_SUBAGENT_TYPE, True),
            (_DISPATCH_VERB, False),
        ):
            for match in pattern.finditer(line):
                if not typed and _INVERTING_GAP.search(match["gap"]):
                    continue
                found.extend(
                    Dispatch(name=name.strip(), typed=typed, line=number)
                    for name in match["names"].split(",")
                )
    return found


def dispatch_edges(files: Iterable[PluginFile], agent_plugins: Mapping[str, str]) -> list[Edge]:
    """Cross-plugin edges; a shared file's dispatches count for each plugin whose files name it."""
    files = tuple(files)
    shared_dispatches = {
        source.path.name: find_dispatches(source.text) for source in files if source.is_shared
    }
    edges: list[Edge] = []
    for source in files:
        if source.is_shared:
            continue
        for dispatch in find_dispatches(source.text):
            edges.extend(
                _edge(source.plugin, dispatch, f"{source.relative}:{dispatch.line}", agent_plugins)
            )
        for shared_file in set(_SHARED_REFERENCE.findall(source.text)):
            for dispatch in shared_dispatches.get(shared_file, []):
                evidence = f"{source.relative} via shared/{shared_file}:{dispatch.line}"
                edges.extend(_edge(source.plugin, dispatch, evidence, agent_plugins))
    return edges


def _edge(
    plugin: str, dispatch: Dispatch, evidence: str, agent_plugins: Mapping[str, str]
) -> list[Edge]:
    owner = agent_plugins.get(dispatch.name)
    if owner is None or owner == plugin:
        return []
    return [Edge(source=plugin, target=owner, evidence=f"{evidence} ({dispatch.name})")]
