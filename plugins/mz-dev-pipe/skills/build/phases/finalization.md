# Phases 8-10: Final Review, Optimization, and Completeness Check

Full detail for the finalization phases of the build skill. Covers the final code review over all changes, post-completion optimization with verification, and the completeness gate that can restart the pipeline from an earlier phase if the task was not fully delivered.

## Contents

- [Phase 8: Final Code Review](#phase-8-final-code-review)
- [Phase 9: Optimization](#phase-9-optimization)
  - 9.1 Optimize
  - 9.2 Verify after optimization
  - 9.3 Review optimization
- [Phase 10: Completeness Check](#phase-10-completeness-check)
  - 10.1 Handle verdict

______________________________________________________________________

## Phase 8: Final Code Review

**Goal**: One last validation pass over ALL code (implementation + tests) together.

Spawn a `pipeline-code-reviewer` agent (model: **opus**) with:

```
Perform a FINAL review of ALL changes for this task:

## Task: <task description>

Read the plan at .mz/task/<task_name>/plan.md.
Read the file lists at .mz/task/<task_name>/implementation.md and .mz/task/<task_name>/tests.md.

Review ALL modified and created files (both implementation and tests).

This is the last gate before the task is declared complete. Check:
1. Implementation matches the plan completely
2. No dead code, unused imports, or debug artifacts
3. Code and tests are consistent with each other
4. No regressions to existing functionality
5. All reviewer feedback from previous rounds has been addressed

Output:
- **VERDICT**: PASS or FAIL
- **Issues** (if FAIL): numbered list with file:line references
```

**If FAIL**: Spawn `pipeline-coder` agent(s) to fix issues, then re-run linters and tests (Phase 7.2-7.4), then re-do this final review. Max 2 retries before escalating.

Update state file phase to `final_review_passed`.

______________________________________________________________________

## Phase 9: Optimization

**Goal**: Clean up the implementation — remove dead code, debug artifacts, unused imports, and unnecessary complexity.

### 9.1 Optimize

Spawn a `pipeline-optimizer` agent (model: **opus**) with:

```
Optimize the code that was implemented for this task.

## Scope
Read .mz/task/<task_name>/implementation.md and .mz/task/<task_name>/tests.md for the list of all files created or modified.

ONLY optimize these files. Do not touch other files.

Work through your full optimization checklist:
1. Debug artifacts (print statements, commented-out code, TODOs)
2. Dead code (unused functions, unreachable blocks)
3. Unused imports
4. Code duplication (within the modified files only)
5. Unnecessary complexity
6. Consistency

Report all changes made.
```

Save report to `.mz/task/<task_name>/optimization.md`.

### 9.2 Verify after optimization

Re-run linters and tests to ensure optimization didn't break anything.

**If any test regressed**: identify which optimization caused the regression from the report, revert that specific change, and re-run checks.

### 9.3 Review optimization

Spawn a `pipeline-code-reviewer` agent (model: **sonnet**) with: <!-- sonnet: heuristic structural pass checking only for behavioral drift introduced by the optimizer over already-opus-reviewed code, not full correctness; opus not required here -->

```
Review the optimization changes made to this code.

The code was functionally complete and passing all tests and reviews before optimization.
Read .mz/task/<task_name>/optimization.md for what was changed.

Verify that:
1. No behavior was changed
2. Removals are genuinely dead (grep-verified, not just seemingly unused)
3. Simplifications are correct

Read all modified files and spot-check removals.

## VERDICT: PASS | FAIL
```

**If FAIL**: Spawn `pipeline-coder` to fix issues, re-run checks. Max 2 retries before escalating.

Update state file phase to `optimized`.

______________________________________________________________________

## Phase 10: Completeness Check

**Goal**: Verify the task is truly, fully complete.

Spawn a `pipeline-completeness-checker` agent (model: **opus**) with:

```
You are the final quality gate for a development task. Determine if the task is FULLY COMPLETE.

## Original Task
<task description>

## Context Files
Read the following files for context:
- .mz/task/<task_name>/plan.md (implementation plan)
- .mz/task/<task_name>/research.md (research findings)
- .mz/task/<task_name>/implementation.md (implementation file list)
- .mz/task/<task_name>/tests.md (test file list)

## Current State
- Linters: PASSING
- Tests: PASSING
- Code review: PASSED
- Test review: PASSED

output_path: .mz/task/<task_name>/completeness_check.md

Evaluate:
1. Does the implementation fulfill 100% of what was requested in the task description?
2. Are there any aspects of the task that were planned but not implemented?
3. Are there any aspects of the task that weren't even planned?
4. Would a user/stakeholder consider this task DONE?

Output:
- **VERDICT**: PASS (task complete) or FAIL (task incomplete)
- If FAIL:
  - **Missing items**: what's not done
  - **Restart phase**: which phase to restart from (research/plan/code/test)
  - **Reason**: why that phase needs re-running
```

### 10.1 Handle verdict

**Check the completeness-checker's STATUS first, before reading any artifact.**

1. **If STATUS is `BLOCKED`**: escalate immediately via AskUserQuestion with the blocker details. Do NOT attempt to read `completeness_check.md` — the agent may not have produced it, and reading a missing or partial artifact leads to silent misjudgment. Do not restart the pipeline — restarting against a blocked state wastes all retry budget.
1. **If STATUS is `NEEDS_CONTEXT`**: re-dispatch the completeness-checker once with the requested context, then re-check STATUS from the beginning of this step.
1. **If STATUS is `DONE` or `DONE_WITH_CONCERNS`**: read `.mz/task/<task_name>/completeness_check.md` as the authoritative verdict, rather than parsing the inline response. Then apply the PASS/FAIL handling below.

**If PASS**:

- Update state file status to `completed`
- Write a summary to `.mz/task/<task_name>/summary.md` listing all files changed, tests added, and key decisions
- Report to user: task is complete, here's what was done

**If FAIL**:

- Update state file with the restart phase and reason
- Jump to the indicated phase and re-execute from there
- Carry forward all existing artifacts — don't delete previous work
- Increment the top-level iteration counter in state.md
- If top-level iterations exceed 2, escalate to user instead of restarting
