import re
from pathlib import Path

from .conftest import PLUGINS_DIR, REPO_ROOT, PluginFile, assert_no_violations, split_fences
from .dispatch_scan import AGENT_NAME

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


MANIFEST_LINE = re.compile(r"^\s*Dispatching .* in parallel\s*$", re.MULTILINE)
MANIFEST = re.compile(r"Dispatching [^—\n]+ — (?:\d+|<[^>]+>) agents in parallel")
ROLLUP_LINE = re.compile(r"^\s*Wave complete.*$", re.MULTILINE)
ROLLUP = re.compile(r"Wave complete(?: \([^()\n]+\))? — <returned>/(?:\d+|<[^>]+>) agents returned")
_PARALLEL = r"(?:in parallel|single message|parallel tool calls)"
PARALLEL_DISPATCH = re.compile(
    rf"\b(?:[Dd]ispatch|[Ss]pawn|[Ll]aunch)\w*\b[^\n]*`{AGENT_NAME}`[^\n]*{_PARALLEL}"
    rf"|{_PARALLEL}[^\n]*`{AGENT_NAME}`"
)
# Skills whose parallel wording isn't a wave: one agent beside inline work, or a quoted shortcut.
NOT_A_WAVE = {
    "plugins/mz-knowledge/skills/vault-review": "moc-gap-detector runs alone beside inline scoring",
    "plugins/mz-knowledge/skills/vault-research": "the wording quotes a rationalization it rejects",
}


def _body_lines(text: str) -> list[tuple[int, str]]:
    """Numbered lines after the frontmatter."""
    head = FRONTMATTER.match(text)
    offset = head.end() if head else 0
    first = text[:offset].count("\n") + 1
    return list(enumerate(text[offset:].splitlines(), start=first))


def _wave_units(files: tuple[PluginFile, ...]) -> dict[str, str]:
    """Text per skill directory or per other file, since a SKILL.md may leave waves to phases."""
    units: dict[str, list[str]] = {}
    for source in files:
        key = source.skill_dir or source.path
        units.setdefault(key.relative_to(REPO_ROOT).as_posix(), []).append(source.text)
    return {key: "\n".join(texts) for key, texts in units.items()}


def _has_manifest(text: str) -> bool:
    return bool(MANIFEST_LINE.search(text)) or "pre-dispatch manifest" in text


def _has_rollup(text: str) -> bool:
    return bool(ROLLUP_LINE.search(text)) or "post-wave rollup" in text


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


class TestWaves:
    def test_wave_headers_follow_the_form(self, plugin_files: tuple[PluginFile, ...]) -> None:
        violations = [
            f"{source.relative}: {match[0].strip()!r} doesn't follow the {form.pattern!r} form"
            for source in plugin_files
            for line, form in ((MANIFEST_LINE, MANIFEST), (ROLLUP_LINE, ROLLUP))
            for match in line.finditer(source.text)
            if not form.fullmatch(match[0].strip())
        ]
        assert_no_violations(violations)

    def test_manifest_and_rollup_come_in_pairs(self, plugin_files: tuple[PluginFile, ...]) -> None:
        violations = [
            f"{unit}: has a {'manifest' if _has_manifest(text) else 'rollup'} but not the other"
            for unit, text in _wave_units(plugin_files).items()
            if _has_manifest(text) != _has_rollup(text)
        ]
        assert_no_violations(violations)

    def test_parallel_dispatch_has_a_manifest(self, plugin_files: tuple[PluginFile, ...]) -> None:
        violations = [
            f"{unit}: dispatches agents in parallel without a pre-dispatch manifest"
            for unit, text in _wave_units(plugin_files).items()
            if unit not in NOT_A_WAVE and PARALLEL_DISPATCH.search(text) and not _has_manifest(text)
        ]
        assert_no_violations(violations)

    def test_not_a_wave_exemptions_are_current(self, plugin_files: tuple[PluginFile, ...]) -> None:
        units = _wave_units(plugin_files)
        stale = sorted(
            unit
            for unit in NOT_A_WAVE
            if unit not in units or not PARALLEL_DISPATCH.search(units[unit])
        )
        assert not stale, f"exempt units no longer match the parallel pattern: {stale}"
