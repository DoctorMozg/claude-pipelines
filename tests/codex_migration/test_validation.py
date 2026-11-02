from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from mozg_pipelines.models import (
    Catalog,
    HookEvent,
    HookEventMapping,
    HookScriptSpec,
    HookSpec,
    ProviderPolicy,
    RoleResourceSpec,
    SkillSpec,
)
from mozg_pipelines.validation import validate_catalog, validate_package

if TYPE_CHECKING:
    from tests.codex_migration.conftest import SourceTree

_DEFAULT_SKILL_BODY = "Provider-neutral instructions.\n"


def _write_manifest(package_root: Path, name: str = "mozg-pipelines") -> None:
    (package_root / "plugin.json").write_text(
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": name,
                "version": "0.49.0",
                "description": "Provider-native development and research pipelines for Codex.",
                "author": {"name": "DoctorMozg"},
            }
        ),
        encoding="utf-8",
    )


def test_valid_catalog_has_no_issues(
    tmp_path: Path,
    valid_catalog: Catalog,
    write_skill: Callable[[Path, str], None],
) -> None:
    write_skill(tmp_path / valid_catalog.skills[0].source / "SKILL.md", _DEFAULT_SKILL_BODY)
    role_path = tmp_path / valid_catalog.roles[0].source
    role_path.parent.mkdir(parents=True, exist_ok=True)
    role_path.write_text("Role contract.\n", encoding="utf-8")

    report = validate_catalog(valid_catalog, tmp_path)

    assert report.is_valid is True
    assert report.issues == ()


def test_catalog_validation_reports_missing_role(
    tmp_path: Path,
    write_skill: Callable[[Path, str], None],
) -> None:
    catalog = Catalog(
        schema_version=1,
        suite_name="mozg-pipelines",
        skills=(
            SkillSpec(
                name="ask",
                plugin="mz-dev-pipe",
                source="plugins/mz-dev-pipe/skills/ask",
                roles=("pipeline-researcher",),
            ),
        ),
    )
    write_skill(tmp_path / catalog.skills[0].source / "SKILL.md", _DEFAULT_SKILL_BODY)

    report = validate_catalog(catalog, tmp_path)

    assert report.is_valid is False
    assert tuple((issue.code, issue.subject) for issue in report.issues) == (
        ("missing-role", "pipeline-researcher"),
    )


def test_catalog_validation_rejects_symlink_escape(
    tmp_path: Path,
    valid_catalog: Catalog,
    write_skill: Callable[[Path, str], None],
) -> None:
    source_root = tmp_path / "source"
    outside_role = tmp_path / "outside-role.md"
    outside_role.write_text("Outside role.\n", encoding="utf-8")
    role_path = source_root / valid_catalog.roles[0].source
    role_path.parent.mkdir(parents=True)
    role_path.symlink_to(outside_role)
    write_skill(
        source_root / valid_catalog.skills[0].source / "SKILL.md",
        _DEFAULT_SKILL_BODY,
    )

    report = validate_catalog(valid_catalog, source_root)

    assert tuple((issue.code, issue.subject) for issue in report.issues) == (
        ("path-escape", "pipeline-researcher"),
    )


class TestSymlinkedSources:
    def test_links_inside_the_marketplace_are_accepted(
        self, source_tree: SourceTree, valid_catalog: Catalog
    ) -> None:
        source_tree.link("references/scope.md", source_tree.shared / "scope.md")
        source_tree.link("shared", source_tree.shared)

        report = validate_catalog(valid_catalog, source_tree.root)

        assert report.issues == ()

    def test_link_to_missing_target_is_reported(
        self, source_tree: SourceTree, valid_catalog: Catalog
    ) -> None:
        source_tree.link("references/gone.md", source_tree.shared / "gone.md")

        report = validate_catalog(valid_catalog, source_tree.root)

        assert tuple((issue.code, issue.subject) for issue in report.issues) == (
            ("missing-symlink-target", "ask"),
        )

    def test_escape_inside_a_linked_directory_is_reported(
        self, source_tree: SourceTree, valid_catalog: Catalog, tmp_path: Path
    ) -> None:
        outside = tmp_path / "outside.md"
        outside.write_text("Outside.\n", encoding="utf-8")
        (source_tree.shared / "escape.md").symlink_to(outside)
        source_tree.link("shared", source_tree.shared)

        report = validate_catalog(valid_catalog, source_tree.root)

        assert tuple((issue.code, issue.subject) for issue in report.issues) == (
            ("path-escape", "ask"),
        )

    def test_link_back_to_an_ancestor_is_reported_as_a_cycle(
        self, source_tree: SourceTree, valid_catalog: Catalog
    ) -> None:
        source_tree.link("loop", source_tree.skill)

        report = validate_catalog(valid_catalog, source_tree.root)

        assert tuple((issue.code, issue.subject) for issue in report.issues) == (
            ("symlink-cycle", "ask"),
        )

    def test_link_chain_that_loops_is_reported_as_a_cycle(
        self, source_tree: SourceTree, valid_catalog: Catalog
    ) -> None:
        source_tree.link("a.md", source_tree.skill / "b.md")
        source_tree.link("b.md", source_tree.skill / "a.md")

        report = validate_catalog(valid_catalog, source_tree.root)

        assert tuple((issue.code, issue.subject) for issue in report.issues) == (
            ("symlink-cycle", "ask"),
            ("symlink-cycle", "ask"),
        )

    def test_two_links_to_one_directory_are_not_a_cycle(
        self, source_tree: SourceTree, valid_catalog: Catalog
    ) -> None:
        source_tree.link("shared", source_tree.shared)
        source_tree.link("references/shared", source_tree.shared)

        assert validate_catalog(valid_catalog, source_tree.root).issues == ()


class TestSharedRoot:
    def test_missing_shared_folder_is_reported(
        self, source_tree: SourceTree, valid_catalog: Catalog
    ) -> None:
        catalog = valid_catalog.model_copy(update={"shared_root": "plugins/mz-dev-pipe/shared"})

        report = validate_catalog(catalog, source_tree.root)

        assert tuple((issue.code, issue.subject) for issue in report.issues) == (
            ("missing-shared-source", "shared"),
        )

    def test_escape_inside_the_shared_folder_is_reported(
        self, source_tree: SourceTree, valid_catalog: Catalog, tmp_path: Path
    ) -> None:
        outside = tmp_path / "outside.md"
        outside.write_text("Outside.\n", encoding="utf-8")
        (source_tree.shared / "escape.md").symlink_to(outside)
        shared_root = source_tree.link_plugin_shared("mz-dev-pipe")
        catalog = valid_catalog.model_copy(update={"shared_root": shared_root})

        report = validate_catalog(catalog, source_tree.root)

        assert tuple((issue.code, issue.subject) for issue in report.issues) == (
            ("path-escape", "shared"),
        )


def test_package_validation_reports_each_forbidden_token(
    tmp_path: Path,
    valid_catalog: Catalog,
    codex_policy: ProviderPolicy,
    write_skill: Callable[[Path, str], None],
) -> None:
    package_root = tmp_path / "package"
    write_skill(
        package_root / "skills/ask/SKILL.md",
        "Use model: sonnet.\nRead phases/research.md.\n",
    )
    phase_path = package_root / "skills/ask/phases/research.md"
    phase_path.parent.mkdir(parents=True)
    phase_path.write_text("Call TaskCreate before research.\n", encoding="utf-8")
    _write_manifest(package_root)

    report = validate_package(valid_catalog, codex_policy, package_root)

    assert tuple((issue.code, issue.subject) for issue in report.issues) == (
        ("forbidden-token", "model: sonnet"),
        ("forbidden-token", "TaskCreate"),
    )


def test_package_validation_ignores_marked_provenance_examples(
    tmp_path: Path,
    valid_catalog: Catalog,
    codex_policy: ProviderPolicy,
    write_skill: Callable[[Path, str], None],
) -> None:
    package_root = tmp_path / "package"
    write_skill(
        package_root / "skills/ask/SKILL.md",
        "\n".join(
            (
                codex_policy.provenance_markers.start,
                "Claude used model: sonnet and TaskCreate.",
                codex_policy.provenance_markers.end,
                "Use provider-neutral execution.",
            )
        ),
    )
    _write_manifest(package_root)

    report = validate_package(valid_catalog, codex_policy, package_root)

    assert report.is_valid is True
    assert report.issues == ()


def test_package_validation_scans_executable_scripts(
    tmp_path: Path,
    valid_catalog: Catalog,
    codex_policy: ProviderPolicy,
    write_skill: Callable[[Path, str], None],
) -> None:
    package_root = tmp_path / "package"
    write_skill(package_root / "skills/ask/SKILL.md", _DEFAULT_SKILL_BODY)
    script_path = package_root / "skills/ask/scripts/run.sh"
    script_path.parent.mkdir(parents=True)
    script_path.write_text("TaskCreate must run first.\n", encoding="utf-8")
    _write_manifest(package_root)

    report = validate_package(valid_catalog, codex_policy, package_root)

    assert tuple((issue.code, issue.subject) for issue in report.issues) == (
        ("forbidden-token", "TaskCreate"),
    )


def test_package_validation_rejects_invalid_manifest(
    tmp_path: Path,
    valid_catalog: Catalog,
    codex_policy: ProviderPolicy,
    write_skill: Callable[[Path, str], None],
) -> None:
    package_root = tmp_path / "package"
    write_skill(package_root / "skills/ask/SKILL.md", _DEFAULT_SKILL_BODY)
    (package_root / "plugin.json").write_text('{"name":"mozg-pipelines"}', encoding="utf-8")

    report = validate_package(valid_catalog, codex_policy, package_root)

    assert tuple(issue.code for issue in report.issues) == ("invalid-manifest",)


def test_package_validation_requires_declared_role_resource(
    tmp_path: Path,
    valid_catalog: Catalog,
    codex_policy: ProviderPolicy,
    write_skill: Callable[[Path, str], None],
) -> None:
    catalog = valid_catalog.model_copy(
        update={
            "role_resources": (
                RoleResourceSpec(
                    role="pipeline-researcher",
                    skill="ask",
                    target="skills/ask/references/roles/pipeline-researcher.md",
                ),
            )
        }
    )
    package_root = tmp_path / "package"
    write_skill(package_root / "skills/ask/SKILL.md", _DEFAULT_SKILL_BODY)
    _write_manifest(package_root)

    report = validate_package(catalog, codex_policy, package_root)

    assert tuple((issue.code, issue.path) for issue in report.issues) == (
        ("missing-role-resource", "skills/ask/references/roles/pipeline-researcher.md"),
    )


def test_catalog_validation_requires_declared_hook_sources(
    tmp_path: Path,
    valid_catalog: Catalog,
    write_role: Callable[[Path], None],
    write_skill: Callable[[Path, str], None],
) -> None:
    catalog = valid_catalog.model_copy(
        update={
            "hooks": (
                HookSpec(
                    source="plugins/mz-dev-pipe/hooks/hooks.json",
                    target="hooks/hooks.json",
                    events=(
                        HookEventMapping(
                            source_event=HookEvent.SESSION_START,
                            target_event=HookEvent.SESSION_START,
                        ),
                    ),
                    scripts=(
                        HookScriptSpec(
                            source="plugins/mz-dev-pipe/scripts/session-start.sh",
                            target="scripts/session-start.sh",
                        ),
                    ),
                ),
            )
        }
    )
    write_skill(tmp_path / catalog.skills[0].source / "SKILL.md", _DEFAULT_SKILL_BODY)
    write_role(tmp_path / catalog.roles[0].source)

    report = validate_catalog(catalog, tmp_path)

    assert tuple((issue.code, issue.path) for issue in report.issues) == (
        ("missing-hook-source", "plugins/mz-dev-pipe/hooks/hooks.json"),
        ("missing-hook-script-source", "plugins/mz-dev-pipe/scripts/session-start.sh"),
    )


def test_package_validation_requires_declared_hook_outputs(
    tmp_path: Path,
    valid_catalog: Catalog,
    codex_policy: ProviderPolicy,
    write_skill: Callable[[Path, str], None],
) -> None:
    catalog = valid_catalog.model_copy(
        update={
            "hooks": (
                HookSpec(
                    source="plugins/mz-dev-pipe/hooks/hooks.json",
                    target="hooks/hooks.json",
                    scripts=(
                        HookScriptSpec(
                            source="plugins/mz-dev-pipe/scripts/session-start.sh",
                            target="scripts/session-start.sh",
                        ),
                    ),
                ),
            )
        }
    )
    package_root = tmp_path / "package"
    write_skill(package_root / "skills/ask/SKILL.md", _DEFAULT_SKILL_BODY)
    _write_manifest(package_root)

    report = validate_package(catalog, codex_policy, package_root)

    assert tuple((issue.code, issue.path) for issue in report.issues) == (
        ("missing-rendered-hook", "hooks/hooks.json"),
        ("missing-rendered-hook-script", "scripts/session-start.sh"),
    )
