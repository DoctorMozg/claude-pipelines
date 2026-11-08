"""Verify skill evidence against real frozen and installed package bytes."""

import copy
import hashlib
import json
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tests.eval_tools.codex_skill_evidence import (
    EvidenceContext,
    SkillCatalog,
    analyze_skill_evidence,
    assess_skill_assertion,
)


@dataclass(frozen=True)
class SkillFiles:
    frozen: Path
    cache: Path
    installed: Path
    workspace: Path

    @property
    def body(self) -> Path:
        return self.installed / "skills/alpha/SKILL.md"

    @property
    def script(self) -> Path:
        return self.installed / "scripts/alpha.sh"

    def catalog(self) -> SkillCatalog:
        return SkillCatalog.from_packages({"example": self.frozen})

    def context(self, events: list[dict[str, Any]]) -> EvidenceContext:
        return EvidenceContext(cache_root=self.cache, workspace=self.workspace, events=events)

    def load(self) -> dict[str, Any]:
        return _command(f"cat {shlex.quote(str(self.body))}", self.body.read_text(), "load")

    def action(self) -> dict[str, Any]:
        return _command(f"bash {shlex.quote(str(self.script))} --lesson 'literal note'", "", "act")


@pytest.fixture
def files(tmp_path: Path) -> SkillFiles:
    frozen = tmp_path / "frozen/example"
    body = frozen / "skills/alpha/SKILL.md"
    body.parent.mkdir(parents=True)
    body.write_text(
        "---\nname: alpha\ndescription: Record a note.\n---\n"
        "Run `${PLUGIN_ROOT}/scripts/alpha.sh` with the requested note.\n",
        encoding="utf-8",
    )
    script = frozen / "scripts/alpha.sh"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\nprintf 'saved\\n'\n", encoding="utf-8")
    script.chmod(0o755)
    (frozen / "plugin.json").write_text(
        json.dumps({"name": "example", "version": "1.2.3"}), encoding="utf-8"
    )
    cache = tmp_path / "installed cache"
    installed = cache / "market/example/1.2.3"
    shutil.copytree(frozen, installed)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return SkillFiles(frozen, cache, installed, workspace)


def _command(command: str, output: str = "", item_id: str = "command") -> dict[str, Any]:
    return {
        "type": "item.completed",
        "item": {
            "id": item_id,
            "type": "command_execution",
            "command": command,
            "aggregated_output": output,
            "exit_code": 0,
            "status": "completed",
        },
    }


def _grader(**updates: object) -> dict[str, Any]:
    return {
        "name": "alpha-fired",
        "type": "tool_used",
        "tool": "Skill",
        "input_match": "example:alpha",
        **updates,
    }


def _state(files: SkillFiles, events: list[dict[str, Any]]) -> str:
    evidence = analyze_skill_evidence(files.catalog(), files.context(events))
    return assess_skill_assertion(_grader(), evidence).state


def test_full_installed_body_read_records_verified_reference_and_scope(files: SkillFiles) -> None:
    event = files.load()
    events = [{"type": "thread.started", "thread_id": "root"}, event]
    evidence = analyze_skill_evidence(files.catalog(), files.context(events))
    assert evidence.scope == "root-cli-events"
    assert evidence.limitations
    (observation,) = evidence.observations
    assert (observation.plugin, observation.skill, observation.state) == (
        "example",
        "alpha",
        "loaded",
    )
    assert not observation.actions
    (reference,) = observation.loads
    assert reference.event_index == 2
    assert reference.item_id == "load"
    assert reference.path == str(files.body)
    assert reference.sha256 == hashlib.sha256(files.body.read_bytes()).hexdigest()
    assert reference.command == event["item"]["command"]
    assessment = assess_skill_assertion(_grader(), evidence)
    assert assessment.grader_name == "alpha-fired"
    assert assessment.skill_ids == ("example:alpha",)
    assert assessment.state == "loaded"
    assert assessment.reason


@pytest.mark.parametrize("shell", ["/bin/bash", "/usr/bin/zsh", "sh"])
def test_literal_shell_wrapper_and_quoted_cache_path_are_supported(
    files: SkillFiles, shell: str
) -> None:
    event = files.load()
    event["item"]["command"] = f"{shell} -lc {shlex.quote(event['item']['command'])}"
    assert _state(files, [event]) == "loaded"


@pytest.mark.parametrize(
    "patch",
    [
        {"exit_code": 1},
        {"exit_code": False},
        {"exit_code": True},
        {"exit_code": "0"},
        {"exit_code": None},
        {"status": "failed"},
        {"status": "in_progress"},
        {"type": "agent_message"},
        {"aggregated_output": None},
    ],
)
def test_failed_or_noncommand_completion_does_not_establish_loading(
    files: SkillFiles, patch: dict[str, object]
) -> None:
    event = files.load()
    event["item"].update(patch)
    assert _state(files, [event]) == "unknown"


@pytest.mark.parametrize("event_type", ["item.started", "item.updated", "turn.completed"])
def test_only_completed_items_establish_loading(files: SkillFiles, event_type: str) -> None:
    event = files.load()
    event["type"] = event_type
    assert _state(files, [event]) == "unknown"


@pytest.mark.parametrize("output_change", ["prefix", "suffix", "trim", "truncated"])
def test_body_output_must_be_byte_exact(files: SkillFiles, output_change: str) -> None:
    event = files.load()
    body = event["item"]["aggregated_output"]
    event["item"]["aggregated_output"] = {
        "prefix": "Files:\n" + body,
        "suffix": body + "\n",
        "trim": body.rstrip(),
        "truncated": body[:40] + "[output truncated]",
    }[output_change]
    assert _state(files, [event]) == "unknown"


def test_workspace_copy_claim_listing_and_script_read_do_not_establish_loading(
    files: SkillFiles,
) -> None:
    copied = files.workspace / "SKILL.md"
    copied.write_bytes(files.body.read_bytes())
    events = [
        _command(f"cat {shlex.quote(str(copied))}", copied.read_text()),
        _command(f"ls {shlex.quote(str(files.body))}", str(files.body)),
        _command(f"cat {shlex.quote(str(files.script))}", files.script.read_text()),
        {"type": "item.completed", "item": {"type": "agent_message", "text": "Used example:alpha"}},
    ]
    assert _state(files, events) == "unknown"


@pytest.mark.parametrize("identity", ["plugin", "version", "frontmatter", "body", "directory"])
def test_installed_identity_and_body_must_match_frozen_package(
    files: SkillFiles, identity: str
) -> None:
    event = files.load()
    if identity in {"plugin", "version"}:
        manifest = files.installed / "plugin.json"
        data = json.loads(manifest.read_text())
        data["name" if identity == "plugin" else "version"] = "different"
        manifest.write_text(json.dumps(data))
    elif identity == "directory":
        other = files.cache / "market/impostor/1.2.3"
        shutil.copytree(files.installed, other)
        event["item"]["command"] = f"cat {shlex.quote(str(other / 'skills/alpha/SKILL.md'))}"
    else:
        text = files.body.read_text().replace("name: alpha", "name: other")
        files.body.write_text(text if identity == "frontmatter" else text + "changed\n")
        event["item"]["aggregated_output"] = files.body.read_text()
    assert _state(files, [event]) == "unknown"


def test_catalog_freezes_bytes_before_later_package_changes(files: SkillFiles) -> None:
    catalog = files.catalog()
    (files.frozen / "skills/alpha/SKILL.md").write_text("changed after freezing\n")
    evidence = analyze_skill_evidence(catalog, files.context([files.load()]))
    assert assess_skill_assertion(_grader(), evidence).state == "loaded"


@pytest.mark.parametrize("target", ["body", "script", "package"])
def test_out_of_cache_symlinks_never_qualify(
    files: SkillFiles, tmp_path: Path, target: str
) -> None:
    outside = tmp_path / "outside"
    if target == "package":
        shutil.copytree(files.installed, outside)
        shutil.rmtree(files.installed)
        files.installed.symlink_to(outside, target_is_directory=True)
    else:
        original = files.body if target == "body" else files.script
        outside.write_bytes(original.read_bytes())
        original.unlink()
        original.symlink_to(outside)
    expected = "loaded" if target == "script" else "unknown"
    assert _state(files, [files.load(), files.action()]) == expected


def test_lexical_path_escape_is_rejected_even_if_it_resolves_to_installed_body(
    files: SkillFiles,
) -> None:
    event = files.load()
    escaped = files.installed / "skills/../skills/alpha/SKILL.md"
    event["item"]["command"] = f"cat {shlex.quote(str(escaped))}"
    assert _state(files, [event]) == "unknown"


@pytest.mark.parametrize("interpreter", ["", "bash ", "sh ", "python ", "python3 "])
def test_later_unique_packaged_script_invocation_establishes_workflow_evidence(
    files: SkillFiles, interpreter: str
) -> None:
    if interpreter.strip() in {"python", "python3"}:
        for root in (files.frozen, files.installed):
            (root / "scripts/alpha.sh").write_text("print('saved')\n")
    action = _command(
        f"{interpreter}{shlex.quote(str(files.script))} 'literal note'", "saved", "act"
    )
    evidence = analyze_skill_evidence(files.catalog(), files.context([files.load(), action]))
    (observation,) = evidence.observations
    assert observation.state == "workflow-observed"
    (reference,) = observation.actions
    assert reference.event_index == 2
    assert reference.item_id == "act"
    assert reference.path == str(files.script)
    assert reference.sha256 == hashlib.sha256(files.script.read_bytes()).hexdigest()
    assert reference.command == action["item"]["command"]
    assert assess_skill_assertion(_grader(), evidence).state == "workflow-observed"


def test_action_before_loading_does_not_retroactively_establish_workflow(files: SkillFiles) -> None:
    assert _state(files, [files.action(), files.load()]) == "loaded"
    assert _state(files, [files.action()]) == "unknown"


@pytest.mark.parametrize("problem", ["changed", "missing", "failed", "bool", "read-only"])
def test_unverified_script_actions_leave_only_loaded_evidence(
    files: SkillFiles, problem: str
) -> None:
    catalog = files.catalog()
    action = files.action()
    if problem == "changed":
        files.script.write_text("#!/bin/sh\nfalse\n")
    elif problem == "missing":
        files.script.unlink()
    elif problem == "failed":
        action["item"]["exit_code"] = 2
    elif problem == "bool":
        action["item"]["exit_code"] = False
    else:
        action["item"]["command"] = f"cat {shlex.quote(str(files.script))}"
    evidence = analyze_skill_evidence(catalog, files.context([files.load(), action]))
    assert assess_skill_assertion(_grader(), evidence).state == "loaded"


def test_shared_script_is_not_attributed_to_either_skill(files: SkillFiles) -> None:
    for root in (files.frozen, files.installed):
        body = root / "skills/beta/SKILL.md"
        body.parent.mkdir()
        body.write_text(
            "---\nname: beta\ndescription: Another workflow.\n---\n"
            "Run `${PLUGIN_ROOT}/scripts/alpha.sh`.\n"
        )
    assert _state(files, [files.load(), files.action()]) == "loaded"


def test_all_direct_references_are_scanned_and_generated_role_copies_are_not_owners(
    files: SkillFiles,
) -> None:
    for root in (files.frozen, files.installed):
        body = root / "skills/alpha/SKILL.md"
        text = body.read_text().replace(
            "Run `", "Example: `${PLUGIN_ROOT}/scripts/missing.sh`.\nRun `"
        )
        body.write_text(text)
        role = root / "skills/beta/references/roles/alpha.md"
        role.parent.mkdir(parents=True)
        role.write_text(text)
        (root / "skills/beta/SKILL.md").write_text(
            "---\nname: beta\ndescription: Unrelated workflow.\n---\nNo helper is needed.\n"
        )
    assert _state(files, [files.load(), files.action()]) == "workflow-observed"


@pytest.mark.parametrize(
    "template",
    [
        "{command}; true",
        "false && {command}",
        "true || {command}",
        "{command} | cat",
        "{command}\ntrue",
        "{command} > result.txt",
        "{command} < input.txt",
        "printf '%s' {path}",
        "echo {path}",
        "$(echo bash) {path}",
        "`echo bash` {path}",
        "bash -c {path}",
        "{command} # misleading comment",
        "{command} << EOF\nbody\nEOF",
        "{command} 'unterminated",
        "python -c 'print(1)' {path}",
    ],
)
def test_ambiguous_shell_forms_cannot_establish_load_or_action(
    files: SkillFiles, template: str
) -> None:
    load = files.load()
    load["item"]["command"] = template.format(
        command=load["item"]["command"], path=shlex.quote(str(files.body))
    )
    assert _state(files, [load]) == "unknown"
    action = files.action()
    action["item"]["command"] = template.format(
        command=action["item"]["command"], path=shlex.quote(str(files.script))
    )
    assert _state(files, [files.load(), action]) == "loaded"


@pytest.mark.parametrize(
    "constraints", [{"min": 0, "max": 0}, {"min": 2}, {"max": 1}, {"min": 1, "max": 1}]
)
def test_negative_and_count_constraints_remain_unknown_even_with_repeated_evidence(
    files: SkillFiles, constraints: dict[str, int]
) -> None:
    evidence = analyze_skill_evidence(
        files.catalog(), files.context([files.load(), files.action(), files.load(), files.action()])
    )
    assessment = assess_skill_assertion(_grader(**constraints), evidence)
    assert assessment.state == "unknown"
    assert assessment.reason


@pytest.mark.parametrize(
    "pattern", ["other:alpha", "example:beta", "--lesson", "literal note", "["]
)
def test_assertion_matching_uses_structured_identity_only(files: SkillFiles, pattern: str) -> None:
    evidence = analyze_skill_evidence(
        files.catalog(), files.context([files.load(), files.action()])
    )
    assert assess_skill_assertion(_grader(input_match=pattern), evidence).state == "unknown"


def test_absent_events_and_missing_cache_are_unknown_not_negative_proof(files: SkillFiles) -> None:
    catalog = files.catalog()
    shutil.rmtree(files.cache)
    evidence = analyze_skill_evidence(catalog, files.context([]))
    assert assess_skill_assertion(_grader(), evidence).state == "unknown"
    assert assess_skill_assertion(_grader(min=0, max=0), evidence).state == "unknown"
    empty = analyze_skill_evidence(SkillCatalog.from_packages({}), files.context([]))
    assert not empty.observations


def test_evidence_analysis_does_not_mutate_raw_cli_events(files: SkillFiles) -> None:
    events = [files.load(), files.action()]
    before = copy.deepcopy(events)
    analyze_skill_evidence(files.catalog(), files.context(events))
    assert events == before


@pytest.mark.parametrize("identity", ["name", "version", "frontmatter"])
def test_invalid_frozen_identity_is_rejected_or_unobservable(
    files: SkillFiles, identity: str
) -> None:
    if identity == "frontmatter":
        body = files.frozen / "skills/alpha/SKILL.md"
        body.write_text(body.read_text().replace("name: alpha", "name: impostor"))
    else:
        manifest = files.frozen / "plugin.json"
        data = json.loads(manifest.read_text())
        data[identity] = "impostor" if identity == "name" else ""
        manifest.write_text(json.dumps(data))
    try:
        catalog = files.catalog()
    except ValueError:
        return
    evidence = analyze_skill_evidence(catalog, files.context([files.load(), files.action()]))
    assert assess_skill_assertion(_grader(), evidence).state == "unknown"


def test_existing_but_unreferenced_script_does_not_identify_skill(files: SkillFiles) -> None:
    for root in (files.frozen, files.installed):
        (root / "scripts/unrelated.sh").write_bytes((root / "scripts/alpha.sh").read_bytes())
    action = _command(f"bash {shlex.quote(str(files.installed / 'scripts/unrelated.sh'))}")
    assert _state(files, [files.load(), action]) == "loaded"


@pytest.mark.parametrize("perform_action", [False, True])
def test_canonical_json_skill_pattern_matches_qualified_identity(
    files: SkillFiles, perform_action: bool
) -> None:
    events = [files.load(), *([files.action()] if perform_action else [])]
    evidence = analyze_skill_evidence(files.catalog(), files.context(events))
    pattern = r'"skill"\s*:\s*"(?:[\w-]+:)?alpha"'
    assessment = assess_skill_assertion(_grader(input_match=pattern), evidence)
    assert assessment.state == ("workflow-observed" if perform_action else "loaded")
    assert assessment.skill_ids == ("example:alpha",)
    mismatch = r'"skill"\s*:\s*"other:alpha"'
    assert assess_skill_assertion(_grader(input_match=mismatch), evidence).state == "unknown"


@pytest.mark.parametrize("interpreter", ["", "bash "])
def test_real_cli_zsh_wrapper_recognizes_both_load_and_script_action(
    files: SkillFiles, interpreter: str
) -> None:
    events = [files.load(), _command(f"{interpreter}{shlex.quote(str(files.script))}")]
    for event in events:
        event["item"]["command"] = f"/usr/bin/zsh -lc {shlex.quote(event['item']['command'])}"
    assert _state(files, events) == "workflow-observed"


def test_another_skills_unique_script_is_not_attributed_to_loaded_skill(files: SkillFiles) -> None:
    for root in (files.frozen, files.installed):
        body = root / "skills/beta/SKILL.md"
        body.parent.mkdir()
        body.write_text(
            "---\nname: beta\ndescription: Other workflow.\n---\n"
            "Run `${PLUGIN_ROOT}/scripts/beta.sh`.\n"
        )
        (root / "scripts/beta.sh").write_text("#!/bin/sh\ntrue\n")
    action = _command(f"bash {shlex.quote(str(files.installed / 'scripts/beta.sh'))}")
    assert _state(files, [files.load(), action]) == "loaded"


def test_unsafe_command_inside_supported_wrapper_does_not_establish_action(
    files: SkillFiles,
) -> None:
    action = files.action()
    inner = action["item"]["command"] + "; true"
    action["item"]["command"] = f"/usr/bin/zsh -lc {shlex.quote(inner)}"
    assert _state(files, [files.load(), action]) == "loaded"


@pytest.mark.parametrize("target", ["skills/alpha/SKILL.md", "scripts/alpha.sh"])
def test_frozen_symlink_escape_is_rejected_or_unobservable(
    files: SkillFiles, tmp_path: Path, target: str
) -> None:
    path = files.frozen / target
    outside = tmp_path / "outside-frozen"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    try:
        catalog = files.catalog()
    except ValueError:
        return
    evidence = analyze_skill_evidence(catalog, files.context([files.load(), files.action()]))
    expected = "unknown" if target.endswith("SKILL.md") else "loaded"
    assert assess_skill_assertion(_grader(), evidence).state == expected


@pytest.mark.parametrize("executable", ["./cat", "./bash", "./sh", "./python", "./python3"])
def test_workspace_executable_alias_is_not_treated_as_a_trusted_binary(
    files: SkillFiles, executable: str
) -> None:
    load = _command(f"{executable} {shlex.quote(str(files.body))}", files.body.read_text())
    assert _state(files, [load]) == "unknown"
    action = _command(f"{executable} {shlex.quote(str(files.script))}")
    assert _state(files, [files.load(), action]) == "loaded"


@pytest.mark.parametrize(
    "reference", ["scripts/./alpha.sh", "scripts//alpha.sh", "scripts/../scripts/alpha.sh"]
)
def test_script_aliases_are_shared_ownership_not_distinct_actions(
    files: SkillFiles, reference: str
) -> None:
    for root in (files.frozen, files.installed):
        body = root / "skills/beta/SKILL.md"
        body.parent.mkdir()
        body.write_text(
            "---\nname: beta\ndescription: Another user of the helper.\n---\n"
            f"Run `${{PLUGIN_ROOT}}/{reference}`.\n"
        )
    assert _state(files, [files.load(), files.action()]) == "loaded"
