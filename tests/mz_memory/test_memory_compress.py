import json
import os
import shlex
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins" / "mz-memory" / "scripts"
COMPRESS_SCRIPT = SCRIPTS / "memory-compress.sh"
BASH = shutil.which("bash") or "/bin/bash"
# PATH holds only these and the claude stub, so the real CLI never runs.
TOOLS = (
    "bash",
    "dirname",
    "mkdir",
    "rmdir",
    "mktemp",
    "mv",
    "cp",
    "rm",
    "cat",
    "awk",
    "grep",
    "head",
    "tail",
    "wc",
    "find",
    "date",
    "jq",
)
# The scripts degrade without these, so a host that lacks them still runs the suite.
OPTIONAL_TOOLS = ("flock", "timeout")
CALLER_VARS = {
    "CLAUDE_PROJECT_DIR",
    "MZ_MEMORY_COMPRESS",
    "MZ_MEMORY_CURATOR",
    "MZ_MEMORY_CURATOR_MODEL",
}

PIN_START = "<!-- mz-pinned-start -->"
PIN_END = "<!-- mz-pinned-end -->"
DIGEST_START = "<!-- mz-digest-start -->"
DIGEST_END = "<!-- mz-digest-end -->"
LOG_START = "<!-- mz-log-start -->"
LOG_END = "<!-- mz-log-end -->"
OLD_SUMMARY_MARK = "<!-- mz-compressed -->"
PINNED = "- [2026-10-01] Use UTC timestamps everywhere."
KEEP_RECENT = 100
COMPRESS_THRESHOLD = 300
DIGEST_MAX_ITEMS = 40
DIGEST_ITEM_CHARS = 300

STUB = """#!{bash}
rec={record}
cat >"$rec/prompt"
printf '%s\\n' "$@" >"$rec/args"
printf '%s\\n' "MZ_MEMORY_CURATOR=${{MZ_MEMORY_CURATOR-unset}}" \\
  "MZ_MEMORY_COMPRESS=${{MZ_MEMORY_COMPRESS-unset}}" >"$rec/env"
if [ -f "$rec/during.sh" ]; then . "$rec/during.sh"; fi
cat "$rec/response"
exit "$(cat "$rec/exit_code")"
"""

type RunCompress = Callable[..., None]
type SeedMemory = Callable[..., Path]


@dataclass(frozen=True)
class FakeCurator:
    """The stub claude on PATH: replies with a canned result and records how it was called."""

    record: Path

    def respond(self, *operations: dict[str, object]) -> None:
        envelope = {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "structured_output": {"operations": list(operations)},
        }
        self.respond_raw(json.dumps(envelope))

    def respond_raw(self, text: str, exit_code: int = 0) -> None:
        (self.record / "response").write_text(text, encoding="utf-8")
        (self.record / "exit_code").write_text(str(exit_code), encoding="utf-8")

    def during_call(self, script: str) -> None:
        (self.record / "during.sh").write_text(script, encoding="utf-8")

    @property
    def called(self) -> bool:
        return (self.record / "prompt").exists()

    def prompt(self) -> str:
        return (self.record / "prompt").read_text(encoding="utf-8")

    def arg(self, flag: str) -> str:
        args = (self.record / "args").read_text(encoding="utf-8").split("\n")[:-1]
        return args[args.index(flag) + 1]

    def env(self) -> dict[str, str]:
        lines = (self.record / "env").read_text(encoding="utf-8").splitlines()
        return {key: value for key, _, value in (line.partition("=") for line in lines)}


def entries(count: int, extra_lines: int = 0, padding: str = "") -> list[str]:
    """Log lines for `count` entries, newest first, each trailed by `extra_lines` indented lines."""
    lines: list[str] = []
    for index in range(count):
        lines.append(
            f"- [2026-10-01] 2026_10_01_build_item_{index:04d} (phase=done) [main@abc1234]{padding}"
        )
        lines.extend(f"  - decision {index}.{line}" for line in range(extra_lines))
    return lines


def digest_item(number: int, n: int = 1, last: str = "2026-10-01", text: str = "") -> str:
    body = text or f"Decision {number} still holds for the auth module"
    return f"- [D-{number:04d}] n={n} last={last} trig=log src=task{number} tags=auth :: {body}"


def op(kind: str, **fields: object) -> dict[str, object]:
    return {"op": kind, "inbox": [], "lessons": [], "text": "", "tags": [], "reason": "", **fields}


def _today() -> str:
    return date.today().isoformat()


def _memory_dir(project: Path) -> Path:
    return project / ".mz" / "memory"


def _memory_file(project: Path) -> Path:
    return _memory_dir(project) / "MEMORY.md"


def _region(project: Path, start: str, end: str) -> list[str]:
    lines = _memory_file(project).read_text(encoding="utf-8").splitlines()
    if start not in lines:
        return []
    return lines[lines.index(start) + 1 : lines.index(end)]


def _log(project: Path) -> list[str]:
    return _region(project, LOG_START, LOG_END)


def _digest(project: Path) -> list[str]:
    return _region(project, DIGEST_START, DIGEST_END)


def _archive(project: Path) -> str:
    archive = _memory_dir(project) / "activity.archive.md"
    return archive.read_text(encoding="utf-8") if archive.exists() else ""


def _ops(project: Path) -> list[dict[str, object]]:
    log = _memory_dir(project) / "activity.ops.jsonl"
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def _insert_after_log_start(project: Path, line: str) -> str:
    """A shell snippet that adds `line` to the top of the log, as a SessionEnd capture would."""
    path = shlex.quote(str(_memory_file(project)))
    program = shlex.quote("{ print } $0 == start { print line }")
    return (
        f"awk -v start={shlex.quote(LOG_START)} -v line={shlex.quote(line)} {program} {path} "
        f">{path}.tmp && mv {path}.tmp {path}\n"
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    _memory_dir(tmp_path).mkdir(parents=True)
    return tmp_path


@pytest.fixture
def seed(project: Path) -> SeedMemory:
    def write(
        log: Sequence[str], digest: Sequence[str] | None = None, *, log_heading: bool = True
    ) -> Path:
        lines = [
            "# Project Memory",
            "",
            "<!-- Auto-managed by mz-memory. Most recent first. -->",
            "<!-- mz-memory:v2 -->",
            "",
            "## Pinned",
            "",
            PIN_START,
            PINNED,
            PIN_END,
            "",
        ]
        if digest is not None:
            lines += ["## Digest", "", DIGEST_START, *digest, DIGEST_END, ""]
        if log_heading:
            lines += ["## Activity Log", ""]
        lines += [LOG_START, *log, LOG_END]
        memory_file = _memory_file(project)
        memory_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return memory_file

    return write


@pytest.fixture
def bin_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    for tool in TOOLS:
        located = shutil.which(tool)
        assert located is not None, f"{tool} is not installed"
        (directory / tool).symlink_to(located)
    for tool in OPTIONAL_TOOLS:
        located = shutil.which(tool)
        if located is not None:
            (directory / tool).symlink_to(located)
    return directory


@pytest.fixture
def curator(tmp_path: Path, bin_dir: Path) -> FakeCurator:
    record = tmp_path / "claude_record"
    record.mkdir()
    stub = bin_dir / "claude"
    stub.write_text(STUB.format(bash=BASH, record=shlex.quote(str(record))), encoding="utf-8")
    stub.chmod(0o755)
    fake = FakeCurator(record)
    fake.respond()
    return fake


@pytest.fixture
def run_compress(project: Path, bin_dir: Path) -> RunCompress:
    env = {key: value for key, value in os.environ.items() if key not in CALLER_VARS}
    env.update({"PATH": str(bin_dir), "MZ_MEMORY_ROOT": str(project)})

    def run(extra: Mapping[str, str] | None = None) -> None:
        result = subprocess.run(
            [BASH, str(COMPRESS_SCRIPT)],
            env={**env, **(extra or {})},
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        # A jq or awk error would otherwise pass as an ordinary failed run.
        assert result.stderr == ""

    return run


class TestCompression:
    def test_old_entries_leave_the_log_for_the_digest_and_the_archive(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        # About 200 KB of log: past the pipe buffer and past the 128 KiB cap on one argument.
        lines = entries(1_000, padding=" " + "x" * 150)
        seed(lines)
        curator.respond(
            op("ADD", inbox=["E-0001", "E-0002"], text="Items 100 and 101 shipped", tags=["auth"])
        )

        run_compress()

        expected = (
            f"- [D-0001] n=2 last={_today()} trig=log src=2026_10_01_build_item_0100 tags=auth"
            " :: Items 100 and 101 shipped"
        )
        assert _log(project) == lines[:KEEP_RECENT]
        assert _digest(project) == [expected]
        assert f"## {_today()} compressed entries\n\n" + "\n".join(lines[KEEP_RECENT:]) in _archive(
            project
        )

    def test_recent_block_keeps_whole_entries(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        # Three-line entries put an entry across line 100; the cut moves to that entry's end.
        lines = entries(120, extra_lines=2)
        seed(lines)

        run_compress()

        assert _log(project) == lines[:102]

    def test_multi_line_entries_count_toward_the_line_threshold(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        seed(entries(110, extra_lines=2))

        run_compress()

        assert curator.called
        assert len(_log(project)) <= COMPRESS_THRESHOLD

    def test_entries_prepended_during_the_call_survive(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        lines = entries(COMPRESS_THRESHOLD + 50)
        seed(lines)
        late = "- [2026-11-02] 2026_11_02_build_late (phase=done) [main@def5678]"
        curator.during_call(_insert_after_log_start(project, late))

        run_compress()

        assert _log(project) == [late, *lines[:KEEP_RECENT]]

    def test_a_recent_entry_identical_to_the_first_old_one_stays(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        lines = entries(COMPRESS_THRESHOLD + 50)
        lines[KEEP_RECENT] = lines[5]
        seed(lines)

        run_compress()

        assert _log(project) == lines[:KEEP_RECENT]

    def test_backslashes_survive_in_the_log_and_the_archive(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        lines = entries(COMPRESS_THRESHOLD + 50, padding=r" C:\builds\new\table")
        seed(lines)

        run_compress()

        assert _log(project) == lines[:KEEP_RECENT]
        assert lines[-1] in _archive(project)

    def test_digest_section_goes_between_pinned_and_the_log(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        seed(entries(COMPRESS_THRESHOLD + 50))
        curator.respond(op("ADD", inbox=["E-0001"], text="Item 100 shipped"))

        run_compress()

        text = _memory_file(project).read_text(encoding="utf-8")
        assert (
            text.index(PIN_END)
            < text.index("## Digest")
            < text.index(DIGEST_START)
            < text.index("## Activity Log")
        )

    def test_file_without_a_log_heading_gets_the_digest_above_the_log_marker(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        seed(entries(COMPRESS_THRESHOLD + 50), log_heading=False)
        curator.respond(op("ADD", inbox=["E-0001"], text="Item 100 shipped"))

        run_compress()

        text = _memory_file(project).read_text(encoding="utf-8")
        assert len(_digest(project)) == 1
        assert text.index(DIGEST_END) < text.index(LOG_START)


class TestDigest:
    def test_existing_items_are_edited_by_id_not_rewritten(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        first, second = digest_item(1, n=2), digest_item(2, n=1)
        seed(entries(COMPRESS_THRESHOLD + 50), [first, second])
        curator.respond(op("MERGE", inbox=["E-0001"], lessons=["D-0001"]))

        run_compress()

        assert _digest(project) == [
            first.replace("n=2 last=2026-10-01", f"n=3 last={_today()}"),
            second,
        ]

    def test_the_strongest_items_stay_when_the_digest_is_full(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        full = [
            digest_item(number, n=2, last=(date(2026, 1, 1) + timedelta(days=number)).isoformat())
            for number in range(DIGEST_MAX_ITEMS, 0, -1)
        ]
        seed(entries(COMPRESS_THRESHOLD + 50), full)
        curator.respond(
            op("ADD", inbox=["E-0001", "E-0002", "E-0003"], text="Items 100 to 102 shipped")
        )

        run_compress()

        digest = _digest(project)
        assert len(digest) == DIGEST_MAX_ITEMS
        assert digest[0].startswith(f"- [D-{DIGEST_MAX_ITEMS + 1:04d}] n=3")
        assert digest[1:] == full[:-1]
        assert f"{_today()} evicted: {full[-1]}" in _archive(project)

    def test_new_ids_continue_past_archived_items(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        seed(entries(COMPRESS_THRESHOLD + 50))
        (_memory_dir(project) / "activity.archive.md").write_text(
            f"2026-10-01 evicted: {digest_item(7)}\n", encoding="utf-8"
        )
        curator.respond(op("ADD", inbox=["E-0001"], text="Item 100 shipped"))

        run_compress()

        assert _digest(project)[0].startswith("- [D-0008] ")

    def test_model_text_is_cut_to_the_item_limit(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        seed(entries(COMPRESS_THRESHOLD + 50))
        curator.respond(op("ADD", inbox=["E-0001"], text="Item 100 shipped " + "with detail " * 60))

        run_compress()

        text = _digest(project)[0].split(" :: ", 1)[1]
        assert text.endswith("...")
        assert len(text) <= DIGEST_ITEM_CHARS + len("...")


class TestMigration:
    OLD_SUMMARY = (
        "",
        OLD_SUMMARY_MARK,
        "## Recurring decisions",
        "- Passwords use argon2id",
        "- Access tokens live 15 minutes",
        "  and rotate on use",
        "## Resolved bugs",
        "* Flaky upload fixed by retrying on 5xx",
    )

    def test_old_summary_becomes_tagged_digest_items_without_a_model_call(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        lines = entries(50)
        seed([*lines, *self.OLD_SUMMARY])

        run_compress()

        assert not curator.called
        assert _log(project) == lines
        assert [(item.split()[1], item.split(" :: ")[1]) for item in _digest(project)] == [
            ("[D-0001]", "Passwords use argon2id"),
            ("[D-0002]", "Access tokens live 15 minutes and rotate on use"),
            ("[D-0003]", "Flaky upload fixed by retrying on 5xx"),
        ]
        assert [item.split("tags=")[1].split()[0] for item in _digest(project)] == [
            "recurring-decisions",
            "recurring-decisions",
            "resolved-bugs",
        ]
        assert f"## {_today()} migrated summary\n\n" + "\n".join(self.OLD_SUMMARY[2:]) in _archive(
            project
        )

    def test_migration_holds_when_the_model_call_fails(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        lines = entries(COMPRESS_THRESHOLD + 50)
        seed([*lines, *self.OLD_SUMMARY])
        curator.respond_raw("")

        run_compress()

        assert _log(project) == lines
        assert len(_digest(project)) == 3

    def test_migration_runs_once(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        seed([*entries(50), *self.OLD_SUMMARY])

        run_compress()
        run_compress()

        assert len(_digest(project)) == 3
        assert _archive(project).count("migrated summary") == 1


FAILED_REPLIES = {
    "empty": ("", 0),
    "not-json": ("Sorry, I cannot help with that.", 0),
    "error-result": (
        json.dumps({"type": "result", "subtype": "error_max_budget_usd", "is_error": True}),
        0,
    ),
    "non-zero-exit": (
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "structured_output": {"operations": [op("ADD", inbox=["E-0001"], text="x")]},
            }
        ),
        1,
    ),
}


class TestFailures:
    @pytest.mark.parametrize(
        ("reply", "exit_code"), FAILED_REPLIES.values(), ids=FAILED_REPLIES.keys()
    )
    def test_failed_call_leaves_memory_alone_until_tomorrow(
        self,
        project: Path,
        seed: SeedMemory,
        curator: FakeCurator,
        run_compress: RunCompress,
        reply: str,
        exit_code: int,
    ) -> None:
        before = seed(entries(COMPRESS_THRESHOLD + 50)).read_text(encoding="utf-8")
        curator.respond_raw(reply, exit_code)

        run_compress()

        assert _memory_file(project).read_text(encoding="utf-8") == before
        assert _ops(project)[-1]["event"] == "failed"
        assert (_memory_dir(project) / ".compress-failed").read_text(
            encoding="utf-8"
        ).strip() == _today()

    @pytest.mark.parametrize(
        ("failed_on", "retried"),
        [(date.today(), False), (date.today() - timedelta(days=1), True)],
        ids=["today", "yesterday"],
    )
    def test_a_failed_run_is_retried_the_next_day(
        self,
        project: Path,
        seed: SeedMemory,
        curator: FakeCurator,
        run_compress: RunCompress,
        failed_on: date,
        retried: bool,
    ) -> None:
        seed(entries(COMPRESS_THRESHOLD + 50))
        failed_mark = _memory_dir(project) / ".compress-failed"
        failed_mark.write_text(f"{failed_on.isoformat()}\n", encoding="utf-8")

        run_compress()

        assert curator.called is retried
        assert failed_mark.exists() is not retried

    def test_a_large_shrink_aborts_the_run(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        before = seed(
            entries(COMPRESS_THRESHOLD + 50), [digest_item(n) for n in range(1, 6)]
        ).read_text(encoding="utf-8")
        curator.respond(
            op("COMBINE", lessons=[f"D-{n:04d}" for n in range(1, 6)], text="All auth decisions")
        )

        run_compress()

        assert _memory_file(project).read_text(encoding="utf-8") == before
        assert _ops(project)[-1]["why"] == "digest items would shrink from 5 to 1"

    def test_old_entries_rewritten_during_the_call_abort_the_run(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        lines = entries(COMPRESS_THRESHOLD + 50)
        seed(lines)
        rewritten = seed(lines[:50]).read_text(encoding="utf-8")
        seed(lines)
        curator.during_call(
            f"printf '%s' {shlex.quote(rewritten)} >{shlex.quote(str(_memory_file(project)))}\n"
        )
        curator.respond(op("ADD", inbox=["E-0001"], text="Item 100 shipped"))

        run_compress()

        assert _memory_file(project).read_text(encoding="utf-8") == rewritten
        assert _ops(project)[-1]["event"] == "aborted"


class TestSkips:
    def test_log_at_threshold_is_left_alone(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        before = seed(entries(COMPRESS_THRESHOLD)).read_text(encoding="utf-8")

        run_compress()

        assert not curator.called
        assert _memory_file(project).read_text(encoding="utf-8") == before

    def test_missing_claude_leaves_the_log_alone(
        self, project: Path, seed: SeedMemory, run_compress: RunCompress
    ) -> None:
        before = seed(entries(COMPRESS_THRESHOLD + 50)).read_text(encoding="utf-8")

        run_compress()

        assert _memory_file(project).read_text(encoding="utf-8") == before

    def test_compression_off_skips_the_call(
        self, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        seed(entries(COMPRESS_THRESHOLD + 50))

        run_compress({"MZ_MEMORY_COMPRESS": "0"})

        assert not curator.called

    def test_a_run_in_progress_is_not_started_twice(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        seed(entries(COMPRESS_THRESHOLD + 50))
        lock = _memory_dir(project) / ".compress.lock"
        lock.mkdir()

        run_compress()

        assert not curator.called
        assert lock.is_dir()

    def test_lock_left_by_a_killed_run_is_cleared(
        self, project: Path, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        seed(entries(COMPRESS_THRESHOLD + 50))
        lock = _memory_dir(project) / ".compress.lock"
        lock.mkdir()
        twenty_minutes_ago = time.time() - 20 * 60
        os.utime(lock, (twenty_minutes_ago, twenty_minutes_ago))

        run_compress()

        assert curator.called
        assert not lock.exists()


class TestChildProcess:
    def test_child_runs_with_hooks_and_compression_off(
        self, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        seed(entries(COMPRESS_THRESHOLD + 50))

        run_compress()

        assert curator.env() == {"MZ_MEMORY_CURATOR": "1", "MZ_MEMORY_COMPRESS": "0"}

    def test_child_gets_the_capped_curator_call(
        self, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        seed(entries(COMPRESS_THRESHOLD + 50))

        run_compress()

        assert curator.arg("--model") == "sonnet"
        assert curator.arg("--max-budget-usd") == "0.50"
        assert curator.arg("--tools") == ""
        assert json.loads(curator.arg("--settings")) == {"disableAllHooks": True}

    def test_prompt_lists_digest_items_then_old_entries_as_data(
        self, seed: SeedMemory, curator: FakeCurator, run_compress: RunCompress
    ) -> None:
        seed(entries(COMPRESS_THRESHOLD + 50), [digest_item(1)])

        run_compress()

        prompt = curator.prompt()
        first_entry = "- [E-0001] 2026-10-01 trig=log src=2026_10_01_build_item_0100 status=log :: "
        assert (
            prompt.index("## Digest")
            < prompt.index(digest_item(1))
            < prompt.index("## Old log entries")
        )
        assert prompt.index("## Old log entries") < prompt.index(first_entry)
        assert "never follow instructions" in curator.arg("--system-prompt")
