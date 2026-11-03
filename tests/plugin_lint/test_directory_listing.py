import json
import re
from pathlib import Path

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
# The directory blocks a README with fewer than 40 words outside code.
MIN_README_WORDS = 40
_FENCED_CODE = re.compile(r"^```.*?^```", re.DOTALL | re.MULTILINE)
_LINK_TARGET = re.compile(
    r"\]\(<?([^)\s>]+)|\bsrc=\"([^\"]+)\"|^\[[^\]]+\]:\s*<?([^\s>]+)", re.MULTILINE
)
_EXTERNAL_TARGET = re.compile(r"[a-z][a-z0-9+.-]*:|#", re.IGNORECASE)


def _manifest(plugin: str) -> dict[str, object]:
    path = PLUGINS_DIR / plugin / ".claude-plugin" / "plugin.json"
    manifest: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return manifest


def _readme(plugin: str) -> str:
    return (PLUGINS_DIR / plugin / "README.md").read_text(encoding="utf-8")


def links_leaving_folder(markdown: str, folder: Path) -> list[str]:
    """Relative link and image targets that resolve outside `folder`; URLs and anchors are fine."""
    root = folder.resolve()
    targets = (
        next(group for group in match.groups() if group)
        for match in _LINK_TARGET.finditer(markdown)
    )
    return [
        target
        for target in targets
        if not _EXTERNAL_TARGET.match(target)
        and not (root / target.split("#", 1)[0]).resolve().is_relative_to(root)
    ]


class TestDirectoryManifests:
    def test_every_directory_plugin_is_in_the_marketplace(self) -> None:
        marketplace = json.loads(
            (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        listed = {entry["name"] for entry in marketplace["plugins"]}
        assert set(DIRECTORY_PLUGINS) <= listed

    @pytest.mark.parametrize("plugin", DIRECTORY_PLUGINS)
    def test_manifest_carries_listing_fields(self, plugin: str) -> None:
        manifest = _manifest(plugin)
        display_name = manifest.get("displayName")
        assert isinstance(display_name, str)
        assert display_name.strip()
        assert manifest.get("homepage") == f"{REPOSITORY_URL}/tree/master/plugins/{plugin}"
        assert manifest.get("repository") == REPOSITORY_URL

    @pytest.mark.parametrize("plugin", DIRECTORY_PLUGINS)
    def test_dependencies_are_directory_plugins(self, plugin: str) -> None:
        # A dependency that is only in the marketplace can't be installed from the directory.
        dependencies = _manifest(plugin).get("dependencies", [])
        assert isinstance(dependencies, list)
        missing = sorted(set(dependencies) - set(DIRECTORY_PLUGINS))
        assert missing == [], f"{plugin} depends on plugins outside the directory set"


class TestDirectoryReadmes:
    @pytest.mark.parametrize("plugin", DIRECTORY_PLUGINS)
    def test_readme_has_enough_prose(self, plugin: str) -> None:
        words = len(_FENCED_CODE.sub("", _readme(plugin)).split())
        assert words >= MIN_README_WORDS, f"{plugin}/README.md has {words} words outside code"

    @pytest.mark.parametrize("plugin", DIRECTORY_PLUGINS)
    def test_readme_discloses_data_handling(self, plugin: str) -> None:
        assert re.search(r"^## Data and network$", _readme(plugin), re.MULTILINE)

    @pytest.mark.parametrize("plugin", DIRECTORY_PLUGINS)
    def test_readme_links_stay_inside_the_plugin(self, plugin: str) -> None:
        # The listing shows the README outside the repo, so a link out of the folder breaks.
        assert links_leaving_folder(_readme(plugin), PLUGINS_DIR / plugin) == []

    @pytest.mark.parametrize(
        ("markdown", "leaving"),
        [
            ("[docs](docs/usage.md) and ![logo](assets/logo.png)", []),
            ("[web](https://example.com) [mail](mailto:a@b.c) [top](#install)", []),
            ("[base](../mz-base/README.md)", ["../mz-base/README.md"]),
            ('<img src="../../assets/hero.webp" alt="hero">', ["../../assets/hero.webp"]),
            ("[guide]: ../../guidelines/GUIDE.md", ["../../guidelines/GUIDE.md"]),
            ("[sneaky](skills/../../mz-gov/)", ["skills/../../mz-gov/"]),
        ],
    )
    def test_link_check_flags_only_targets_outside_the_folder(
        self, markdown: str, leaving: list[str]
    ) -> None:
        assert links_leaving_folder(markdown, PLUGINS_DIR / "mz-funny") == leaving
