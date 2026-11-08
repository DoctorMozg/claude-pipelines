"""Replay retained skill evidence without executing models or rewriting old runs."""

import copy
import hashlib
import json
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Never

import pytest
import yaml

from tests.eval_tools import codex_skill_replay


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }


@dataclass(frozen=True)
class ReplayFiles:
    index: Path
    run: Path
    trial: Path
    source: Path
    fixture: Path
    frozen: Path
    installed: Path
    output: Path

    def row(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = json.loads(self.index.read_text())
        return rows[0]

    def case(self) -> dict[str, Any]:
        case: dict[str, Any] = json.loads((self.trial / "case.json").read_text())
        return case

    def replace_case(self, case: dict[str, Any]) -> None:
        _json(self.trial / "case.json", case)

    def replace_row(self, row: dict[str, Any]) -> None:
        _json(self.index, [row])
        original = {key: value for key, value in row.items() if key != "evidence_run"}
        _json(self.trial / "result.json", original)

    def replay(self, output: Path | None = None) -> int:
        return codex_skill_replay.main(
            [
                "--index",
                str(self.index),
                "--output-dir",
                str(output or self.output),
            ]
        )


@pytest.fixture
def retained(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ReplayFiles:
    def forbid_process(*_args: object, **_kwargs: object) -> Never:
        raise AssertionError("Offline replay must not start subprocesses or paid model calls")

    monkeypatch.setattr(subprocess, "run", forbid_process)
    monkeypatch.setattr(subprocess, "Popen", forbid_process)
    run = tmp_path / "old-run"
    trial = run / "cases/example/use/run-1"
    workspace = trial / "home/cwd"
    workspace.mkdir(parents=True)
    frozen = run / "runtime/frozen/example"
    body = frozen / "skills/alpha/SKILL.md"
    body.parent.mkdir(parents=True)
    body.write_text(
        "---\nname: alpha\ndescription: Record a note.\n---\n"
        "Run `${PLUGIN_ROOT}/scripts/alpha.sh`.\n"
    )
    script = frozen / "scripts/alpha.sh"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\nprintf 'saved\\n'\n")
    script.chmod(0o755)
    _json(frozen / "plugin.json", {"name": "example", "version": "1.2.3"})
    installed = trial / "home/.codex/plugins/cache/market/example/1.2.3"
    shutil.copytree(frozen, installed)
    source = tmp_path / "repository/evals/example/use/case.yaml"
    source.parent.mkdir(parents=True)
    specification = {
        "name": "use",
        "plugins": ["../../../plugins/example"],
        "execution": {"prompt": "Record a note."},
        "graders": [
            {
                "name": "positive",
                "type": "tool_used",
                "tool": "Skill",
                "input_match": r'"skill"\s*:\s*"(?:[\w-]+:)?alpha"',
            },
            {"name": "negative", "type": "tool_used", "tool": "Skill", "min": 0, "max": 0},
        ],
    }
    source.write_text(yaml.safe_dump(specification))
    fixture = source.with_name("scaffold.sh")
    fixture.write_text("printf fixture >fixture.txt\n")
    case = {
        "source_path": str(source),
        "source_sha256": _sha(source),
        "input_hashes": {str(source): _sha(source), str(fixture): _sha(fixture)},
        "spec": specification,
        "plugins": ["example"],
        "prompt": "Record a note.",
        "execution_status": "completed",
        "error": "",
        "limitations": [],
    }
    _json(trial / "case.json", case)
    events: list[dict[str, Any]] = [{"type": "thread.started", "thread_id": "retained-root"}]
    for item_id, command, output in (
        ("load", f"cat {shlex.quote(str(installed / 'skills/alpha/SKILL.md'))}", body.read_text()),
        ("action", f"bash {shlex.quote(str(installed / 'scripts/alpha.sh'))}", "saved\n"),
    ):
        events.append(
            {
                "type": "item.completed",
                "item": {
                    "id": item_id,
                    "type": "command_execution",
                    "command": command,
                    "exit_code": 0,
                    "status": "completed",
                    "aggregated_output": output,
                },
            }
        )
    events.extend(
        [
            {"type": "item.completed", "item": {"type": "agent_message", "text": "Saved"}},
            {"type": "turn.completed", "usage": {}},
        ]
    )
    (trial / "stdout.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
    (trial / "trace.jsonl").symlink_to("stdout.jsonl")
    _json(trial / "initial-files.json", ["fixture.txt"])
    _json(trial / "created-files.json", [])
    provenance = {
        "packages": {
            "example": {
                "version": "1.2.3",
                "files": {
                    str(path.relative_to(frozen)): _sha(path)
                    for path in frozen.rglob("*")
                    if path.is_file()
                },
            }
        },
        "runtime_sources": {},
        "git_head": "historical",
        "git_status": "",
        "probe": {},
    }
    _json(run / "runtime/provenance.json", provenance)
    _json(run / "metadata.json", {"provenance": provenance, "completed": True})
    row = {
        "name": "use",
        "status": "unsupported",
        "graders": [
            {"name": name, "status": "unsupported", "reason": "No native Skill event", "hits": None}
            for name in ("positive", "negative")
        ],
        "limitations": ["historical limit"],
        "error": "",
        "trace": str(trial / "trace.jsonl"),
        "source_path": str(source),
        "case_key": "example/use",
        "run_index": 1,
        "execution_status": "completed",
        "artifacts": str(trial),
        "evidence_run": "old-run",
        "extra_original_field": "preserved",
    }
    index = tmp_path / "latest.json"
    result = ReplayFiles(index, run, trial, source, fixture, frozen, installed, tmp_path / "replay")
    result.replace_row(row)
    return result


def _replayed(retained: ReplayFiles) -> dict[str, Any]:
    rows: list[dict[str, Any]] = json.loads((retained.output / "results.json").read_text())
    assert len(rows) == 1
    return rows[0]


def _input_snapshot(retained: ReplayFiles) -> dict[str, bytes]:
    return {
        str(path): path.read_bytes() for path in (retained.source, retained.fixture, retained.index)
    }


def test_replay_preserves_strict_results_and_adds_separately_verified_evidence(
    retained: ReplayFiles,
) -> None:
    before = _snapshot(retained.run)
    inputs_before = _input_snapshot(retained)
    original = copy.deepcopy(retained.row())
    assert retained.replay() == 0
    row = _replayed(retained)
    for key, value in original.items():
        assert row[key] == value
    assert row["evidence_validation"]["status"] == "verified"
    assert row["evidence_validation"]["errors"] == []
    assert row["skill_evidence"]["observations"][0]["state"] == "workflow-observed"
    assert {item["grader_name"]: item["state"] for item in row["skill_assessments"]} == {
        "positive": "workflow-observed",
        "negative": "unknown",
    }
    sidecar = retained.output / "cases/example/use/run-1/skill-evidence.json"
    assert json.loads(sidecar.read_text()) == row["skill_evidence"]
    lines = (retained.output / "results.jsonl").read_text().splitlines()
    assert [json.loads(line) for line in lines] == [row]
    summary = json.loads((retained.output / "summary.json").read_text())
    assert summary["case_count"] == 1
    assert summary["original_case_statuses"] == {"unsupported": 1}
    assert summary["observation_states"]["workflow-observed"] == 1
    assert summary["assessment_states"]["workflow-observed"] == 1
    assert summary["assessment_states"]["unknown"] == 1
    assert summary["validation_statuses"] == {"verified": 1}
    assert summary["unassessed_skill_assertions"] == 0
    manifest = json.loads((retained.output / "manifest.json").read_text())
    assert _sha(retained.index) in json.dumps(manifest)
    assert _sha(Path(__file__).with_name("codex_skill_evidence.py")) in json.dumps(manifest)
    fingerprints = json.dumps(row["evidence_validation"]["fingerprints"])
    for path in (
        retained.source,
        retained.fixture,
        retained.trial / "case.json",
        retained.trial / "result.json",
        retained.trial / "trace.jsonl",
        retained.run / "runtime/provenance.json",
    ):
        assert _sha(path) in fingerprints
    assert _snapshot(retained.run) == before
    assert _input_snapshot(retained) == inputs_before


@pytest.mark.parametrize(
    "tamper",
    [
        "source",
        "fixture",
        "input-hash",
        "recorded-spec",
        "frozen-change",
        "frozen-missing",
        "frozen-extra",
        "provenance-copy",
        "malformed-trace",
        "trace-escape",
        "result-agreement",
    ],
)
def test_invalid_retained_inputs_are_reported_without_regrading_original_case(
    retained: ReplayFiles, tmp_path: Path, tamper: str
) -> None:
    if tamper in {"source", "fixture"}:
        (retained.source if tamper == "source" else retained.fixture).write_text("tampered\n")
    elif tamper in {"input-hash", "recorded-spec"}:
        case = retained.case()
        if tamper == "input-hash":
            case["input_hashes"][str(retained.fixture)] = "0" * 64
        else:
            case["spec"]["graders"][0]["input_match"] = "impostor"
        retained.replace_case(case)
    elif tamper.startswith("frozen"):
        path = retained.frozen / "scripts/alpha.sh"
        if tamper == "frozen-change":
            path.write_text("changed\n")
        elif tamper == "frozen-missing":
            path.unlink()
        else:
            path.with_name("extra.sh").write_text("extra\n")
    elif tamper == "provenance-copy":
        metadata = json.loads((retained.run / "metadata.json").read_text())
        metadata["provenance"]["git_head"] = "different"
        _json(retained.run / "metadata.json", metadata)
    elif tamper == "malformed-trace":
        (retained.trial / "stdout.jsonl").write_text("not json\n")
    elif tamper == "result-agreement":
        result = json.loads((retained.trial / "result.json").read_text())
        result["graders"][0]["status"] = "pass"
        _json(retained.trial / "result.json", result)
    else:
        trace = retained.trial / "trace.jsonl"
        outside = tmp_path / "outside.jsonl"
        outside.write_bytes(trace.read_bytes())
        trace.unlink()
        trace.symlink_to(outside)
    before = _snapshot(retained.run)
    inputs_before = _input_snapshot(retained)
    original = retained.row()
    assert retained.replay() == 1
    row = _replayed(retained)
    assert row["evidence_validation"]["status"] == "error"
    assert row["evidence_validation"]["errors"]
    assert row["status"] == original["status"]
    assert row["graders"] == original["graders"]
    assert row["skill_assessments"] == []
    summary = json.loads((retained.output / "summary.json").read_text())
    assert summary["validation_statuses"] == {"error": 1}
    assert summary["original_case_statuses"] == {"unsupported": 1}
    assert summary["unassessed_skill_assertions"] == 2
    assert _snapshot(retained.run) == before
    assert _input_snapshot(retained) == inputs_before


def test_historical_executor_drift_is_disclosed_and_does_not_reject_valid_evidence(
    retained: ReplayFiles, tmp_path: Path
) -> None:
    source = tmp_path / "historical-runtime.py"
    source.write_text("current source differs\n")
    provenance = json.loads((retained.run / "runtime/provenance.json").read_text())
    provenance["runtime_sources"] = {
        str(source): hashlib.sha256(b"historical source\n").hexdigest()
    }
    _json(retained.run / "runtime/provenance.json", provenance)
    _json(retained.run / "metadata.json", {"provenance": provenance, "completed": True})
    assert retained.replay() == 0
    row = _replayed(retained)
    assert row["evidence_validation"]["status"] == "verified"
    assert any("drift" in item.lower() for item in row["evidence_validation"]["limitations"])


@pytest.mark.parametrize("execution_status", ["timeout", "error"])
def test_partial_trace_keeps_loaded_evidence_without_skill_assessments(
    retained: ReplayFiles, execution_status: str
) -> None:
    case = retained.case()
    case.update(execution_status=execution_status, error="original execution unfinished")
    retained.replace_case(case)
    row = retained.row()
    row.update(status="error", execution_status=execution_status, error=case["error"], graders=[])
    retained.replace_row(row)
    lines = (retained.trial / "stdout.jsonl").read_text().splitlines()
    (retained.trial / "stdout.jsonl").write_text("\n".join(lines[:2]) + "\n")
    assert retained.replay() == 0
    replayed = _replayed(retained)
    assert replayed["status"] == "error"
    assert replayed["execution_status"] == execution_status
    assert replayed["skill_evidence"]["observations"][0]["state"] == "loaded"
    assert replayed["skill_assessments"] == []
    summary = json.loads((retained.output / "summary.json").read_text())
    assert summary["unassessed_skill_assertions"] == 2
    assert summary["validation_statuses"] == {"verified": 1}


def test_known_original_missing_dependency_and_cache_remain_reportable_unknown(
    retained: ReplayFiles,
) -> None:
    case = retained.case()
    case.update(execution_status="error", error="Unavailable Codex package dependencies: missing")
    case["plugins"].append("missing")
    case["spec"]["plugins"].append("../../../plugins/missing")
    retained.source.write_text(yaml.safe_dump(case["spec"]))
    case["source_sha256"] = _sha(retained.source)
    case["input_hashes"][str(retained.source)] = _sha(retained.source)
    retained.replace_case(case)
    row = retained.row()
    row.update(status="error", execution_status="error", error=case["error"], graders=[])
    retained.replace_row(row)
    shutil.rmtree(retained.trial / "home/.codex/plugins/cache")
    (retained.trial / "stdout.jsonl").write_text("")
    assert retained.replay() == 0
    replayed = _replayed(retained)
    assert replayed["error"] == case["error"]
    assert replayed["evidence_validation"]["status"] == "verified"
    assert replayed["skill_assessments"] == []
    assert not replayed["skill_evidence"]["observations"]
    assert "missing" in json.dumps(replayed["evidence_validation"]["limitations"]).lower()


@pytest.mark.parametrize("destination", ["existing", "run", "trial"])
def test_replay_refuses_existing_or_historical_output_directories(
    retained: ReplayFiles, destination: str
) -> None:
    output = {
        "existing": retained.output,
        "run": retained.run / "replay",
        "trial": retained.trial / "replay",
    }[destination]
    if destination == "existing":
        output.mkdir()
        (output / "keep.txt").write_text("keep")
    before = _snapshot(retained.run)
    assert retained.replay(output) == 2
    assert _snapshot(retained.run) == before
    if destination == "existing":
        assert (output / "keep.txt").read_text() == "keep"
    else:
        assert not output.exists()


def test_duplicate_case_selection_is_rejected_before_output_is_created(
    retained: ReplayFiles,
) -> None:
    _json(retained.index, [retained.row(), retained.row()])
    assert retained.replay() == 2
    assert not retained.output.exists()


@pytest.mark.parametrize("content", ["not-json", "{}", '["not-a-row"]', "[{}]"])
def test_malformed_indexes_fail_setup_without_touching_old_artifacts(
    retained: ReplayFiles, content: str
) -> None:
    retained.index.write_text(content)
    before = _snapshot(retained.run)
    assert retained.replay() == 2
    assert _snapshot(retained.run) == before
    assert not retained.output.exists()


@pytest.mark.parametrize("tamper", [False, True])
def test_existing_root_seal_is_verified_and_fingerprinted(
    retained: ReplayFiles, tamper: bool
) -> None:
    summary = retained.run / "summary.json"
    _json(summary, {"historical": True})
    seal = retained.run / "seal.json"
    _json(seal, {"summary.json": _sha(summary)})
    if tamper:
        summary.write_text("changed after sealing\n")
    before = _snapshot(retained.run)
    assert retained.replay() == (1 if tamper else 0)
    row = _replayed(retained)
    assert row["evidence_validation"]["status"] == ("error" if tamper else "verified")
    manifest = (retained.output / "manifest.json").read_text()
    assert _sha(seal) in manifest
    assert _snapshot(retained.run) == before


@pytest.mark.parametrize("problem", ["relative-escape", "absolute-escape", "symlink-escape"])
def test_frozen_inventory_paths_cannot_escape_the_package(
    retained: ReplayFiles, tmp_path: Path, problem: str
) -> None:
    outside = tmp_path / "outside-package"
    outside.write_bytes((retained.frozen / "scripts/alpha.sh").read_bytes())
    provenance = json.loads((retained.run / "runtime/provenance.json").read_text())
    if problem == "symlink-escape":
        script = retained.frozen / "scripts/alpha.sh"
        script.unlink()
        script.symlink_to(outside)
    else:
        reference = "../outside-package" if problem == "relative-escape" else str(outside)
        provenance["packages"]["example"]["files"][reference] = _sha(outside)
    _json(retained.run / "runtime/provenance.json", provenance)
    _json(retained.run / "metadata.json", {"provenance": provenance, "completed": True})
    assert retained.replay() == 1
    assert _replayed(retained)["evidence_validation"]["status"] == "error"


@pytest.mark.parametrize(
    "patch", [{"case_key": "../escaped"}, {"run_index": 0}, {"run_index": True}]
)
def test_unsafe_output_identity_is_a_setup_error(
    retained: ReplayFiles, patch: dict[str, object]
) -> None:
    row = retained.row()
    row.update(patch)
    _json(retained.index, [row])
    assert retained.replay() == 2
    assert not retained.output.exists()


@pytest.mark.parametrize("corruption", ["manifest", "body", "script", "missing-cache"])
def test_completed_case_requires_its_original_installed_package_bytes(
    retained: ReplayFiles, corruption: str
) -> None:
    if corruption == "missing-cache":
        shutil.rmtree(retained.trial / "home/.codex/plugins/cache")
    else:
        relative = {
            "manifest": "plugin.json",
            "body": "skills/alpha/SKILL.md",
            "script": "scripts/alpha.sh",
        }[corruption]
        (retained.installed / relative).write_text("lost or corrupted installed bytes\n")
    before = _snapshot(retained.run)
    inputs_before = _input_snapshot(retained)
    assert retained.replay() == 1
    row = _replayed(retained)
    assert row["evidence_validation"]["status"] == "error"
    assert row["evidence_validation"]["errors"]
    assert row["skill_assessments"] == []
    assert row["status"] == "unsupported"
    assert row["graders"] == retained.row()["graders"]
    assert _snapshot(retained.run) == before
    assert _input_snapshot(retained) == inputs_before


def _add_second_run(retained: ReplayFiles, tmp_path: Path) -> dict[str, Any]:
    run = tmp_path / "second-run"
    shutil.copytree(retained.run, run, symlinks=True)
    case_root = run / "cases/example/second"
    (run / "cases/example/use").rename(case_root)
    trial = case_root / "run-1"
    frozen = run / "runtime/frozen/example"
    installed = trial / retained.installed.relative_to(retained.trial)
    body = (frozen / "skills/alpha/SKILL.md").read_text() + "Different run instructions.\n"
    for package in (frozen, installed):
        (package / "skills/alpha/SKILL.md").write_text(body)
        (package / "scripts/alpha.sh").write_text("#!/bin/sh\nprintf 'second run\\n'\n")
    case = retained.case()
    case["spec"]["name"] = "second"
    case["spec"]["execution"]["prompt"] = "Use this distinct second-run workflow."
    source = retained.source.parent.parent / "second/case.yaml"
    source.parent.mkdir()
    source.write_text(yaml.safe_dump(case["spec"]))
    fixture = source.with_name("scaffold.sh")
    fixture.write_text("printf distinct-second-fixture >fixture.txt\n")
    case.update(
        source_path=str(source),
        source_sha256=_sha(source),
        input_hashes={str(source): _sha(source), str(fixture): _sha(fixture)},
        execution_status="timeout",
        error="second run timed out",
        prompt=case["spec"]["execution"]["prompt"],
    )
    _json(trial / "case.json", case)
    events = [json.loads(line) for line in (trial / "stdout.jsonl").read_text().splitlines()[:2]]
    events[0]["thread_id"] = "second-root"
    events[1]["item"].update(
        id="second-load",
        command=f"cat {shlex.quote(str(installed / 'skills/alpha/SKILL.md'))}",
        aggregated_output=body,
    )
    (trial / "stdout.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
    provenance = json.loads((run / "runtime/provenance.json").read_text())
    provenance["packages"]["example"]["files"] = {
        str(path.relative_to(frozen)): _sha(path) for path in frozen.rglob("*") if path.is_file()
    }
    _json(run / "runtime/provenance.json", provenance)
    _json(run / "metadata.json", {"provenance": provenance, "completed": True})
    row = retained.row()
    row.update(
        name="second",
        case_key="example/second",
        source_path=str(source),
        artifacts=str(trial),
        trace=str(trial / "trace.jsonl"),
        status="error",
        execution_status="timeout",
        error=case["error"],
        graders=[],
        evidence_run="second-run",
    )
    _json(
        trial / "result.json", {key: value for key, value in row.items() if key != "evidence_run"}
    )
    return row


def test_every_selected_case_uses_its_own_frozen_run_and_keeps_partial_results(
    retained: ReplayFiles, tmp_path: Path
) -> None:
    second = _add_second_run(retained, tmp_path)
    originals = [retained.row(), second]
    _json(retained.index, originals)
    before = {"first": _snapshot(retained.run), "second": _snapshot(tmp_path / "second-run")}
    inputs_before = _input_snapshot(retained)
    second_source = Path(second["source_path"])
    second_inputs = {
        path: path.read_bytes() for path in (second_source, second_source.with_name("scaffold.sh"))
    }
    assert retained.replay() == 0
    rows: list[dict[str, Any]] = json.loads((retained.output / "results.json").read_text())
    assert len(rows) == 2
    by_key = {row["case_key"]: row for row in rows}
    for original in originals:
        row = by_key[original["case_key"]]
        for key, value in original.items():
            assert row[key] == value
        assert row["evidence_validation"]["status"] == "verified"
        sidecar = retained.output / "cases" / row["case_key"] / "run-1/skill-evidence.json"
        assert json.loads(sidecar.read_text()) == row["skill_evidence"]
    assert (
        by_key["example/use"]["skill_evidence"]["observations"][0]["state"] == "workflow-observed"
    )
    partial = by_key["example/second"]
    assert partial["skill_evidence"]["observations"][0]["state"] == "loaded"
    load = partial["skill_evidence"]["observations"][0]["loads"][0]
    assert load["sha256"] == _sha(
        tmp_path / "second-run/runtime/frozen/example/skills/alpha/SKILL.md"
    )
    assert partial["skill_assessments"] == []
    summary = json.loads((retained.output / "summary.json").read_text())
    assert summary["case_count"] == 2
    assert summary["original_case_statuses"] == {"unsupported": 1, "error": 1}
    assert summary["observation_states"]["workflow-observed"] == 1
    assert summary["observation_states"]["loaded"] == 1
    assert summary["assessment_states"]["workflow-observed"] == 1
    assert summary["assessment_states"]["unknown"] == 1
    assert summary["validation_statuses"] == {"verified": 2}
    assert summary["unassessed_skill_assertions"] == 2
    assert _snapshot(retained.run) == before["first"]
    assert _snapshot(tmp_path / "second-run") == before["second"]
    assert _input_snapshot(retained) == inputs_before
    assert all(path.read_bytes() == contents for path, contents in second_inputs.items())


@pytest.mark.parametrize("failure", ["mkdir", "sidecar-write", "summary-write"])
@pytest.mark.parametrize("error_type", [PermissionError, OSError])
def test_output_io_failures_return_setup_error_and_leave_manifest_incomplete(
    retained: ReplayFiles,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    error_type: type[OSError],
) -> None:
    before = _snapshot(retained.run)
    inputs_before = _input_snapshot(retained)
    mkdir = Path.mkdir
    write_text = Path.write_text

    def failing_mkdir(
        path: Path, mode: int = 0o777, parents: bool = False, exist_ok: bool = False
    ) -> None:
        if failure == "mkdir" and path == retained.output:
            raise error_type("synthetic replay output mkdir failure")
        mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)

    def failing_write(
        path: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        target = retained.output / (
            "cases/example/use/run-1/skill-evidence.json"
            if failure == "sidecar-write"
            else "summary.json"
        )
        if failure != "mkdir" and path == target:
            raise error_type("synthetic replay output write failure")
        return write_text(path, data, encoding=encoding, errors=errors, newline=newline)

    monkeypatch.setattr(Path, "mkdir", failing_mkdir)
    monkeypatch.setattr(Path, "write_text", failing_write)
    assert retained.replay() == 2
    if failure == "mkdir":
        assert not retained.output.exists()
    else:
        manifest = json.loads((retained.output / "manifest.json").read_text())
        assert manifest["completed"] is False
    assert _snapshot(retained.run) == before
    assert _input_snapshot(retained) == inputs_before


@pytest.mark.parametrize(
    "violation", ["missing-turn", "missing-message", "failed-turn", "runtime-error", "item-error"]
)
def test_completed_execution_requires_a_complete_successful_native_trace(
    retained: ReplayFiles, violation: str
) -> None:
    stdout = retained.trial / "stdout.jsonl"
    events = [json.loads(line) for line in stdout.read_text().splitlines()]
    if violation == "missing-turn":
        events = [event for event in events if event["type"] != "turn.completed"]
    elif violation == "missing-message":
        events = [event for event in events if event.get("item", {}).get("type") != "agent_message"]
    else:
        events.append(
            {
                "failed-turn": {"type": "turn.failed", "error": {"message": "failed"}},
                "runtime-error": {"type": "error", "message": "failed"},
                "item-error": {
                    "type": "item.completed",
                    "item": {"type": "error", "message": "failed"},
                },
            }[violation]
        )
    stdout.write_text("".join(json.dumps(event) + "\n" for event in events))
    before = _snapshot(retained.run)
    assert retained.replay() == 1
    row = _replayed(retained)
    assert row["evidence_validation"]["status"] == "error"
    assert row["skill_assessments"] == []
    assert row["status"] == "unsupported"
    assert row["graders"] == retained.row()["graders"]
    assert _snapshot(retained.run) == before


@pytest.mark.parametrize(
    "violation",
    ["missing-both", "missing-entry", "missing-source-hash", "invalid-hash", "nonstring-hash"],
)
def test_source_integrity_requires_a_valid_hash_and_its_input_inventory_entry(
    retained: ReplayFiles, violation: str
) -> None:
    case = retained.case()
    if violation in {"missing-both", "missing-source-hash"}:
        case.pop("source_sha256")
    if violation in {"missing-both", "missing-entry"}:
        case["input_hashes"].pop(str(retained.source))
    if violation in {"invalid-hash", "nonstring-hash"}:
        value = "not-a-sha256" if violation == "invalid-hash" else False
        case["source_sha256"] = value
        case["input_hashes"][str(retained.source)] = value
    retained.replace_case(case)
    before = _snapshot(retained.run)
    assert retained.replay() == 1
    row = _replayed(retained)
    assert row["evidence_validation"]["status"] == "error"
    assert row["skill_assessments"] == []
    assert row["status"] == "unsupported"
    assert _snapshot(retained.run) == before


@pytest.mark.parametrize("field", ["skill_evidence", "skill_assessments", "evidence_validation"])
def test_existing_derived_fields_are_rejected_before_original_values_can_be_overwritten(
    retained: ReplayFiles, field: str
) -> None:
    row = retained.row()
    row[field] = [] if field == "skill_assessments" else {"original": "must be preserved"}
    retained.replace_row(row)
    before = _snapshot(retained.run)
    inputs_before = _input_snapshot(retained)
    assert retained.replay() == 2
    assert not retained.output.exists()
    assert _snapshot(retained.run) == before
    assert _input_snapshot(retained) == inputs_before


@pytest.mark.parametrize("modified", [False, True])
def test_known_hook_trust_notice_is_nonfatal_only_when_exact_and_turn_completed(
    retained: ReplayFiles, modified: bool
) -> None:
    notice = (
        "`--dangerously-bypass-hook-trust` is enabled. "
        "Enabled hooks may run without review for this invocation."
    )
    stdout = retained.trial / "stdout.jsonl"
    events = [json.loads(line) for line in stdout.read_text().splitlines()]
    events.insert(
        1,
        {
            "type": "item.completed",
            "item": {
                "id": "hook-trust-notice",
                "type": "error",
                "message": notice + (" unexpected details" if modified else ""),
            },
        },
    )
    stdout.write_text("".join(json.dumps(event) + "\n" for event in events))
    before = _snapshot(retained.run)
    assert retained.replay() == (1 if modified else 0)
    row = _replayed(retained)
    assert row["evidence_validation"]["status"] == ("error" if modified else "verified")
    assert row["status"] == "unsupported"
    if modified:
        assert row["skill_assessments"] == []
    else:
        assert row["skill_evidence"]["observations"][0]["state"] == "workflow-observed"
        assert {item["grader_name"]: item["state"] for item in row["skill_assessments"]} == {
            "positive": "workflow-observed",
            "negative": "unknown",
        }
    assert _snapshot(retained.run) == before
