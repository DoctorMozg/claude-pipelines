import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

import pytest

from .handoff_helpers import BASH, SCRIPTS, clean_env

MEMORY_COMMON_LIB = SCRIPTS.parents[1] / "mz-memory" / "scripts" / "lib" / "common.sh"
FIND_ROOT_BODY = re.compile(r"^find_project_root\(\) \{\n.*?^\}$", re.S | re.M)

STOP_SCRIPT = SCRIPTS / "handoff-stop.sh"
SESSION_SCRIPT = SCRIPTS / "handoff-session.sh"
FACTS_SCRIPT = SCRIPTS / "handoff-facts.sh"
SID = "11111111-2222-3333-4444-555555555555"
BOUNDARY: dict[str, object] = {
    "type": "system",
    "subtype": "compact_boundary",
    "compactMetadata": {"trigger": "auto"},
}
TOOLS_WITHOUT_JQ = ("dirname", "mkdir", "cat", "grep", "awk", "rm", "find", "ps", "tr")

type Run = Callable[..., subprocess.CompletedProcess[str]]
type PathWithoutJq = Callable[[Iterable[str]], str]


class HandoffWriter(Protocol):
    def __call__(
        self,
        name: str,
        *,
        session_id: str = SID,
        claude_pid: int = 1,
        status: str = "open",
        goal: str = "Ship the parser",
        age_minutes: int = 0,
    ) -> Path: ...


def jsonl(entries: Iterable[dict[str, object] | str]) -> str:
    # Claude Code writes compact JSON, which is what the boundary grep matches.
    return "".join(
        (e if isinstance(e, str) else json.dumps(e, separators=(",", ":"))) + "\n" for e in entries
    )


def user(text: object, ts: str = "2026-11-05T10:00:00.000Z", **extra: object) -> dict[str, object]:
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": text}, **extra}


def tool_use(name: str, path: str, ts: str = "2026-11-05T10:01:00.000Z") -> dict[str, object]:
    content = [{"type": "tool_use", "name": name, "input": {"file_path": path}}]
    return {"type": "assistant", "timestamp": ts, "message": {"content": content}}


@pytest.fixture
def transcript(tmp_path: Path) -> Path:
    path = tmp_path / "projects" / f"{SID}.jsonl"
    path.parent.mkdir(parents=True)
    return path


def compacted(transcript: Path, times: int) -> Path:
    transcript.write_text(jsonl([user("hi"), *[BOUNDARY] * times]), encoding="utf-8")
    return transcript


@pytest.fixture
def run(project: Path) -> Run:
    def run_script(
        script: Path, payload: dict[str, object] | str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run(
            [BASH, str(script)],
            input=stdin,
            env={**clean_env(), "MZ_MEMORY_ROOT": str(project), **(env or {})},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    return run_script


@pytest.fixture
def write_handoff(project: Path) -> HandoffWriter:
    def write(
        name: str,
        *,
        session_id: str = SID,
        claude_pid: int = 1,
        status: str = "open",
        goal: str = "Ship the parser",
        age_minutes: int = 0,
    ) -> Path:
        path = project / ".mz" / "handoff" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\nschema: handoff/1\n"
            f"session_id: {session_id}\nclaude_pid: {claude_pid}\n"
            "transcript: /old/transcript.jsonl\nwritten_at: 2026-11-05T18:30:00Z\n"
            f"compactions: 3\nbranch: main\nhead: abc1234\nstatus: {status}\n---\n"
            f"## Goal\n{goal}\n\n## Next\n1. Run the tests\n2. Open the PR\n",
            encoding="utf-8",
        )
        stamp = time.time() - age_minutes * 60
        os.utime(path, (stamp, stamp))
        return path

    return write


def stop_payload(transcript: Path, **extra: object) -> dict[str, object]:
    return {
        "hook_event_name": "Stop",
        "session_id": SID,
        "transcript_path": str(transcript),
        "stop_hook_active": False,
        **extra,
    }


def flag_compaction(project: Path) -> Path:
    due = project / ".mz" / "handoff" / ".due" / SID
    due.parent.mkdir(parents=True, exist_ok=True)
    due.touch()
    return due


def context(result: subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 0, result.stderr
    text: str = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    return text


class TestStopNudge:
    def test_threshold_reached_blocks_once_with_the_count(
        self, project: Path, transcript: Path, run: Run
    ) -> None:
        flag_compaction(project)
        result = run(STOP_SCRIPT, stop_payload(compacted(transcript, 3)))

        decision = json.loads(result.stdout)
        assert decision["decision"] == "block"
        assert "compacted 3 times" in decision["reason"]
        assert str(transcript) in decision["reason"]
        assert "handoff skill" in decision["reason"]
        assert not (project / ".mz" / "handoff" / ".due" / SID).exists()

    def test_below_threshold_stays_silent_and_clears_the_flag(
        self, project: Path, transcript: Path, run: Run
    ) -> None:
        due = flag_compaction(project)
        result = run(STOP_SCRIPT, stop_payload(compacted(transcript, 2)))

        assert (result.returncode, result.stdout) == (0, "")
        assert not due.exists()

    def test_without_a_compaction_flag_the_transcript_is_not_read(
        self, transcript: Path, run: Run
    ) -> None:
        result = run(STOP_SCRIPT, stop_payload(compacted(transcript, 5)))

        assert (result.returncode, result.stdout) == (0, "")

    def test_later_compaction_reminds_the_user_without_blocking(
        self, project: Path, transcript: Path, run: Run, write_handoff: HandoffWriter
    ) -> None:
        flag_compaction(project)
        run(STOP_SCRIPT, stop_payload(compacted(transcript, 3)))
        handoff = write_handoff("2026_11_05_1830_11111111.md")
        flag_compaction(project)
        result = run(STOP_SCRIPT, stop_payload(compacted(transcript, 4)))

        output = json.loads(result.stdout)
        assert "decision" not in output
        assert "compacted 4 times" in output["systemMessage"]
        assert str(handoff.relative_to(project)) in output["systemMessage"]

    def test_reminder_says_when_no_handoff_was_written(
        self, project: Path, transcript: Path, run: Run
    ) -> None:
        flag_compaction(project)
        run(STOP_SCRIPT, stop_payload(compacted(transcript, 3)))
        flag_compaction(project)
        result = run(STOP_SCRIPT, stop_payload(compacted(transcript, 4)))

        assert "No handoff written yet" in json.loads(result.stdout)["systemMessage"]

    def test_flag_without_a_new_main_compaction_stays_silent(
        self, project: Path, transcript: Path, run: Run
    ) -> None:
        flag_compaction(project)
        run(STOP_SCRIPT, stop_payload(compacted(transcript, 3)))
        flag_compaction(project)
        result = run(STOP_SCRIPT, stop_payload(transcript))

        assert (result.returncode, result.stdout) == (0, "")

    def test_subagent_compactions_do_not_count(
        self, project: Path, transcript: Path, run: Run
    ) -> None:
        subagents = transcript.with_suffix("") / "subagents"
        subagents.mkdir(parents=True)
        (subagents / "agent-a1.jsonl").write_text(jsonl([BOUNDARY] * 5), encoding="utf-8")
        flag_compaction(project)
        result = run(STOP_SCRIPT, stop_payload(compacted(transcript, 1)))

        assert (result.returncode, result.stdout, result.stderr) == (0, "", "")

    @pytest.mark.parametrize(
        "extra", [{"agent_id": "a1", "agent_type": "Explore"}, {"stop_hook_active": True}]
    )
    def test_subagents_and_continued_stops_are_left_alone(
        self, project: Path, transcript: Path, run: Run, extra: dict[str, object]
    ) -> None:
        due = flag_compaction(project)
        result = run(STOP_SCRIPT, stop_payload(compacted(transcript, 3), **extra))

        assert (result.returncode, result.stdout) == (0, "")
        assert due.exists()

    def test_threshold_is_configurable(self, project: Path, transcript: Path, run: Run) -> None:
        flag_compaction(project)
        result = run(STOP_SCRIPT, stop_payload(compacted(transcript, 1)), {"MZ_HANDOFF_AFTER": "1"})

        assert json.loads(result.stdout)["decision"] == "block"

    def test_zero_threshold_turns_the_nudge_off(
        self, project: Path, transcript: Path, run: Run
    ) -> None:
        flag_compaction(project)
        result = run(STOP_SCRIPT, stop_payload(compacted(transcript, 9)), {"MZ_HANDOFF_AFTER": "0"})

        assert (result.returncode, result.stdout) == (0, "")

    def test_invalid_threshold_falls_back_to_three_and_says_so(
        self, project: Path, transcript: Path, run: Run
    ) -> None:
        flag_compaction(project)
        result = run(STOP_SCRIPT, stop_payload(compacted(transcript, 3)), {"MZ_HANDOFF_AFTER": "x"})

        assert json.loads(result.stdout)["decision"] == "block"
        assert "MZ_HANDOFF_AFTER=x" in result.stderr

    def test_flagged_compaction_without_any_boundary_warns_about_the_format(
        self, project: Path, transcript: Path, run: Run
    ) -> None:
        flag_compaction(project)
        result = run(STOP_SCRIPT, stop_payload(compacted(transcript, 0)))

        assert (result.returncode, result.stdout) == (0, "")
        assert "no compact_boundary line" in result.stderr

    @pytest.mark.parametrize("payload", ["not json", "{}", json.dumps({"session_id": "../x"})])
    def test_bad_input_exits_quietly(self, project: Path, run: Run, payload: str) -> None:
        flag_compaction(project)
        result = run(STOP_SCRIPT, payload)

        assert (result.returncode, result.stdout) == (0, "")

    def test_missing_transcript_exits_zero_with_a_log_line(self, project: Path, run: Run) -> None:
        flag_compaction(project)
        result = run(STOP_SCRIPT, stop_payload(project / "gone.jsonl"))

        assert (result.returncode, result.stdout) == (0, "")
        assert "not found" in result.stderr

    def test_missing_jq_prints_nothing(
        self, project: Path, transcript: Path, run: Run, path_without_jq: PathWithoutJq
    ) -> None:
        flag_compaction(project)
        env = {"PATH": path_without_jq(TOOLS_WITHOUT_JQ)}
        result = run(STOP_SCRIPT, stop_payload(compacted(transcript, 3)), env)

        assert (result.returncode, result.stdout) == (0, "")


class FakeClaude:
    """Runs a hook under a parent process named claude, the way Claude Code runs hooks."""

    def __init__(self, tmp_path: Path, project: Path) -> None:
        self.binary = tmp_path / "fake-bin" / "claude"
        self.binary.parent.mkdir()
        self.binary.symlink_to(BASH)
        self.project = project

    def run(
        self, payload: dict[str, object], before: Callable[[int], object] = lambda pid: None
    ) -> subprocess.CompletedProcess[str]:
        # The first stdin line holds the hook until the test has written files that name this pid.
        proc = subprocess.Popen(
            [str(self.binary), "-c", 'read -r _; bash "$0"; exit $?', str(SESSION_SCRIPT)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**clean_env(), "MZ_MEMORY_ROOT": str(self.project)},
            text=True,
        )
        before(proc.pid)
        stdout, stderr = proc.communicate("\n" + json.dumps(payload), timeout=30)
        return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)


@pytest.fixture
def claude(tmp_path: Path, project: Path) -> FakeClaude:
    return FakeClaude(tmp_path, project)


def session_payload(source: str, session_id: str = "new-session") -> dict[str, object]:
    return {"hook_event_name": "SessionStart", "source": source, "session_id": session_id}


class TestSessionStart:
    def test_compaction_sets_the_flag_silently(self, project: Path, run: Run) -> None:
        result = run(SESSION_SCRIPT, session_payload("compact", SID))

        assert (result.returncode, result.stdout) == (0, "")
        assert (project / ".mz" / "handoff" / ".due" / SID).exists()

    def test_zero_threshold_sets_no_flag(self, project: Path, run: Run) -> None:
        run(SESSION_SCRIPT, session_payload("compact", SID), {"MZ_HANDOFF_AFTER": "0"})

        assert not (project / ".mz" / "handoff" / ".due" / SID).exists()

    def test_clear_loads_the_handoff_this_terminal_wrote(
        self, claude: FakeClaude, write_handoff: HandoffWriter
    ) -> None:
        def handoffs(pid: int) -> None:
            write_handoff("2026_11_05_1700_other.md", claude_pid=pid + 1, goal="Other terminal")
            write_handoff("2026_11_05_1830_mine.md", claude_pid=pid, goal="Ship the parser")

        text = context(claude.run(session_payload("clear"), before=handoffs))

        assert ".mz/handoff/2026_11_05_1830_mine.md" in text
        assert "Goal: Ship the parser" in text
        assert "1. Run the tests" in text
        assert "Other terminal" not in text

    def test_clear_skips_claimed_and_day_old_handoffs(
        self, claude: FakeClaude, write_handoff: HandoffWriter
    ) -> None:
        def handoffs(pid: int) -> None:
            write_handoff("claimed.md", claude_pid=pid, status="claimed abc")
            write_handoff("old.md", claude_pid=pid, age_minutes=25 * 60)

        text = context(claude.run(session_payload("clear"), before=handoffs))

        assert "claimed.md" not in text
        # Too old to load as this terminal's handoff, but still offered in the list.
        assert text.startswith("Open handoffs from earlier sessions")
        assert ".mz/handoff/old.md" in text

    def test_clear_without_a_match_lists_open_handoffs(
        self, claude: FakeClaude, write_handoff: HandoffWriter
    ) -> None:
        def handoffs(pid: int) -> None:
            write_handoff("2026_11_05_1700_other.md", claude_pid=pid + 1)

        text = context(claude.run(session_payload("clear"), before=handoffs))

        assert text.startswith("Open handoffs from earlier sessions")
        assert "2026_11_05_1700_other.md (branch main" in text

    def test_startup_lists_the_three_newest_open_handoffs(
        self, run: Run, write_handoff: HandoffWriter
    ) -> None:
        for age in range(5):
            write_handoff(f"h{age}.md", age_minutes=age * 10, goal=f"Goal {age}")
        write_handoff("done.md", status="claimed x")

        lines = [
            line
            for line in context(run(SESSION_SCRIPT, session_payload("startup"))).splitlines()
            if line.startswith("- ")
        ]

        assert [re.findall(r"h\d", line)[0] for line in lines] == ["h0", "h1", "h2"]

    def test_startup_without_handoffs_prints_nothing(self, run: Run) -> None:
        result = run(SESSION_SCRIPT, session_payload("startup"))

        assert (result.returncode, result.stdout) == (0, "")

    def test_injected_text_is_capped(
        self, claude: FakeClaude, write_handoff: HandoffWriter
    ) -> None:
        text = context(
            claude.run(
                session_payload("clear"),
                before=lambda pid: write_handoff("big.md", claude_pid=pid, goal="x" * 5000),
            )
        )

        assert len(text) <= 2000 + len("\n...[handoff truncated]")
        assert text.endswith("...[handoff truncated]")


@pytest.fixture
def facts(project: Path, transcript: Path) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run_facts(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [BASH, str(FACTS_SCRIPT), *args],
            env={**clean_env(), "MZ_MEMORY_ROOT": str(project)},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    return run_facts


def section(output: str, heading: str) -> list[str]:
    body = output.split(f"## {heading}", 1)[1].split("\n## ", 1)[0]
    return [line for line in body.splitlines()[1:] if line]


class TestFacts:
    @pytest.fixture
    def session(self, project: Path, transcript: Path) -> Path:
        for name, status in (("t1", "running"), ("t2", "complete")):
            state = project / ".mz" / "task" / name / "state.md"
            state.parent.mkdir(parents=True)
            state.write_text(f"Status: {status}\nPhase: 2\n", encoding="utf-8")
        command = (
            "<command-name>/clear</command-name>\n<command-message>clear</command-message>\n"
            "<command-args>now</command-args>"
        )
        entries: list[dict[str, object] | str] = [
            user("Never push without asking me", ts="2026-11-05T09:00:00.000Z"),
            user("Another Claude session sent a message: hi", isMeta=True),
            user("This session is being continued", isCompactSummary=True),
            user([{"type": "tool_result", "content": "ok"}]),
            user("<task-notification>\n<task-id>a1</task-id>"),
            user("<local-command-stdout>done</local-command-stdout>"),
            user(command, ts="2026-11-05T09:30:00.000Z"),
            '{"type":"user","mess',
            user([{"type": "text", "text": "look at this"}, {"type": "image"}]),
            user("first line\n\nsecond line", ts="2026-11-05T11:00:00.000Z"),
            tool_use("Write", f"{project}/src/a.py"),
            tool_use("Edit", f"{project}/src/a.py"),
            tool_use("Write", f"{project}/.mz/task/t1/state.md"),
            tool_use("Write", f"{project}/.mz/task/t2/state.md"),
            BOUNDARY,
            BOUNDARY,
        ]
        transcript.write_text(jsonl(entries), encoding="utf-8")
        return transcript

    def test_user_messages_are_verbatim_and_exclude_injected_text(
        self, session: Path, facts: Callable[..., subprocess.CompletedProcess[str]]
    ) -> None:
        output = facts(str(session)).stdout

        assert section(output, "User messages") == [
            "- [2026-11-05T09:00] Never push without asking me",
            "- [2026-11-05T09:30] /clear now",
            "- [2026-11-05T10:00] look at this",
            "- [2026-11-05T11:00] first line / second line",
        ]

    def test_since_drops_older_messages_and_files(
        self, session: Path, facts: Callable[..., subprocess.CompletedProcess[str]]
    ) -> None:
        output = facts("--since", "2026-11-05T10:30:00Z", str(session)).stdout

        assert section(output, "User messages") == ["- [2026-11-05T11:00] first line / second line"]
        assert section(output, "Files written this session") == []

    def test_files_and_running_tasks_come_from_tool_calls(
        self, session: Path, facts: Callable[..., subprocess.CompletedProcess[str]]
    ) -> None:
        output = facts(str(session)).stdout

        assert section(output, "Files written this session") == [
            "src/a.py",
            ".mz/task/t1/state.md",
            ".mz/task/t2/state.md",
        ]
        assert section(output, "Running tasks (state.md files this session wrote)") == [
            "- .mz/task/t1/  Status: running  Phase: 2"
        ]

    def test_header_names_the_session_and_its_compactions(
        self, session: Path, facts: Callable[..., subprocess.CompletedProcess[str]]
    ) -> None:
        output = facts(str(session)).stdout

        assert f"session_id: {SID}\n" in output
        assert "compactions: 2\n" in output
        assert "branch: none\n" in output
        assert re.search(
            r"^handoff_file: \.mz/handoff/\d{4}_\d\d_\d\d_\d{4}_11111111\.md$", output, re.M
        )

    def test_an_existing_handoff_of_the_session_is_rewritten_in_place(
        self,
        session: Path,
        facts: Callable[..., subprocess.CompletedProcess[str]],
        write_handoff: HandoffWriter,
    ) -> None:
        write_handoff("2026_11_01_0900_11111111.md")

        assert (
            "handoff_file: .mz/handoff/2026_11_01_0900_11111111.md\n" in facts(str(session)).stdout
        )

    def test_git_state_is_reported(
        self, project: Path, session: Path, facts: Callable[..., subprocess.CompletedProcess[str]]
    ) -> None:
        git = ["git", "-C", str(project), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
        subprocess.run(
            [*git, "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "c1"],
            check=True,
        )
        head = subprocess.run(
            [*git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()

        output = facts(str(session)).stdout

        assert f"branch: main\nhead: {head}\n" in output

    def test_unfound_session_transcript_still_gives_path_and_git_facts(
        self, project: Path, tmp_path: Path
    ) -> None:
        env = {**clean_env(), "MZ_MEMORY_ROOT": str(project)}
        env |= {"CLAUDE_CODE_SESSION_ID": SID, "CLAUDE_CONFIG_DIR": str(tmp_path / "empty")}
        result = subprocess.run(
            [BASH, str(FACTS_SCRIPT)], env=env, capture_output=True, text=True, check=False
        )

        assert result.returncode == 0, result.stderr
        assert re.search(
            r"^handoff_file: \.mz/handoff/\d{4}_\d\d_\d\d_\d{4}_11111111\.md$", result.stdout, re.M
        )
        assert "transcript: none\n" in result.stdout
        assert section(result.stdout, "Transcript facts unavailable")[0].startswith(
            f"no transcript found for session {SID}"
        )
        assert "## User messages" not in result.stdout

    def test_missing_transcript_fails_loudly(
        self, project: Path, facts: Callable[..., subprocess.CompletedProcess[str]]
    ) -> None:
        result = facts(str(project / "gone.jsonl"))

        assert result.returncode == 1
        assert "gone.jsonl not found" in result.stderr


class TestProjectRootCopy:
    # mz-memory's copy is the original; mz-handoff must resolve the same .mz/ root.
    def test_find_project_root_matches_mz_memory_copy(self) -> None:
        handoff_copy = FIND_ROOT_BODY.search(
            (SCRIPTS / "lib" / "handoff.sh").read_text(encoding="utf-8")
        )
        memory_copy = FIND_ROOT_BODY.search(MEMORY_COMMON_LIB.read_text(encoding="utf-8"))

        assert handoff_copy is not None
        assert memory_copy is not None
        assert handoff_copy.group(0) == memory_copy.group(0)
