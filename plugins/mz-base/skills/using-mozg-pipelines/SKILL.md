---
name: using-mozg-pipelines
description: 'Separates look-alike mozg skills and chains several per task. Use when the user is unsure which of their tools fits or what they have ("which pipeline fits", "what plugins do I have", "route this"). Not when the user named a skill (invoke it).'
argument-hint: '[task description]'
allowed-tools: Read, AskUserQuestion
---

## Overview

This is a routing map, not a discipline skill. It loads on demand, when the user asks which skill fits or describes work without naming one, and tells Claude which concrete skill to invoke for that task phrase. Consult the map, then delegate to the matching skill. Do not attempt the work under this skill's own identity.

## When to Use

Choosing which installed mozg skill or plugin fits a task, or seeing what is installed, when the user has not named a skill.

### When NOT to use

- The user already named a specific skill ("run audit", "use build") — invoke it directly.
- The user is mid-phase inside another skill — stay inside that skill.
- The user asked a direct question answerable without routing (code read, quick fix) — answer it.
- The task matches exactly one obvious skill from context — invoke it without re-citing the map.

## Core Process

1. When the user states a task, map the phrase against the Techniques table BEFORE drafting an answer.
1. If the phrase matches multiple skills, list all candidates with the distinguishing condition, ask which fits, or pick the most specific.
1. If the phrase matches no entry, say so explicitly — do not invent a routing.
1. Prefer the most specific skill over a general one (e.g., `audit` over `debug certainty:low` for security review).
1. Do not paraphrase the user's task to fit a different skill's territory.
1. After routing, invoke the target skill directly. Do not re-explain the routing decision to the user unless they asked.

## Techniques

Routing table. Phrases are indicative, not exact matches.

| Task phrase                                                                                                                                          | Skill                                                          | Plugin           |
| ---------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- | ---------------- |
| "build a feature", "implement X", "add capability"                                                                                                   | build                                                          | mz-dev-pipe      |
| "fix this bug", "debug", "why is this broken"                                                                                                        | debug                                                          | mz-dev-pipe      |
| "security review", "audit for vulns", "threat model"                                                                                                 | audit                                                          | mz-dev-pipe      |
| "verify this works", "prove correctness", "check behavior"                                                                                           | verify                                                         | mz-dev-pipe      |
| "polish this", "clean up", "finalize"                                                                                                                | polish                                                         | mz-dev-pipe      |
| "decomment", "strip AI comments", "remove robotic comments", "clean LLM comments from code"                                                          | decomment                                                      | mz-dev-pipe      |
| "optimize", "make it faster", "profile hotspot"                                                                                                      | optimize                                                       | mz-dev-pipe      |
| "refactor", "remove dead code", "remove unused imports", "reduce complexity"                                                                         | cleanup                                                        | mz-dev-pipe      |
| "explain this code", "what does this do"                                                                                                             | explain                                                        | mz-research-pipe |
| "investigate X", "dig into", "find root cause", "is X actually doing Y", "verify hypothesis"                                                         | debug certainty:low                                            | mz-dev-pipe      |
| "blast radius", "what breaks if I change X", "impact analysis"                                                                                       | audit scope:branch or audit <path> (expands to impacted files) | mz-dev-pipe      |
| "deep audit", "pre-PR audit", "ship audit", "before publishing", "before I open a PR"                                                                | audit depth:deep                                               | mz-dev-pipe      |
| "research topic deeply", "survey the field"                                                                                                          | deep-research                                                  | mz-research-pipe |
| "synthesize past research", "combine findings", "consolidate prior work"                                                                             | combine                                                        | mz-research-pipe |
| "translate this", "localize", "translate to <lang>"                                                                                                  | translate                                                      | mz-research-pipe |
| "bootstrap rules", "init project rules"                                                                                                              | init-rules                                                     | mz-base          |
| "review my branch", "what changed locally"                                                                                                           | review-branch                                                  | mz-dev-git       |
| "review this PR", "what's wrong with this PR"                                                                                                        | github-review-pr                                               | mz-dev-git       |
| "scan open PRs", "triage PRs"                                                                                                                        | github-scan-prs                                                | mz-dev-git       |
| "help me author a new skill", "write a SKILL.md", "construct a skill"                                                                                | construct-skill                                                | mz-base          |
| "which skill fits", "route this", "what plugins do I have"                                                                                           | using-mozg-pipelines                                           | mz-base          |
| "draft an outreach brief", "prep outreach", "research local market for outreach", "scope outreach campaign", "outreach brief"                        | outreach-brief                                                 | mz-biz-outreach  |
| "find leads", "customers matching X", "outreach list", "research targets", "find contacts at <company>", "decision-makers at X", "who do I write to" | outreach-research                                              | mz-biz-outreach  |
| "draft outreach letters from this card", "write letters from <card path>", "enrich this card", "deepen research on <card>", "go deeper on <card>"    | outreach-enrich-company                                        | mz-biz-outreach  |
| "log action on <card>", "update card with <action>", "record interaction on <card>", "I just <action>, add to <card>"                                | outreach-update-card                                           | mz-biz-outreach  |
| "find a job", "search for vacancies", "job hunt", "match jobs to my CV"                                                                              | job-search                                                     | mz-job-outreach  |
| "find a recruiter", "hiring manager for X", "careers email for X", "who do I apply to"                                                               | job-recruiter-info                                             | mz-job-outreach  |
| "brainstorm", "generate ideas", "creative options"                                                                                                   | brainstorm                                                     | mz-creative      |
| "should I do X or Y", "record this decision", "write an ADR", "RFD for X", "is this decision sound"                                                  | govern                                                         | mz-gov           |
| "install governance policy", "init governance", "set up decision records"                                                                            | gov-init                                                       | mz-gov           |
| "review our ADRs", "audit decision records", "are our design docs sound"                                                                             | gov-review                                                     | mz-gov           |

mz-memory contributes SessionStart, SessionEnd, UserPromptSubmit and PostToolUse (AskUserQuestion) hooks and the `/memory-note` skill; it is referenced by agents that need persistent state.

## Red Flags

- You answered a routing-type question by attempting the task directly without checking the routing table.
- You routed to a general skill (`debug certainty:low`) when a specific one (`audit`, `audit depth:deep`) exists for the phrase.
- You paraphrased the user's task into a different skill's territory to justify a skill you prefer.

## Verification

Before handing off, confirm:

- The chosen skill appears in the routing table above, or you told the user that no entry matches.
- When several skills matched, you named the condition that decided between them, or asked the user.
- You invoked the target skill instead of doing the work under this skill's identity.
