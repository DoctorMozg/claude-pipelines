# Phases 3-4: Implementation and Code Review

Full detail for the implementation and code-review phases of the build skill. Covers parsing work units into execution waves, dispatching parallel coder agents, reviewing the resulting code, and iterating fixes.

## Contents

- [Phase 3: Implementation](#phase-3-implementation)
  - 3.1 Parse work units
  - 3.2 Execute waves
  - 3.3 Collect results
- [Phase 4: Code Review](#phase-4-code-review)
  - 4.1 Review code
  - 4.2 Handle verdict

______________________________________________________________________

## Phase 3: Implementation

**Goal**: Implement the plan using parallel coders where possible.

### 3.1 Parse work units

From the approved plan, extract all work units. Group them into execution waves:

- **Wave 1**: All units marked PARALLEL with no dependencies
- **Wave 2**: Units that depend on Wave 1 outputs
- **Wave N**: Continue until all units scheduled

### 3.2 Execute waves

For each wave, spawn **one agent per work unit** in parallel.

Use `pipeline-coder` agent type for all work units. Model: **opus** for all coders.

Each coder agent prompt:

```
You are implementing one work unit of a larger task.

## Overall Task
<task description>

## Plan
Read the full plan at .mz/task/<task_name>/plan.md for context.

## Your Work Unit
<specific work unit details>

## Instructions
1. Read all files you need to modify BEFORE making changes
2. Implement exactly what the plan specifies for this work unit
3. Follow existing code conventions in the project
4. Add appropriate logging at decision points
5. Do NOT write tests — that's a separate phase
6. Do NOT run linters — that's a separate phase
7. After implementation, list all files you created or modified

Be precise. Don't add features not in the plan. Don't refactor unrelated code.
```

### 3.3 Collect results

After all waves complete, collect the list of all files modified/created across all coders.
Save implementation summary to `.mz/task/<task_name>/implementation.md`.
Update state file phase to `implementation_complete`.

______________________________________________________________________

## Phase 4: Code Review

**Goal**: Catch bugs, architecture issues, and missed requirements.

Set `code_review_iteration = 0`.

**Loop start:**

### 4.1 Review code

Spawn a `pipeline-code-reviewer` agent (model: **opus**) with:

```
Review the implementation of this task:
<task description>

Read the plan at .mz/task/<task_name>/plan.md.
Read the file list at .mz/task/<task_name>/implementation.md.

Review each modified file for:
1. **Correctness** — Does it match the plan? Logic bugs? Off-by-one errors?
2. **Security** — OWASP top 10, input validation, injection risks
3. **Error handling** — Are errors caught and handled properly?
4. **Code quality** — Naming, structure, DRY, SOLID principles
5. **Completeness** — Is anything from the plan missing?
6. **Integration** — Will changes work together? Any conflicts between work units?

Read every file that was modified. Do not skip any.

Output a structured review:
- **VERDICT**: PASS or FAIL
- **Critical Issues** (must fix): numbered list
- **Minor Issues** (should fix): numbered list
- **Notes**: observations that don't need changes
```

Save review to `.mz/task/<task_name>/code_review_<iteration>.md`.

### 4.2 Handle verdict

**If PASS**: proceed to Phase 5.

**If FAIL and code_review_iteration < 3**:

- Increment `code_review_iteration`
- Group critical issues by file/work-unit
- Spawn `pipeline-coder` agents in parallel to fix issues, giving each agent the specific issues for its files
- Each fix agent gets: the review feedback for its files, the plan for context, and instructions to fix ONLY the flagged issues
- **Go to Loop start**

**If FAIL and code_review_iteration >= 3**:

- Use AskUserQuestion to escalate with unresolved issues.

Update state file phase to `code_review_passed`.

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
