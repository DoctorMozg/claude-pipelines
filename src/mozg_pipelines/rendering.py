import json
import logging
import re
import shutil
from enum import StrEnum
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from mozg_pipelines.manifest import NonEmptyText, PortableManifest, SemanticVersion
from mozg_pipelines.models import (
    Catalog,
    HookEvent,
    HookScriptAdapter,
    HookSpec,
    Provider,
    ProviderPolicy,
)
from mozg_pipelines.validation import validate_catalog, validate_package

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
_COMMON_CODEX_TRANSFORMS = (
    ("$ARGUMENTS", "the user's request"),
    ("AskUserQuestion", "ask the user directly"),
    ("TaskCreate", "record the task in the active goal"),
    ("TaskUpdate", "update the active goal"),
    ("WebSearch", "web search"),
    ("WebFetch", "web fetch"),
    ("${CLAUDE_PLUGIN_ROOT}", "${PLUGIN_ROOT}"),
    # Codex substitutes no variables in SKILL.md bodies, but it gives the model each skill's path.
    ("${CLAUDE_SKILL_DIR}", "<directory containing this SKILL.md>"),
    ("CLAUDE.md", "AGENTS.md"),
    (".claude/rules", ".codex/rules"),
    ("Agent(s)", "Codex subagent(s)"),
)
_AGENT_CALL = re.compile(r"Agent\((?P<role>[a-z0-9][a-z0-9-]*)\)")
_SUPPORTED_HOOK_EVENT_MOVES = frozenset(
    {
        (HookEvent.POST_TOOL_USE, HookEvent.USER_PROMPT_SUBMIT),
    }
)
# The command-handler fields Codex documents; Claude-only ones such as `once` and `if` are dropped.
_CODEX_COMMAND_HANDLER_FIELDS = frozenset(
    {
        "type",
        "command",
        "timeout",
        "statusMessage",
        "async",
        "commandWindows",
        "additionalContextLimit",
    }
)
_DEPENDENCY_CONTRACT_PATH = Path("mozg-dependencies.json")
_CODEX_USER_PROMPT_JOURNAL = """#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

INPUT=$(cat || true)
PROMPT=$(jq -r '.prompt // empty' <<<"$INPUT" 2>/dev/null || true)
[[ -n "$PROMPT" ]] || exit 0

PROJECT_DIR=$(find_project_root)
JOURNAL_FILE="${PROJECT_DIR}/.mz/journal.md"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SESSION=$(jq -r '.session_id // "unknown"' <<<"$INPUT" 2>/dev/null || echo "unknown")

ENTRY=$(printf '### %s · session %s · UserPromptSubmit\n\nprompt (verbatim):\n%s' \
  "$TIMESTAMP" "$SESSION" "$PROMPT")
printf '%s' "$ENTRY" | journal_append "$JOURNAL_FILE" 2>/dev/null || exit 0
"""


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceFrontmatter(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    name: NonEmptyText
    description: NonEmptyText


class MarkdownDocument[FrontmatterT: SourceFrontmatter](FrozenModel):
    frontmatter: FrontmatterT
    body: str


class CodexPackageSpec(FrozenModel):
    catalog: Catalog
    policy: ProviderPolicy
    source_root: Path
    package_root: Path
    version: SemanticVersion
    description: NonEmptyText
    author_name: NonEmptyText

    @model_validator(mode="after")
    def policy_matches_catalog(self) -> "CodexPackageSpec":
        if self.policy.provider is not Provider.CODEX:
            raise ValueError("Codex package rendering requires a Codex provider policy")
        if self.policy.plugin_name != self.catalog.suite_name:
            raise ValueError("provider plugin_name must match catalog suite_name")
        return self


class RenderResult(FrozenModel):
    package_root: Path
    skill_paths: tuple[Path, ...]
    role_resource_paths: tuple[Path, ...]
    hook_paths: tuple[Path, ...]
    script_paths: tuple[Path, ...]
    shared_path: Path | None
    dependency_contract_path: Path | None


class RenderFailure(StrEnum):
    TARGET_EXISTS = "target-exists"
    INVALID_SOURCE = "invalid-source"
    INVALID_FRONTMATTER = "invalid-frontmatter"
    INVALID_PACKAGE = "invalid-package"
    IO_ERROR = "io-error"


class RenderError(RuntimeError):
    def __init__(self, path: Path, kind: RenderFailure, message: str) -> None:
        super().__init__(f"Cannot render Codex package at {path}: {message}")
        self.path = path
        self.kind = kind


def render_codex_package(spec: CodexPackageSpec) -> RenderResult:
    logger.info(
        "Rendering Codex package %s with %d skills and %d role resources to %s",
        spec.catalog.suite_name,
        len(spec.catalog.skills),
        len(spec.catalog.role_resources),
        spec.package_root,
    )
    if spec.package_root.exists():
        raise RenderError(
            spec.package_root,
            RenderFailure.TARGET_EXISTS,
            "target already exists; renderer never overwrites packages",
        )

    source_report = validate_catalog(spec.catalog, spec.source_root)
    if not source_report.is_valid:
        messages = "; ".join(issue.message for issue in source_report.issues)
        raise RenderError(spec.source_root, RenderFailure.INVALID_SOURCE, messages)

    try:
        spec.package_root.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(
            prefix=f".{spec.policy.plugin_name}-",
            dir=spec.package_root.parent,
        ) as temporary_directory:
            staging_root = Path(temporary_directory) / spec.policy.plugin_name
            skill_paths = _render_skills(spec, staging_root)
            role_resource_paths = _render_role_resources(spec, staging_root)
            hook_paths = _render_hooks(spec, staging_root)
            script_paths = _render_scripts(spec, staging_root)
            shared_path = _render_shared(spec, staging_root)
            dependency_contract_path = _render_dependency_contract(spec, staging_root)
            _write_manifest(spec, staging_root)

            package_report = validate_package(spec.catalog, spec.policy, staging_root)
            if not package_report.is_valid:
                messages = "; ".join(issue.message for issue in package_report.issues)
                raise RenderError(staging_root, RenderFailure.INVALID_PACKAGE, messages)

            staging_root.replace(spec.package_root)
    except RenderError:
        raise
    except OSError as error:
        logger.exception("Codex package rendering failed at %s", spec.package_root)
        raise RenderError(spec.package_root, RenderFailure.IO_ERROR, str(error)) from error

    result = RenderResult(
        package_root=spec.package_root,
        skill_paths=skill_paths,
        role_resource_paths=role_resource_paths,
        hook_paths=hook_paths,
        script_paths=script_paths,
        shared_path=shared_path,
        dependency_contract_path=dependency_contract_path,
    )
    logger.info("Rendered Codex package successfully at %s", result.package_root)
    return result


def _render_skills(spec: CodexPackageSpec, staging_root: Path) -> tuple[Path, ...]:
    rendered_paths: list[Path] = []
    for skill in sorted(spec.catalog.skills, key=lambda item: item.name):
        source_root = spec.source_root / skill.source
        target_root = staging_root / "skills" / skill.name
        document = _read_markdown(source_root / "SKILL.md", SourceFrontmatter)
        if document.frontmatter.name != skill.name:
            raise RenderError(
                source_root / "SKILL.md",
                RenderFailure.INVALID_FRONTMATTER,
                f"frontmatter name {document.frontmatter.name!r} does not match {skill.name!r}",
            )

        _copy_source_tree(spec, source_root, target_root)
        target_path = target_root / "SKILL.md"
        target_path.write_text(
            _render_skill_markdown(spec, source_root / "SKILL.md", document),
            encoding="utf-8",
        )
        rendered_paths.append(target_path.relative_to(staging_root))
    return tuple(rendered_paths)


def _render_shared(spec: CodexPackageSpec, staging_root: Path) -> Path | None:
    if spec.catalog.shared_root is None:
        return None
    target = Path("shared")
    _copy_source_tree(spec, spec.source_root / spec.catalog.shared_root, staging_root / target)
    logger.info("Rendered shared folder %s", spec.catalog.shared_root)
    return target


def _render_role_resources(spec: CodexPackageSpec, staging_root: Path) -> tuple[Path, ...]:
    rendered_paths: list[Path] = []
    roles_by_name = {role.name: role for role in spec.catalog.roles}
    for resource in sorted(spec.catalog.role_resources, key=lambda item: (item.skill, item.role)):
        role = roles_by_name[resource.role]
        source_path = spec.source_root / role.source
        document = _read_markdown(source_path, SourceFrontmatter)
        if document.frontmatter.name != role.name:
            raise RenderError(
                source_path,
                RenderFailure.INVALID_FRONTMATTER,
                f"frontmatter name {document.frontmatter.name!r} does not match {role.name!r}",
            )

        target_path = staging_root / resource.target
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            _adapt_contents(spec, source_path, document.body),
            encoding="utf-8",
        )
        rendered_paths.append(target_path.relative_to(staging_root))
    return tuple(rendered_paths)


def _render_hooks(spec: CodexPackageSpec, staging_root: Path) -> tuple[Path, ...]:
    hook_paths: list[Path] = []
    for hook in sorted(spec.catalog.hooks, key=lambda item: item.target):
        source_hook_path = spec.source_root / hook.source
        target_hook_path = staging_root / hook.target
        target_hook_path.parent.mkdir(parents=True, exist_ok=True)
        target_hook_path.write_text(
            _adapt_hook_config(spec, hook, source_hook_path),
            encoding="utf-8",
        )
        hook_paths.append(target_hook_path.relative_to(staging_root))
    return tuple(hook_paths)


def _render_scripts(spec: CodexPackageSpec, staging_root: Path) -> tuple[Path, ...]:
    script_paths: list[Path] = []
    for script in sorted(spec.catalog.scripts, key=lambda item: item.target):
        source_script_path = spec.source_root / script.source
        target_script_path = staging_root / script.target
        try:
            source_contents = source_script_path.read_text(encoding="utf-8")
            source_mode = source_script_path.stat().st_mode
        except (OSError, UnicodeError) as error:
            logger.error("Cannot read script source %s: %s", source_script_path, error)
            raise RenderError(source_script_path, RenderFailure.IO_ERROR, str(error)) from error

        target_script_path.parent.mkdir(parents=True, exist_ok=True)
        target_script_path.write_text(
            _adapt_script(spec, script.adapter, source_script_path, source_contents),
            encoding="utf-8",
        )
        target_script_path.chmod(source_mode)
        script_paths.append(target_script_path.relative_to(staging_root))
    return tuple(script_paths)


def _adapt_hook_config(spec: CodexPackageSpec, hook: HookSpec, source_path: Path) -> str:
    try:
        payload: object = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        logger.error("Cannot parse hook configuration %s: %s", source_path, error)
        raise RenderError(source_path, RenderFailure.INVALID_SOURCE, str(error)) from error

    if not isinstance(payload, dict):
        raise RenderError(
            source_path, RenderFailure.INVALID_SOURCE, "hook configuration must be an object"
        )
    source_groups = payload.get("hooks")
    if not isinstance(source_groups, dict):
        raise RenderError(
            source_path,
            RenderFailure.INVALID_SOURCE,
            "hook configuration must contain a hooks object",
        )

    event_mappings = {mapping.source_event: mapping.target_event for mapping in hook.events}
    rendered_groups: dict[str, list[dict[str, object]]] = {}
    for source_event_name, groups in source_groups.items():
        if not isinstance(source_event_name, str):
            raise RenderError(
                source_path, RenderFailure.INVALID_SOURCE, "hook event names must be strings"
            )
        try:
            source_event = HookEvent(source_event_name)
        except ValueError as error:
            raise RenderError(
                source_path,
                RenderFailure.INVALID_SOURCE,
                f"unsupported hook event: {source_event_name}",
            ) from error

        target_event = event_mappings.get(source_event, source_event)
        if target_event is None:
            logger.warning(
                "Dropping unsupported Codex hook event %s from %s",
                source_event.value,
                source_path,
            )
            continue
        if (
            source_event is not target_event
            and (source_event, target_event) not in _SUPPORTED_HOOK_EVENT_MOVES
        ):
            raise RenderError(
                source_path,
                RenderFailure.INVALID_SOURCE,
                "unsupported Codex hook event mapping: "
                f"{source_event.value} -> {target_event.value}",
            )
        if not isinstance(groups, list):
            raise RenderError(
                source_path,
                RenderFailure.INVALID_SOURCE,
                f"hook event groups must be a list: {source_event.value}",
            )

        target_groups = rendered_groups.setdefault(target_event.value, [])
        target_groups.extend(
            _adapt_hook_group(source_path, source_event, target_event, group) for group in groups
        )

    rendered_payload = {"hooks": rendered_groups}
    return _adapt_contents(
        spec,
        source_path,
        json.dumps(rendered_payload, ensure_ascii=False, indent=2) + "\n",
    )


def _adapt_hook_group(
    source_path: Path,
    source_event: HookEvent,
    target_event: HookEvent,
    group: object,
) -> dict[str, object]:
    if not isinstance(group, dict):
        raise RenderError(source_path, RenderFailure.INVALID_SOURCE, "hook group must be an object")
    handlers = group.get("hooks")
    if not isinstance(handlers, list):
        raise RenderError(
            source_path, RenderFailure.INVALID_SOURCE, "hook group must contain a hooks list"
        )

    adapted_group = {key: value for key, value in group.items() if key != "hooks"}
    adapted_handlers: list[dict[str, object]] = []
    for handler in handlers:
        if not isinstance(handler, dict):
            raise RenderError(
                source_path, RenderFailure.INVALID_SOURCE, "hook handler must be an object"
            )
        if handler.get("type") != "command" or not isinstance(handler.get("command"), str):
            raise RenderError(
                source_path,
                RenderFailure.INVALID_SOURCE,
                "Codex hook adapters require command handlers",
            )
        dropped = sorted(set(handler) - _CODEX_COMMAND_HANDLER_FIELDS)
        if dropped:
            logger.debug("Dropping Claude-only hook fields %s from %s", dropped, source_path)
        adapted_handlers.append(
            {key: value for key, value in handler.items() if key in _CODEX_COMMAND_HANDLER_FIELDS}
        )

    if source_event is HookEvent.POST_TOOL_USE and target_event is HookEvent.USER_PROMPT_SUBMIT:
        adapted_group.pop("matcher", None)
    adapted_group["hooks"] = adapted_handlers
    return adapted_group


def _adapt_script(
    spec: CodexPackageSpec,
    adapter: HookScriptAdapter,
    source_path: Path,
    contents: str,
) -> str:
    if adapter is HookScriptAdapter.USER_PROMPT_JOURNAL:
        return _CODEX_USER_PROMPT_JOURNAL
    return _adapt_contents(spec, source_path, contents)


def _render_dependency_contract(spec: CodexPackageSpec, staging_root: Path) -> Path | None:
    if not spec.catalog.dependencies:
        return None

    contract_path = staging_root / _DEPENDENCY_CONTRACT_PATH
    contract_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "requires": [
                    {
                        "plugin": dependency,
                        "installation": (
                            f"Install and enable {dependency} before starting a new Codex session."
                        ),
                    }
                    for dependency in spec.catalog.dependencies
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.info(
        "Rendered %d explicit dependency contract entries for %s",
        len(spec.catalog.dependencies),
        spec.catalog.suite_name,
    )
    return _DEPENDENCY_CONTRACT_PATH


def _write_manifest(spec: CodexPackageSpec, staging_root: Path) -> None:
    display_name = " ".join(part.capitalize() for part in spec.catalog.suite_name.split("-"))
    payload: dict[str, object] = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": spec.policy.plugin_name,
        "version": spec.version,
        "description": spec.description,
        "author": {"name": spec.author_name},
        "extensions": {
            "com.openai": {
                "interface": {
                    "displayName": display_name,
                    "shortDescription": f"Use {display_name} skills in Codex.",
                    "longDescription": spec.description,
                    "developerName": spec.author_name,
                    "category": "Developer Tools",
                    "capabilities": ["Interactive", "Write"],
                    "defaultPrompt": ["Help me choose a Mozg pipeline."],
                }
            }
        },
    }
    manifest = PortableManifest.model_validate(payload)
    manifest_path = staging_root / "plugin.json"
    manifest_path.write_text(
        json.dumps(
            manifest.model_dump(by_alias=True, exclude_defaults=True, exclude_none=True),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _read_markdown[FrontmatterT: SourceFrontmatter](
    path: Path,
    frontmatter_type: type[FrontmatterT],
) -> MarkdownDocument[FrontmatterT]:
    try:
        contents = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        logger.error("Cannot read provider source %s: %s", path, error)
        raise RenderError(path, RenderFailure.IO_ERROR, str(error)) from error

    closing_marker = contents.find("\n---\n", 4) if contents.startswith("---\n") else -1
    if closing_marker < 0:
        raise RenderError(
            path,
            RenderFailure.INVALID_FRONTMATTER,
            "markdown must start with closed YAML frontmatter",
        )

    frontmatter_text = contents[4:closing_marker]
    try:
        payload: object = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as error:
        logger.warning(
            "Provider frontmatter is not strict YAML in %s; extracting required fields: %s",
            path,
            error,
        )
        payload = _required_frontmatter_fields(frontmatter_text)

    try:
        frontmatter = frontmatter_type.model_validate(payload)
    except ValidationError as error:
        logger.error("Invalid provider frontmatter in %s: %s", path, error)
        raise RenderError(path, RenderFailure.INVALID_FRONTMATTER, str(error)) from error

    body = contents[closing_marker + len("\n---\n") :].lstrip("\n")
    return MarkdownDocument[FrontmatterT](frontmatter=frontmatter, body=body)


def _required_frontmatter_fields(frontmatter_text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        key, separator, value = line.partition(":")
        if separator and key in {"name", "description"}:
            fields[key] = value.strip()
    return fields


def _copy_source_tree(spec: CodexPackageSpec, source_root: Path, target_root: Path) -> None:
    """Copy a skill tree, writing each symlink's content in its place like Claude Code's cache."""
    # validate_catalog has already rejected links that escape the marketplace, dangle or loop.
    target_root.mkdir(parents=True, exist_ok=True)
    for source_path in sorted(source_root.iterdir()):
        target_path = target_root / source_path.name
        if source_path.is_symlink():
            logger.debug("Dereferencing %s -> %s", source_path, source_path.resolve())
        if source_path.is_dir():
            _copy_source_tree(spec, source_path, target_path)
        elif source_path.is_file():
            _copy_source_file(spec, source_path, target_path)
        else:
            raise RenderError(
                source_path, RenderFailure.INVALID_SOURCE, "source is not a file or directory"
            )


def _copy_source_file(spec: CodexPackageSpec, source_path: Path, target_path: Path) -> None:
    if source_path.suffix.lower() not in _TEXT_SUFFIXES:
        shutil.copy2(source_path, target_path)
        return
    try:
        contents = source_path.read_text(encoding="utf-8")
        target_path.write_text(_adapt_contents(spec, source_path, contents), encoding="utf-8")
    except (OSError, UnicodeError) as error:
        logger.error("Cannot adapt provider source %s: %s", source_path, error)
        raise RenderError(source_path, RenderFailure.IO_ERROR, str(error)) from error


def _render_skill_markdown(
    spec: CodexPackageSpec,
    source_path: Path,
    document: MarkdownDocument[SourceFrontmatter],
) -> str:
    description = _adapt_contents(spec, source_path, document.frontmatter.description)
    return "\n".join(
        (
            "---",
            f"name: {json.dumps(document.frontmatter.name, ensure_ascii=False)}",
            f"description: {json.dumps(description, ensure_ascii=False)}",
            "---",
            "",
            _adapt_contents(spec, source_path, document.body),
        )
    )


def _adapt_contents(spec: CodexPackageSpec, source_path: Path, contents: str) -> str:
    rendered_contents = contents
    for source_transform in spec.catalog.transforms:
        if source_transform.source == source_path.relative_to(spec.source_root).as_posix():
            rendered_contents = rendered_contents.replace(
                source_transform.match,
                source_transform.replacement,
            )
    for source, replacement in _COMMON_CODEX_TRANSFORMS:
        rendered_contents = rendered_contents.replace(source, replacement)
    return _AGENT_CALL.sub(
        lambda match: _adapt_agent_call(spec, source_path, match), rendered_contents
    )


def _adapt_agent_call(spec: CodexPackageSpec, source_path: Path, match: re.Match[str]) -> str:
    role_name = match.group("role")
    if role_name in {role.name for role in spec.catalog.roles}:
        return f"delegate to a Codex subagent using the {role_name} role prompt"
    if not spec.catalog.dependencies:
        raise RenderError(
            source_path,
            RenderFailure.INVALID_SOURCE,
            f"Role {role_name!r} is neither local nor declared by a dependency contract",
        )
    dependency_names = ", ".join(spec.catalog.dependencies)
    return (
        f"delegate to a Codex subagent for the {role_name} task; consult the relevant installed "
        f"skills from {dependency_names}, as declared in mozg-dependencies.json"
    )
