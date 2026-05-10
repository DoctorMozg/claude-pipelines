# Approval Gate — Shared Conventions

Canonical pattern for every user approval gate across mz-dev-pipe skills. Gates are the most expensive UX surface in the pipeline — they cost user attention. This file defines the two-surface format, the cost-preview line, and the unattended-mode bypass so every gate looks the same and behaves predictably.

## Two-surface pattern

Every gate has TWO chat-visible surfaces:

1. **Pre-gate text block** — a chat-visible bullet block emitted by the orchestrator BEFORE the AskUserQuestion call. Contains: bold title, 1-2 sentence summary, **Approve** / **Reject** / **Feedback** option list, and the cost-preview line.
1. **AskUserQuestion body** — carries the verbatim artifact (plan.md, panel.md, findings.md, …) and closes with the literal sentence: `Type **Approve** to proceed, **Reject** to cancel, or type your feedback.`

Never collapse the two surfaces into one. The pre-gate block is for orientation; the AskUserQuestion body is for the artifact bytes the user must read.

## Pre-gate block template

```text
**<Gate title>**
<1-2 sentence summary of what is being approved and what happens next>

- **Approve** → <next-phase outcome>
- **Reject** → <abort outcome>
- **Feedback** → <feedback-loop outcome>

Approve cost (estimated): <N> agents × ~<X>k tokens ≈ ~$<Y.YY> on <model tier>
```

## Cost-preview line

Format: `Approve cost (estimated): <N> agents × ~<X>k tokens ≈ ~$<Y.YY> on <model tier>`

How to compute the estimate at the gate site:

- **`<N>` (agent count)** — sum the dispatches that will fire between this gate and the next user gate. For build Phase 2 → Phase 3-11, count: 1 test-writer + 3 test-reviewers + N coders (one per parallel wave from plan.md) + 1 code-reviewer + 1 final reviewer + 1 optimizer + 1 completeness-checker. If a count depends on plan parsing, read the plan's work-unit count and use it as N.
- **`<X>k tokens`** — rough per-agent budget. Default assumptions: research/review agents ~12k input + 4k output ≈ 16k; coder agents ~20k input + 8k output ≈ 28k; planner agents ~10k input + 6k output ≈ 16k. Use the dominant agent type for the phase.
- **`<Y.YY>`** — `<N> × <X>k × price_per_1k_tokens / 1000`. Use the active model's published price.
- **`<model tier>`** — name the dominant tier ("Sonnet", "Opus", "mixed"). If tiers vary across the dispatched agents, use "mixed".

The estimate is order-of-magnitude — never claim it is precise. The point is to make a 30-coder fan-out feel different from a 3-coder fan-out at the moment of approval. Off-by-2× is fine; off-by-10× is the bug this preview prevents.

## AskUserQuestion body convention

```text
<one-line orientation sentence — what the artifact is and why approval is needed>

<verbatim artifact contents>

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

Never substitute a path, summary, or `<contents of artifact>` placeholder. The user must read the actual bytes in the question itself — if context compaction destroys their memory of an earlier iteration, the gate is the only place they re-orient.

## Response handling

- **`approve`** (case-insensitive) → update state to the next-phase token, proceed.
- **`reject`** (case-insensitive) → update state to `aborted_by_user`, stop. Do not re-dispatch any agent.
- **Anything else** → treat as feedback. Apply the requested changes, overwrite the artifact, return to the gate, re-read the artifact, re-present via AskUserQuestion with the full new contents. **Loop until explicit Approve.** Never proceed without explicit approval.

## Unattended mode (`MZ_DEV_PIPE_AUTO_APPROVE`)

When the environment variable `MZ_DEV_PIPE_AUTO_APPROVE=1` is set, the orchestrator skips the AskUserQuestion call and logs `auto-approved (unattended mode)` to chat and to `.mz/task/<task_name>/state.md` under `## Auto-approvals`. The pre-gate block is still emitted so the chat transcript shows what would have been approved.

This bypass exists for CI and scheduled runs. It is opt-in only — never default-on. Variant gates with menu options (more than `Approve / Reject / Feedback`) MUST NOT auto-approve; they require an explicit value choice.

## Variant: menu gates

Some gates present more than three options (panel-composition gates with optional swaps, scope-selection gates with branch/global/working modes). For these, format each option as `**<Name>** — <one-sentence summary>` in the pre-gate block, then list the same options in the AskUserQuestion options array. The cost-preview line still applies and should be computed for the most-likely chosen option, with a note: `Cost varies by selection — estimate shown for <default option>`.
