import json
from pathlib import Path

import pytest

from mozg_pipelines.inventory import (
    MigrationInventoryError,
    MigrationPlanLoadError,
    MigrationPlanLoadFailure,
    build_codex_package_spec,
    discover_packages,
    load_migration_plan,
    validate_migration_plan,
)
from mozg_pipelines.models import HookEvent, HookScriptAdapter, PackageDisposition
from mozg_pipelines.rendering import render_codex_package

_REPOSITORY_ROOT = Path(__file__).parents[2]
_PLAN_PATH = _REPOSITORY_ROOT / "data/codex_migration.toml"


def test_migration_plan_covers_the_canonical_marketplace() -> None:
    plan = load_migration_plan(_PLAN_PATH)

    report = validate_migration_plan(plan, _REPOSITORY_ROOT)
    packages = discover_packages(plan, _REPOSITORY_ROOT)

    assert report.is_valid is True
    assert tuple(package.plan.name for package in packages) == (
        "mz-dev-base",
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
    assert sum(len(package.skill_sources) for package in packages) == 54
    assert sum(len(package.role_sources) for package in packages) == 116
    assert not any(package.plan.disposition is PackageDisposition.BLOCKED for package in packages)
    assert tuple(
        (package.plan.name, package.plan.dependencies)
        for package in packages
        if package.plan.disposition is PackageDisposition.DEPENDENT
    ) == (
        ("mz-research-pipe", ("mz-dev-pipe",)),
        ("mz-dev-git", ("mz-dev-pipe",)),
        ("mz-biz-outreach", ("mz-creative",)),
    )
    assert {package.marketplace.version for package in packages} == {"0.49.0"}


def test_migration_plan_rejects_marketplace_membership_drift() -> None:
    plan = load_migration_plan(_PLAN_PATH)
    changed_plan = plan.model_copy(update={"packages": plan.packages[1:]})

    report = validate_migration_plan(changed_plan, _REPOSITORY_ROOT)

    assert tuple(issue.code for issue in report.issues) == ("marketplace-plan-mismatch",)


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
        "mz-dev-base",
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
        assert spec.description == package.marketplace.description
        assert spec.author_name == "Stanislav Gonorovskii"
        assert tuple(role.name for role in spec.catalog.roles) == role_names
        assert all(skill.roles == role_names for skill in spec.catalog.skills)
        assert len(spec.catalog.role_resources) == len(spec.catalog.skills) * len(role_names)

    assert {
        spec.catalog.suite_name: spec.catalog.dependencies
        for spec in specs
        if spec.catalog.dependencies
    } == {
        "mz-research-pipe": ("mz-dev-pipe",),
        "mz-dev-git": ("mz-dev-pipe",),
        "mz-biz-outreach": ("mz-creative",),
    }

    hook_specs = {
        spec.catalog.suite_name: spec.catalog.hooks[0] for spec in specs if spec.catalog.hooks
    }
    assert tuple(hook_specs) == ("mz-dev-base", "mz-dev-pipe", "mz-memory", "mz-knowledge")
    memory_hook = hook_specs["mz-memory"]
    assert tuple(
        (mapping.source_event, mapping.target_event) for mapping in memory_hook.events
    ) == (
        (HookEvent.POST_TOOL_USE, HookEvent.USER_PROMPT_SUBMIT),
        (HookEvent.POST_COMPACT, HookEvent.SESSION_START),
        (HookEvent.PRE_COMPACT, None),
    )
    assert {script.adapter for script in memory_hook.scripts} >= {
        HookScriptAdapter.USER_PROMPT_JOURNAL,
        HookScriptAdapter.COMPACTION_REINJECT,
    }


def test_blocked_package_cannot_build_a_codex_spec(
    tmp_path: Path,
) -> None:
    plan = load_migration_plan(_PLAN_PATH)
    packages = discover_packages(plan, _REPOSITORY_ROOT)
    package = next(item for item in packages if item.plan.name == "mz-dev-base")
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
    assert sum(len(result.hook_paths) for result in results) == 4
    assert sum(len(result.hook_script_paths) for result in results) == sum(
        len(package.hook_script_sources) for package in renderable_packages
    )
    assert tuple(
        result.package_root.name
        for result in results
        if result.dependency_contract_path is not None
    ) == ("mz-research-pipe", "mz-dev-git", "mz-biz-outreach")

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
        "mz-dev-base": {
            "SessionStart": ("${PLUGIN_ROOT}/scripts/session-start.sh",),
        },
        "mz-dev-pipe": {
            "SessionStart": ("${PLUGIN_ROOT}/scripts/detect-tooling.sh",),
        },
        "mz-memory": {
            "SessionStart": (
                "${PLUGIN_ROOT}/scripts/memory-reinject.sh",
                "${PLUGIN_ROOT}/scripts/memory-inject.sh",
            ),
            "UserPromptSubmit": (
                "${PLUGIN_ROOT}/scripts/journal-capture.sh",
                "${PLUGIN_ROOT}/scripts/memory-prompt-inject.sh",
            ),
            "SessionEnd": ("${PLUGIN_ROOT}/scripts/memory-capture.sh",),
        },
        "mz-knowledge": {
            "PostToolUse": ("${PLUGIN_ROOT}/scripts/frontmatter-normalize.sh",),
            "SessionStart": ("${PLUGIN_ROOT}/scripts/vault-context.sh",),
        },
    }
    assert rendered_hooks["mz-memory"]["SessionStart"][0]["matcher"] == "compact"
    assert rendered_hooks["mz-knowledge"]["PostToolUse"][0]["matcher"] == "Write|Edit|MultiEdit"
    assert all(
        "once" not in handler
        for hooks in rendered_hooks.values()
        for groups in hooks.values()
        for group in groups
        for handler in group["hooks"]
    )
