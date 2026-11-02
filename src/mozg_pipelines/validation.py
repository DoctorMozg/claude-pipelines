import logging
import re
import tomllib
from enum import StrEnum
from pathlib import Path

from pydantic import ValidationError

from mozg_pipelines.manifest import (
    LegacyPluginManifest,
    ManifestLoadError,
    PortableManifest,
    load_legacy_manifest,
    load_portable_manifest,
)
from mozg_pipelines.models import (
    Catalog,
    HookSpec,
    IssueSeverity,
    ProviderPolicy,
    ValidationIssue,
    ValidationReport,
)

logger = logging.getLogger(__name__)

_TEXT_SUFFIXES = frozenset(
    {
        "",
        ".bash",
        ".js",
        ".json",
        ".jsx",
        ".md",
        ".py",
        ".sh",
        ".toml",
        ".ts",
        ".tsx",
        ".yaml",
        ".yml",
    }
)


class CatalogLoadFailure(StrEnum):
    MISSING = "missing"
    READ_ERROR = "read-error"
    INVALID_TOML = "invalid-toml"
    INVALID_SCHEMA = "invalid-schema"


class CatalogLoadError(RuntimeError):
    def __init__(self, path: Path, kind: CatalogLoadFailure, message: str) -> None:
        super().__init__(f"Cannot load migration catalog {path}: {message}")
        self.path = path
        self.kind = kind


def load_catalog(path: Path) -> Catalog:
    logger.info("Loading migration catalog from %s", path)
    try:
        contents = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        logger.error("Migration catalog does not exist: %s", path)
        raise CatalogLoadError(path, CatalogLoadFailure.MISSING, "file does not exist") from error
    except (OSError, UnicodeError) as error:
        logger.error("Cannot read migration catalog %s: %s", path, error)
        raise CatalogLoadError(path, CatalogLoadFailure.READ_ERROR, str(error)) from error

    try:
        payload: object = tomllib.loads(contents)
    except tomllib.TOMLDecodeError as error:
        logger.error("Migration catalog contains invalid TOML at %s: %s", path, error)
        raise CatalogLoadError(path, CatalogLoadFailure.INVALID_TOML, str(error)) from error

    try:
        catalog = Catalog.model_validate(payload)
    except ValidationError as error:
        logger.error("Migration catalog schema validation failed at %s: %s", path, error)
        raise CatalogLoadError(path, CatalogLoadFailure.INVALID_SCHEMA, str(error)) from error

    logger.info(
        "Loaded migration catalog %s with %d skills and %d roles",
        catalog.suite_name,
        len(catalog.skills),
        len(catalog.roles),
    )
    return catalog


def validate_catalog(catalog: Catalog, source_root: Path) -> ValidationReport:
    logger.info("Validating %d catalog skills under %s", len(catalog.skills), source_root)
    root = source_root.resolve()
    issues: list[ValidationIssue] = []
    role_names = frozenset(role.name for role in catalog.roles)

    for skill in catalog.skills:
        skill_root = root / skill.source
        if not _is_contained(root, skill_root):
            issues.append(
                _error(
                    "path-escape",
                    f"Skill source resolves outside the source root: {skill.source}",
                    skill.source,
                    skill.name,
                )
            )
        elif not skill_root.is_dir() or not (skill_root / "SKILL.md").is_file():
            issues.append(
                _error(
                    "missing-skill-source",
                    f"Skill source is missing SKILL.md: {skill.source}",
                    skill.source,
                    skill.name,
                )
            )
        else:
            issues.extend(_symlink_issues(root, skill_root, skill.name))
            issue = _unreadable_source_issue(root, skill_root / "SKILL.md", skill.name)
            if issue is not None:
                issues.append(issue)

        for role_name in skill.roles:
            if role_name not in role_names:
                issues.append(
                    _error(
                        "missing-role",
                        f"Skill {skill.name} references unknown role {role_name}",
                        subject=role_name,
                    )
                )

    for role in catalog.roles:
        role_path = root / role.source
        if not _is_contained(root, role_path):
            issues.append(
                _error(
                    "path-escape",
                    f"Role source resolves outside the source root: {role.source}",
                    role.source,
                    role.name,
                )
            )
        elif not role_path.is_file():
            issues.append(
                _error(
                    "missing-role-source",
                    f"Role source does not exist: {role.source}",
                    role.source,
                    role.name,
                )
            )
        else:
            issue = _unreadable_source_issue(root, role_path, role.name)
            if issue is not None:
                issues.append(issue)

    for hook in catalog.hooks:
        issues.extend(_validate_hook_sources(root, hook))

    report = ValidationReport(issues=tuple(issues))
    logger.info(
        "Catalog validation finished with %d issue(s) under %s",
        len(report.issues),
        source_root,
    )
    return report


def validate_package(
    catalog: Catalog,
    policy: ProviderPolicy,
    package_root: Path,
) -> ValidationReport:
    logger.info(
        "Validating %s package with %d catalog skills under %s",
        policy.provider,
        len(catalog.skills),
        package_root,
    )
    root = package_root.resolve()
    issues: list[ValidationIssue] = []

    if not root.is_dir():
        return ValidationReport(
            issues=(
                _error(
                    "missing-package-root",
                    f"Rendered package root does not exist: {package_root}",
                ),
            )
        )

    _validate_manifest(root, policy, issues)

    for skill in catalog.skills:
        rendered_skill = root / "skills" / skill.name / "SKILL.md"
        if not _is_contained(root, rendered_skill) or not rendered_skill.is_file():
            issues.append(
                _error(
                    "missing-rendered-skill",
                    f"Rendered skill is missing: skills/{skill.name}/SKILL.md",
                    f"skills/{skill.name}/SKILL.md",
                    skill.name,
                )
            )

    for resource in catalog.role_resources:
        rendered_resource = root / resource.target
        if not _is_contained(root, rendered_resource) or not rendered_resource.is_file():
            issues.append(
                _error(
                    "missing-role-resource",
                    f"Rendered role resource is missing: {resource.target}",
                    resource.target,
                    resource.role,
                )
            )

    for hook in catalog.hooks:
        rendered_hook = root / hook.target
        if not _is_contained(root, rendered_hook) or not rendered_hook.is_file():
            issues.append(
                _error(
                    "missing-rendered-hook",
                    f"Rendered hook configuration is missing: {hook.target}",
                    hook.target,
                )
            )
        for script in hook.scripts:
            rendered_script = root / script.target
            if not _is_contained(root, rendered_script) or not rendered_script.is_file():
                issues.append(
                    _error(
                        "missing-rendered-hook-script",
                        f"Rendered hook script is missing: {script.target}",
                        script.target,
                    )
                )

    text_files = tuple(
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() in _TEXT_SUFFIXES and _is_contained(root, path)
    )
    readable_contents: list[str] = []
    readable_paths: list[Path] = []
    for path in text_files:
        try:
            readable_contents.append(path.read_text(encoding="utf-8"))
            readable_paths.append(path)
        except (OSError, UnicodeError) as error:
            relative_path = path.relative_to(root).as_posix()
            logger.error("Cannot read rendered package file %s: %s", path, error)
            issues.append(
                _error(
                    "unreadable-package-file",
                    f"Cannot read rendered package file {relative_path}: {error}",
                    relative_path,
                )
            )

    for token in policy.forbidden_tokens:
        for path, contents in zip(readable_paths, readable_contents, strict=True):
            visible_contents = _without_provenance(contents, policy)
            if token in visible_contents:
                relative_path = path.relative_to(root).as_posix()
                issues.append(
                    _error(
                        "forbidden-token",
                        f"Rendered package contains forbidden token {token!r}",
                        relative_path,
                        token,
                    )
                )
                break

    report = ValidationReport(issues=tuple(issues))
    logger.info(
        "Rendered %s package validation finished with %d issue(s)",
        policy.provider,
        len(report.issues),
    )
    return report


def _is_contained(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root)
    except (OSError, ValueError):
        return False
    return True


def _symlink_issues(
    source_root: Path,
    directory: Path,
    subject: str,
    ancestors: frozenset[Path] = frozenset(),
) -> tuple[ValidationIssue, ...]:
    """Walk a source tree through its symlinks, as Claude Code's cache copy does."""
    ancestors = ancestors | {directory.resolve()}
    issues: list[ValidationIssue] = []
    for path in sorted(directory.iterdir()):
        relative = path.relative_to(source_root).as_posix()
        if path.is_symlink():
            issue = _symlink_target_issue(source_root, path, relative, subject)
            if issue is not None:
                issues.append(issue)
                continue
        if not path.is_dir():
            continue
        if path.resolve() in ancestors:
            issues.append(
                _error(
                    "symlink-cycle",
                    f"Source symlink points back to an ancestor directory: {relative}",
                    relative,
                    subject,
                )
            )
            continue
        issues.extend(_symlink_issues(source_root, path, subject, ancestors))
    return tuple(issues)


def _symlink_target_issue(
    source_root: Path,
    path: Path,
    relative: str,
    subject: str,
) -> ValidationIssue | None:
    try:
        target = path.resolve(strict=True)
    except FileNotFoundError:
        return _error(
            "missing-symlink-target",
            f"Source symlink target does not exist: {relative}",
            relative,
            subject,
        )
    except (OSError, RuntimeError):
        # A link chain that loops on itself: RuntimeError on Python 3.12, OSError on 3.13+.
        return _error("symlink-cycle", f"Source symlink chain loops: {relative}", relative, subject)
    if not target.is_relative_to(source_root):
        logger.warning("Source symlink %s resolves outside %s", path, source_root)
        return _error(
            "path-escape",
            f"Source symlink resolves outside the source root: {relative}",
            relative,
            subject,
        )
    return None


def _unreadable_source_issue(
    root: Path,
    path: Path,
    subject: str,
) -> ValidationIssue | None:
    try:
        path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        relative_path = path.relative_to(root).as_posix()
        logger.error("Cannot read provider source %s: %s", path, error)
        return _error(
            "unreadable-source-file",
            f"Cannot read provider source {relative_path}: {error}",
            relative_path,
            subject,
        )
    return None


def _validate_hook_sources(root: Path, hook: HookSpec) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    hook_source = root / hook.source
    if not _is_contained(root, hook_source) or not hook_source.is_file():
        issues.append(
            _error(
                "missing-hook-source",
                f"Hook configuration does not exist: {hook.source}",
                hook.source,
            )
        )
    else:
        issue = _unreadable_source_issue(root, hook_source, hook.source)
        if issue is not None:
            issues.append(issue)

    for script in hook.scripts:
        script_source = root / script.source
        if not _is_contained(root, script_source) or not script_source.is_file():
            issues.append(
                _error(
                    "missing-hook-script-source",
                    f"Hook script does not exist: {script.source}",
                    script.source,
                )
            )
        else:
            issue = _unreadable_source_issue(root, script_source, script.source)
            if issue is not None:
                issues.append(issue)
    return tuple(issues)


def _validate_manifest(
    root: Path,
    policy: ProviderPolicy,
    issues: list[ValidationIssue],
) -> None:
    portable_path = root / "plugin.json"
    legacy_path = root / ".codex-plugin/plugin.json"
    manifest: PortableManifest | LegacyPluginManifest | None = None

    if portable_path.is_file():
        try:
            manifest = load_portable_manifest(portable_path)
        except ManifestLoadError as error:
            issues.append(_error("invalid-manifest", str(error), "plugin.json"))
    elif legacy_path.is_file():
        try:
            manifest = load_legacy_manifest(legacy_path)
            issues.append(
                _warning(
                    "legacy-manifest",
                    "Package uses the .codex-plugin compatibility manifest; "
                    "render a portable root plugin.json.",
                    ".codex-plugin/plugin.json",
                )
            )
        except ManifestLoadError as error:
            issues.append(_error("invalid-manifest", str(error), ".codex-plugin/plugin.json"))
    else:
        issues.append(
            _error(
                "missing-manifest",
                "Rendered package must contain plugin.json or .codex-plugin/plugin.json.",
            )
        )

    if manifest is not None and manifest.name != policy.plugin_name:
        issues.append(
            _error(
                "manifest-name-mismatch",
                f"Manifest name {manifest.name!r} does not match {policy.plugin_name!r}.",
                "plugin.json" if portable_path.is_file() else ".codex-plugin/plugin.json",
                manifest.name,
            )
        )


def _without_provenance(contents: str, policy: ProviderPolicy) -> str:
    pattern = re.compile(
        re.escape(policy.provenance_markers.start)
        + ".*?"
        + re.escape(policy.provenance_markers.end),
        flags=re.DOTALL,
    )
    return pattern.sub("", contents)


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


def _warning(
    code: str,
    message: str,
    path: str | None = None,
    subject: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        severity=IssueSeverity.WARNING,
        code=code,
        message=message,
        path=path,
        subject=subject,
    )
