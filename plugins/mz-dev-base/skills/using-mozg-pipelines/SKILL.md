---
name: using-mozg-pipelines
description: ALWAYS invoke when user asks which mozg skill/plugin to use, says 'what plugins do I have', 'which pipeline fits', 'route this'. Maps task phrases to skills across mz-dev-base, mz-dev-pipe, mz-dev-hooks, mz-memory, mz-biz-outreach, mz-creative.
argument-hint: '[task description]'
model: haiku
allowed-tools: Read, AskUserQuestion
---

## Overview

This is a routing map, not a discipline skill. It is loaded into every new session via the mz-dev-base SessionStart hook and tells Claude which concrete skill to invoke for a given user task phrase. When the user describes work in natural language, consult this map first, then delegate to the matching skill. Do not attempt the work under this skill's own identity.

## When to Use

Invoke when the user:

- asks "which skill/plugin/pipeline do I use for X"
- says "what plugins do I have" or "what can mozg do"
- asks to "route this task" or "pick the right pipeline"
- describes a task without naming a skill and you need to dispatch

### When NOT to use

- The user already named a specific skill ("run audit", "use build") — invoke it directly.
- The user is mid-phase inside another skill — stay inside that skill.
- The user asked a direct question answerable without routing (code read, quick fix) — answer it.
- The task matches exactly one obvious skill from context — invoke it without re-citing the map.

## Core Process

1. When the user states a task, map the phrase against the Techniques table BEFORE drafting an answer.
1. If the phrase matches multiple skills, list all candidates with the distinguishing condition, ask which fits, or pick the most specific.
1. If the phrase matches no entry, say so explicitly — do not invent a routing.
1. Prefer the most specific skill over a general one (e.g., `audit` over `investigate` for security review).
1. Do not paraphrase the user's task to fit a different skill's territory.
1. After routing, invoke the target skill directly. Do not re-explain the routing decision to the user unless they asked.

## Techniques

Routing table. Phrases are indicative, not exact matches.

| Task phrase                                                    | Skill                | Plugin          |
| -------------------------------------------------------------- | -------------------- | --------------- |
| "build a feature", "implement X", "add capability"             | build                | mz-dev-pipe     |
| "fix this bug", "debug", "why is this broken"                  | debug                | mz-dev-pipe     |
| "security review", "audit for vulns", "threat model"           | audit                | mz-dev-pipe     |
| "verify this works", "prove correctness", "check behavior"     | verify               | mz-dev-pipe     |
| "polish this", "clean up", "finalize"                          | polish               | mz-dev-pipe     |
| "optimize", "make it faster", "profile hotspot"                | optimize             | mz-dev-pipe     |
| "explain this code", "what does this do"                       | explain              | mz-dev-pipe     |
| "investigate", "dig into", "find root cause"                   | investigate          | mz-dev-pipe     |
| "blast radius", "what breaks if I change X", "impact analysis" | blast-radius         | mz-dev-pipe     |
| "research topic deeply", "survey the field"                    | deep-research        | mz-dev-base     |
| "bootstrap rules", "init project rules"                        | init-rules           | mz-dev-base     |
| "review my branch", "what changed locally"                     | review-branch        | mz-dev-base     |
| "review this PR", "what's wrong with this PR"                  | review-pr            | mz-dev-base     |
| "scan open PRs", "triage PRs"                                  | scan-prs             | mz-dev-base     |
| "help me author a new skill", "write a SKILL.md"               | writing-skills       | mz-dev-base     |
| "which skill fits", "route this", "what plugins do I have"     | using-mozg-pipelines | mz-dev-base     |
| "find leads", "customers matching X", "outreach list"          | lead-gen             | mz-biz-outreach |
| "brainstorm", "generate ideas", "creative options"             | brainstorm           | mz-creative     |

mz-dev-hooks contributes safety gates (pre-tool checks) and has no user-facing skills. mz-memory contributes SessionStart/SessionEnd memory hooks and has no user-facing skills; it is referenced by agents that need persistent state.

## Common Rationalizations

N/A — informational routing skill, not a discipline skill.

## Red Flags

- You answered a routing-type question by attempting the task directly without checking the routing table.
- You routed to a general skill (`investigate`) when a specific one (`audit`, `blast-radius`) exists for the phrase.
- You paraphrased the user's task into a different skill's territory to justify a skill you prefer.

## Verification

To confirm the router was loaded into this session:

- Grep the initial system/context for the string `using-mozg-pipelines` or `Mozg pipelines routing map`.
- Ask Claude to recite the first column header of the routing table (`Task phrase | Skill | Plugin`).
- If neither is present, the SessionStart hook did not fire — re-enable the mz-dev-base plugin or run the session-start script manually.
