"""Live smoke test for the mz-dev-git GitHub collector agents, run from working-tree files.
Needs an authenticated gh and spends a few cents of tokens, so it stays out of CI."""

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import yaml

log = logging.getLogger("gh_smoke")

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "plugins" / "mz-dev-git" / "agents"
SMOKE_PREFIX = "smoke-"
SCORER = "github-pr-info-scorer"
FETCHER = "github-pr-data-fetcher"
SESSION_MODEL = "haiku"
# The commands the two agents run; in -p mode a missing grant is a silent denial.
SESSION_TOOLS = (
    "Agent",
    "Read",
    "Write",
    "Bash(gh *)",
    "Bash(wc *)",
    "Bash(mkdir *)",
    "Bash(date *)",
    "Bash(sort *)",
)
RUN_TIMEOUT_S = 600
# Mirrors the --limit in the fetcher's Step 2 queries; a query that fills it may be truncated.
FETCH_LIMIT = 50

# 411 files: changedFiles is right, files[] stops at 100.
SIZE_PR = ("kubernetes/kubernetes", 141224)
# 65 comments: the true last commenter is on page 3, so a run without --paginate names another.
PAGINATION_PR = ("kubernetes/kubernetes", 130806)
FETCH_USER = "williammartin"
FETCH_REPO = "cli/cli"
# Has PRs, none involving FETCH_USER: the fetcher must disclose ZERO RESULTS VERIFIED.
ZERO_REPO = "octocat/Hello-World"

FIELD_LINE = re.compile(r"^- (?P<key>[a-z_]+): (?P<value>.*)$", re.MULTILINE)
TABLE_PR_NUMBER = re.compile(r"^\| (?P<number>\d+) \|", re.MULTILINE)
TOTAL_PRS = re.compile(r"\*\*Total PRs found\*\*: (?P<total>\d+)")
STATUS_LINE = re.compile(r"STATUS: (?P<status>[A-Z_]+)")


class SmokeError(RuntimeError):
    """A precondition or tool failure that stops the run before any verdict."""


@dataclass(frozen=True)
class Run:
    label: str
    agent: str
    dispatch: str
    artifact: Path


@dataclass(frozen=True)
class RunResult:
    run: Run
    status: str
    cost_usd: float


@dataclass(frozen=True)
class Check:
    label: str
    expected: object
    actual: object

    @property
    def passed(self) -> bool:
        return self.expected == self.actual


def gh(*args: str) -> str:
    try:
        done = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as error:
        raise SmokeError(f"gh {' '.join(args)} failed: {error.stderr.strip()}") from error
    return done.stdout


def gh_lines(*args: str) -> list[str]:
    return [line for line in gh(*args).splitlines() if line.strip()]


def check_preconditions() -> None:
    for tool in ("gh", "claude"):
        if shutil.which(tool) is None:
            raise SmokeError(f"{tool} is not on PATH")
    try:
        gh("auth", "status")
    except SmokeError as error:
        raise SmokeError(
            f"{error}. If gh works in your own shell, point GH_CONFIG_DIR at its config folder."
        ) from error


def comment_stream(repo: str, number: int, *, paginate: bool) -> list[str]:
    """Review and issue comments as sorted "<created_at> <login>" lines, as in scorer Step 3."""
    jq = '.[] | "\\(.created_at) \\(.user.login)"'
    page_flag = ["--paginate"] if paginate else []
    lines: list[str] = []
    for kind in ("pulls", "issues"):
        lines += gh_lines("api", *page_flag, f"repos/{repo}/{kind}/{number}/comments", "--jq", jq)
    return sorted(lines)


def last_login(stream: Sequence[str]) -> str:
    return stream[-1].split(" ", 1)[1] if stream else "none"


def fetcher_union(repo: str, user: str) -> set[int]:
    """The PR numbers the fetcher's four Step 2 queries return for one repo."""
    selectors = (
        ["--search", f"review-requested:{user}"],
        ["--assignee", user],
        ["--search", f"mentions:{user}"],
        ["--author", user],
    )
    union: set[int] = set()
    for selector in selectors:
        numbers = gh_lines(
            "pr",
            "list",
            "--repo",
            repo,
            *selector,
            "--json",
            "number",
            "--limit",
            str(FETCH_LIMIT),
            "--jq",
            ".[].number",
        )
        if len(numbers) >= FETCH_LIMIT:
            log.warning(
                "%s %s filled --limit %d; ground truth may be truncated",
                repo,
                selector,
                FETCH_LIMIT,
            )
        union |= {int(number) for number in numbers}
    return union


def build_agents(path: Path) -> None:
    """Write the --agents JSON from the working-tree agent files, so uncommitted edits run."""
    agents: dict[str, dict[str, object]] = {}
    for name in (SCORER, FETCHER):
        text = (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")
        try:
            _, frontmatter, body = text.split("---", 2)
            meta = yaml.safe_load(frontmatter)
        except (ValueError, yaml.YAMLError) as error:
            raise SmokeError(f"cannot parse the frontmatter of {name}.md: {error}") from error
        agents[SMOKE_PREFIX + name] = {
            "description": meta["description"],
            "prompt": body.strip(),
            "tools": [tool.strip() for tool in meta["tools"].split(",")],
            "model": meta["model"],
        }
    path.write_text(json.dumps(agents), encoding="utf-8")
    log.info("built %s from %s", path.name, ", ".join(agents))


def plan_runs(workdir: Path) -> list[Run]:
    def scorer_run(label: str, repo: str, number: int) -> Run:
        artifact = workdir / "pr_info" / f"{repo.replace('/', '_')}_{number}.md"
        dispatch = (
            "Collect triage info for a single PR.\n"
            f"pr_url: https://github.com/{repo}/pull/{number}\n"
            f"github_username: {FETCH_USER}\n"
            f"output_path: {artifact}\n"
            "category: awaiting-review"
        )
        return Run(label, SCORER, dispatch, artifact)

    fetch_artifact = workdir / "pr_data.md"
    fetch_dispatch = (
        "Collect PR data across the target repositories.\n"
        f"repos:\n{FETCH_REPO}\n{ZERO_REPO}\n"
        f"github_username: {FETCH_USER}\n"
        f"output_path: {fetch_artifact}"
    )
    return [
        scorer_run("scorer_size", *SIZE_PR),
        scorer_run("scorer_pagination", *PAGINATION_PR),
        Run("fetcher", FETCHER, fetch_dispatch, fetch_artifact),
    ]


def execute(run: Run, workdir: Path, agents_file: Path, max_usd: float) -> RunResult:
    prompt = (
        f"Dispatch the {SMOKE_PREFIX}{run.agent} agent in the foreground with exactly this prompt "
        f"and nothing else, then report its final STATUS line:\n{run.dispatch}"
    )
    command = [
        "claude",
        "-p",
        prompt,
        "--model",
        SESSION_MODEL,
        "--agents",
        str(agents_file),
        "--allowedTools",
        *SESSION_TOOLS,
        "--max-budget-usd",
        f"{max_usd:.2f}",
        "--no-session-persistence",
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    transcript = workdir / f"{run.label}.jsonl"
    log.info("starting %s", run.label)
    try:
        with transcript.open("w", encoding="utf-8") as out:
            subprocess.run(
                command,
                cwd=workdir,
                stdout=out,
                stderr=subprocess.STDOUT,
                timeout=RUN_TIMEOUT_S,
                check=False,
            )
    except subprocess.TimeoutExpired:
        log.error("%s timed out after %ds", run.label, RUN_TIMEOUT_S)
        return RunResult(run, "TIMEOUT", 0.0)
    return read_result(run, transcript)


def read_result(run: Run, transcript: Path) -> RunResult:
    for line in reversed(transcript.read_text(encoding="utf-8").splitlines()):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result":
            statuses = STATUS_LINE.findall(str(event.get("result", "")))
            status = statuses[-1] if statuses else "NO_STATUS"
            return RunResult(run, status, float(event.get("total_cost_usd", 0.0)))
    log.error("%s left no result event; see %s", run.label, transcript)
    return RunResult(run, "NO_RESULT", 0.0)


def read_artifact(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def fields(text: str) -> dict[str, str]:
    return {match["key"]: match["value"].strip() for match in FIELD_LINE.finditer(text)}


def repo_section(text: str, repo: str) -> str:
    """The body under `### <repo>` up to the next heading of level 3 or above."""
    match = re.search(
        rf"^### {re.escape(repo)}\s*$(?P<body>.*?)(?=^#{{1,3}} |\Z)", text, re.M | re.S
    )
    return match["body"] if match else ""


def scorer_size_checks(text: str) -> list[Check]:
    repo, number = SIZE_PR
    truth = json.loads(
        gh(
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "author,changedFiles,additions,deletions",
        )
    )
    got = fields(text)
    return [
        Check("files_changed", str(truth["changedFiles"]), got.get("files_changed")),
        Check("lines_added", str(truth["additions"]), got.get("lines_added")),
        Check("lines_deleted", str(truth["deletions"]), got.get("lines_deleted")),
        Check("author", truth["author"]["login"], got.get("author")),
    ]


def scorer_pagination_checks(text: str) -> list[Check]:
    repo, number = PAGINATION_PR
    full = comment_stream(repo, number, paginate=True)
    first_page = comment_stream(repo, number, paginate=False)
    if last_login(full) == last_login(first_page):
        log.warning("%s#%d no longer separates paginated from first-page reads", repo, number)
    return [Check("last_commenter", last_login(full), fields(text).get("last_commenter"))]


def fetcher_checks(text: str) -> list[Check]:
    union = fetcher_union(FETCH_REPO, FETCH_USER)
    found = {int(n) for n in TABLE_PR_NUMBER.findall(repo_section(text, FETCH_REPO))}
    total = TOTAL_PRS.search(text)
    zero_truth = fetcher_union(ZERO_REPO, FETCH_USER)
    if zero_truth:
        log.warning(
            "%s now has %d PRs for %s; the zero case is void",
            ZERO_REPO,
            len(zero_truth),
            FETCH_USER,
        )
    return [
        Check(f"{FETCH_REPO} PR numbers", sorted(union), sorted(found)),
        Check("Total PRs found", len(union), int(total["total"]) if total else None),
        Check(
            f"{ZERO_REPO} disclosure",
            True,
            "ZERO RESULTS VERIFIED" in repo_section(text, ZERO_REPO),
        ),
    ]


CHECKS: dict[str, Callable[[str], list[Check]]] = {
    "scorer_size": scorer_size_checks,
    "scorer_pagination": scorer_pagination_checks,
    "fetcher": fetcher_checks,
}


def verdict(result: RunResult) -> list[Check]:
    text = read_artifact(result.run.artifact)
    checks = [Check("status", "DONE", result.status), Check("artifact written", True, bool(text))]
    if text:
        checks += CHECKS[result.run.label](text)
    return checks


def report(results: Sequence[RunResult], workdir: Path) -> bool:
    all_passed = True
    for result in results:
        print(f"\n{result.run.label} (${result.cost_usd:.3f})")
        for check in verdict(result):
            all_passed &= check.passed
            mark = "PASS" if check.passed else "FAIL"
            detail = "" if check.passed else f"  expected {check.expected!r}, got {check.actual!r}"
            print(f"  {mark}  {check.label}{detail}")
    total = sum(result.cost_usd for result in results)
    print(f"\n{'passed' if all_passed else 'FAILED'}; cost ${total:.3f}; artifacts in {workdir}")
    return all_passed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--max-usd-per-run", type=float, default=0.50)
    args = parser.parse_args(argv)
    if args.max_usd_per_run <= 0:
        parser.error("--max-usd-per-run must be positive")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        check_preconditions()
        workdir = Path(tempfile.mkdtemp(prefix="gh_smoke_"))
        agents_file = workdir / "agents.json"
        build_agents(agents_file)
        runs = plan_runs(workdir)
        with ThreadPoolExecutor(max_workers=len(runs)) as pool:
            results = list(
                pool.map(lambda run: execute(run, workdir, agents_file, args.max_usd_per_run), runs)
            )
        return 0 if report(results, workdir) else 1
    except SmokeError as error:
        log.error("%s", error)
        return 2


if __name__ == "__main__":
    sys.exit(main())
