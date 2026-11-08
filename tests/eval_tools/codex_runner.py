"""Run the canonical plugin eval cases against rendered Codex packages."""

import argparse
import fnmatch
import hashlib
import json
import logging
import re
from collections.abc import Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml

from tests.eval_tools.codex_runtime import (
    CaseRequest,
    FrozenCase,
    PreparedRuntime,
    RuntimeConfig,
    execute_case,
    prepare_runtime,
    write_json,
)
from tests.eval_tools.codex_runtime import codex_command as codex_command
from tests.eval_tools.codex_runtime import workspace_files as workspace_files
from tests.eval_tools.codex_skill_evidence import (
    SkillAssessment,
    SkillEvidence,
    assess_skill_assertion,
)
from tests.eval_tools.local_graders import EvalCase, hook_line, regex_flags

ROOT = Path(__file__).resolve().parents[2]
LOGGER = logging.getLogger(__name__)
Status = Literal["pass", "fail", "unsupported"]
CLAUDE_TRACE_MARKERS = (
    "hook_response",
    "hook_started",
    "tool_result",
    "tool_use",
    "parent_tool_use_id",
    '"role"',
    '"type":"text"',
    '"name"',
    '"input"',
    "File created successfully at:",
)


@dataclass(frozen=True)
class GraderResult:
    name: str
    status: Status
    reason: str = ""
    hits: int | None = None


@dataclass(frozen=True)
class CaseResult:
    name: str
    status: Literal["pass", "fail", "unsupported", "error"]
    graders: tuple[GraderResult, ...]
    limitations: tuple[str, ...] = ()
    error: str = ""
    trace: str = ""
    source_path: str = ""
    case_key: str = ""
    run_index: int = 1
    execution_status: str = "completed"
    artifacts: str = ""
    skill_evidence: SkillEvidence | None = None
    skill_assessments: tuple[SkillAssessment, ...] = ()


@dataclass(frozen=True)
class _GradingContext:
    workspace: Path
    trace: str
    message: str
    created_files: frozenset[str] | None
    hook_responses: str | None


def _normalized_hook_responses(
    case: EvalCase,
    records: Sequence[Mapping[str, Any]] | None,
) -> str | None:
    if not records:
        return None
    plugins = {Path(str(plugin)).name for plugin in case.spec.get("plugins", ()) or ()}
    lines: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            return None
        plugin, root = record.get("plugin"), record.get("package_root")
        event, stdout = record.get("event"), record.get("stdout")
        if (
            record.get("type") != "hook_execution"
            or not isinstance(plugin, str)
            or plugin not in plugins
            or not isinstance(root, str)
            or not root
            or not Path(root).is_absolute()
            or not isinstance(event, str)
            or not event
            or not isinstance(stdout, str)
            or type(record.get("exit_code")) is not int
            or record["exit_code"] != 0
            or not isinstance(record.get("stdin"), str)
        ):
            return None
        try:
            payload: object = json.loads(record["stdin"])
            manifest: object = json.loads((Path(root) / "plugin.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if (
            not isinstance(payload, dict)
            or payload.get("hook_event_name") != event
            or not isinstance(manifest, dict)
            or manifest.get("name") != plugin
        ):
            return None
        # Claude eval traces expose startup responses; prompt-time I/O stays in the raw log.
        if event == "SessionStart" and stdout.strip():
            lines.append(hook_line(stdout, event))
    return "\n".join(lines) if lines else None


def load_case(directory: Path) -> EvalCase:
    path = directory / "case.yaml"
    try:
        source = path.read_bytes()
        spec = yaml.safe_load(source)
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"Cannot load eval case {path}: {error}") from error
    if not isinstance(spec, dict) or not isinstance(spec.get("execution"), dict):
        raise ValueError(f"Invalid eval case: {path}")
    case = EvalCase(directory, spec)
    inputs = {str(path.resolve()): hashlib.sha256(source).hexdigest()}
    if case.fixture is not None:
        suite = next(
            (parent for parent in directory.parents if parent.parent.name == "evals"), directory
        )
        paths = [case.fixture, *(suite / "_lib").rglob("*")]
        for fixture_input in paths:
            if fixture_input.is_file():
                inputs[str(fixture_input.resolve())] = hashlib.sha256(
                    fixture_input.read_bytes()
                ).hexdigest()
    return FrozenCase(directory, spec, hashlib.sha256(source).hexdigest(), inputs)


def codex_prompt(prompt: str) -> str:
    tool_guidance = ""
    if re.search(r"\b(?:Write|Edit|MultiEdit|Read|Glob|Grep) tool\b", prompt):
        LOGGER.debug("Adapting explicit Claude file-tool terminology for Codex")
        tool_guidance = (
            "Codex tool mapping: when the request names the Claude Write, Edit, or MultiEdit "
            "tool, use apply_patch to create or edit files. For Read, Glob, and Grep, use "
            "available native file-reading/search tools or shell commands. Preserve requested "
            "file content exactly.\n\n"
        )
    direct = re.match(r"^/([a-z0-9-]+):([a-z0-9-]+)(?:\s+|$)", prompt)
    if direct is None:
        return tool_guidance + prompt
    plugin, skill = direct.group(1, 2)
    remainder = prompt[direct.end() :]
    return tool_guidance + (
        f"Use the ${skill} skill from {plugin}.\n"
        "The invocation arguments below are supplied; use them wherever the skill refers "
        "to arguments or the user's request.\n"
        f"<skill_arguments>\n{remainder}\n</skill_arguments>"
    )


def trace_text(events: list[dict[str, Any]]) -> str:
    return "\n".join(
        json.dumps(event, separators=(",", ":"), ensure_ascii=False) for event in events
    )


def _regex_result(
    grader: Mapping[str, Any],
    context: _GradingContext,
) -> GraderResult:
    name = str(grader["name"])
    target = grader.get("target", "last_message")
    pattern = str(grader["pattern"])
    reason = ""
    if isinstance(target, Mapping):
        if target.get("source") != "file":
            return GraderResult(name, "unsupported", "unknown regex target")
        path = (context.workspace / str(target.get("path", ""))).resolve()
        if not path.is_relative_to(context.workspace.resolve()):
            return GraderResult(name, "unsupported", "file target escapes eval workspace")
        if not path.is_file():
            return GraderResult(name, "unsupported", "target file missing")
        text = path.read_text(encoding="utf-8")
    elif target == "trace":
        wire_pattern = pattern.replace(r"\s*", "").replace(r"\s+", "").replace("\\", "")
        markers = {marker for marker in CLAUDE_TRACE_MARKERS if marker in wire_pattern}
        if markers and markers != {"hook_response"}:
            return GraderResult(name, "unsupported", "Claude-specific trace pattern")
        if markers:
            if context.hook_responses is None:
                return GraderResult(
                    name, "unsupported", "Verified hook response observations unavailable"
                )
            text = context.hook_responses
            reason = "Normalized observed hook I/O as hook_response"
        else:
            text = context.trace
    elif target == "last_message":
        text = context.message
    elif target == "files":
        if context.created_files is None:
            return GraderResult(name, "unsupported", "created-file baseline unavailable")
        text = "\n".join(sorted(context.created_files))
    else:
        return GraderResult(name, "unsupported", f"unknown regex target: {target}")

    hits = len(re.findall(pattern, text, regex_flags(grader)))
    match = str(grader.get("match", "contains"))
    if match == "contains":
        passed = hits > 0
    elif match == "not_contains":
        passed = hits == 0
    elif match.startswith("count:") and match[6:].isdigit():
        passed = hits == int(match[6:])
    else:
        return GraderResult(name, "unsupported", f"unknown match mode: {match}")
    return GraderResult(name, "pass" if passed else "fail", reason=reason, hits=hits)


def _tool_result(grader: Mapping[str, Any], events: list[dict[str, Any]]) -> GraderResult:
    name = str(grader["name"])
    # Codex emits command_execution items. Claude's Skill, Agent, and file tools have
    # no one-to-one event or argument shape, so those assertions cannot be inferred.
    if grader.get("tool") != "Bash":
        return GraderResult(name, "unsupported", "Claude tool has no equivalent Codex event")
    calls = [
        event["item"]
        for event in events
        if event.get("type") == "item.completed"
        and isinstance(event.get("item"), dict)
        and event["item"].get("type") == "command_execution"
    ]
    input_match = grader.get("input_match")
    if input_match is not None:
        pattern = re.compile(str(input_match))
        calls = [
            call
            for call in calls
            if pattern.search(
                json.dumps(
                    {"command": call.get("command", "")}, separators=(",", ":"), ensure_ascii=False
                )
            )
        ]
    hits = len(calls)
    low = int(grader.get("min", 1))
    high = grader.get("max")
    passed = hits >= low and (high is None or hits <= int(high))
    return GraderResult(name, "pass" if passed else "fail", hits=hits)


def evaluate_case(
    case: EvalCase,
    workspace: Path,
    events: list[dict[str, Any]],
    last_message: str,
    *,
    created_files: frozenset[str] | None = None,
    hook_records: Sequence[Mapping[str, Any]] | None = None,
    skill_evidence: SkillEvidence | None = None,
) -> CaseResult:
    context = _GradingContext(
        workspace,
        trace_text(events),
        last_message,
        created_files,
        _normalized_hook_responses(case, hook_records),
    )
    results: list[GraderResult] = []
    assessments: list[SkillAssessment] = []
    for grader in case.graders:
        name = str(grader.get("name", "unnamed"))
        kind = grader.get("type")
        if kind == "regex":
            results.append(_regex_result(grader, context))
        elif kind == "tool_used":
            result = _tool_result(grader, events)
            if grader.get("tool") == "Skill" and skill_evidence is not None:
                assessment = assess_skill_assertion(grader, skill_evidence)
                assessments.append(assessment)
                result = replace(
                    result,
                    reason=f"{result.reason}; portable evidence: {assessment.state}. "
                    + assessment.reason,
                )
            results.append(result)
        elif kind == "file_exists":
            if created_files is None:
                results.append(
                    GraderResult(name, "unsupported", "created-file baseline unavailable")
                )
                continue
            found = any(fnmatch.fnmatchcase(path, str(grader["path"])) for path in created_files)
            passed = found == bool(grader.get("exists", True))
            results.append(GraderResult(name, "pass" if passed else "fail"))
        else:
            results.append(GraderResult(name, "unsupported", f"unknown grader type: {kind}"))
    statuses = {result.status for result in results}
    status: Status = (
        "fail" if "fail" in statuses else "unsupported" if "unsupported" in statuses else "pass"
    )
    limitations = []
    if "allowed_tools" in case.spec["execution"]:
        limitations.append("Current runner does not enforce an equivalent of Claude allowed_tools")
    if "max_turns" in case.spec["execution"]:
        limitations.append("Current runner does not enforce an equivalent of Claude max_turns")
    return CaseResult(
        case.name,
        status,
        tuple(results),
        tuple(limitations),
        skill_evidence=skill_evidence,
        skill_assessments=tuple(assessments),
    )


def _run_trial(case: EvalCase, runtime: PreparedRuntime, root: Path, run_index: int) -> CaseResult:
    execution_status = "error"
    limitations: tuple[str, ...] = ()
    skill_evidence: SkillEvidence | None = None
    try:
        execution = execute_case(CaseRequest(case, root, codex_prompt(case.prompt)), runtime)
        execution_status, limitations = execution.execution_status, execution.limitations
        skill_evidence = execution.skill_evidence
        normalized = _normalized_hook_responses(case, execution.hook_records)
        if normalized is not None:
            (root / "normalized-hook-responses.jsonl").write_text(
                normalized + "\n", encoding="utf-8"
            )
        if execution.execution_status != "completed":
            result = CaseResult(
                case.name, "error", (), error=execution.error, skill_evidence=skill_evidence
            )
        else:
            result = evaluate_case(
                case,
                execution.workspace,
                execution.events,
                execution.last_message,
                created_files=execution.created_files,
                hook_records=execution.hook_records,
                skill_evidence=skill_evidence,
            )
    except Exception as error:
        LOGGER.exception("Eval trial could not be graded for %s", case.name)
        root.mkdir(parents=True, exist_ok=True)
        result = CaseResult(
            case.name, "error", (), error=f"Trial error: {error}", skill_evidence=skill_evidence
        )
    key = case.directory.relative_to(runtime.config.repository / "evals").as_posix()
    result = replace(
        result,
        limitations=tuple(dict.fromkeys((*result.limitations, *limitations))),
        source_path=str((case.directory / "case.yaml").resolve()),
        case_key=key,
        run_index=run_index,
        execution_status=execution_status,
        trace=str(root / "trace.jsonl"),
        artifacts=str(root),
    )
    write_json(root / "result.json", asdict(result))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin", help="Existing evals/<plugin> suite, or all")
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--case", default="*")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument(
        "--runs", type=int, default=None, help="Override each canonical case's runs"
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--retain-sessions",
        action="store_true",
        help="Retain isolated Codex session rollouts",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.jobs <= 8:
        parser.error("--jobs must be between 1 and 8")
    if args.runs is not None and args.runs < 1:
        parser.error("--runs must be positive")
    evals = ROOT / "evals"
    suite = evals if args.plugin == "all" else (evals / args.plugin).resolve()
    if not suite.is_dir() or not suite.is_relative_to(evals.resolve()):
        parser.error(f"No eval suite: {suite}")
    cases = [
        load_case(path.parent)
        for path in sorted(suite.rglob("case.yaml"))
        if "results" not in path.relative_to(evals).parts
    ]
    cases = [
        case
        for case in cases
        if fnmatch.fnmatchcase(case.name, args.case)
        or fnmatch.fnmatchcase(case.directory.relative_to(evals).as_posix(), args.case)
    ]
    if not cases:
        parser.error(f"No eval cases match {args.case!r}")
    trials: list[tuple[EvalCase, int]] = []
    for case in cases:
        count = args.runs if args.runs is not None else case.spec.get("runs", 1)
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            parser.error(f"Invalid runs count in {case.directory / 'case.yaml'}")
        trials.extend((case, index) for index in range(1, count + 1))
    output = (
        args.output_dir or evals / "results" / datetime.now(UTC).strftime("codex-%Y%m%dT%H%M%S%fZ")
    ).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        LOGGER.error("Refusing nonempty eval output directory: %s", output)
        return 2
    output.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, object] = {
        "completed": False,
        "started_at": datetime.now(UTC).isoformat(),
        "model": args.model,
        "suite": args.plugin,
        "jobs": args.jobs,
        "case_count": len(cases),
        "trial_count": len(trials),
        "retain_sessions": args.retain_sessions,
    }
    write_json(output / "metadata.json", metadata)
    results: list[CaseResult] = []
    try:
        runtime = prepare_runtime(
            RuntimeConfig(
                ROOT,
                output,
                args.model,
                retain_sessions=args.retain_sessions,
            )
        )
        metadata["provenance"] = runtime.provenance
        write_json(output / "metadata.json", metadata)
        executor = ThreadPoolExecutor(max_workers=args.jobs)
        pending: dict[Future[CaseResult], tuple[EvalCase, int]] = {}
        try:
            for case, index in trials:
                future = executor.submit(
                    _run_trial,
                    case,
                    runtime,
                    output / "cases" / case.directory.relative_to(evals) / f"run-{index}",
                    index,
                )
                pending[future] = (case, index)
            with (output / "results.jsonl").open("x", encoding="utf-8") as stream:
                for future in as_completed(pending):
                    case, index = pending[future]
                    result = future.result()
                    results.append(result)
                    stream.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
                    stream.flush()
                    print(f"{result.status:11} {result.case_key} run={index}", flush=True)
        except BaseException:
            runtime.cancelled.set()
            for future in pending:
                future.cancel()
            executor.shutdown(wait=True, cancel_futures=True)
            raise
        else:
            executor.shutdown(wait=True)
        results.sort(key=lambda item: (item.case_key, item.run_index))
        write_json(output / "results.json", [asdict(result) for result in results])
        metadata.update(completed=True, completed_at=datetime.now(UTC).isoformat())
        write_json(output / "metadata.json", metadata)
        print(f"Results: {output / 'results.json'}", flush=True)
    except KeyboardInterrupt:
        metadata.update(interrupted=True, completed=False)
        write_json(output / "metadata.json", metadata)
        LOGGER.warning("Codex eval run interrupted; queued cases cancelled")
        return 130
    except (OSError, RuntimeError, ValueError) as error:
        LOGGER.exception("Codex eval run could not complete")
        metadata["setup_error"] = str(error)
        write_json(output / "metadata.json", metadata)
        return 2
    return 1 if any(result.status != "pass" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
