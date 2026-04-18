# Phases 5-7: Parallel Review, Iteration, and Finalization

Full detail for the review, rejection-handling, and finalization phases of the optimize skill. Covers dispatching mirrored reviewers per chunk, respawning optimizers on rejection, and writing the final summary.

## Contents

- [Phase 5: Parallel Review](#phase-5-parallel-review)
  - 5.1 Dispatch reviewers
  - 5.2 Collect verdicts
- [Phase 6: Handle Verdicts](#phase-6-handle-verdicts)
  - 6.1 Decision tree
  - 6.2 Borderline verdicts
- [Phase 7: Final Summary](#phase-7-final-summary)
  - 7.1 Final verification
  - 7.2 Write summary
  - 7.3 Report to user

______________________________________________________________________

## Phase 5: Parallel Review

**Goal**: Validate every chunk's optimization against the behavior-preservation contract.

**Initialize `review_iteration = 0` before entering the review loop.** This counter governs the Phase 6 respawn loop bound.

### 5.1 Dispatch reviewers

Spawn M = N `pipeline-code-reviewer` agents (model: **opus**) in a **single message** using parallel tool calls. One reviewer per chunk (1:1 mirror with optimizers).

Each reviewer's prompt:

```
Review the optimization applied to one chunk of a larger optimize pass.

## Chunk: <chunk name>

## Files modified in this chunk
<file list>

## Context
Read .mz/task/<task_name>/scan.md for the chunking rationale and cross-chunk dependencies.
Read .mz/task/<task_name>/baseline.md for pre-optimization test/lint state.
Read .mz/task/<task_name>/optimization_<iteration>.md — specifically the section for this chunk — for what the optimizer claims to have done.
Read .mz/task/<task_name>/verify_<iteration>.md — the code is currently passing tests and lint.

## What to verify
1. **Behavior preservation**: spot-check every removal and simplification. Would any test-observable behavior change? The fact that tests pass is necessary but not sufficient — tests can have coverage gaps.
2. **Dead-code safety**: for anything the optimizer removed as "dead", grep the entire project (not just the chunk) to confirm no references exist. Check direct calls, string references, dynamic dispatch, config files, test files.
3. **Cross-scope edits**: if the optimizer reported cross-scope edits, verify each one is genuinely necessary for the in-chunk optimization to compile or pass tests. Flag any that look like scope creep.
4. **Contract adherence**: did the optimizer stay within the behavior-preserving contract? Any new features, refactors, or public API changes are violations.
5. **Conventions**: do the changes match the project's existing style and patterns?

Read every modified file in this chunk. Do not skip any.

Output:
- **VERDICT**: PASS or FAIL
- **Critical Issues** (must fix): numbered list with file:line references
- **Minor Issues** (nice to fix): numbered list
- **Notes**: observations that don't require changes
```

**Important**: reviewers only run for chunks that were optimized in the current iteration. Previously-approved chunks are frozen and not re-reviewed.

### 5.2 Collect verdicts

After all reviewers complete, merge their verdicts into `.mz/task/<task_name>/review_<iteration>.md`:

```markdown
# Review (Iteration <N>)

## Chunk 1: <name> — PASS / FAIL
<reviewer output>

## Chunk 2: <name> — PASS / FAIL
...

## Summary
- Chunks reviewed this iteration: X
- Chunks PASSED: Y
- Chunks FAILED: Z
- Chunks frozen (previously approved): W
- Rejected chunks for next iteration: <list>
```

______________________________________________________________________

## Phase 6: Handle Verdicts

**Goal**: Decide whether to finalize, iterate, or escalate.

**On re-entry after context compaction, read `review_iteration` from `state.md` before proceeding.** The counter must never be assumed to be in scope from prior phases.

### 6.1 Decision tree

**If ALL chunks PASS** (including frozen ones from prior iterations):

- Update state file phase to `review_passed`
- Proceed to Phase 7

**If ANY chunk FAILS AND `review_iteration < MAX_REVIEW_ITERATIONS`**:

- Increment `review_iteration`
- Build a rejection list: chunk name + consolidated reviewer feedback for each failing chunk
- Go back to **Phase 3** — but dispatch optimizers ONLY for rejected chunks. Previously-approved chunks are frozen.
- Each rejected chunk's optimizer gets its specific reviewer feedback as input.
- After Phase 3 (re-optimize), Phase 4 (re-verify tests), Phase 5 (re-review) run normally for the rejected chunks only.

**If ANY chunk FAILS AND `review_iteration == MAX_REVIEW_ITERATIONS`**:

- Escalate via AskUserQuestion:

```
After <N> review iterations, these chunks still fail review:

<chunk name>:
<unresolved reviewer feedback>

<another chunk>:
...

Options:
1. Revert the rejected chunks' changes entirely and finalize with only the approved chunks
2. Accept the rejected chunks as-is despite the reviewer feedback (NOT recommended)
3. Manually investigate — pause the pipeline
```

### 6.2 Borderline verdicts

If a reviewer returns a PASS with significant "minor issues" OR a FAIL where the critical issues look like style/preference rather than real bugs, **ask the user** via AskUserQuestion rather than auto-deciding. The pipeline should not railroad through subjective reviewer calls.

Example:

```
Reviewer for chunk "<name>" returned a borderline verdict:

<reviewer output>

The critical issues look stylistic rather than behavior-breaking. How should I proceed?
1. Treat as FAIL and iterate
2. Treat as PASS and finalize
3. Fix specific issues only (name them)
```

______________________________________________________________________

## Phase 7: Final Summary

**Goal**: Record what happened and report to the user.

### 7.1 Final verification

Run tests and linters one last time to confirm the final state is still green after the last iteration. If any regression appears at this stage (should not, since Phase 4 ran per iteration), treat it as an escalation — do not try to auto-fix it here; ask the user.

### 7.2 Write summary

Write `.mz/task/<task_name>/summary.md`:

```markdown
# Optimize Summary

**Scope**: <original argument>
**Task directory**: .mz/task/<task_name>/
**Completed**: <timestamp>

## Outcome
- Chunks: N
- Files modified: M
- Review iterations: R
- Fix-loop attempts: F
- Final test status: PASS
- Final lint status: CLEAN

## Chunks
### Chunk 1: <name>
- Files: <count>
- Optimizations applied: <brief list by category>
- Review iterations to pass: X

### Chunk 2: ...

## Cross-Scope Edits
<files touched outside the primary scope, with justification for each>

## Deferred Observations
Cross-chunk duplication and other cleanups that were observed but NOT fixed in this pass, for follow-up:
- <observation>

## Key Decisions
<any non-obvious choices made during the run, especially clarifications from AskUserQuestion prompts>
```

### 7.3 Report to user

Display:

- Path to `summary.md`
- One line per chunk: "Chunk `<name>`: `<N>` files, `<M>` optimizations applied"
- Total files modified across all chunks
- Any deferred observations the user should know about for follow-up work
- Final test and lint status

Update state file status to `completed`.

______________________________________________________________________

## Sub-agent status handling

Follow `skills/shared/agent-status-protocol.md` for the standard 4-status protocol (DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED). Skill-specific overrides are noted inline above where applicable.
