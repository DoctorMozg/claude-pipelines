import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from mozg_pipelines.inventory import (
    MigrationInventoryError,
    MigrationPlanLoadError,
    MigrationPlanLoadFailure,
    build_codex_package_spec,
    discover_packages,
    load_migration_plan,
    validate_migration_plan,
)
from mozg_pipelines.models import (
    HookEvent,
    HookScriptAdapter,
    MigrationPlan,
    PackageDisposition,
    PackagePlanSpec,
)
from mozg_pipelines.rendering import render_codex_package

_REPOSITORY_ROOT = Path(__file__).parents[2]
_PLAN_PATH = _REPOSITORY_ROOT / "data/codex_migration.toml"
# Each dependent package names the packages that own the agents and files it dispatches.
_EXPECTED_DEPENDENCIES = {
    "mz-dev-pipe": ("mz-base",),
    "mz-research-pipe": ("mz-base", "mz-dev-pipe"),
    "mz-dev-git": ("mz-base", "mz-dev-pipe"),
    "mz-biz-outreach": ("mz-creative",),
    "mz-creative": ("mz-base",),
}


def test_migration_plan_covers_the_canonical_marketplace() -> None:
    plan = load_migration_plan(_PLAN_PATH)

    report = validate_migration_plan(plan, _REPOSITORY_ROOT)
    packages = discover_packages(plan, _REPOSITORY_ROOT)

    assert report.is_valid is True
    assert tuple(package.plan.name for package in packages) == (
        "mz-base",
        "mz-dev-pipe",
        "mz-research-pipe",
        "mz-dev-git",
        "mz-biz-outreach",
        "mz-job-outreach",
        "mz-creative",
        "mz-funny",
        "mz-memory",
        "mz-design",
        "mz-knowledge",
        "mz-gov",
    )
    assert sum(len(package.skill_sources) for package in packages) == 52
    assert sum(len(package.role_sources) for package in packages) == 116
    assert not any(package.plan.disposition is PackageDisposition.BLOCKED for package in packages)
    assert {
        package.plan.name: package.plan.dependencies
        for package in packages
        if package.plan.disposition is PackageDisposition.DEPENDENT
    } == _EXPECTED_DEPENDENCIES
    assert {package.source_manifest.version for package in packages} == {"0.49.0"}


def test_migration_plan_rejects_marketplace_membership_drift() -> None:
    plan = load_migration_plan(_PLAN_PATH)
    changed_plan = plan.model_copy(update={"packages": plan.packages[1:]})

    report = validate_migration_plan(changed_plan, _REPOSITORY_ROOT)

    assert tuple(issue.code for issue in report.issues) == ("marketplace-plan-mismatch",)


def test_migration_plan_excludes_skills_that_cannot_run_under_codex() -> None:
    plan = load_migration_plan(_PLAN_PATH)

    packages = discover_packages(plan, _REPOSITORY_ROOT)

    assert {
        package.plan.name: package.plan.excluded_skills
        for package in packages
        if package.plan.excluded_skills
    } == {"mz-base": ("init-rules",), "mz-dev-pipe": ("optimize",)}
    skill_names = {
        Path(source).parent.name for package in packages for source in package.skill_sources
    }
    assert skill_names.isdisjoint({"init-rules", "optimize"})


def test_migration_plan_rejects_unknown_excluded_skill() -> None:
    plan = load_migration_plan(_PLAN_PATH)
    stale_package = plan.packages[0].model_copy(update={"excluded_skills": ("no-such-skill",)})
    changed_plan = plan.model_copy(update={"packages": (stale_package, *plan.packages[1:])})

    report = validate_migration_plan(changed_plan, _REPOSITORY_ROOT)

    assert tuple(issue.code for issue in report.issues) == ("unknown-excluded-skill",)
    with pytest.raises(MigrationInventoryError, match="no-such-skill"):
        discover_packages(changed_plan, _REPOSITORY_ROOT)


def test_package_plan_rejects_duplicate_excluded_skills() -> None:
    with pytest.raises(ValidationError, match="duplicate excluded skill: optimize"):
        PackagePlanSpec(
            name="mz-dev-pipe",
            disposition=PackageDisposition.READY,
            excluded_skills=("optimize", "optimize"),
        )


def _write_marketplace(root: Path, *names: str) -> MigrationPlan:
    (root / ".claude-plugin").mkdir()
    plugins = [{"name": name, "source": f"./{name}"} for name in names]
    (root / ".claude-plugin/marketplace.json").write_text(
        json.dumps({"owner": {"name": "Owner"}, "plugins": plugins}), encoding="utf-8"
    )
    for name in names:
        manifest_dir = root / name / ".claude-plugin"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "plugin.json").write_text(
            json.dumps({"name": name, "version": "1.0.0", "description": "Example."}),
            encoding="utf-8",
        )
    return MigrationPlan(
        schema_version=1,
        source_marketplace=".claude-plugin/marketplace.json",
        packages=tuple(
            PackagePlanSpec(name=name, disposition=PackageDisposition.READY) for name in names
        ),
    )


def test_migration_plan_reads_manifest_only_from_claude_plugin_dir(tmp_path: Path) -> None:
    plan = _write_marketplace(tmp_path, "mz-x")
    manifest = tmp_path / "mz-x/.claude-plugin/plugin.json"
    legacy_manifest = manifest.rename(tmp_path / "mz-x/plugin.json")

    legacy_report = validate_migration_plan(plan, tmp_path)
    legacy_manifest.rename(manifest)
    packages = discover_packages(plan, tmp_path)

    assert tuple(issue.code for issue in legacy_report.issues) == ("invalid-package-manifest",)
    assert packages[0].source_manifest.version == "1.0.0"


class TestSharedFolderDiscovery:
    def test_real_and_linked_shared_folders_reach_the_catalog(self, tmp_path: Path) -> None:
        plan = _write_marketplace(tmp_path, "mz-base", "mz-x")
        (tmp_path / "mz-base/shared").mkdir()
        (tmp_path / "mz-base/shared/scope.md").write_text("Scope.\n", encoding="utf-8")
        (tmp_path / "mz-x/shared").symlink_to("../mz-base/shared", target_is_directory=True)

        packages = discover_packages(plan, tmp_path)
        specs = tuple(
            build_codex_package_spec(package, tmp_path, tmp_path / "out" / package.plan.name)
            for package in packages
        )

        assert tuple(package.shared_root for package in packages) == (
            "mz-base/shared",
            "mz-x/shared",
        )
        assert tuple(spec.catalog.shared_root for spec in specs) == (
            "mz-base/shared",
            "mz-x/shared",
        )

    def test_plugin_without_shared_folder_has_no_shared_root(self, tmp_path: Path) -> None:
        plan = _write_marketplace(tmp_path, "mz-x")

        package = discover_packages(plan, tmp_path)[0]
        spec = build_codex_package_spec(package, tmp_path, tmp_path / "out")

        assert package.shared_root is None
        assert spec.catalog.shared_root is None

    def test_dangling_shared_link_is_kept_for_the_validator_to_reject(self, tmp_path: Path) -> None:
        plan = _write_marketplace(tmp_path, "mz-x")
        (tmp_path / "mz-x/shared").symlink_to("../mz-base/shared", target_is_directory=True)

        assert discover_packages(plan, tmp_path)[0].shared_root == "mz-x/shared"

    def test_shared_file_in_place_of_a_folder_is_ignored(self, tmp_path: Path) -> None:
        plan = _write_marketplace(tmp_path, "mz-x")
        (tmp_path / "mz-x/shared").write_text("not a folder\n", encoding="utf-8")

        assert discover_packages(plan, tmp_path)[0].shared_root is None


def test_load_migration_plan_reports_missing_file(tmp_path: Path) -> None:
    missing_plan = tmp_path / "missing.toml"

    with pytest.raises(MigrationPlanLoadError) as caught:
        load_migration_plan(missing_plan)

    assert caught.value.path == missing_plan
    assert caught.value.kind is MigrationPlanLoadFailure.MISSING


def test_renderable_packages_build_complete_codex_specs(tmp_path: Path) -> None:
    plan = load_migration_plan(_PLAN_PATH)
    packages = discover_packages(plan, _REPOSITORY_ROOT)
    renderable_packages = tuple(
        package
        for package in packages
        if package.plan.disposition is not PackageDisposition.BLOCKED
    )

    specs = tuple(
        build_codex_package_spec(package, _REPOSITORY_ROOT, tmp_path / package.plan.name)
        for package in renderable_packages
    )

    assert tuple(spec.catalog.suite_name for spec in specs) == (
        "mz-base",
        "mz-dev-pipe",
        "mz-research-pipe",
        "mz-dev-git",
        "mz-biz-outreach",
        "mz-job-outreach",
        "mz-creative",
        "mz-funny",
        "mz-memory",
        "mz-design",
        "mz-knowledge",
        "mz-gov",
    )
    for package, spec in zip(renderable_packages, specs, strict=True):
        role_names = tuple(Path(source).stem for source in package.role_sources)

        assert spec.source_root == _REPOSITORY_ROOT
        assert spec.package_root == tmp_path / package.plan.name
        assert spec.version == "0.49.0"
        assert spec.description == package.source_manifest.description
        assert spec.author_name == "Stanislav Gonorovskii"
        assert tuple(role.name for role in spec.catalog.roles) == role_names
        assert all(skill.roles == role_names for skill in spec.catalog.skills)
        assert len(spec.catalog.role_resources) == len(spec.catalog.skills) * len(role_names)

    assert {
        spec.catalog.suite_name: spec.catalog.dependencies
        for spec in specs
        if spec.catalog.dependencies
    } == _EXPECTED_DEPENDENCIES

    hook_specs = {
        spec.catalog.suite_name: spec.catalog.hooks[0] for spec in specs if spec.catalog.hooks
    }
    assert tuple(hook_specs) == ("mz-dev-pipe", "mz-memory", "mz-knowledge")
    memory_hook = hook_specs["mz-memory"]
    assert tuple(
        (mapping.source_event, mapping.target_event) for mapping in memory_hook.events
    ) == ((HookEvent.POST_TOOL_USE, HookEvent.USER_PROMPT_SUBMIT),)
    assert HookScriptAdapter.USER_PROMPT_JOURNAL in {
        script.adapter for script in memory_hook.scripts
    }


def test_blocked_package_cannot_build_a_codex_spec(
    tmp_path: Path,
) -> None:
    plan = load_migration_plan(_PLAN_PATH)
    packages = discover_packages(plan, _REPOSITORY_ROOT)
    package = next(item for item in packages if item.plan.name == "mz-base")
    package = package.model_copy(
        update={
            "plan": package.plan.model_copy(
                update={"disposition": PackageDisposition.BLOCKED, "blockers": ("test",)}
            )
        }
    )

    with pytest.raises(MigrationInventoryError, match="blocked from Codex rendering"):
        build_codex_package_spec(package, _REPOSITORY_ROOT, tmp_path / package.plan.name)


def test_renderable_packages_render_from_canonical_sources(tmp_path: Path) -> None:
    plan = load_migration_plan(_PLAN_PATH)
    packages = discover_packages(plan, _REPOSITORY_ROOT)
    renderable_packages = tuple(
        package
        for package in packages
        if package.plan.disposition is not PackageDisposition.BLOCKED
    )

    results = tuple(
        render_codex_package(
            build_codex_package_spec(package, _REPOSITORY_ROOT, tmp_path / package.plan.name)
        )
        for package in renderable_packages
    )

    assert tuple(result.package_root.name for result in results) == tuple(
        package.plan.name for package in renderable_packages
    )
    assert sum(len(result.skill_paths) for result in results) == sum(
        len(package.skill_sources) for package in renderable_packages
    )
    assert sum(len(result.role_resource_paths) for result in results) == sum(
        len(package.skill_sources) * len(package.role_sources) for package in renderable_packages
    )
    assert sum(len(result.hook_paths) for result in results) == 3
    assert sum(len(result.hook_script_paths) for result in results) == sum(
        len(package.hook_script_sources) for package in renderable_packages
    )
    assert {
        result.package_root.name
        for result in results
        if result.dependency_contract_path is not None
    } == set(_EXPECTED_DEPENDENCIES)

    rendered_contents = "\n".join(
        file_path.read_text(encoding="utf-8")
        for result in results
        for file_path in result.package_root.rglob("*")
        if file_path.is_file() and file_path.suffix in {".json", ".md", ".sh"}
    )
    assert "Agent(" not in rendered_contents
    assert "Agent(s)" not in rendered_contents

    rendered_hooks = {
        result.package_root.name: json.loads(
            (result.package_root / result.hook_paths[0]).read_text(encoding="utf-8")
        )["hooks"]
        for result in results
        if result.hook_paths
    }
    assert {
        package_name: {
            event: tuple(command["command"] for group in groups for command in group["hooks"])
            for event, groups in hooks.items()
        }
        for package_name, hooks in rendered_hooks.items()
    } == {
        "mz-dev-pipe": {
            "SessionStart": ('"${PLUGIN_ROOT}"/scripts/detect-tooling.sh',),
        },
        "mz-memory": {
            "SessionStart": ('"${PLUGIN_ROOT}"/scripts/memory-inject.sh',),
            "UserPromptSubmit": (
                '"${PLUGIN_ROOT}"/scripts/journal-capture.sh',
                '"${PLUGIN_ROOT}"/scripts/memory-prompt-inject.sh',
            ),
            "SessionEnd": ('"${PLUGIN_ROOT}"/scripts/memory-capture.sh',),
        },
        "mz-knowledge": {
            "PostToolUse": ('"${PLUGIN_ROOT}"/scripts/frontmatter-normalize.sh',),
            "SessionStart": ('"${PLUGIN_ROOT}"/scripts/vault-context.sh',),
        },
    }
    assert rendered_hooks["mz-memory"]["SessionStart"][0]["matcher"] == "startup|clear|compact"
    assert rendered_hooks["mz-knowledge"]["PostToolUse"][0]["matcher"] == "Write|Edit"
    assert all(
        "once" not in handler
        for hooks in rendered_hooks.values()
        for groups in hooks.values()
        for group in groups
        for handler in group["hooks"]
    )
