# Phase 1: Propose — Route the Artifact, Draft It

Decide which governance artifact (if any) this decision needs, then draft a populated copy into the scratch dir. This phase owns the routing dispatch and the intake draft; it does **not** write to `docs/` — that happens only after the human sign-off gate.

## Inputs (from Phase 0)

- The decision text, the `artifact:` override (or `auto`), the `rich` flag.
- `.mz/task/<task_name>/provenance.md` — already written, `human_signoff: pending`.
- `state.md` at `Phase: 1`.

## Step 1.1 — Dispatch the router

Dispatch `gov-router` (sonnet, read-only). It reads `references/artifact-router.md` and runs the two-gate algorithm itself — your prompt carries only the decision and the overrides, not the algorithm. Dispatch prompt:

```
Route the governance artifact for this change.

## Task Directory
.mz/task/<task_name>/

## Change to route
<the decision text verbatim>

## Overrides
artifact: <adr | rfd | design | auto>   (auto = you choose)
rich: <true | false>

## Algorithm
Read skills/govern/references/artifact-router.md and apply Gate A then Gate B verbatim.

## Output
Write the routing decision to .mz/task/<task_name>/routing.md and emit the decision block (ARTIFACT / GATE_FIRED / WEIGHT / STATUS_VOCAB / OVERRIDE + rationale), then STATUS:.
```

This is a single-agent dispatch — no wave manifest needed.

## Step 1.2 — Consume the routing decision

Read `routing.md` (or the returned block). Parse and store: `ARTIFACT` (`none|adr|rfd|design`, where ADR may resolve to `adr-nygard`/`adr-madr`), `WEIGHT` (`light|heavy|n/a`), `STATUS_VOCAB`, and the rationale.

Handle the router's `STATUS:` line:

- `DONE` / `DONE_WITH_CONCERNS` → proceed (log any concern to `state.md`).
- `NEEDS_CONTEXT` → the change description is too thin. Relay the router's named gap to the user via AskUserQuestion, then re-dispatch with the added context. Do not advance.
- `BLOCKED` → `artifact-router.md` is unreadable or no change was supplied. Escalate via AskUserQuestion; do not fabricate a routing.

Emit a visible routing block: `ARTIFACT`, `WEIGHT`, `STATUS_VOCAB`, and a one-line rationale.

## Step 1.3 — Exemption path (`ARTIFACT: none`)

When the router returns `ARTIFACT: none`, Gate A found the change not substantial-and-ambiguous. Do **not** select a template, draft, discuss, or gate. Instead:

1. Append a one-line exemption note to `state.md` under `## Exemption` — the router's reason verbatim (e.g. "behavior-preserving refactor — exempt under Gate A").
1. Keep `provenance.md` as the run record (the exemption is itself a governed outcome worth tracing).
1. Update `state.md`: `Status: complete`, `Phase: 1`, `phase_complete: true`, `what_remains: []`. Append `routing.md` to `FilesWritten` (`provenance.md` is already tracked from Phase 0, so the exempt run records both).
1. Report to the user: the decision was assessed and needs no governance artifact, with the one-line reason and the path to `routing.md`. **Stop the pipeline here** — there is no Phase 2 through 5 for an exempt change.

This is the cheap, correct outcome for routine work. Routing `none` is a real result, not a failure — report it plainly and stop.

## Step 1.4 — Read the matching template

Reached only when `ARTIFACT` is `adr`, `rfd`, or `design`. Read the template the router selected, in full, with the Read tool:

| Router `ARTIFACT` | Template to read                    | Target dir later  | Default status  |
| ----------------- | ----------------------------------- | ----------------- | --------------- |
| `adr-nygard`      | `references/adr-nygard-template.md` | `docs/decisions/` | `proposed`      |
| `adr-madr`        | `references/adr-madr-template.md`   | `docs/decisions/` | `proposed`      |
| `rfd`             | `references/rfd-template.md`        | `docs/rfcs/`      | `prediscussion` |
| `design`          | `references/design-doc-template.md` | `docs/design/`    | `draft`         |

If the router reported a bare `adr` without the variant, pick Nygard by default and MADR when `rich` was set or the decision weighs three or more options (the same rule the router applies).

## Step 1.5 — Draft into `draft.md`

The orchestrator writes the intake draft itself — this is a small markdown fill, not a dispatched job (it saves a round-trip and the draft is revised in-loop during Phase 2). Populate the template from the decision:

- Fill every section the template defines from what the decision states. Where a section's content is genuinely not yet known (an RFD's `Determinations`, a still-open trade-off), leave the template's guidance placeholder or write `<to be resolved in discussion>` — do not invent facts to fill a heading.
- Copy the AgDR provenance fence shape into the header exactly as the template shows it, but leave the fence values as placeholders here — `gov-artifact-writer` embeds the real fence from `provenance.md` at record time. `draft.md` is transient; the durable fence is stamped in Phase 4.
- Set the artifact's own `status` field to the default for its type from the table above. For an **RFD** that means `prediscussion` — it enters discussion not yet ready for sign-off; the gate advances it.
- Write the result to `.mz/task/<task_name>/draft.md` (transient — **not** `docs/` yet). Append it to `FilesWritten`.

## Step 1.6 — Carry weight forward and advance

Record `WEIGHT` (`light`/`heavy`) and the resolved artifact type in `state.md` — Phase 2 scales its panel on the weight, Phase 4 resolves the target dir from the type. Update `state.md`: `Phase: 2`, `phase_complete: true` for Phase 1, refresh `what_remains` (e.g. "run the discuss panel", "human sign-off gate", "write to docs/"). Emit a short transition block, then read `phases/discuss.md`.

## Anti-rationalization — do not skip the router

| Rationalization                                          | Rebuttal                                                                                                                                                                                                                                                                       |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| "I already know this is an ADR, I'll just draft it."     | Routing is also the Gate-A exemption check. Skipping the router skips the test for whether *any* artifact is warranted — and silently turns a routine refactor into ceremony, or worse, drafts a heavy artifact the change never needed. Dispatch the router every run.        |
| "The user passed `artifact:adr`, so routing is settled." | The override sets the artifact, not the weight or the exemption. The router still emits `WEIGHT` (which scales Phase 2) and records the override-vs-inference disagreement as a `Nit:` for the record. The dispatch is cheap; the routing metadata is load-bearing downstream. |
| "I can guess the weight myself and save a dispatch."     | Weight drives whether four opus critics run or one sonnet critic does — a real cost and rigor difference. The router computes it from the option count and artifact type deterministically; guessing it under- or over-scales the panel.                                       |

## Notes

- The router is read-only and never drafts — the draft is the orchestrator's job, the durable write is `gov-artifact-writer`'s. Three distinct lanes; keep them distinct.
- `draft.md` is the single source the Phase 2 critics read and the Phase 3 gate presents. There is exactly one `draft.md`; revisions overwrite it in place, never fork it.
