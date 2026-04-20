# Phase 1: Source Inventory and Lens Decomposition

**Goal**: Produce a concrete, classified inventory of on-disk sources and decompose the task into 3–6 research lenses, each with an explicit file list. No file bodies are read in this phase — only names, mtimes, and task-text hints. The output feeds Phase 1.5 (user approval) and then Phase 2 (parallel lens dispatch).

## Contents

- [Phase 1.1: Fast Inventory](#phase-11-fast-inventory)
- [Phase 1.2: Classification](#phase-12-classification)
- [Phase 1.3: Lens Derivation](#phase-13-lens-derivation)
- [Phase 1.4: Inventory Artifact](#phase-14-inventory-artifact)
- [Phase 1.5 Gate](#phase-15-gate)
- [Transition](#transition)

______________________________________________________________________

## Phase 1.1: Fast Inventory

**The orchestrator runs these commands inline.** Do NOT delegate this step to a subagent — these are cheap, bounded shell calls whose output is a handful of filenames, and a subagent round-trip would add latency with no benefit.

Run each command and append the raw output to `.mz/task/<task_name>/inventory_raw.txt` (create the file on first write, then append each block with a one-line header of the command string). The orchestrator only reads filenames and mtimes from these results — **never read the body of any listed file in this phase**.

```bash
ls -lt .mz/research/ 2>/dev/null
ls -lt .mz/reports/ 2>/dev/null
ls -lt .mz/reviews/ 2>/dev/null
ls -lt .mz/task/   2>/dev/null | head -40
git log --oneline -50 2>/dev/null
git status --short  2>/dev/null
```

Notes on each bucket:

- `.mz/research/` — prior `/deep-research` reports. Uses `RESEARCH_STALE_DAYS = 90`.
- `.mz/reports/` — final reports from previous pipeline runs. Uses `REPORT_STALE_DAYS = 60`.
- `.mz/reviews/` — review outputs from `/review` or similar. Uses `REPORT_STALE_DAYS = 60`.
- `.mz/task/` — per-task working artifacts. `head -40` bounds the listing to the 40 most recently touched task directories; do NOT recurse into them here. Uses `TASK_ARTIFACT_STALE_DAYS = 30`.
- `git log --oneline -50` — bounded 50-commit window for the `git_history` lens.
- `git status --short` — captures any in-flight dirty state the synthesis should mention.

### Git unavailable degradation

If `git log --oneline -50` or `git status --short` fail (non-zero exit, empty output on a non-git directory, or `fatal: not a git repository` on stderr), the `git_history` lens is **unavailable**. The orchestrator must:

1. Record `git_history: unavailable` in `state.md` under a `buckets_unavailable` key.
1. Note the reason (e.g., `not a git repository`, `git command not found`) next to the bucket entry.
1. Skip the `git_history` lens entirely in §Phase 1.3 — do NOT dispatch a lens with zero sources.
1. Do **not** count `git_history` toward the 3-lens floor in §Phase 1.3. If the remaining available buckets cannot reach 3 lenses, fall through to the codebase-only-or-abort AskUserQuestion described in SKILL.md §Error Handling.

This degradation is intentional: `/combine` must work in non-git project roots (documentation bundles, fresh scratch dirs) without silently dropping a required lens. Unavailable buckets are surfaced to the user in the Phase 1.5 gate so the decomposition is transparent.

______________________________________________________________________

## Phase 1.2: Classification

Each file discovered in §1.1 is tagged along three axes: **freshness**, **slug-match**, and **source-type**. Freshness uses the constant appropriate to the source bucket — not a single global threshold.

### Freshness thresholds (per source type)

| Source bucket    | Constant                   | Days |
| ---------------- | -------------------------- | ---- |
| `.mz/task/*/`    | `TASK_ARTIFACT_STALE_DAYS` | 30   |
| `.mz/reports/*`  | `REPORT_STALE_DAYS`        | 60   |
| `.mz/reviews/*`  | `REPORT_STALE_DAYS`        | 60   |
| `.mz/research/*` | `RESEARCH_STALE_DAYS`      | 90   |

Pick the threshold that matches the file's bucket. A file in `.mz/research/` compared against `TASK_ARTIFACT_STALE_DAYS` would incorrectly drop 60-day-old research that is still perfectly usable, and vice versa.

### Tagging rules

For each file, compute `age_days = (now - mtime) / 86400` and tag:

- **Fresh** — `age_days <= threshold` for its bucket. Always included in the candidate pool.
- **Stale** — `age_days > threshold`. Excluded **unless** the task text implies historical framing (case-insensitive match for any of: `history`, `evolution`, `archive`, `what we tried`, `previously`, `old`, `past`). If the task is historical, stale files are included and tagged as such in the artifact.
- **Slug-matched** — any token from the derived task slug (split on `_`, tokens length >=3) appears as a case-insensitive substring of the filename. Slug-matched files are **always included regardless of freshness**, because a file whose name obviously matches the task is almost certainly on-topic even if old.

A file can carry both `stale` and `slug-match` tags — slug-match wins and the file is included.

### Classification table (written into the inventory artifact)

The orchestrator produces a table with one row per discovered file:

| Column              | Meaning                                                        |
| ------------------- | -------------------------------------------------------------- |
| `path`              | Relative path from repo root                                   |
| `mtime_age_days`    | Integer days since last modification                           |
| `fresh_or_stale`    | `fresh` or `stale`                                             |
| `slug_match`        | `yes` or `no`                                                  |
| `source_type`       | `research` / `task` / `report` / `review` / `codebase` / `git` |
| `threshold_applied` | The constant used (e.g., `RESEARCH_STALE_DAYS=90`)             |

Files tagged **stale + no slug-match** on a non-historical task are added to the artifact's `Excluded sources` section with reason `stale, no slug-match`, not to the main classification table.

______________________________________________________________________

## Phase 1.3: Lens Derivation

Lens derivation is a two-step process: **seed** from structural defaults, then **augment** based on the task text. The cap is `MAX_LENSES = 6`; the floor is 3 *available* lenses.

### Step 1 — Seed (B-hybrid defaults)

Start with these five structural default lenses. A default lens is seeded only if its bucket has at least one fresh-or-slug-matched file from §1.2.

| Lens              | Source glob                                      | Threshold constant         | Notes                                                                             |
| ----------------- | ------------------------------------------------ | -------------------------- | --------------------------------------------------------------------------------- |
| `research`        | `.mz/research/*.md`                              | `RESEARCH_STALE_DAYS`      | Deep-research outputs                                                             |
| `tasks`           | `.mz/task/*/`                                    | `TASK_ARTIFACT_STALE_DAYS` | Pre-filtered by Fresh + Slug-matched; never dispatch an agent on all 40 task dirs |
| `reports_reviews` | `.mz/reports/*.md` + `.mz/reviews/*.md`          | `REPORT_STALE_DAYS`        | Merged because neither alone usually justifies a full lens                        |
| `codebase`        | project root, narrowed by `scope:` or task hints | n/a (code is always fresh) | Use `scope:` param if set; else Grep/Glob against filename hints in the task text |
| `git_history`     | `git log` slice                                  | n/a                        | Skipped entirely if marked unavailable in §1.1                                    |

For the `codebase` lens, if `scope:` was set in Phase 0, use the resolved file list directly. Otherwise, extract filename-looking tokens from the task text (e.g., `auth.py`, `WebSocketManager`, `src/payments/`) and run Glob/Grep to resolve them into a concrete list. If neither yields files, drop the `codebase` lens entirely — better than dispatching an agent to scan the whole repo.

### Step 2 — Augment (task-adaptive)

Inspect the task text for domain keywords and apply these transformations:

- **Split** a default lens into two when the task implies orthogonal sub-domains. Example: task mentions both "tests" and "implementation" → split `tasks` into `task_tests` (files matching `test_*`, `*_test.*`, `*.spec.*`) and `task_impl` (everything else). Each split lens must still have at least 1 file; otherwise do not split.
- **Drop** an empty or irrelevant bucket. If `.mz/reviews/` is empty **and** the task does not mention review history, drop the lens rather than dispatch an agent with nothing to read. If `.mz/research/` has only stale, non-slug-matched files and the task is not historical, drop the `research` lens.
- **Add** a custom lens for a domain the five defaults miss. Example: task mentions a vendored third-party API with docs on disk under `docs/vendor/` → add an `external_docs` lens with an explicit file list from that path. Custom lenses follow the same rules as defaults: explicit file list, local-only, `pipeline-researcher` agent.

### Step 3 — Enforce cap and floor

- **Cap (`MAX_LENSES = 6`)**: if augmentation would produce more than 6 lenses, merge the two lenses with the smallest file counts until the total is ≤6. Record each merge in `state.md` under a `lens_merges` key.
- **Floor (3 available lenses)**: `git_history` does not count if marked unavailable in §1.1. If the number of available lenses is less than 3, the orchestrator must escalate via SKILL.md §Error Handling (codebase-only-or-abort AskUserQuestion). Do not silently proceed with fewer than 3 lenses.

### Step 4 — Bind explicit file lists

Every lens must carry an **explicit file list** — the concrete paths selected in §1.2, not globs. The `pipeline-researcher` agent dispatched for each lens receives this list verbatim and is forbidden from discovering additional files (see WU-3 dispatch prompt template). File lists prevent context blowup: the agent knows exactly what to read and cannot chase references off disk.

For the `git_history` lens (when available), the "file list" is a short text blob: the output of `git log --oneline -50` plus the slug-matched commit subset. The lens agent receives this blob in its prompt rather than a file list — call out this exception explicitly when writing the artifact in §1.4.

______________________________________________________________________

## Phase 1.4: Inventory Artifact

Write the decomposition to `.mz/task/<task_name>/inventory.md` using this template. The artifact is the single source of truth for §Phase 1.5 gate presentation and for §Phase 2 dispatch.

```markdown
# Inventory

**Task**: <full task text>
**Task slug**: <slug>
**Generated**: <YYYY-MM-DD HH:MM:SS>

## Sources discovered

| Path | Type | Age (days) | Fresh? | Slug-match? | Threshold |
| ---- | ---- | ---------- | ------ | ----------- | --------- |
| .mz/research/2026_03_14_deep_research_auth.md | research | 28 | fresh | yes | RESEARCH_STALE_DAYS=90 |
| .mz/task/2026_04_08_investigate_auth/findings.md | task  | 12 | fresh | yes | TASK_ARTIFACT_STALE_DAYS=30 |
| ...                                           | ...      | .. | ...   | ...  | ... |

## Proposed lenses

### Lens 1: <name>
- **Purpose**: <one-line — what this lens extracts and why>
- **Files** (N):
  - path/to/file_a
  - path/to/file_b
- **Constraint**: local-only, no web

### Lens 2: <name>
- **Purpose**: ...
- **Files** (N):
  - ...
- **Constraint**: local-only, no web

<repeat for each lens, up to MAX_LENSES = 6>

## Excluded sources
- `.mz/reports/old_report.md` — stale (age 180d > REPORT_STALE_DAYS=60), no slug-match
- `.mz/task/unrelated_task_123/` — no slug-match, not fresh enough to auto-include

## Unavailable buckets
- `git_history` — not a git repository (git status returned fatal error)
```

The artifact is written once per Phase 1 pass. If the user provides feedback at §Phase 1.5 Gate that changes the decomposition, overwrite this file and re-present.

______________________________________________________________________

## Phase 1.5 Gate

**This gate body is read by the orchestrator directly. It must NEVER be delegated to a subagent.** The orchestrator reads this section, then issues the `AskUserQuestion` call itself from SKILL.md §Phase 1.5. Delegating the read would defeat the approval-gate guarantee — an agent holding the gate body could make the approval decision on the user's behalf, which is exactly what the approval gate exists to prevent.

### Presentation content

Before issuing `AskUserQuestion`, the orchestrator assembles an inventory summary block from the `inventory.md` artifact produced in §1.4:

- **Total local sources discovered** — one count per bucket: `research: N`, `tasks: N`, `reports_reviews: N`, `codebase: N`, `git_history: N` (or `unavailable`).
- **Excluded sources** — each excluded path with its one-line reason (stale / no slug-match / empty bucket).
- **Proposed lenses** — numbered list. Each entry: lens name, one-line purpose, file count. Example: `1. research — consolidate prior deep-research findings on auth (4 files)`.
- **Dropped default lenses** — any of the five structural defaults that were dropped because their bucket was empty, and why.
- **Unavailable buckets** — any bucket marked unavailable in §1.1 (typically `git_history` on non-git directories), with reason.

The presentation is **summary only** — do not dump the full file lists into the AskUserQuestion message. The user reviews lens names and counts; if they want detail, they will ask in feedback and the orchestrator will re-present with the expanded lens.

### Verbatim AskUserQuestion prompt body template

Before invoking AskUserQuestion, emit a text block to the user:

```
**Inventory and decomposition ready for review**
Source buckets: research, tasks, reports/reviews, codebase, git history (if available). Proposed lenses identify 3–6 focused research topics with explicit file lists.

- **Approve** → proceed to Phase 2 (parallel lens dispatch)
- **Reject** → task marked aborted, no further phases run
- **Feedback** → incorporate your changes, re-run lens derivation, loop back for re-approval
```

The orchestrator then issues `AskUserQuestion` with this message body, filling the `<placeholders>` from the presentation content above:

```
Inventory and lens decomposition ready. Please review:

Sources: <breakdown by bucket with counts>
Proposed lenses:
<numbered list — each line: "N. <name> — <purpose> (<file_count> files)">
Excluded: <list with reasons, or "none">
Unavailable buckets: <list with reasons, e.g., "git_history (no git repository)", or "none">

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

The trailing line **must appear verbatim** — it is the canonical approval-gate reply instruction and is checked by structural tests.

### Response handling

- **"approve"** → update `state.md` phase to `decomposition_approved`, then proceed to Phase 2 by reading `phases/lens_dispatch.md`. Do not proceed to Phase 2 on any response other than an explicit `approve`.
- **"reject"** → update `state.md` status to `aborted_by_user`, write a one-line reason (`user rejected decomposition at Phase 1.5`) to state, and stop. Do not proceed to any later phase. Do not silently restart.
- **Feedback** → incorporate the user's feedback (add/remove/rename lenses, adjust file lists, re-classify sources, add or drop buckets), re-run §Phase 1.2 and §Phase 1.3 as needed, overwrite `inventory.md` with the revised decomposition, and return to this gate — re-present **via AskUserQuestion** using the same format above. Never skip the re-presentation step; the user must see and approve the revised decomposition.

### Loop language

**This is a loop — repeat until the user explicitly approves. Never dispatch lens agents without explicit approval.** The orchestrator must not short-circuit the loop on its own judgment (e.g., "the user's feedback was minor, I'll just proceed"). Every iteration ends with a fresh `AskUserQuestion` call; every `approve` requires an explicit user response; every `reject` stops the pipeline.

### Orchestrator-only notice

This gate body is read by the orchestrator directly. It must NEVER be delegated to a subagent. The orchestrator reads this section, then issues the `AskUserQuestion` call itself from SKILL.md §Phase 1.5. If a subagent is ever observed reading this file, it is an approval-gate violation and the pipeline must abort.

______________________________________________________________________

## Transition

After the user explicitly approves at §Phase 1.5 Gate:

1. Confirm `state.md` now shows `phase: decomposition_approved`.
1. The orchestrator stub in SKILL.md §Phase 1.5 completes — **return to SKILL.md Phase 1.5** so the orchestrator can fall through to Phase 2.
1. The orchestrator then reads `phases/lens_dispatch.md` (Phase 2) and begins the parallel lens fan-out using the `inventory.md` artifact as the source of truth for lens names, purposes, and file lists.

Phase 1 is complete when control has returned to SKILL.md Phase 1.5 and the state file records `decomposition_approved`. Do not proceed further from within this file.
