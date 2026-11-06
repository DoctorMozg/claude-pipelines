"""Mutation check for the eval suites: break plugin code in a snapshot, then see the cases fail.
Paid, one `claude plugin eval` per mutant: `python -m tests.eval_tools.mutants [MUTANT ...]`."""

import argparse
import io
import json
import logging
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests.eval_tools.mutant_catalog import MUTANTS, Mutant

log = logging.getLogger("eval_mutants")

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_TIMEOUT_S = 1500


class MutantError(RuntimeError):
    """A snapshot or anchor problem that stops a mutant before any eval runs."""


@dataclass(frozen=True)
class MutantResult:
    mutant_id: str
    ok: bool
    detail: str
    cost_usd: float


@dataclass(frozen=True)
class EvalSettings:
    model: str
    judge_model: str
    max_usd: float
    jobs: int

    def command(self, mutant: Mutant, root: Path, out: Path) -> list[str]:
        command = [
            "claude",
            "plugin",
            "eval",
            str(root),
            "--eval-dir",
            f"evals/{mutant.plugin}",
            *mutant.select,
            "--runs",
            "1",
            "--scaffold",
            "--ablation",
            "none",
            "--trust-plugin",
            "--no-publish",
            "--model",
            self.model,
            "--judge-model",
            self.judge_model,
            "--max-cost-usd",
            f"{self.max_usd:g}",
            "-j",
            str(self.jobs),
        ]
        if mutant.allow_bash:
            command += ["--allow-tools", "Bash"]
        return [*command, "--json", str(out)]


def expand(root: Path, pattern: str) -> list[Path]:
    if "{" not in pattern:
        return sorted(root.glob(pattern))
    head, rest = pattern.split("{", 1)
    options, tail = rest.split("}", 1)
    return sorted(path for option in options.split(",") for path in root.glob(head + option + tail))


def plan_edits(root: Path, mutant: Mutant) -> dict[Path, str]:
    """The mutated text of each file `mutant` touches; a later edit sees the earlier ones."""
    if not root.is_dir():
        raise MutantError(f"{root} is not a directory")
    texts: dict[Path, str] = {}
    for edit in mutant.edits:
        targets = expand(root, edit.files)
        if not targets:
            raise MutantError(f"{mutant.id}: no file matches {edit.files}")
        for target in targets:
            text = texts[target] if target in texts else target.read_text(encoding="utf-8")
            count = text.count(edit.old)
            if count != 1:
                where = target.relative_to(root).as_posix()
                raise MutantError(f"{mutant.id}: anchor found {count} times in {where}")
            texts[target] = text.replace(edit.old, edit.new)
    return texts


def build_snapshot(dest: Path, repo: Path = REPO_ROOT) -> None:
    """Export HEAD's plugins/ into `dest`, then copy the working tree's evals/ minus results/."""
    # Runs see committed plugin code, not a peer's unfinished edits, plus cases not yet committed.
    try:
        archive = subprocess.run(
            ["git", "-C", str(repo), "archive", "--format=tar", "HEAD", "plugins"],
            capture_output=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError as error:
        stderr = error.stderr.decode(errors="replace").strip()
        raise MutantError(f"git archive HEAD plugins failed: {stderr}") from error
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(dest, filter="data")
    if (repo / "evals").is_dir():
        shutil.copytree(
            repo / "evals", dest / "evals", symlinks=True, ignore=shutil.ignore_patterns("results")
        )
    log.info("snapshot: HEAD plugins with working-tree evals in %s", dest)


def judge(mutant: Mutant, doc: dict[str, Any]) -> MutantResult:
    """Score one eval result: every must_fail grader failed, every must_pass case scored 1.0."""
    arms = [(case["name"], case["arms"]["with"][0]) for case in doc["cases"]]
    graders = {
        (name, grader["name"]): bool(grader["passed"])
        for name, arm in arms
        for grader in arm["graders"]
    }
    scores = {name: float(arm["score"]) for name, arm in arms}
    # Cases with a small max_turns end on the turn limit by design; any other error voids the run.
    run_errors = [
        error
        for _, arm in arms
        if (error := arm.get("error")) and "maximum number of turns" not in error
    ]
    # A grader missing from the result never ran, which counts as not caught.
    not_caught = [f"{c}/{g}" for c, g in mutant.must_fail if graders.get((c, g), True)]
    broken = [name for name in mutant.must_pass if scores.get(name, 0.0) < 1.0]
    failed = sorted(f"{c}/{g}" for (c, g), passed in graders.items() if not passed)
    parts = ["failed: " + (", ".join(failed) or "none")]
    if run_errors:
        parts.append(f"run errors: {run_errors[:2]}")
    if not_caught:
        parts.append(f"NOT CAUGHT: {not_caught}")
    if broken:
        parts.append(f"SHOULD HAVE PASSED: {broken}")
    ok = not (run_errors or not_caught or broken)
    return MutantResult(mutant.id, ok, " | ".join(parts), float(doc.get("costUsd", 0.0)))


def run_mutant(mutant: Mutant, head: Path, settings: EvalSettings) -> MutantResult:
    """Run the mutant's cases on a mutated copy of `head`; the result JSON stays beside `head`."""
    work = head.parent / f"mut-{mutant.id}"
    out = head.parent / f"{mutant.id}.json"
    shutil.copytree(head, work, symlinks=True)
    try:
        for path, text in plan_edits(work, mutant).items():
            path.write_text(text, encoding="utf-8")
        log.info("running %s against the %s suite", mutant.id, mutant.plugin)
        proc = subprocess.run(
            settings.command(mutant, work, out),
            capture_output=True,
            text=True,
            timeout=EVAL_TIMEOUT_S,
            check=False,
        )
    except MutantError as error:
        return MutantResult(mutant.id, False, str(error), 0.0)
    except subprocess.TimeoutExpired:
        log.error("%s: eval timed out after %ds", mutant.id, EVAL_TIMEOUT_S)
        return MutantResult(mutant.id, False, f"eval timed out after {EVAL_TIMEOUT_S}s", 0.0)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if not out.exists():
        log.error("%s: eval exited %d without a result", mutant.id, proc.returncode)
        return MutantResult(
            mutant.id, False, f"no result (exit {proc.returncode}): {proc.stderr[-300:]}", 0.0
        )
    try:
        return judge(mutant, json.loads(out.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
        log.error("%s: unreadable result %s: %r", mutant.id, out, error)
        return MutantResult(mutant.id, False, f"unreadable result {out}: {error!r}", 0.0)


def main(argv: Sequence[str] | None = None) -> int:
    ids = [mutant.id for mutant in MUTANTS]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("mutants", nargs="*", metavar="MUTANT", help="ids to run; all if omitted")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--judge-model", default="claude-haiku-5-5")
    parser.add_argument("--max-usd", type=float, default=2.0, help="cost cap per mutant")
    parser.add_argument("-j", "--jobs", type=int, default=4)
    args = parser.parse_args(argv)
    if unknown := sorted(set(args.mutants) - set(ids)):
        parser.error(f"unknown mutants: {', '.join(unknown)}")
    if args.max_usd <= 0:
        parser.error("--max-usd must be positive")
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    chosen = [mutant for mutant in MUTANTS if not args.mutants or mutant.id in args.mutants]
    workdir = Path(tempfile.mkdtemp(prefix="eval_mutants_"))
    head = workdir / "head"
    try:
        build_snapshot(head)
        # Every anchor is checked before the first paid run, so a stale one costs nothing.
        for mutant in chosen:
            plan_edits(head, mutant)
    except MutantError as error:
        log.error("%s", error)
        return 2
    settings = EvalSettings(args.model, args.judge_model, args.max_usd, args.jobs)
    results: list[MutantResult] = []
    for mutant in chosen:
        result = run_mutant(mutant, head, settings)
        results.append(result)
        status = "ok  " if result.ok else "FAIL"
        print(f"{status} {result.mutant_id:34} ${result.cost_usd:.2f} {result.detail}", flush=True)
    shutil.rmtree(head, ignore_errors=True)
    problems = sum(not result.ok for result in results)
    total = sum(result.cost_usd for result in results)
    print(f"total ${total:.2f}, {problems} problem(s); results in {workdir}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
