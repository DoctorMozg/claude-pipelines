import re
import shlex
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = REPO_ROOT / "plugins/mz-knowledge"
SKILLS = PLUGIN / "skills"
PROPOSER = PLUGIN / "agents/atomization-proposer.md"
PROCESS_NOTES = SKILLS / "process-notes/SKILL.md"
ATOMIZE_PHASE = SKILLS / "process-notes/phases/atomize_and_draft.md"
SCAFFOLD_PHASE = SKILLS / "obsidian-init/phases/scaffold_vault.md"
VAULT_RESEARCH = SKILLS / "vault-research"
ANSWER_PHASE = SKILLS / "vault-answer/phases/search_and_synthesize.md"
ANSWERER = PLUGIN / "agents/vault-query-answerer.md"
EMPTY_SOURCES_RULE = re.compile(r"no read note bears on the question", re.I)

MAX_INPUT_WORDS = re.compile(r"\*\*MAX_INPUT_WORDS_PER_PASS\*\*: (\d+)")
PHASE_CAP = re.compile(r"`MAX_INPUT_WORDS_PER_PASS` \((\d+)\)")
PROPOSER_CAP = re.compile(r"\*\*(\d+)-word cap per input pass\.\*\*")
RESTATED_PROPOSER_CAP = re.compile(r"(\d+)-word (?:input )?cap")
WINDOW_CAP = re.compile(r"\*\*ATOMIZATION_WAVE_WORD_CAP\*\*: (\d+)")
CAP_LINES = re.compile(
    r"^- (?:\*\*\d+-word cap per input pass\.\*\*|`STATUS: DONE_WITH_CONCERNS`).*$", re.M
)
DECLARED_STATUS = re.compile(r"^- `STATUS: (?P<status>[A-Z_]+)`", re.M)
STATUS_HANDLER = re.compile(r"^\s*- `(?P<status>[A-Z_]+)` → (?P<action>.+)$", re.M)
ESCALATIONS = ("AskUserQuestion", "Status: blocked")

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
TOOL_SEPARATOR = re.compile(r",(?![^(]*\))")
BASH_GRANT = re.compile(r"^Bash\((?P<prefix>[^)]+?) \*\)$")
SHELL_FENCE_OPEN = re.compile(r"^\s*```(?:bash|sh|shell)\s*$")
FENCE_CLOSE = re.compile(r"^\s*```\s*$")
CONTROL_OPERATORS = frozenset({"|", "||", "&&", ";", "&"})

SCAFFOLD_ROW = re.compile(r"^\| `(?P<folder>[^`]+)/` +\|", re.M)
INBOX_CONSTANT = r"\*\*INBOX_FOLDER\*\*: `(?P<folder>[^`/]+)/?`"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _h2_section(path: Path, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", _read(path), re.M | re.S)
    assert match is not None, f"{path.name} has no '## {heading}' section"
    return match[1]


def _bash_grants(skill_md: Path) -> list[list[str]]:
    match = FRONTMATTER.match(_read(skill_md))
    assert match is not None, f"{skill_md} has no frontmatter"
    frontmatter = yaml.safe_load(match[1])
    allowed = frontmatter.get("allowed-tools", "")
    assert isinstance(allowed, str), f"{skill_md}: allowed-tools should be a string"
    entries = (entry.strip() for entry in TOOL_SEPARATOR.split(allowed))
    return [grant["prefix"].split() for entry in entries if (grant := BASH_GRANT.match(entry))]


def _shell_fence_lines(text: str) -> list[str]:
    lines: list[str] = []
    inside = False
    for line in text.splitlines():
        if inside and FENCE_CLOSE.match(line):
            inside = False
        elif inside:
            lines.append(line)
        elif SHELL_FENCE_OPEN.match(line):
            inside = True
    return lines


def _commands(line: str) -> list[list[str]]:
    # Claude Code checks each command of a compound line separately, so split on control operators.
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    commands: list[list[str]] = [[]]
    for token in lexer:
        if token in CONTROL_OPERATORS:
            commands.append([])
        else:
            commands[-1].append(token)
    return [command for command in commands if command]


@pytest.fixture(scope="module")
def max_input_words() -> int:
    match = MAX_INPUT_WORDS.search(_read(PROCESS_NOTES))
    assert match is not None, "process-notes should define MAX_INPUT_WORDS_PER_PASS"
    return int(match[1])


@pytest.fixture(scope="module")
def proposer_cap() -> int:
    match = PROPOSER_CAP.search(_read(PROPOSER))
    assert match is not None, "atomization-proposer should state its per-pass word cap"
    return int(match[1])


@pytest.fixture(scope="module")
def declared_statuses() -> frozenset[str]:
    statuses = frozenset(DECLARED_STATUS.findall(_h2_section(PROPOSER, "Output Format")))
    assert "DONE" in statuses, f"atomization-proposer should declare STATUS: DONE, got {statuses}"
    return statuses


@pytest.fixture(scope="module")
def status_handlers() -> dict[str, str]:
    section = _h2_section(ATOMIZE_PHASE, "After the agent returns")
    return {match["status"]: match["action"] for match in STATUS_HANDLER.finditer(section)}


@pytest.fixture(scope="module")
def scaffolded_folders() -> frozenset[str]:
    section = _h2_section(SCAFFOLD_PHASE, "Step 1: Create folder structure")
    folders = frozenset(SCAFFOLD_ROW.findall(section))
    assert folders, "obsidian-init's Step 1 table should list the folders it scaffolds"
    return folders


class TestAtomizationInputCap:
    def test_proposer_cap_matches_max_input_words_per_pass(self, max_input_words: int) -> None:
        cap_lines = CAP_LINES.findall(_read(PROPOSER))
        stated = {int(number) for line in cap_lines for number in re.findall(r"\d+", line)}

        assert len(cap_lines) == 2, f"expected the cap principle and overflow status: {cap_lines}"
        assert stated == {max_input_words}, (
            f"atomization-proposer caps input at {sorted(stated)} words, "
            f"but process-notes sends up to {max_input_words}"
        )

    def test_phase_restates_the_cap_constant(self, max_input_words: int) -> None:
        restated = {int(number) for number in PHASE_CAP.findall(_read(ATOMIZE_PHASE))}

        assert restated == {max_input_words}


class TestVaultResearchWindows:
    def test_restated_proposer_cap_matches_the_agent(self, proposer_cap: int) -> None:
        restated = {
            path.relative_to(VAULT_RESEARCH).as_posix(): int(number)
            for path in sorted(VAULT_RESEARCH.rglob("*.md"))
            for number in RESTATED_PROPOSER_CAP.findall(_read(path))
        }

        assert restated, "vault-research no longer states the proposer's cap"
        assert set(restated.values()) == {proposer_cap}, restated

    def test_window_fits_under_the_proposer_cap(self, proposer_cap: int) -> None:
        match = WINDOW_CAP.search(_read(VAULT_RESEARCH / "SKILL.md"))

        assert match is not None, "vault-research should define ATOMIZATION_WAVE_WORD_CAP"
        assert int(match[1]) < proposer_cap


class TestAtomizationStatusHandling:
    def test_every_declared_status_has_a_handler(
        self, declared_statuses: frozenset[str], status_handlers: dict[str, str]
    ) -> None:
        unhandled = sorted(declared_statuses - status_handlers.keys())

        assert not unhandled, f"atomize_and_draft.md never handles: {unhandled}"

    def test_non_done_statuses_escalate_or_block(
        self, declared_statuses: frozenset[str], status_handlers: dict[str, str]
    ) -> None:
        silent = sorted(
            status
            for status in declared_statuses - {"DONE"}
            if not any(word in status_handlers.get(status, "") for word in ESCALATIONS)
        )

        assert not silent, f"these statuses neither ask the user nor block: {silent}"


class TestShellGrants:
    def test_shell_fence_commands_have_bash_grants(self) -> None:
        checked = 0
        uncovered: list[str] = []
        for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
            grants = _bash_grants(skill_md)
            for path in sorted(skill_md.parent.rglob("*.md")):
                for line in _shell_fence_lines(_read(path)):
                    for command in _commands(line):
                        checked += 1
                        if not any(command[: len(grant)] == grant for grant in grants):
                            where = path.relative_to(REPO_ROOT).as_posix()
                            uncovered.append(f"{where}: {command[0]!r} in {line.strip()!r}")

        assert checked, "no commands found in mz-knowledge shell fences"
        assert not uncovered, "commands without a Bash(<cmd> *) grant:\n" + "\n".join(uncovered)


class TestVaultFolders:
    @pytest.mark.parametrize(
        ("consumer", "pattern"),
        [
            pytest.param(SKILLS / "vault-ingest/SKILL.md", INBOX_CONSTANT, id="vault-ingest"),
            pytest.param(SKILLS / "vault-triage/SKILL.md", INBOX_CONSTANT, id="vault-triage"),
            pytest.param(
                PROCESS_NOTES, r"<vault>/(?P<folder>[^/`]+)/YYYY-MM-DD\.md", id="process-notes"
            ),
            pytest.param(
                PLUGIN / "scripts/vault-context.sh",
                r"\$VAULT/(?P<folder>[^/\"]+)/\$today\.md",
                id="vault-context",
            ),
        ],
    )
    def test_obsidian_init_scaffolds_the_folders_consumers_read(
        self, scaffolded_folders: frozenset[str], consumer: Path, pattern: str
    ) -> None:
        name = consumer.relative_to(PLUGIN).as_posix()
        folders = {match["folder"] for match in re.finditer(pattern, _read(consumer))}

        assert folders, f"{name} no longer names its folder in the expected form"
        assert folders <= scaffolded_folders, (
            f"{name} reads {sorted(folders - scaffolded_folders)}, "
            f"which obsidian-init does not scaffold: {sorted(scaffolded_folders)}"
        )


class TestVaultAnswerNoAnswer:
    # A no-answer has nothing to cite; enforcing density made the answerer cite unrelated notes.
    def test_density_check_is_skipped_for_empty_sources(self) -> None:
        step = _h2_section(ANSWER_PHASE, "Step 3: Citation density check")
        skip = step.find("Skip this step when `## Sources` is empty")
        retry = step.find("Re-dispatch")

        assert skip != -1, "Step 3 should skip the density check when ## Sources is empty"
        assert skip < retry, "the empty-Sources skip must come before the density retry"

    @pytest.mark.parametrize(
        "source",
        [
            pytest.param(ANSWERER, id="agent"),
            pytest.param(ANSWER_PHASE, id="dispatch-prompt"),
        ],
    )
    def test_answerer_leaves_sources_empty_when_nothing_bears(self, source: Path) -> None:
        assert EMPTY_SOURCES_RULE.search(_read(source)), (
            f"{source.relative_to(PLUGIN).as_posix()} should tell the answerer to leave "
            "## Sources empty when no read note bears on the question"
        )
