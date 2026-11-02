import re
from pathlib import Path

from .conftest import PLUGINS_DIR, PluginFile, assert_no_violations, split_fences

ROOTED_PATH = re.compile(
    r"(?P<root><SKILL_DIR>|\$\{CLAUDE_SKILL_DIR\}|<PLUGIN_ROOT>|\$\{CLAUDE_PLUGIN_ROOT\})"
    r"/(?P<path>[A-Za-z0-9_./-]+)"
)
MARKDOWN_LINK = re.compile(r"\]\((?P<target>\.{1,2}/[^)\s#]+)")
QUESTION_HEADER = re.compile(r"\bheader(?::|\s)\s*[`\"](?P<header>[^`\"\n]+)[`\"]")
MAX_HEADER_CHARS = 12
# Models over-apply all-caps rules; descriptions keep their trigger wording and are skipped.
EMPHASIS = re.compile(r"\b(?:MUST|ALWAYS|NEVER|IMPORTANT|NOT|ONLY|ANY|EVERY)\b")
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
# Code spans, quotes, hyphenated labels such as DOC-ONLY, and fixed names that hold a capital word.
NOT_EMPHASIS = re.compile(
    r"`[^`\n]*`|\"[^\"\n]*\"|\b[A-Z]+(?:-[A-Z]+)+\b|When NOT to [Uu]se|NOT FOUND|Logical NOT"
)


def _body_lines(text: str) -> list[tuple[int, str]]:
    """Numbered lines after the frontmatter."""
    head = FRONTMATTER.match(text)
    offset = head.end() if head else 0
    first = text[:offset].count("\n") + 1
    return list(enumerate(text[offset:].splitlines(), start=first))


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


class TestMarkdown:
    def test_code_fences_close(self, plugin_files: tuple[PluginFile, ...]) -> None:
        # An unclosed fence turns every later section into a code sample the model reads as data.
        violations = [
            f"{source.relative}: a {fence} fence is never closed"
            for source in plugin_files
            if (fence := split_fences(source.text)[1]) is not None
        ]
        assert_no_violations(violations)

    def test_bodies_skip_all_caps_emphasis(self, plugin_files: tuple[PluginFile, ...]) -> None:
        violations = [
            f"{source.relative}:{number}: all-caps {match[0]!r}; write it in lowercase"
            for source in plugin_files
            for number, line in _body_lines(source.text)
            if (match := EMPHASIS.search(NOT_EMPHASIS.sub("", line)))
        ]
        assert_no_violations(violations)
