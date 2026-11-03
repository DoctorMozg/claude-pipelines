import json

import pytest

from .conftest import PLUGINS_DIR, REPO_ROOT

REPOSITORY_URL = "https://github.com/DoctorMozg/claude-pipelines"
# The plugins submitted to Anthropic's directory; the rest stay marketplace-only.
DIRECTORY_PLUGINS = (
    "mz-base",
    "mz-creative",
    "mz-design",
    "mz-dev-git",
    "mz-dev-pipe",
    "mz-funny",
    "mz-gov",
    "mz-knowledge",
    "mz-research-pipe",
)


def _manifest(plugin: str) -> dict[str, object]:
    return json.loads((PLUGINS_DIR / plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))


class TestDirectoryManifests:
    def test_every_directory_plugin_is_in_the_marketplace(self) -> None:
        marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        listed = {entry["name"] for entry in marketplace["plugins"]}
        assert set(DIRECTORY_PLUGINS) <= listed

    @pytest.mark.parametrize("plugin", DIRECTORY_PLUGINS)
    def test_manifest_carries_listing_fields(self, plugin: str) -> None:
        manifest = _manifest(plugin)
        assert isinstance(manifest.get("displayName"), str) and manifest["displayName"].strip()
        assert manifest.get("homepage") == f"{REPOSITORY_URL}/tree/master/plugins/{plugin}"
        assert manifest.get("repository") == REPOSITORY_URL

    @pytest.mark.parametrize("plugin", DIRECTORY_PLUGINS)
    def test_dependencies_are_directory_plugins(self, plugin: str) -> None:
        # A listed plugin whose dependency is marketplace-only would fail to install from the directory.
        missing = sorted(set(_manifest(plugin).get("dependencies", [])) - set(DIRECTORY_PLUGINS))
        assert missing == [], f"{plugin} depends on plugins outside the directory set"
