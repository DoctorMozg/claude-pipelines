"""Live smoke test for plugin hooks in headless sessions: startup, session end, resume, compact.
Spends about a cent on haiku and covers what plugin evals can't reach, so it stays out of CI."""

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tests.e2e.smoke_common import (
    Check,
    Event,
    SmokeError,
    print_checks,
    result_event,
    run_claude,
    stream_events,
)

log = logging.getLogger("hooks_smoke")

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORDER = Path(__file__).resolve().parent / "fixtures" / "hook-recorder"
# mz-dev-pipe depends on mz-base, and a plugin whose dependency isn't loaded is skipped.
PLUGINS = ("mz-memory", "mz-dev-pipe", "mz-base")
FIXTURE_LIB = Path("mz-memory/evals/_lib/fixture.sh")
MODEL = "haiku"
RUN_TIMEOUT_S = 300

PINNED = "QUILLFEATHER"
TASK = "2026_11_02_build_smoke_capture"
MEMORY = Path(".mz/memory/MEMORY.md")
TOOLING = Path(".mz/tooling.json")
RECORDS = Path(".hook-recorder/sessionstart.log")
# Plugin eval traces omit UserPromptSubmit output, so the correction nudge is only observable here.
NUDGE = "If this corrects something you did"
STARTUP_PROMPT = "Reply with just OK. Don't search the files, and you must never call a tool here."
RESUME_PROMPT = "No, that's not what I asked. Reply with just OK again."

# Reuses the eval fixture helpers, so the smoke project has the same layout as the eval cases.
SEED = f"""set -euo pipefail
source "$1"
init_project
write_memory "- [2026-10-12] The deploy codename for this service is {PINNED}." ""
printf '## Decisions\\n- Keep hook smoke runs on haiku\\n' | write_task {TASK} complete
printf '[project]\\nname = "smoke"\\n\\n[tool.ruff]\\nline-length = 100\\n' > pyproject.toml
"""


@dataclass(frozen=True)
class Session:
    label: str
    events: list[Event]
    cost_usd: float

    def hook_outputs(self, hook_name: str) -> list[str]:
        return [
            str(event.get("output") or "")
            for event in self.events
            if event.get("subtype") == "hook_response" and event.get("hook_name") == hook_name
        ]


@dataclass(frozen=True)
class Harness:
    plugins_root: Path
    workdir: Path
    repo: Path
    max_usd: float

    def run(self, label: str, prompt: str, session_args: Sequence[str]) -> Session:
        plugin_dirs = [
            arg for name in PLUGINS for arg in ("--plugin-dir", str(self.plugins_root / name))
        ]
        command = [
            "claude",
            "-p",
            prompt,
            "--model",
            MODEL,
            # Only local settings: the user's own installed plugins and hooks would add noise.
            "--setting-sources",
            "local",
            *plugin_dirs,
            "--plugin-dir",
            str(RECORDER),
            *session_args,
            "--max-budget-usd",
            f"{self.max_usd:.2f}",
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-hook-events",
        ]
        transcript = self.workdir / f"{label}.jsonl"
        log.info("starting %s", label)
        if not run_claude(command, self.repo, transcript, RUN_TIMEOUT_S):
            raise SmokeError(f"{label} timed out; see {transcript}")
        events = stream_events(transcript)
        result = result_event(events)
        if result is None:
            raise SmokeError(f"{label} left no result event; see {transcript}")
        return Session(label, events, float(result.get("total_cost_usd", 0.0)))

    def last_source(self) -> str:
        path = self.repo / RECORDS
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        return lines[-1].removeprefix("source=") if lines else "none"

    def tooling_mtime(self) -> int:
        path = self.repo / TOOLING
        return path.stat().st_mtime_ns if path.exists() else 0


def check_preconditions(plugins_root: Path) -> None:
    for tool in ("claude", "git", "jq"):
        if shutil.which(tool) is None:
            raise SmokeError(f"{tool} is not on PATH")
    for name in PLUGINS:
        if not (plugins_root / name / ".claude-plugin" / "plugin.json").is_file():
            raise SmokeError(f"no plugin manifest for {name} under {plugins_root}")


def seed_project(repo: Path, plugins_root: Path) -> None:
    try:
        subprocess.run(
            ["bash", "-c", SEED, "seed", str(plugins_root / FIXTURE_LIB)],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise SmokeError(f"seeding the smoke project failed: {error.stderr.strip()}") from error


def startup_checks(session: Session, harness: Harness) -> list[Check]:
    start = session.hook_outputs("SessionStart:startup")
    prompt = session.hook_outputs("UserPromptSubmit")
    failed_hooks = [
        event.get("hook_name")
        for event in session.events
        if event.get("subtype") == "hook_response" and event.get("outcome") != "success"
    ]
    memory = harness.repo / MEMORY
    return [
        Check("recorder saw source=startup", "startup", harness.last_source()),
        Check("SessionStart injected the pinned memory", True, any(PINNED in out for out in start)),
        Check(
            "SessionStart announced the python tooling",
            True,
            any("Project tooling detected: python" in out for out in start),
        ),
        Check("detect-tooling wrote tooling.json", True, (harness.repo / TOOLING).is_file()),
        Check(
            "UserPromptSubmit injected the pinned memory",
            True,
            any(PINNED in out for out in prompt),
        ),
        Check(
            "no correction nudge on a plain instruction", False, any(NUDGE in out for out in prompt)
        ),
        Check("every hook exited successfully", [], failed_hooks),
        # SessionEnd runs as `claude -p` exits, so its write is on disk by now.
        Check(
            "SessionEnd logged the completed task",
            True,
            memory.exists() and TASK in memory.read_text(encoding="utf-8"),
        ),
    ]


def resume_checks(session: Session, harness: Harness, tooling_mtime: int) -> list[Check]:
    start = session.hook_outputs("SessionStart:resume")
    prompt = session.hook_outputs("UserPromptSubmit")
    return [
        Check("recorder saw source=resume", "resume", harness.last_source()),
        Check("correction nudge on a correction", True, any(NUDGE in out for out in prompt)),
        Check(
            "memory not re-injected on resume", False, any("Project memory" in out for out in start)
        ),
        Check("detect-tooling skipped on resume", tooling_mtime, harness.tooling_mtime()),
    ]


def compact_checks(session: Session, harness: Harness) -> list[Check]:
    start = session.hook_outputs("SessionStart:compact")
    compacted = any(event.get("subtype") == "compact_boundary" for event in session.events)
    return [
        Check("recorder saw source=compact", "compact", harness.last_source()),
        Check("conversation was compacted", True, compacted),
        Check("memory re-injected after compaction", True, any(PINNED in out for out in start)),
    ]


def forget_session(session_id: str, repo: Path) -> None:
    """Delete the transcript the runs left in the claude config dir, which `--resume` needed."""
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    # Claude Code names a project's transcript folder after its path, every other character a dash.
    project_name = re.sub(r"[^A-Za-z0-9]", "-", str(repo.resolve()))
    for transcript in config.glob(f"projects/*/{session_id}.jsonl"):
        if transcript.parent.name == project_name:
            shutil.rmtree(transcript.parent)
        else:
            transcript.unlink()
        log.info("removed %s", transcript)


def run_all(harness: Harness) -> list[tuple[Session, list[Check]]]:
    session_id = str(uuid.uuid4())
    try:
        startup = harness.run("startup", STARTUP_PROMPT, ["--session-id", session_id])
        results = [(startup, startup_checks(startup, harness))]
        tooling_mtime = harness.tooling_mtime()
        resume = harness.run("resume", RESUME_PROMPT, ["--resume", session_id])
        results.append((resume, resume_checks(resume, harness, tooling_mtime)))
        compact = harness.run("compact", "/compact", ["--resume", session_id])
        results.append((compact, compact_checks(compact, harness)))
        return results
    finally:
        forget_session(session_id, harness.repo)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--max-usd-per-run", type=float, default=0.10)
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
    try:
        plugins_root = args.plugins_root.resolve()
        check_preconditions(plugins_root)
        workdir = Path(tempfile.mkdtemp(prefix="hooks_smoke_"))
        repo = workdir / "project"
        repo.mkdir()
        seed_project(repo, plugins_root)
        results = run_all(Harness(plugins_root, workdir, repo, args.max_usd_per_run))
    except SmokeError as error:
        log.error("%s", error)
        return 2
    all_passed = True
    for session, checks in results:
        all_passed &= print_checks(f"{session.label} (${session.cost_usd:.3f})", checks)
    total = sum(session.cost_usd for session, _ in results)
    print(f"\n{'passed' if all_passed else 'FAILED'}; cost ${total:.3f}; transcripts in {workdir}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
