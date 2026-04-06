---
name: dev-review-and-fix
description: Multi-lens bug and improvement hunter — researches the codebase across correctness / security / performance / maintainability / reliability lenses, ranks findings, gets user approval, then dispatches parallel coders and reviewers to fix them. Optional argument to focus scope or lenses.
argument-hint: [optional focus — e.g. "concurrency bugs", audit src/auth, security review]
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Autonomous Problem-Locator Pipeline

You orchestrate a multi-agent codebase audit. You run parallel researchers across different lenses (correctness, security, performance, maintainability, reliability) to locate bugs and improvement opportunities, consolidate and rank the findings, get user approval on the plan, then dispatch parallel coders to apply fixes and mirrored reviewers to validate them. Critical and high-severity fixes get dedicated regression tests.

## Input

- `$ARGUMENTS` — Optional focus. Any one of:
  - **Empty** (roam mode): scan the entire repo minus `.gitignore`, vendored deps, generated code, and test files
  - **Lens hint**: `"concurrency bugs"`, `"security review"`, `"performance audit"` — narrows which research lenses run
  - **Scope hint**: `"src/auth/"`, `"plugins/mz-dev-pipe"` — narrows which files are scanned
  - **Combined**: `"security audit of src/auth/"` — both

If the argument is ambiguous (no recognized lens keywords and no valid path), ask the user via AskUserQuestion. Never guess.

## Core Principles

1. **Research first, fix later.** Do not touch code until findings are consolidated, ranked, and approved by the user.
1. **Parallel where safe, sequential where necessary.** Multiple findings in the same file are atomic — they go to one coder. Different files fan out.
1. **Ask when unclear.** Ambiguous argument, borderline reviewer verdict, unclear test regression — stop and ask. Do not plow ahead.
1. **Strict fix scope with a narrow exception.** Coders fix ONLY approved findings plus trivially-adjacent bugs in the same function body (see Phase 5 for the exact definition). No refactors, no new features.

## Constants

- **MAX_RESEARCHERS**: 5 — one per lens
- **MAX_CODERS**: 6 — hard cap on parallel fix agents per wave
- **MAX_REVIEWERS**: 6 — always equals coder count (1:1 mirror)
- **MAX_REVIEW_ITERATIONS**: 3 — max rejection rounds before escalating
- **MAX_FIX_ATTEMPTS**: 3 — max inner-fix-loop attempts in Phase 6 before escalating
- **CRITICAL_CAP**: unlimited — every critical finding is included
- **HIGH_CAP**: 10 — top 10 high-severity findings by confidence
- **MEDIUM_CAP**: 5 — top 5 medium-severity findings by confidence
- **LOW_CAP**: 0 — low-severity findings are skipped from the fix plan (reported as a count in the summary only)
- **REGRESSION_TEST_SEVERITIES**: `[critical, high]` — which fixes get regression tests
- **TASK_DIR**: `.mz/task/` — all artifacts under `.mz/task/<task_name>/`

## Phase Overview

| #   | Phase                  | Reference                       | Loop?                   |
| --- | ---------------------- | ------------------------------- | ----------------------- |
| 0   | Setup                  | inline below                    | —                       |
| 1   | Scope & Lens Selection | `phases/research.md`            | —                       |
| 2   | Multi-Lens Research    | `phases/research.md`            | —                       |
| 3   | Consolidate & Rank     | `phases/research.md`            | —                       |
| 3.5 | User Approval Gate     | inline below                    | re-research on feedback |
| 4   | Chunk Findings         | `phases/fix_and_verify.md`      | —                       |
| 5   | Parallel Fix           | `phases/fix_and_verify.md`      | —                       |
| 6   | Verify & Auto-Fix      | `phases/fix_and_verify.md`      | inner fix loop (max 3)  |
| 7   | Parallel Review        | `phases/review_and_finalize.md` | —                       |
| 8   | Handle Verdicts        | `phases/review_and_finalize.md` | respawn loop (max 3)    |
| 9   | Regression Tests       | `phases/review_and_finalize.md` | —                       |
| 10  | Final Summary          | `phases/review_and_finalize.md` | —                       |

______________________________________________________________________

## Phase 0: Setup

### 0.1 Derive task name

From the argument (or "roam" if empty), derive a short snake_case name (max 30 chars).
Examples:

- `""` → `review_and_fix_roam`
- `"concurrency bugs"` → `locate_concurrency_bugs`
- `"audit src/auth/"` → `locate_audit_src_auth`
- `"security review"` → `locate_security_review`

### 0.2 Create task directory

```bash
mkdir -p .mz/task/<task_name>
```

### 0.3 Initialize state file

Write `.mz/task/<task_name>/state.md`:

```markdown
# Locate Problems: <argument or "roam">
- **Status**: started
- **Phase**: setup
- **Started**: <timestamp>
- **Review iterations**: 0
- **Fix attempts**: 0
- **Lenses dispatched**: 0 (pending Phase 1)
- **Findings**: 0 (pending Phase 3)
```

### 0.4 Create task tracking

Use TaskCreate to create one top-level task per pipeline phase so the user can track progress.

______________________________________________________________________

## Phase 1: Scope & Lens Selection

Parse the argument into (scope filter, lens filter). Pure path arguments → all 5 lenses on narrow scope. Lens-keyword arguments → matching lenses on full roam scope. Ambiguous arguments → ask the user.

**See `phases/research.md` → Phase 1** for the keyword-matching table, path detection rules, and ambiguity escalation.

Artifacts: `.mz/task/<task_name>/scope.md` — resolved file list and selected lenses.

Update state file phase to `scope_selected`.

______________________________________________________________________

## Phase 2: Multi-Lens Research

Dispatch 1-5 `pipeline-researcher` agents (model: **sonnet**) in a **single message**, one per selected lens. Each researcher combs the scoped file list with its lens-specific prompt and produces a list of findings.

**See `phases/research.md` → Phase 2** for the five lens-specific dispatch prompts and the per-lens artifact format.

Update state file phase to `researched`.

______________________________________________________________________

## Phase 3: Consolidate & Rank

Merge all lens outputs, dedupe cross-lens hits, rank by severity then confidence, apply per-tier caps.

**See `phases/research.md` → Phase 3** for the dedup algorithm, ranking rules, cap application, and the `.mz/task/<task_name>/findings.md` artifact.

**If the consolidated plan has zero findings at severity ≥ medium**: report that to the user and exit cleanly. No code changes to make.

Update state file phase to `findings_ranked`.

______________________________________________________________________

## Phase 3.5: User Approval Gate

After Phase 3, **this orchestrator** (not a subagent) must present the ranked findings to the user via AskUserQuestion. This step is interactive and must not be delegated.

Present:

1. **Summary counts**: N critical, M high (of K total high), P medium (of Q total medium), R low (skipped — reported as count only)
1. **Scope used**: file count and lenses that ran
1. **Full ranked findings list**: numbered, each with file:line, severity, confidence, one-line description, and proposed fix in one line
1. **Coder assignment preview**: which findings group into which chunks (based on affected file)

Use AskUserQuestion with:

```
Found <N> actionable findings. Please review:

<findings list>

Reply 'approve' to proceed with fixes, 'reject' to abort, or provide feedback for changes
(e.g. "drop finding 3", "rerun research with security lens only", "narrow scope to src/api/").
```

**Response handling**:

- **"approve"** → proceed to Phase 4
- **"reject" with no guidance** → update state to `aborted_by_user` and exit
- **Free-text feedback** — three sub-cases:
  - *Drop/adjust specific findings* → remove them from the plan and re-present (no re-research)
  - *Scope or lens changes* → return to Phase 1 with the adjusted parameters (re-research)
  - *Unclear feedback* → ask a follow-up question; do not guess the intent

Update state file phase to `plan_approved`.

______________________________________________________________________

## Phase 4: Chunk Findings

Group approved findings by affected file. All findings in the same file must go to the same coder. Group files into waves of ≤ `MAX_CODERS = 6` chunks.

**See `phases/fix_and_verify.md` → Phase 4** for the chunking algorithm and wave scheduling.

Update state file phase to `chunked`.

______________________________________________________________________

## Phase 5: Parallel Fix

Dispatch up to 6 `pipeline-coder` agents (model: **opus**) per wave in a **single message**, one per chunk. Each coder fixes the approved findings in its file(s) and is permitted to fix trivially-adjacent bugs under the strict definition in the phase file.

**See `phases/fix_and_verify.md` → Phase 5** for the coder dispatch prompt, the "trivially adjacent" rule, and the `.mz/task/<task_name>/fixes_<iteration>.md` artifact.

______________________________________________________________________

## Phase 6: Verify & Auto-Fix

Re-run tests and linters after each fix batch. Inner fix loop dispatches `pipeline-coder` agents to repair any regressions. Must restore green state before Phase 7 — never enter review on a red build.

**See `phases/fix_and_verify.md` → Phase 6** for the inner fix loop with `MAX_FIX_ATTEMPTS = 3` and escalation logic.

Update state file phase to `verified_green`.

______________________________________________________________________

## Phase 7: Parallel Review

Dispatch M = N `pipeline-code-reviewer` agents (model: **opus**) in a single message, one per chunk. Each reviewer verifies: (a) every approved finding is actually fixed, (b) trivial-adjacent fixes are actually trivial, (c) no new bugs introduced, (d) behavior preserved outside the intentional fix surface.

**See `phases/review_and_finalize.md` → Phase 7** for the dispatch prompt and the `.mz/task/<task_name>/review_<iteration>.md` artifact.

______________________________________________________________________

## Phase 8: Handle Verdicts

Selective re-dispatch of rejected chunks only. Previously-approved chunks are frozen for the rest of the run.

**See `phases/review_and_finalize.md` → Phase 8** for the decision tree, borderline-verdict escalation, and the respawn loop (`MAX_REVIEW_ITERATIONS = 3`).

Update state file phase to `review_passed` when all chunks PASS.

______________________________________________________________________

## Phase 9: Regression Tests

For findings with severity in `REGRESSION_TEST_SEVERITIES = [critical, high]`, dispatch `pipeline-test-writer` agents (model: **opus**) to write regression tests that pin the fixed behavior. Group by affected file, waves of ≤6.

**See `phases/review_and_finalize.md` → Phase 9** for the test writer dispatch, verification step, and escalation if new tests fail.

______________________________________________________________________

## Phase 10: Final Summary

Writes `.mz/task/<task_name>/summary.md` listing all findings (approved and skipped), fixes applied, tests added, review iterations used, and researcher follow-ups (low-severity findings + observations from coders/reviewers).

**See `phases/review_and_finalize.md` → Phase 10** for the summary template and user report.

Update state file status to `completed`.

______________________________________________________________________

## Error Handling

- **Ambiguous argument**: ask the user to clarify before Phase 1. Never guess between interpretations.
- **Empty resolved scope**: report and exit — nothing to scan.
- **Zero findings**: report the clean bill of health and exit cleanly at the end of Phase 3.
- **No test framework detected**: ask the user for a verification command. Do not proceed without one.
- **No linter detected**: note it and skip lint checks; don't block.
- **Researcher fails on a lens**: log the failure, continue with the remaining lenses, flag the gap in the Phase 3.5 approval plan.
- **Parallel write conflict**: should not happen since chunking is by affected file, but if a coder reports cross-file edits (similar to dev-optimize's cross-scope exception), detect and sequentialize in the next iteration.
- **Regression test fails on first run**: escalate to user — do not auto-fix, since the test itself may be wrong and the fix may also be wrong.

## State Management

After each phase, update `.mz/task/<task_name>/state.md` with:

- Current phase
- Review iteration count
- Fix-attempt count
- Cumulative list of files modified
- Any escalation notes

This allows the pipeline to be resumed if interrupted.
