# Phase 3: Final Review, Final Gate and Report

Expand `<PROJECT_ROOT>`, `<SKILL_DIR>`, `<PLUGIN_ROOT>` and `<TASK_DIR>` before every Read, command and dispatch prompt. `DAG`, `dag.sh` and `integrate.sh` are as in run.md. Each repository under `integration` in state has a `start_branch`, a `start_checkout`, an `integration_branch` and a `worktree`; `<base>` below is the basename of its `start_checkout`, so a `--bg` session's own repository keeps its real name instead of its worktree's.

The units are merged. This phase checks each integration branch as a whole, fixes what that check finds when the user says so, and brings each branch into the user's branch only after the final gate. It never pushes.

Every check here runs through its agents, however small the change: the suite through the tooling detector and the test runner, lint and types through the lint runner, benchmarks through the measure runner, and the review as a unit through run.md. Running the tests yourself, or reading the diff in place of the review unit, skips the check this phase exists for. Every git step goes through `integrate.sh`; when it fails, report its message rather than retrying with `git` by hand.

Set `Phase: final`, `phase_complete: false`, and `final_round: 1` unless state already has one. A resumed run starts again at Step 1, which is safe to repeat.

## Step 1: Sync with the start branch

The user's branch may have moved during the run. For each repository, bring it in so the suite and the review see what landing would produce:

1. `integrate.sh merge <worktree> <start_branch> "orch sync <start_branch>"`.
1. `state=up-to-date`: nothing to sync. `state=staged`: leave the merge open for Step 2. Exit 3: resolve it as run.md, Step 4.3, says, with `sync` as the unit id and every merged unit whose `owns` covers a conflicted file; when the resolver fails, `integrate.sh abort <worktree>` and record `sync: conflict` for the repository, which Step 4 lists like a failing test.

## Step 2: Full suite, lint and types

Reuse `<TASK_DIR>/final/<base>/tooling.md` from run.md Step 1; dispatch `mz-dev-pipe:pipeline-tooling-detector` (model as pinned) with `project_root: <worktree>` and that `output_path` only for a repository without one.

The run's files in a repository are those `git -C <worktree> diff --name-only --diff-filter=d <start_branch>...HEAD` prints. Then, in one wave, for each repository:

- When its tooling names a test command, dispatch `mz-dev-pipe:pipeline-test-runner` with `test_command: cd <worktree> && <test command>` and `output_path: <TASK_DIR>/final/<base>/tests_<final_round>.md`. Without one, record `suite: not-run` and ask nothing.
- When it names a lint or format command, dispatch `mz-dev-pipe:pipeline-lint-runner` with `lint_command: cd <worktree> && <lint command>`, `format_command: cd <worktree> && <format command in check mode>`, such as `ruff format --check` or `prettier --check`, `scope_files:` the run's files, and `output_path: <TASK_DIR>/final/<base>/lint_<final_round>.md`. Never pass a format command that rewrites files.
- When it names a type check command, dispatch `mz-dev-pipe:pipeline-lint-runner` with `lint_command: cd <worktree> && <type check command>`, no `format_command`, and `output_path: <TASK_DIR>/final/<base>/types_<final_round>.md`. A type check covers the whole project, since a change in one file breaks types in another.

Emit the wave manifest and rollup in run.md's format, with `Purpose: suite, lint and types per repository`. When a runner returns, read its artifact, not its summary:

- Green, with a sync staged: `integrate.sh conclude <worktree>` and record the new `tip`.
- Red, with a sync staged: `integrate.sh abort <worktree>`; record `suite: red after sync` and the failing tests.
- Red without a sync: record `suite: red` and the failing tests.
- Lint, format or type errors in the run's files: record them as `lint` or `types` findings with `file:line` and rule. Errors in other files were there before the run: record only their count.

**Benchmarks.** After that wave, for each `merged` unit whose skill is `mz-dev-pipe:optimize`, one at a time and with nothing else running, so the numbers don't share the machine: dispatch `mz-dev-pipe:pipeline-measure-runner` with `measure_command: cd <worktree> && <the measurement command from the unit's spec>`, `reps: 10`, `warmup: 3`, `noise_ceiling_cv: 0.10` and `output_path: <TASK_DIR>/final/<base>/bench_<id>_<final_round>.md`. Compare its median with the unit's `result` line and its spec's target. A missed target, or a median worse than the banked value by more than twice the measured CV in the metric's direction, is a `bench` finding: `<id>: <metric> <banked> → <median now>`. `BENCHMARK UNRELIABLE` is reported, not a finding.

## Step 3: Review each integration branch

First run `git -C <worktree> diff --quiet <start_branch>...HEAD` for each repository. Exit 0 means the run changed nothing there (a sync merge alone doesn't count, since the three-dot diff starts at the merge base): record `review: no changes`, which Step 4 treats as a review with no findings, and add no unit for it. A review of an empty diff checks nothing, and a report of one reads like a pass.

For each other repository whose suite isn't red, add a review unit and run it through the normal loop, so it goes to a review-role peer when one fits and to a subagent or a session otherwise:

1. Write `<TASK_DIR>/final/<base>/review_<final_round>.json`:
   `{"id": "FR<final_round>-<base>", "title": "Final review of <base>", "kind": "review", "repo": "<repo>", "skill": "mz-dev-git:review-branch", "owns": [], "verify": "true", "depends_on": [], "backend": "auto", "spec": "<spec>"}`. The spec opens with `Base branch: <start_branch>.`, which review-branch's worker mode diffs against, and says: review every change between `<start_branch>` and this branch's head (`git diff <start_branch>...HEAD`), the work of the whole run, whose plan is `<TASK_DIR>/source_plan.md`; report findings with a severity of `critical`, `major` or `minor`, a `file:line` and a one-line fix; change nothing.
1. `dag.sh DAG add <that file> <REGISTRY>` (leave the registry out when there is none). It prints `lint: ok`.

Then run run.md Steps 2 to 4 until no `FR<final_round>-*` unit is `running` or `pending`, and come back to Step 4 here instead of going on to run.md Step 6. Each report lands at `<TASK_DIR>/units/<id>.md`. A review unit that ends anything but `done` counts as `review: not-run` for its repository, with the reason.

## Step 4: Triage

Collect, per repository: the suite result and failing tests, a sync conflict, lint and type errors in the run's files, `bench` findings, and the review findings by severity. Findings marked `critical` or `major`, every failing test, every lint or type error in the run's files and every `bench` finding are the **open items**; `minor` findings and errors that predate the run are only reported.

No open items in any repository: go to Step 6.

## Step 5: The findings gate

**This orchestrator** presents this gate; it is a variant gate with named actions. Write `<TASK_DIR>/final/findings_<final_round>.md` with, per repository, the suite result with its failing tests, the lint and type errors in the run's files, the `bench` findings, then a table of findings (`severity | file:line | finding | fix`), and the minor findings after it.

**State**: `awaiting approval: findings gate round <final_round>` in `what_remains`.

**Surface 1.** Emit as a chat message:

```text
## Final review, round <final_round>

<verbatim contents of <TASK_DIR>/final/findings_<final_round>.md>

---
**Fix** — add fix units for the open items, run them, then check again; type which items to fix to narrow it  ·  **Continue** — go to the final gate with the open items listed  ·  **Stop** — end here; nothing lands
```

When `final_round` equals `MAX_FINAL_ROUNDS`, leave **Fix** out and say that the fix rounds are used up.

**Surface 2.** AskUserQuestion, question `Round <final_round> found open items. What next?`, header `Findings`, options **Fix**, **Continue** and **Stop** (or **Continue** and **Stop**), each with its one-line summary. Without AskUserQuestion in your tool list, this is **No answer**.

**Response handling**:

- **Fix**, or typed text, which is Fix narrowed to the items it names: dispatch `orchestrate-plan-compiler` (model: **opus**, as pinned) with the Phase 1 compile prompt plus `Fix round <final_round>: add change units with ids FX<final_round>-<n> that fix these items: <the items, verbatim, with their repositories>. At most one unit per repository for tests, bugs, lint and types: mz-dev-pipe:debug for failing tests and bugs, mz-dev-pipe:polish for the rest. A bench finding gets its own mz-dev-pipe:optimize unit with exclusive: true, whose spec repeats the original unit's measurement command, metric and target. Each unit's verify runs that repository's full suite. Keep every existing unit unchanged.` Run `dag.sh DAG lint <REGISTRY>` and show `dag.sh DAG render` in chat. Add a `(review)` line under `## Lessons` for each item that a later plan should avoid. Set `final_round` to one more, `Phase: run`, and continue with run.md Step 2; run.md Step 6 brings the run back to Step 1 here.
- **Continue**: go to Step 6.
- **Stop**: set `landed: no` for every repository and go to Step 7 with `Status: aborted_by_user`.
- **No answer**: `Status: blocked` with the gate in `what_remains`, and stop.

**Unattended** (`unattended: true`): skip both surfaces. Choose **Fix** for every open item when `final_round` is 1, and **Continue** otherwise. Log the choice under `## Auto-approvals` as `<PLUGIN_ROOT>/shared/approval-gate.md`, "Unattended mode", says.

Journal the gate as `<PLUGIN_ROOT>/shared/approval-gate.md` says, with `<TASK_DIR>/final/findings_<final_round>.md` as the artifact.

## Step 6: The final gate

For each repository, decide how it lands. When `start_checkout` is not the repository path this session uses, the session runs in a `--bg` worktree of that repository and may not touch the user's checkout, so landing there is the user's command: `git -C <start_checkout> merge --ff-only <integration_branch>`. Every other repository lands through `integrate.sh land`.

Write `<TASK_DIR>/final_gate.md` with one section per repository: `start_branch` and `start_checkout`; the commits `git -C <worktree> log --oneline <start_branch>..HEAD` prints; the last line of `git -C <worktree> diff --stat <start_branch>...HEAD`; the suite result; lint and type errors in the run's files; each optimize unit's banked and re-measured value; the checkpoints and the fix units they added; open items left; the units that ended `blocked`, `skipped` or `failed`; and how it lands.

**State**: before Surface 1, edit `state.md`: `what_remains: ["awaiting approval: final gate"]`.

**Surface 1.** Emit as a chat message:

```text
## Final gate: <task_name>

<verbatim contents of <TASK_DIR>/final_gate.md>

---
**Approve** → fast-forward each start branch to its integration branch  ·  **Reject** → land nothing and keep the integration branches
```

**Surface 2.** AskUserQuestion, question `The integration branches above are ready to land.`, header `Final gate`, options **Approve** — fast-forward each start branch; never pushes · **Reject** — land nothing, keep the branches. When AskUserQuestion isn't in your tool list, as in a headless run, nobody can answer: that is **No answer** below, so edit `state.md` to `Status: blocked` before you end the turn. Asking for "approve" in prose instead leaves the run marked `running` with nobody to reply.

**Response handling**:

- **Approve**: for each repository that lands through the script, `integrate.sh land <start_checkout> <start_branch> <integration_branch>`:
  - `tip=<sha>`: record `landed: <sha>`, then `integrate.sh cleanup <repo> <worktree> <integration_branch> <start_branch>`, which removes the integration worktree and branch now that the start branch holds them.
  - `merge <start_branch> into <integration_branch> first`: the user committed during the gate. Run Steps 1 and 2 for that repository once more; green lands without asking again; red records `landed: no` with the failing tests.
  - Any other failure, such as a checkout on another branch or uncommitted edits in the way: record `landed: no` with the message and the command for the user. Never force it.
  - For a `--bg` repository, record `landed: user` and keep its integration worktree.
- **Reject**: record `landed: no` for every repository.
- **No answer**: `Status: blocked` with `awaiting approval: final gate`, and stop.

**Unattended**: emit Surface 1 and skip Surface 2, but don't land; landing changes the user's branch, which unattended mode never does. Record `landed: no` and log it under `## Auto-approvals` as not approved.

Journal the gate with `<TASK_DIR>/final_gate.md` as the artifact.

## Step 7: Report and finish

Write `<PROJECT_ROOT>/.mz/reports/<task_name>.md`:

- **Outcome**: one line per repository: `landed <sha> on <start_branch>`, `land it yourself: <command>`, or `not landed: <reason>`, plus the integration branch and worktree that remain.
- **Units**: the output of `dag.sh DAG render`.
- **Final checks**: per repository and round, the suite, lint and type results, the re-measured benchmarks and the review's finding counts by severity, plus each checkpoint with the merge it blamed, if any.
- **Open items**: what is left, with `file:line`, and the minor findings.
- **Concerns**: what workers raised in `DONE_WITH_CONCERNS` results.
- **Kept branches**: failed attempts whose branches and worktrees stay for inspection.

Show the report's Outcome lines in chat with the report's path. Set `Phase: done`, `phase_complete: true`. `Status` is `aborted_by_user` after Abort or Stop, `blocked` when a unit ended `blocked` (its question stays in `what_remains`), and otherwise `complete` with `what_remains: []`.
