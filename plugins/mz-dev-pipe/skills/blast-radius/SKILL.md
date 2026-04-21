---
name: blast-radius
description: ALWAYS invoke when the user wants to see the impact of changing a file, function, or module before refactoring. Triggers: "blast radius of X", "what depends on X", "impact analysis". When NOT to use: the refactor itself (use optimize or build).
argument-hint: <file path, function name, or module name>
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Refactor Blast Radius Map

## Overview

Orchestrates a read-only impact analysis pipeline. Given a target (file, function, or module), computes the full dependency graph, overlays git age data, scores risk, and produces a ranked report showing what breaks if the target changes.

## When to Use

- User wants impact analysis before a refactor or rename.
- Triggers: "blast radius of X", "what depends on X", "impact analysis", "what would break if I change X".
- You need a read-only dependency map, not a code change.

### When NOT to use

- Performing the refactor itself — use `optimize` or `build`.
- Fixing a known bug — use `debug`.
- Bug hunt across the repo — use `audit`.

## Input

- `$ARGUMENTS` — A file path, function name, or module name. If empty or ambiguous, ask via AskUserQuestion. Never guess.

## Scope Parameter

See [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md) for the canonical scope modes (`branch`, `global`, `working`) and their git commands. Document any skill-specific overrides or restrictions below this line.

- This pipeline is read-only and takes a single target (`$ARGUMENTS`); scope narrows **only the graph-expansion file set**, not the grep-for-references universe. Cross-repo references must still be surfaced if they touch the target.
- **Default** (no `scope:`): all project files are eligible for reference discovery.

## Constants

- **MAX_DEPTH**: 3 | **MAX_RESEARCHERS**: 4 | **MAX_GRAPH_NODES**: 100
- **TASK_DIR**: `.mz/task/`

## Core Process

### Phase Overview

| #   | Phase             | Reference                       | Loop? |
| --- | ----------------- | ------------------------------- | ----- |
| 0   | Setup             | inline below                    | —     |
| 1   | Discovery & Graph | `phases/discovery.md`           | hops  |
| 2   | Analysis & Report | `phases/analysis_and_report.md` | —     |

### Phase 0: Setup

1. Parse `$ARGUMENTS` to determine target type:
   - **File**: argument contains `/` or `.` extension → validate file exists via Glob.
   - **Function**: argument matches identifier pattern (no path separators) → grep to locate definition, resolve to file + line.
   - **Module**: argument matches directory name → validate directory exists.
1. If target not found: ask user to clarify via AskUserQuestion.
1. Derive task name as `<YYYY_MM_DD>_blast_radius_<slug>` where `<YYYY_MM_DD>` is today's date (underscores) and slug is a snake_case summary (max 20 chars) of the target basename; on same-day collision append `_v2`, `_v3`. Create `.mz/task/<task_name>/`. Write `state.md` with Status: started, Phase: setup, Target, Target type, Started timestamp. Use TaskCreate for tracking.

### Phase 1: Discovery & Graph Building

Dispatch **MAX_RESEARCHERS** (4) `pipeline-researcher` agents (model: sonnet) in parallel, each covering a distinct reference category. Then run iterative hop expansion up to **MAX_DEPTH**.

**See `phases/discovery.md`** for researcher dispatch prompts, reference categories, hop expansion algorithm, and `graph.md` artifact.

Update state phase to `graph_complete`.

### Phase 2: Analysis & Report

Overlay git age data on every node in the graph. Compute risk scores. Generate the final report with safety verdict.

**See `phases/analysis_and_report.md`** for age analysis commands, risk scoring formula, report template, and safety verdict criteria.

Write report to `.mz/reports/<YYYY_MM_DD>_blast_radius_<target_slug>.md`. Present summary to user. Update state to `completed`.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                | Rebuttal                                                                          |
| ------------------------------ | --------------------------------------------------------------------------------- |
| "small refactor, skip the map" | "small refactors produce the most silent breakage because reviewers don't look"   |
| "I know what this touches"     | "you know what the call graph you remember touches, not what it actually touches" |
| "the tests will catch it"      | "tests only catch what they cover; the map catches what tests miss"               |

## Red Flags

- You skipped the call-graph scan because the change "felt small".
- You relied on memory of the codebase instead of fresh grep results.
- You didn't run the test suite on the dependents the graph surfaced.

## Verification

Output the final report block: target, graph node count, top risk dependents, safety verdict, and the written report path.

## Error Handling

- **Empty argument**: ask via AskUserQuestion. Never guess.
- **Target not found**: ask user to clarify. Suggest similar files via Glob.
- **Zero references found**: report that the target appears isolated. Note caveats (dynamic imports, reflection, external consumers).
- **Graph exceeds MAX_GRAPH_NODES**: truncate at depth boundary, note truncation in report.
- **Researcher returns empty**: retry once with broadened search terms. If still empty, proceed with remaining results and note the gap. After collecting all seed researcher results, if the total direct-dependent count across all researchers is 0, run a one-line smoke test to confirm isolation (e.g., `grep -r "<target basename>" --include="*.{js,ts,py,go,rs,java}" .` or equivalent for the target type). If the smoke test also returns no matches, emit `ZERO RESULTS VERIFIED` in the report and proceed to Phase 2 (Analysis & Report). If the smoke test returns matches (indicating a search gap in the researcher dispatch), escalate via AskUserQuestion before continuing — do not proceed to reporting.

## State Management

Update `.mz/task/<task_name>/state.md` after each phase with: current phase, graph node count, files analyzed, risk summary. All intermediate artifacts persist in the task directory.

Produce a ranked report showing exactly what depends on the target and how risky each dependency is. Every claim must trace back to a specific grep match or git log entry — never fabricate references.
