import re
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGINS_DIR = REPO_ROOT / "plugins"
DEV_PIPE = PLUGINS_DIR / "mz-dev-pipe"
SKILLS_DIR = DEV_PIPE / "skills"
TOOLING_DETECTOR = "pipeline-tooling-detector"

AGENT_NAME = r"[a-z0-9]+(?:-[a-z0-9]+)+"
_FRONTMATTER = re.compile(r"\A---\n(?P<yaml>.*?)\n---\n", re.DOTALL)
_BACKTICKED_AGENT = re.compile(rf"`(?P<name>{AGENT_NAME})`")
# An agent, by backticked name or as "the <role>", as the subject of "writes".
_WRITE_CLAIM = re.compile(
    rf"(?:`(?P<name>{AGENT_NAME})`"
    r"|\b(?:[Tt]he|[Ee]ach|[Ee]very)\s+(?:[a-z-]+\s+)??(?P<role>[a-z]+?)s?)"
    r"(?:\s+agent)?\s+(?:(?:also|then|now|itself|[a-z]+ly)\s+)?writes?\b"
)
_MISSING_INPUT = re.compile(r"missing `(?P<key>[a-z_]+)`")
_FENCE_OPEN = re.compile(r"^\s*(?P<fence>`{3,}|~{3,})")


def _can_write(frontmatter: Mapping[str, object]) -> bool:
    tools = frontmatter.get("tools")
    # An agent without a tools list inherits every tool, Write included.
    if tools is None:
        return True
    entries = tools if isinstance(tools, list) else re.split(r",(?![^(]*\))", str(tools))
    return "Write" in {str(entry).strip() for entry in entries}


def load_write_access() -> dict[str, bool]:
    """Every agent name in the registry mapped to whether its frontmatter grants Write."""
    access: dict[str, bool] = {}
    for path in sorted(PLUGINS_DIR.glob("*/agents/*.md")):
        match = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
        assert match is not None, f"{path}: no frontmatter"
        frontmatter = yaml.safe_load(match["yaml"])
        name = str(frontmatter["name"])
        access[name] = access.get(name, False) or _can_write(frontmatter)
    return access


def find_write_claims(
    lines: Iterable[str], named_agents: Iterable[str], can_write: Mapping[str, bool]
) -> list[tuple[int, str]]:
    """Lines that say an agent without Write writes; "the <role>" resolves against named agents."""
    named = frozenset(named_agents) & can_write.keys()
    claims: list[tuple[int, str]] = []
    for number, line in enumerate(lines, start=1):
        for match in _WRITE_CLAIM.finditer(line):
            if match["name"]:
                agents = {match["name"]} & can_write.keys()
            else:
                agents = {agent for agent in named if agent.rsplit("-", 1)[-1] == match["role"]}
            if agents and not any(can_write[agent] for agent in agents):
                claims.append((number, f"{match.group(0)!r} -> {', '.join(sorted(agents))}"))
    return claims


def dispatch_prompts(text: str, agent: str) -> list[tuple[int, str]]:
    """Each dispatch of `agent`: the dispatching line plus the fenced prompt right after it."""
    verb = re.compile(rf"\b[Dd]ispatch(?:es|ed|ing)?\s+(?:an?\s+|the\s+)?`{re.escape(agent)}`")
    lines = text.splitlines()
    prompts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if not verb.search(line):
            continue
        rest = lines[index + 1 :]
        following = next((i for i, candidate in enumerate(rest) if candidate.strip()), None)
        body: list[str] = []
        if following is not None and (opener := _FENCE_OPEN.match(rest[following])):
            for candidate in rest[following + 1 :]:
                if candidate.strip() == opener["fence"]:
                    break
                body.append(candidate)
        prompts.append((index + 1, "\n".join([line, *body])))
    return prompts


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


@pytest.fixture(scope="module")
def can_write() -> dict[str, bool]:
    access = load_write_access()
    assert not all(access.values()), "no Write-less agent found; the frontmatter parse is broken"
    return access


class TestWriteClaimDetector:
    @pytest.mark.parametrize(
        "line",
        [
            "Wait for completion. The researcher writes `web_research.md` directly.",
            "`pipeline-researcher` writes the findings file.",
            "Each researcher then writes its own lens file.",
            "The web researchers write their reports to disk.",
        ],
    )
    def test_flags_a_write_less_agent_said_to_write(
        self, can_write: dict[str, bool], line: str
    ) -> None:
        named = ["pipeline-researcher", "pipeline-web-researcher"]

        assert find_write_claims([line], named, can_write)

    @pytest.mark.parametrize(
        "line",
        [
            "After it returns, the **orchestrator** (not a sub-agent) writes the response.",
            "After the researcher returns, the orchestrator writes it to `import_graph.json`.",
            "The researcher never writes files; it returns the report inline.",
            "The coder writes the implementation.",
            "Skill and phase files write `<PLUGIN_ROOT>/...` paths literally.",
        ],
    )
    def test_ignores_lines_where_no_write_less_agent_writes(
        self, can_write: dict[str, bool], line: str
    ) -> None:
        named = ["pipeline-researcher", "pipeline-coder"]

        assert not find_write_claims([line], named, can_write)

    def test_ignores_a_role_shared_with_an_agent_that_can_write(
        self, can_write: dict[str, bool]
    ) -> None:
        # "the reviewer" could mean either agent, so the claim is not provably wrong.
        named = ["pipeline-code-reviewer", "branch-reviewer"]

        assert not find_write_claims(["The reviewer writes its report."], named, can_write)


class TestWriteLessAgentClaims:
    @pytest.mark.parametrize(
        "skill_dir",
        sorted(path for path in SKILLS_DIR.iterdir() if path.is_dir()),
        ids=lambda path: path.name,
    )
    def test_no_phase_says_a_write_less_agent_writes_a_file(
        self, can_write: dict[str, bool], skill_dir: Path
    ) -> None:
        files = {path: path.read_text(encoding="utf-8") for path in sorted(skill_dir.rglob("*.md"))}
        named = {m["name"] for text in files.values() for m in _BACKTICKED_AGENT.finditer(text)}

        violations = [
            f"{_relative(path)}:{number}: {claim}"
            for path, text in files.items()
            for number, claim in find_write_claims(text.splitlines(), named, can_write)
        ]

        assert not violations, "the orchestrator must persist these agents' reports:\n" + "\n".join(
            violations
        )


class TestToolingDetectorDispatch:
    def test_every_dispatch_passes_the_inputs_the_detector_requires(self) -> None:
        agent_text = (DEV_PIPE / "agents" / f"{TOOLING_DETECTOR}.md").read_text(encoding="utf-8")
        required = {m["key"] for m in _MISSING_INPUT.finditer(agent_text)}
        assert required, f"{TOOLING_DETECTOR} names no required dispatch input"
        sites = [
            (path, number, prompt)
            for path in sorted(SKILLS_DIR.rglob("*.md"))
            for number, prompt in dispatch_prompts(
                path.read_text(encoding="utf-8"), TOOLING_DETECTOR
            )
        ]
        assert sites, f"no mz-dev-pipe skill dispatches {TOOLING_DETECTOR}"

        violations = [
            f"{_relative(path)}:{number}: missing {sorted(missing)}"
            for path, number, prompt in sites
            if (missing := {key for key in required if f"{key}:" not in prompt})
        ]

        assert not violations, "\n".join(violations)
