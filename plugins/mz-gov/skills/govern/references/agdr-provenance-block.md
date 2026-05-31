# AgDR Provenance Block

Every governed artifact carries an AI-provenance fence in its header. It records *which agent, running which model, under what trigger* proposed the decision — and crucially, **whether a human signed off**. The fence is the machine-readable trace that turns "the AI decided this" into "this agent proposed it on this date and this human approved it".

> **Source & caveat.** The field set is borrowed from the emerging AgDR (Agent Decision Record) proposal — `me2resh/agent-decision-record`. It is a single low-traction proposal seeking community input, and the "AgDR" name collides with unrelated efforts. Treat this as a **borrowed pattern — revalidate the field names** against the upstream spec before relying on exact specifics.

## What `mz-gov` adds

AgDR as proposed has **no human approval step** — its `status` moves straight to `executed` with no human-gated transition. That's the gap `mz-gov` exists to close. We add one field the upstream spec omits:

- **`human_signoff`** — the recorded human approval. An agent **proposes**; a human **approves**. A decision artifact whose `human_signoff` is still `pending` is **not done**.

This single field is the point of the plugin. Everything else is provenance; this is accountability.

## Delimiters

Wrap the block in HTML comments so it survives in rendered markdown without showing as visible content, and so tooling can find it by exact string:

```
<!-- mz-gov:agdr start -->
...
<!-- mz-gov:agdr end -->
```

Exactly one `start`/`end` pair per artifact. Place it in the artifact header — for an ADR, directly above the Status line; for a design doc or RFD, at the very top under the title.

## Fields

| Field           | Type / format                               | Notes                                                                                                                                           |
| --------------- | ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `agdr_id`       | short stable id                             | unique per decision; e.g. `agdr-0007`. Reuse the artifact's own number when there is one.                                                       |
| `timestamp`     | ISO-8601                                    | when the agent produced the proposal, e.g. `2026-05-31T14:32:00Z`                                                                               |
| `agent`         | string                                      | the proposing agent, e.g. `gov-artifact-writer`                                                                                                 |
| `model`         | exact model id                              | not a family name — the full identifier, e.g. `claude-opus-4-8`                                                                                 |
| `trigger`       | `user-prompt \| hook \| automation`         | how the run started (see below)                                                                                                                 |
| `status`        | `proposed → accepted/executed → superseded` | the agent-side lifecycle of the *proposal*                                                                                                      |
| `human_signoff` | `pending` or `<approver>@<ISO-8601>`        | **the field AgDR omits.** `pending` until a human approves; then the approver id and the moment they signed, e.g. `drmozg@2026-05-31T15:10:00Z` |

### `trigger` values

- `user-prompt` — a human directly asked for this run.
- `hook` — a lifecycle hook fired the run. (`mz-gov` ships no hooks, but the field exists for artifacts authored under other tooling.)
- `automation` — policy-directed proactive invocation: the governance policy block told Claude to run `/govern` itself before baking a substantial decision into code. This is **not** a hook firing — it's an agent following a standing instruction. Use `automation` and read it as "self-initiated per policy", not "an event handler ran".

### `status` vs `human_signoff` — keep them distinct

`status` tracks the *proposal's* state from the agent's side (proposed, then executed once written, eventually superseded). `human_signoff` tracks the *human gate*. A proposal can be `status: proposed` with `human_signoff: pending` (awaiting approval), and only after a human approves does the orchestrator stamp the signoff and let the artifact advance. Never let `status` reach `executed` while `human_signoff` is still `pending` — that's the exact failure mode the plugin prevents.

## Template

Copy this into the artifact header and fill the placeholders:

```markdown
<!-- mz-gov:agdr start -->
agdr_id: <agdr-NNNN>
timestamp: <YYYY-MM-DDThh:mm:ssZ>
agent: <agent-name>
model: <exact-model-id>
trigger: <user-prompt | hook | automation>
status: <proposed | accepted | executed | superseded>
human_signoff: <pending | approver@YYYY-MM-DDThh:mm:ssZ>
<!-- mz-gov:agdr end -->
```

## Filled example

```markdown
<!-- mz-gov:agdr start -->
agdr_id: agdr-0001
timestamp: 2026-05-31T14:32:00Z
agent: gov-artifact-writer
model: claude-opus-4-8
trigger: user-prompt
status: executed
human_signoff: drmozg@2026-05-31T15:10:00Z
<!-- mz-gov:agdr end -->
```

This block says: the writer agent, running `claude-opus-4-8`, produced this proposal at 14:32 because a human asked; the artifact was written (`executed`); and `drmozg` signed off at 15:10. The decision is traceable end to end and a human's name is on it.
