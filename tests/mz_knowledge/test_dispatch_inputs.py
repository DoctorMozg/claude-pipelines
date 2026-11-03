import re
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = REPO_ROOT / "plugins/mz-knowledge"
AGENTS = PLUGIN / "agents"
SKILLS = PLUGIN / "skills"

HEADING = re.compile(r"^#{1,6} ")
INPUT_HEADING = re.compile(r"^#{2,4} (?:.*Parse dispatch inputs|Inputs?)\s*$", re.I)
INPUT_BULLET = re.compile(r"^\s*[-*] `(?P<name>[a-z][a-z0-9_]*)`(?P<rest>.*)$")
OPTIONAL_INPUT = re.compile(r"\b(?:optional|default)\b", re.I)
SENTENCE_BREAK = re.compile(r"(?<=\.)\s+")
FIELD_NAME = re.compile(r"`([a-z][a-z0-9_]*)`")
FENCE_OPEN = re.compile(r"^\s*(?P<marker>`{3,}|~{3,})")
# A "re-dispatch" only amends an earlier prompt and "Dispatches" describes a skill.
DISPATCH_WORD = r"(?<![\w-])dispatch(?![\w-])"


@dataclass(frozen=True)
class Fence:
    line: int
    body: str


@dataclass(frozen=True)
class DispatchCase:
    agent: str
    skill_file: str
    fences: tuple[Fence, ...]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _required_inputs(agent_text: str) -> frozenset[str]:
    required: set[str] = set()
    in_inputs = False
    for line in agent_text.splitlines():
        if HEADING.match(line):
            in_inputs = bool(INPUT_HEADING.match(line))
        elif (
            in_inputs
            and (bullet := INPUT_BULLET.match(line))
            and not OPTIONAL_INPUT.search(bullet["rest"])
        ):
            required.add(bullet["name"])
        for sentence in SENTENCE_BREAK.split(line):
            if "NEEDS_CONTEXT" in sentence and "missing" in sentence.lower():
                required.update(FIELD_NAME.findall(sentence))
    return frozenset(required)


def _closes(line: str, marker: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(marker) and set(stripped) == {marker[0]}


def _fences_after_dispatches(text: str, agent: str) -> list[Fence]:
    lines = text.splitlines()
    own_dispatch = re.compile(rf"{DISPATCH_WORD}.*?`{re.escape(agent)}`", re.I)
    any_dispatch = re.compile(rf"{DISPATCH_WORD}.*?`[a-z0-9-]+`", re.I)
    fences: list[Fence] = []
    marker: str | None = None
    for index, line in enumerate(lines):
        if marker is not None:
            if _closes(line, marker):
                marker = None
            continue
        if opening := FENCE_OPEN.match(line):
            marker = opening["marker"]
            continue
        if own_dispatch.search(line) and (fence := _next_fence(lines, index + 1, any_dispatch)):
            fences.append(fence)
    return fences


def _next_fence(lines: list[str], start: int, any_dispatch: re.Pattern[str]) -> Fence | None:
    # Stop at the next dispatch so a heading and the dispatch line under it never share a fence.
    for index in range(start, len(lines)):
        line = lines[index]
        if HEADING.match(line) or any_dispatch.search(line):
            return None
        if opening := FENCE_OPEN.match(line):
            marker = opening["marker"]
            end = next(
                (i for i in range(index + 1, len(lines)) if _closes(lines[i], marker)),
                len(lines),
            )
            return Fence(line=index + 1, body="\n".join(lines[index + 1 : end]))
    return None


def _label(name: str) -> re.Pattern[str]:
    # A bare substring would pass vacuously: every fence already holds `.mz/task/<task_name>/`.
    words = "[_ ]".join(re.escape(word) for word in name.split("_"))
    return re.compile(rf"^\s*(?:[-*]\s+)?{words}\s*:", re.I | re.M)


def _unlabelled(fence: Fence, required: frozenset[str]) -> list[str]:
    return sorted(name for name in required if not _label(name).search(fence.body))


def _agent_inputs() -> dict[str, frozenset[str]]:
    return {path.stem: _required_inputs(_read(path)) for path in AGENTS.glob("*.md")}


def _dispatch_cases(agent_inputs: dict[str, frozenset[str]]) -> list[DispatchCase]:
    cases: list[DispatchCase] = []
    for agent, required in sorted(agent_inputs.items()):
        if not required:
            continue
        for skill_file in sorted(SKILLS.rglob("*.md")):
            fences = _fences_after_dispatches(_read(skill_file), agent)
            if fences:
                relative = skill_file.relative_to(SKILLS).as_posix()
                cases.append(DispatchCase(agent, relative, tuple(fences)))
    return cases


AGENT_INPUTS = _agent_inputs()
DISPATCH_CASES = _dispatch_cases(AGENT_INPUTS)


class TestInputParsing:
    @pytest.mark.parametrize(
        ("fence_body", "name", "labelled"),
        [
            ("Task name: demo", "task_name", True),
            ("  task_name: demo", "task_name", True),
            ("- Output path: /tmp/x.md", "output_path", True),
            ("Task dir: <PROJECT_ROOT>/.mz/task/<task_name>/", "task_name", False),
            ("Write findings to output_path when done.", "output_path", False),
            ("References report: /tmp/r.md", "references_report_path", False),
        ],
    )
    def test_label_match(self, fence_body: str, name: str, labelled: bool) -> None:
        assert bool(_label(name).search(fence_body)) is labelled

    def test_every_input_step_yields_required_inputs(self) -> None:
        silent = [
            path.name
            for path in AGENTS.glob("*.md")
            if any(INPUT_HEADING.match(line) for line in _read(path).splitlines())
            and not AGENT_INPUTS[path.stem]
        ]
        assert not silent, f"input step parsed to nothing in: {silent}"

    def test_every_agent_with_inputs_has_a_dispatch(self) -> None:
        dispatched = {case.agent for case in DISPATCH_CASES}
        undispatched = sorted(
            agent
            for agent, required in AGENT_INPUTS.items()
            if required and agent not in dispatched
        )
        assert not undispatched, f"no fenced dispatch found for: {undispatched}"


class TestDispatchLabelsInputs:
    @pytest.mark.parametrize(
        "case",
        [pytest.param(case, id=f"{case.agent}@{case.skill_file}") for case in DISPATCH_CASES],
    )
    def test_dispatch_labels_every_required_input(self, case: DispatchCase) -> None:
        required = AGENT_INPUTS[case.agent]
        gaps = {
            fence.line: missing
            for fence in case.fences
            if (missing := _unlabelled(fence, required))
        }
        assert not gaps, (
            f"{case.skill_file}: {case.agent} dispatch leaves inputs unlabelled "
            f"(fence line: names): {gaps}; the agent requires {sorted(required)}"
        )
