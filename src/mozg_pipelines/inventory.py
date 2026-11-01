import json
import logging
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from mozg_pipelines.models import (
    ArgumentBinding,
    Catalog,
    HookEvent,
    HookEventMapping,
    HookScriptAdapter,
    HookScriptSpec,
    HookSpec,
    Identifier,
    IssueSeverity,
    MigrationPlan,
    ModelEffortPolicy,
    NonEmptyText,
    PackageDisposition,
    PackagePlanSpec,
    ProgressBackend,
    Provider,
    ProviderPolicy,
    ReasoningEffort,
    RepositoryPath,
    RoleResourceSpec,
    RoleSpec,
    SkillSpec,
    ValidationIssue,
    ValidationReport,
)

if TYPE_CHECKING:
    from mozg_pipelines.rendering import CodexPackageSpec

logger = logging.getLogger(__name__)


class MarketplaceModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class MarketplacePlugin(MarketplaceModel):
    name: Identifier
    source: RepositoryPath
    version: NonEmptyText
    description: NonEmptyText


class MarketplaceOwner(MarketplaceModel):
    name: NonEmptyText


class MarketplaceDocument(MarketplaceModel):
    owner: MarketplaceOwner
    plugins: tuple[MarketplacePlugin, ...]


class SourcePluginManifest(MarketplaceModel):
    name: Identifier
    version: NonEmptyText
    description: NonEmptyText


class RoleFrontmatter(MarketplaceModel):
    model: NonEmptyText


class PackageInventory(MarketplaceModel):
    plan: PackagePlanSpec
    marketplace: MarketplacePlugin
    source_manifest: SourcePluginManifest
    author_name: NonEmptyText
    skill_sources: tuple[RepositoryPath, ...]
    role_sources: tuple[RepositoryPath, ...]
    hook_config: RepositoryPath | None = None
    hook_script_sources: tuple[RepositoryPath, ...] = ()


class MigrationPlanLoadFailure(StrEnum):
    MISSING = "missing"
    READ_ERROR = "read-error"
    INVALID_TOML = "invalid-toml"
    INVALID_SCHEMA = "invalid-schema"


class MigrationPlanLoadError(RuntimeError):
    def __init__(self, path: Path, kind: MigrationPlanLoadFailure, message: str) -> None:
        super().__init__(f"Cannot load Codex migration plan {path}: {message}")
        self.path = path
        self.kind = kind


class MigrationInventoryError(RuntimeError):
    pass


def load_migration_plan(path: Path) -> MigrationPlan:
    logger.info("Loading Codex migration plan from %s", path)
    try:
        contents = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        logger.error("Codex migration plan does not exist: %s", path)
        raise MigrationPlanLoadError(
            path, MigrationPlanLoadFailure.MISSING, "file does not exist"
        ) from error
    except (OSError, UnicodeError) as error:
        logger.error("Cannot read Codex migration plan %s: %s", path, error)
        raise MigrationPlanLoadError(
            path, MigrationPlanLoadFailure.READ_ERROR, str(error)
        ) from error

    try:
        payload: object = tomllib.loads(contents)
    except tomllib.TOMLDecodeError as error:
        logger.error("Codex migration plan contains invalid TOML at %s: %s", path, error)
        raise MigrationPlanLoadError(
            path, MigrationPlanLoadFailure.INVALID_TOML, str(error)
        ) from error

    try:
        return MigrationPlan.model_validate(payload)
    except ValidationError as error:
        logger.error("Codex migration plan schema validation failed at %s: %s", path, error)
        raise MigrationPlanLoadError(
            path, MigrationPlanLoadFailure.INVALID_SCHEMA, str(error)
        ) from error


def validate_migration_plan(plan: MigrationPlan, repository_root: Path) -> ValidationReport:
    root = repository_root.resolve()
    issues: list[ValidationIssue] = []
    marketplace_path = _resolve_under_root(root, plan.source_marketplace)
    if marketplace_path is None or not marketplace_path.is_file():
        return ValidationReport(
            issues=(
                _error(
                    "missing-marketplace-source",
                    f"Marketplace source does not exist: {plan.source_marketplace}",
                    plan.source_marketplace,
                ),
            )
        )

    try:
        marketplace = _load_marketplace(marketplace_path)
    except MigrationInventoryError as error:
        return ValidationReport(
            issues=(_error("invalid-marketplace-source", str(error), plan.source_marketplace),)
        )

    planned_names = tuple(package.name for package in plan.packages)
    marketplace_names = tuple(plugin.name for plugin in marketplace.plugins)
    if planned_names != marketplace_names:
        issues.append(
            _error(
                "marketplace-plan-mismatch",
                "Migration plan package order and membership must match the canonical marketplace.",
                plan.source_marketplace,
            )
        )

    marketplace_by_name = {plugin.name: plugin for plugin in marketplace.plugins}
    for package in plan.packages:
        marketplace_plugin = marketplace_by_name.get(package.name)
        if marketplace_plugin is None:
            continue
        source_root = _resolve_under_root(root, marketplace_plugin.source)
        if source_root is None or not source_root.is_dir():
            issues.append(
                _error(
                    "missing-package-source",
                    f"Package source does not exist: {marketplace_plugin.source}",
                    marketplace_plugin.source,
                    package.name,
                )
            )
            continue

        manifest_path = source_root / "plugin.json"
        try:
            source_manifest = _load_source_manifest(manifest_path)
        except MigrationInventoryError as error:
            issues.append(_error("invalid-package-manifest", str(error), marketplace_plugin.source))
            continue

        if source_manifest.name != package.name:
            issues.append(
                _error(
                    "manifest-name-mismatch",
                    f"Source manifest name {source_manifest.name!r} does not match "
                    f"{package.name!r}.",
                    marketplace_plugin.source,
                    package.name,
                )
            )
        if source_manifest.version != marketplace_plugin.version:
            issues.append(
                _error(
                    "version-mismatch",
                    f"Source manifest version {source_manifest.version!r} does not match "
                    f"marketplace version {marketplace_plugin.version!r}.",
                    marketplace_plugin.source,
                    package.name,
                )
            )
    return ValidationReport(issues=tuple(issues))


def discover_packages(plan: MigrationPlan, repository_root: Path) -> tuple[PackageInventory, ...]:
    report = validate_migration_plan(plan, repository_root)
    if not report.is_valid:
        messages = "; ".join(issue.message for issue in report.issues)
        raise MigrationInventoryError(messages)

    root = repository_root.resolve()
    marketplace_path = _resolve_under_root(root, plan.source_marketplace)
    if marketplace_path is None:
        raise MigrationInventoryError(
            f"Marketplace source escapes repository: {plan.source_marketplace}"
        )
    marketplace = _load_marketplace(marketplace_path)
    marketplace_by_name = {plugin.name: plugin for plugin in marketplace.plugins}

    packages: list[PackageInventory] = []
    for package_plan in plan.packages:
        marketplace_plugin = marketplace_by_name[package_plan.name]
        source_root = _resolve_under_root(root, marketplace_plugin.source)
        if source_root is None:
            raise MigrationInventoryError(
                f"Package source escapes repository: {marketplace_plugin.source}"
            )
        packages.append(
            PackageInventory(
                plan=package_plan,
                marketplace=marketplace_plugin,
                source_manifest=_load_source_manifest(source_root / "plugin.json"),
                author_name=marketplace.owner.name,
                skill_sources=_source_files(root, source_root / "skills", "SKILL.md"),
                role_sources=_source_files(root, source_root / "agents", "*.md"),
                hook_config=_source_file(root, source_root / "hooks" / "hooks.json"),
                hook_script_sources=_source_files(root, source_root / "scripts", "*"),
            )
        )
    return tuple(packages)


def build_codex_package_spec(
    package: PackageInventory,
    repository_root: Path,
    package_root: Path,
) -> "CodexPackageSpec":
    if package.plan.disposition is PackageDisposition.BLOCKED:
        raise MigrationInventoryError(
            f"Package {package.plan.name} is blocked from Codex rendering: "
            f"{package.plan.disposition}."
        )

    repository = repository_root.resolve()
    role_names = tuple(Path(source).stem for source in package.role_sources)
    skills = tuple(
        SkillSpec(
            name=Path(source).parent.name,
            plugin=package.plan.name,
            source=Path(source).parent.as_posix(),
            roles=role_names,
        )
        for source in package.skill_sources
    )
    roles = tuple(
        RoleSpec(
            name=Path(source).stem,
            source=source,
            reasoning_effort=_role_reasoning_effort(repository / source),
        )
        for source in package.role_sources
    )
    role_resources = tuple(
        RoleResourceSpec(
            role=role.name,
            skill=skill.name,
            target=f"skills/{skill.name}/references/roles/{role.name}.md",
        )
        for skill in skills
        for role in roles
    )
    hooks = _build_hook_specs(package)
    catalog = Catalog(
        schema_version=1,
        suite_name=package.plan.name,
        skills=skills,
        dependencies=package.plan.dependencies,
        roles=roles,
        role_resources=role_resources,
        hooks=hooks,
    )
    policy = ProviderPolicy(
        provider=Provider.CODEX,
        plugin_name=package.plan.name,
        progress_backend=ProgressBackend.STATE_FILE,
        argument_binding=ArgumentBinding.USER_REQUEST,
        model_efforts=ModelEffortPolicy(
            fast=ReasoningEffort.LOW,
            standard=ReasoningEffort.MEDIUM,
            critical=ReasoningEffort.HIGH,
        ),
        forbidden_tokens=(
            "$ARGUMENTS",
            "AskUserQuestion",
            "TaskCreate",
            "TaskUpdate",
            "WebSearch",
            "WebFetch",
            "${CLAUDE_PLUGIN_ROOT}",
            "${CLAUDE_SKILL_DIR}",
            "CLAUDE.md",
            ".claude/rules",
        ),
    )

    from mozg_pipelines.rendering import CodexPackageSpec

    return CodexPackageSpec(
        catalog=catalog,
        policy=policy,
        source_root=repository,
        package_root=package_root,
        version=package.marketplace.version,
        description=package.marketplace.description,
        author_name=package.author_name,
    )


def _build_hook_specs(package: PackageInventory) -> tuple[HookSpec, ...]:
    if package.hook_config is None:
        return ()

    package_source = Path(package.marketplace.source)
    scripts = tuple(
        HookScriptSpec(
            source=source,
            target=Path(source).relative_to(package_source).as_posix(),
            adapter=_hook_script_adapter(package.plan.name, source),
        )
        for source in package.hook_script_sources
    )
    return (
        HookSpec(
            source=package.hook_config,
            target="hooks/hooks.json",
            events=_hook_event_mappings(package.plan.name),
            scripts=scripts,
        ),
    )


def _hook_event_mappings(package_name: str) -> tuple[HookEventMapping, ...]:
    if package_name != "mz-memory":
        return ()
    return (
        HookEventMapping(
            source_event=HookEvent.POST_TOOL_USE,
            target_event=HookEvent.USER_PROMPT_SUBMIT,
        ),
    )


def _hook_script_adapter(package_name: str, source: RepositoryPath) -> HookScriptAdapter:
    if package_name != "mz-memory":
        return HookScriptAdapter.PASSTHROUGH
    if source.endswith("/scripts/journal-capture.sh"):
        return HookScriptAdapter.USER_PROMPT_JOURNAL
    return HookScriptAdapter.PASSTHROUGH


def _load_marketplace(path: Path) -> MarketplaceDocument:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        return MarketplaceDocument.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as error:
        raise MigrationInventoryError(f"Cannot load marketplace {path}: {error}") from error


def _load_source_manifest(path: Path) -> SourcePluginManifest:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        return SourcePluginManifest.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as error:
        raise MigrationInventoryError(f"Cannot load source manifest {path}: {error}") from error


def _resolve_under_root(root: Path, relative_path: str) -> Path | None:
    candidate = root / relative_path
    try:
        candidate.resolve().relative_to(root)
    except (OSError, ValueError):
        return None
    return candidate


def _source_files(root: Path, directory: Path, pattern: str) -> tuple[RepositoryPath, ...]:
    if not directory.is_dir():
        return ()
    files = (path for path in sorted(directory.rglob(pattern)) if path.is_file())
    return tuple(path.relative_to(root).as_posix() for path in files)


def _source_file(root: Path, path: Path) -> RepositoryPath | None:
    if not path.is_file():
        return None
    return path.relative_to(root).as_posix()


def _role_reasoning_effort(path: Path) -> ReasoningEffort:
    try:
        contents = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        logger.error("Cannot read role source %s: %s", path, error)
        raise MigrationInventoryError(f"Cannot read role source {path}: {error}") from error

    closing_marker = contents.find("\n---\n", 4) if contents.startswith("---\n") else -1
    if closing_marker < 0:
        raise MigrationInventoryError(f"Role source has invalid frontmatter: {path}")

    frontmatter_text = contents[4:closing_marker]
    try:
        payload: object = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as error:
        logger.warning(
            "Role frontmatter is not strict YAML in %s; extracting model: %s",
            path,
            error,
        )
        payload = _required_role_frontmatter(frontmatter_text)

    try:
        frontmatter = RoleFrontmatter.model_validate(payload)
    except ValidationError as error:
        logger.error("Role source has invalid frontmatter %s: %s", path, error)
        raise MigrationInventoryError(
            f"Role source has invalid frontmatter {path}: {error}"
        ) from error

    effort_by_model = {
        "haiku": ReasoningEffort.LOW,
        "sonnet": ReasoningEffort.MEDIUM,
        "opus": ReasoningEffort.HIGH,
    }
    reasoning_effort = effort_by_model.get(frontmatter.model.lower())
    if reasoning_effort is None:
        raise MigrationInventoryError(
            f"Role source has unsupported model {frontmatter.model!r}: {path}"
        )
    return reasoning_effort


def _required_role_frontmatter(frontmatter_text: str) -> dict[str, str]:
    for line in frontmatter_text.splitlines():
        key, separator, value = line.partition(":")
        if separator and key == "model":
            return {"model": value.strip()}
    return {}


def _error(
    code: str,
    message: str,
    path: str | None = None,
    subject: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        severity=IssueSeverity.ERROR,
        code=code,
        message=message,
        path=path,
        subject=subject,
    )
