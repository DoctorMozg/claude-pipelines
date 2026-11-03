import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest
import yaml

PLUGIN = Path(__file__).resolve().parents[2] / "plugins/mz-knowledge"
SCRIPT = PLUGIN / "scripts/frontmatter-normalize.sh"
HOOKS = PLUGIN / "hooks/hooks.json"
SCAFFOLD = PLUGIN / "skills/obsidian-init/phases/scaffold_vault.md"
DSL_REFERENCE = PLUGIN / "skills/vault-schema/references/schema-dsl-syntax.md"
YAML_FENCE = re.compile(r"```yaml\n(.*?)```", re.S)
# A documented convention line, such as `  tag_case: keep      # keep | lower`.
CONVENTION_LINE = re.compile(r"^  (?P<key>\w+): \w+ +# (?P<choices>\w+(?: \| \w+)+)$", re.M)
BASH = shutil.which("bash") or "/bin/bash"
# Everything the script runs except jq, so a PATH built from these hides jq only.
TOOLS_WITHOUT_JQ = ("awk", "cp", "date", "dirname", "mktemp", "mv", "rm", "tail")
AWKS = ("mawk", "gawk", "busybox", "original-awk")
NOTE = "notes/note.md"
BODY = "# Note\n\nBody text.\n"
SCHEMA = """\
conventions:
  tag_case: keep      # keep | lower
  key_order: schema   # schema | keep

note_types:
  permanent:
    required: [status, created, tags]
    optional: [source]
    allowed_values:
      status: [draft, evergreen]
  fleeting:
    required:
      - created
      - tags
"""
KEEP_ORDER_SCHEMA = "note_types:\n  permanent:\n    required: [status, created, tags]\n"
LOWER_CASE_SCHEMA = "conventions:\n  tag_case: lower\n"
# Odd spacing, a nested map and a block scalar with a blank line, none of which the hook may touch.
VERBATIM_KEYS = 'title:   "Spaced"  \nmeta:\n  nested: x\nsummary: |\n  one\n\n  two\n'

type RunHook = Callable[..., subprocess.CompletedProcess[str]]
type PathWithoutJq = Callable[[Iterable[str]], str]
type WriteNote = Callable[..., Path]
type WriteSchema = Callable[[str], None]


@dataclass(frozen=True)
class Case:
    before: str
    after: str
    schema: str | None = None


def _today() -> str:
    return date.today().isoformat()


def _frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), text
    end = text.index("\n---\n", 3)
    return text[4 : end + 1]


def _yaml_block(path: Path, heading: str) -> str:
    text = path.read_text(encoding="utf-8")
    assert heading in text, f"{path.name} has no {heading!r} section"
    match = YAML_FENCE.search(text, text.index(heading))
    assert match is not None, f"{path.name} has no yaml block after {heading!r}"
    return match.group(1)


def _documented_conventions() -> dict[str, set[str]]:
    block = _yaml_block(DSL_REFERENCE, "## Conventions block")
    documented = {m["key"]: set(m["choices"].split(" | ")) for m in CONVENTION_LINE.finditer(block)}
    assert documented, f"{DSL_REFERENCE.name} documents no conventions"
    return documented


def _context(stdout: str) -> str:
    output = json.loads(stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    context: str = output["hookSpecificOutput"]["additionalContext"]
    return context


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / ".obsidian").mkdir(parents=True)
    return root


@pytest.fixture
def write_note(vault: Path) -> WriteNote:
    def write(frontmatter: str, rel: str = NOTE, body: str = BODY, root: Path = vault) -> Path:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
        return path

    return write


@pytest.fixture
def write_schema(vault: Path) -> WriteSchema:
    def write(text: str) -> None:
        path = vault / ".mz/vault-schema.yml"
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")

    return write


@pytest.fixture
def run_hook(tmp_path: Path) -> RunHook:
    stripped = {"OBSIDIAN_VAULT_PATH", "MZ_VAULT_PATH", "MZ_FRONTMATTER_NORMALIZE"}
    base_env = {key: value for key, value in os.environ.items() if key not in stripped}
    workdir = tmp_path / "cwd"
    workdir.mkdir()

    def run(
        file_path: Path | str,
        env: dict[str, str] | None = None,
        tool: str = "Write",
        stdin: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": tool,
            "tool_input": {"file_path": str(file_path)},
        }
        result = subprocess.run(
            [BASH, str(SCRIPT)],
            input=json.dumps(payload) if stdin is None else stdin,
            env={**base_env, **(env or {})},
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        return result

    return run


@pytest.fixture
def path_with_awk(tmp_path: Path) -> Callable[[str], str]:
    def build(awk: str) -> str:
        bin_dir = tmp_path / f"bin-{awk}"
        bin_dir.mkdir()
        for tool in ("jq", *TOOLS_WITHOUT_JQ):
            located = shutil.which(awk if tool == "awk" else tool)
            assert located is not None, f"{tool} is not installed"
            (bin_dir / tool).symlink_to(located)
        return str(bin_dir)

    return build


TRANSFORMS = {
    "hashed tag with a space": Case(
        'tag: "#AI Ethics"\ncreated: 2024-01-01\n', "tags:\n  - AI-Ethics\ncreated: 2024-01-01\n"
    ),
    "comma separated tags": Case(
        "tags: a, b\ncreated: 2024-01-01\n", "tags:\n  - a\n  - b\ncreated: 2024-01-01\n"
    ),
    "hashed words are separate tags": Case(
        'tags: "#a #b"\ncreated: 2024-01-01\n', "tags:\n  - a\n  - b\ncreated: 2024-01-01\n"
    ),
    "flow list cleaned and deduplicated": Case(
        'tags: ["#a", a, "b  c"]\ncreated: 2024-01-01\n',
        "tags:\n  - a\n  - b-c\ncreated: 2024-01-01\n",
    ),
    "nested tag keeps its slash": Case(
        'tag: "#project/alpha"\ncreated: 2024-01-01\n',
        "tags:\n  - project/alpha\ncreated: 2024-01-01\n",
    ),
    "tag merged into tags": Case(
        "tags: [a]\ntitle: T\ntag: b\ncreated: 2024-01-01\n",
        "tags:\n  - a\n  - b\ntitle: T\ncreated: 2024-01-01\n",
    ),
    "tag before tags merges at the tags position": Case(
        "tag: b\ntags:\n  - a\ncreated: 2024-01-01\n", "tags:\n  - a\n  - b\ncreated: 2024-01-01\n"
    ),
    "aliases are never split": Case(
        "alias: Smith, John\ncreated: 2024-01-01\n",
        "aliases:\n  - Smith, John\ncreated: 2024-01-01\n",
    ),
    "alias with a colon is quoted": Case(
        'alias: "Re: meeting"\ncreated: 2024-01-01\n',
        'aliases:\n  - "Re: meeting"\ncreated: 2024-01-01\n',
    ),
    "alias with a double quote gets single quotes": Case(
        "alias: '\"Quoted\" Name'\ncreated: 2024-01-01\n",
        "aliases:\n  - '\"Quoted\" Name'\ncreated: 2024-01-01\n",
    ),
    "cssclass splits on spaces": Case(
        "cssclass: wide dark\ncreated: 2024-01-01\n",
        "cssclasses:\n  - wide\n  - dark\ncreated: 2024-01-01\n",
    ),
    "numbers and booleans are quoted": Case(
        "tag: 2024, yes, ok\ncreated: 2024-01-01\n",
        'tags:\n  - "2024"\n  - "yes"\n  - ok\ncreated: 2024-01-01\n',
    ),
    "empty singular becomes an empty list": Case(
        'tag: ""\ncreated: 2024-01-01\n', "tags: []\ncreated: 2024-01-01\n"
    ),
    "lower tag case from conventions": Case(
        "tags: [AI, Ml]\ncreated: 2024-01-01\n",
        "tags:\n  - ai\n  - ml\ncreated: 2024-01-01\n",
        LOWER_CASE_SCHEMA,
    ),
    "slashed created date": Case("created: 2024/01/02\n", "created: 2024-01-02\n"),
    "dotted quoted created date": Case('created: "2024.01.02"\n', "created: 2024-01-02\n"),
    "missing created is filled with today": Case("title: T\n", "title: T\ncreated: {today}\n"),
    "empty frontmatter gets created": Case("", "created: {today}\n"),
    "required keys are stubbed at the end": Case(
        "type: permanent\ncreated: 2024-01-01\n",
        "type: permanent\ncreated: 2024-01-01\nstatus:\ntags: []\n",
        KEEP_ORDER_SCHEMA,
    ),
    "schema key order puts required then optional first": Case(
        "title: T\ntype: permanent\ntags: [a]\nsource: web\ncreated: 2024-01-01\n",
        "status:\ncreated: 2024-01-01\ntags: [a]\nsource: web\ntitle: T\ntype: permanent\n",
        SCHEMA,
    ),
    "block list of required keys": Case(
        "type: fleeting\n", "created: {today}\ntags: []\ntype: fleeting\n", SCHEMA
    ),
    "blank line stays and blocks reordering": Case(
        "type: permanent\n\ntag: a\nstatus: draft\ncreated: 2024-01-01\n",
        "type: permanent\n\ntags:\n  - a\nstatus: draft\ncreated: 2024-01-01\n",
        SCHEMA,
    ),
    "untouched keys are copied byte for byte": Case(
        f"{VERBATIM_KEYS}tag: a\ncreated: 2024-01-01\n",
        f"{VERBATIM_KEYS}tags:\n  - a\ncreated: 2024-01-01\n",
    ),
}

ALREADY_CLEAN = {
    "block list": ("tags:\n  - a\ncreated: 2024-01-01\n", None),
    "flow list stays flow": ("tags: [a, b]\ncreated: 2024-01-01\n", None),
    "flow aliases are already a list": ("aliases: [Smith, John]\ncreated: 2024-01-01\n", None),
    "empty list": ("tags: []\ncreated: 2024-01-01\n", None),
    "empty value": ("tags:\ncreated: 2024-01-01\n", None),
    "datetime created": ("created: 2024-01-02T10:00\n", None),
    "type missing from the schema": ("type: journal\ncreated: 2024-01-01\n", SCHEMA),
    "schema order already": (
        "status: draft\ncreated: 2024-01-01\ntags: [a]\ntype: permanent\n",
        SCHEMA,
    ),
}

UNTOUCHED = {
    "no frontmatter block": "# Title\ntag: a\n",
    "frontmatter never closes": "---\ntag: a\n",
    "closing past 200 lines": "---\n" + "".join(f"k{i}: v\n" for i in range(200)) + "tag: a\n---\n",
    "CRLF endings": "---\r\ntag: a\r\n---\r\n",
    "CRLF after the first line": "---\ntag: a\r\n---\n",
    "tab": "---\ntag:\ta\n---\n",
    "comment line": "---\n# note\ntag: a\n---\n",
    "inline comment": "---\ntag: a # c\n---\n",
    "unquoted hash is a comment": "---\ntag: #ai\n---\n",
    "duplicate key": "---\ntag: a\ntag: b\n---\n",
    "block scalar tags": "---\ntags: |\n  a\n---\n",
    "anchor": "---\ntags: &t [a]\n---\n",
    "alias": "---\ntags: *t\n---\n",
    "nested map in tags": "---\ntags:\n  a: b\n---\n",
    "flow map": "---\ntags: {a: 1}\n---\n",
    "nested flow list": "---\ntags: [a, [b]]\n---\n",
    "flow list over two lines": "---\ntags: [a,\n  b]\n---\n",
    "uneven list indentation": "---\ntags:\n  - a\n    - b\n---\n",
    "escape inside double quotes": '---\ntag: "a\\tb"\n---\n',
    "core template placeholder": "---\ncreated: {{date}}\ntag: a\n---\n",
    "templater placeholder": "---\ncreated: <% tp.date.now() %>\n---\n",
    "stray line": "---\njust text\n---\n",
    "list item outside any key": "---\n- a\n---\n",
}


class TestTransforms:
    @pytest.mark.parametrize("case", TRANSFORMS.values(), ids=TRANSFORMS.keys())
    def test_rewrites_the_frontmatter(
        self, run_hook: RunHook, write_note: WriteNote, write_schema: WriteSchema, case: Case
    ) -> None:
        if case.schema is not None:
            write_schema(case.schema)
        note = write_note(case.before)
        result = run_hook(note)
        assert _frontmatter(note) == case.after.format(today=_today())
        assert note.read_text(encoding="utf-8").endswith(f"---\n{BODY}")
        assert NOTE in _context(result.stdout)

    @pytest.mark.parametrize("case", TRANSFORMS.values(), ids=TRANSFORMS.keys())
    def test_second_run_changes_nothing(
        self, run_hook: RunHook, write_note: WriteNote, write_schema: WriteSchema, case: Case
    ) -> None:
        if case.schema is not None:
            write_schema(case.schema)
        note = write_note(case.before)
        run_hook(note)
        normalized = note.read_text(encoding="utf-8")
        assert run_hook(note).stdout == ""
        assert note.read_text(encoding="utf-8") == normalized


class TestAlreadyClean:
    @pytest.mark.parametrize(
        ("frontmatter", "schema"), ALREADY_CLEAN.values(), ids=ALREADY_CLEAN.keys()
    )
    def test_leaves_the_file_alone(
        self,
        run_hook: RunHook,
        write_note: WriteNote,
        write_schema: WriteSchema,
        frontmatter: str,
        schema: str | None,
    ) -> None:
        if schema is not None:
            write_schema(schema)
        note = write_note(frontmatter)
        before = note.stat()
        assert run_hook(note).stdout == ""
        assert _frontmatter(note) == frontmatter
        assert (note.stat().st_ino, note.stat().st_mtime_ns) == (before.st_ino, before.st_mtime_ns)


class TestUntouched:
    @pytest.mark.parametrize("text", UNTOUCHED.values(), ids=UNTOUCHED.keys())
    def test_unsupported_yaml_is_left_byte_for_byte(
        self, run_hook: RunHook, vault: Path, text: str
    ) -> None:
        note = vault / NOTE
        note.parent.mkdir(parents=True)
        note.write_bytes(text.encode())
        result = run_hook(note)
        assert result.stdout == ""
        assert note.read_bytes() == text.encode()
        assert f"left {NOTE} untouched" in result.stderr


class TestStops:
    @pytest.mark.parametrize(
        "rel", [".trash/note.md", "notes/.hidden.md", "notes/.drafts/note.md", "notes/n.txt"]
    )
    def test_skipped_paths(self, run_hook: RunHook, write_note: WriteNote, rel: str) -> None:
        note = write_note("tag: a\n", rel=rel)
        assert run_hook(note).stdout == ""
        assert _frontmatter(note) == "tag: a\n"

    def test_opt_out(self, run_hook: RunHook, write_note: WriteNote) -> None:
        note = write_note("tag: a\n")
        assert run_hook(note, env={"MZ_FRONTMATTER_NORMALIZE": "0"}).stdout == ""
        assert _frontmatter(note) == "tag: a\n"

    def test_missing_jq(
        self, run_hook: RunHook, write_note: WriteNote, path_without_jq: PathWithoutJq
    ) -> None:
        note = write_note("tag: a\n")
        assert run_hook(note, env={"PATH": path_without_jq(TOOLS_WITHOUT_JQ)}).stdout == ""
        assert _frontmatter(note) == "tag: a\n"

    @pytest.mark.parametrize(
        "path", ["notes/note.md", "{vault}/notes/../notes/note.md", "{vault}/notes/gone.md"]
    )
    def test_relative_traversing_or_missing_path(
        self, run_hook: RunHook, write_note: WriteNote, vault: Path, path: str
    ) -> None:
        note = write_note("tag: a\n")
        assert run_hook(path.format(vault=vault)).stdout == ""
        assert _frontmatter(note) == "tag: a\n"

    def test_symlinked_note(self, run_hook: RunHook, write_note: WriteNote, vault: Path) -> None:
        target = write_note("tag: a\n")
        link = vault / "notes/link.md"
        link.symlink_to(target)
        assert run_hook(link).stdout == ""
        assert link.is_symlink()
        assert _frontmatter(target) == "tag: a\n"

    @pytest.mark.skipif(os.geteuid() == 0, reason="root can write a read-only file")
    def test_unwritable_note(self, run_hook: RunHook, write_note: WriteNote) -> None:
        note = write_note("tag: a\n")
        note.chmod(0o444)
        assert run_hook(note).stdout == ""
        assert _frontmatter(note) == "tag: a\n"

    @pytest.mark.parametrize("env_vault", [None, "{tmp}/vault"])
    def test_outside_any_vault(
        self, run_hook: RunHook, write_note: WriteNote, tmp_path: Path, env_vault: str | None
    ) -> None:
        note = write_note("tag: a\n", root=tmp_path / "elsewhere")
        env = {} if env_vault is None else {"OBSIDIAN_VAULT_PATH": env_vault.format(tmp=tmp_path)}
        assert run_hook(note, env=env).stdout == ""
        assert _frontmatter(note) == "tag: a\n"

    @pytest.mark.parametrize(
        ("config", "content"),
        [
            ("templates.json", '{"folder": "99 - Meta/Templates"}'),
            (
                "plugins/templater-obsidian/data.json",
                '{"templates_folder": "/99 - Meta/Templates/"}',
            ),
        ],
    )
    def test_templates_folder(
        self, run_hook: RunHook, write_note: WriteNote, vault: Path, config: str, content: str
    ) -> None:
        settings = vault / ".obsidian" / config
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(content, encoding="utf-8")
        template = write_note("tags: []\n", rel="99 - Meta/Templates/Permanent.md")
        result = run_hook(template)
        assert result.stdout == ""
        assert _frontmatter(template) == "tags: []\n"
        assert "skipped template" in result.stderr

    @pytest.mark.parametrize(
        "stdin", ["", "not json", '{"tool_input": {}}', '{"tool_input": {"file_path": 7}}']
    )
    def test_malformed_input(self, run_hook: RunHook, stdin: str) -> None:
        assert run_hook("", stdin=stdin).stdout == ""


class TestVaultDetection:
    def test_deep_note_reports_a_vault_relative_path(
        self, run_hook: RunHook, write_note: WriteNote
    ) -> None:
        note = write_note("tag: a\n", rel="a/b/c/deep.md")
        assert "in a/b/c/deep.md." in _context(run_hook(note).stdout)

    @pytest.mark.parametrize("variable", ["OBSIDIAN_VAULT_PATH", "MZ_VAULT_PATH"])
    @pytest.mark.parametrize("suffix", ["", "/"])
    def test_env_vault_without_obsidian_folder(
        self, run_hook: RunHook, write_note: WriteNote, tmp_path: Path, variable: str, suffix: str
    ) -> None:
        root = tmp_path / "plain"
        note = write_note("tag: a\n", root=root)
        context = _context(run_hook(note, env={variable: f"{root}{suffix}"}).stdout)
        assert f"in {NOTE}." in context

    def test_vault_inside_a_dot_folder(
        self, run_hook: RunHook, write_note: WriteNote, tmp_path: Path
    ) -> None:
        # The dot-folder rule applies below the vault root only, so ~/.vaults/main still counts.
        root = tmp_path / ".vaults/main"
        (root / ".obsidian").mkdir(parents=True)
        note = write_note("tag: a\n", root=root)
        run_hook(note)
        assert _frontmatter(note) == f"tags:\n  - a\ncreated: {_today()}\n"

    def test_edit_tool_input(self, run_hook: RunHook, write_note: WriteNote) -> None:
        note = write_note("tag: a\n")
        assert _context(run_hook(note, tool="Edit").stdout)
        assert _frontmatter(note).startswith("tags:\n")


class TestOutput:
    def test_context_names_the_changes_and_the_note(
        self, run_hook: RunHook, write_note: WriteNote
    ) -> None:
        note = write_note("tag: a\n")
        output = json.loads(run_hook(note).stdout)
        assert output == {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    "frontmatter-normalize: tag -> tags list, added created"
                    f" in {NOTE}. Re-read it before editing."
                ),
            }
        }

    def test_mode_and_body_survive_without_temp_files(
        self, run_hook: RunHook, write_note: WriteNote
    ) -> None:
        note = write_note("tag: a\n", body="no trailing newline")
        note.chmod(0o640)
        run_hook(note)
        assert note.read_text(encoding="utf-8").endswith("---\nno trailing newline")
        assert note.stat().st_mode & 0o777 == 0o640
        assert [path.name for path in note.parent.iterdir()] == [note.name]

    @pytest.mark.parametrize("awk", AWKS)
    def test_same_result_under_each_installed_awk(
        self,
        run_hook: RunHook,
        write_note: WriteNote,
        write_schema: WriteSchema,
        path_with_awk: Callable[[str], str],
        awk: str,
    ) -> None:
        if shutil.which(awk) is None:
            pytest.skip(f"{awk} is not installed")
        case = TRANSFORMS["schema key order puts required then optional first"]
        write_schema(SCHEMA)
        note = write_note(case.before.replace("tags: [a]", 'tag: "#AI Ethics"'))
        run_hook(note, env={"PATH": path_with_awk(awk)})
        assert _frontmatter(note) == case.after.replace("tags: [a]", "tags:\n  - AI-Ethics")


class TestRegistration:
    def test_one_md_filtered_handler_per_tool(self) -> None:
        groups = json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"]["PostToolUse"]
        handlers = [
            (group["matcher"], hook["if"], hook["command"])
            for group in groups
            for hook in group["hooks"]
        ]
        command = '"${CLAUDE_PLUGIN_ROOT}"/scripts/frontmatter-normalize.sh'
        # A bare **/*.md anchors at the working directory, so it misses a vault elsewhere.
        assert handlers == [
            ("Write", "Write(//**/*.md)", command),
            ("Edit", "Edit(//**/*.md)", command),
        ]

    def test_scripts_are_executable(self) -> None:
        assert os.access(SCRIPT, os.X_OK)


class TestSchemaConventions:
    PROBE = "title: T\ntags: [AI]\ntype: permanent\ncreated: 2024-01-01\n"
    TYPES = "note_types:\n  permanent:\n    required: [created, type, tags]\n"

    def test_obsidian_init_writes_a_documented_value_for_every_convention(self) -> None:
        schema = yaml.safe_load(_yaml_block(SCAFFOLD, "## Step 3"))
        documented = _documented_conventions()
        assert set(schema["conventions"]) == set(documented)
        for key, value in schema["conventions"].items():
            assert value in documented[key], f"{key}: {value} is not one of {documented[key]}"

    def test_every_documented_choice_changes_what_the_hook_writes(
        self, run_hook: RunHook, write_note: WriteNote, write_schema: WriteSchema
    ) -> None:
        write_schema(self.TYPES)
        kept = write_note(self.PROBE, rel="kept.md")
        run_hook(kept)
        for key, choices in _documented_conventions().items():
            # keep is what an absent key means, so every other choice must change the output.
            for choice in sorted(choices - {"keep"}):
                write_schema(f"conventions:\n  {key}: {choice}\n{self.TYPES}")
                note = write_note(self.PROBE, rel=f"{key}-{choice}.md")
                run_hook(note)
                assert _frontmatter(note) != _frontmatter(kept), f"{key}: {choice} had no effect"

    def test_obsidian_init_schema_orders_a_new_note(
        self, run_hook: RunHook, write_note: WriteNote, write_schema: WriteSchema
    ) -> None:
        write_schema(_yaml_block(SCAFFOLD, "## Step 3"))
        note = write_note("title: T\ntags: x\ntype: permanent\ncreated: 2024-01-01\n")
        run_hook(note)
        assert (
            _frontmatter(note) == "created: 2024-01-01\ntype: permanent\ntags:\n  - x\ntitle: T\n"
        )
