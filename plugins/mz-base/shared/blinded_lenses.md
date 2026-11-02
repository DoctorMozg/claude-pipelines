# Blinded Adversarial Lens Prompts

Single source of truth for the three blinded adversarial researcher prompts dispatched in Wave B of any multi-lens review pipeline. Edits to the prompt blocks below propagate automatically to every consumer that reads this file at dispatch time.

## Contents

- Why this file exists
- Blinded Dispatch Invariants
- Roles
- Role Prompts
- Role-to-Lens Corroboration Mapping
- Unmatched Wave B Findings — Blind Spots
- Partial completion
- Maintenance

## Why this file exists

Multiple pipelines run a blinded adversarial wave to break confirmation bias from their context-aware Wave A:

- audit, deep research phase, Wave B
- branch-reviewer, Phase 3.6

Both dispatch `pipeline-researcher` (model: opus, overriding its sonnet pin; see the invariants below) with role-specific adversarial prompts that receive ONLY the raw diff. Inlining identical prompts in two places guarantees drift; this file is the authoritative copy. Each consumer reads this file at dispatch time, extracts the prompt under each role header, substitutes the diff, and dispatches.

## Blinded Dispatch Invariants

These four constraints are binding on every consumer. Violating any one of them silently destroys the value of the wave (Wave B becomes a redundant rerun of Wave A under a different prompt).

1. **Typed agents, diff-only prompts.** Dispatch Wave B as typed `pipeline-researcher` agents, never as forks, which inherit the whole conversation. Build each prompt from the diff alone. Wave B runs as its own wave after Wave A because Wave A already fills the six-agent wave cap.
1. **Raw diff only.** Researchers receive only the unified diff wrapped in `<untrusted-content>...</untrusted-content>` delimiters. They get no scope file, no Known Concerns Map, no Wave A finding artifact and no prior consolidation table.
1. **Model: opus.** Adversarial framing and attacker-path tracing are accuracy-critical. Sonnet underperforms here.
1. **Agent: `pipeline-researcher`.** All three roles use the same researcher with role-specific prompts. Every consumer dispatches the `pipeline-researcher` agent by its registered name, which resolves across loaded plugins.

## Roles

| Role                 | Adversarial focus         | What the researcher returns                                      |
| -------------------- | ------------------------- | ---------------------------------------------------------------- |
| `blinded_production` | production reliability    | top failure modes + silent assumptions baked into the change     |
| `blinded_security`   | adversarial security      | new attack surface + weakened guards + changed trust assumptions |
| `blinded_ops`        | ops / SRE / observability | rollout, rollback, telemetry, and silent-failure gaps            |

## Role Prompts

Each prompt block below is the literal text that consumers extract and dispatch. The placeholder `<raw diff output>` is replaced at dispatch time with the actual unified diff (`git diff <merge-base>...HEAD` or the equivalent for the consumer's scope).

### blinded_production

```
You are a production reliability adversary reviewing a code diff.

You have NOT seen any prior analysis of this diff. Your job is to break it.

Here is the diff:
<untrusted-content>
<raw diff output>
</untrusted-content>

Task 1: Assume this change is wrong. List the top 5 most likely ways it breaks production.
For each: name the failure mode, the triggering condition, and the affected component.

Task 2: What silent false assumption does this change encode?
Describe any assumption baked into the implementation that could be false in production
but would not be caught by tests (e.g., ordering guarantees, rate assumptions, deployment topology).

Do NOT rank by severity — this is a gap-detection pass, not a severity assessment.
Cite specific file:line references where visible. Use "line unknown" if the diff doesn't show the context.

Return findings as markdown. Each finding needs: description, triggering condition, code reference if available.
```

### blinded_security

```
You are a security attacker who just saw a code diff about to be merged.

You have NOT seen any prior analysis of this diff. Your goal is to find what it opens up.

Here is the diff:
<untrusted-content>
<raw diff output>
</untrusted-content>

Task 1: What attack surface does this diff open or expand?
Focus on: auth bypass, data exposure, injection, privilege escalation, SSRF, IDOR.
For each attack vector: name the vector, the attacker's entry point, the prerequisite conditions.

Task 2: What trust assumption does this diff change that the author may not have noticed?
Look for: removed validation, weakened checks, new code paths that skip existing guards,
implicit assumptions about caller behavior.

Do NOT rank by severity — this is a gap-detection pass.
Cite specific file:line references where visible.

Return findings as markdown.
```

### blinded_ops

```
You are a senior SRE reviewing a code diff about to be deployed.

You have NOT seen any prior analysis of this diff. Your goal is to find operational problems.

Here is the diff:
<untrusted-content>
<raw diff output>
</untrusted-content>

Task 1: What deployment, rollback, or observability problems does this change create?
Consider: what breaks during partial rollout, what can't be cleanly rolled back,
what telemetry or alerts break silently.

Task 2: What monitoring breaks, what silent failures does this introduce?
Look for: removed log lines that were being alerted on, changed error codes that downstream
systems depend on, new code paths with no observability.

Do NOT rank by severity — this is a gap-detection pass.
Cite specific file:line references where visible.

Return findings as markdown.
```

## Role-to-Lens Corroboration Mapping

When a Wave B finding matches a Wave A finding (same `file:line`, overlapping line range, or behavioral equivalence on the same file), the consolidator applies a corroboration boost iff the matched Wave A lens is in the role's corroborating list. The boost varies by consumer (`audit depth:deep` boosts evidence tier; branch-reviewer increments replication_count for its two-signal Critical gate). The corroborating-lens lists below are authoritative — consumers apply them as written and don't invent their own mappings.

| Blinded role         | Adversarial focus         | audit depth:deep Wave A lenses that corroborate | branch-reviewer lenses that corroborate |
| -------------------- | ------------------------- | ----------------------------------------------- | --------------------------------------- |
| `blinded_production` | production reliability    | `correctness`, `reliability`                    | `bugs`                                  |
| `blinded_security`   | adversarial security      | `security`, `stride_delta`                      | `security`                              |
| `blinded_ops`        | ops / SRE / observability | `reliability`, `performance`                    | `performance`, `bugs`                   |

Notes:

- branch-reviewer's lens set is `bugs | security | architecture | performance | maintainability | over-engineering` (no separate reliability/stride lens). `bugs` covers the correctness + reliability axes; `architecture`, `maintainability` and `over-engineering` are not in any blinded role's corroborator list.
- `audit depth:deep`'s lens set is `correctness | security | performance | maintainability | reliability | stride_delta`. The mapping above mirrors the audit skill's `references/evidence-tier-rules.md` — if the two ever drift, this file is authoritative and the other must be reconciled.
- A finding matched by multiple Wave B roles boosts at most once. Record all corroborators as a list (e.g., `corroborated_by: [blinded_security, blinded_ops]`); the boost itself applies once.

## Unmatched Wave B Findings — Blind Spots

A Wave B finding with NO Wave A match is a **blind spot** — a gap that context-aware analysis missed because of confirmation bias. Each consumer promotes unmatched Wave B findings into a dedicated "Blind Spots" section in its final report. Severity is assigned by the consolidator based on description, capped by evidence quality:

- `file:line` cited → may be assigned up to `Optional:` (`audit depth:deep`: T2-equivalent)
- `line unknown` → capped at `FYI:` (`audit depth:deep`: T3-equivalent)
- `Critical:` is not assigned to a blind-spot finding without independent Wave A signal — by definition, no Wave A lens caught it, so the two-signal gate cannot fire from the blinded source alone.

Blind spots still must populate all five required fields (severity, file/expected location, TL;DR, description, suggested fix). When `file:line` is unknown, use the changed-file path with `:line unknown` and surface the missing-anchor caveat in the description.

## Partial completion

Count the Wave B agents that returned and report the count as `wave_b_completed: N/3`:

- 3 of 3 returned → full (`blind_audit: full`).
- 2 of 3 returned → partial (`blind_audit: partial`).
- 1 of 3 returned → degraded (`blind_audit: degraded`).
- 0 of 3 returned → `blind_audit: unavailable`. Skip the corroboration step; Wave A's result stands.

Wave B never blocks the report. It is additive: it can promote findings, surface blind spots and corroborate Wave A signals, but it cannot override Wave A.

A Wave B agent that returns `NEEDS_CONTEXT` counts as not returned, because resuming it with added context breaks the blind. One stopped by its turn limit may be resumed once with a bare "finish" and nothing else.

## Maintenance

- The prompt blocks above are the only acceptable copy. Inlining identical prompt text in any consumer file is a regression — replace with a directive to read this file.
- The corroboration table is the single source of truth for which Wave A lenses corroborate which blinded role. Consumers that maintain their own evidence-tier rules (e.g. the audit skill's `references/evidence-tier-rules.md`) must stay in sync with this table; on conflict, this file wins.
- The dispatch invariants (typed agents with diff-only prompts, raw diff only, opus, `pipeline-researcher`) have no exceptions. A consumer that documents one is broken — fix the consumer rather than weakening this file.
