# Phase 2: Propose — Route the Artifact, Draft It

Route the decision again, now with the user's answers and the research, then draft a populated copy into the scratch dir. This phase owns the final routing and the intake draft; it does **not** write to `docs/`, which happens only after the human sign-off gate.

## Inputs (from Phase 1)

- The decision text, the `artifact:` override (or `auto`), the `rich` flag.
- `<PROJECT_ROOT>/.mz/task/<task_name>/brief.md`: the user's answers, related records and assumptions.
- `<PROJECT_ROOT>/.mz/task/<task_name>/research.md`: the code report and one section per outside technology.
- `state.md` at `Phase: 2`, with `ScreenArtifact`.

## Step 2.1 — Dispatch the router

Dispatch `gov-router` (sonnet; it writes only `routing.md`). It reads `<SKILL_DIR>/references/artifact-router.md` and runs the two gates itself; your prompt carries the decision, the overrides and the two files, not the algorithm:

```
Route the governance artifact for this change.

## Task Directory
<PROJECT_ROOT>/.mz/task/<task_name>/

## Change to route
<the decision text verbatim>

## Overrides
artifact: <adr | rfd | design | auto>   (auto = you choose)
rich: <true | false>

## Brief and research
<PROJECT_ROOT>/.mz/task/<task_name>/brief.md   (the user's stage, options and priorities)
<PROJECT_ROOT>/.mz/task/<task_name>/research.md

## Algorithm
Read <SKILL_DIR>/references/artifact-router.md and apply Gate A then Gate B verbatim. Gate B decides on the brief's Stage.

## Output
Overwrite <PROJECT_ROOT>/.mz/task/<task_name>/routing.md with the routing decision and emit the decision block (ARTIFACT / GATE_FIRED / WEIGHT / STATUS_VOCAB / OVERRIDE + rationale), then STATUS:.
```

Single-agent dispatch, no manifest.

## Step 2.2 — Consume the routing decision

Read `routing.md` (or the returned block). Parse and store: `ARTIFACT` (`none|adr-nygard|adr-madr|rfd|design`), `STAGE`, `WEIGHT` (`light|heavy|n/a`), `STATUS_VOCAB`, and the rationale.

Handle the router's `STATUS:` line:

- `DONE` / `DONE_WITH_CONCERNS` → proceed (log any concern to `state.md`).
- `NEEDS_CONTEXT` → relay the router's named gap to the user via AskUserQuestion, add the answer to `brief.md` under `## Answers`, then dispatch again. Do not advance.
- `BLOCKED` → escalate via AskUserQuestion; do not fabricate a routing.

`ARTIFACT: none` here means the answers showed there is one sensible option after all. Take the exemption path in `phases/interview.md` with `Phase: 2`, and stop.

Emit a visible routing block: `ARTIFACT`, `WEIGHT`, `STATUS_VOCAB`, the one-line rationale, and the screen's artifact when it differs.

## Step 2.3 — Read the matching template

Read the template the router selected, in full, with the Read tool:

| Router `ARTIFACT` | Template to read                                | Target dir later  | Default status  |
| ----------------- | ----------------------------------------------- | ----------------- | --------------- |
| `adr-nygard`      | `<SKILL_DIR>/references/adr-nygard-template.md` | `docs/decisions/` | `proposed`      |
| `adr-madr`        | `<SKILL_DIR>/references/adr-madr-template.md`   | `docs/decisions/` | `proposed`      |
| `rfd`             | `<SKILL_DIR>/references/rfd-template.md`        | `docs/rfcs/`      | `prediscussion` |
| `design`          | `<SKILL_DIR>/references/design-doc-template.md` | `docs/design/`    | `draft`         |

## Step 2.4 — Draft into `draft.md`

The orchestrator writes the intake draft itself: a small markdown fill, revised in-loop during Phase 3. Populate the template from the decision, the brief and the research:

- The options are the brief's `Options` answer, each described from `research.md`. Ground context, consequences and trade-offs in the research and cite the path or source it gives; weigh them against the brief's `Priorities`.
- A related record the user marked **Supersedes** goes in the template's supersedes or links field.
- Where a section's content is genuinely not yet known (an RFD's `Determinations`, a trade-off the research left open, a `## Gaps` line), write `<to be resolved in discussion>`; do not invent facts to fill a heading. Each `## Assumptions` line from the brief appears in the draft as a stated assumption, so the critics and the gate see it.
- Copy the AgDR provenance fence shape into the header exactly as the template shows it, with placeholder values: `gov-artifact-writer` embeds the real fence from `provenance.md` in Phase 5.
- Set the artifact's own `status` to the default for its type from the table above.
- Write the result to `<PROJECT_ROOT>/.mz/task/<task_name>/draft.md` (transient, **not** `docs/` yet). Append it to `FilesWritten`.

## Step 2.5 — Carry weight forward and advance

Record `WEIGHT` (`light`/`heavy`) and the resolved artifact type in `state.md`: Phase 3 scales its panel on the weight, Phase 5 resolves the target dir from the type. Update `state.md`: `Phase: 3`, `phase_complete: true` for Phase 2, refresh `what_remains` (e.g. "run the discuss panel", "human sign-off gate", "write to docs/"). Emit a short transition block, then read `phases/discuss.md`.

## Anti-rationalization — do not skip the router

| Rationalization                                          | Rebuttal                                                                                                                                                                                                                    |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "The screen already routed it, I'll reuse that."         | The screen saw only the text. The user's Stage answer decides Gate B, and the research can change the option count and so the weight. Route again every run.                                                                |
| "The user passed `artifact:adr`, so routing is settled." | The override sets the artifact, not the weight. The router still emits `WEIGHT` (which scales Phase 3) and records any override-vs-inference disagreement as a `Nit:`. The dispatch is cheap; its metadata is load-bearing. |
| "I can guess the weight myself and save a dispatch."     | Weight decides whether four opus critics run or one sonnet critic does: a real cost and rigor difference. The router computes it from the stage, the option count and the artifact type.                                    |

## Notes

- The router writes only `routing.md` and never drafts. The draft is the orchestrator's job, the durable write is `gov-artifact-writer`'s. Three distinct lanes; keep them distinct.
- `draft.md` is the single source the Phase 3 critics read and the Phase 4 gate presents. There is exactly one `draft.md`; revisions overwrite it in place, never fork it.
