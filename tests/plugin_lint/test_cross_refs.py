import re
from pathlib import Path

from .conftest import PLUGINS_DIR, PluginFile, assert_no_violations

ROOTED_PATH = re.compile(
    r"(?P<root><SKILL_DIR>|\$\{CLAUDE_SKILL_DIR\}|<PLUGIN_ROOT>|\$\{CLAUDE_PLUGIN_ROOT\})"
    r"/(?P<path>[A-Za-z0-9_./-]+)"
)
MARKDOWN_LINK = re.compile(r"\]\((?P<target>\.{1,2}/[^)\s#]+)")
QUESTION_HEADER = re.compile(r"\bheader(?::|\s)\s*[`\"](?P<header>[^`\"\n]+)[`\"]")
MAX_HEADER_CHARS = 12


def _inside(target: Path, root: Path) -> bool:
    return target.resolve().is_relative_to(root.resolve())


def _rooted_target(source: PluginFile, root: str, path: str) -> Path | None:
    if "SKILL" not in root:
        return PLUGINS_DIR / source.plugin / path
    return source.skill_dir / path if source.skill_dir is not None else None


class TestPaths:
    def test_rooted_paths_resolve_inside_the_plugin(
        self, plugin_files: tuple[PluginFile, ...]
    ) -> None:
        violations: list[str] = []
        for source in plugin_files:
            for match in ROOTED_PATH.finditer(source.text):
                path = match["path"].rstrip(".,:;")
                if path.endswith("/") or "*" in path:
                    continue
                target = _rooted_target(source, match["root"], path)
                if target is None:
                    violations.append(f"{source.relative}: {match[0]} outside a skill")
                elif not _inside(target, PLUGINS_DIR):
                    violations.append(f"{source.relative}: {match[0]} leaves the marketplace")
                elif not target.exists():
                    violations.append(f"{source.relative}: {match[0]} does not exist")
        assert_no_violations(violations)

    def test_relative_links_stay_inside_the_plugin(
        self, plugin_files: tuple[PluginFile, ...]
    ) -> None:
        violations: list[str] = []
        for source in plugin_files:
            for match in MARKDOWN_LINK.finditer(source.text):
                target = source.path.parent / match["target"]
                if not _inside(target, PLUGINS_DIR / source.plugin):
                    violations.append(
                        f"{source.relative}: link {match['target']} leaves the plugin"
                    )
                elif not target.exists():
                    violations.append(f"{source.relative}: link {match['target']} does not exist")
        assert_no_violations(violations)


class TestQuestions:
    def test_question_headers_fit_twelve_characters(
        self, plugin_files: tuple[PluginFile, ...]
    ) -> None:
        violations = [
            f"{source.relative}: header {match['header']!r} is over {MAX_HEADER_CHARS} characters"
            for source in plugin_files
            if source.skill_dir is not None
            for match in QUESTION_HEADER.finditer(source.text)
            if len(match["header"]) > MAX_HEADER_CHARS and "<" not in match["header"]
        ]
        assert_no_violations(violations)
