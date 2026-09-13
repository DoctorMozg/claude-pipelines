import json
import logging
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, cast

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
)

from mozg_pipelines.models import Identifier, RepositoryPath

logger = logging.getLogger(__name__)

SemanticVersion = Annotated[
    str,
    StringConstraints(
        pattern=(
            r"^(0|[1-9]\d*)\."
            r"(0|[1-9]\d*)\."
            r"(0|[1-9]\d*)"
            r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
            r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
            r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
        )
    ),
]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _plugin_relative_path(value: str) -> str:
    if not value.startswith("./"):
        raise ValueError("path must start with './'")
    return value


PluginPath = Annotated[RepositoryPath, AfterValidator(_plugin_relative_path)]


class ManifestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class ManifestAuthor(ManifestModel):
    name: NonEmptyText
    email: str | None = None
    url: str | None = None


class PluginInterface(ManifestModel):
    display_name: NonEmptyText = Field(alias="displayName")
    short_description: NonEmptyText = Field(alias="shortDescription")
    long_description: NonEmptyText = Field(alias="longDescription")
    developer_name: NonEmptyText = Field(alias="developerName")
    category: NonEmptyText
    capabilities: tuple[NonEmptyText, ...]
    default_prompt: tuple[NonEmptyText, ...] = Field(alias="defaultPrompt")


class OpenAIExtension(ManifestModel):
    hooks: PluginPath | tuple[PluginPath, ...] | None = None
    interface: PluginInterface | None = None


class PluginExtensions(ManifestModel):
    openai: OpenAIExtension | None = Field(default=None, alias="com.openai")


class PortableManifest(ManifestModel):
    schema_url: Literal["https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"] = Field(
        alias="$schema"
    )
    name: Identifier
    version: SemanticVersion
    description: NonEmptyText
    author: ManifestAuthor
    homepage: str | None = None
    repository: str | None = None
    license: str | None = None
    keywords: tuple[NonEmptyText, ...] = ()
    extensions: PluginExtensions | None = None


class LegacyPluginManifest(ManifestModel):
    name: Identifier
    version: SemanticVersion
    description: NonEmptyText
    author: ManifestAuthor
    skills: PluginPath
    interface: PluginInterface


class ManifestLoadFailure(StrEnum):
    MISSING = "missing"
    READ_ERROR = "read-error"
    INVALID_JSON = "invalid-json"
    INVALID_SCHEMA = "invalid-schema"


class ManifestLoadError(RuntimeError):
    def __init__(self, path: Path, kind: ManifestLoadFailure, message: str) -> None:
        super().__init__(f"Cannot load plugin manifest {path}: {message}")
        self.path = path
        self.kind = kind


def load_portable_manifest(path: Path) -> PortableManifest:
    return _load_manifest(path, PortableManifest)


def load_legacy_manifest(path: Path) -> LegacyPluginManifest:
    return _load_manifest(path, LegacyPluginManifest)


def _load_manifest[ManifestT: PortableManifest | LegacyPluginManifest](
    path: Path,
    manifest_type: type[ManifestT],
) -> ManifestT:
    logger.info("Loading plugin manifest from %s", path)
    try:
        contents = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        logger.error("Plugin manifest does not exist: %s", path)
        raise ManifestLoadError(path, ManifestLoadFailure.MISSING, "file does not exist") from error
    except (OSError, UnicodeError) as error:
        logger.error("Cannot read plugin manifest %s: %s", path, error)
        raise ManifestLoadError(path, ManifestLoadFailure.READ_ERROR, str(error)) from error

    try:
        payload: object = json.loads(contents)
    except json.JSONDecodeError as error:
        logger.error("Plugin manifest contains invalid JSON at %s: %s", path, error)
        raise ManifestLoadError(path, ManifestLoadFailure.INVALID_JSON, str(error)) from error

    try:
        return cast(ManifestT, manifest_type.model_validate(payload))
    except ValidationError as error:
        logger.error("Plugin manifest schema validation failed at %s: %s", path, error)
        raise ManifestLoadError(path, ManifestLoadFailure.INVALID_SCHEMA, str(error)) from error
