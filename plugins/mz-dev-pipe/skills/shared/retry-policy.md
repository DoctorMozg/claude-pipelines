# Retry Policy — Typed Error Matrix

Canonical retry classes and budgets for any agent dispatch or external call inside mz-dev-pipe skills. Replaces the ad-hoc "retry once" / "escalate immediately" decisions previously scattered across phase files, where each loop re-derived the policy from scratch.

## Error classes

When a dispatched agent returns a terminal STATUS or VERDICT line (per `shared/agent-status-protocol.md`), classify the failure into one of three classes before deciding what to do next.

| Class                | Examples                                                                                                    | Default retry budget                                         |
| -------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `transient`          | Network blip, rate-limit, agent timeout, MCP server hiccup, sub-agent crash with no contract violation      | 2 retries with jittered backoff (1s → 4s)                    |
| `contract-violation` | Agent returns malformed STATUS line, missing required output file, schema mismatch, wrong artifact path     | 1 retry with clarified prompt; on second violation, escalate |
| `blocked`            | Agent emits `STATUS: BLOCKED`, missing tool/credential, env unset, gh CLI 4xx after MCP fallback also fails | 0 retries — escalate immediately via `AskUserQuestion`       |
| `expected_failure`   | Test was supposed to fail (RED phase), reviewer was supposed to find issues, audit returns findings         | Not a failure — proceed per the skill's normal handling      |

## Decision flow

For every dispatched agent:

1. **Read the agent's terminal line.** Use `shared/agent-status-protocol.md` to parse `STATUS:` / `VERDICT:`.
1. **If terminal line is missing entirely** → classify as `contract-violation`. Do not re-prompt without the explicit "your previous output was missing the STATUS line" preamble.
1. **Classify into one of the four error classes** above.
1. **Apply the retry budget**. Increment a per-call retry counter (NOT the loop-level iteration counter).
1. **If budget exhausted** → escalate via the standard escalation gate below. Do not silently advance.

## Escalation gate

Three options, presented via `AskUserQuestion`:

- **Retry once more** → reset that single retry counter, do not reset the loop counter.
- **Skip and continue** → mark the work unit as `failed` in `state.md`, proceed without it.
- **Abort task** → write `Status: failed` to `state.md`, stop. Do not write `Status: complete`.

Honor `MZ_DEV_PIPE_AUTO_APPROVE=1` for `transient` only — auto-default to `Skip and continue`. NEVER auto-default `contract-violation` or `blocked` — those require human judgment.

## Override precedence

Per-class budgets MAY be overridden at task start:

1. **Environment variable** — `MZ_DEV_PIPE_TRANSIENT_RETRIES=5`, `MZ_DEV_PIPE_CONTRACT_RETRIES=2`, `MZ_DEV_PIPE_BLOCKED_RETRIES=0` (the last one is fixed at 0 by design — overriding upward is rejected).
1. **Project config** — `.mz/config.toml` `[retry_budget]` table.
1. **Skill default** — values from this file.

## Distinction from iteration limits

This module governs **per-call retries** (agent A failed, do we re-dispatch agent A?). `shared/iteration-limits.md` governs **per-loop bounds** (the fix-test loop has run N times, do we exit?). They compose: a single loop iteration may include multiple retries against the same agent.

Loop-counter values must be checkpointed to `state.md` after each iteration per the resume protocol. Per-call retry counters are ephemeral — they reset on every loop iteration and need not be persisted.

## Why typed classes

Without typed error classes, every retry loop re-derives "should we retry or escalate?" from local context. This produces inconsistent UX (some loops retry forever, some escalate immediately) and makes resume harder (the resume entry can't know whether the recorded retry counter is exhausted or fresh). Typed classes give every loop the same vocabulary and let the resume protocol restore counter state predictably.
