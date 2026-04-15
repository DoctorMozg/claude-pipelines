# Phases 3-4: Parallel Optimization and Verify

Full detail for the optimization and verification phases of the optimize skill. Covers dispatching parallel optimizer agents per chunk and running the inner fix loop that restores green state before review.

## Contents

- [Phase 3: Parallel Optimization](#phase-3-parallel-optimization)
  - 3.1 Dispatch optimizers
  - 3.2 Collect reports and detect conflicts
- [Phase 4: Verify & Auto-Fix](#phase-4-verify--auto-fix)
  - 4.1 Run tests and linters
  - 4.2 Inner fix loop
  - 4.3 Final green check

______________________________________________________________________

## Phase 3: Parallel Optimization

**Goal**: Apply optimizations across all chunks simultaneously.

Set `iteration` to the current review iteration (starts at 0; increments when the rejection loop re-enters Phase 3).

### 3.1 Dispatch optimizers

Spawn N `pipeline-optimizer` agents (model: **opus**) in a **single message** using parallel tool calls. One agent per chunk.

Each optimizer's prompt:

```
You are optimizing one chunk of a scoped optimization pass.

## Chunk: <chunk name>
Files: <exact file list>

Read .mz/task/<task_name>/scan.md for chunking breakdown and cross-chunk warnings.
Read .mz/task/<task_name>/baseline.md for pre-optimization test/lint state.

## Rules
1. Work through your full optimization checklist on these files.
2. OWN the files above. If you MUST edit a file in another chunk or outside scope to keep code compiling, report it in a "Cross-Scope Edits" section with the reason.
3. Never change test-observable behavior.
4. Grep before removing — verify "dead code" is unreferenced across the full project.
```

**If this is a rejection re-run** (iteration > 0, dispatched for rejected chunks only): include in the prompt the specific reviewer feedback for this chunk from `review_<iteration-1>.md`, and instruct the optimizer to address that feedback while preserving any changes that were already approved.

Do NOT dispatch optimizers for chunks that previously passed review — they are frozen for the remainder of this run.

### 3.2 Collect reports and detect conflicts

After all optimizers complete, merge their reports into `.mz/task/<task_name>/optimization_<iteration>.md`:

```markdown
# Optimization Report (Iteration <N>)

## Chunk 1: <name>
<pipeline-optimizer report>

### Cross-Scope Edits
- <file outside chunk>: <reason>

## Chunk 2: <name>
...

## Conflicts Detected
- <file> was edited by both Chunk A and Chunk B — see resolution below
```

**Conflict detection**: if any file was edited by more than one optimizer in this wave (possible only via cross-scope edits), mark the conflict. Two resolution paths:

- **No content conflict** (both edits applied cleanly because they touched different lines): record the conflict as a warning only, no action needed.
- **Content conflict** (the second optimizer's Edit failed because the first changed the file, or the merged result is broken): revert the affected file to its pre-iteration state and mark both chunks to re-run sequentially in the next iteration.

Update state file with the cumulative list of files modified so far.

______________________________________________________________________

## Phase 4: Verify & Auto-Fix

**Goal**: Restore green state after the optimization batch. Never enter review on a red build.

### 4.1 Run tests and linters

Dispatch `pipeline-test-runner` and `pipeline-lint-runner` in parallel (single message, two agent calls):

```
Run tests to check for regressions after optimization.
test_command: <Test command from .mz/task/<task_name>/tooling.md>
output_path: .mz/task/<task_name>/verify_test_results_<iteration>.md
```

```
Run linters to check for regressions after optimization.
lint_command: <Lint command from .mz/task/<task_name>/tooling.md, or "none detected">
output_path: .mz/task/<task_name>/verify_lint_results_<iteration>.md
```

Read both artifacts. Compare against `baseline.md`:

- **Tests**: does the pass/fail set match the baseline? Any NEW failing test is a regression.
- **Lint**: is the error/warning count ≤ baseline?

**If green** (no regressions from baseline): write `verify_<iteration>.md`, update state to `verified_green`, proceed to Phase 5.

**If regressed**: enter the inner fix loop (4.2).

### 4.2 Inner fix loop

Set `fix_attempt = 0`.

**Loop start**:

1. Increment `fix_attempt`.

1. Identify which optimizer's changes most likely caused the regression:

   - Match failing test names to files in specific chunks via the import graph
   - Read the optimization reports for the prime suspects
   - If multiple chunks could be responsible, pick the one with the most changes to files referenced by the failing tests

1. Dispatch a `pipeline-coder` agent (model: **opus**) with:

```
A regression was introduced during code optimization. Fix it while preserving the optimization.

## Regression
<failing test output, lint errors>

## Suspected Cause
<optimization report excerpt for suspect chunk>
Read .mz/task/<task_name>/optimization_<iteration>.md for full report.

## Instructions
1. Read failing tests and modified files to understand the break
2. Prefer adjusting the optimization to preserve behavior over full revert
3. If optimization is fundamentally unsafe, revert ONLY that specific change
4. No NEW optimizations — regression repair only
```

4. Re-run tests and linters.

1. If green → exit the inner loop, proceed to Phase 4.3.

1. If still red AND `fix_attempt < MAX_FIX_ATTEMPTS` → go to **Loop start**.

1. If still red AND `fix_attempt == MAX_FIX_ATTEMPTS` → escalate via AskUserQuestion:

```
Optimization caused a regression that couldn't be auto-fixed after <N> attempts.

Failing tests / lint:
<output>

Optimizations applied this iteration:
<summary>

Options:
1. Revert the entire optimization batch and restart
2. Revert only specific chunks (name them)
3. Accept the regression and proceed (NOT recommended)
4. Pause for manual investigation
```

### 4.3 Final green check

Once the inner loop exits green, re-confirm:

- Tests match the baseline pass/fail set (no new failures)
- Lint count ≤ baseline

Write `.mz/task/<task_name>/verify_<iteration>.md`:

```markdown
# Verify (Iteration <N>)

## Test Result
- Result: PASS (matches baseline)
- Regressions fixed: <count>

## Lint Result
- Result: CLEAN / <count> issues (≤ baseline)

## Fix Loop
- Attempts used: <N>
- Chunks partially reverted: <list, if any>
- Optimizations preserved: <summary>
```

Update state file phase to `verified_green`.

______________________________________________________________________

## Sub-agent status handling

Review verdict parsing:

- `VERDICT: PASS` — proceed. A review is PASS if it contains zero `Critical:` findings, regardless of the count of `Nit:`, `Optional:`, or `FYI` entries.
- `VERDICT: FAIL` — loop back and fix. Only `Critical:` findings block.

Coder/planner status handling (four-status protocol):

- `DONE` — proceed to the next step.
- `DONE_WITH_CONCERNS` — log the concern block to `.mz/task/<task_name>/state.md` under a `## Concerns` heading, then proceed.
- `NEEDS_CONTEXT` — re-dispatch the coder with the additional context included in the new prompt. Do not proceed to the next step until the coder returns with `DONE` or `DONE_WITH_CONCERNS`.
- `BLOCKED` — escalate to the user via AskUserQuestion with the blocker details. Never auto-retry the same operation. Wait for user direction or abort.
