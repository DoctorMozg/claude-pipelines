# Agent Status Protocol

Canonical four-status terminal protocol for sub-agent dispatches across all mz-dev-pipe skills. Every coder, reviewer, researcher, test writer, or other dispatched agent ends its run with exactly one of the four statuses below. Orchestrators must branch on the status before advancing to the next phase.

## DONE

The agent completed its work with no concerns.

**Default handling**: proceed to the next step.

## DONE_WITH_CONCERNS

The agent completed its work but flagged non-blocking concerns in a `## Concerns` section above the status line.

**Default handling**: log the concern block to `.mz/task/<task_name>/state.md` under a `## Concerns` heading, then proceed. The concerns do not block progress but must be visible for later review.

## NEEDS_CONTEXT

The agent cannot proceed without specific missing information (e.g., a referenced file was not available, a cross-chunk dependency is unclear). The agent lists the required information in a `## Required Context` section above the status line.

**Default handling**: resolve the requested context (read the referenced files, pull details from neighbouring artifacts), then re-dispatch the same agent with the additional context included in the new prompt. Do not proceed to the next step until the agent returns `DONE` or `DONE_WITH_CONCERNS`. Re-dispatches triggered by `NEEDS_CONTEXT` do not consume retry/iteration counters unless the skill explicitly says otherwise.

## BLOCKED

The agent hit a fundamental obstacle (broken environment, impossible constraint, ambiguous specification). The agent describes the obstacle in a `## Blocker` section above the status line.

**Default handling**: escalate to the user via AskUserQuestion with the blocker details. Never auto-retry the same operation. Wait for user direction or abort. Do not consume retry/iteration counters — the counter is for fixable failures, not for blockers.

## Review verdict parsing

Review-oriented agents (code reviewers, coverage reviewers, quality reviewers) additionally emit a verdict token alongside the status:

- `VERDICT: PASS` — proceed. A review is PASS if it contains zero `Critical:` findings, regardless of the count of `Nit:`, `Optional:`, or `FYI` entries.
- `VERDICT: FAIL` — loop back and fix. Only `Critical:` findings block.

## Skill-specific overrides

Individual skills may override specific behaviors inline where the generic default does not match the phase's needs (e.g., wave-merge semantics in audit Phase 5, do-not-increment-counter rules in polish Phase 4.5). Any override is documented above the reference to this file; the defaults above apply everywhere an override is not given.
