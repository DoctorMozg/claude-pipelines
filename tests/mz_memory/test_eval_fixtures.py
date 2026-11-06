import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.eval_tools.local_graders import (
    EvalCase,
    Grader,
    Outcome,
    ToolCall,
    grade,
    hook_line,
    load_cases,
    regex_flags,
    scaffold,
)

from .memory_helpers import SCRIPTS

CASES = load_cases(SCRIPTS.parents[2] / "evals/mz-memory")
# Nudge cases grade what the model does with the nudge, so TestNudgeScenarios acts those runs out.
HOOK_CASES = sorted(n for n, c in CASES.items() if c.fixture is not None and "nudge" not in c.tags)
NUDGE_CASES = sorted(name for name, case in CASES.items() if "nudge" in case.tags)
# Graders no run without the model can pass, because they match a step only the model takes.
NEEDS_THE_MODEL = {
    ("lessons-promote-gate-no-answer", "lessons-promote-started"): "the skill's Write of state.md",
}
NUDGE = "/memory-note --lesson"
# Off so capture never starts the curator, which would call the real claude CLI.
NO_CURATOR = {"MZ_MEMORY_COMPRESS": "0"}

CORRECTION = "memory-note-lesson-correction"
TYPO = "memory-note-lesson-typo"
LESSON = (
    "WHEN adding a database migration → put it in db/migrations/ named MIG-<YYYYMMDD>-<slug>.sql "
    "— WHY the deploy runner applies only files whose names start with MIG-"
)
TYPO_LESSON = (
    "WHEN writing contributor names → spell Kowalski with an i — WHY the user corrected it"
)
NOTE_SCRIPT = SCRIPTS / "memory-note.sh"
MOVE = (
    "mv",
    "migrations/20261101_add_orders_index.sql",
    "db/migrations/MIG-20261101-add-orders-index.sql",
)


@dataclass(frozen=True)
class HookSession:
    outcome: Outcome
    start_context: str
    prompt_context: str


@dataclass(frozen=True)
class Step:
    call: ToolCall
    # What the call did to the workspace; empty when it changed nothing.
    command: tuple[str, ...] = ()


@dataclass(frozen=True)
class Scenario:
    case: str
    name: str
    steps: tuple[Step, ...]
    # Graders that must fail for the case to catch this run; empty for a good run, which passes all.
    caught_by: frozenset[str] = frozenset()
    reply: str = "Done."


def _save_lesson(text: str) -> Step:
    call = ToolCall("Bash", {"command": f"\"{NOTE_SCRIPT}\" --lesson '{text}'"})
    return Step(call, (str(NOTE_SCRIPT), "--lesson", text))


MOVE_CALL = ToolCall("Bash", {"command": " ".join(MOVE)})
NOTE_SKILL = ToolCall("Skill", {"skill": "mz-memory:memory-note", "args": f"--lesson {LESSON}"})
TYPO_FIX = Step(
    ToolCall(
        "Edit", {"file_path": "CONTRIBUTORS.md", "old_string": "Kowalsky", "new_string": "Kowalski"}
    ),
    ("sed", "-i", "s/Kowalsky/Kowalski/", "CONTRIBUTORS.md"),
)
SCENARIOS = [
    Scenario(CORRECTION, "good", (Step(MOVE_CALL, MOVE), Step(NOTE_SKILL), _save_lesson(LESSON))),
    Scenario(
        CORRECTION,
        "no-lesson",
        (Step(MOVE_CALL, MOVE),),
        frozenset({"lesson-script-run", "lesson-in-inbox"}),
    ),
    Scenario(
        CORRECTION,
        "gated",
        (Step(NOTE_SKILL),),
        frozenset({"approval-not-requested", "lesson-script-run"}),
        reply="Reply Approve to save this lesson, or Reject.",
    ),
    # The live run's failure: the sandbox mounted the workspace read-only, so the mv did nothing.
    Scenario(CORRECTION, "move-failed", (Step(MOVE_CALL),), frozenset({"old-file-moved"})),
    Scenario(TYPO, "good", (TYPO_FIX,)),
    Scenario(
        TYPO,
        "lesson-written",
        (TYPO_FIX, _save_lesson(TYPO_LESSON)),
        frozenset({"lesson-script-not-run", "inbox-empty"}),
    ),
]


def _answer_graders(case: EvalCase) -> list[Grader]:
    return [
        grader
        for grader in case.graders
        if grader["type"] == "regex"
        and str(grader["name"]).startswith("answer-")
        and grader.get("match", "contains") == "contains"
    ]


ANSWER_CASES = [name for name in HOOK_CASES if _answer_graders(CASES[name])]


def _hook_session(case: EvalCase, root: Path) -> HookSession:
    workspace = scaffold(case, root)

    def hook(script: Path, payload: Mapping[str, object]) -> str:
        return workspace.run_hook(script, payload, **NO_CURATOR)

    start = hook(
        SCRIPTS / "memory-inject.sh", {"source": "startup", "hook_event_name": "SessionStart"}
    )
    prompt = hook(
        SCRIPTS / "memory-prompt-inject.sh",
        {"prompt": case.prompt, "hook_event_name": "UserPromptSubmit"},
    )
    hook(SCRIPTS / "memory-capture.sh", {"reason": "other", "hook_event_name": "SessionEnd"})
    return HookSession(Outcome(workspace.cwd, (hook_line(start, "SessionStart"),)), start, prompt)


@pytest.fixture(scope="module")
def hook_session(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], HookSession]:
    """One fixture-and-hooks run per case, shared by the tests that grade it."""
    sessions: dict[str, HookSession] = {}

    def get(name: str) -> HookSession:
        if name not in sessions:
            sessions[name] = _hook_session(CASES[name], tmp_path_factory.mktemp(name))
        return sessions[name]

    return get


class TestHookCaseFixtures:
    @pytest.mark.parametrize("name", HOOK_CASES)
    def test_file_and_trace_graders_pass_on_the_hooks_alone(
        self, name: str, hook_session: Callable[[str], HookSession]
    ) -> None:
        verdicts = grade(CASES[name].graders, hook_session(name).outcome)
        failing = [
            str(v) for v in verdicts if not v.passed and (name, v.grader) not in NEEDS_THE_MODEL
        ]

        assert verdicts, f"{name} has no file or trace grader for a precheck to apply"
        detail = "\n".join(failing)
        assert not failing, f"{name}: the fixture and hooks fail these graders:\n{detail}"

    # An answer-* grader checks a fact the hooks deliver, so its pattern must be in a hook's output.
    @pytest.mark.parametrize("name", ANSWER_CASES)
    def test_answer_facts_reach_the_model_through_a_hook(
        self, name: str, hook_session: Callable[[str], HookSession]
    ) -> None:
        session = hook_session(name)
        unreached = [
            str(grader["name"])
            for grader in _answer_graders(CASES[name])
            if not any(
                re.search(str(grader["pattern"]), context, regex_flags(grader))
                for context in (session.start_context, session.prompt_context)
            )
        ]

        assert not unreached, f"{name}: no hook delivers the fact these graders expect: {unreached}"

    def test_every_exemption_names_a_grader_that_still_exists(self) -> None:
        stale = [
            f"{case}/{grader}"
            for case, grader in NEEDS_THE_MODEL
            if case not in CASES or grader not in {g["name"] for g in CASES[case].graders}
        ]

        assert not stale, f"NEEDS_THE_MODEL names graders that are gone: {stale}"


class TestNudgeScenarios:
    def test_every_nudge_case_has_a_good_and_a_bad_run(self) -> None:
        runs = {(s.case, not s.caught_by) for s in SCENARIOS}

        assert runs == {(case, good) for case in NUDGE_CASES for good in (True, False)}

    @pytest.mark.parametrize(
        "scenario", [pytest.param(s, id=f"{s.case}-{s.name}") for s in SCENARIOS]
    )
    def test_graders_tell_the_good_run_from_the_bad(
        self, scenario: Scenario, tmp_path: Path
    ) -> None:
        case = CASES[scenario.case]
        workspace = scaffold(case, tmp_path)
        context = workspace.run_hook(
            SCRIPTS / "memory-prompt-inject.sh", {"prompt": case.prompt}, **NO_CURATOR
        )
        assert NUDGE in context, f"{case.name}'s prompt no longer draws the lesson nudge"
        for step in scenario.steps:
            if step.command:
                workspace.run(step.command, **NO_CURATOR)
        outcome = Outcome(
            workspace.cwd, tool_calls=tuple(s.call for s in scenario.steps), reply=scenario.reply
        )

        verdicts = grade(case.graders, outcome)

        failed = {v.grader for v in verdicts if not v.passed}
        if scenario.caught_by:
            missed = sorted(scenario.caught_by - failed)
            assert not missed, f"{scenario.name} should fail {missed}; it failed {sorted(failed)}"
        else:
            assert not failed, "the good run fails:\n" + "\n".join(map(str, verdicts))
