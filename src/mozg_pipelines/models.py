from enum import StrEnum
from graphlib import CycleError, TopologicalSorter
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


def _repository_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or value != value.strip()
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in value
    ):
        raise ValueError("path must be repository-relative and cannot escape its root")
    return value


Identifier = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=1),
]
RepositoryPath = Annotated[str, AfterValidator(_repository_path)]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Provider(StrEnum):
    CLAUDE = "claude"
    CODEX = "codex"


class ReasoningEffort(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProgressBackend(StrEnum):
    STATE_FILE = "state-file"


class ArgumentBinding(StrEnum):
    USER_REQUEST = "user-request"


class IssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class HookEvent(StrEnum):
    SESSION_START = "SessionStart"
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    PRE_COMPACT = "PreCompact"
    POST_COMPACT = "PostCompact"
    SESSION_END = "SessionEnd"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    SUBAGENT_START = "SubagentStart"
    SUBAGENT_STOP = "SubagentStop"
    STOP = "Stop"
    INTERRUPT = "Interrupt"


class HookScriptAdapter(StrEnum):
    PASSTHROUGH = "passthrough"
    USER_PROMPT_JOURNAL = "user-prompt-journal"


class PackageDisposition(StrEnum):
    READY = "ready"
    DEPENDENT = "dependent"
    BLOCKED = "blocked"


class ModelEffortPolicy(FrozenModel):
    fast: ReasoningEffort
    standard: ReasoningEffort
    critical: ReasoningEffort


class ProvenanceMarkers(FrozenModel):
    start: str = "<!-- mozg:provider-provenance:start -->"
    end: str = "<!-- mozg:provider-provenance:end -->"


class ProviderPolicy(FrozenModel):
    provider: Provider
    plugin_name: Identifier
    progress_backend: ProgressBackend
    argument_binding: ArgumentBinding
    model_efforts: ModelEffortPolicy
    forbidden_tokens: tuple[str, ...] = ()
    provenance_markers: ProvenanceMarkers = Field(default_factory=ProvenanceMarkers)


class SkillSpec(FrozenModel):
    name: Identifier
    plugin: Identifier
    source: RepositoryPath
    roles: tuple[Identifier, ...] = ()


class RoleSpec(FrozenModel):
    name: Identifier
    source: RepositoryPath
    reasoning_effort: ReasoningEffort


class RoleResourceSpec(FrozenModel):
    role: Identifier
    skill: Identifier
    target: RepositoryPath

    @model_validator(mode="after")
    def target_matches_role_and_skill(self) -> Self:
        expected = f"skills/{self.skill}/references/roles/{self.role}.md"
        if self.target != expected:
            raise ValueError(f"role resource target must be {expected}")
        return self


class HookEventMapping(FrozenModel):
    source_event: HookEvent
    target_event: HookEvent | None


class ScriptSpec(FrozenModel):
    source: RepositoryPath
    target: RepositoryPath
    adapter: HookScriptAdapter = HookScriptAdapter.PASSTHROUGH


class HookSpec(FrozenModel):
    source: RepositoryPath
    target: RepositoryPath
    events: tuple[HookEventMapping, ...] = ()


class ExactTransformSpec(FrozenModel):
    source: RepositoryPath
    match: NonEmptyText
    replacement: str


class PackagePlanSpec(FrozenModel):
    name: Identifier
    disposition: PackageDisposition
    dependencies: tuple[Identifier, ...] = ()
    blockers: tuple[NonEmptyText, ...] = ()
    # Skills that cannot work under Codex; the rest of the package still renders.
    excluded_skills: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def excluded_skills_are_unique(self) -> Self:
        duplicate = next(
            (name for name in self.excluded_skills if self.excluded_skills.count(name) > 1),
            None,
        )
        if duplicate is not None:
            raise ValueError(f"duplicate excluded skill: {duplicate}")
        return self

    @model_validator(mode="after")
    def disposition_matches_requirements(self) -> Self:
        if self.disposition is PackageDisposition.READY:
            if self.dependencies or self.blockers:
                raise ValueError("ready packages cannot declare dependencies or blockers")
        elif self.disposition is PackageDisposition.DEPENDENT:
            if not self.dependencies or self.blockers:
                raise ValueError(
                    "dependent packages require dependencies and cannot declare blockers"
                )
        elif not self.blockers:
            raise ValueError("blocked packages require at least one blocker")
        return self


class MigrationPlan(FrozenModel):
    schema_version: Literal[1]
    source_marketplace: RepositoryPath
    packages: tuple[PackagePlanSpec, ...]

    @model_validator(mode="after")
    def package_references_are_valid(self) -> Self:
        package_names = [package.name for package in self.packages]
        duplicate = next(
            (name for name in package_names if package_names.count(name) > 1),
            None,
        )
        if duplicate is not None:
            raise ValueError(f"duplicate package plan: {duplicate}")

        known_packages = frozenset(package_names)
        for package in self.packages:
            if package.name in package.dependencies:
                raise ValueError(f"package cannot depend on itself: {package.name}")
            unknown_dependencies = set(package.dependencies) - known_packages
            if unknown_dependencies:
                dependency = sorted(unknown_dependencies)[0]
                raise ValueError(f"package {package.name} depends on unknown package: {dependency}")
        try:
            TopologicalSorter(
                {package.name: package.dependencies for package in self.packages}
            ).prepare()
        except CycleError as error:
            raise ValueError(f"dependency cycle: {' -> '.join(error.args[1])}") from error
        return self


class Catalog(FrozenModel):
    schema_version: Literal[1]
    suite_name: Identifier
    skills: tuple[SkillSpec, ...]
    dependencies: tuple[Identifier, ...] = ()
    roles: tuple[RoleSpec, ...] = ()
    role_resources: tuple[RoleResourceSpec, ...] = ()
    hooks: tuple[HookSpec, ...] = ()
    # Hooks and skills both run files from scripts/, so scripts render whether or not hooks exist.
    scripts: tuple[ScriptSpec, ...] = ()
    transforms: tuple[ExactTransformSpec, ...] = ()
    # The plugin's shared/ folder (often a link to mz-base's); it renders to shared/ in the package.
    shared_root: RepositoryPath | None = None

    @model_validator(mode="after")
    def names_are_unique(self) -> Self:
        skill_names = [skill.name for skill in self.skills]
        duplicate_skill = next(
            (name for name in skill_names if skill_names.count(name) > 1),
            None,
        )
        if duplicate_skill is not None:
            raise ValueError(f"duplicate skill name: {duplicate_skill}")
        if self.suite_name in self.dependencies:
            raise ValueError(f"catalog cannot depend on itself: {self.suite_name}")

        role_names = [role.name for role in self.roles]
        duplicate_role = next(
            (name for name in role_names if role_names.count(name) > 1),
            None,
        )
        if duplicate_role is not None:
            raise ValueError(f"duplicate role name: {duplicate_role}")

        self._validate_role_resources(skill_names, role_names)
        self._validate_hook_targets()
        self._validate_script_targets()
        self._validate_transforms()
        return self

    def _validate_role_resources(
        self,
        skill_names: list[str],
        role_names: list[str],
    ) -> None:
        if not self.role_resources:
            return

        expected = {(skill.name, role) for skill in self.skills for role in skill.roles}
        actual = {(resource.skill, resource.role) for resource in self.role_resources}
        duplicate = next(
            (
                resource
                for resource in self.role_resources
                if sum(
                    candidate.skill == resource.skill and candidate.role == resource.role
                    for candidate in self.role_resources
                )
                > 1
            ),
            None,
        )
        if duplicate is not None:
            raise ValueError(f"duplicate role resource: {duplicate.skill}/{duplicate.role}")

        for resource in self.role_resources:
            if resource.role not in role_names:
                raise ValueError(f"role resource references unknown role: {resource.role}")
            if resource.skill not in skill_names:
                raise ValueError(f"role resource references unknown skill: {resource.skill}")
            if (resource.skill, resource.role) not in expected:
                raise ValueError(
                    "role resource must map a role declared by its owning skill: "
                    f"{resource.skill}/{resource.role}"
                )

        missing = expected - actual
        if missing:
            skill, role = sorted(missing)[0]
            raise ValueError(f"missing role resource: {skill}/{role}")

    def _validate_hook_targets(self) -> None:
        hook_targets = [hook.target for hook in self.hooks]
        duplicate_hook_target = next(
            (target for target in hook_targets if hook_targets.count(target) > 1),
            None,
        )
        if duplicate_hook_target is not None:
            raise ValueError(f"duplicate hook target: {duplicate_hook_target}")

        for hook in self.hooks:
            source_events = [event.source_event for event in hook.events]
            duplicate_source_event = next(
                (event for event in source_events if source_events.count(event) > 1),
                None,
            )
            if duplicate_source_event is not None:
                raise ValueError(f"duplicate hook event mapping: {duplicate_source_event}")

    def _validate_script_targets(self) -> None:
        script_targets = [script.target for script in self.scripts]
        duplicate_script_target = next(
            (target for target in script_targets if script_targets.count(target) > 1),
            None,
        )
        if duplicate_script_target is not None:
            raise ValueError(f"duplicate script target: {duplicate_script_target}")

    def _validate_transforms(self) -> None:
        transforms = [(transform.source, transform.match) for transform in self.transforms]
        duplicate = next(
            (entry for entry in transforms if transforms.count(entry) > 1),
            None,
        )
        if duplicate is not None:
            source, match = duplicate
            raise ValueError(f"duplicate exact transform for {source}: {match!r}")


class ValidationIssue(FrozenModel):
    severity: IssueSeverity
    code: Identifier
    message: str
    path: RepositoryPath | None = None
    subject: str | None = None


class ValidationReport(FrozenModel):
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return all(issue.severity is not IssueSeverity.ERROR for issue in self.issues)
