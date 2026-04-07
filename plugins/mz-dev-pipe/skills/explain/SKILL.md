---
name: explain
description: Deep code explainer — researches a scope across structure, execution flow, and domain context, then produces a comprehensive report with mermaid diagrams documenting how the code works, design rationale, and potential observations.
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

**Default** (no `output:` parameter): `.mz/reports/explain_<YYYY_MM_DD>_<report_name>.md`

Report file naming convention: `<skill_type>_<YYYY_MM_DD>_<detailed_name><_vN>.md`

- `skill_type`: `explain`
- `YYYY_MM_DD`: current date
- `detailed_name`: snake_case descriptive name derived from scope + question (e.g., `src_auth_token_refresh`, `payment_flow`, `branch_changes`)
- `_vN`: version suffix only if a report with the same base name already exists in `.mz/reports/` (check with Glob before writing — append `_v2`, `_v3`, etc.)

Examples: `explain_2026_04_06_src_auth_token_refresh.md`, `explain_2026_04_06_branch_websocket_logic.md`, `explain_2026_04_06_payment_flow_v2.md`

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
| 3   | Report Generation | `phases/research.md` | —     |

______________________________________________________________________

## Phase 0: Setup

### 0.1 Parse argument

Split `$ARGUMENTS` (after removing `scope:`, `output:` parameters) into:

- **Path-like tokens**: globs, directories, file paths (contains `/`, matches on disk, or has glob characters)
- **Question tokens**: everything else — the user's question or focus area

### 0.2 Derive task name

Short snake_case name (max 30 chars) from the scope and question.
Examples:

- `"src/auth/"` → `explain_src_auth`
- `"how does payment work"` → `explain_payment_flow`
- `"scope:branch"` → `explain_branch_changes`

### 0.3 Create task directory and state

```bash
mkdir -p .mz/task/<task_name>
```

Write `.mz/task/<task_name>/state.md`:

```markdown
# Explain: <scope + question summary>
- **Status**: started
- **Phase**: setup
- **Started**: <timestamp>
- **Researchers dispatched**: 0 (pending)
- **Output path**: <resolved output path>
```

### 0.4 Create task tracking

Use TaskCreate for each pipeline phase.

______________________________________________________________________

## Phase 1: Scope Resolution

Resolve the argument into a concrete file list:

- **`scope:` parameter given**: use the git-derived file list, applying standard exclusions
- **Path-like tokens**: expand via Glob or directory walk
- **Free-text only (no paths, no `scope:`)**: spawn a `pipeline-researcher` agent (model: **sonnet**) to identify which files match the description. If low confidence or multiple plausible interpretations, ask the user via AskUserQuestion.

**Exclusions** (always applied):

- `.gitignore`, vendored deps (`node_modules/`, `vendor/`, `.venv/`, `target/`, `build/`, `dist/`)
- Generated/lock files (`*.lock`, `*_pb2.py`, `*.pb.go`, `*.generated.*`)
- Files > 5000 LOC (flag separately)
- Note: test files are NOT excluded — they're valuable context for understanding behavior

**If the file list is empty**: report and exit.

**If `scope:global` with no focusing question**: ask the user what aspect to explain.

Write `.mz/task/<task_name>/scope.md`:

```markdown
# Scope
- Mode: <branch / global / working / path / free-text>
- Files: N
- Question/focus: "<user's question or 'general explanation'>"
- File list:
  <file list, collapsed by directory if > 30 files>
```

Update state phase to `scope_resolved`.

______________________________________________________________________

## Phase 2: Research Dispatch

Dispatch 1-3 `pipeline-researcher` agents based on scope size and external dependency detection.

**See `phases/research.md` → Phase 2** for the dispatch decision matrix, researcher prompts, analysis checklists, and per-researcher artifact format.

Update state phase to `researched`.

______________________________________________________________________

## Phase 3: Report Generation

Compile all researcher outputs into a single comprehensive report with mandatory mermaid diagrams.

**See `phases/research.md` → Phase 3** for the report template, mandatory diagram requirements, compilation rules, and quality checks.

Write the report to the resolved output path. Update state to `completed`. Present a brief summary to the user with the path to the full report.

______________________________________________________________________

## Error Handling

- **Ambiguous scope**: ask the user to clarify. Never guess.
- **Empty file list**: report and exit cleanly.
- **`scope:global` without question**: ask for a focusing question.
- **Researcher fails**: log it, continue with remaining researchers, note the gap in the report.
- **Free-text scope resolution low confidence**: ask the user to confirm the file list.
- **Domain research returns nothing useful**: note it in the report rather than guessing.
- **Mermaid diagram can't be constructed** (too many nodes, unclear relationships): include a textual description instead and note the limitation.

## State Management

After each phase, update `.mz/task/<task_name>/state.md` with:

- Current phase
- Researchers dispatched and completed
- Output path
- Any issues encountered
