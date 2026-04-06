# Phases 3-4: Parallel Optimization and Verify

Full detail for the optimization and verification phases of the dev-optimize skill. Covers dispatching parallel optimizer agents per chunk and running the inner fix loop that restores green state before review.

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
You are optimizing one chunk of a larger scoped optimization pass.

## Chunk: <chunk name>

## Files in your scope
<exact file list for this chunk>

## Context
Read .mz/task/<task_name>/scan.md for the full chunking breakdown and cross-chunk dependency warnings.
Read .mz/task/<task_name>/baseline.md for the pre-optimization test/lint state.

## Rules
1. Work through your full optimization checklist on the files in your chunk.
2. **Strict within-chunk ownership**: you OWN the files listed above. Prefer to edit only these files.
3. **Cross-chunk / out-of-scope exception**: if an optimization in your chunk requires editing a file that is (a) listed in another chunk or (b) entirely outside the dev-optimize scope — to keep the code compiling and passing tests — you MAY edit that file. You MUST report such edits explicitly in a "Cross-Scope Edits" section at the end of your report, including the reason the edit was necessary.
4. **Behavior preservation**: never change test-observable behavior. If in doubt, don't touch it.
5. **Grep before removing**: verify any "dead code" is actually unreferenced across the entire project, not just within your chunk. Check imports, string references, dynamic dispatch, config files, and test files.
6. Report all changes in the standard pipeline-optimizer format, plus the "Cross-Scope Edits" section.
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

Run the exact same commands captured in `baseline.md`. Compare results:

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
A regression was introduced during code optimization. Fix it while preserving as much of the optimization as possible.

## Original Task
Optimization pass on <scope>.

## Regression
<failing test output, lint errors>

## Suspected Cause
The following optimizer report contains the changes most likely responsible:
<optimization report excerpt for the suspect chunk>

Read .mz/task/<task_name>/optimization_<iteration>.md for the full report.

## Instructions
1. Read the failing tests and the modified files to understand the break.
2. Identify the minimal change needed to restore green state.
3. Prefer adjusting the optimization so it still preserves behavior over reverting it entirely.
4. If the optimization is fundamentally unsafe, revert ONLY that specific change and document why.
5. Do not introduce NEW optimizations. Your job is regression repair only.
6. Report what you changed and why.
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
