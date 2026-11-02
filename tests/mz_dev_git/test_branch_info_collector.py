import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS = REPO_ROOT / "plugins/mz-dev-git/agents"
COLLECTOR = AGENTS / "branch-info-collector.md"
BRANCH_REVIEWER = AGENTS / "branch-reviewer.md"
PR_REVIEWER = AGENTS / "github-pr-reviewer.md"

SHELL_FENCE = re.compile(r"^```(?:bash|sh|shell)\n(.*?)^```", re.S | re.M)
# A git command word, not part of a path such as `.git/` or a name such as `git-foo`.
GIT_CALL = re.compile(r"(?<![\w./$-])git(?=\s)")
INPUT_FIELD = re.compile(r"^- `(\w+)`:", re.M)
PROMPT_FIELD = re.compile(r"^(\w+): (\S+)$", re.M)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    match = re.search(rf"^{re.escape(start)}.*?(?=^{re.escape(end)})", text, re.S | re.M)
    assert match, f"section {start!r} not found"
    return match.group(0)


def _dispatch_prompt(text: str, agent: str) -> dict[str, str]:
    """Fields of the first fenced prompt after the line that dispatches `agent`."""
    match = re.search(rf"Dispatch (?:a|the) `{agent}`.*?^```\n(.*?)^```", text, re.S | re.M)
    assert match, f"no dispatch prompt for {agent}"
    return dict(PROMPT_FIELD.findall(match.group(1)))


def _collector_inputs() -> list[str]:
    return INPUT_FIELD.findall(_section(_read(COLLECTOR), "### Step 1", "### Step 2"))


class TestCollectorTargetsRepoRoot:
    def test_collector_declares_repo_root_input(self) -> None:
        assert "repo_root" in _collector_inputs()

    def test_every_git_call_in_shell_blocks_runs_against_repo_root(self) -> None:
        targeted = re.compile(r'\s+-C\s+"<repo_root>"\s')
        blocks = SHELL_FENCE.findall(_read(COLLECTOR))
        calls = [call for block in blocks for call in GIT_CALL.finditer(block)]
        assert calls, "no git calls found in the collector's shell blocks"
        stray = [
            call.string[call.start() :].splitlines()[0]
            for call in calls
            if not targeted.match(call.string, call.end())
        ]
        assert stray == []


class TestDispatchersPassTheReviewedCheckout:
    def test_branch_reviewer_sets_every_collector_input(self) -> None:
        prompt = _dispatch_prompt(_read(BRANCH_REVIEWER), "branch-info-collector")
        assert set(_collector_inputs()) <= prompt.keys()

    def test_branch_reviewer_passes_the_root_its_own_git_calls_use(self) -> None:
        text = _read(BRANCH_REVIEWER)
        code_roots = set(re.findall(r'git -C "(\$\w+)"', text))
        assert len(code_roots) == 1, code_roots
        assert _dispatch_prompt(text, "branch-info-collector")["repo_root"] in code_roots

    def test_pr_reviewer_points_branch_reviewer_at_its_worktree(self) -> None:
        text = _read(PR_REVIEWER)
        worktree = re.search(r"worktree add --detach (\$\w+)", text)
        assert worktree, "github-pr-reviewer creates no worktree"
        reviewer_inputs = INPUT_FIELD.findall(_read(BRANCH_REVIEWER))
        prompt = _dispatch_prompt(text, "branch-reviewer")
        assert "code_root" in reviewer_inputs
        assert prompt["code_root"] == worktree.group(1)
