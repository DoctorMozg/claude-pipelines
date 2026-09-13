from collections.abc import Callable
from pathlib import Path

import pytest

from mozg_pipelines.models import (
    ArgumentBinding,
    Catalog,
    ModelEffortPolicy,
    ProgressBackend,
    Provider,
    ProviderPolicy,
    ReasoningEffort,
    RoleSpec,
    SkillSpec,
)
from mozg_pipelines.rendering import CodexPackageSpec


@pytest.fixture
def write_skill() -> Callable[[Path, str], None]:
    def write(path: Path, body: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '---\nname: "ask"\ndescription: "Research a codebase question."\n---\n\n' + body,
            encoding="utf-8",
        )

    return write


@pytest.fixture
def write_role() -> Callable[[Path], None]:
    def write(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            """---
name: pipeline-researcher
description: Researches a codebase before implementation.
tools: Read, Grep, Glob
model: sonnet
effort: high
---

Research the repository and return evidence-backed findings.
""",
            encoding="utf-8",
        )

    return write


@pytest.fixture
def valid_catalog() -> Catalog:
    return Catalog(
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
        roles=(
            RoleSpec(
                name="pipeline-researcher",
                source="plugins/mz-dev-pipe/agents/pipeline-researcher.md",
                reasoning_effort=ReasoningEffort.MEDIUM,
            ),
        ),
    )


@pytest.fixture
def codex_policy() -> ProviderPolicy:
    return ProviderPolicy(
        provider=Provider.CODEX,
        plugin_name="mozg-pipelines",
        progress_backend=ProgressBackend.STATE_FILE,
        argument_binding=ArgumentBinding.USER_REQUEST,
        model_efforts=ModelEffortPolicy(
            fast=ReasoningEffort.LOW,
            standard=ReasoningEffort.MEDIUM,
            critical=ReasoningEffort.HIGH,
        ),
        forbidden_tokens=("model: sonnet", "TaskCreate"),
    )


@pytest.fixture
def package_spec_factory(
    valid_catalog: Catalog,
    codex_policy: ProviderPolicy,
) -> Callable[[Path, str], CodexPackageSpec]:
    def create(tmp_path: Path, version: str) -> CodexPackageSpec:
        return CodexPackageSpec(
            catalog=valid_catalog,
            policy=codex_policy,
            source_root=tmp_path / "source",
            package_root=tmp_path / "rendered/mozg-pipelines",
            version=version,
            description="Provider-native development and research pipelines for Codex.",
            author_name="DoctorMozg",
        )

    return create
