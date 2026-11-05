# Phases 1-3: Assessment, Quick Fixes, Research

## Phase 1: Initial Assessment

**Goal**: Understand current state — what passes, what fails, what needs fixing.

### 1.1 Run all checks

Execute each criterion's verification command in parallel where possible:

- **Tests**: detect test framework and run relevant tests
- **Linters**: run pre-commit or project linters
- **Custom checks**: grep, file existence, behavioral checks

Record results for each criterion: PASS or FAIL with details. Cleanup and residue criteria have no check of their own; they stay `pending` until Phase 5.

### 1.1.5 Cleanup and residue scope

Skip this step when no criterion is `cleanup` or `residue`. Otherwise, for those criteria:

1. **Resolve the scope to files.** A `scope:` parameter's list is used as is, intersected with any explicit scope in the criterion. Otherwise:

   | Form        | Detection                           | Resolution                                                   |
   | ----------- | ----------------------------------- | ------------------------------------------------------------ |
   | Glob        | Contains `*`, `?`, `[...]`, `{...}` | The files matching the pattern                               |
   | Directory   | Exists on disk                      | Source files below it, honoring `.gitignore`                 |
   | Git range   | `refA..refB` or a valid ref         | `git diff --name-only <range>`, existing files               |
   | Description | None of the above                   | A `pipeline-researcher` (model: **sonnet**) maps it to files |

   When the researcher's confidence is low or it offers several readings, ask the user which one; never guess. Keep source files only: drop generated, vendored and lock files, test files unless the criterion targets tests, and files over 5000 lines (list those for the gate). Save the result to `<PROJECT_ROOT>/.mz/task/<task_name>/cleanup_files.txt`. An empty list goes to the gate as is.

1. **Baseline.** The test and lint runs in 1.1 are the baseline, and Phase 5 needs them green before it touches the scope. A red baseline is written into the assessment, and the gate decides: fix it first as ordinary criteria, or abort.

1. **Blast radius, for cleanup criteria only.** Run `<PLUGIN_ROOT>/shared/blast-radius.md` inline with `cleanup_files.txt` as `input_files` and save its YAML to `<PROJECT_ROOT>/.mz/task/<task_name>/blast_radius.yml`. The assessment carries its verdict and every file with `risk_level >= high`, with its downstream callers. On RISKY or DANGEROUS, say at the gate: "Cleaning up this scope affects N downstream files (verdict: <verdict>). Consider a narrower scope, or `/audit depth:deep` first."

1. **Chunks.** With more than `CHUNK_THRESHOLD` files, group them by directory into at most `MAX_OPTIMIZERS` chunks of similar size. A high-risk file gets a chunk of its own while the cap allows, and files that plainly import each other stay together. With `CHUNK_THRESHOLD` files or fewer there is one chunk.

### 1.2 Triage

Categorize each failing criterion:

| Criterion   | Status    | Failure Type                                                 | Coverage            | Complexity                  |
| ----------- | --------- | ------------------------------------------------------------ | ------------------- | --------------------------- |
| <criterion> | PASS/FAIL | test_failure / lint_error / missing_feature / behavioral_bug | covered / uncovered | simple / moderate / complex |

- **Failure type**:
  - `simple`: formatting, unused import, typo — fix directly without subagent.
  - `moderate`: logic bug, missing error handling — needs a coder agent.
  - `complex`: architectural issue, missing feature, unclear requirement — needs research first.
- **Coverage**: applies to behavioral criteria (`missing_feature`, `behavioral_bug`). Mark `covered` if at least one existing test would fail when the criterion is unmet; otherwise `uncovered`. To check, search for tests referencing the relevant module/function/behavior. When in doubt, mark `uncovered` and let Phase 1.5 expose it to the user.

Behavioral criteria flagged `uncovered` enter the **TDD lane**: in Phase 4, the orchestrator writes the missing test first, verifies it fails, and only then dispatches the coder. This pins the fix against a regression-catching assertion.

### 1.3 Handle unclear criteria

If any criterion is ambiguous or you can't determine how to verify it:

Use AskUserQuestion:

```
I need clarification on these criteria:

1. "<ambiguous criterion>" — How should I verify this? What does "correct" look like?
```

Do not proceed with unclear criteria. Get clarity first.

### 1.4 Save assessment

Write `<PROJECT_ROOT>/.mz/task/<task_name>/assessment.md` with the triage table, all test/lint output, the verification commands for each criterion, and an explicit **TDD lane** section listing every behavioral criterion marked `uncovered`. The Phase 1.5 user approval gate must surface this section so the user knows which fixes will be preceded by a new test.

When 1.1.5 ran, add a **Cleanup** section: the file count and the files left out, the chunk table (chunk, files, why grouped), the baseline status, and for cleanup criteria the blast-radius verdict with each high-risk file. A red baseline goes at the top of this section.

Update state phase to `assessed`.

______________________________________________________________________

## Phase 2: Quick Fixes

**Goal**: Handle all simple failures directly before entering the agent loop.

### 2.1 Apply simple fixes

For each **simple** failure, fix it directly (no agent needed):

- Run formatters (`ruff format`, `clang-format`, etc.)
- Fix unused imports
- Fix trivial lint errors
- Fix obvious typos

### 2.2 Re-run checks

After quick fixes, re-run all failing criteria checks.
Update the criteria checklist in state.md.

If all criteria now pass, counting cleanup and residue criteria as handled by Phase 5, skip to Phase 5 (Optimization & cleanup). Read `phases/fix_review_and_finalize.md` and jump to Phase 5.

______________________________________________________________________

## Phase 3: Research (if needed)

**Goal**: Gather context for moderate/complex failures.

Only enter this phase if there are **complex** failures OR if moderate failures involve code you don't understand.

### 3.1 Codebase exploration

When 3.2 also applies, the two researchers go out together as one wave. Emit the pre-dispatch manifest before spawning either one, and pass each role label as the agent's `description`:

```
Dispatching polish research — 2 agents in parallel
Purpose: root causes and external context for failing criteria
- pipeline-researcher — codebase exploration of failures
- pipeline-researcher — external context research
```

Spawn a `pipeline-researcher` agent (model: **sonnet**) with:

```
I'm polishing existing code to meet these criteria:
<failing criteria with error details>

Explore the codebase to understand:
1. The architecture around the failing code
2. How similar issues are handled elsewhere in the project
3. What the failing tests expect and why they fail
4. Any patterns or conventions relevant to the fixes

Report:
- Root cause analysis for each failure
- Relevant files and their roles
- Suggested fix approaches
- Any risks or dependencies

Save nothing — just report findings.
```

### 3.2 Domain research (if complex failures involve external knowledge)

Spawn a second `pipeline-researcher` agent (model: **sonnet**) in parallel if needed:

```
Research external context for these issues:
<complex failure descriptions>

Focus on:
1. Correct behavior/API usage for the failing functionality
2. Known issues or gotchas
3. Best practices for the fix approach

Report concise, actionable findings.
```

**Minimalism gate.** When proposing fix approaches above, climb the minimalism ladder: prefer deleting code or using a standard-library / native / already-installed-dependency solution over writing new custom code, and don't introduce an abstraction a single fix doesn't yet need. For a non-trivial fix, web-validate the approach before writing it. Code health — validation, error handling, security, tests — is exempt. See `<PLUGIN_ROOT>/shared/minimalism.md`.

### 3.3 Save research

When both researchers ran, emit the post-wave rollup once both have reported:

```
Wave complete (polish research) — <returned>/<dispatched> agents returned
- pipeline-researcher: <STATUS> — <summary, ≤8 words>
```

An agent that returns no `STATUS:` line is listed as `NO RETURN BLOCK` and counted as not-returned.

Write findings to `<PROJECT_ROOT>/.mz/task/<task_name>/research.md`.
Update state phase to `researched`.

Proceed to Phase 4. Read `phases/fix_review_and_finalize.md`.
