# mz-design

Iterative UI/UX design-document generation with multi-critic refinement.

## What it does

Takes a design brief, researches the problem domain and your codebase, drafts a comprehensive UI/UX specification with ASCII wireframes, Mermaid flow diagrams, and a WCAG contrast report, then runs the draft through four specialist critics in parallel. The critique loop iterates until every critic approves and zero WCAG AA contrast violations remain (max 5 rounds).

## Skill

| Skill               | Command            | Inputs                                                            | Output                                                                                      |
| ------------------- | ------------------ | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| **design-document** | `/design-document` | Text brief; optional `@image:` refs, `scope:`, `@doc:` references | `design.md`, `wireframes.md`, `wcag-report.md`, `final-summary.md`, per-iteration critiques |

## Pipeline

```
/design-document "settings page for a team-admin console"
  │
  ├─ Phase 1: Intake & research
  │     └─ design-researcher (sonnet) — codebase + WebSearch
  ├─ Phase 2: Initial draft
  │     └─ design-document-writer (opus) — design.md + wireframes.md + wcag-report.md
  ├─ Phase 3: Critique loop (max 5 iterations)
  │     ├─ ui-designer              (opus) — layout, grid, hierarchy
  │     ├─ ux-designer              (opus) — flows, IA, Nielsen heuristics
  │     ├─ art-designer             (opus) — color theory, type pairing, mood
  │     ├─ accessibility-specialist (opus) — WCAG 2.2 AA hard gate
  │     ├─ design-critique-synthesizer (sonnet) — merges findings
  │     └─ design-revision-writer   (opus) — applies action items if any critic fails
  └─ Phase 4: Finalization
        └─ User approval gate → final-summary.md
```

## Agents

| Agent                         | Model  | Role                                                           |
| ----------------------------- | ------ | -------------------------------------------------------------- |
| `design-researcher`           | sonnet | Codebase scan + WebSearch for domain patterns                  |
| `design-document-writer`      | opus   | Produces initial design.md, wireframes.md, wcag-report.md      |
| `design-revision-writer`      | opus   | Applies critique action items without rewriting clean sections |
| `design-critique-synthesizer` | sonnet | Merges four critic outputs into a single action plan           |
| `ui-designer`                 | opus   | Visual layout, grid systems, whitespace, hierarchy critic      |
| `ux-designer`                 | opus   | Flows, IA, interaction, Nielsen heuristics critic              |
| `art-designer`                | opus   | Color harmony, type pairing, mood, aesthetic coherence         |
| `accessibility-specialist`    | opus   | WCAG 2.2 AA validator; owns the hard gate                      |

## Exit criteria

The critique loop terminates successfully only when **all four critics return VERDICT: PASS** (zero `Critical:` findings) **and** the accessibility-specialist returns `WCAG_GATE: PASS` (zero AA-normal contrast violations). If neither condition is met after 5 iterations, the orchestrator escalates to the user via `AskUserQuestion` — no silent partial acceptance.

## Output location

```
.mz/design/<YYYY_MM_DD>_design_<slug>/
├── state.md
├── intake.md
├── research.md
├── design.md
├── wireframes.md
├── wcag-report.md
├── critique_1.md ... critique_N.md
└── final-summary.md
```

## Install

```bash
claude plugin install mz-design
```

## Usage

```
/design-document "team admin console — settings page with sections for members, billing, integrations, and audit log"
```

Provide codebase scope to anchor the design against existing components:

```
/design-document scope:branch "add a design for the new notifications preferences page"
```
