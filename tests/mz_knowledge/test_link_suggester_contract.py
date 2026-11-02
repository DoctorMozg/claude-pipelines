import re
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = REPO_ROOT / "plugins/mz-knowledge"
AGENT = PLUGIN / "agents/link-suggester.md"

DISPATCH = re.compile(r"Dispatch the `link-suggester` agent")
FENCE = re.compile(r"^[ \t]*```[^\n]*\n.*?^[ \t]*```[ \t]*$", re.M | re.S)
YAML_FENCE = re.compile(r"^```yaml\n(.*?)^```", re.M | re.S)
INLINE_CODE = re.compile(r"`([^`\n]+)`")
KEY_NAME = re.compile(r"[a-z][a-z0-9_]*")
INPUTS_STEP = re.compile(r"^#+ .*Parse dispatch inputs\n(.*?)(?=^#)", re.M | re.S)
INPUT_BULLET = re.compile(r"^- `(?P<name>[a-z_]+)`", re.M)
ARTIFACT = re.compile(r"<task_name>/(?P<artifact>[\w.-]+\.md)")
DECLARED_STATUS = re.compile(r"^- `STATUS: (?P<status>[A-Z_]+)`", re.M)
STATUS_HANDLER = re.compile(r"^\s*- `(?P<status>[A-Z_]+)` → (?P<action>.+)$", re.M)
STATUS_REFERENCE = re.compile(r"`(?P<status>[A-Z_]+)`")
GATE_OPTION = re.compile(r"\*\*(?P<option>[A-Z][a-z]+)\*\* —")
ESCALATIONS = ("AskUserQuestion", "Status: blocked")


@dataclass(frozen=True)
class OutputBlock:
    keys: frozenset[str]
    values: frozenset[str]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _h2_section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match is not None, f"no '## {heading}' section"
    return match[1]


def _skill_dir(path: Path) -> Path:
    return next(parent for parent in path.parents if (parent / "SKILL.md").is_file())


def _dispatch_section(text: str) -> str:
    sections = [part for part in re.split(r"^(?=## )", text, flags=re.M) if DISPATCH.search(part)]
    assert len(sections) == 1, f"expected one section dispatching link-suggester: {len(sections)}"
    return sections[0]


def _artifact_name(dispatch_section: str) -> str:
    fence = FENCE.search(dispatch_section)
    assert fence is not None, "the link-suggester dispatch has no prompt fence"
    match = ARTIFACT.search(fence[0])
    assert match is not None, "the link-suggester prompt names no output file under the task dir"
    return match["artifact"]


def _reading_region(caller: Path) -> str:
    """The dispatch section onward, plus every other phase file that opens the artifact."""
    text = _read(caller)
    section = _dispatch_section(text)
    artifact = _artifact_name(section)
    readers = [
        _read(path)
        for path in sorted(_skill_dir(caller).rglob("*.md"))
        if path not in (caller, _skill_dir(caller) / "SKILL.md") and artifact in _read(path)
    ]
    return "\n".join([text[text.index(section) :], *readers])


def _key_references(markdown: str) -> set[str]:
    # Fenced blocks hold prompts and the orchestrator's own state, not reads of the artifact.
    names = (span.removesuffix(":") for span in INLINE_CODE.findall(FENCE.sub("", markdown)))
    return {name for name in names if KEY_NAME.fullmatch(name)}


def _orchestrator_words(skill_md: Path) -> set[str]:
    """Gate answers and state keys: names the orchestrator owns, never output keys."""
    text = _read(skill_md)
    gate_answers = {option.lower() for option in GATE_OPTION.findall(text)}
    return gate_answers | _key_references(_h2_section(text, "State Management"))


def _walk(node: object, keys: set[str], values: set[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            keys.add(str(key))
            _walk(value, keys, values)
    elif isinstance(node, list):
        for item in node:
            _walk(item, keys, values)
    elif node is not None:
        values.add(str(node))


def _status_handlers(caller: Path) -> dict[str, str]:
    section = _dispatch_section(_read(caller))
    return {match["status"]: match["action"] for match in STATUS_HANDLER.finditer(section)}


def _escalates(status: str, handlers: dict[str, str], seen: frozenset[str] = frozenset()) -> bool:
    action = handlers.get(status, "")
    if any(word in action for word in ESCALATIONS):
        return True
    # "handle it as `BLOCKED`" escalates when the handler it defers to does.
    deferred = set(STATUS_REFERENCE.findall(action)) & handlers.keys() - seen - {status}
    return any(_escalates(other, handlers, seen | {status}) for other in deferred)


CALLERS = sorted(path for path in (PLUGIN / "skills").rglob("*.md") if DISPATCH.search(_read(path)))
CALLER_PARAMS = [pytest.param(path, id=_skill_dir(path).name) for path in CALLERS]


@pytest.fixture(scope="module")
def output_block() -> OutputBlock:
    blocks = YAML_FENCE.findall(_read(AGENT))
    assert len(blocks) == 1, f"link-suggester should show its artifact as one yaml block: {blocks}"
    keys: set[str] = set()
    values: set[str] = set()
    _walk(yaml.safe_load(blocks[0]), keys, values)
    return OutputBlock(keys=frozenset(keys), values=frozenset(values))


@pytest.fixture(scope="module")
def input_names() -> frozenset[str]:
    match = INPUTS_STEP.search(_read(AGENT))
    assert match is not None, "link-suggester has no 'Parse dispatch inputs' step"
    names = frozenset(INPUT_BULLET.findall(match[1]))
    assert names, "link-suggester's 'Parse dispatch inputs' step lists no inputs"
    return names


@pytest.fixture(scope="module")
def declared_statuses() -> frozenset[str]:
    statuses = frozenset(DECLARED_STATUS.findall(_h2_section(_read(AGENT), "Output Format")))
    assert "DONE" in statuses, f"link-suggester should declare STATUS: DONE, got {statuses}"
    return statuses


class TestCallers:
    def test_link_suggester_has_callers(self) -> None:
        assert CALLERS, "no mz-knowledge skill dispatches link-suggester"


class TestOutputShape:
    @pytest.mark.parametrize("caller", CALLER_PARAMS)
    def test_caller_reads_only_keys_the_agent_writes(
        self, caller: Path, output_block: OutputBlock, input_names: frozenset[str]
    ) -> None:
        name = caller.relative_to(PLUGIN).as_posix()
        read = (
            _key_references(_reading_region(caller))
            - _orchestrator_words(_skill_dir(caller) / "SKILL.md")
            - input_names
            - output_block.values
        )

        assert read <= output_block.keys, (
            f"{name} reads {sorted(read - output_block.keys)}, which link-suggester's "
            f"Output block never writes; it writes {sorted(output_block.keys)}"
        )
        assert read, f"{name} never names a key it reads from link-suggester's artifact"


class TestStatusHandling:
    @pytest.mark.parametrize("caller", CALLER_PARAMS)
    def test_every_declared_status_has_a_handler(
        self, caller: Path, declared_statuses: frozenset[str]
    ) -> None:
        unhandled = sorted(declared_statuses - _status_handlers(caller).keys())

        assert not unhandled, f"{caller.relative_to(PLUGIN)} never handles: {unhandled}"

    @pytest.mark.parametrize("caller", CALLER_PARAMS)
    def test_failure_statuses_escalate_or_block(
        self, caller: Path, declared_statuses: frozenset[str]
    ) -> None:
        handlers = _status_handlers(caller)
        failures = {status for status in declared_statuses if not status.startswith("DONE")}
        silent = sorted(status for status in failures if not _escalates(status, handlers))

        assert failures, "link-suggester declares no failure status"
        assert not silent, (
            f"{caller.relative_to(PLUGIN)}: these statuses neither ask the user nor block: {silent}"
        )
