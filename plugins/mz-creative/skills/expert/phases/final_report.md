# Phase 3: Final Report

Full detail for dispatching `expert-report-writer` and producing the polished report. No user approval gate at this phase — the report is written, its path is returned, and the skill exits.

## Goal

Produce a single structured report at `.mz/reports/expert_<YYYY_MM_DD>_<slug>.md` synthesising the 3 rounds into a multi-sided analysis.

## Inputs

From Phase 2:

- `panel.md`
- `intake.md` (+ `research.md` if `scope:` was set)
- `iter_1_<agent>.md` × 5, `round_1_summary.md`
- `iter_2_<agent>.md` × 5, `round_2_summary.md`
- `iter_3_<agent>.md` × 5, `round_3_summary.md`

## Step 3.1 — Pre-dispatch checks

Verify all artifacts are on disk. If any round file is missing, log the gap and proceed anyway — the report writer must document gaps rather than block.

```bash
ls .mz/task/<task_name>/iter_{1,2,3}_*.md .mz/task/<task_name>/round_{1,2,3}_summary.md
```

## Step 3.2 — Compute report filename

Slug = same as `task_name` slug portion. Date = today's date in `YYYY_MM_DD`.

```
report_path = .mz/reports/expert_<YYYY_MM_DD>_<slug>.md
```

If the file already exists, append `_v2`, `_v3`, … until a free slot is found. Ensure `.mz/reports/` exists (`mkdir -p`) before dispatch.

## Step 3.3 — Dispatch `expert-report-writer`

Spawn `expert-report-writer` (model: **sonnet**) with this prompt:

```
You are producing the final report for an expert panel review.

## Task Directory
.mz/task/<task_name>/

## Output path
<computed report_path from step 3.2>

## Read
- .mz/task/<task_name>/intake.md
- .mz/task/<task_name>/research.md (if exists)
- .mz/task/<task_name>/panel.md
- .mz/task/<task_name>/iter_1_<each panelist>.md  (5 files)
- .mz/task/<task_name>/round_1_summary.md
- .mz/task/<task_name>/iter_2_<each panelist>.md  (5 files)
- .mz/task/<task_name>/round_2_summary.md
- .mz/task/<task_name>/iter_3_<each panelist>.md  (5 files)
- .mz/task/<task_name>/round_3_summary.md

## Your Job
Write the final report to the output path following the schema in your agent spec. Key rules:

1. Every claim in the report must be attributable to a specific agent + round. Use inline tags like "[lens-cto R2]" so the reader can trace.
2. The Executive Summary must be 3-5 sentences. It is the only thing most readers will read. Make it land.
3. Consensus Findings capture what held across all 3 rounds — NOT what appeared once. Cite round numbers.
4. Divergent Views must present BOTH sides with the agents on each side and the core tradeoff. Never resolve the tension — let the reader decide.
5. Recommendations are ranked by panel endorsement strength. Each recommendation lists the agents who endorsed it (not just the round-3 view — weigh consistency across rounds).
6. Per-Expert Takes come verbatim from round 3 (last position). Do not rewrite — quote or paraphrase tightly.
7. Methodology block must list: panel composition, rounds run, synthesizer, source files (relative paths), and the task directory.

## Rules
- No generic filler. Every section earns its place.
- No chart or diagram (it's a markdown report, not a deck).
- If a gap was logged in state.md (missing panelist output in a round), note it in Methodology → Gaps.
- Do not invent agent names. Only the 5 panelists listed in panel.md.
- Do not exceed ~600 lines. A tight report beats a long one.

Terminal status line: STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
```

## Step 3.4 — Handle writer status

- `DONE` — verify the file exists and is non-empty; proceed to Step 3.5.
- `DONE_WITH_CONCERNS` — log concerns; verify file; proceed.
- `NEEDS_CONTEXT` — re-dispatch with the missing piece (most commonly a missing file path or ambiguous panel entry).
- `BLOCKED` — escalate to user via `AskUserQuestion`. Offer: accept partial report (inspect what was written), re-run report writer with guidance, abort without a report.

## Step 3.5 — Verify report

```bash
test -s <report_path>
```

Structural sanity:

```bash
grep -c '^## ' <report_path>
```

Should be ≥ 8 (Executive Summary, Consensus Findings, Divergent Views, Strengths, Weaknesses, Top Risks, Recommendations, Per-Expert Takes, Methodology). If fewer, dispatch a revision pass with the missing sections listed.

## Step 3.6 — Update state to complete

```
Status: complete
Phase: 3
PhaseName: report_written
Round: 3
Completed: <timestamp>
ReportPath: <report_path>
FilesWritten:
  - ... (append report_path)
```

## Step 3.7 — Emit final completion block

Output a visible block to the user:

```
Expert consultation finalized.

Task dir:  .mz/task/<task_name>/
Report:    <report_path>
Panel:     <5 names>
Rounds:    3/3

Top-line findings (from Executive Summary):
  <first 3 bullets or sentences from the report's Executive Summary>
```

Do not print the full report inline — it is on disk, and the user knows where to find it.

## Notes

- There is no user approval gate at Phase 3 by design (confirmed with user). The panel was already gated at Phase 1.5. A second gate would add friction without new information.
- If the user wants iterative feedback on the report, they can re-run `/expert` with a narrower follow-up brief that references the prior report.
- The report writer is sonnet (not opus) because synthesis benefits from breadth-over-depth and sonnet handles long-context reliably at lower cost.
- `.mz/reports/` is the same directory brainstorm uses. Naming convention `expert_<date>_<slug>.md` avoids collision with `brainstorm_<date>_<slug>.md` via the prefix.
