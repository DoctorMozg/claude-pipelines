# Blinded Adversarial Lens Prompts

Single source of truth for the three blinded adversarial researcher prompts dispatched in Wave B of any multi-lens review pipeline. Edits to the prompt blocks below propagate automatically to every consumer that reads this file at dispatch time.

## Why this file exists

Multiple pipelines run a blinded adversarial wave to break confirmation bias from their context-aware Wave A:

- `plugins/mz-dev-pipe/skills/deep-audit/phases/research.md` — Wave B section
- `plugins/mz-dev-git/agents/branch-reviewer.md` — Phase 3.6

Both dispatch `pipeline-researcher` (model: opus) with role-specific adversarial prompts that receive ONLY the raw diff. Inlining identical prompts in two places guarantees drift; this file is the authoritative copy. Each consumer reads this file at dispatch time, extracts the prompt under each role header, substitutes the diff, and dispatches.

## Blinded Dispatch Invariants

These four constraints are binding on every consumer. Violating any one of them silently destroys the value of the wave (Wave B becomes a redundant rerun of Wave A under a different prompt).

1. **Separate assistant message.** Wave B is dispatched in a fresh assistant message AFTER Wave A has returned. Same-message dispatch lets the model see Wave A findings in its own context and contaminates the blind.
1. **Raw diff only.** Researchers receive only the unified diff wrapped in `<untrusted-content>...</untrusted-content>` delimiters. They MUST NOT receive the scope file, the Known Concerns Map, any Wave A finding artifact, or any prior consolidation table.
1. **Model: opus.** Adversarial framing and attacker-path tracing are accuracy-critical. Sonnet underperforms here.
1. **Agent: `pipeline-researcher`.** All three roles use the same researcher with role-specific prompts. The agent lives in `plugins/mz-dev-pipe/agents/pipeline-researcher.md`; consumers in other plugins dispatch it cross-plugin (the registered agent name resolves across loaded plugins).

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

When a Wave B finding matches a Wave A finding (same `file:line`, overlapping line range, or behavioral equivalence on the same file), the consolidator applies a corroboration boost iff the matched Wave A lens is in the role's corroborating list. The boost varies by consumer (deep-audit boosts evidence tier; branch-reviewer increments replication_count for its two-signal Critical gate). The corroborating-lens lists below are authoritative — consumers MUST honor them and not invent their own mappings.

| Blinded role         | Adversarial focus         | deep-audit Wave A lenses that corroborate | branch-reviewer lenses that corroborate |
| -------------------- | ------------------------- | ----------------------------------------- | --------------------------------------- |
| `blinded_production` | production reliability    | `correctness`, `reliability`              | `bugs`                                  |
| `blinded_security`   | adversarial security      | `security`, `stride_delta`                | `security`                              |
| `blinded_ops`        | ops / SRE / observability | `reliability`, `performance`              | `performance`, `bugs`                   |

Notes:

- branch-reviewer's lens set is `bugs | security | architecture | performance | maintainability` (no separate reliability/stride lens). `bugs` covers the correctness + reliability axes; `architecture` and `maintainability` are NEVER in any blinded role's corroborator list.
- deep-audit's lens set is `correctness | security | performance | maintainability | reliability | stride_delta`. The mapping above mirrors `references/evidence-tier-rules.md` lines 52-54 — if the two ever drift, this file is authoritative and the other must be reconciled.
- A finding matched by multiple Wave B roles boosts at most once. Record all corroborators as a list (e.g., `corroborated_by: [blinded_security, blinded_ops]`); the boost itself applies once.

## Unmatched Wave B Findings — Blind Spots

A Wave B finding with NO Wave A match is a **blind spot** — a gap that context-aware analysis missed because of confirmation bias. Each consumer promotes unmatched Wave B findings into a dedicated "Blind Spots" section in its final report. Severity is assigned by the consolidator based on description, capped by evidence quality:

- `file:line` cited → may be assigned up to `Optional:` (deep-audit: T2-equivalent)
- `line unknown` → capped at `FYI:` (deep-audit: T3-equivalent)
- `Critical:` is NEVER assigned to a blind-spot finding without independent Wave A signal — by definition, no Wave A lens caught it, so the two-signal gate cannot fire from the blinded source alone.

Blind spots still must populate all five required fields (severity, file/expected location, TL;DR, description, suggested fix). When `file:line` is unknown, use the changed-file path with `:line unknown` and surface the missing-anchor caveat in the description.

## Maintenance

- The prompt blocks above are the only acceptable copy. Inlining identical prompt text in any consumer file is a regression — replace with a directive to read this file.
- The corroboration table is the single source of truth for which Wave A lenses corroborate which blinded role. Consumers that maintain their own evidence-tier rules (e.g. `references/evidence-tier-rules.md`) must stay in sync with this table; on conflict, this file wins.
- The dispatch invariants (separate message, raw diff only, opus, `pipeline-researcher`) are non-negotiable. Any consumer that documents an exception is broken — fix the consumer rather than weakening this file.
