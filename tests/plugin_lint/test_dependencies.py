from pathlib import Path

import pytest

from .conftest import PLUGINS_DIR, PluginFile, assert_no_violations
from .dispatch_scan import BUILT_IN_AGENTS, dispatch_edges, find_dispatches

AGENT_PLUGINS = {"pipeline-coder": "mz-dev-pipe", "pipeline-researcher": "mz-base"}


def _file(plugin: str, relative: str, text: str) -> PluginFile:
    return PluginFile(path=PLUGINS_DIR / plugin / relative, plugin=plugin, text=text)


class TestDispatchScanner:
    @pytest.mark.parametrize(
        "line",
        [
            "Dispatch a `pipeline-coder` agent per work unit.",
            "Spawn M = N `pipeline-coder` agents in one message.",
            "tools: Read, Agent(pipeline-coder, pipeline-researcher)",
            "Agent(pipeline-coder)",
            'subagent_type: "pipeline-coder"',
        ],
    )
    def test_dispatch_forms_are_detected(self, line: str) -> None:
        assert "pipeline-coder" in {dispatch.name for dispatch in find_dispatches(line)}

    @pytest.mark.parametrize(
        "line",
        [
            "Do not dispatch `pipeline-coder` from this phase.",
            "Never dispatch `pipeline-coder` here.",
            "Pipeline-only agent dispatched by `pipeline-coder`.",
            "For code changes, use `pipeline-coder` instead.",
            "Its output lands in `plugins/mz-dev-pipe/agents/pipeline-coder.md`.",
            'description: "Dispatches `pipeline-coder` for each unit."',
            "| Phase | Agent(s) |",
            "The dispatch prompt from `pipeline-coder` provides these inputs.",
        ],
    )
    def test_mentions_are_not_dispatches(self, line: str) -> None:
        assert find_dispatches(line) == []

    def test_typed_forms_are_marked(self) -> None:
        dispatches = find_dispatches("Agent(pipeline-coder)\nDispatch `pipeline-researcher` now.")
        assert [(d.name, d.typed, d.line) for d in dispatches] == [
            ("pipeline-coder", True, 1),
            ("pipeline-researcher", False, 2),
        ]


class TestEdgeAttribution:
    def test_dispatch_inside_the_agents_own_plugin_is_no_edge(self) -> None:
        source = _file("mz-dev-pipe", "skills/build/SKILL.md", "Dispatch `pipeline-coder`.")
        assert dispatch_edges([source], AGENT_PLUGINS) == []

    def test_shared_file_dispatch_counts_for_each_plugin_naming_it(self) -> None:
        shared = _file("mz-base", "shared/lenses.md", "Dispatch `pipeline-coder` per lens.")
        user = _file("mz-dev-git", "agents/reviewer.md", "Read `<PLUGIN_ROOT>/shared/lenses.md`.")
        bystander = _file("mz-creative", "skills/expert/SKILL.md", "No shared files here.")
        edges = dispatch_edges([shared, user, bystander], AGENT_PLUGINS)
        assert [(edge.source, edge.target) for edge in edges] == [("mz-dev-git", "mz-dev-pipe")]


class TestMarketplace:
    def test_cross_plugin_dispatch_is_declared(
        self,
        plugin_files: tuple[PluginFile, ...],
        agent_plugins: dict[str, str],
        declared_dependencies: dict[str, frozenset[str]],
    ) -> None:
        violations = sorted(
            {
                f"{edge.evidence}: {edge.source} dispatches into {edge.target}, "
                f"which its plugin.json does not list in dependencies"
                for edge in dispatch_edges(plugin_files, agent_plugins)
                if edge.target not in declared_dependencies.get(edge.source, frozenset())
            }
        )
        assert_no_violations(violations)

    def test_declared_dependency_is_used(
        self,
        plugin_files: tuple[PluginFile, ...],
        agent_plugins: dict[str, str],
        declared_dependencies: dict[str, frozenset[str]],
    ) -> None:
        used = {(edge.source, edge.target) for edge in dispatch_edges(plugin_files, agent_plugins)}
        violations = [
            f"plugins/{plugin}/.claude-plugin/plugin.json: no detected dispatch into {dependency}"
            for plugin, dependencies in sorted(declared_dependencies.items())
            for dependency in sorted(dependencies)
            if (plugin, dependency) not in used
        ]
        assert_no_violations(violations)

    def test_dispatched_agent_exists(
        self, plugin_files: tuple[PluginFile, ...], agent_plugins: dict[str, str]
    ) -> None:
        violations = [
            f"{source.relative}:{dispatch.line}: no agent named {dispatch.name!r}"
            for source in plugin_files
            for dispatch in find_dispatches(source.text)
            if dispatch.typed
            and dispatch.name not in agent_plugins
            and dispatch.name not in BUILT_IN_AGENTS
        ]
        assert_no_violations(violations)


def test_scanned_files_include_every_plugin(plugin_files: tuple[PluginFile, ...]) -> None:
    plugins = {path.name for path in PLUGINS_DIR.iterdir() if (path / ".claude-plugin").is_dir()}
    assert {source.plugin for source in plugin_files} == plugins
    assert all(isinstance(source.path, Path) for source in plugin_files)
