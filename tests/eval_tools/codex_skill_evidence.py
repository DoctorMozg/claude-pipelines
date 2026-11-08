"""Observe verified skill loads and packaged workflow actions in root CLI events."""

import hashlib
import json
import logging
import re
import shlex
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

import yaml

logger = logging.getLogger(__name__)
EvidenceState = Literal["loaded", "workflow-observed", "unknown"]
_LIMITATIONS = (
    "Root CLI events do not capture every native injection or child-thread skill load.",
    "A body load and workflow action do not establish native activation or completion.",
    "Missing observations cannot establish non-use; reads and actions are not invocation counts.",
    "Only complete literal cat reads and direct packaged-script commands are recognized.",
)
_SCRIPT_REFERENCE = re.compile(r"\$\{PLUGIN_ROOT\}/(scripts/[\w./-]+)")
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")


@dataclass(frozen=True)
class EvidenceReference:
    event_index: int
    item_id: str
    path: str
    sha256: str
    command: str


@dataclass(frozen=True)
class SkillObservation:
    plugin: str
    skill: str
    state: EvidenceState
    loads: tuple[EvidenceReference, ...] = ()
    actions: tuple[EvidenceReference, ...] = ()


@dataclass(frozen=True)
class SkillEvidence:
    observations: tuple[SkillObservation, ...] = ()
    scope: str = "root-cli-events"
    limitations: tuple[str, ...] = _LIMITATIONS


@dataclass(frozen=True)
class SkillAssessment:
    grader_name: str
    state: EvidenceState
    skill_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class EvidenceContext:
    cache_root: Path
    workspace: Path
    events: Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class ScriptDefinition:
    path: str
    content: bytes


@dataclass(frozen=True)
class SkillDefinition:
    plugin: str
    version: str
    skill: str
    body: bytes
    scripts: tuple[ScriptDefinition, ...]


@dataclass(frozen=True)
class SkillCatalog:
    skills: tuple[SkillDefinition, ...] = ()

    @classmethod
    def from_packages(cls, packages: Mapping[str, Path]) -> "SkillCatalog":
        definitions: list[SkillDefinition] = []
        for plugin, supplied_root in sorted(packages.items()):
            root = supplied_root.absolute()
            manifest = _manifest(root)
            if not _IDENTITY.fullmatch(plugin) or manifest is None or manifest[0] != plugin:
                raise ValueError(f"Invalid frozen plugin identity: {plugin!r} at {root}")
            version = manifest[1]
            plugin_skills: list[SkillDefinition] = []
            ambiguous_ownership = False
            for path in sorted((root / "skills").glob("*/SKILL.md")):
                body = _read_regular(path, root)
                skill = path.parent.name
                if body is None or not _IDENTITY.fullmatch(skill) or _skill_name(body) != skill:
                    raise ValueError(f"Invalid frozen skill body or identity: {path}")
                scripts: list[ScriptDefinition] = []
                raw_references = _SCRIPT_REFERENCE.findall(body.decode("utf-8"))
                if any(".." in Path(reference).parts for reference in raw_references):
                    ambiguous_ownership = True
                references = {
                    Path(reference).as_posix()
                    for reference in raw_references
                    if ".." not in Path(reference).parts
                }
                for relative in sorted(references):
                    content = _read_regular(root / relative, root)
                    if content is not None:
                        scripts.append(ScriptDefinition(relative, content))
                plugin_skills.append(SkillDefinition(plugin, version, skill, body, tuple(scripts)))
            owners = Counter(script.path for skill in plugin_skills for script in skill.scripts)
            if ambiguous_ownership:
                logger.warning(
                    "Script attribution disabled for %s: ambiguous relative reference", plugin
                )
            definitions.extend(
                replace(
                    skill,
                    scripts=tuple(
                        s for s in skill.scripts if not ambiguous_ownership and owners[s.path] == 1
                    ),
                )
                for skill in plugin_skills
            )
        logger.info("Frozen skill evidence catalog contains %d skills", len(definitions))
        return cls(tuple(definitions))


def _read_regular(path: Path, root: Path) -> bytes | None:
    try:
        if ".." in path.parts or not path.is_relative_to(root):
            return None
        # Reject symlink aliases as well as escapes; evidence names the installed file itself.
        if path.resolve(strict=True) != path.absolute() or not path.is_file():
            return None
        return path.read_bytes()
    except (OSError, RuntimeError):
        return None


def _manifest(root: Path) -> tuple[str, str] | None:
    content = _read_regular(root / "plugin.json", root)
    if content is None:
        return None
    try:
        data = json.loads(content)
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    name, version = data.get("name"), data.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        return None
    if not version or version in {".", ".."} or any(c in version for c in "/\\\0"):
        return None
    return name, version


def _skill_name(body: bytes) -> str | None:
    try:
        text = body.decode("utf-8")
        if not text.startswith("---\n"):
            return None
        header, separator, _ = text[4:].partition("\n---\n")
        if not separator:
            return None
        metadata = yaml.safe_load(header)
    except (UnicodeDecodeError, yaml.YAMLError):
        return None
    name = metadata.get("name") if isinstance(metadata, dict) else None
    return name if isinstance(name, str) else None


def _literal_argv(command: str) -> list[str] | None:
    quote = ""
    escaped = False
    for character in command:
        if escaped:
            if character in "\r\n":
                return None
            escaped = False
        elif character == "\\" and quote != "'":
            escaped = True
        elif character == quote:
            quote = ""
        elif character in "'\"" and not quote:
            quote = character
        elif (
            (quote != "'" and character in "$`")
            or (not quote and character in ";&|<>#\r\n(){}*?[]~")
            or character == "\0"
        ):
            return None
    if quote or escaped:
        return None
    try:
        return shlex.split(command)
    except ValueError:
        return None


def _program(token: str, names: set[str]) -> bool:
    return token in names or any(
        token == f"{directory}/{name}" for directory in ("/bin", "/usr/bin") for name in names
    )


def _command_argv(command: str) -> list[str] | None:
    argv = _literal_argv(command)
    if argv and _program(argv[0], {"bash", "sh", "zsh"}) and len(argv) == 3 and argv[1] == "-lc":
        return _literal_argv(argv[2])
    return argv


@dataclass(frozen=True)
class _InstalledSkill:
    definition: SkillDefinition
    package: Path
    body_path: Path


def _installed_skill(path: Path, catalog: SkillCatalog, cache_root: Path) -> _InstalledSkill | None:
    if not path.is_absolute() or ".." in path.parts or not path.is_relative_to(cache_root):
        return None
    parts = path.relative_to(cache_root).parts
    if len(parts) != 6 or parts[3] != "skills" or parts[5] != "SKILL.md":
        return None
    _, plugin, version, _, skill, _ = parts
    definition = next(
        (s for s in catalog.skills if (s.plugin, s.version, s.skill) == (plugin, version, skill)),
        None,
    )
    if definition is None:
        return None
    package = cache_root.joinpath(*parts[:3])
    if _manifest(package) != (plugin, version):
        return None
    if _read_regular(path, package) != definition.body:
        return None
    return _InstalledSkill(definition, package, path)


def _installed_catalog_matches(installed: _InstalledSkill, catalog: SkillCatalog) -> bool:
    definitions = tuple(s for s in catalog.skills if s.plugin == installed.definition.plugin)
    paths = set((installed.package / "skills").glob("*/SKILL.md"))
    expected = {installed.package / "skills" / s.skill / "SKILL.md" for s in definitions}
    return paths == expected and all(
        _read_regular(installed.package / "skills" / s.skill / "SKILL.md", installed.package)
        == s.body
        for s in definitions
    )


def _completed_command(event: Mapping[str, Any]) -> Mapping[str, Any] | None:
    item = event.get("item")
    if event.get("type") != "item.completed" or not isinstance(item, Mapping):
        return None
    if item.get("type") != "command_execution" or item.get("status") != "completed":
        return None
    if type(item.get("exit_code")) is not int or item.get("exit_code") != 0:
        return None
    return item if isinstance(item.get("command"), str) else None


def analyze_skill_evidence(catalog: SkillCatalog, context: EvidenceContext) -> SkillEvidence:
    if not isinstance(catalog, SkillCatalog) or not isinstance(context, EvidenceContext):
        raise TypeError("Skill evidence requires a SkillCatalog and EvidenceContext")
    cache_root = context.cache_root.absolute()
    observations: dict[tuple[str, str], SkillObservation] = {}
    loaded: dict[tuple[str, str], _InstalledSkill] = {}
    for ordinal, event in enumerate(context.events, 1):
        item = _completed_command(event)
        if item is None:
            continue
        command = item["command"]
        argv = _command_argv(command)
        if not argv:
            continue
        item_id = item.get("id", "")
        if not isinstance(item_id, str):
            continue
        if len(argv) == 2 and _program(argv[0], {"cat"}):
            installed = _installed_skill(Path(argv[1]), catalog, cache_root)
            output = item.get("aggregated_output")
            if installed is None or not isinstance(output, str):
                continue
            try:
                output_bytes = output.encode("utf-8")
            except UnicodeEncodeError:
                continue
            if output_bytes != installed.definition.body:
                continue
            definition = installed.definition
            key = definition.plugin, definition.skill
            reference = EvidenceReference(
                ordinal,
                item_id,
                str(installed.body_path),
                hashlib.sha256(definition.body).hexdigest(),
                command,
            )
            previous = observations.get(key, SkillObservation(*key, "loaded"))
            observations[key] = replace(previous, loads=(*previous.loads, reference))
            loaded[key] = installed
            continue
        candidate = (
            argv[1]
            if len(argv) > 1 and _program(argv[0], {"bash", "sh", "python", "python3"})
            else argv[0]
        )
        for key, installed in loaded.items():
            path = Path(candidate)
            if _installed_skill(installed.body_path, catalog, cache_root) is None:
                continue
            if not _installed_catalog_matches(installed, catalog):
                continue
            for script in installed.definition.scripts:
                expected = installed.package / script.path
                if path != expected or _read_regular(path, installed.package) != script.content:
                    continue
                reference = EvidenceReference(
                    ordinal, item_id, str(path), hashlib.sha256(script.content).hexdigest(), command
                )
                previous = observations[key]
                observations[key] = replace(
                    previous, state="workflow-observed", actions=(*previous.actions, reference)
                )
    return SkillEvidence(tuple(observations[key] for key in sorted(observations)))


def assess_skill_assertion(grader: Mapping[str, Any], evidence: SkillEvidence) -> SkillAssessment:
    name = str(grader.get("name", ""))
    unknown = SkillAssessment(
        name, "unknown", (), "No matching verified skill evidence was observed."
    )
    if grader.get("type") != "tool_used" or grader.get("tool") != "Skill":
        return replace(unknown, reason="Only Skill tool assertions have portable skill evidence.")
    if (
        type(grader.get("min", 1)) is not int
        or grader.get("min", 1) != 1
        or grader.get("max") is not None
    ):
        return replace(
            unknown, reason="Behavioral observations cannot establish absence or invocation counts."
        )
    pattern = grader.get("input_match", ".*")
    if not isinstance(pattern, str):
        return replace(unknown, reason="Skill input_match must be a regular expression string.")
    try:
        matcher = re.compile(pattern)
    except re.error:
        return replace(unknown, reason="Skill input_match is not a valid regular expression.")
    matches = tuple(
        observation
        for observation in evidence.observations
        if observation.state != "unknown"
        and matcher.search(json.dumps({"skill": f"{observation.plugin}:{observation.skill}"}))
    )
    if not matches:
        return unknown
    state: EvidenceState = "workflow-observed" if any(s.actions for s in matches) else "loaded"
    return SkillAssessment(
        name,
        state,
        tuple(f"{s.plugin}:{s.skill}" for s in matches),
        "Verified body load followed by an attributable packaged-script action; "
        "native activation remains unproven."
        if state == "workflow-observed"
        else "Verified complete installed skill-body load; native activation remains unproven.",
    )
