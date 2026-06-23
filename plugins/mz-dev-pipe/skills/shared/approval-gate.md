# Approval Gate — Shared Conventions

Canonical pattern for every user approval gate across mz-dev-pipe skills. Gates are the most expensive UX surface in the pipeline — they cost user attention. This file defines the two-surface plan pattern, the cost-preview line, and the unattended-mode bypass so every gate looks the same and behaves predictably.

## Two-surface plan pattern

Gates are modeled on Claude Code's plan mode: the artifact is rendered as an ordinary markdown chat message — the way a plan appears in plan mode — and `AskUserQuestion` is only the short selector beneath it.

1. **Surface 1 — the plan message**: a normal markdown chat message, emitted by the orchestrator BEFORE the `AskUserQuestion` call, carrying the **full verbatim artifact** (plan.md, panel.md, findings.md, …). It opens with a `## Plan for review — <skill>` heading, contains the verbatim artifact, and closes with a `---` rule and a one-line footer.
1. **Surface 2 — the AskUserQuestion selector**: a short call. `question` is one orientation line pointing at the plan message above; `options` are exactly **Approve** and **Reject**. No verbatim artifact in the question body — it lives in Surface 1. No "Feedback" option — `AskUserQuestion`'s always-present free-text reply field carries feedback.

Never collapse the two surfaces. Surface 1 is the artifact the user reads; Surface 2 is the decision. The artifact is never buried inside the `AskUserQuestion` body — that body truncates in chat history and renders cramped.

## Plan message template

```text
## Plan for review — <skill>

<verbatim artifact contents>

---
**Approve** → <next-phase outcome>  ·  **Reject** → <abort outcome>  ·  reply with feedback to revise

Approve cost (estimated): <N> agents × ~<X>k tokens ≈ ~$<Y.YY> on <model tier>
```

Emit the full verbatim artifact — never a path, a summary, or a `<contents of artifact>` placeholder. The user must read the actual bytes in the message; if context compaction destroys their memory of an earlier iteration, this message is the only place they re-orient.

## Cost-preview line

Format: `Approve cost (estimated): <N> agents × ~<X>k tokens ≈ ~$<Y.YY> on <model tier>`

The cost-preview line sits in the footer of the plan message (Surface 1).

How to compute the estimate at the gate site:

- **`<N>` (agent count)** — sum the dispatches that will fire between this gate and the next user gate. For build Phase 2 → Phase 3-11, count: 1 test-writer + 3 test-reviewers + N coders (one per parallel wave from plan.md) + 1 code-reviewer + 1 final reviewer + 1 optimizer + 1 completeness-checker. If a count depends on plan parsing, read the plan's work-unit count and use it as N.
- **`<X>k tokens`** — rough per-agent budget. Default assumptions: research/review agents ~12k input + 4k output ≈ 16k; coder agents ~20k input + 8k output ≈ 28k; planner agents ~10k input + 6k output ≈ 16k. Use the dominant agent type for the phase.
- **`<Y.YY>`** — `<N> × <X>k × price_per_1k_tokens / 1000`. Use the active model's published price.
- **`<model tier>`** — name the dominant tier ("Sonnet", "Opus", "mixed"). If tiers vary across the dispatched agents, use "mixed".

The estimate is order-of-magnitude — never claim it is precise. The point is to make a 30-coder fan-out feel different from a 3-coder fan-out at the moment of approval. Off-by-2× is fine; off-by-10× is the bug this preview prevents.

## AskUserQuestion selector convention

```text
question: "The plan above is ready for review. Approve to proceed, or Reject to abort — reply with feedback to revise."
options:
  - Approve — proceed to <next phase>
  - Reject  — abort, nothing written
```

Never embed the verbatim artifact in the question body — Surface 1 already carries it. Never add a third "Feedback" option: a reply that is neither Approve nor Reject is feedback.

## Response handling

- **Approve** → update state to the next-phase token, proceed.
- **Reject** → update state to `aborted_by_user`, stop. Do not re-dispatch any agent.
- **Any other reply** → treat as feedback. Apply the requested changes, overwrite the artifact, return to Surface 1, re-emit the full updated plan message from scratch (full verbatim — never a diff, never a summary), re-present the selector. **Loop until explicit Approve.** Never proceed without explicit approval.

## Journal logging

Every gate is recorded in the interaction journal (`.mz/journal.md`). In attended mode the `mz-memory` `PostToolUse` hook captures the `AskUserQuestion` question and answer verbatim automatically — nothing is required for the audit baseline. You MAY append an enrichment entry (skill, task, phase, the verbatim artifact) for a record that outlives the chat transcript; wrap any sensitive span in `<private>…</private>` so it is redacted before write.

In **unattended mode there is no `AskUserQuestion` call, so the hook never fires** — the orchestrator MUST append the gate entry itself or the auto-approved decision leaves no audit trace (see below). See `guidelines/JOURNAL_GUIDELINES.md` for the entry format and redaction convention.

## Unattended mode (`MZ_DEV_PIPE_AUTO_APPROVE`)

When the environment variable `MZ_DEV_PIPE_AUTO_APPROVE=1` is set, the orchestrator skips the `AskUserQuestion` call and logs `auto-approved (unattended mode)` to chat and to `.mz/task/<task_name>/state.md` under `## Auto-approvals`. The plan message (Surface 1) is still emitted so the chat transcript shows what would have been approved.

Because the journaling hook fires on `AskUserQuestion` — which is skipped here — the orchestrator also appends the auto-approval to `.mz/journal.md` (gate label, `auto-approved`, task, phase) so unattended runs keep a complete audit trail. Append it with a single Bash redirect, wrapping any sensitive span in `<private>`:

```bash
printf '### %s · <skill> · <task> · gate\n- outcome: auto-approved (unattended)\n- phase: <n> (<name>)\n\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>.mz/journal.md
```

This bypass exists for CI and scheduled runs. It is opt-in only — never default-on. Variant gates with menu actions (more than `Approve / Reject`) MUST NOT auto-approve; they require an explicit value choice.

## Variant: menu gates

Some gates present extra named actions beyond Approve/Reject (panel-composition gates with optional swaps, scope-selection gates with branch/global/working modes). For these, each named action becomes an `AskUserQuestion` `options` entry formatted as `**<Name>** — <one-sentence summary>`, and the plan message footer lists the same actions. Feedback still rides the free-text reply field — never add a "Feedback" option. The cost-preview line still applies and should be computed for the most-likely chosen option, with a note: `Cost varies by selection — estimate shown for <default option>`.
