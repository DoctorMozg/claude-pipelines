"""Live smoke test for plugin hooks in headless runs: start, end, resume, compact, clear, vault.
Spends a few cents on haiku and covers what plugin evals can't reach, so it stays out of CI."""

import argparse
import logging
import shutil
import sys
import tempfile
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from tests.e2e.smoke_common import (
    Check,
    HeadlessClaude,
    Session,
    SmokeError,
    forget_session,
    print_checks,
    run_seed,
)

log = logging.getLogger("hooks_smoke")

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORDER = Path(__file__).resolve().parent / "fixtures" / "hook-recorder"
# mz-dev-pipe depends on mz-base, and a plugin whose dependency isn't loaded is skipped.
PLUGINS = ("mz-memory", "mz-dev-pipe", "mz-base")
KNOWLEDGE_PLUGINS = ("mz-knowledge",)
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

VAULT_NOTE = Path("notes/smoke.md")
VAULT_PLAIN = Path("notes/plain.txt")
VAULT_MOC = Path("00 - MOCs/Smoke-MOC.md")
MOC_LINE = "Vault MOCs: Smoke-MOC"
NORMALIZED = "---\ntags:\n  - AI-Ethics\ncreated: {today}\n---\n"
# The .txt write proves the if-rules skip other files; the Edit proves Claude survives the rewrite.
FRONTMATTER_PROMPT = """Do these three steps with your tools, in order, then reply with just OK.
1. Write the file {note} with exactly this content:
---
tag: "#AI Ethics"
---
# Smoke
2. Write the file {plain} with the content: plain
3. Edit {note} so the line "# Smoke" becomes "# Smoke edited"."""

# Reuses the eval fixture helpers, so the smoke project has the same layout as the eval cases.
SEED = f"""set -euo pipefail
source "$1"
init_project
write_memory "- [2026-10-12] The deploy codename for this service is {PINNED}." ""
printf '## Decisions\\n- Keep hook smoke runs on haiku\\n' | write_task {TASK} complete
printf '[project]\\nname = "smoke"\\n\\n[tool.ruff]\\nline-length = 100\\n' > pyproject.toml
"""


@dataclass(frozen=True)
class Harness:
    plugins_root: Path
    claude: HeadlessClaude

    @property
    def repo(self) -> Path:
        return self.claude.cwd

    def memory_plugins(self) -> list[Path]:
        return [*(self.plugins_root / name for name in PLUGINS), RECORDER]

    def knowledge_plugins(self) -> list[Path]:
        return [self.plugins_root / name for name in KNOWLEDGE_PLUGINS]

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
    for name in (*PLUGINS, *KNOWLEDGE_PLUGINS):
        if not (plugins_root / name / ".claude-plugin" / "plugin.json").is_file():
            raise SmokeError(f"no plugin manifest for {name} under {plugins_root}")


def make_vault(vault: Path) -> None:
    """A vault with one MOC and today's daily note, beside the project like most real vaults."""
    for folder in (".obsidian", VAULT_NOTE.parent, VAULT_MOC.parent, Path("daily")):
        (vault / folder).mkdir(parents=True, exist_ok=True)
    (vault / VAULT_MOC).write_text("# Smoke map\n", encoding="utf-8")
    (vault / "daily" / f"{date.today().isoformat()}.md").write_text("# Today\n", encoding="utf-8")


def startup_checks(session: Session, harness: Harness) -> list[Check]:
    start = session.hook_outputs("SessionStart:startup")
    prompt = session.hook_outputs("UserPromptSubmit")
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
        Check("every hook exited successfully", [], session.failed_hooks()),
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


def frontmatter_checks(session: Session, vault: Path) -> list[Check]:
    writes = session.tool_inputs("Write")
    md_writes = [write for write in writes if str(write.get("file_path", "")).endswith(".md")]
    write_outputs = session.hook_outputs("PostToolUse:Write")
    note = vault / VAULT_NOTE
    text = note.read_text(encoding="utf-8") if note.exists() else ""
    return [
        Check("Claude also wrote the .txt file", True, len(writes) > len(md_writes)),
        # The vault sits outside the working directory, and the .txt write must not spawn the hook.
        Check("one Write hook run per .md Write", len(md_writes), len(write_outputs)),
        Check(
            "the Write hook reported its change",
            True,
            any("tag -> tags list" in out for out in write_outputs),
        ),
        Check("the Edit hook ran", True, bool(session.hook_outputs("PostToolUse:Edit"))),
        Check(
            "frontmatter normalized on disk",
            NORMALIZED.format(today=date.today().isoformat()),
            text.partition("# Smoke")[0],
        ),
        Check("the Edit after the rewrite landed", True, "# Smoke edited" in text),
        Check("every hook exited successfully", [], session.failed_hooks()),
    ]


def vault_startup_checks(session: Session) -> list[Check]:
    start = session.hook_outputs("SessionStart:startup")
    daily = f"Today's daily note: {date.today().isoformat()}.md"
    return [
        Check("vault-context listed the MOC", True, any(MOC_LINE in out for out in start)),
        Check("vault-context named today's daily note", True, any(daily in out for out in start)),
        Check("every hook exited successfully", [], session.failed_hooks()),
    ]


def clear_checks(session: Session, harness: Harness) -> list[Check]:
    start = session.hook_outputs("SessionStart:clear")
    return [
        Check("recorder saw source=clear", "clear", harness.last_source()),
        Check(
            "vault context re-injected after /clear", True, any(MOC_LINE in out for out in start)
        ),
        Check("every hook exited successfully", [], session.failed_hooks()),
    ]


def run_all(harness: Harness) -> list[tuple[Session, list[Check]]]:
    session_id = str(uuid.uuid4())
    try:
        plugins = harness.memory_plugins()
        startup = harness.claude.run(
            "startup", STARTUP_PROMPT, plugins, ["--session-id", session_id]
        )
        results = [(startup, startup_checks(startup, harness))]
        tooling_mtime = harness.tooling_mtime()
        resume = harness.claude.run("resume", RESUME_PROMPT, plugins, ["--resume", session_id])
        results.append((resume, resume_checks(resume, harness, tooling_mtime)))
        compact = harness.claude.run("compact", "/compact", plugins, ["--resume", session_id])
        results.append((compact, compact_checks(compact, harness)))
        return results
    finally:
        forget_session(session_id, harness.repo)


def run_frontmatter(harness: Harness, vault: Path) -> tuple[Session, list[Check]]:
    session_id = str(uuid.uuid4())
    prompt = FRONTMATTER_PROMPT.format(note=vault / VAULT_NOTE, plain=vault / VAULT_PLAIN)
    args = ["--session-id", session_id, "--add-dir", str(vault), "--permission-mode", "acceptEdits"]
    try:
        session = harness.claude.run("frontmatter", prompt, harness.knowledge_plugins(), args)
        return session, frontmatter_checks(session, vault)
    finally:
        forget_session(session_id, harness.repo)


def run_vault_context(harness: Harness, vault: Path) -> list[tuple[Session, list[Check]]]:
    session_id = str(uuid.uuid4())
    claude = replace(harness.claude, extra_env={"OBSIDIAN_VAULT_PATH": str(vault)})
    plugins = [*harness.knowledge_plugins(), RECORDER]
    try:
        startup = claude.run("vault-startup", STARTUP_PROMPT, plugins, ["--session-id", session_id])
        results = [(startup, vault_startup_checks(startup))]
        # `/clear` costs nothing under -p, yet still runs SessionStart with source=clear.
        cleared = claude.run("clear", "/clear", plugins, ["--resume", session_id])
        results.append((cleared, clear_checks(cleared, harness)))
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
        run_seed(repo, SEED, str(plugins_root / FIXTURE_LIB))
        vault = workdir / "vault"
        make_vault(vault)
        claude = HeadlessClaude(workdir, repo, MODEL, args.max_usd_per_run, RUN_TIMEOUT_S)
        harness = Harness(plugins_root, claude)
        results = [
            *run_all(harness),
            run_frontmatter(harness, vault),
            *run_vault_context(harness, vault),
        ]
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
