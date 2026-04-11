# Phase 2: Initial Draft

Full detail for the initial-draft phase. Covers dispatching the writer, verifying the three output artifacts, and handing off to the critique loop.

## Goal

Produce three files in `.mz/design/<task_name>/`:

1. `design.md` — the comprehensive design document following the canonical 14-section template
1. `wireframes.md` — ASCII wireframes plus Mermaid user flows, IA, and state diagrams
1. `wcag-report.md` — computed contrast report for every color pair used in the design

## Inputs

From Phase 1:

- `.mz/design/<task_name>/intake.md`
- `.mz/design/<task_name>/research.md`

## Step 2.1 — Dispatch the writer

Spawn a `design-document-writer` agent (model: **opus**) with this prompt:

```
You are producing the initial UI/UX design document.

## Task Directory
.mz/design/<task_name>/

## Inputs
- Read .mz/design/<task_name>/intake.md in full
- Read .mz/design/<task_name>/research.md in full
- Grep references/design-spec-template.md for each section as you draft it
- Grep references/wcag-contrast-thresholds.md for the contrast formula when computing the report
- Grep references/nielsen-heuristics.md to self-check the interaction design

## Your Job
Follow the canonical 14-section template exactly. Produce three files in one dispatch:

1. design.md — following the canonical template:
   §1 Overview · §2 User Flows · §3 Information Architecture · §4 Layout & Grid
   §5 Components · §6 Color System · §7 Typography · §8 Spacing & Sizing
   §9 Motion & Interaction · §10 Responsive Strategy · §11 States
   §12 Accessibility · §13 Design Rationale · §14 Open Questions

2. wireframes.md — ASCII box-drawing wireframes for top 3-5 screens,
   Mermaid flowcharts (primary + 2 secondary/error flows),
   Mermaid sitemap for IA, Mermaid state diagrams for non-trivial components.

3. wcag-report.md — every text and non-text color pair with computed ratios
   using the WCAG luminance + contrast formula from the reference file.
   If any text pair fails AA-normal (4.5:1), fix the palette in design.md
   BEFORE finalizing and recompute.

## Rules
- Every hex value must be parseable: `#XXXXXX` uppercase, 6 digits.
- §6 must declare the color harmony relationship (complementary, analogous, etc.).
- §7 must declare the type-pairing rationale and type-scale ratio.
- §11 must document loading, empty, error, disabled, focus, hover, active states.
- §12 must specify WCAG 2.2 AA as the conformance target and cover keyboard,
  focus management, and screen-reader semantics.

Terminal status line: STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
```

## Step 2.2 — Handle writer status

- `DONE` — verify artifacts and proceed to Phase 3.
- `DONE_WITH_CONCERNS` — log concerns to `state.md`, verify artifacts, proceed. Concerns might be "§14 Open Questions needs product decision on X".
- `NEEDS_CONTEXT` — the writer could not proceed. Re-dispatch the researcher for the missing piece, then re-dispatch the writer.
- `BLOCKED` — escalate to the user via `AskUserQuestion`. Offer: clarify brief, abort, proceed with a minimal draft.

## Step 2.3 — Verify artifacts

Check all three files exist, are non-empty, and have the expected shape:

```bash
test -s .mz/design/<task_name>/design.md
test -s .mz/design/<task_name>/wireframes.md
test -s .mz/design/<task_name>/wcag-report.md
```

Additional structural checks:

- `grep -c '^## ' .mz/design/<task_name>/design.md` → should be ≥ 14 (one per template section)
- ```` grep -c '```mermaid' .mz/design/<task_name>/wireframes.md ```` → should be ≥ 3 (at least primary flow + IA + one state diagram)
- `grep -c '^|' .mz/design/<task_name>/wcag-report.md` → should be ≥ 4 (table header + separator + at least 2 pairs)

If any check fails, retry the writer once with the explicit failing check as the issue. If it still fails, escalate.

## Step 2.4 — Output summary block

Emit a visible block:

```
Initial draft complete:
- design.md       — <line count> lines, <section count> sections
- wireframes.md   — <line count> lines, <mermaid block count> diagrams
- wcag-report.md  — <line count> lines, <pair count> color pairs tested

Pairs failing AA-normal: <count>
Pairs failing AA-large:  <count>
```

If any text pair is already failing AA-normal from the initial draft, note it explicitly. The accessibility-specialist will catch it in the critique loop, but surfacing it here saves a round.

## Step 2.5 — Update state

```
Status: running
Phase: 2
PhaseName: initial_draft_complete
Iteration: 0
FilesWritten:
  - .mz/design/<task_name>/intake.md
  - .mz/design/<task_name>/research.md
  - .mz/design/<task_name>/design.md
  - .mz/design/<task_name>/wireframes.md
  - .mz/design/<task_name>/wcag-report.md
```

Proceed to Phase 3 (Critique Loop).

## Notes

- Phase 2 is not gated — the draft is intentionally subject to critique in Phase 3. Gating here would waste user attention on an unreviewed draft.
- Do not instruct the writer to self-critique. That is the critique loop's job.
- The writer is responsible for producing all three files in a single dispatch. Do not split into three writers.
