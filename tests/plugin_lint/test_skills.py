import re
from pathlib import Path

from .conftest import REPO_ROOT, DocSet, PluginDoc, assert_no_violations, split_tool_list

KNOWN_KEYS = frozenset(
    {
        "name",
        "description",
        "when_to_use",
        "argument-hint",
        "arguments",
        "allowed-tools",
        "disallowed-tools",
        "model",
        "effort",
        "context",
        "agent",
        "hooks",
        "paths",
        "shell",
        "disable-model-invocation",
        "user-invocable",
        "license",
        "compatibility",
        "metadata",
        "version",
    }
)
# The sections a skill body is built from; a placeholder in one of these is noise in every load.
ANATOMY_SECTIONS = frozenset(
    {
        "Overview",
        "When to Use",
        "When NOT to Use",
        "Arguments",
        "Constants",
        "Core Process",
        "Techniques",
        "Common Rationalizations",
        "Red Flags",
        "Verification",
        "References",
        "Error Handling",
        "State Management",
    }
)
PLACEHOLDER = re.compile(r"^(?:-\s*)?(?:N/A|n/a|None|TBD)\.?$")
POINTER = re.compile(r"^(?:-\s*)?(?:\w+: )?(?:[Ss]ee|[Dd]elegated to|[Dd]efined in) .*$")
SECTION = re.compile(
    r"^## (?P<title>[^\n]+)\n(?P<content>.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL
)
PHASE_TABLE = re.compile(r"^\|\s*Phase\s*\|[^\n]*\n(?P<delimiter>\|[-: |]+\|\n)?", re.MULTILINE)
HEADING = re.compile(r"^#+ [^\n]*$", re.MULTILINE)
TABLE_OF_CONTENTS = re.compile(r"^(?:## Contents|\*\*Contents:?\*\*)", re.MULTILINE)
REFERENCE_TOC_MIN_LINES = 100
# SKILL.md loads in full on every invocation; phase files load once per phase.
SKILL_MAX_CHARS = 20_000
SKILL_MAX_LINES = 500
PHASE_MAX_LINES = 400
# Every installed skill's description shares one listing budget; past it, whole descriptions drop.
DESCRIPTION_MAX_CHARS = 250
# Interpreters and exec wrappers run whatever follows them: a bare-program grant is bare Bash.
BASH_EQUIVALENT_GRANT = re.compile(
    r"^Bash\((?:\*|(?:bash|sh|zsh|python3?|node|perl|env|eval|exec|xargs|sudo|npx|uv run)"
    r"(?: \*|:\*)?)\)$"
)
# `Bash(ls*)` also matches `lsof`; ` *` and `:*` are the word-boundary forms.
UNBOUNDED_TRAILING_STAR = re.compile(r"[^ :]\*\)$")
# Orchestrators running commands nobody can list in advance keep bare Bash (user, 2026-11-02).
OPEN_ENDED_BASH_SKILLS = {
    "debug": "reproduces failures with the project's test command, trigger scripts and git bisect",
    "polish": "runs the user's criterion checks and the project's formatters itself",
    "optimize": "runs the user's measure command and a profiler it picks",
    "verify": "runs the type checker, example scripts and README code blocks",
    "clean-leftovers": "runs the detected linter, often through npx or uv run",
}


def _skill_dir_files(doc: PluginDoc, folder: str) -> list[Path]:
    return sorted((doc.path.parent / folder).glob("*.md"))


def _skill_text(doc: PluginDoc) -> str:
    """SKILL.md plus its phase files: everything that runs in the skill's own turn."""
    parts = [doc.path.read_text(encoding="utf-8")]
    parts.extend(path.read_text(encoding="utf-8") for path in _skill_dir_files(doc, "phases"))
    return "\n".join(parts)


class TestFrontmatter:
    def test_frontmatter_is_strict_yaml_mapping(self, skills: DocSet) -> None:
        assert_no_violations(list(skills.parse_errors))

    def test_frontmatter_has_only_known_keys(self, skills: DocSet) -> None:
        violations = [
            f"{item.doc.relative}: unknown key {key!r}"
            for item in skills.parsed
            for key in item.frontmatter
            if key not in KNOWN_KEYS
        ]
        assert_no_violations(violations)

    def test_name_matches_directory(self, skills: DocSet) -> None:
        violations = [
            f"{item.doc.relative}: name {item.frontmatter.get('name')!r}"
            for item in skills.parsed
            if item.frontmatter.get("name") != item.doc.path.parent.name
        ]
        assert_no_violations(violations)

    def test_description_is_a_single_line_string(self, skills: DocSet) -> None:
        violations: list[str] = []
        for item in skills.parsed:
            description = item.frontmatter.get("description")
            if not isinstance(description, str) or not description.strip():
                violations.append(f"{item.doc.relative}: description is missing or not a string")
            elif "\n" in description:
                violations.append(f"{item.doc.relative}: description spans several lines")
        assert_no_violations(violations)

    def test_description_fits_listing_budget(self, skills: DocSet) -> None:
        violations: list[str] = []
        for item in skills.parsed:
            description = str(item.frontmatter.get("description") or "")
            when_to_use = str(item.frontmatter.get("when_to_use") or "")
            length = len(description) + len(when_to_use)
            if length > DESCRIPTION_MAX_CHARS:
                violations.append(
                    f"{item.doc.relative}: description plus when_to_use is {length} characters,"
                    f" over {DESCRIPTION_MAX_CHARS}"
                )
        assert_no_violations(violations)

    def test_argument_hint_is_a_string(self, skills: DocSet) -> None:
        # An unquoted hint such as `[base-branch]` parses as a YAML list, not as text.
        violations = [
            f"{item.doc.relative}: argument-hint is {item.frontmatter['argument-hint']!r}"
            for item in skills.parsed
            if not isinstance(item.frontmatter.get("argument-hint", ""), str)
        ]
        assert_no_violations(violations)

    def test_allowed_tools_list_ask_user_question_when_used(self, skills: DocSet) -> None:
        violations = [
            f"{item.doc.relative}: uses AskUserQuestion without listing it in allowed-tools"
            for item in skills.parsed
            if "AskUserQuestion" in _skill_text(item.doc)
            and "AskUserQuestion" not in split_tool_list(item.frontmatter.get("allowed-tools"))
        ]
        assert_no_violations(violations)

    def test_bash_grants_are_scoped(self, skills: DocSet) -> None:
        violations: list[str] = []
        for parsed in skills.parsed:
            skill = parsed.doc.path.parent.name
            for entry in split_tool_list(parsed.frontmatter.get("allowed-tools")):
                if entry == "Bash" and skill in OPEN_ENDED_BASH_SKILLS:
                    continue
                if entry == "Bash" or BASH_EQUIVALENT_GRANT.match(entry):
                    violations.append(f"{parsed.doc.relative}: {entry!r} grants any command")
                elif entry.startswith("Bash(") and UNBOUNDED_TRAILING_STAR.search(entry):
                    violations.append(f"{parsed.doc.relative}: {entry!r} needs a space before *")
        assert_no_violations(violations)

    def test_open_ended_bash_exemptions_are_current(self, skills: DocSet) -> None:
        bare_bash = {
            parsed.doc.path.parent.name
            for parsed in skills.parsed
            if "Bash" in split_tool_list(parsed.frontmatter.get("allowed-tools"))
        }
        stale = sorted(set(OPEN_ENDED_BASH_SKILLS) - bare_bash)
        assert not stale, f"exempt skills that no longer grant bare Bash: {stale}"


class TestStructure:
    def test_phase_table_sits_under_phase_overview_with_delimiter(self, skills: DocSet) -> None:
        violations: list[str] = []
        for doc in skills.docs:
            for table in PHASE_TABLE.finditer(doc.body):
                headings = HEADING.findall(doc.body[: table.start()])
                if not headings or headings[-1].strip() != "### Phase Overview":
                    violations.append(f"{doc.relative}: phase table sits outside Phase Overview")
                if table["delimiter"] is None:
                    violations.append(f"{doc.relative}: phase table has no delimiter row")
        assert_no_violations(violations)

    def test_anatomy_sections_hold_content(self, skills: DocSet) -> None:
        violations: list[str] = []
        for doc in skills.docs:
            for section in SECTION.finditer(doc.body):
                title = section["title"].strip()
                if title not in ANATOMY_SECTIONS:
                    continue
                lines = [line.strip() for line in section["content"].splitlines() if line.strip()]
                if not lines:
                    violations.append(f"{doc.relative}: ## {title} is empty")
                elif len(lines) == 1 and (PLACEHOLDER.match(lines[0]) or POINTER.match(lines[0])):
                    violations.append(f"{doc.relative}: ## {title} is only {lines[0]!r}")
        assert_no_violations(violations)

    def test_every_reference_file_is_listed_in_skill_md(self, skills: DocSet) -> None:
        violations = [
            f"{reference.relative_to(REPO_ROOT).as_posix()}: not listed in SKILL.md"
            for doc in skills.docs
            for reference in _skill_dir_files(doc, "references")
            if f"references/{reference.name}" not in doc.body
        ]
        assert_no_violations(violations)

    def test_long_reference_files_open_with_contents(self, skills: DocSet) -> None:
        violations: list[str] = []
        for doc in skills.docs:
            for reference in _skill_dir_files(doc, "references"):
                text = reference.read_text(encoding="utf-8")
                too_long = text.count("\n") > REFERENCE_TOC_MIN_LINES
                if too_long and not TABLE_OF_CONTENTS.search(text):
                    violations.append(f"{reference.relative_to(REPO_ROOT).as_posix()}: no TOC")
        assert_no_violations(violations)

    def test_skill_and_phase_files_fit_size_limits(self, skills: DocSet) -> None:
        violations: list[str] = []
        for doc in skills.docs:
            text = doc.path.read_text(encoding="utf-8")
            if len(text) >= SKILL_MAX_CHARS or text.count("\n") >= SKILL_MAX_LINES:
                violations.append(
                    f"{doc.relative}: {len(text)} chars, {text.count(chr(10))} lines "
                    f"(limit {SKILL_MAX_CHARS} chars, {SKILL_MAX_LINES} lines)"
                )
            for phase in _skill_dir_files(doc, "phases"):
                lines = phase.read_text(encoding="utf-8").count("\n")
                if lines >= PHASE_MAX_LINES:
                    relative = phase.relative_to(REPO_ROOT).as_posix()
                    violations.append(f"{relative}: {lines} lines (limit {PHASE_MAX_LINES})")
        assert_no_violations(violations)
