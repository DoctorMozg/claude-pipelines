"""Live smoke test for approval gates: a scripted MCP permission host answers AskUserQuestion.
Runs Approve, Reject, feedback and no answer through memory-note and polish; stays out of CI.
The host approves every other permission prompt, as the attending user would, and lists them."""

import argparse
import json
import logging
import re
import shutil
import sys
import tempfile
import uuid
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests.e2e.gate_host import ASK_TOOL, TOOL_NAME
from tests.e2e.smoke_common import (
    Check,
    HeadlessClaude,
    Session,
    SmokeError,
    forget_session,
    print_checks,
    run_seed,
)

log = logging.getLogger("gate_smoke")

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_SCRIPT = Path(__file__).resolve().parent / "gate_host.py"
HOST_SERVER = "gate"
MODEL = "haiku"
RUN_TIMEOUT_S = 600
MAX_PARALLEL = 6
FIXTURE_LIB = Path("mz-memory/evals/_lib/fixture.sh")
MEMORY = Path(".mz/memory/MEMORY.md")
JOURNAL = Path(".mz/journal.md")
MEMORY_NOTE_SKILL = Path("mz-memory/skills/memory-note/SKILL.md")
POLISH_SKILL = Path("mz-dev-pipe/skills/polish/SKILL.md")
MEMORY_PLUGINS = ("mz-memory",)
# mz-dev-pipe depends on mz-base, and mz-memory brings the journal hook along.
DEV_PIPE_PLUGINS = ("mz-memory", "mz-dev-pipe", "mz-base")
GATE_QUESTION = re.compile(r"^- question: `([^`]+)`", re.MULTILINE)
PROMPT_TARGET_KEYS = ("command", "file_path", "path", "pattern")
PROMPT_CHARS = 90

MEMORY_SEED = """set -euo pipefail
source "$1"
init_project
write_memory "" ""
"""

# Each removable comment meets one of the optimizer's AI-residue rules exactly: a robotic
# section label, or a comment whose every content word is in the next code line. The WHY comment
# is a control.
WHY_COMMENT = "# Totals stay ints because the billing API rejects floats."
LABEL_COMMENT = "# Helpers"
FOR_COMMENT = "# For each item in items"
RETURN_COMMENT = "# Return result"
CODE_LINES = ("result = 0", "for item in items:", "result += item", "return result")
CALC = f"""{LABEL_COMMENT}
def total(items: list[int]) -> int:
    {WHY_COMMENT}
    result = 0
    {FOR_COMMENT}
    for item in items:
        result += item
    {RETURN_COMMENT}
    return result
"""
# polish runs the project's tests before its gate, so the project names a test command that
# needs nothing installed; without one, polish would ask for it, a question the script can't answer.
TEST_CALC = """import unittest

from calc import total


class TotalTest(unittest.TestCase):
    def test_sums_items(self) -> None:
        self.assertEqual(total([1, 2, 3]), 6)
"""
POLISH_SEED = f"""set -euo pipefail
git init -q -b main
git -c user.name=smoke -c user.email=smoke@example.invalid commit -q --allow-empty -m init
git checkout -q -b feature
cat > calc.py <<'PY'
{CALC}PY
cat > test_calc.py <<'PY'
{TEST_CALC}PY
printf '# calc\\n\\nTest command: `python3 -m unittest`. There is no linter.\\n' > CLAUDE.md
git add calc.py test_calc.py CLAUDE.md
git -c user.name=smoke -c user.email=smoke@example.invalid commit -q -m calc
"""


@dataclass(frozen=True)
class GateRun:
    session: Session
    project: Path
    session_id: str
    requests: list[dict[str, Any]]

    def asked(self) -> list[dict[str, Any]]:
        return [request for request in self.requests if request.get("tool") == ASK_TOOL]

    def prompts(self) -> list[str]:
        """The permission prompts besides the gate, each a click for a user in a real session."""
        prompts = []
        for request in self.requests:
            if request.get("tool") == ASK_TOOL:
                continue
            tool_input = request.get("input") or {}
            target = next((tool_input[k] for k in PROMPT_TARGET_KEYS if k in tool_input), "")
            prompts.append(f"{request.get('tool')}: {' '.join(str(target).split())[:PROMPT_CHARS]}")
        return prompts

    def read(self, path: Path) -> str:
        file = self.project / path
        return file.read_text(encoding="utf-8") if file.is_file() else ""

    def polish_state(self) -> str:
        states = sorted(self.project.glob(".mz/task/*_polish_*/state.md"))
        return states[-1].read_text(encoding="utf-8") if states else ""

    def journal_answers(self) -> list[object]:
        """Answers that journal-capture recorded for this session, in order."""
        answers: list[object] = []
        for block in self.read(JOURNAL).split("\n### ")[1:]:
            header, _, body = block.partition("\n")
            if f"session {self.session_id}" not in header or ASK_TOOL not in header:
                continue
            response = body.partition("response (verbatim):\n")[2].strip().split("\n", 1)[0]
            try:
                answers.extend((json.loads(response).get("answers") or {}).values())
            except (json.JSONDecodeError, AttributeError):
                answers.append(f"unparsed response: {response[:80]}")
        return answers


@dataclass(frozen=True)
class Scenario:
    label: str
    prompt: str
    answers: tuple[str, ...]
    plugins: tuple[str, ...]
    seed: str
    skill: Path
    checks: Callable[[GateRun], list[Check]]


def memory_has(text: str, present: bool) -> Callable[[GateRun], list[Check]]:
    verb = "reached" if present else "stayed out of"
    return lambda run: [Check(f"'{text}' {verb} MEMORY.md", present, text in run.read(MEMORY))]


def feedback_note_checks(run: GateRun) -> list[Check]:
    memory = run.read(MEMORY)
    return [
        Check("the revised note reached MEMORY.md", True, "kestrel-6" in memory),
        Check("the first draft stayed out", False, "kestrel-5" in memory),
    ]


def code_kept(calc: str) -> Check:
    return Check("calc.py kept every code line", True, all(line in calc for line in CODE_LINES))


def polish_approve_checks(run: GateRun) -> list[Check]:
    calc = run.read(Path("calc.py"))
    return [
        Check(
            "all three removable comments are gone",
            [False, False, False],
            [LABEL_COMMENT in calc, FOR_COMMENT in calc, RETURN_COMMENT in calc],
        ),
        Check("the WHY comment stayed", True, WHY_COMMENT in calc),
        code_kept(calc),
        Check("state.md records the approval", True, "assessment approved" in run.polish_state()),
    ]


def polish_reject_checks(run: GateRun) -> list[Check]:
    return [
        Check("calc.py is untouched", CALC, run.read(Path("calc.py"))),
        Check("state.md says aborted_by_user", True, "aborted_by_user" in run.polish_state()),
    ]


def polish_feedback_checks(run: GateRun) -> list[Check]:
    calc = run.read(Path("calc.py"))
    return [
        Check(
            "the other two were removed",
            [False, False],
            [LABEL_COMMENT in calc, FOR_COMMENT in calc],
        ),
        Check("the comment the feedback kept stayed", True, RETURN_COMMENT in calc),
        Check("the WHY comment stayed", True, WHY_COMMENT in calc),
        code_kept(calc),
    ]


POLISH_PROMPT = "/mz-dev-pipe:polish No AI leftovers in calc.py"


def note(body: str) -> str:
    return f"/mz-memory:memory-note {body}"


SCENARIOS = (
    Scenario(
        "note-approve",
        note("The staging database host is heron-7."),
        ("Approve",),
        MEMORY_PLUGINS,
        MEMORY_SEED,
        MEMORY_NOTE_SKILL,
        memory_has("heron-7", present=True),
    ),
    Scenario(
        "note-reject",
        note("The staging database host is osprey-3."),
        ("Reject",),
        MEMORY_PLUGINS,
        MEMORY_SEED,
        MEMORY_NOTE_SKILL,
        memory_has("osprey-3", present=False),
    ),
    Scenario(
        "note-feedback",
        note("The staging database host is kestrel-5."),
        ("Change the host name to kestrel-6.", "Approve"),
        MEMORY_PLUGINS,
        MEMORY_SEED,
        MEMORY_NOTE_SKILL,
        feedback_note_checks,
    ),
    Scenario(
        "note-no-answer",
        note("The staging database host is plover-2."),
        (),
        MEMORY_PLUGINS,
        MEMORY_SEED,
        MEMORY_NOTE_SKILL,
        memory_has("plover-2", present=False),
    ),
    Scenario(
        "polish-approve",
        POLISH_PROMPT,
        ("Approve",),
        DEV_PIPE_PLUGINS,
        POLISH_SEED,
        POLISH_SKILL,
        polish_approve_checks,
    ),
    Scenario(
        "polish-reject",
        POLISH_PROMPT,
        ("Reject",),
        DEV_PIPE_PLUGINS,
        POLISH_SEED,
        POLISH_SKILL,
        polish_reject_checks,
    ),
    Scenario(
        "polish-feedback",
        POLISH_PROMPT,
        (f"Keep the comment '{RETURN_COMMENT}' and apply the other edits.", "Approve"),
        DEV_PIPE_PLUGINS,
        POLISH_SEED,
        POLISH_SKILL,
        polish_feedback_checks,
    ),
)


def gate_question(skill_file: Path) -> str:
    match = GATE_QUESTION.search(skill_file.read_text(encoding="utf-8"))
    if match is None:
        raise SmokeError(f"no '- question:' line in {skill_file}")
    return match.group(1)


def host_status(session: Session) -> object:
    servers = session.init().get("mcp_servers") or []
    return next(
        (server.get("status") for server in servers if server.get("name") == HOST_SERVER), "absent"
    )


def common_checks(run: GateRun, scenario: Scenario, question: str) -> list[Check]:
    asked = run.asked()
    questions = [
        q.get("question") for request in asked for q in request["input"].get("questions") or []
    ]
    return [
        Check("the gate host connected", "connected", host_status(run.session)),
        Check(
            "AskUserQuestion was offered", True, ASK_TOOL in (run.session.init().get("tools") or [])
        ),
        # A no-answer run still asks once; the host's refusal stands in for the silent user.
        Check(
            "one question per scripted answer",
            list(scenario.answers) or [None],
            [r.get("answer") for r in asked],
        ),
        Check(
            "every question was the skill's gate question", [question] * len(questions), questions
        ),
        Check(
            "journal-capture recorded each answer", list(scenario.answers), run.journal_answers()
        ),
        Check("every hook exited successfully", [], run.session.failed_hooks()),
    ]


def write_mcp_config(path: Path, answers: Sequence[str], host_log: Path) -> Path:
    server = {
        "type": "stdio",
        "command": sys.executable,
        "args": ["-I", str(HOST_SCRIPT)],
        "env": {"GATE_ANSWERS": json.dumps(list(answers)), "GATE_HOST_LOG": str(host_log)},
    }
    path.write_text(json.dumps({"mcpServers": {HOST_SERVER: server}}), encoding="utf-8")
    return path


def read_host_log(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@dataclass(frozen=True)
class Outcome:
    label: str
    cost_usd: float
    checks: list[Check]
    prompts: list[str]


@dataclass(frozen=True)
class Runner:
    plugins_root: Path
    workdir: Path
    max_usd: float

    def run(self, scenario: Scenario) -> Outcome:
        try:
            run, checks = self.run_session(scenario)
        except SmokeError as error:
            log.error("%s", error)
            return Outcome(
                scenario.label, 0.0, [Check("the run finished", "finished", str(error))], []
            )
        return Outcome(scenario.label, run.session.cost_usd, checks, run.prompts())

    def run_session(self, scenario: Scenario) -> tuple[GateRun, list[Check]]:
        project = self.workdir / scenario.label
        project.mkdir()
        run_seed(project, scenario.seed, str(self.plugins_root / FIXTURE_LIB))
        host_log = self.workdir / f"{scenario.label}.host.jsonl"
        config = write_mcp_config(
            self.workdir / f"{scenario.label}.mcp.json", scenario.answers, host_log
        )
        session_id = str(uuid.uuid4())
        args = [
            "--session-id",
            session_id,
            "--strict-mcp-config",
            "--mcp-config",
            str(config),
            "--permission-prompt-tool",
            f"mcp__{HOST_SERVER}__{TOOL_NAME}",
            # The mode approves file writes, so the prompt notes show what acceptEdits still asks.
            "--permission-mode",
            "acceptEdits",
        ]
        claude = HeadlessClaude(self.workdir, project, MODEL, self.max_usd, RUN_TIMEOUT_S)
        plugins = [self.plugins_root / name for name in scenario.plugins]
        try:
            session = claude.run(scenario.label, scenario.prompt, plugins, args)
        finally:
            forget_session(session_id, project)
        run = GateRun(session, project, session_id, read_host_log(host_log))
        question = gate_question(self.plugins_root / scenario.skill)
        return run, [*common_checks(run, scenario, question), *scenario.checks(run)]


def check_preconditions(plugins_root: Path, scenarios: Sequence[Scenario]) -> None:
    for tool in ("claude", "git", "jq"):
        if shutil.which(tool) is None:
            raise SmokeError(f"{tool} is not on PATH")
    for scenario in scenarios:
        for name in scenario.plugins:
            if not (plugins_root / name / ".claude-plugin" / "plugin.json").is_file():
                raise SmokeError(f"no plugin manifest for {name} under {plugins_root}")
        gate_question(plugins_root / scenario.skill)


def main(argv: Sequence[str] | None = None) -> int:
    labels = [scenario.label for scenario in SCENARIOS]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--max-usd-per-run", type=float, default=1.00)
    parser.add_argument(
        "--scenario", action="append", choices=labels, help="run only these; repeatable"
    )
    parser.add_argument(
        "--plugins-root",
        type=Path,
        default=REPO_ROOT / "plugins",
        help="plugins under test; point it at an exported HEAD to skip uncommitted edits",
    )
    args = parser.parse_args(argv)
    if args.max_usd_per_run <= 0:
        parser.error("--max-usd-per-run must be positive")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    scenarios = [s for s in SCENARIOS if not args.scenario or s.label in args.scenario]
    plugins_root = args.plugins_root.resolve()
    try:
        check_preconditions(plugins_root, scenarios)
    except SmokeError as error:
        log.error("%s", error)
        return 2
    workdir = Path(tempfile.mkdtemp(prefix="gate_smoke_"))
    runner = Runner(plugins_root, workdir, args.max_usd_per_run)
    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(scenarios))) as pool:
        outcomes = list(pool.map(runner.run, scenarios))
    all_passed = True
    for outcome in outcomes:
        all_passed &= print_checks(f"{outcome.label} (${outcome.cost_usd:.3f})", outcome.checks)
        for prompt in outcome.prompts:
            print(f"  note  permission prompt, approved: {prompt}")
    total = sum(outcome.cost_usd for outcome in outcomes)
    print(f"\n{'passed' if all_passed else 'FAILED'}; cost ${total:.3f}; transcripts in {workdir}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
