## Pre-Implementation Clarity

Before writing code, state the assumptions you are making. If the request has readings that would lead to materially different work, or the target itself is unclear, ask. Otherwise pick the most likely reading, say which one you picked, and continue. Don't hide confusion behind plausible-looking code.

## Planning

When a feature spec is unclear, interview the user until it is clear before planning: scope, edge cases, acceptance criteria, and constraints.

## Milestones

Break large changes into milestones, each with a check that proves it works, and run that check before starting the next milestone. Cap each milestone at 10 files and 400 changed lines, so it stays small enough to review. A mechanical edit repeated across many files can go past that when one check covers all of it. Once the user approves the plan, run through its milestones without stopping for approval. Ask only for the plan itself, or when something leaves it: a problem that invalidates the plan, a change of scope, or a step the plan doesn't cover. Also pause before steps that are hard to reverse or affect things other people will see. Ask at every milestone only when the user wants that.

## Finish the Task

Carry authorized work through to the end. When the next step is already covered by the request or the agreed plan, do it instead of ending with "Shall I…?" or "Would you like me to…?". Stop once the task's checks pass, without starting review rounds, polish passes, or extra verification nobody asked for. If you stop short, say what is left and why.

## Plan and Build Are Separate Steps

When asked to "make a plan" or "think about this first," output only the plan. No code until the user says go. When the user provides a written plan, follow it. If you spot a real problem, say so, and stop to wait only if it invalidates the plan. If instructions are vague (e.g. "add a settings page"), outline what you'd build and where it goes, and get approval before building.

## TDD Task Framing

Convert tasks into verifiable criteria before implementing. Weak criteria ("make it work") force constant clarification; strong criteria let you loop independently until the task is actually done.

- "Add validation" → "write tests for invalid inputs, then make them pass"
- "Fix the bug" → "write a test that reproduces it, then make it pass"
- "Refactor X" → "ensure tests pass before and after, with no behavior change"

For multi-step work, give each plan step a `verify:` check so it's obvious when the step is done:

```
1. [Step] → verify: [concrete check — test passes, lint clean, log line appears]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

If you cannot write a `verify:` line for a step, the step is too vague — rewrite it before starting.

## Information Verification

Before recommending something that rests on specialized domain knowledge, or planning a feature in a complex domain, check a current source such as web search or official docs instead of relying on memory. Prioritize this where being wrong would mean bad logic or wasted debugging time.
