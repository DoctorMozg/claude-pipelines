"""Replay skill observations from retained Codex trials without running models."""

import argparse
import hashlib
import json
import logging
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from tests.eval_tools.codex_runtime import _parse_session
from tests.eval_tools.codex_skill_evidence import (
    EvidenceContext,
    SkillAssessment,
    SkillCatalog,
    SkillEvidence,
    analyze_skill_evidence,
    assess_skill_assertion,
)

LOGGER = logging.getLogger(__name__)
_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_HISTORICAL_LIMIT = (
    "Historical root seals do not seal per-case traces, metadata or installed caches; "
    "their recorded hashes below are fresh replay fingerprints."
)


@dataclass(frozen=True)
class _Selection:
    row: dict[str, Any]
    trial: Path
    run: Path
    key: str
    index: int


@dataclass
class _Validation:
    errors: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=lambda: [_HISTORICAL_LIMIT])
    fingerprints: dict[str, str] = field(default_factory=dict)

    def document(self) -> dict[str, object]:
        return {"status": "error" if self.errors else "verified", **asdict(self)}


@dataclass
class _Run:
    root: Path
    validation: _Validation
    packages: dict[str, Path] = field(default_factory=dict)
    inventories: dict[str, dict[str, str]] = field(default_factory=dict)
    catalog: SkillCatalog = field(default_factory=SkillCatalog)


def _safe_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.as_posix() != value:
        raise ValueError(f"Unsafe relative evidence path: {value!r}")
    return path


def _read(path: Path, validation: _Validation, root: Path | None = None) -> bytes:
    if root is not None:
        if not path.is_relative_to(root) or not path.resolve(strict=True).is_relative_to(root):
            raise ValueError(f"Evidence path escapes {root}: {path}")
        if path.resolve(strict=True) != path.absolute() and not (
            path.name == "trace.jsonl" and path.parent.resolve() == root
        ):
            raise ValueError(f"Unexpected evidence symlink: {path}")
    content = path.read_bytes()
    validation.fingerprints[str(path)] = hashlib.sha256(content).hexdigest()
    return content


def _object(path: Path, validation: _Validation, root: Path) -> dict[str, Any]:
    value: object = json.loads(_read(path, validation, root))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {path}")
    return value


def _verify_hash(
    path: Path, expected: object, validation: _Validation, root: Path | None = None
) -> None:
    if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
        raise ValueError(f"Invalid recorded SHA-256 for {path}")
    if hashlib.sha256(_read(path, validation, root)).hexdigest() != expected:
        raise ValueError(f"Recorded hash mismatch: {path}")


def _selections(index: Path, output: Path) -> tuple[list[_Selection], str]:
    content = index.read_bytes()
    rows = json.loads(content)
    if not isinstance(rows, list) or not rows:
        raise ValueError("Replay index must contain a nonempty list of result objects")
    if output.exists() or output.is_symlink():
        raise ValueError(f"Replay output must not exist: {output}")
    selections: list[_Selection] = []
    identities: set[tuple[str, int]] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Every replay index row must be an object")
        if {"skill_evidence", "skill_assessments", "evidence_validation"} & row.keys():
            raise ValueError("Replay requires original results without derived evidence fields")
        key, run_index = row.get("case_key"), row.get("run_index")
        if not isinstance(key, str) or not key:
            raise ValueError("Replay row requires a case_key")
        relative = _safe_relative(key)
        if any(not _COMPONENT.fullmatch(part) for part in relative.parts):
            raise ValueError(f"Unsafe case identity: {key!r}")
        if type(run_index) is not int or run_index < 1:
            raise ValueError(f"Invalid trial index: {run_index!r}")
        if (key, run_index) in identities:
            raise ValueError(f"Duplicate replay selection: {key} run {run_index}")
        identities.add((key, run_index))
        for name in (
            "artifacts",
            "trace",
            "source_path",
            "name",
            "status",
            "execution_status",
            "error",
        ):
            if not isinstance(row.get(name), str):
                raise ValueError(f"Replay row requires string {name}")
        if not isinstance(row.get("graders"), list):
            raise ValueError("Replay row requires grader results")
        if row["status"] not in {"pass", "fail", "unsupported", "error"}:
            raise ValueError("Replay row has an invalid original case status")
        if row["execution_status"] not in {"completed", "error", "timeout"}:
            raise ValueError("Replay row has an invalid original execution status")
        trial = Path(row["artifacts"])
        if not trial.is_absolute() or ".." in trial.parts:
            raise ValueError(f"Trial path must be absolute: {trial}")
        suffix = Path("cases") / relative / f"run-{run_index}"
        if (
            len(trial.parts) <= len(suffix.parts)
            or trial.parts[-len(suffix.parts) :] != suffix.parts
        ):
            raise ValueError(f"Trial path disagrees with case identity: {trial}")
        run = trial.parents[len(relative.parts) + 1]
        if output.is_relative_to(run.resolve()):
            raise ValueError(f"Replay output cannot be inside historical run: {run}")
        if output == index.resolve() or index.resolve().is_relative_to(output):
            raise ValueError("Replay output would contain its input index")
        if Path(row["trace"]) != trial / "trace.jsonl":
            raise ValueError("Trace path must name the selected trial's trace.jsonl")
        selections.append(_Selection(row, trial, run, key, run_index))
    return selections, hashlib.sha256(content).hexdigest()


def _verify_run(root: Path) -> _Run:
    run = _Run(root, _Validation())
    validation = run.validation
    try:
        provenance = _object(root / "runtime/provenance.json", validation, root)
        metadata = _object(root / "metadata.json", validation, root)
        if metadata.get("provenance") != provenance:
            raise ValueError("Historical metadata and provenance disagree")
        packages = provenance.get("packages")
        if not isinstance(packages, dict):
            raise ValueError("Historical package inventory is missing")
        frozen = root / "runtime/frozen"
        if {path.name for path in frozen.iterdir()} != set(packages):
            raise ValueError("Frozen package set disagrees with provenance")
        for plugin, details in packages.items():
            if not isinstance(plugin, str) or not _COMPONENT.fullmatch(plugin):
                raise ValueError("Invalid plugin identity in historical provenance")
            if not isinstance(details, dict) or not isinstance(details.get("files"), dict):
                raise ValueError(f"Missing frozen file inventory for {plugin}")
            package = frozen / plugin
            inventory: dict[str, str] = {}
            for relative, expected in details["files"].items():
                if not isinstance(relative, str):
                    raise ValueError(f"Invalid frozen filename for {plugin}")
                path = package / _safe_relative(relative)
                _verify_hash(path, expected, validation, package)
                inventory[relative] = str(expected)
            paths = tuple(package.rglob("*"))
            if any(path.is_symlink() for path in paths):
                raise ValueError(f"Frozen package contains a symlink: {plugin}")
            actual = {path.relative_to(package).as_posix() for path in paths if path.is_file()}
            if actual != set(inventory):
                raise ValueError(f"Frozen file inventory disagrees with package: {plugin}")
            manifest = _object(package / "plugin.json", validation, package)
            if manifest.get("name") != plugin or manifest.get("version") != details.get("version"):
                raise ValueError(f"Frozen package identity mismatch: {plugin}")
            run.packages[plugin], run.inventories[plugin] = package, inventory
        run.catalog = SkillCatalog.from_packages(run.packages)
        sources = provenance.get("runtime_sources", {})
        if not isinstance(sources, dict):
            raise ValueError("Historical runtime source hashes must be an object")
        for filename, expected in sources.items():
            path = Path(filename)
            try:
                current = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                current = None
            if current != expected:
                validation.limitations.append(
                    f"Historical executor source drift or absence: {path}"
                )
        seal_path = root / "seal.json"
        if seal_path.exists() or seal_path.is_symlink():
            seal = _object(seal_path, validation, root)
            for relative, expected in seal.items():
                _verify_hash(root / _safe_relative(relative), expected, validation, root)
        else:
            validation.limitations.append("This historical run has no root seal.")
    except (OSError, ValueError, TypeError) as error:
        validation.errors.append(f"Historical run validation failed: {error}")
        LOGGER.warning("Historical run validation failed for %s: %s", root, error)
    return run


def _recorded_case(selection: _Selection, validation: _Validation) -> dict[str, Any]:
    trial, row = selection.trial, selection.row
    case = _object(trial / "case.json", validation, trial)
    result = _object(trial / "result.json", validation, trial)
    if result != {key: value for key, value in row.items() if key != "evidence_run"}:
        raise ValueError("Index and historical result disagree")
    for name in ("source_path", "execution_status", "error"):
        if case.get(name) != row[name]:
            raise ValueError(f"Recorded case and result disagree on {name}")
    spec, inputs = case.get("spec"), case.get("input_hashes")
    if not isinstance(spec, dict) or not isinstance(inputs, dict):
        raise ValueError("Recorded case requires spec and input hashes")
    source = Path(row["source_path"])
    source_sha = case.get("source_sha256")
    if (
        not source.is_absolute()
        or not isinstance(source_sha, str)
        or not _SHA256.fullmatch(source_sha)
        or str(source) not in inputs
        or inputs[str(source)] != source_sha
    ):
        raise ValueError("Recorded source SHA-256 disagrees with input hashes")
    for filename, expected in inputs.items():
        if not isinstance(filename, str) or not Path(filename).is_absolute():
            raise ValueError("Recorded input paths must be absolute")
        _verify_hash(Path(filename), expected, validation)
    if yaml.safe_load(_read(source, validation)) != spec:
        raise ValueError("Recorded spec disagrees with the verified canonical source")
    if spec.get("name", source.parent.name) != row["name"]:
        raise ValueError("Recorded case name disagrees with the original result")
    if not isinstance(spec.get("execution"), dict) or not isinstance(spec.get("graders"), list):
        raise ValueError("Recorded spec requires execution and grader definitions")
    plugins = spec.get("plugins", [])
    if not isinstance(plugins, list) or any(not isinstance(p, str) for p in plugins):
        raise ValueError("Recorded plugins must be a list of paths")
    expected_plugins = list(dict.fromkeys(Path(plugin).name for plugin in plugins))
    if case.get("plugins") != expected_plugins:
        raise ValueError("Recorded plugin identities disagree with the recorded spec")
    if any(not _COMPONENT.fullmatch(plugin) for plugin in expected_plugins):
        raise ValueError("Recorded plugin identity is unsafe")
    return case


def _installed_packages(
    selection: _Selection, case: Mapping[str, Any], run: _Run, validation: _Validation
) -> SkillCatalog:
    plugins = case["plugins"]
    missing = [plugin for plugin in plugins if plugin not in run.packages]
    known_failure = (
        case["execution_status"] == "error"
        and bool(missing)
        and case["error"] == "Unavailable Codex package dependencies: " + ", ".join(missing)
    )
    if known_failure:
        validation.limitations.append(case["error"] + "; installed cache unavailable.")
        return SkillCatalog()
    if missing:
        raise ValueError(f"Requested packages absent from historical run: {missing}")
    cache = selection.trial / "home/.codex/plugins/cache"
    for plugin in plugins:
        inventory = run.inventories[plugin]
        definitions = tuple(skill for skill in run.catalog.skills if skill.plugin == plugin)
        manifest = json.loads((run.packages[plugin] / "plugin.json").read_bytes())
        installed = tuple(cache.glob(f"*/{plugin}/{manifest['version']}"))
        if not installed:
            raise ValueError(f"Installed requested package is unavailable: {plugin}")
        for package in installed:
            _verify_hash(package / "plugin.json", inventory["plugin.json"], validation, cache)
            expected_bodies = {f"skills/{skill.skill}/SKILL.md" for skill in definitions}
            actual_bodies = {
                p.relative_to(package).as_posix() for p in (package / "skills").glob("*/SKILL.md")
            }
            if actual_bodies != expected_bodies:
                raise ValueError(f"Installed skill body set changed: {plugin}")
            for relative in expected_bodies:
                _verify_hash(package / relative, inventory[relative], validation, cache)
            for skill in definitions:
                for script in skill.scripts:
                    _verify_hash(package / script.path, inventory[script.path], validation, cache)
    return SkillCatalog(tuple(skill for skill in run.catalog.skills if skill.plugin in plugins))


def _events(
    selection: _Selection, validation: _Validation, completed: bool
) -> list[dict[str, Any]]:
    text = _read(selection.trial / "trace.jsonl", validation, selection.trial).decode("utf-8")
    events, _, error = _parse_session(text)
    if error and (completed or error == "Invalid JSON in Codex session output"):
        raise ValueError(f"Invalid retained CLI trace: {error}")
    return events


def _skill_graders(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    spec = case.get("spec", {})
    graders = spec.get("graders", []) if isinstance(spec, dict) else []
    if not isinstance(graders, list):
        return ()
    return tuple(
        g
        for g in graders
        if isinstance(g, dict) and g.get("type") == "tool_used" and g.get("tool") == "Skill"
    )


def _replay(selection: _Selection, run: _Run) -> tuple[dict[str, Any], int]:
    validation = _Validation(
        list(run.validation.errors),
        list(run.validation.limitations),
        {
            name: digest
            for name, digest in run.validation.fingerprints.items()
            if not Path(name).is_relative_to(run.root / "runtime/frozen")
        },
    )
    evidence = SkillEvidence()
    assessments: tuple[SkillAssessment, ...] = ()
    case: dict[str, Any] = {}
    try:
        # Preserve the recorded assertion count even when later input verification fails.
        case = _object(selection.trial / "case.json", validation, selection.trial)
        case = _recorded_case(selection, validation)
        events = _events(selection, validation, case["execution_status"] == "completed")
        if not validation.errors:
            catalog = _installed_packages(selection, case, run, validation)
            evidence = analyze_skill_evidence(
                catalog,
                EvidenceContext(
                    selection.trial / "home/.codex/plugins/cache",
                    selection.trial / "home/cwd",
                    events,
                ),
            )
            if case["execution_status"] == "completed":
                assessments = tuple(
                    assess_skill_assertion(g, evidence) for g in _skill_graders(case)
                )
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as error:
        validation.errors.append(f"Trial evidence validation failed: {error}")
        LOGGER.warning(
            "Trial evidence rejected for %s run %s: %s", selection.key, selection.index, error
        )
    if validation.errors:
        evidence = SkillEvidence(
            limitations=(*SkillEvidence().limitations, "Retained input validation failed.")
        )
        assessments = ()
    row = {
        **selection.row,
        "skill_evidence": asdict(evidence),
        "skill_assessments": [asdict(a) for a in assessments],
        "evidence_validation": validation.document(),
    }
    return row, len(_skill_graders(case)) - len(assessments)


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output_dir.is_symlink():
        LOGGER.error("Replay output must not be a symlink: %s", args.output_dir)
        return 2
    output = args.output_dir.resolve()
    try:
        selections, index_sha = _selections(args.index, output)
    except (OSError, ValueError, TypeError) as error:
        LOGGER.error("Replay setup failed: %s", error)
        return 2
    try:
        runs = {root: _verify_run(root) for root in dict.fromkeys(s.run for s in selections)}
        manifest = {
            "completed": False,
            "index": {"path": str(args.index.resolve()), "sha256": index_sha},
            "analyzer_sources": {
                str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (
                    Path(__file__).resolve(),
                    Path(__file__).with_name("codex_skill_evidence.py").resolve(),
                    Path(__file__).with_name("codex_runtime.py").resolve(),
                )
            },
            "runs": {str(root): run.validation.document() for root, run in runs.items()},
        }
        output.mkdir(parents=True)
        _write(output / "manifest.json", manifest)
        rows: list[dict[str, Any]] = []
        unassessed = 0
        with (output / "results.jsonl").open("x", encoding="utf-8") as stream:
            for selection in selections:
                row, count = _replay(selection, runs[selection.run])
                rows.append(row)
                unassessed += count
                sidecar = (
                    output
                    / "cases"
                    / selection.key
                    / f"run-{selection.index}"
                    / "skill-evidence.json"
                )
                sidecar.parent.mkdir(parents=True)
                _write(sidecar, row["skill_evidence"])
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
        summary = {
            "case_count": len(rows),
            "original_case_statuses": dict(Counter(row["status"] for row in rows)),
            "observation_states": dict(
                Counter(
                    item["state"] for row in rows for item in row["skill_evidence"]["observations"]
                )
            ),
            "assessment_states": dict(
                Counter(item["state"] for row in rows for item in row["skill_assessments"])
            ),
            "validation_statuses": dict(
                Counter(row["evidence_validation"]["status"] for row in rows)
            ),
            "unassessed_skill_assertions": unassessed,
        }
        _write(output / "results.json", rows)
        _write(output / "summary.json", summary)
        manifest["completed"] = True
        pending_manifest = output / "manifest.pending.json"
        _write(pending_manifest, manifest)
        pending_manifest.replace(output / "manifest.json")
    except OSError as error:
        LOGGER.error("Replay output could not be written to %s: %s", output, error)
        return 2
    return 1 if any(row["evidence_validation"]["errors"] for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
