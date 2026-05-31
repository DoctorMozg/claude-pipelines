# Phase 3: Decide — The Human Sign-Off Gate

This is the gate the whole plugin exists for. AI-authored decisions get far weaker human review than human-authored ones; this phase forces a real human signature onto the record before anything is committed to `docs/`. An agent proposed the decision and a panel critiqued it — but only a human approves it here.

**NOTE — there is no auto-approve bypass on this gate.** Other pipelines support an unattended `AUTO_APPROVE` mode; this one does not, by design. A recorded human signature is the entire point. No environment variable, no flag, and no "the critics all passed" consensus substitutes for the human choosing **Approve**. If the run is unattended, the pipeline waits here — it does not self-sign.

This gate uses the two-surface plan pattern: the artifact is emitted as an ordinary markdown chat message (the way a plan appears in plan mode), then a short AskUserQuestion selector beneath it.

## Inputs (from Phase 2)

- `.mz/task/<task_name>/draft.md` — the converged (or accepted-with-unresolved) artifact.
- The verdict: `discussion_<N>.md` (heavy) or `discuss_<N>_quick.md` (light), with the final `AGGREGATE:`/`VERDICT:`.
- `.mz/task/<task_name>/provenance.md` — `human_signoff: pending`.
- The artifact type and its target `docs/` path; any carried unresolved caveats.

## Step 3.1 — Delegation guard

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated. No critic, synthesizer, or writer agent runs the gate — handing the human sign-off to a subagent defeats it. The orchestrator that has held the run's context from Phase 0 is the one that presents and records the signature.

## Step 3.2 — Mandatory pre-read

Before emitting the gate, Read these with the Read tool and capture their full contents into context:

- `.mz/task/<task_name>/draft.md` — the complete artifact body.
- The converged verdict file — `.mz/task/<task_name>/discussion_<N>.md` (heavy) or `.mz/task/<task_name>/discuss_<N>_quick.md` (light) — for the final verdict block and any remaining findings.
- `.mz/task/<task_name>/provenance.md` — the AI-provenance block to show the user (still `pending` at this point).

The discuss phase must have converged (`AGGREGATE: PASS` / `VERDICT: PASS`) or reached an explicit accept-with-unresolved before this gate fires. Read the actual bytes — do not present from memory; context compaction may have destroyed the draft you revised three iterations ago.

## Step 3.3 — Surface 1: emit the plan message

Emit the artifact, verdict, and provenance as an **ordinary markdown chat message** (not inside a tool call), so the markdown renders fully and survives in scrollback. Emit the **full verbatim contents** you read in Step 3.2 — never substitute a path, a line count, a `<contents of draft.md>` placeholder, or a summary. Structure (each `<verbatim ...>` marker replaced by the bytes you read):

```
## Decision ready for sign-off — govern

<artifact type>, <one-way | two-way> door · verdict: <PASS | accepted with unresolved>. A human signature is required before this is recorded; on approval it is committed to `<docs target path>`.

### Artifact (draft.md → <docs target path>)

<verbatim draft.md contents>

### Panel Verdict

<verbatim verdict block from discussion_<N>.md or discuss_<N>_quick.md, plus any unresolved Critical findings>

### AI-Provenance (embedded in the committed artifact)

<verbatim provenance.md contents — currently human_signoff: pending>

---
**Approve** → stamp your sign-off, advance status, write the durable artifact  ·  **Reject** → mark aborted, nothing written to docs/  ·  reply with feedback to revise
```

The door class comes from the reversibility critic (heavy) or the quick critic's reversibility lens (light); state the concrete `docs/` path the artifact will land in — it is the consequence the user is authorizing. The provenance block is shown so the human sees exactly what AI-origin metadata — the agent, the model id, the trigger — will be committed alongside their signature, and is signing that record, not just the prose.

## Step 3.4 — Surface 2: the AskUserQuestion selector

Immediately after the plan message, call AskUserQuestion as a short selector. Do **not** re-embed the draft, verdict, or provenance — they live in the plan message above.

- question: `The decision above is ready for your sign-off.`
- options: **Approve** — stamp the sign-off and write the durable artifact · **Reject** — abort, write nothing to `docs/`

Two named options only. Do not add a "Feedback" option — any reply that is not Approve or Reject is feedback, and it rides AskUserQuestion's always-present free-text field.

## Step 3.5 — Response handling

- **Approve** → the human has signed. In `provenance.md`, set `human_signoff: <user>@<ISO-8601>` (the approver id and the moment of approval, e.g. `drmozg@2026-05-31T15:10:00Z`) — overwrite the `pending` value. Advance the artifact's own `status` field by type: **ADR** `proposed → accepted`, **RFD** `prediscussion → discussion`, **design** `draft → reviewed`. Update `state.md` (`phase_complete: true` for Phase 3, record the signature), then proceed to Phase 4. Read `phases/record.md`.
- **Reject** → update `state.md` to `Status: aborted_by_user` and stop. **Write nothing to `docs/`.** Leave `provenance.md` at `human_signoff: pending` and leave all scratch files on disk — the user can resume or discard manually. Do not dispatch `gov-artifact-writer`.
- **Any other reply (feedback)** → incorporate it. If the change is **structural** (alters the decision, the options, or the design — anything a critic lens would re-examine), revise `draft.md` and re-run the discuss phase (`phases/discuss.md`) before returning here. If it is a **wording or scoping polish**, just revise `draft.md` directly. Either way, return to Step 3.2, re-read the updated `draft.md`, and **re-emit the entire plan message from scratch** with the full new contents — never diff-only, never summary-only, since context compaction may have destroyed the user's memory of earlier iterations. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 4 without explicit approval.

## Step 3.6 — Never proceed without explicit approval

The approval gate is the human's last line of defense and the plugin's reason to exist. Never proceed to Phase 4 on critic consensus, on a clean `AGGREGATE: PASS`, on an empty response, or on silence. A passing panel is the agents agreeing among themselves — it is not the human's approval. Only an explicit **Approve** stamps the sign-off and authorizes the write to `docs/`. If you are tempted to skip this because "the verdict was clean," that is exactly the AI-authored-decision-without-human-review failure mode this gate prevents.

## Notes

- `gov-artifact-writer` refuses to write while `provenance.md` reads `human_signoff: pending`. Stamping the real signature in Step 3.5 is the precondition that unlocks Phase 4 — get the order right: sign first, then dispatch the writer.
- Advancing the artifact's `status` here (e.g. ADR `proposed → accepted`) is the in-draft status; the writer initializes the committed artifact's status from the configured vocabulary at record time and the values agree by type.
- On reject, the absence of any `docs/` write is the correct, complete outcome — a rejected decision that left no durable trace is the gate working, not a failure to finish.
