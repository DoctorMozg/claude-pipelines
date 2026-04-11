## Pre-Implementation Clarity

Before writing code, state any assumptions you are making out loud. If multiple interpretations of the request exist, surface them and pick one explicitly — never silently choose. If something is unclear, stop and ask. Do not hide confusion behind plausible-looking code.

- Name your assumptions before implementing, even the "obvious" ones.
- If the request has two or more reasonable readings, list them and choose one on the record.
- Unknown domain terms, unclear acceptance criteria, and ambiguous scope are all stop-and-ask triggers.

## Planning

- When planning a feature in a complex domain, always use web search and fetching to validate approaches. Don't try to figure out complex things solely from internal knowledge.
- Always ask the user at least 5 important questions before starting, then continue asking until all aspects of the planned functionality are completely full and clear.

## Phased Execution

Never attempt multi-file refactors in a single response. Break work into explicit phases. Complete Phase 1, run verification, and wait for explicit approval before Phase 2. Each phase must touch no more than 5 files.

## Plan and Build Are Separate Steps

When asked to "make a plan" or "think about this first," output only the plan. No code until the user says go. When the user provides a written plan, follow it exactly. If you spot a real problem, flag it and wait — don't improvise. If instructions are vague (e.g. "add a settings page"), don't start building. Outline what you'd build and where it goes. Get approval first.

## TDD Task Framing

Convert tasks into verifiable criteria before implementing. Weak criteria ("make it work") force constant clarification; strong criteria let you loop independently until the task is actually done.

- "Add validation" → "write tests for invalid inputs, then make them pass"
- "Fix the bug" → "write a test that reproduces it, then make it pass"
- "Refactor X" → "ensure tests pass before and after, with no behavior change"

For multi-step work, each plan step must carry an explicit `verify:` check so it's obvious when the step is done:

```
1. [Step] → verify: [concrete check — test passes, lint clean, log line appears]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

If you cannot write a `verify:` line for a step, the step is too vague — rewrite it before starting.

## Information Verification

When about to recommend something that relies on specialized domain knowledge, use web search to verify accuracy before presenting it. Prioritize this for non-trivial claims where being wrong could lead to bad logic or wasted debugging time.
