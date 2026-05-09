# Anti-Rationalization Library

Adapted from `addyosmani/superpowers` universal anti-rationalization tables and `obra/superpowers` writing-skills.
This is a **living catalogue** — new rationalizations are added as they are observed in practice. Each entry is a verbatim excuse a user or a future Claude run has raised to skip a discipline step, paired with a concrete, non-generic rebuttal.
This file is a reference: grep for the label or skill type you need; do not load the whole file into context.

## Entry format

Each entry follows this shape:

```
### <short label>

- **Skill type**: discipline | collaboration | reference
- **Rationalization**: "<verbatim user excuse>"
- **Rebuttal**: "<specific counter, not generic>"
- **Source**: <addyosmani/superpowers | obra/superpowers | observed>
```

## Entries

### build — plan without review

- **Skill type**: discipline
- **Rationalization**: "the plan is fine without review"
- **Rebuttal**: "plan review catches integration gaps that become 3 review cycles downstream"
- **Source**: observed

### debug — fix by inspection

- **Skill type**: discipline
- **Rationalization**: "I know what the bug is, I'll just fix it"
- **Rebuttal**: "the bug you diagnosed by inspection is the bug you'll miss in a similar codepath tomorrow — write the reproducer first"
- **Source**: addyosmani/superpowers

### audit — skip approval

- **Skill type**: discipline
- **Rationalization**: "findings look obvious, skip approval"
- **Rebuttal**: "parallel fix dispatch is expensive; user approval is the cost cap"
- **Source**: observed

### verify — skip rerun

- **Skill type**: discipline
- **Rationalization**: "tests passed last time, skip rerun"
- **Rebuttal**: "environment drift silently breaks suites between runs"
- **Source**: observed

### polish — good enough

- **Skill type**: discipline
- **Rationalization**: "good enough, ship"
- **Rebuttal**: "polish is the last line of defense before users see it"
- **Source**: observed

### optimize — dead code is harmless

- **Skill type**: discipline
- **Rationalization**: "dead code is harmless, leave it"
- **Rebuttal**: "dead code accelerates context decay and hides the live code"
- **Source**: observed

### blast-radius — skip the map

- **Skill type**: discipline
- **Rationalization**: "small refactor, skip the map"
- **Rebuttal**: "small refactors produce the most silent breakage because reviewers don't look"
- **Source**: observed

### tests — write after

- **Skill type**: discipline
- **Rationalization**: "I'll write tests after"
- **Rebuttal**: "'after' never arrives; write the failing test first, then make it pass"
- **Source**: addyosmani/superpowers

### refactor — too risky now

- **Skill type**: discipline
- **Rationalization**: "refactor is too risky to do now"
- **Rebuttal**: "risk compounds; the longer you delay, the more code depends on the broken shape"
- **Source**: observed

### survivorship — old code worked

- **Skill type**: discipline
- **Rationalization**: "the old code worked fine"
- **Rebuttal**: "it worked until it didn't; survivorship bias is not a design principle"
- **Source**: observed

### commented-out code

- **Skill type**: discipline
- **Rationalization**: "I'll just comment it out for now"
- **Rebuttal**: "commented code is dead code with a zombie reference; delete it and trust git"
- **Source**: observed

### one-more-feature

- **Skill type**: discipline
- **Rationalization**: "one more feature before cleanup"
- **Rebuttal**: "this is how technical debt compounds — stop and clean before adding"
- **Source**: observed

### linter too strict

- **Skill type**: discipline
- **Rationalization**: "the linter is too strict"
- **Rebuttal**: "the linter encodes decisions your team already agreed to; disagree with the team, not the tool"
- **Source**: observed

### types — not this one

- **Skill type**: discipline
- **Rationalization**: "I don't need types on this one"
- **Rebuttal**: "'this one' is how typed codebases become untyped codebases"
- **Source**: observed

### docs — no time

- **Skill type**: discipline
- **Rationalization**: "no time for documentation"
- **Rebuttal**: "no time now means no context next quarter when this breaks"
- **Source**: observed

### large PR — skim it

- **Skill type**: discipline
- **Rationalization**: "the PR is too big to review properly"
- **Rebuttal**: "that's a reason to split the PR, not to skim-approve it"
- **Source**: addyosmani/superpowers

### flaky test — retry

- **Skill type**: discipline
- **Rationalization**: "the test is flaky, just retry"
- **Rebuttal**: "a flaky test is a bug filing itself; retries mask the signal"
- **Source**: observed

### monitor in prod

- **Skill type**: discipline
- **Rationalization**: "we'll monitor it in prod"
- **Rebuttal**: "monitoring catches known-unknowns; the failure you didn't imagine doesn't have a metric"
- **Source**: observed

### stack trace doesn't make sense

- **Skill type**: discipline
- **Rationalization**: "the stack trace doesn't make sense"
- **Rebuttal**: "stack traces always make sense; your mental model is wrong somewhere"
- **Source**: addyosmani/superpowers

### edge case nobody hits

- **Skill type**: discipline
- **Rationalization**: "nobody will run into this edge case"
- **Rebuttal**: "every edge case is somebody's hot path"
- **Source**: observed

### build — tests can wait

- **Skill type**: discipline
- **Rationalization**: "tests can wait until after first ship"
- **Rebuttal**: "missing tests on Day 1 become 'why is this flaky?' in Week 2"
- **Source**: observed

### build — one big commit

- **Skill type**: discipline
- **Rationalization**: "one big commit is easier"
- **Rebuttal**: "atomic commits are the only way to bisect a regression cheaply"
- **Source**: observed

### debug — can't reproduce

- **Skill type**: discipline
- **Rationalization**: "can't reproduce, probably flaky"
- **Rebuttal**: "intermittent bugs are the ones that cost real money in prod"
- **Source**: observed

### debug — works locally

- **Skill type**: discipline
- **Rationalization**: "fix works locally, done"
- **Rebuttal**: "local environment is not prod; write the regression test that pins the behavior"
- **Source**: observed

### audit — severity is subjective

- **Skill type**: discipline
- **Rationalization**: "severity is subjective, label later"
- **Rebuttal**: "unlabeled audits get ignored"
- **Source**: observed

### audit — one-pass scan

- **Skill type**: discipline
- **Rationalization**: "one-pass scan is enough"
- **Rebuttal**: "multi-lens is the point of an audit; single-lens is a grep"
- **Source**: observed

### verify — type-check is slow

- **Skill type**: discipline
- **Rationalization**: "type-check is slow, skip"
- **Rebuttal**: "the bug you didn't type-check is the one that crashes in staging"
- **Source**: observed

### verify — coverage is vanity

- **Skill type**: discipline
- **Rationalization**: "coverage is a vanity metric"
- **Rebuttal**: "coverage < 70% means you're shipping blind in the uncovered 30%"
- **Source**: observed

### polish — edge cases are rare

- **Skill type**: discipline
- **Rationalization**: "edge cases are rare"
- **Rebuttal**: "every bug report you've ever gotten is an edge case"
- **Source**: observed

### polish — green-test refactor

- **Skill type**: discipline
- **Rationalization**: "tests are green, refactor can wait"
- **Rebuttal**: "green-test refactor debt compounds"
- **Source**: observed

### optimize — this loop is fine

- **Skill type**: discipline
- **Rationalization**: "this loop is fine"
- **Rebuttal**: "hot-path loops are the 5% of code that is 80% of CPU time"
- **Source**: observed

### optimize — premature

- **Skill type**: discipline
- **Rationalization**: "premature optimization is the root of all evil"
- **Rebuttal**: "so is late optimization of a known hot path; profile before you decide"
- **Source**: observed

### blast-radius — I know what this touches

- **Skill type**: discipline
- **Rationalization**: "I know what this touches"
- **Rebuttal**: "you know what the call graph you remember touches, not what it actually touches"
- **Source**: observed

### blast-radius — tests will catch it

- **Skill type**: discipline
- **Rationalization**: "the tests will catch it"
- **Rebuttal**: "tests only catch what they cover; the map catches what tests miss"
- **Source**: observed

## How to grow this library

When you observe a new rationalization in the wild:

1. Capture the verbatim excuse — do not paraphrase.
1. Write a rebuttal that cites a specific failure mode or past incident.
1. Classify by skill type (discipline / collaboration / reference).
1. Tag the source: `addyosmani/superpowers`, `obra/superpowers`, or `observed`.
1. Add an entry under `## Entries` using the format above.

Generic rebuttals ("because it is best practice", "because the docs say so") are rejected — rebuttals must push back with a concrete cost or failure mode.
