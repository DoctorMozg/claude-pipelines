from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from mozg_pipelines.models import (
    ExactTransformSpec,
    HookEvent,
    HookEventMapping,
    HookScriptAdapter,
    HookSpec,
    RoleResourceSpec,
    ScriptSpec,
)
from mozg_pipelines.rendering import (
    CodexPackageSpec,
    RenderError,
    RenderFailure,
    render_codex_package,
)
from mozg_pipelines.validation import validate_package

if TYPE_CHECKING:
    from tests.codex_migration.conftest import SourceTree


def test_renderer_builds_portable_plugin_and_embedded_role_resources(
    tmp_path: Path,
    package_spec_factory: Callable[[Path, str], CodexPackageSpec],
    write_role: Callable[[Path], None],
) -> None:
    spec = package_spec_factory(tmp_path, "0.49.0")
    catalog = spec.catalog.model_copy(
        update={
            "transforms": (
                ExactTransformSpec(
                    source="plugins/mz-dev-pipe/skills/ask/phases/research.md",
                    match="Research the requested topic.",
                    replacement="Review the user's request.",
                ),
            ),
            "role_resources": (
                RoleResourceSpec(
                    role="pipeline-researcher",
                    skill="ask",
                    target="skills/ask/references/roles/pipeline-researcher.md",
                ),
            ),
        }
    )
    spec = spec.model_copy(update={"catalog": catalog})
    skill_root = spec.source_root / spec.catalog.skills[0].source
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        """---
name: ask
description: Research a codebase question.
argument-hint: <question>
model: sonnet
allowed-tools: Agent, Read, TaskCreate
---

Use $ARGUMENTS. AskUserQuestion before TaskCreate.
Use WebSearch and WebFetch. Read ${CLAUDE_PLUGIN_ROOT}, CLAUDE.md, and .claude/rules.
Bundled files live under ${CLAUDE_SKILL_DIR}/references.
Coordinate Agent(s), then delegate through Agent(pipeline-researcher).
""",
        encoding="utf-8",
    )
    phase_path = skill_root / "phases/research.md"
    phase_path.parent.mkdir()
    phase_path.write_text("Research the requested topic.\n", encoding="utf-8")
    write_role(spec.source_root / spec.catalog.roles[0].source)

    result = render_codex_package(spec)

    assert result.package_root == spec.package_root
    assert result.skill_paths == (Path("skills/ask/SKILL.md"),)
    assert result.role_resource_paths == (
        Path("skills/ask/references/roles/pipeline-researcher.md"),
    )
    manifest: object = json.loads((spec.package_root / "plugin.json").read_text(encoding="utf-8"))
    assert manifest == {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "mozg-pipelines",
        "version": "0.49.0",
        "description": "Provider-native development and research pipelines for Codex.",
        "author": {"name": "DoctorMozg"},
        "extensions": {
            "com.openai": {
                "interface": {
                    "displayName": "Mozg Pipelines",
                    "shortDescription": "Use Mozg Pipelines skills in Codex.",
                    "longDescription": (
                        "Provider-native development and research pipelines for Codex."
                    ),
                    "developerName": "DoctorMozg",
                    "category": "Developer Tools",
                    "capabilities": ["Interactive", "Write"],
                    "defaultPrompt": ["Help me choose a Mozg pipeline."],
                }
            }
        },
    }
    rendered_skill = (spec.package_root / result.skill_paths[0]).read_text(encoding="utf-8")
    assert rendered_skill.startswith(
        '---\nname: "ask"\ndescription: "Research a codebase question."\n---\n'
    )
    assert "argument-hint" not in rendered_skill
    assert "model: sonnet" not in rendered_skill
    assert "allowed-tools" not in rendered_skill
    assert (spec.package_root / "skills/ask/phases/research.md").read_text(
        encoding="utf-8"
    ) == "Review the user's request.\n"
    assert "the user's request" in rendered_skill
    assert "ask the user directly" in rendered_skill
    assert "record the task in the active goal" in rendered_skill
    assert "web search" in rendered_skill
    assert "web fetch" in rendered_skill
    assert "${PLUGIN_ROOT}" in rendered_skill
    assert "<directory containing this SKILL.md>/references" in rendered_skill
    assert "AGENTS.md" in rendered_skill
    assert ".codex/rules" in rendered_skill
    assert "Coordinate Codex subagent(s)" in rendered_skill
    assert (
        "delegate to a Codex subagent using the pipeline-researcher role prompt" in rendered_skill
    )
    assert "$ARGUMENTS" not in rendered_skill
    assert "AskUserQuestion" not in rendered_skill
    assert "TaskCreate" not in rendered_skill
    assert "WebSearch" not in rendered_skill
    assert "WebFetch" not in rendered_skill
    assert "${CLAUDE_PLUGIN_ROOT}" not in rendered_skill
    assert "${CLAUDE_SKILL_DIR}" not in rendered_skill
    assert "CLAUDE.md" not in rendered_skill
    assert ".claude/rules" not in rendered_skill
    assert "Agent(pipeline-researcher)" not in rendered_skill
    assert (spec.package_root / result.role_resource_paths[0]).read_text(
        encoding="utf-8"
    ) == "Research the repository and return evidence-backed findings.\n"
    assert not (spec.package_root / "agents").exists()
    assert validate_package(spec.catalog, spec.policy, spec.package_root).is_valid is True


def test_renderer_refuses_to_replace_an_existing_target(
    tmp_path: Path,
    package_spec_factory: Callable[[Path, str], CodexPackageSpec],
) -> None:
    spec = package_spec_factory(tmp_path, "0.49.0")
    spec.package_root.mkdir(parents=True)

    with pytest.raises(RenderError) as caught:
        render_codex_package(spec)

    assert caught.value.kind is RenderFailure.TARGET_EXISTS


type HookPackageBuilder = Callable[
    [tuple[HookEventMapping, ...], dict[str, object]], CodexPackageSpec
]

_MEMORY_SCRIPT_SOURCES = {
    "journal-capture.sh": "legacy journal script\n",
    "memory-inject.sh": 'echo "${CLAUDE_PLUGIN_ROOT}"\n',
}


def _command(script: str) -> dict[str, object]:
    return {"command": f"${{CLAUDE_PLUGIN_ROOT}}/scripts/{script}", "type": "command"}


@pytest.fixture
def hook_package(
    tmp_path: Path,
    package_spec_factory: Callable[[Path, str], CodexPackageSpec],
    write_role: Callable[[Path], None],
    write_skill: Callable[[Path, str], None],
) -> HookPackageBuilder:
    def build(
        events: tuple[HookEventMapping, ...], source_hooks: dict[str, object]
    ) -> CodexPackageSpec:
        spec = package_spec_factory(tmp_path, "0.49.0")
        hook = HookSpec(
            source="plugins/mz-memory/hooks/hooks.json",
            target="hooks/hooks.json",
            events=events,
        )
        scripts = (
            ScriptSpec(
                source="plugins/mz-memory/scripts/journal-capture.sh",
                target="scripts/journal-capture.sh",
                adapter=HookScriptAdapter.USER_PROMPT_JOURNAL,
            ),
            ScriptSpec(
                source="plugins/mz-memory/scripts/memory-inject.sh",
                target="scripts/memory-inject.sh",
            ),
        )
        catalog = spec.catalog.model_copy(update={"hooks": (hook,), "scripts": scripts})
        spec = spec.model_copy(update={"catalog": catalog})
        write_skill(
            spec.source_root / spec.catalog.skills[0].source / "SKILL.md",
            "Use provider-neutral execution.\n",
        )
        write_role(spec.source_root / spec.catalog.roles[0].source)

        source_hook = spec.source_root / hook.source
        source_hook.parent.mkdir(parents=True)
        source_hook.write_text(json.dumps({"hooks": source_hooks}), encoding="utf-8")
        scripts_dir = spec.source_root / "plugins/mz-memory/scripts"
        scripts_dir.mkdir(parents=True)
        for script, contents in _MEMORY_SCRIPT_SOURCES.items():
            path = scripts_dir / script
            path.write_text(contents, encoding="utf-8")
            path.chmod(0o755)
        return spec

    return build


def test_renderer_adapts_hook_events_and_scripts_for_codex(
    hook_package: HookPackageBuilder,
) -> None:
    spec = hook_package(
        (
            HookEventMapping(
                source_event=HookEvent.POST_TOOL_USE,
                target_event=HookEvent.USER_PROMPT_SUBMIT,
            ),
            HookEventMapping(source_event=HookEvent.PRE_COMPACT, target_event=None),
        ),
        {
            "PostToolUse": [
                {"matcher": "AskUserQuestion", "hooks": [_command("journal-capture.sh")]}
            ],
            "PreCompact": [{"hooks": [_command("handover.sh")]}],
            "SessionStart": [
                {
                    "matcher": "startup|clear|compact",
                    "hooks": [{**_command("memory-inject.sh"), "once": True}],
                }
            ],
        },
    )

    result = render_codex_package(spec)

    assert result.hook_paths == (Path("hooks/hooks.json"),)
    assert result.script_paths == (
        Path("scripts/journal-capture.sh"),
        Path("scripts/memory-inject.sh"),
    )
    rendered_hooks: object = json.loads(
        (spec.package_root / "hooks/hooks.json").read_text(encoding="utf-8")
    )
    assert rendered_hooks == {
        "hooks": {
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "command": "${PLUGIN_ROOT}/scripts/journal-capture.sh",
                            "type": "command",
                        }
                    ]
                }
            ],
            "SessionStart": [
                {
                    "matcher": "startup|clear|compact",
                    "hooks": [
                        {
                            "command": "${PLUGIN_ROOT}/scripts/memory-inject.sh",
                            "type": "command",
                        }
                    ],
                }
            ],
        }
    }
    journal_script = (spec.package_root / "scripts/journal-capture.sh").read_text(encoding="utf-8")
    assert "UserPromptSubmit" in journal_script
    assert ".prompt" in journal_script
    assert "AskUserQuestion" not in journal_script
    assert (spec.package_root / "scripts/memory-inject.sh").read_text(encoding="utf-8") == (
        'echo "${PLUGIN_ROOT}"\n'
    )
    assert validate_package(spec.catalog, spec.policy, spec.package_root).is_valid is True


def test_renderer_rejects_unsupported_hook_event_move(
    hook_package: HookPackageBuilder,
) -> None:
    spec = hook_package(
        (
            HookEventMapping(
                source_event=HookEvent.POST_COMPACT, target_event=HookEvent.SESSION_START
            ),
        ),
        {"PostCompact": [{"hooks": [_command("memory-inject.sh")]}]},
    )

    with pytest.raises(RenderError, match="PostCompact -> SessionStart") as caught:
        render_codex_package(spec)

    assert caught.value.kind is RenderFailure.INVALID_SOURCE
    assert not spec.package_root.exists()


def test_renderer_ships_scripts_of_a_package_without_hooks(
    tmp_path: Path,
    package_spec_factory: Callable[[Path, str], CodexPackageSpec],
    write_role: Callable[[Path], None],
    write_skill: Callable[[Path, str], None],
) -> None:
    spec = package_spec_factory(tmp_path, "0.49.0")
    script = ScriptSpec(source="plugins/mz-creative/scripts/check.sh", target="scripts/check.sh")
    spec = spec.model_copy(
        update={"catalog": spec.catalog.model_copy(update={"scripts": (script,)})}
    )
    write_skill(spec.source_root / spec.catalog.skills[0].source / "SKILL.md", "Run the check.\n")
    write_role(spec.source_root / spec.catalog.roles[0].source)
    source = spec.source_root / script.source
    source.parent.mkdir(parents=True)
    source.write_text('exec "${CLAUDE_PLUGIN_ROOT}/lib.sh"\n', encoding="utf-8")
    source.chmod(0o755)

    result = render_codex_package(spec)

    rendered = spec.package_root / script.target
    assert (result.hook_paths, result.script_paths) == ((), (Path("scripts/check.sh"),))
    assert rendered.read_text(encoding="utf-8") == 'exec "${PLUGIN_ROOT}/lib.sh"\n'
    assert rendered.stat().st_mode & 0o111
    assert validate_package(spec.catalog, spec.policy, spec.package_root).is_valid is True


def test_renderer_writes_dependency_contract_for_external_role_guidance(
    tmp_path: Path,
    package_spec_factory: Callable[[Path, str], CodexPackageSpec],
    write_role: Callable[[Path], None],
    write_skill: Callable[[Path, str], None],
) -> None:
    spec = package_spec_factory(tmp_path, "0.49.0")
    spec = spec.model_copy(
        update={"catalog": spec.catalog.model_copy(update={"dependencies": ("mz-dev-pipe",)})}
    )
    skill_root = spec.source_root / spec.catalog.skills[0].source
    write_skill(skill_root / "SKILL.md", "Delegate through Agent(external-researcher).\n")
    write_role(spec.source_root / spec.catalog.roles[0].source)

    result = render_codex_package(spec)

    assert result.dependency_contract_path == Path("mozg-dependencies.json")
    contract: object = json.loads(
        (spec.package_root / result.dependency_contract_path).read_text(encoding="utf-8")
    )
    assert contract == {
        "schema_version": 1,
        "requires": [
            {
                "plugin": "mz-dev-pipe",
                "installation": (
                    "Install and enable mz-dev-pipe before starting a new Codex session."
                ),
            }
        ],
    }
    rendered_skill = (spec.package_root / result.skill_paths[0]).read_text(encoding="utf-8")
    assert "external-researcher task" in rendered_skill
    assert "mozg-dependencies.json" in rendered_skill
    assert "Agent(external-researcher)" not in rendered_skill


def test_renderer_tolerates_non_yaml_description_frontmatter(
    tmp_path: Path,
    package_spec_factory: Callable[[Path, str], CodexPackageSpec],
    write_role: Callable[[Path], None],
) -> None:
    spec = package_spec_factory(tmp_path, "0.49.0")
    skill_root = spec.source_root / spec.catalog.skills[0].source
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        """---
name: ask
description: Research a question. Triggers: \"ask\".
---

Use provider-neutral execution.
""",
        encoding="utf-8",
    )
    write_role(spec.source_root / spec.catalog.roles[0].source)

    result = render_codex_package(spec)

    assert (
        (spec.package_root / result.skill_paths[0])
        .read_text(encoding="utf-8")
        .startswith(
            '---\nname: "ask"\ndescription: "Research a question. Triggers: \\"ask\\"."\n---\n'
        )
    )


class TestSymlinkedSources:
    @pytest.fixture
    def spec(
        self,
        tmp_path: Path,
        source_tree: SourceTree,
        package_spec_factory: Callable[[Path, str], CodexPackageSpec],
    ) -> CodexPackageSpec:
        return package_spec_factory(tmp_path, "0.49.0")

    def test_linked_file_is_copied_as_adapted_content(
        self, spec: CodexPackageSpec, source_tree: SourceTree
    ) -> None:
        source_tree.link("references/scope.md", source_tree.shared / "scope.md")

        render_codex_package(spec)

        rendered = spec.package_root / "skills/ask/references/scope.md"
        assert not rendered.is_symlink()
        assert rendered.read_text(encoding="utf-8") == "Scope from ${PLUGIN_ROOT}.\n"

    def test_linked_directory_is_copied_as_a_real_tree(
        self, spec: CodexPackageSpec, source_tree: SourceTree
    ) -> None:
        source_tree.link("shared", source_tree.shared)

        render_codex_package(spec)

        rendered = spec.package_root / "skills/ask/shared"
        assert not rendered.is_symlink()
        assert (rendered / "nested/deep.md").read_text(encoding="utf-8") == "Deep reference.\n"

    def test_link_outside_the_marketplace_blocks_rendering(
        self, spec: CodexPackageSpec, source_tree: SourceTree, tmp_path: Path
    ) -> None:
        outside = tmp_path / "outside.md"
        outside.write_text("Outside.\n", encoding="utf-8")
        source_tree.link("references/outside.md", outside)

        with pytest.raises(RenderError, match="outside the source root") as caught:
            render_codex_package(spec)

        assert caught.value.kind is RenderFailure.INVALID_SOURCE
        assert not spec.package_root.exists()

    def test_link_to_missing_target_blocks_rendering(
        self, spec: CodexPackageSpec, source_tree: SourceTree
    ) -> None:
        source_tree.link("references/gone.md", source_tree.shared / "gone.md")

        with pytest.raises(RenderError, match="target does not exist") as caught:
            render_codex_package(spec)

        assert caught.value.kind is RenderFailure.INVALID_SOURCE
        assert not spec.package_root.exists()


class TestSharedFolder:
    @pytest.fixture
    def spec(
        self,
        tmp_path: Path,
        source_tree: SourceTree,
        package_spec_factory: Callable[[Path, str], CodexPackageSpec],
    ) -> CodexPackageSpec:
        return package_spec_factory(tmp_path, "0.49.0")

    def test_linked_shared_folder_renders_at_package_root(
        self, spec: CodexPackageSpec, source_tree: SourceTree
    ) -> None:
        shared_root = source_tree.link_plugin_shared("mz-dev-pipe")
        catalog = spec.catalog.model_copy(update={"shared_root": shared_root})

        result = render_codex_package(spec.model_copy(update={"catalog": catalog}))

        rendered = spec.package_root / "shared"
        assert result.shared_path == Path("shared")
        assert not rendered.is_symlink()
        assert (rendered / "scope.md").read_text(encoding="utf-8") == "Scope from ${PLUGIN_ROOT}.\n"
        assert (rendered / "nested/deep.md").is_file()

    def test_catalog_without_shared_root_renders_no_shared_folder(
        self, spec: CodexPackageSpec
    ) -> None:
        result = render_codex_package(spec)

        assert result.shared_path is None
        assert not (spec.package_root / "shared").exists()
