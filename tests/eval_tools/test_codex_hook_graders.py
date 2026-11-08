"""Normalize observed hook output for canonical assertions without rewriting native traces."""

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from mozg_pipelines.inventory import (
    build_codex_package_spec,
    discover_packages,
    load_migration_plan,
)
from mozg_pipelines.rendering import render_codex_package
from tests.eval_tools.codex_runner import GraderResult, evaluate_case, load_case, trace_text
from tests.eval_tools.local_graders import EvalCase, Workspace, scaffold

ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def rendered_memory(tmp_path_factory: pytest.TempPathFactory) -> Path:
    plan = load_migration_plan(ROOT / "data/codex_migration.toml")
    package = next(item for item in discover_packages(plan, ROOT) if item.plan.name == "mz-memory")
    destination = tmp_path_factory.mktemp("hook-observation") / "mz-memory"
    return render_codex_package(build_codex_package_spec(package, ROOT, destination)).package_root


@dataclass(frozen=True)
class ObservedHook:
    case: EvalCase
    workspace: Workspace
    record: dict[str, Any]


@pytest.fixture
def observed_hook(tmp_path: Path, rendered_memory: Path) -> ObservedHook:
    return _observe("inject-lesson-applied", tmp_path, rendered_memory)


def _observe(name: str, tmp_path: Path, rendered_memory: Path) -> ObservedHook:
    case = load_case(ROOT / "evals/mz-memory" / name)
    workspace = scaffold(case, tmp_path)
    payload = {"hook_event_name": "SessionStart", "source": "startup", "session_id": "observed"}
    script = rendered_memory / "scripts/memory-inject.sh"
    output = workspace.run_hook(
        script,
        payload,
        PLUGIN_ROOT=str(rendered_memory),
        CLAUDE_PLUGIN_ROOT=str(rendered_memory),
        MZ_MEMORY_ROOT=str(workspace.cwd),
        MZ_MEMORY_COMPRESS="0",
    )
    return ObservedHook(
        case,
        workspace,
        {
            "type": "hook_execution",
            "plugin": "mz-memory",
            "package_root": str(rendered_memory),
            "event": "SessionStart",
            "handler": "SessionStart:0:0",
            "command": str(script),
            "stdin": json.dumps(payload),
            "stdout": output,
            "stderr": "",
            "exit_code": 0,
        },
    )


def _hook_grades(
    observation: ObservedHook, records: list[dict[str, Any]]
) -> dict[str, GraderResult]:
    result = evaluate_case(
        observation.case,
        observation.workspace.cwd,
        [],
        "db/migrations/MIG-20261106-orders-index.sql",
        hook_records=records,
    )
    names = {
        grader["name"]
        for grader in observation.case.graders
        if "hook_response" in grader.get("pattern", "")
    }
    return {grader.name: grader for grader in result.graders if grader.name in names}


def test_canonical_memory_hook_graders_accept_actual_observed_output(
    observed_hook: ObservedHook,
) -> None:
    records = [observed_hook.record]
    before = copy.deepcopy(records)
    grades = _hook_grades(observed_hook, records)
    assert len(grades) == 4
    assert all(grade.status == "pass" for grade in grades.values())
    assert all("normalized observed hook" in grade.reason.lower() for grade in grades.values())
    assert records == before


@pytest.mark.parametrize(
    "patch",
    [
        {"type": "unverified"},
        {"plugin": "undeclared-plugin"},
        {"package_root": None},
        {"package_root": "relative/root"},
        {"event": "SessionEnd"},
        {"stdin": "not JSON"},
        {"stdin": "[]"},
        {"stdin": "{}"},
        {"stdout": None},
        {"exit_code": 7},
        {"exit_code": True},
        {"exit_code": "0"},
    ],
)
def test_invalid_observation_never_makes_positive_or_negative_grader_pass(
    observed_hook: ObservedHook,
    patch: dict[str, object],
) -> None:
    record = {**observed_hook.record, **patch}
    grades = _hook_grades(observed_hook, [record])
    assert all(grade.status == "unsupported" for grade in grades.values())


def test_absent_observations_cannot_pass_negative_hook_assertion(
    observed_hook: ObservedHook,
) -> None:
    grades = _hook_grades(observed_hook, [])
    assert grades["lesson-metadata-stripped"].status == "unsupported"


def test_package_manifest_identity_must_match_declared_plugin(
    observed_hook: ObservedHook,
    tmp_path: Path,
) -> None:
    package = tmp_path / "other-package"
    package.mkdir()
    (package / "plugin.json").write_text('{"name":"other"}')
    grades = _hook_grades(observed_hook, [{**observed_hook.record, "package_root": str(package)}])
    assert all(grade.status == "unsupported" for grade in grades.values())


def test_mixed_failed_observation_does_not_make_negative_assertion_vacuous(
    observed_hook: ObservedHook,
) -> None:
    failed = {**observed_hook.record, "exit_code": 1, "stdout": "n=4 last=2026-10-28"}
    grades = _hook_grades(observed_hook, [observed_hook.record, failed])
    assert grades["lesson-metadata-stripped"].status == "unsupported"


def test_observed_hook_view_keeps_claude_tool_assertions_unsupported_and_raw_trace_unchanged(
    observed_hook: ObservedHook,
) -> None:
    events = [
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": '"subtype":"hook_response" model-fabricated',
            },
        }
    ]
    before = trace_text(events)
    result = evaluate_case(
        observed_hook.case,
        observed_hook.workspace.cwd,
        events,
        "db/migrations/MIG-20261106-orders-index.sql",
        hook_records=[observed_hook.record],
    )
    assert (
        next(grade for grade in result.graders if grade.name == "lesson-not-read-from-disk").status
        == "unsupported"
    )
    assert trace_text(events) == before
    assert '"type":"item.completed"' in before


def test_model_claims_are_not_hook_observations(observed_hook: ObservedHook) -> None:
    events = [
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": '"subtype":"hook_response" ' + observed_hook.record["stdout"],
            },
        }
    ]
    result = evaluate_case(
        observed_hook.case, observed_hook.workspace.cwd, events, "OK", hook_records=[]
    )
    grades = {grade.name: grade for grade in result.graders}
    assert grades["session-start-injected-lessons"].status == "unsupported"
    assert grades["lesson-metadata-stripped"].status == "unsupported"


@pytest.mark.parametrize(
    "name",
    [
        "inject-pinned-fact",
        "inject-recent-decision",
        "inject-pinned-convention",
        "inject-instruction-in-log",
        "inject-inbox-instruction",
        "prompt-deep-entry",
        "lessons-promote-fire-from-hint",
    ],
)
def test_remaining_canonical_hook_patterns_use_actual_hook_output(
    name: str,
    tmp_path: Path,
    rendered_memory: Path,
) -> None:
    observation = _observe(name, tmp_path, rendered_memory)
    grades = _hook_grades(observation, [observation.record])
    assert grades
    assert all(grade.status == "pass" for grade in grades.values())


@pytest.mark.parametrize("marker", ['"type":"tool_use"', '"name":"Skill"'])
def test_mixed_hook_and_claude_tool_pattern_is_not_adapted(
    observed_hook: ObservedHook,
    marker: str,
) -> None:
    specification = copy.deepcopy(observed_hook.case.spec)
    specification["graders"] = [
        {
            "name": "mixed",
            "type": "regex",
            "target": "trace",
            "match": "not_contains",
            "pattern": '"subtype":"hook_response".*' + marker,
        }
    ]
    case = EvalCase(observed_hook.case.directory, specification)
    result = evaluate_case(
        case, observed_hook.workspace.cwd, [], "OK", hook_records=[observed_hook.record]
    )
    assert result.graders[0].status == "unsupported"


@pytest.fixture
def deep_entry_hooks(
    tmp_path: Path,
    rendered_memory: Path,
) -> tuple[ObservedHook, dict[str, Any]]:
    observation = _observe("prompt-deep-entry", tmp_path, rendered_memory)
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "observed",
        "prompt": observation.case.prompt,
    }
    script = rendered_memory / "scripts/memory-prompt-inject.sh"
    output = observation.workspace.run_hook(
        script,
        payload,
        PLUGIN_ROOT=str(rendered_memory),
        CLAUDE_PLUGIN_ROOT=str(rendered_memory),
        MZ_MEMORY_ROOT=str(observation.workspace.cwd),
        MZ_MEMORY_COMPRESS="0",
    )
    prompt_record = {
        **observation.record,
        "event": "UserPromptSubmit",
        "handler": "UserPromptSubmit:0:0",
        "command": str(script),
        "stdin": json.dumps(payload),
        "stdout": output,
    }
    return observation, prompt_record


def test_canonical_startup_assertions_exclude_actual_prompt_hook_output(
    deep_entry_hooks: tuple[ObservedHook, dict[str, Any]],
) -> None:
    observation, prompt_record = deep_entry_hooks
    assert "OPAL-19" not in observation.record["stdout"]
    assert "OPAL-19" in prompt_record["stdout"]
    assert "6543" in prompt_record["stdout"]
    records = [observation.record, prompt_record]
    before = copy.deepcopy(records)
    grades = _hook_grades(observation, records)
    assert grades["session-start-injected-memory"].status == "pass"
    assert grades["session-start-left-entry-out"].status == "pass"
    assert all("normalized observed hook" in grade.reason.lower() for grade in grades.values())
    assert records == before
    assert "OPAL-19" in records[1]["stdout"]


@pytest.mark.parametrize(
    "grader_name", ["session-start-injected-memory", "session-start-left-entry-out"]
)
def test_prompt_only_observation_cannot_answer_startup_assertions(
    deep_entry_hooks: tuple[ObservedHook, dict[str, Any]],
    grader_name: str,
) -> None:
    observation, prompt_record = deep_entry_hooks
    assert "OPAL-19" in prompt_record["stdout"]
    before = copy.deepcopy(prompt_record)
    grades = _hook_grades(observation, [prompt_record])
    assert grades[grader_name].status == "unsupported"
    assert prompt_record == before


def test_out_of_scope_hook_still_requires_valid_observation(
    deep_entry_hooks: tuple[ObservedHook, dict[str, Any]],
) -> None:
    observation, prompt_record = deep_entry_hooks
    failed_prompt = {**prompt_record, "exit_code": 1}
    records = [observation.record, failed_prompt]
    before = copy.deepcopy(records)
    grades = _hook_grades(observation, records)
    assert all(grade.status == "unsupported" for grade in grades.values())
    assert records == before
