# Phases 1-2: Research and Planning

Full detail for the research and planning phases of the build skill. Covers gathering context, generating a detailed implementation plan, running the plan-review loop, and obtaining user approval.

## Contents

- [Phase 1: Research](#phase-1-research)
  - 1.1 Codebase exploration
  - 1.2 Domain research (if needed)
  - 1.3 Save research
- [Phase 2: Planning](#phase-2-planning)
  - 2.1 Generate plan
  - 2.2 Plan review loop
  - 2.3 User approval

______________________________________________________________________

## Phase 1: Research

**Goal**: Gather context about the codebase and domain to inform planning.

### 1.1 Codebase exploration

Spawn a `pipeline-researcher` agent (model: **sonnet**) with:

```
Explore the codebase to understand the context for this task:
<task description>

Focus on:
1. Project structure, key directories, entry points
2. Existing patterns, conventions, and architecture relevant to the task
3. Files that will likely need modification
4. Existing tests and how they're structured
5. Build system, lint commands, test commands
6. Reusable components and utilities

Report structured findings per the agent's output format.
Save nothing — just report findings.
```

### 1.2 Domain research (if needed)

If the task involves external APIs, protocols, libraries, or domain knowledge that isn't obvious from the codebase, spawn a second `pipeline-researcher` agent (model: **sonnet**) with:

```
Research the external domain knowledge needed for this task:
<task description>

Use WebSearch and WebFetch to find:
1. Best practices and common patterns
2. API documentation or protocol specs if applicable
3. Known pitfalls and edge cases
4. Security considerations
5. Performance implications

Report concise, actionable findings. No fluff.
```

Run 1.1 and 1.2 **in parallel** if both are needed.

### 1.3 Save research

Write combined findings to `.mz/task/<task_name>/research.md`.
Update state file phase to `research_complete`.

______________________________________________________________________

## Phase 2: Planning

**Goal**: Create a detailed, actionable implementation plan.

### 2.1 Generate plan

Spawn a `pipeline-planner` agent (model: **opus**) with:

```
You are planning the implementation of this task:
<task description>

Read the research file at .mz/task/<task_name>/research.md for codebase and domain context.

Create a detailed implementation plan with:

1. **Summary** — What we're building and why
2. **Work Units** — Break the implementation into independent, parallelizable units where possible. Each unit should specify:
   - Files to create or modify (with paths)
   - What changes to make (specific enough for a developer to implement without guessing)
   - Dependencies on other work units (if any)
3. **Test Strategy** — What tests to write, what to cover, edge cases
4. **Risk Assessment** — What could go wrong, what to watch out for
5. **Verification Criteria** — How we know the task is truly complete

Mark each work unit as either PARALLEL (can run simultaneously with others) or SEQUENTIAL (depends on prior units).
Be specific about file paths and function signatures. Vague plans waste time.
```

Save output to `.mz/task/<task_name>/plan.md`.

### 2.2 Plan review loop

Set `plan_iteration = 0`.

**Loop start:**

Spawn a `pipeline-plan-reviewer` agent (model: **sonnet**) with:

```
Review this implementation plan for the task: <task description>

Read the plan at .mz/task/<task_name>/plan.md and the research at .mz/task/<task_name>/research.md.

Evaluate:
1. **Completeness** — Does it cover all aspects of the task? Missing pieces?
2. **Correctness** — Are the proposed changes technically sound?
3. **Architecture** — Does it fit the existing codebase patterns? Any anti-patterns?
4. **Parallelizability** — Are work units properly split for parallel execution?
5. **Testability** — Is the test strategy comprehensive? Missing edge cases?
6. **Risk** — Are risks properly identified? Missing any?

Output a structured review:
- **VERDICT**: PASS or FAIL
- **Issues** (if FAIL): numbered list of specific issues to fix
- **Suggestions** (optional): improvements that aren't blockers
```

Save review to `.mz/task/<task_name>/plan_review_<iteration>.md`.

**If PASS**: proceed to Phase 2.3.

**If FAIL and plan_iteration < 3**:

- Increment `plan_iteration`
- Spawn a new `pipeline-planner` agent (model: **opus**) with the original task, research, current plan, AND the review feedback. Ask it to revise the plan addressing all issues.
- Save revised plan to `.mz/task/<task_name>/plan.md` (overwrite)
- **Go to Loop start**

**If FAIL and plan_iteration >= 3**:

- Use AskUserQuestion to escalate: "Plan failed review 3 times. Here are the unresolved issues: <issues>. Please provide guidance."
- Incorporate user guidance and create a final plan revision.

### 2.3 User approval

Use AskUserQuestion to present the final plan to the user:

```
The implementation plan is ready and passed review. Please review and approve:

<contents of plan.md>

Reply 'approve' to proceed, or provide feedback for changes.
```

If the user provides feedback instead of approving, revise the plan accordingly (spawn `pipeline-planner` agent again with feedback) and re-present. Do NOT re-run the review loop — the user's word is final.

Update state file phase to `plan_approved`.
