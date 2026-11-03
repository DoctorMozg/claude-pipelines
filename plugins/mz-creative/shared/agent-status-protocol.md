# Agent Status Protocol

Canonical source: AGENTS_GUIDELINES.md, "Status Protocol" and "Review Output" (repository guidelines, not shipped with the plugin).

A dispatched agent whose output the orchestrator consumes, or that writes artifacts for a later phase, ends with a `STATUS:` line carrying one of four values. The orchestrator handles all four before it moves on. Without a handler, retries loop silently or `DONE_WITH_CONCERNS` passes as `DONE`.

## DONE

The work is complete. Proceed.

## DONE_WITH_CONCERNS

The work is complete, and the agent lists its concerns in a `## Concerns` section above the status line. Settle concerns about correctness or scope before the next review step. Log the rest under `## Concerns` in `state.md`, one line each, and proceed.

## NEEDS_CONTEXT

The agent can't continue without specific information, which it lists in a `## Required Context` section above the status line. Supply it once: resume the same agent with `SendMessage` and add the missing context, or, where the agent can't be resumed, dispatch it again with the context in the prompt. If it still lacks context, treat the result as `BLOCKED`.

An agent in a blinded wave is the exception. Resuming it with added context breaks the blind, so it counts as not returned, and the wave's partial-completion rule applies (`blinded_lenses.md`, "Partial completion").

## BLOCKED

A fundamental obstacle, such as a broken environment, an impossible constraint or an ambiguous spec, described in a `## Blocker` section above the status line. First try what the orchestrator can change itself: more context, a stronger model or a smaller task. When none of that applies, escalate:

- In an interactive main session, ask the user with AskUserQuestion, giving the blocker and the options.
- In a subagent, or where nobody can answer (`claude -p` without a permission host, `--permission-prompts none`, `dontAsk`), finish the work that doesn't depend on the answer. Then write the blocker and the options to `state.md`, set `Status: blocked`, and stop. A skill running inside a subagent returns its own `STATUS: BLOCKED` with the blocker and the options.

Don't re-run a blocked dispatch unchanged. An unanswered or timed-out question is not a decision.

## Output without a valid status

Output with no valid final `STATUS:` line is never `DONE`, and a partial marking overrides any `STATUS:` line in it.

- **Partial**, because the agent hit its turn limit (`maxTurns`): resume it once with `SendMessage` and say what is left. Explore and Plan agents can't be resumed.
- **Failed** with an API error or a usage limit, or **stopped** by the user: don't resume or re-dispatch it. Treat it as `BLOCKED` and say why.
- **Empty or malformed**: re-dispatch once with something changed, as `retry-policy.md` describes.

When parsing, take the last `STATUS:` line. Several differing `STATUS:` lines count as no status.

## Token order

An agent emits only the tokens its role defines. When several appear, they come in this order:

1. Disclosure tokens where they arise: `STACK DETECTED:` (with a space) before the first research query, `CONFLICT DETECTED:` and `UNVERIFIED:` inline at the claim, and the `ZERO RESULTS` tokens from `retry-policy.md`.
1. `VERDICT:`, immediately before `STATUS:` when both appear.
1. `STATUS:`, as the final line with nothing after it. A subagent that reports through `SubagentHandback` puts the line inside that report, because only the report is delivered.

## Review verdicts

Every finding carries one label. `Critical:` blocks merge or plan advancement; `Nit:`, `Optional:` and `FYI:` are advisory. A defect that was there before the change is `FYI:`, not `Critical:`.

Only the agent that decides a gate emits a verdict, written as a bare line:

- `VERDICT: PASS`: zero `Critical:` findings, however many advisory ones. Proceed.
- `VERDICT: FAIL`: at least one `Critical:` finding. Loop back and fix.

## Skill-specific overrides

A skill may override one of these defaults where a phase needs something else, such as the wave-merge rule in audit's consolidation or polish's counter rule. The override sits next to the skill's link to this file and says what it changes. The defaults above apply everywhere else.
