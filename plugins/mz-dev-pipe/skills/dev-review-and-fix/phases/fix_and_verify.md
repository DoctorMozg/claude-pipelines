# Phases 4-6: Chunk Findings, Parallel Fix, and Verify

Full detail for the fix-dispatch phases of the dev-review-and-fix skill. Covers grouping approved findings into parallel-safe chunks, dispatching coder agents with the strict "trivially adjacent" fix rule, and the inner verification loop that restores green state before review.

## Contents

- [Phase 4: Chunk Findings](#phase-4-chunk-findings)
  - 4.1 Group by affected file
  - 4.2 Schedule waves
- [Phase 5: Parallel Fix](#phase-5-parallel-fix)
  - 5.1 Dispatch coders
  - 5.2 The "trivially adjacent" rule
  - 5.3 Collect reports
- [Phase 6: Verify & Auto-Fix](#phase-6-verify--auto-fix)
  - 6.1 Run tests and linters
  - 6.2 Inner fix loop
  - 6.3 Final green check

______________________________________________________________________

## Phase 4: Chunk Findings

**Goal**: Turn the approved findings list into a set of parallel-safe work chunks for the coders.

### 4.1 Group by affected file

**Rule**: all findings that touch the same file must be fixed by the same coder. This avoids parallel-write conflicts on the Edit tool — two coders editing the same file concurrently will have stale string state.

Walk the approved findings list:

1. Build a map: `file_path → [finding_ids]`
1. Each unique file becomes one chunk
1. A chunk's size is its finding count (not its file LOC)

**Cross-file findings**: if a single finding requires edits to multiple files (e.g., "rename API X and update all N callers"), the chunk includes all those files. That chunk is then locked — no other chunk can include any of those files. Detect this at chunk-assembly time by checking `cross_references` on each finding.

### 4.2 Schedule waves

**Rule**: wave size ≤ `MAX_CODERS = 6`.

- If total chunks ≤ 6 → 1 wave, all chunks in parallel
- If total chunks > 6 → multiple sequential waves of up to 6 chunks each

**Wave ordering**: prioritize waves containing the most critical findings first. This gives the user a green build covering the most important fixes as early as possible — if the pipeline has to escalate later, the worst bugs are already fixed.

Within a wave, there is no ordering — all chunks run in parallel.

Write `.mz/task/<task_name>/chunks.md`:

```markdown
# Fix Chunks

## Wave 1 (contains <N> critical findings)
### Chunk 1: path/to/file_a.py
- Findings: F1, F4, F7
- Severities: critical, high, medium
- Cross-file: no

### Chunk 2: path/to/file_b.py
- Findings: F2
- Severities: critical
- Cross-file: no

...

## Wave 2
...

## Summary
- Total chunks: C
- Waves: W
- Cross-file chunks: X
```

Update state file phase to `chunked`.

______________________________________________________________________

## Phase 5: Parallel Fix

**Goal**: Apply fixes for all approved findings across chunks in parallel waves.

Set `iteration = 0` at first entry; increment only when the rejection loop in Phase 8 re-enters this phase.

### 5.1 Dispatch coders

For each wave, spawn up to 6 `pipeline-coder` agents (model: **opus**) in a **single message** using parallel tool calls. One agent per chunk.

Each coder's prompt:

````
You are fixing specific bugs and improvement findings in one file (or small file group) as part of a larger codebase audit.

## Chunk: <chunk name / primary file>

## Files you own for this chunk
<file list — you may edit ONLY these files>

## Context
Read .mz/task/<task_name>/scope.md for the overall audit context.
Read .mz/task/<task_name>/findings.md for the full finding list (all chunks).
Read .mz/task/<task_name>/chunks.md to confirm your chunk's scope.

## Your findings to fix
<list of findings for this chunk, with full details from findings.md>

For each finding:
- <F<id>>: <file:line> — <description>
  - Proposed fix: <from findings.md>

## Instructions
1. Read every file in your chunk BEFORE making changes.
2. Fix each approved finding using its proposed fix as guidance. You may deviate from the proposed fix if you find a better approach while preserving the same behavior change.
3. Apply the **trivially adjacent** rule (see below) for adjacent obvious bugs.
4. Do NOT fix anything outside your chunk's files.
5. Do NOT introduce new features, new abstractions, new dependencies, or refactor unrelated code.
6. Do NOT add or modify tests — test changes happen in a later phase.
7. After applying fixes, list every change you made in your report (both approved findings and any trivial-adjacent fixes).

## The "trivially adjacent" rule
While fixing an approved finding, you MAY fix additional bugs ONLY if ALL of these hold:
- The additional bug is in the SAME FUNCTION BODY as the approved fix
- The bug is obvious: null-pointer miss, typo, clear off-by-one, wrong variable name, missing guard on an impossible branch
- The fix requires NO new imports, NO new helpers, NO new tests
- The fix is ≤ 5 lines of code change
- A senior engineer doing a code review of the approved fix would also flag this adjacent bug

You MUST report every trivial-adjacent fix in a dedicated "Trivial Adjacent Fixes" section of your output. Reviewers will validate that each one genuinely meets the rule.

You may NOT:
- Fix bugs in sibling functions or other functions in the file
- Refactor the function structure
- Rename things
- Add error handling broader than one line
- Improve performance
- Fix code style issues the formatter would catch

If you see OTHER problems that don't meet the trivially-adjacent criteria, list them in a "Observed Additional Issues" section. The orchestrator will feed these back to the user as potential follow-up findings. Do NOT fix them.

## Output format
```markdown
# Coder Report — Chunk <name>

## Approved Findings Fixed
### F<id> — <file:line>
- **Change**: <what you modified>
- **Why your approach**: <if you deviated from the proposed fix>

### F<id> — ...

## Trivial Adjacent Fixes
### TA1 — <file:line>
- **Context**: fixing F<approved_id>
- **Bug found**: <description>
- **Why it qualifies as trivially adjacent**: <reason matching all 5 rules>
- **Change**: <what you modified>

### TA2 — ...

## Observed Additional Issues (not fixed)
### OA1 — <file:line>
- **Description**: <what you saw>
- **Why not fixed**: <doesn't meet trivial-adjacent criteria>

## Files Modified
- <file_a>
- <file_b>
````

````

**If this is a rejection re-run** (iteration > 0): include in the prompt the specific reviewer feedback for this chunk from `review_<iteration-1>.md`, and instruct the coder to address that feedback alongside any findings that weren't previously resolved.

Do NOT dispatch coders for chunks that previously passed review — they are frozen.

### 5.2 The "trivially adjacent" rule

This rule is repeated in the coder prompt above because it's the critical guard against scope creep. In summary: same function body, obvious bug, no new imports / helpers / tests, ≤ 5 lines of change, and a senior engineer reviewing the approved fix would also catch it. Reviewers in Phase 7 validate every trivial-adjacent fix against these criteria and will FAIL a chunk that abused the rule.

### 5.3 Collect reports

After all coders in a wave complete, merge their reports into `.mz/task/<task_name>/fixes_<iteration>.md`:

```markdown
# Fixes (Iteration <N>)

## Wave 1

### Chunk 1: <name>
<coder report>

### Chunk 2: <name>
<coder report>

## Wave 2
...

## Cumulative Changes
- Files modified: <list>
- Approved findings fixed: <F_ids>
- Trivial-adjacent fixes: <TA_ids>
- Observed additional issues: <OA_ids> — deferred to summary
````

Update state file with the cumulative list of files modified.

Run all waves sequentially before proceeding to Phase 6. Do not verify between waves — wave-level verification is expensive and the cumulative changes are small enough that a single verification pass after all waves is sufficient.

______________________________________________________________________

## Phase 6: Verify & Auto-Fix

**Goal**: Restore green state after the fix batch. Never enter review on a red build.

### 6.1 Run tests and linters

Detect and run:

- Project test command (pytest, jest, cargo test, go test, etc.)
- Project lint command (pre-commit, ruff, eslint, clippy, etc.)

Capture baseline to compare: the pre-fix test state may have had some failures (unlike dev-optimize, the scope here is bug hunting, so failing tests may be expected). Use git stash or a separate comparison:

- **Before any fixes were applied**: run tests once to capture the pre-fix state into `.mz/task/<task_name>/pre_fix_tests.md` — this happens once at the START of Phase 6 on iteration 0, not on every iteration.
- **After fixes**: compare to pre-fix state.
  - Tests that were failing and are now passing → good (fix worked)
  - Tests that were passing and are now failing → regression (must fix)
  - Tests that were failing and still fail → neutral (fix may not be complete; log but do not block)
  - Tests that were passing and still pass → good

**Lint**: error count must not exceed pre-fix count. Warnings are tolerated.

**If no regressions**: write `verify_<iteration>.md`, update state to `verified_green`, proceed to Phase 7.

**If regressions**: enter the inner fix loop (6.2).

### 6.2 Inner fix loop

Set `fix_attempt = 0`.

**Loop start**:

1. Increment `fix_attempt`.

1. Identify which chunk's changes most likely caused the regression:

   - Match failing test names and file paths to specific chunks
   - Read the coder reports for the prime suspects
   - If multiple chunks could be responsible, pick the one with the most changes to files referenced by the failing tests

1. Dispatch a `pipeline-coder` agent (model: **opus**) with:

```
A regression was introduced during a bug-fix pass. Fix it while preserving as much of the original fix as possible.

## Original Task
Fixing audit findings on <scope>.

## Regression
<failing test output, lint errors that exceed pre-fix>

## Suspected Cause
The following coder report contains the changes most likely responsible:
<coder report excerpt for the suspect chunk>

Read .mz/task/<task_name>/fixes_<iteration>.md for the full fix report.
Read .mz/task/<task_name>/pre_fix_tests.md for the pre-fix test state (so you know what was already failing).

## Instructions
1. Read the failing tests and the modified files to understand the break.
2. Identify the minimal change needed to restore green (within the pre-fix failure set).
3. Prefer adjusting the fix to still resolve the original finding AND not regress anything. Reverting the fix should be a last resort.
4. Do not introduce NEW fixes for findings that weren't in this chunk.
5. Report what you changed and why.
```

4. Re-run tests and linters.

1. If green (matches or improves pre-fix state) → exit the inner loop, proceed to Phase 6.3.

1. If still regressed AND `fix_attempt < MAX_FIX_ATTEMPTS` → go to **Loop start**.

1. If still regressed AND `fix_attempt == MAX_FIX_ATTEMPTS` → escalate via AskUserQuestion:

```
A fix introduced a regression that couldn't be auto-repaired after <N> attempts.

Pre-fix test state:
<summary>

Current failing tests:
<list>

Fixes applied this iteration:
<summary>

Options:
1. Revert the entire batch of fixes for this chunk
2. Revert the entire iteration and restart
3. Accept the regression and proceed (NOT recommended)
4. Pause for manual investigation
```

### 6.3 Final green check

Once the inner loop exits green, re-confirm:

- Test state is ≤ pre-fix failures (no new red)
- Lint error count ≤ pre-fix count

Write `.mz/task/<task_name>/verify_<iteration>.md`:

```markdown
# Verify (Iteration <N>)

## Pre-fix state
- Failing tests: <count> — <list>
- Lint errors: <count>

## Post-fix state
- Failing tests: <count> — <list>
- Lint errors: <count>

## Delta
- Tests now passing that were failing: <list> ← fixes working
- Tests still failing (pre-existing): <list>
- NEW regressions: <list> ← must be empty before proceeding

## Fix loop
- Attempts used: <N>
- Chunks partially reverted: <list, if any>
```

Update state file phase to `verified_green`.
