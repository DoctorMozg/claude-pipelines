# Phases 1-2: Research and Planning

Full detail for the research and planning phases of the build skill. Covers gathering codebase context, assessing feasibility and comparing approaches, optional domain research, generating a detailed plan, running the plan-review loop, and obtaining user approval.

## Contents

- [Phase 1: Research](#phase-1-research)
  - 1.1 Codebase exploration
  - 1.2 Feasibility & approach analysis
  - 1.3 Domain research (if needed)
  - 1.4 Save research
- [Phase 2: Planning](#phase-2-planning)
  - 2.1 Generate plan
  - 2.2 Plan review loop
  - 2.3 User approval

______________________________________________________________________

## Phase 1: Research

**Goal**: Gather codebase context, assess feasibility, compare implementation approaches, and optionally research external domain knowledge.

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
7. Architectural constraints that could limit implementation options
8. Integration points — where new code must connect to existing systems

Report structured findings per the agent's output format.
Save nothing — just report findings.
```

### 1.2 Feasibility & approach analysis

Spawn a `pipeline-researcher` agent (model: **sonnet**) with:

```
Assess feasibility and compare implementation approaches for this task:
<task description>

Use WebSearch and WebFetch to research how others solve similar problems.

Deliver:
1. **Feasibility assessment** — Is this achievable within the project's current architecture?
   What are the hard constraints (language limitations, framework restrictions, dependency conflicts)?
   Are there blockers that would require architectural changes first?

2. **Approach comparison** — Identify 2-3 viable implementation approaches. For each:
   - Brief description (2-3 sentences)
   - Pros (what makes it good)
   - Cons (what makes it risky or costly)
   - Complexity estimate (low / medium / high)
   - Fits existing patterns? (yes / partially / requires new pattern)

3. **Recommended approach** — Pick one and explain why. Reference which pros outweigh which cons.

4. **Risks and unknowns** — What could go wrong? What needs further investigation during planning?

If web search yields relevant comparisons, best practices, or cautionary tales, include them with source URLs.
Report concise findings. No fluff.
```

Run 1.1 and 1.2 **in parallel** — they are independent.

### 1.3 Domain research (if needed)

If the task involves external APIs, protocols, libraries, or domain knowledge that isn't obvious from the codebase, spawn a third `pipeline-researcher` agent (model: **sonnet**) with:

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

**Parallel dispatch**: if domain research is obviously needed (task mentions specific APIs, protocols, or libraries), dispatch 1.1, 1.2, and 1.3 all in parallel. If unclear, dispatch 1.1 and 1.2 first, then decide on 1.3 from their results.

### 1.4 Save research

Write combined findings to `.mz/task/<task_name>/research.md`. Structure:

```markdown
# Research: <task summary>

## Codebase Context
<findings from 1.1>

## Feasibility & Approaches
<findings from 1.2 — including the recommended approach>

## Domain Research
<findings from 1.3, or "Not needed — no external dependencies">
```

Update state file phase to `research_complete`.

______________________________________________________________________

## Phase 2: Planning

**Goal**: Create a detailed, actionable implementation plan.

### 2.1 Generate plan

Spawn a `pipeline-planner` agent (model: **opus**) with:

```
You are planning the implementation of this task:
<task description>

Read the research file at .mz/task/<task_name>/research.md for codebase context, feasibility analysis, and the recommended approach.

Create a detailed implementation plan with:

1. **Chosen Approach** — Which approach from the research you're building on and why. If you deviate from the recommended approach, explain the reasoning. List alternatives considered (from research) so the user can evaluate the choice.
2. **Summary** — What we're building and why
3. **Work Units** — Break the implementation into independent, parallelizable units where possible. Each unit should specify:
   - Files to create or modify (with paths)
   - What changes to make (specific enough for a developer to implement without guessing)
   - Dependencies on other work units (if any)
4. **Test Strategy** — What tests to write, what to cover, edge cases
5. **Risk Assessment** — What could go wrong, what to watch out for. Address risks identified in the feasibility analysis.
6. **Verification Criteria** — How we know the task is truly complete

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
1. **Feasibility** — Is the chosen approach achievable? Does it respect the constraints identified in research? If the plan deviates from the recommended approach, is the reasoning sound?
2. **Completeness** — Does it cover all aspects of the task? Missing pieces?
3. **Correctness** — Are the proposed changes technically sound?
4. **Architecture** — Does it fit the existing codebase patterns? Any anti-patterns?
5. **Parallelizability** — Are work units properly split for parallel execution?
6. **Testability** — Is the test strategy comprehensive? Missing edge cases?
7. **Risk** — Are risks properly identified? Does it address risks from the feasibility analysis?

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

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

Use AskUserQuestion to present the final plan to the user:

```
The implementation plan is ready and passed review. Please review and approve:

<contents of plan.md>

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

Response handling:

- **"approve"** → update state, proceed to next phase.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → incorporate, re-run upstream phase (spawn pipeline-planner with feedback), re-present via AskUserQuestion (same format). This is a loop — repeat until the user explicitly approves. Never proceed without explicit approval.

Do NOT re-run the review loop on feedback — the user's word is final.

Update state file phase to `plan_approved`.
