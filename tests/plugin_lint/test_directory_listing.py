import json
import re
import struct
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
# The directory screens 256 KiB of printable text per image or font and holds the file past that.
# Compressed pixels run about 37% printable, so a 1024 px PNG icon goes over.
MAX_ASSET_PRINTABLE_BYTES = 256 * 1024
ASSET_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ttf", ".otf", ".woff", ".woff2"}
)
_PRINTABLE = bytes([9, 10, 13, *range(0x20, 0x7F)])
# The listing icon: a square PNG at .claude-plugin/icon.png, 512 to 2048 px a side, under 2 MB.
# 512 px is also what keeps an icon under the text screen above, so the floor is tight.
ICON_MIN_PX, ICON_MAX_PX = 512, 2048
ICON_MAX_BYTES = 2_000_000
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _manifest(plugin: str) -> dict[str, object]:
    path = PLUGINS_DIR / plugin / ".claude-plugin" / "plugin.json"
    manifest: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return manifest


def _readme(plugin: str) -> str:
    return (PLUGINS_DIR / plugin / "README.md").read_text(encoding="utf-8")


def printable_bytes(data: bytes) -> int:
    """Every printable byte in `data`, an upper bound on any run-based count the portal may use."""
    return len(data) - len(data.translate(None, _PRINTABLE))


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


class TestDirectoryAssets:
    @pytest.mark.parametrize("plugin", DIRECTORY_PLUGINS)
    def test_images_and_fonts_stay_under_the_text_screen(self, plugin: str) -> None:
        over = [
            f"{path.relative_to(PLUGINS_DIR)}: {printable_bytes(path.read_bytes()) // 1024} KiB"
            for path in sorted((PLUGINS_DIR / plugin).rglob("*"))
            if path.suffix.lower() in ASSET_SUFFIXES
            and printable_bytes(path.read_bytes()) > MAX_ASSET_PRINTABLE_BYTES
        ]
        assert over == [], "downscale or recompress each file so the directory doesn't hold it"

    @pytest.mark.parametrize("plugin", DIRECTORY_PLUGINS)
    def test_icon_meets_listing_rules(self, plugin: str) -> None:
        icon = PLUGINS_DIR / plugin / ".claude-plugin" / "icon.png"
        assert icon.is_file(), f"{plugin} has no listing icon"
        data = icon.read_bytes()
        assert data.startswith(_PNG_SIGNATURE), f"{plugin} icon is not a PNG"
        width, height = struct.unpack(">II", data[16:24])
        assert width == height, f"{plugin} icon is {width}x{height}, not square"
        assert ICON_MIN_PX <= width <= ICON_MAX_PX, f"{plugin} icon is {width} px a side"
        assert len(data) < ICON_MAX_BYTES, f"{plugin} icon is {len(data)} bytes"

    def test_printable_count_ignores_control_and_high_bytes(self) -> None:
        assert printable_bytes(b"ab\tc\n\x00\x1f\x7f\x80\xff") == 5
