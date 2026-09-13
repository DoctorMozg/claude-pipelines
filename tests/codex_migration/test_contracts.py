import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from mozg_pipelines.manifest import PortableManifest, load_portable_manifest
from mozg_pipelines.models import (
    Catalog,
    ExactTransformSpec,
    ReasoningEffort,
    RoleResourceSpec,
    RoleSpec,
    SkillSpec,
)
from mozg_pipelines.rendering import CodexPackageSpec
from mozg_pipelines.validation import (
    CatalogLoadError,
    CatalogLoadFailure,
    load_catalog,
)


def test_load_catalog_returns_strict_models(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.toml"
    catalog_path.write_text(
        """
schema_version = 1
suite_name = "mozg-pipelines"

[[skills]]
name = "ask"
plugin = "mz-dev-pipe"
source = "plugins/mz-dev-pipe/skills/ask"
roles = ["pipeline-researcher"]

[[roles]]
name = "pipeline-researcher"
source = "plugins/mz-dev-pipe/agents/pipeline-researcher.md"
reasoning_effort = "medium"
""".strip(),
        encoding="utf-8",
    )

    catalog = load_catalog(catalog_path)

    assert catalog.suite_name == "mozg-pipelines"
    assert catalog.skills == (
        SkillSpec(
            name="ask",
            plugin="mz-dev-pipe",
            source="plugins/mz-dev-pipe/skills/ask",
            roles=("pipeline-researcher",),
        ),
    )
    assert catalog.roles == (
        RoleSpec(
            name="pipeline-researcher",
            source="plugins/mz-dev-pipe/agents/pipeline-researcher.md",
            reasoning_effort=ReasoningEffort.MEDIUM,
        ),
    )


@pytest.mark.parametrize(
    "source",
    ["/absolute/SKILL.md", "../outside/SKILL.md", "skills/../../outside/SKILL.md"],
)
def test_source_paths_must_stay_inside_the_repository(source: str) -> None:
    with pytest.raises(ValidationError, match="repository-relative"):
        SkillSpec(name="ask", plugin="mz-dev-pipe", source=source)


def test_catalog_rejects_duplicate_names() -> None:
    skill = SkillSpec(
        name="ask",
        plugin="mz-dev-pipe",
        source="plugins/mz-dev-pipe/skills/ask",
    )

    with pytest.raises(ValidationError, match="duplicate skill name: ask"):
        Catalog(schema_version=1, suite_name="mozg-pipelines", skills=(skill, skill))


def test_catalog_rejects_duplicate_role_names() -> None:
    role = RoleSpec(
        name="pipeline-researcher",
        source="plugins/mz-dev-pipe/agents/pipeline-researcher.md",
        reasoning_effort=ReasoningEffort.MEDIUM,
    )

    with pytest.raises(ValidationError, match="duplicate role name: pipeline-researcher"):
        Catalog(schema_version=1, suite_name="mozg-pipelines", skills=(), roles=(role, role))


def test_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SkillSpec.model_validate_json(
            '{"name":"ask","plugin":"mz-dev-pipe",'
            '"source":"plugins/mz-dev-pipe/skills/ask","unexpected":true}'
        )


def test_load_portable_manifest_returns_strict_model(tmp_path: Path) -> None:
    manifest_path = tmp_path / "plugin.json"
    manifest_path.write_text(
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "mz-dev-pipe",
                "version": "0.49.0",
                "description": "Development workflows for Codex.",
                "author": {"name": "DoctorMozg"},
                "extensions": {"com.openai": {"hooks": "./hooks/hooks.json"}},
            }
        ),
        encoding="utf-8",
    )

    manifest = load_portable_manifest(manifest_path)

    assert manifest.name == "mz-dev-pipe"
    assert manifest.extensions is not None
    assert manifest.extensions.openai is not None
    assert manifest.extensions.openai.hooks == "./hooks/hooks.json"


def test_portable_manifest_rejects_non_relative_hook_path() -> None:
    with pytest.raises(ValidationError, match=r"path must start with '\./'"):
        PortableManifest.model_validate(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "mz-dev-pipe",
                "version": "0.49.0",
                "description": "Development workflows for Codex.",
                "author": {"name": "DoctorMozg"},
                "extensions": {"com.openai": {"hooks": "hooks/hooks.json"}},
            }
        )


def test_catalog_rejects_unknown_role_resource() -> None:
    role = RoleSpec(
        name="pipeline-researcher",
        source="plugins/mz-dev-pipe/agents/pipeline-researcher.md",
        reasoning_effort=ReasoningEffort.MEDIUM,
    )
    skill = SkillSpec(
        name="ask",
        plugin="mz-dev-pipe",
        source="plugins/mz-dev-pipe/skills/ask",
        roles=("pipeline-researcher",),
    )

    with pytest.raises(ValidationError, match="role resource references unknown role: unknown"):
        Catalog(
            schema_version=1,
            suite_name="mozg-pipelines",
            skills=(skill,),
            roles=(role,),
            role_resources=(
                RoleResourceSpec(
                    role="unknown",
                    skill="ask",
                    target="skills/ask/references/roles/unknown.md",
                ),
            ),
        )


def test_exact_transform_rejects_empty_match() -> None:
    with pytest.raises(ValidationError, match="at least 1 character"):
        ExactTransformSpec(
            source="plugins/mz-dev-pipe/skills/ask/SKILL.md",
            match="",
            replacement="Use Codex.",
        )


@pytest.mark.parametrize(
    ("content", "kind"),
    [
        ("schema_version =", CatalogLoadFailure.INVALID_TOML),
        (
            'schema_version = 2\nsuite_name = "mozg-pipelines"\nskills = []',
            CatalogLoadFailure.INVALID_SCHEMA,
        ),
    ],
)
def test_load_catalog_reports_invalid_input(
    tmp_path: Path,
    content: str,
    kind: CatalogLoadFailure,
) -> None:
    catalog_path = tmp_path / "catalog.toml"
    catalog_path.write_text(content, encoding="utf-8")

    with pytest.raises(CatalogLoadError) as caught:
        load_catalog(catalog_path)

    assert caught.value.path == catalog_path
    assert caught.value.kind is kind


def test_load_catalog_reports_missing_file(tmp_path: Path) -> None:
    catalog_path = tmp_path / "missing.toml"

    with pytest.raises(CatalogLoadError) as caught:
        load_catalog(catalog_path)

    assert caught.value.path == catalog_path
    assert caught.value.kind is CatalogLoadFailure.MISSING


def test_package_spec_accepts_strict_semver_prerelease(
    tmp_path: Path,
    package_spec_factory: Callable[[Path, str], CodexPackageSpec],
) -> None:
    spec = package_spec_factory(tmp_path, "1.2.3-rc.1+build.7")

    assert spec.version == "1.2.3-rc.1+build.7"
