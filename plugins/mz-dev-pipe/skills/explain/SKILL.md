---
name: explain
description: ALWAYS invoke when the user wants to understand how code works, needs visual documentation, or asks "what does X do". Triggers: "explain X", "how does X work", "diagram this", "what does this do", "walk me through", "document this code", "visualize the flow". Deep diagram-first code explainer — researches structure, execution flow, and domain context, then produces a mermaid-rich report (architecture, sequence, data flow, and optional mindmap diagrams) documenting design rationale and observations.
argument-hint: [scope:branch|global|working] [output:<path>] <scope or question — e.g. "src/auth/", "how does the payment flow work", "explain the WebSocket reconnection logic">
allowed-tools: Agent, Bash, Read, Write, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Code Explanation Pipeline

You orchestrate a deep-dive code analysis that produces a comprehensive, diagram-rich report explaining how a section of code works, why it's designed that way, and what potential issues exist. This is a read-only pipeline — it never modifies source code.

## Input

- `$ARGUMENTS` — The scope and optional question. Any combination of:
  - **Path/glob**: `"src/auth/"`, `"src/**/*.py"` — which files to explain
  - **Free-text question**: `"how does the payment flow work"`, `"explain the WebSocket reconnection logic"` — what to focus on
  - **Combined**: `"src/auth/ how does token refresh work"` — narrows both scope and focus

If empty or ambiguous, ask the user via AskUserQuestion. Never guess.

## Scope Parameter

Extract `scope:<mode>` from `$ARGUMENTS` if present (case-insensitive). Remove it from the remaining argument text before parsing.

| Mode      | Resolution                                          | Git command                                                                                                                                                                                            |
| --------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `branch`  | Files changed on this branch vs base branch         | Detect base: try `main`, then `master`. Run `git diff $(git merge-base HEAD <base>)..HEAD --name-only`. If on the base branch itself (empty diff), warn the user via AskUserQuestion.                  |
| `global`  | All source files in the repo                        | Honor `.gitignore`. Apply standard exclusions (vendored, generated, lock files, >5000 LOC). **Requires a focusing question** — if no question tokens are present, ask the user what aspect to explain. |
| `working` | Uncommitted changes (staged + unstaged + untracked) | `git diff HEAD --name-only` plus `git ls-files --others --exclude-standard`. If no changes exist, warn the user.                                                                                       |

**Default** (no `scope:` parameter): use path/glob/free-text detection from the argument.

The `scope:` parameter controls **which files** to analyze. The remaining argument text controls **what to focus on** within those files. They are orthogonal. Example: `scope:branch "how does error handling work"` analyzes only branch-changed files, focused on error handling.

## Output Parameter

Extract `output:<path>` from `$ARGUMENTS` if present. This is where the final report will be written.

**Default** (no `output:` parameter): `.mz/reports/explain_<YYYY_MM_DD>_<scope_name>.md` (append `_v2`, `_v3` if exists).

Example: `explain_2026_04_06_src_auth_token_refresh.md`

## Constants

- **MAX_RESEARCHERS**: 3 — hard cap on parallel researcher agents
- **LARGE_SCOPE_THRESHOLD**: 10 — file count above which structure and flow analysis split into separate researchers
- **TASK_DIR**: `.mz/task/` — working artifacts under `.mz/task/<task_name>/`

## Phase Overview

| #   | Phase             | Reference            | Loop? |
| --- | ----------------- | -------------------- | ----- |
| 0   | Setup             | inline below         | —     |
| 1   | Scope Resolution  | inline below         | —     |
| 2   | Research Dispatch | `phases/research.md` | —     |
| 3   | Report Generation | `phases/report.md`   | —     |

______________________________________________________________________

## Phase 0: Setup

### 0.1 Parse argument

Split `$ARGUMENTS` (after removing `scope:`, `output:` parameters) into:

- **Path-like tokens**: globs, directories, file paths (contains `/`, matches on disk, or has glob characters)
- **Question tokens**: everything else — the user's question or focus area

### 0.2 Derive task name

Task name format: `explain_<slug>_<HHMMSS>` where slug is a snake_case summary (max 20 chars) and HHMMSS is current time. Examples: `explain_src_auth_143022`, `explain_payment_flow_150511`.

### 0.3 Create task directory and state

Create `.mz/task/<task_name>/` directory. Write `state.md` with Status, Phase, Started, Researchers dispatched, and Output path fields.

### 0.4 Create task tracking

Use TaskCreate for each pipeline phase.

______________________________________________________________________

## Phase 1: Scope Resolution

Resolve the argument into a concrete file list:

- **`scope:` parameter given**: use the git-derived file list, applying standard exclusions
- **Path-like tokens**: expand via Glob or directory walk
- **Free-text only (no paths, no `scope:`)**: spawn a `pipeline-researcher` agent (model: **sonnet**) to identify which files match the description. If low confidence or multiple plausible interpretations, ask the user via AskUserQuestion.

**Exclusions**: `.gitignore`, vendored deps, generated/lock files, files > 5000 LOC. Test files are NOT excluded — they're valuable context.

**If the file list is empty**: report and exit. **If `scope:global` with no focusing question**: ask the user what aspect to explain.

Write `.mz/task/<task_name>/scope.md` with Mode, file count, Question/focus, and the file list (collapsed by directory if > 30 files).

Update state phase to `scope_resolved`.

______________________________________________________________________

## Phase 2: Research Dispatch

Dispatch 1-3 `pipeline-researcher` agents based on scope size and external dependency detection.
**See `phases/research.md`** for the dispatch decision matrix, researcher prompts, and per-researcher artifact format.
Update state phase to `researched`.

______________________________________________________________________

## Phase 3: Report Generation

Compile all researcher outputs into a single report with mandatory mermaid diagrams.
**See `phases/report.md`** for the report template, diagram requirements, and quality checks.
Write the report to the resolved output path. Update state to `completed`. Present a summary to the user with the report path.

______________________________________________________________________

## Error Handling

- **Ambiguous scope / low confidence scope resolution**: ask the user to clarify. Never guess.
- **Empty file list**: report and exit cleanly.
- **`scope:global` without question**: ask for a focusing question.
- **Researcher fails**: log it, continue with remaining researchers, note the gap in the report.
- **Domain research returns nothing useful / diagram can't be constructed**: note it in the report rather than guessing.

## State Management

After each phase, update `.mz/task/<task_name>/state.md` with current phase, researchers dispatched/completed, output path, and any issues encountered.
