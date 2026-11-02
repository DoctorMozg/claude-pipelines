import re

from .conftest import DocSet, assert_no_violations, split_tool_list

KNOWN_KEYS = frozenset(
    {
        "name",
        "description",
        "tools",
        "disallowedTools",
        "model",
        "effort",
        "maxTurns",
        "color",
        "skills",
        "memory",
        "isolation",
        "background",
        "omitClaudeMd",
        "autoCompactWindow",
        "experimental",
    }
)
# Plugin agents ignore these; declaring one promises a hook, server or mode that never applies.
IGNORED_PLUGIN_KEYS = frozenset({"hooks", "mcpServers", "permissionMode", "initialPrompt"})
REQUIRED_KEYS = ("tools", "model", "effort", "maxTurns")
MODEL_TIERS = frozenset({"haiku", "sonnet", "opus"})
EFFORT_LEVELS = frozenset({"low", "medium", "high", "xhigh", "max"})
ABOVE_MEDIUM = frozenset({"high", "xhigh", "max"})
# medium is the 5.5 default; high is for work where verification matters (user, 2026-11-02).
HIGH_EFFORT_AGENTS = {
    "branch-reviewer": "deep branch review",
    "github-pr-reviewer": "pull request review",
    "pipeline-code-reviewer": "code review in build, polish and debug",
    "pipeline-completeness-checker": "final verification gate",
    "gov-audit-reviewer": "rubric review of decision records",
    "gov-critic-alternatives": "adversarial decision critique",
    "gov-critic-assumptions": "adversarial decision critique",
    "gov-critic-blast-radius": "adversarial decision critique",
    "gov-critic-reversibility": "adversarial decision critique",
    "pipeline-planner": "implementation planning",
    "accessibility-specialist": "WCAG hard-gate validation",
    "pipeline-coder": "bug fixes in polish and debug, where edge cases are likely",
    "pipeline-test-writer": "edge-case tests written before the code",
    "pipeline-perf-candidate": "optimizations that must keep the correctness command green",
}
COLORS = frozenset({"red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"})
KNOWN_TOOLS = frozenset(
    {
        "Read",
        "Write",
        "Edit",
        "Glob",
        "Grep",
        "Bash",
        "WebFetch",
        "WebSearch",
        "NotebookEdit",
        "TodoWrite",
        "Skill",
        "SendMessage",
        "ToolSearch",
        "LSP",
        "Monitor",
        "TaskCreate",
        "TaskGet",
        "TaskList",
        "TaskUpdate",
        "TaskStop",
    }
)
# Claude Code removes these from custom subagents, so an agent body can never rely on them.
STRIPPED_TOOLS = frozenset({"AskUserQuestion"})
NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+){1,3}")
MCP_TOOL = re.compile(r"mcp__[A-Za-z0-9_-]+__(?:\*|[A-Za-z0-9_-]+)")
AGENT_TOOL = re.compile(r"Agent\((?P<types>[^)]*)\)")


class TestFrontmatterShape:
    def test_frontmatter_is_strict_yaml_mapping(self, agents: DocSet) -> None:
        assert_no_violations(list(agents.parse_errors))

    def test_frontmatter_has_only_known_keys(self, agents: DocSet) -> None:
        violations = [
            f"{item.doc.relative}: unknown key {key!r}"
            for item in agents.parsed
            for key in item.frontmatter
            if key not in KNOWN_KEYS | IGNORED_PLUGIN_KEYS
        ]
        assert_no_violations(violations)

    def test_frontmatter_has_no_ignored_plugin_fields(self, agents: DocSet) -> None:
        violations = [
            f"{item.doc.relative}: plugin agents ignore {key!r}"
            for item in agents.parsed
            for key in item.frontmatter
            if key in IGNORED_PLUGIN_KEYS
        ]
        assert_no_violations(violations)

    def test_required_fields_are_set(self, agents: DocSet) -> None:
        violations = [
            f"{item.doc.relative}: missing {key!r}"
            for item in agents.parsed
            for key in REQUIRED_KEYS
            if key not in item.frontmatter
        ]
        assert_no_violations(violations)


class TestNames:
    def test_name_is_kebab_case_and_matches_filename(self, agents: DocSet) -> None:
        violations: list[str] = []
        for item in agents.parsed:
            name = item.frontmatter.get("name")
            if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
                violations.append(f"{item.doc.relative}: name {name!r} is not 2-4 kebab-case words")
            elif not 3 <= len(name) <= 50:
                violations.append(f"{item.doc.relative}: name {name!r} is not 3-50 characters")
            elif name != item.doc.stem:
                violations.append(f"{item.doc.relative}: name {name!r} differs from the filename")
        assert_no_violations(violations)

    def test_names_are_unique_across_marketplace(self, agents: DocSet) -> None:
        owners: dict[str, list[str]] = {}
        for item in agents.parsed:
            owners.setdefault(str(item.frontmatter.get("name")), []).append(item.doc.relative)
        violations = [
            f"{name}: {', '.join(paths)}" for name, paths in owners.items() if len(paths) > 1
        ]
        assert_no_violations(violations)


class TestModelAndLimits:
    def test_model_is_an_explicit_tier(self, agents: DocSet) -> None:
        violations = [
            f"{item.doc.relative}: model {item.frontmatter.get('model')!r} is not a tier"
            for item in agents.parsed
            if "model" in item.frontmatter and item.frontmatter["model"] not in MODEL_TIERS
        ]
        assert_no_violations(violations)

    def test_effort_is_a_valid_level(self, agents: DocSet) -> None:
        violations = [
            f"{item.doc.relative}: effort {item.frontmatter.get('effort')!r}"
            for item in agents.parsed
            if "effort" in item.frontmatter and item.frontmatter["effort"] not in EFFORT_LEVELS
        ]
        assert_no_violations(violations)

    def test_effort_above_medium_is_allowlisted(self, agents: DocSet) -> None:
        violations = [
            f"{item.doc.relative}: effort {item.frontmatter['effort']!r} is not allowlisted"
            for item in agents.parsed
            if item.frontmatter.get("effort") in ABOVE_MEDIUM
            and item.frontmatter.get("name") not in HIGH_EFFORT_AGENTS
        ]
        assert_no_violations(violations)

    def test_high_effort_allowlist_is_current(self, agents: DocSet) -> None:
        above_medium = {
            item.frontmatter.get("name")
            for item in agents.parsed
            if item.frontmatter.get("effort") in ABOVE_MEDIUM
        }
        stale = sorted(set(HIGH_EFFORT_AGENTS) - above_medium)
        assert not stale, f"allowlisted agents no longer above medium: {stale}"

    def test_max_turns_is_a_positive_integer(self, agents: DocSet) -> None:
        violations: list[str] = []
        for item in agents.parsed:
            if "maxTurns" not in item.frontmatter:
                continue
            value = item.frontmatter["maxTurns"]
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                violations.append(f"{item.doc.relative}: maxTurns {value!r}")
        assert_no_violations(violations)

    def test_color_is_one_of_the_valid_values(self, agents: DocSet) -> None:
        violations = [
            f"{item.doc.relative}: color {item.frontmatter['color']!r} is ignored by Claude Code"
            for item in agents.parsed
            if "color" in item.frontmatter and item.frontmatter["color"] not in COLORS
        ]
        assert_no_violations(violations)


class TestTools:
    def test_tools_are_known_names(self, agents: DocSet) -> None:
        violations = [
            f"{item.doc.relative}: unknown tool {entry!r}"
            for item in agents.parsed
            for entry in split_tool_list(item.frontmatter.get("tools"))
            if entry not in KNOWN_TOOLS | STRIPPED_TOOLS
            and not MCP_TOOL.fullmatch(entry)
            and not entry.startswith("Agent")
        ]
        assert_no_violations(violations)

    def test_tools_skip_those_stripped_from_subagents(self, agents: DocSet) -> None:
        violations = [
            f"{item.doc.relative}: {entry} is removed from custom subagents"
            for item in agents.parsed
            for entry in split_tool_list(item.frontmatter.get("tools"))
            if entry in STRIPPED_TOOLS
        ]
        assert_no_violations(violations)

    def test_only_orchestrators_list_agent_with_named_types(self, agents: DocSet) -> None:
        known_agents = {str(item.frontmatter.get("name")) for item in agents.parsed}
        violations: list[str] = []
        for item in agents.parsed:
            for entry in split_tool_list(item.frontmatter.get("tools")):
                if not entry.startswith("Agent"):
                    continue
                match = AGENT_TOOL.fullmatch(entry)
                if match is None:
                    violations.append(f"{item.doc.relative}: bare {entry!r}; write Agent(<type>)")
                    continue
                types = [name.strip() for name in match["types"].split(",") if name.strip()]
                if not types:
                    violations.append(f"{item.doc.relative}: {entry!r} names no dispatch types")
                violations.extend(
                    f"{item.doc.relative}: dispatches unknown agent {name!r}"
                    for name in types
                    if name not in known_agents
                )
        assert_no_violations(violations)


class TestDescription:
    def test_description_has_no_transcript_examples(self, agents: DocSet) -> None:
        transcript = re.compile(r"<example>|^\s*(?:user|assistant):", re.MULTILINE)
        violations = [
            f"{item.doc.relative}: description holds an <example> block or transcript line"
            for item in agents.parsed
            if transcript.search(str(item.frontmatter.get("description", "")))
        ]
        assert_no_violations(violations)


class TestBody:
    def test_no_task_alias_calls(self, agents: DocSet) -> None:
        task_call = re.compile(r"\bTask\(")
        violations = [
            f"{doc.relative}: uses the Task(...) alias; write Agent(...)"
            for doc in agents.docs
            if task_call.search(doc.path.read_text(encoding="utf-8"))
        ]
        assert_no_violations(violations)

    def test_verdict_is_a_bare_line_not_a_heading(self, agents: DocSet) -> None:
        heading = re.compile(r"^#+\s*VERDICT", re.MULTILINE)
        violations = [
            f"{doc.relative}: VERDICT written as a heading"
            for doc in agents.docs
            if heading.search(doc.body)
        ]
        assert_no_violations(violations)

    def test_stack_detected_is_written_with_a_space(self, agents: DocSet) -> None:
        violations = [
            f"{doc.relative}: STACK_DETECTED should read STACK DETECTED"
            for doc in agents.docs
            if "STACK_DETECTED" in doc.body
        ]
        assert_no_violations(violations)
