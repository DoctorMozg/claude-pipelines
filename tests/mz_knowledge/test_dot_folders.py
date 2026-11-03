"""Every mz-knowledge vault scan skips dot-folders, the way Obsidian does."""

import os
import re
import shlex
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = REPO_ROOT / "plugins/mz-knowledge"
SOURCE_GLOBS = ("skills/*/SKILL.md", "skills/*/phases/*.md", "agents/*.md", "scripts/*.sh")
PLUGIN_TEXT_FILES = sorted(
    path for path in PLUGIN.rglob("*") if path.suffix in {".md", ".sh"} and path.is_file()
)

EXCLUSION_CUE = re.compile(r"exclud|includ|skip|ignor|-not\s+-path", re.I)
VAULT_FIND = re.compile(r"""\bfind\s+["']?(?:<vault|\$\{?vault)[^|;]*\*\.md""", re.I)
RECURSIVE_MD_GLOB = re.compile(r"\*\*/\*\.md")
PROSE_MD_SCAN = re.compile(r"\b(?:all|every|any)\s+`?\.md`?\s+files?\b", re.I)
# Globbing a dot-folder itself is deliberate, e.g. obsidian-init checking its own scaffold.
DELIBERATE_DOT_GLOB = re.compile(r"(?:<vault>|\$\{?VAULT\}?)/\.[\w-]+/\*\*", re.I)
FIND_COMMAND = re.compile(r"\bfind\s+\S+.*\s-(?:i?name|i?path|type)\s")

FIND_MINDEPTH_ONE = re.compile(r"-mindepth\s+1\b")
FIND_DOT_PRUNE = re.compile(r"""-name\s+(['"])\.\*\1\s+-prune\b""")
# A -path test also sees the vault's own path, so a vault under `~/.vaults/` matches nothing.
FULL_PATH_DOT_TEST = re.compile(r"""-i?(?:path|wholename)\s+['"]?\*/\.\*""")
SEGMENT_RULE = re.compile(r"segment (?:that )?start(?:s|ing) with", re.I)
VAULT_ROOT_ANCHOR = re.compile(r"below (?:the vault root|`vault_path`)", re.I)
DOCUMENTED_VAULT_FIND = re.compile(r"""`(find\s+["']?<vault>["']?\s[^`]*)`""")
FIND_SIDE_EFFECT = re.compile(r"\s-(?:exec|execdir|ok|okdir|delete|fprint\w*|fls)\b")
PROSE_DOT_RULE = re.compile(
    r"dot[- ]?(?:folder|dir|segment|prefixed)|hidden (?:folder|dir)"
    r"|(?:start|begin)(?:s|ing)?\s+with\s+(?:a\s+)?(?:dot\b|`\.`|'\.'|\"\.\"|\.(?=[\s,;:)]|$))",
    re.I,
)
HEADING = re.compile(r"^#{1,6}\s")
FENCE = re.compile(r"^\s*(?:```|~~~)")


@dataclass(frozen=True)
class ScanLine:
    number: int
    text: str
    step: str


def _shell_lines(text: str) -> list[tuple[int, str, str]]:
    lines: list[tuple[int, str, str]] = []
    pending: list[str] = []
    start = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        if not pending:
            start = number
        pending.append(raw.removesuffix("\\"))
        if raw.endswith("\\"):
            continue
        joined = " ".join(pending)
        pending = []
        if not joined.lstrip().startswith("#"):
            lines.append((start, joined, joined))
    return lines


def _markdown_lines(text: str) -> list[tuple[int, str, str]]:
    sections: list[list[tuple[int, str]]] = [[]]
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and HEADING.match(line):
            sections.append([])
        sections[-1].append((number, line))
    return [
        (number, line, "\n".join(body for _, body in section))
        for section in sections
        for number, line in section
    ]


def _is_vault_scan(line: str) -> bool:
    if DELIBERATE_DOT_GLOB.search(line):
        return False
    if ".obsidian" in line and EXCLUSION_CUE.search(line):
        return True
    return any(pattern.search(line) for pattern in (VAULT_FIND, RECURSIVE_MD_GLOB, PROSE_MD_SCAN))


def scan_lines(path: Path) -> list[ScanLine]:
    text = path.read_text(encoding="utf-8")
    candidates = _shell_lines(text) if path.suffix == ".sh" else _markdown_lines(text)
    return [ScanLine(n, line, step) for n, line, step in candidates if _is_vault_scan(line)]


def prunes_dot_entries(command: str) -> bool:
    # Without -mindepth 1 a vault root named `.vault`, or `.` itself, is pruned whole.
    return bool(FIND_MINDEPTH_ONE.search(command) and FIND_DOT_PRUNE.search(command))


def skips_dot_folders(scan: ScanLine) -> bool:
    if prunes_dot_entries(scan.text):
        return True
    # A find command runs as written, so prose elsewhere in the step does not filter it.
    if FIND_COMMAND.search(scan.text):
        return False
    return PROSE_DOT_RULE.search(scan.step) is not None


def _source_files() -> list[Path]:
    return sorted(path for pattern in SOURCE_GLOBS for path in PLUGIN.glob(pattern))


def _numbered_lines(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".sh":
        return [(number, line) for number, line, _ in _shell_lines(text)]
    return list(enumerate(text.splitlines(), start=1))


def _documented_vault_finds() -> list[tuple[str, str]]:
    return [
        (f"{path.relative_to(PLUGIN)}:{number}", match.group(1))
        for path in PLUGIN_TEXT_FILES
        if path.suffix == ".md"
        for number, line in _numbered_lines(path)
        for match in DOCUMENTED_VAULT_FIND.finditer(line)
    ]


SCANNING_FILES = [path for path in _source_files() if scan_lines(path)]
DOCUMENTED_FINDS = _documented_vault_finds()
VAULT_NOTES = frozenset({"note.md", "sub/deep.md"})
DOT_ENTRIES = (
    ".mz/memory/MEMORY.md",
    ".mz/task/2026_01_01_vault-health_x/state.md",
    ".obsidian/workspace.md",
    ".trash/old.md",
    "sub/.hidden/draft.md",
    ".dotfile.md",
)
# Old enough for every documented `-mtime +N` filter to keep the notes.
OLD_MTIME = time.time() - 400 * 86400

type WriteSource = Callable[[str, str], Path]


@pytest.fixture
def write_source(tmp_path: Path) -> WriteSource:
    def write(name: str, body: str) -> Path:
        path = tmp_path / name
        path.write_text(body, encoding="utf-8")
        return path

    return write


@pytest.fixture
def vault_under_dot_folder(tmp_path: Path) -> Path:
    vault = tmp_path / ".vaults" / "main"
    for relative in (*VAULT_NOTES, *DOT_ENTRIES):
        note = vault / relative
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text("# note\n", encoding="utf-8")
        os.utime(note, (OLD_MTIME, OLD_MTIME))
    return vault


class TestVaultScansSkipDotFolders:
    def test_every_source_glob_reaches_files(self) -> None:
        empty = [pattern for pattern in SOURCE_GLOBS if not any(PLUGIN.glob(pattern))]
        assert not empty, f"these globs match nothing under {PLUGIN}: {empty}"

    def test_discovery_finds_vault_scans(self) -> None:
        assert SCANNING_FILES, "no mz-knowledge file scans the vault; the detector has drifted"

    @pytest.mark.parametrize(
        "path", SCANNING_FILES, ids=[str(p.relative_to(PLUGIN)) for p in SCANNING_FILES]
    )
    def test_scan_skips_dot_folders(self, path: Path) -> None:
        misses = [
            f"  line {scan.number}: {scan.text.strip()}"
            for scan in scan_lines(path)
            if not skips_dot_folders(scan)
        ]
        assert not misses, (
            f"{path.relative_to(PLUGIN)} scans the vault without skipping dot-folders, "
            "which Obsidian ignores (`-mindepth 1 -name '.*' -prune` or the prose rule):\n"
            + "\n".join(misses)
        )


class TestFindPrunesDotEntries:
    def test_no_full_path_dot_test(self) -> None:
        hits = [
            f"  {path.relative_to(PLUGIN)}:{number}: {line.strip()}"
            for path in PLUGIN_TEXT_FILES
            for number, line in _numbered_lines(path)
            if FULL_PATH_DOT_TEST.search(line)
        ]
        assert not hits, (
            "these lines test the whole path for a dot, so a vault under a dot-folder such as "
            "`~/.vaults/main` matches nothing; use `-mindepth 1 -name '.*' -prune` instead:\n"
            + "\n".join(hits)
        )

    def test_prose_rule_is_anchored_below_the_vault_root(self) -> None:
        hits = [
            f"  {path.relative_to(PLUGIN)}:{number}: {line.strip()}"
            for path in PLUGIN_TEXT_FILES
            for number, line in _numbered_lines(path)
            if SEGMENT_RULE.search(line) and not VAULT_ROOT_ANCHOR.search(line)
        ]
        assert not hits, (
            "a dot-segment rule without 'below the vault root' also skips a whole vault that "
            "sits under a dot-folder such as `~/.vaults/main`:\n" + "\n".join(hits)
        )

    def test_documented_finds_are_discovered(self) -> None:
        assert DOCUMENTED_FINDS, "no backticked `find <vault> ...` command found; extractor drifted"

    @pytest.mark.parametrize(
        ("where", "command"), DOCUMENTED_FINDS, ids=[where for where, _ in DOCUMENTED_FINDS]
    )
    def test_documented_find_lists_only_notes(
        self, vault_under_dot_folder: Path, where: str, command: str
    ) -> None:
        assert not FIND_SIDE_EFFECT.search(command), f"{where}: refusing to run `{command}`"
        argv = shlex.split(command.replace("<vault>", str(vault_under_dot_folder)))
        result = subprocess.run(argv, capture_output=True, text=True, check=True, timeout=10)
        found = {
            Path(line).relative_to(vault_under_dot_folder).as_posix()
            for line in result.stdout.splitlines()
        }
        assert found == VAULT_NOTES, (
            f"{where}: `{command}` listed {sorted(found)} in a vault under a dot-folder, "
            f"expected only {sorted(VAULT_NOTES)}"
        )


class TestScanDetector:
    @pytest.mark.parametrize(
        "line",
        [
            'Use `find <vault> -name "*.md" -not -path "*/.obsidian/*" -mtime +30` here.',
            "- Exclude the `.obsidian/` system directory from every scan.",
            "- Including `.obsidian/` system files in counts.",
            "Glob `<vault>/**/*.md` excluding `daily/` and `templates/`.",
            "List all `.md` files under `vault_path`.",
        ],
    )
    def test_obsidian_only_scan_fails(self, write_source: WriteSource, line: str) -> None:
        scans = scan_lines(write_source("agent.md", f"## Step\n\n{line}\n"))
        assert len(scans) == 1
        assert not skips_dot_folders(scans[0])

    @pytest.mark.parametrize(
        "line",
        [
            "Use `find <vault> -name \"*.md\" -not -path '*/.*' -mtime +30` here.",
            "Use `find <vault> -name '.*' -prune -o -name '*.md' -print` here.",
        ],
    )
    def test_find_without_prune_form_fails(self, write_source: WriteSource, line: str) -> None:
        scans = scan_lines(write_source("agent.md", f"## Step\n\nSkip dot-folders.\n{line}\n"))
        assert len(scans) == 1
        assert not skips_dot_folders(scans[0])

    @pytest.mark.parametrize(
        "command",
        [
            "find <vault> -name '*.md' -not -path '*/.*'",
            'find "$VAULT" ! -path "*/.*" -name "*.md"',
            "find <vault> -path '*/.*' -prune -o -name '*.md' -print",
            "find <vault> -name '*.md' -not -ipath '*/.*/*'",
        ],
    )
    def test_full_path_dot_test_is_caught(self, command: str) -> None:
        assert FULL_PATH_DOT_TEST.search(command)

    @pytest.mark.parametrize(
        "command",
        [
            "find <vault> -mindepth 1 -name '.*' -prune -o -name '*.md' -type f -print",
            "find <vault> -name '*.md' -not -path '*/.obsidian/*'",
            "find \"$moc_dir\" -maxdepth 1 -name '*.md' -not -name '.*'",
        ],
    )
    def test_other_find_is_not_caught(self, command: str) -> None:
        assert not FULL_PATH_DOT_TEST.search(command)

    @pytest.mark.parametrize(
        "line",
        [
            "Use `find <vault> -mindepth 1 -name '.*' -prune -o -name '*.md' -mtime +30 -print`.",
            "- Skip any path with a segment that starts with `.`, such as `.obsidian/`.",
            "List all `.md` files under `vault_path`, skipping dot-folders.",
        ],
    )
    def test_dot_folder_scan_passes(self, write_source: WriteSource, line: str) -> None:
        scans = scan_lines(write_source("agent.md", f"## Step\n\n{line}\n"))
        assert len(scans) == 1
        assert skips_dot_folders(scans[0])

    @pytest.mark.parametrize(
        "line",
        [
            "Walk up from the working directory until a `.obsidian/` folder is found.",
            "- Never create `.obsidian/`; the Obsidian app owns it.",
            "List `<vault>/**/*.md` and `<vault>/.mz/**` to confirm all planned files exist.",
            "mocs=$(find \"$moc_dir\" -maxdepth 1 -name '*.md' -not -name '.*')",
        ],
    )
    def test_non_scan_line_is_ignored(self, write_source: WriteSource, line: str) -> None:
        assert scan_lines(write_source("agent.md", f"## Step\n\n{line}\n")) == []

    def test_prose_rule_covers_its_own_step(self, write_source: WriteSource) -> None:
        path = write_source("agent.md", "## Step 1\n\nGlob `<vault>/**/*.md`.\nSkip dot-folders.\n")
        assert all(skips_dot_folders(scan) for scan in scan_lines(path))

    def test_prose_rule_does_not_cover_other_steps(self, write_source: WriteSource) -> None:
        body = "## Step 1\n\nSkip dot-folders.\n\n## Step 2\n\nGlob `<vault>/**/*.md`.\n"
        assert not any(skips_dot_folders(scan) for scan in scan_lines(write_source("a.md", body)))

    def test_find_needs_its_own_predicate(self, write_source: WriteSource) -> None:
        body = '## Step\n\nSkip dot-folders.\nRun `find <vault> -name "*.md" -mtime +90`.\n'
        assert not any(skips_dot_folders(scan) for scan in scan_lines(write_source("a.md", body)))

    def test_fenced_heading_stays_in_step(self, write_source: WriteSource) -> None:
        body = "## Step\n\nSkip dot-folders.\n\n```\n# Answer\nGlob `<vault>/**/*.md`.\n```\n"
        scans = scan_lines(write_source("agent.md", body))
        assert len(scans) == 1
        assert skips_dot_folders(scans[0])

    def test_shell_find_without_rule_fails(self, write_source: WriteSource) -> None:
        body = "find \"$VAULT\" -name '*.md' -not -path '*/.obsidian/*' -print0\n"
        scans = scan_lines(write_source("hook.sh", body))
        assert len(scans) == 1
        assert not skips_dot_folders(scans[0])

    def test_shell_continuation_is_one_command(self, write_source: WriteSource) -> None:
        body = "find \"$VAULT\" -mindepth 1 -name '.*' -prune \\\n  -o -name '*.md' -print0\n"
        scans = scan_lines(write_source("hook.sh", body))
        assert len(scans) == 1
        assert skips_dot_folders(scans[0])

    def test_shell_comment_is_ignored(self, write_source: WriteSource) -> None:
        body = "# excluding .obsidian/ used to be enough here\n"
        assert scan_lines(write_source("hook.sh", body)) == []
