# Phase 1: Intake & Research

Full detail for the intake-and-research phase of the `design-document` skill. Covers parsing the brief, capturing modifiers, dispatching the researcher, and saving the research artifacts.

## Goal

Produce `intake.md` and `research.md` in `.mz/design/<task_name>/` that give the writer everything it needs to draft a complete, codebase-aware, domain-grounded design document in one shot.

## Inputs

From Phase 0:

- The design brief text
- Optional modifiers: `scope:branch|global|working`, `@image:<path>`, `@doc:<path>`
- The task name and working directory

## Step 1.1 — Dispatch the researcher

Spawn a `design-researcher` agent (model: **sonnet**) with this prompt:

```
You are researching context for a new UI/UX design task.

## Brief
<the verbatim brief>

## Modifiers
- scope: <branch|global|working>
- image refs: <list of @image: paths, or "none">
- doc refs: <list of @doc: paths, or "none">

## Task Directory
.mz/design/<task_name>/

## Your Job
1. Parse the brief and modifiers. Record them into intake.md.
2. For each @doc: reference, read the file in full and record a summary in intake.md.
3. For each @image: reference, acknowledge the path in intake.md but DO NOT attempt to decode binary image data. The writer will leave placeholders for visual references the user later supplies.
4. Scan the codebase within the declared scope for:
   - Existing component library (components/, ui/, design-system/)
   - Design tokens / theme files (theme.*, tokens.*, tailwind.config.*, CSS variables)
   - Style conventions (utility CSS, styled-components, CSS modules)
   - Icon system
   - Typography setup
   - Accessibility conventions (ARIA, focus rings, skip links)
   - Existing screens similar to the brief
5. Use WebSearch to research domain patterns for the problem area (settings, billing, onboarding, etc.). Cross-reference 2+ authoritative sources.
6. Write intake.md and research.md per the formats in the agent spec.

Emit disclosure tokens:
- STACK DETECTED: <stack + version>
- CONFLICT DETECTED: <...>  (when sources disagree)
- UNVERIFIED: <...>         (when no authoritative source found)

Terminal status line: STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
```

## Step 1.2 — Handle researcher status

- `DONE` — proceed to Phase 2.
- `DONE_WITH_CONCERNS` — log the concern block to `state.md` under `## Concerns` and proceed.
- `NEEDS_CONTEXT` — escalate to the user via `AskUserQuestion`, asking the specific question the researcher surfaced. Re-dispatch with the added context.
- `BLOCKED` — escalate to the user immediately. Do not retry. Offer options: clarify the brief, abort, or skip codebase scan.

## Step 1.3 — Verify research artifacts

After the researcher returns, verify both files exist and are non-empty:

```bash
test -s .mz/design/<task_name>/intake.md && test -s .mz/design/<task_name>/research.md
```

Output a visible block showing:

- Paths to both files
- Detected stack (grep `STACK DETECTED:` from research.md)
- Number of CONFLICT / UNVERIFIED tokens (grep counts)
- Summary of codebase findings (first 10 lines of the `## Codebase Context` section in intake.md)

If either file is missing or empty, retry the researcher once with the explicit instruction to write both files. If it still fails, escalate.

## Step 1.4 — Update state

Update `.mz/design/<task_name>/state.md`:

```
Status: running
Phase: 1
PhaseName: intake_and_research_complete
Iteration: 0
FilesWritten:
  - .mz/design/<task_name>/intake.md
  - .mz/design/<task_name>/research.md
```

Proceed to Phase 2.

## Notes

- Phase 1 is not gated. The user already approved the intent by invoking the skill; research is read-only and low-risk.
- The researcher uses WebSearch but never WebFetch on authenticated URLs (docs sites only).
- Image references are intentionally not decoded. The pipeline's ceiling is text; the writer leaves TODO markers for visual references in the final doc.
- Keep the researcher focused on the domain of the brief. Do not expand scope to the whole product.
