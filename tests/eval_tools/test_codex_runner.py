"""Codex evals consume the existing Claude case files without copying them."""

import json
import tomllib
from pathlib import Path

import pytest

from tests.eval_tools.codex_runner import codex_prompt, evaluate_case, load_case, trace_text
from tests.eval_tools.codex_skill_evidence import EvidenceReference, SkillEvidence, SkillObservation


def test_load_case_reads_canonical_yaml(tmp_path: Path) -> None:
    case_dir = tmp_path / "example"
    case_dir.mkdir()
    (case_dir / "case.yaml").write_text(
        "name: example\nexecution:\n  prompt: Check this.\ngraders:\n"
        "  - name: answer\n    type: regex\n    pattern: OK\n",
        encoding="utf-8",
    )

    case = load_case(case_dir)

    assert case.name == "example"
    assert case.prompt == "Check this."
    assert case.directory == case_dir


def test_codex_trace_is_not_relabelled_as_claude_trace() -> None:
    events = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": "OK"}},
        {"type": "turn.completed", "usage": {"input_tokens": 10}},
    ]

    trace = trace_text(events)

    assert '"type":"item.completed"' in trace
    assert "hook_response" not in trace


def test_evaluate_case_reports_supported_and_unsupported_graders(tmp_path: Path) -> None:
    case_dir = tmp_path / "example"
    case_dir.mkdir()
    (case_dir / "case.yaml").write_text(
        "name: example\nexecution:\n  prompt: Check this.\ngraders:\n"
        "  - name: answer\n    type: regex\n    pattern: OK\n"
        "  - name: output-file\n    type: file_exists\n    path: report.md\n"
        "  - name: claude-hook\n    type: regex\n    target: trace\n"
        "    pattern: hook_response\n"
        "  - name: claude-skill\n    type: tool_used\n"
        "    tool: Skill\n    input_match: build\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "report.md").write_text("found", encoding="utf-8")

    result = evaluate_case(
        load_case(case_dir),
        workspace,
        [{"type": "item.completed", "item": {"type": "agent_message", "text": "OK"}}],
        "OK",
        created_files=frozenset({"report.md"}),
    )

    assert [(item.name, item.status) for item in result.graders] == [
        ("answer", "pass"),
        ("output-file", "pass"),
        ("claude-hook", "unsupported"),
        ("claude-skill", "unsupported"),
    ]
    assert result.status == "unsupported"


def test_missing_file_does_not_satisfy_negative_content_check(tmp_path: Path) -> None:
    case_dir = tmp_path / "example"
    case_dir.mkdir()
    (case_dir / "case.yaml").write_text(
        "name: example\nexecution:\n  prompt: Check.\ngraders:\n"
        "  - name: missing\n    type: regex\n    pattern: bad\n"
        "    match: not_contains\n    target: {source: file, path: result.txt}\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = evaluate_case(load_case(case_dir), workspace, [], "OK")

    assert result.graders[0].status == "unsupported"
    assert "missing" in result.graders[0].reason


def test_codex_command_does_not_inject_prompt_into_shell() -> None:
    from tests.eval_tools.codex_runner import codex_command

    command = codex_command(Path("/tmp/work"), "gpt-test", 3)

    overrides: dict[str, object] = {}
    for index, argument in enumerate(command[:-1]):
        if argument in ("-c", "--config"):
            overrides.update(tomllib.loads(command[index + 1]))
    assert overrides["project_doc_fallback_filenames"] == ["CLAUDE.md"]

    assert command[:2] == ["codex", "exec"]
    assert "--json" in command
    assert "--ephemeral" in command
    assert command[-1] == "-"
    assert "$(touch /tmp/pwned)" not in json.dumps(command)


def test_codex_prompt_translates_claude_direct_skill_invocation() -> None:
    assert codex_prompt("/mz-dev-pipe:ask where is retry set?") == (
        "Use the $ask skill from mz-dev-pipe.\n"
        "The invocation arguments below are supplied; use them wherever the skill refers "
        "to arguments or the user's request.\n"
        "<skill_arguments>\nwhere is retry set?\n</skill_arguments>"
    )
    assert codex_prompt("Find the retry policy") == "Find the retry policy"


def test_direct_skill_arguments_preserve_current_directory() -> None:
    prompt = codex_prompt("/mz-knowledge:vault-health .")

    assert "<skill_arguments>\n.\n</skill_arguments>" in prompt
    assert "arguments below are supplied" in prompt


def test_canonical_claude_trace_with_regex_whitespace_is_unsupported(tmp_path: Path) -> None:
    repository = Path(__file__).parents[2]
    case = load_case(repository / "evals/mz-base/construct-skill-gate-plugin-choice")

    result = evaluate_case(case, tmp_path, [], "team-core or team-extra?")

    blocked = next(item for item in result.graders if item.name == "blocked-recorded")
    assert blocked.status == "unsupported"


def test_file_exists_excludes_fixture_files(tmp_path: Path) -> None:
    repository = Path(__file__).parents[2]
    case = load_case(repository / "evals/mz-biz-outreach/outreach-update-card-args-no-action")
    active = tmp_path / ".mz/outreach/active"
    active.mkdir(parents=True)
    (active / "seed.md").write_text("Fixture card", encoding="utf-8")

    result = evaluate_case(
        case, tmp_path, [], "What action should I log?", created_files=frozenset()
    )

    assert next(g for g in result.graders if g.name == "no-new-active-card").status == "pass"


def test_files_target_uses_only_created_paths(tmp_path: Path) -> None:
    repository = Path(__file__).parents[2]
    case = load_case(repository / "evals/mz-knowledge/vault-refactor-args-no-separator")
    grader_name = next(g["name"] for g in case.graders if g.get("target") == "files")

    unchanged = evaluate_case(case, tmp_path, [], "", created_files=frozenset())
    written = evaluate_case(case, tmp_path, [], "", created_files=frozenset({"new.md"}))

    assert next(g for g in unchanged.graders if g.name == grader_name).status == "pass"
    assert next(g for g in written.graders if g.name == grader_name).status == "fail"


def test_bash_input_match_does_not_match_command_output(tmp_path: Path) -> None:
    repository = Path(__file__).parents[2]
    case = load_case(repository / "evals/mz-memory/memory-note-gate-no-answer")
    event = {
        "type": "item.completed",
        "item": {
            "type": "command_execution",
            "command": "cat skills/memory-note/SKILL.md",
            "aggregated_output": "Call scripts/memory-note.sh only after approval.",
        },
    }

    result = evaluate_case(case, tmp_path, [event], "Approve?")

    assert next(g for g in result.graders if g.name == "write-script-not-run").status == "pass"


def test_negative_claude_event_assertions_remain_unsupported(tmp_path: Path) -> None:
    directory = tmp_path / "case"
    directory.mkdir()
    (directory / "case.yaml").write_text(
        "name: no-false-pass\nexecution:\n  prompt: Check.\ngraders:\n"
        "  - name: no-hook-response\n    type: regex\n    target: trace\n"
        "    pattern: hook_response\n    match: not_contains\n"
        "  - name: no-skill\n    type: tool_used\n    tool: Skill\n    min: 0\n    max: 0\n"
    )
    result = evaluate_case(load_case(directory), tmp_path, [], "OK")
    assert result.status == "unsupported"
    assert [grader.status for grader in result.graders] == ["unsupported", "unsupported"]


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
def test_explicit_claude_file_tool_request_maps_to_apply_patch_without_rewriting_payload(
    tool: str,
) -> None:
    payload = (
        '---\ntags: "not-a-list"\n---\n'
        'Keep the words "Write", "Edit", and "MultiEdit".\n'
        "Literal shell text: $(printf untouched) and `echo untouched`.\n"
    )
    prompt = (
        f"Use the {tool} tool to save exactly this content in note.md:\n"
        f"<content>\n{payload}</content>"
    )

    adapted = codex_prompt(prompt)

    assert adapted != prompt
    assert adapted.endswith(prompt)
    assert adapted.count(prompt) == 1
    assert "apply_patch" in adapted[: -len(prompt)]
    assert payload in adapted


@pytest.mark.parametrize("tool", ["Read", "Glob", "Grep"])
def test_explicit_claude_read_or_search_tool_request_gets_native_guidance(tool: str) -> None:
    prompt = f'Use the {tool} tool to inspect the project for the exact text "retry policy".'

    adapted = codex_prompt(prompt)

    assert adapted != prompt
    assert adapted.endswith(prompt)
    guidance = adapted[: -len(prompt)].lower()
    assert "native" in guidance or "shell" in guidance


@pytest.mark.parametrize(
    "prompt",
    [
        "Write a file describing the retry policy.",
        "Edit the retry policy documentation.",
        "Read the retry policy documentation.",
        "Find the retry policy with grep.",
        "Use the write tool mentioned in this document.",
    ],
)
def test_neutral_and_generic_english_prompts_are_not_adapted(prompt: str) -> None:
    assert codex_prompt(prompt) == prompt


def test_quoted_tool_names_are_preserved_verbatim() -> None:
    prompt = 'Copy this exact sentence into a note: "The Write tool differs from the Edit tool."'

    adapted = codex_prompt(prompt)

    assert adapted.endswith(prompt)
    assert adapted.count(prompt) == 1


def test_tool_guidance_preserves_direct_skill_translation_and_quoted_arguments() -> None:
    arguments = 'Use the Write tool to save the exact text "Read tool and Edit tool".'
    prompt = f"/mz-dev-pipe:ask {arguments}"

    adapted = codex_prompt(prompt)

    assert "apply_patch" in adapted
    assert "Use the $ask skill from mz-dev-pipe." in adapted
    assert adapted.endswith(f"<skill_arguments>\n{arguments}\n</skill_arguments>")
    assert "/mz-dev-pipe:ask" not in adapted


@pytest.fixture
def observed_skill(tmp_path: Path) -> SkillEvidence:
    body = EvidenceReference(1, "load", str(tmp_path / "SKILL.md"), "a" * 64, "cat SKILL.md")
    action = EvidenceReference(2, "action", str(tmp_path / "helper.sh"), "b" * 64, "bash helper.sh")
    observation = SkillObservation("example", "alpha", "workflow-observed", (body,), (action,))
    return SkillEvidence((observation,), "root-cli-events", ("Native activation remains unknown",))


def test_portable_skill_evidence_is_separate_from_legacy_grades_and_counts(
    tmp_path: Path, observed_skill: SkillEvidence
) -> None:
    directory = tmp_path / "case"
    directory.mkdir()
    (directory / "case.yaml").write_text(
        "name: portable-evidence\nexecution:\n  prompt: Check.\ngraders:\n"
        "  - name: positive\n    type: tool_used\n    tool: Skill\n"
        "    input_match: example:alpha\n"
        "  - name: negative\n    type: tool_used\n    tool: Skill\n    min: 0\n    max: 0\n"
        "    input_match: example:alpha\n"
        "  - name: counted\n    type: tool_used\n    tool: Skill\n    min: 2\n"
        "    input_match: example:alpha\n"
    )
    case = load_case(directory)
    baseline = evaluate_case(case, tmp_path, [], "OK")
    result = evaluate_case(case, tmp_path, [], "OK", skill_evidence=observed_skill)

    assert result.status == baseline.status == "unsupported"
    assert [(grade.status, grade.hits) for grade in result.graders] == [
        (grade.status, grade.hits) for grade in baseline.graders
    ]
    assert all(grade.status == "unsupported" for grade in result.graders)
    assert result.skill_evidence is observed_skill
    assert {item.grader_name: item.state for item in result.skill_assessments} == {
        "positive": "workflow-observed",
        "negative": "unknown",
        "counted": "unknown",
    }


def test_runner_limitations_describe_current_runner_instead_of_all_codex(tmp_path: Path) -> None:
    directory = tmp_path / "case"
    directory.mkdir()
    (directory / "case.yaml").write_text(
        "name: limits\nexecution:\n  prompt: Check.\n  max_turns: 2\n"
        "  allowed_tools: [Bash]\ngraders:\n"
        "  - name: answer\n    type: regex\n    pattern: OK\n"
    )
    result = evaluate_case(load_case(directory), tmp_path, [], "OK")
    assert result.skill_evidence is None
    assert result.skill_assessments == ()
    assert any("allowed_tools" in item for item in result.limitations)
    assert any("max_turns" in item for item in result.limitations)
    assert all("runner" in item.lower() for item in result.limitations)
    assert all("Codex CLI cannot enforce" not in item for item in result.limitations)
