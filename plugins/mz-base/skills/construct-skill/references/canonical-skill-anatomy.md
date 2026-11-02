# Canonical Skill Anatomy

Canonical source: guidelines/SKILL_GUIDELINES.md, "Skill Anatomy", with "Phase Overview Table", "Phase and Reference Files", "Constants and Paths", "State Management", "Error Handling and Escalation" and "Approval Gates" for the supporting blocks, and "Report Naming", "Wave Observability", "Tooling Detection" and "Input Parsing" for the supporting rules; guidelines/STATE_SCHEMA.md, "Compact Inline Contract", for the state blocks (in the repo checkout; not shipped with the plugin).

The section layout of a SKILL.md body, a skeleton to copy, and the path rules, state blocks, gate skeleton and supporting rules that the skeleton points to.

## Contents

- Sections
- Skeleton
- Paths
- State blocks
- Gate skeleton
- Supporting rules

## Sections

Use these section names, in this relative order, for the content the skill has:

1. `## Overview`: one paragraph on what the skill does. Required.
1. `## When to Use`: one scope line plus redirects to the nearest sibling skills, or the heading `## When NOT to Use` holding only the redirects. Required. Trigger phrases belong in `description` or `when_to_use`, because the body loads only after the skill is picked. A skill with no near-miss sibling doesn't need a redirect list.
1. `## Core Process`: the steps, or the phase table. Required. Be prescriptive where the task is fragile (gates, irreversible actions, output contracts); elsewhere state the goal.
1. `## Techniques`: concrete patterns and tools the skill applies.
1. `## Common Rationalizations`: the anti-rationalization table, for a skill that guards a rule agents know and skip under pressure (see `anti-rationalization-library.md`, "When a table helps").
1. `## Red Flags`: signs the skill is being skipped or misapplied.
1. `## Verification`: how to confirm the skill ran.

The last four appear only when they carry content. Leave a heading out rather than writing `N/A` or a pointer line. The supporting sections have fixed places too, as a repo convention: `## Input`, `## Scope Parameter` and `## Constants` go between When to Use and Core Process; `## References`, `## Error Handling` and `## State Management` go after Verification. Keep anything that has to survive compaction in the first 5,000 tokens of SKILL.md.

The pattern comes from addyosmani/agent-skills, `docs/skill-anatomy.md`, which calls itself "a recommended pattern, not a rigid template". The voice of the body follows the skill's role: discipline, collaboration or reference (see `persuasion-principles.md`, "Register by role").

Around these sections, SKILL.md is the slim orchestrator: frontmatter, input, scope, constants, the phase table, gates or pointers to them, error handling and state. Aim for about 150 lines, and stay under about 20,000 characters, where Claude Code truncates a skill at compaction.

## Skeleton

Replace every `<placeholder>` and drop any section the skill has no content for.

```markdown
---
name: <kebab-case-name>
description: "<What the skill produces or covers>. Use when <the user's goal, in phrases users type>. Not for <nearest near miss> (use <sibling-skill>)."
argument-hint: "[what the user passes]"
allowed-tools: <comma-separated tool list>
---

# <Skill Title>

## Overview

<One paragraph: what the skill does.>

## When to Use

<One line on the skill's scope.>

- <Near miss>: use `<sibling-skill>`.

## Input

<Accepted formats and the default for each optional argument.>

## Scope Parameter

<Only for a skill that edits or analyzes code. It accepts `scope:branch|global|working`, defined in `<PLUGIN_ROOT>/shared/scope-parameter.md`. State the default and the read and edit boundary here.>

## Constants

- **SKILL_DIR**: `${CLAUDE_SKILL_DIR}`
- **PLUGIN_ROOT**: `${CLAUDE_PLUGIN_ROOT}`, only when the skill reads plugin-level files
- **PROJECT_ROOT**: the path printed in Phase 0 by `echo "${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"`, only when the skill writes under `.mz/`
- **<BOUND_NAME>**: <value>. <Why this bound.>

## Core Process

### Phase Overview

| Phase | Goal          | Details            | Loop                   |
| ----- | ------------- | ------------------ | ---------------------- |
| 0     | Setup         | Inline below       |                        |
| 1     | <goal>        | `phases/<file>.md` |                        |
| 1.5   | User approval | Inline below       | until approved         |
| 2     | <goal>        | `phases/<file>.md` | up to `MAX_ITERATIONS` |

<Phase 0 inline: resolve PROJECT_ROOT, parse the input, name the task, write state.md. A single-step skill replaces the table with numbered steps.>

After compaction, re-read `<PROJECT_ROOT>/.mz/task/<task_name>/state.md`, then the current phase file, before continuing.

## Techniques

- <A concrete pattern or tool the skill applies.>

## Common Rationalizations

| Rationalization | Rebuttal |
| --- | --- |
| "<excuse an agent was seen making>" | "<the concrete cost, or the rule it protects>" |

## Red Flags

- <A concrete, observable sign the skill is skipped or misapplied.>

## Verification

- <A check, with the command and output it cites.>

## References

- `${CLAUDE_SKILL_DIR}/references/<file>.md`: <what it holds>. <When to read it, and whether to search it or read it in full.>

## Error Handling

- **<Predictable failure>**: <the documented default or fallback, or ask>.
- **Nobody can answer**: finish the work that doesn't need the answer, write the blocker and its options to `state.md`, set `Status: blocked`, and stop. Inside a subagent, return `STATUS: BLOCKED` with the question and its options.

## State Management

<The state block that fits the skill, from "State blocks" below.>
```

Leave `model:` out unless the whole run benefits from one model. A skill's own `model:` switches the session's model for the rest of the turn and loses prompt-cache hits (AGENTS_GUIDELINES.md, "Model and Effort"). A skill meant for claude.ai uploads or the Skills API keeps only `name`, `description`, `license`, `compatibility`, `metadata` and `allowed-tools`.

A multi-phase skill has two or more phase files or any approval gate. Inline gates take a `.5` number, a gate inside a phase file is listed with that file, and the Loop column is optional. Keep the table's delimiter row; without it, mdformat turns the table into a paragraph.

## Paths

- SKILL.md defines `SKILL_DIR: ${CLAUDE_SKILL_DIR}`, and `PLUGIN_ROOT: ${CLAUDE_PLUGIN_ROOT}` when it needs plugin-level files. Claude Code substitutes these in SKILL.md only: a phase file opened with Read gets them literally, and neither is set in the Bash environment.
- A skill that writes under `.mz/` resolves `PROJECT_ROOT` once during setup, before any `cd` or worktree switch, with the command in the skeleton. Shell variables don't persist between Bash calls, so the skill keeps the printed path and writes every `.mz/` path under it, never against the Bash working directory.
- Phase files write `<SKILL_DIR>/...`, `<PLUGIN_ROOT>/...` and `<PROJECT_ROOT>/...`. The orchestrator expands each placeholder to the absolute path before reading a file, running a command or passing a path to an agent.
- Read each phase file at the start of its phase with `Read <SKILL_DIR>/phases/<file>.md`, not all of them up front, and re-read the current one after compaction.
- List every reference file in SKILL.md as `${CLAUDE_SKILL_DIR}/references/<file>.md`, with what it holds and when to read it. Phase files may name it again as `<SKILL_DIR>/references/<file>.md`. Give dispatched agents absolute paths, without an `@` prefix. Search a lookup catalog for the entry you need; read templates, rubrics, threshold tables and short rule sets in full.
- A file several plugins use lives once, in `plugins/mz-base/shared/`. Each consumer plugin has a `shared` symlink at its root pointing to `../mz-base/shared`, and mz-base holds the real directory. Skills reach it as `<PLUGIN_ROOT>/shared/<file>.md`.
- Don't write a path into another plugin's directory (`../other-plugin/...`); only the `shared` link crosses plugins. Keep directory symlinks out of `skills/`. A file the skill needs on every surface, claude.ai included, stays inside the skill's own folder.

## State blocks

These are the compact contracts from STATE_SCHEMA.md, "Compact Inline Contract". Copy the one that fits into the State Management section. A skill adds its own keys below the schema keys and never renames or replaces one. The task name is `<YYYY_MM_DD>_<skill>_<slug>`: today's date with underscores, then a snake_case summary of the argument of at most 20 characters, with `_v2`, `_v3` on a same-day collision. Keep `## Decisions` short and first of the body sections: the harvest copies only the first 10 non-blank lines of `## Decisions`, `## Lessons` and `## Notes` together. Keep `state.md` well under 5,000 tokens: put bulk output in its own files and keep body sections to one line per entry.

Multi-phase skills:

> State persists to `.mz/task/<task_name>/state.md` under the project root, `${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}`, resolved once at the start of the run. Schema is **v2**: line 1 is `schema_version: 2`; line 2 is `Status:` with one of `pending`, `running`, `blocked`, `complete`, `aborted_by_user` or `failed`, lowercase and unquoted; then `Phase`, `Started`, `phase_complete` (boolean) and `what_remains` (YAML list of strings), with skill-specific keys below them. Milestones go in `Phase`; the reason for `blocked` or `failed` goes in `what_remains`. Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass. Refresh `what_remains` on every phase transition; it is `[]` when `Status` is `complete`. Write the file after every phase and before every gate, and re-read it after compaction. Record decisions worth recalling under a heading that reads exactly `## Decisions`, placed before `## Lessons` and `## Notes`; mz-memory harvests them only once `Status` is `complete`. Treat a legacy `completed` as `complete`. On reading a `schema_version: 1` or unversioned file, put `schema_version: 2` on line 1 and `Status` on line 2, add the missing keys, and log the upgrade. Leave a file with a higher `schema_version` untouched: ask whether to Restart (archive it), start New (`_v2`) or Abort, and stop if nobody can answer.

Single-dispatch skills, which run setup, one dispatch and its report in a single turn with no approval gate and no phase files:

> State persists to `.mz/task/<task_name>/state.md` under the project root, `${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}`, resolved once at the start of the run. Schema is **v2**: line 1 is `schema_version: 2`; line 2 is `Status:` with one of `pending`, `running`, `blocked`, `complete`, `aborted_by_user` or `failed`, lowercase and unquoted; then `Phase` and `Started`. This skill runs setup, one dispatch and its report in a single turn with no approval gate, so it leaves out `phase_complete` and `what_remains`. On reading an older file, put `schema_version: 2` on line 1 and `Status` on line 2, add no other keys, and log the upgrade. Leave a file with a higher `schema_version` untouched: ask whether to Restart (archive it), start New (`_v2`) or Abort, and stop if nobody can answer.

## Gate skeleton

Put a gate before an irreversible or expensive step, such as changing code, launching a large agent wave, or sending something outside the repo. A read-only skill may put one gate before its main agent wave when that wave is large or costly; a single search or lookup runs without a gate, and other read-only skills need none. Every gate follows this skeleton:

```
**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `<artifact_path>` and capture its full contents into context.
**State**: write `state.md` with the artifact path and `awaiting approval: <gate>`.

**Surface 1: emit the plan message.** Output the artifact verbatim as a chat message:

    ## Plan for review: <skill name>

    <verbatim contents of <artifact_path>>

    ---
    **Approve** → <next phase>  ·  **Reject** → <abort outcome>  ·  reply with feedback to revise

Emit the full verbatim contents, never a path, summary or placeholder.

**Surface 2: call AskUserQuestion.** question: "The plan above is ready for review." header: "<12 chars max>"
options: **Approve** — <next phase> · **Reject** — <abort outcome>.

**Response handling**:
- **Approve** → record the approved artifact path as a `## Decisions` line in `state.md`, clear `awaiting approval`, proceed to <next phase>.
- **Reject** → set `Status: aborted_by_user`, stop.
- **Any other answer** → apply the feedback (re-run the upstream phase if needed), overwrite `<artifact_path>`, return to Surface 1, re-emit the full updated plan message, re-present. Loop until explicit Approve.
- **No answer** → set `Status: blocked` with `awaiting approval: <gate>`, stop. A missing answer is never approval.
```

- `Status` stays `running` while the gate waits. "No answer" covers a denied or unavailable AskUserQuestion and a result that carries the away signal, whatever option it names.
- `header` is at most 12 characters, and a plain gate offers exactly Approve and Reject, with no Feedback option.
- A variant gate presents each extra action as `**<Name>** — <one-sentence summary>`, with 2-4 options per question. Beyond four actions, keep the four most common as options and list the rest in the Surface 1 footer as typed replies, or ask in two calls: first the category, then the action.
- After the gate resolves, the skill should append a `gate` entry to `<PROJECT_ROOT>/.mz/journal.md`: skill, task, phase, gate label, outcome and the artifact. A direct append isn't redacted, so the artifact goes through perl, which replaces each `<private>` span with `[redacted]` and indents the text under its bullet. `<path>` is relative to `PROJECT_ROOT`, or absolute outside it. For several artifacts, repeat the three artifact lines once per file.

```bash
mkdir -p "<PROJECT_ROOT>/.mz" && {
  printf '### %s · <skill> · <task_name> · gate\n\n- phase: <phase>\n- gate: <label>\n- outcome: <approve | reject | no answer>\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '%s\n\n' "- artifact: <path>, verbatim:"
  perl -0777 -pe 's|<private>.*?</private>|[redacted]|gs; s/^(?=.)/  /gm' "<absolute path>"
  printf '\n'
} >>"<PROJECT_ROOT>/.mz/journal.md"
```

## Supporting rules

These copy the SKILL_GUIDELINES.md sections named in the canonical-source line at the top, plus the wave cap from AGENTS_GUIDELINES.md, "Parallel Waves". Each applies only to a skill that does what it covers.

- **Reports.** A report lives at `<PROJECT_ROOT>/.mz/<root>/<task_name>.md`, where `<root>` is `reports`, `reviews`, `research`, `design` or `outreach`, and the date is the one already in the task name. A run with several final files gets the folder `.mz/<root>/<task_name>/`. Before writing, check the path, and on a collision append the next free `_vN`. Pass the full path to the agent that writes the report; agents don't compose the name. Use `.md` unless the user asks for another format.
- **Waves.** Issue a wave's `Agent` calls in one message, at most 6 agents per wave, and split overflow into sequential waves. Right before a wave of two or more agents, print `Dispatching <wave label> — <N> agents in parallel`, a `Purpose: <one line>` line, and one `- <agent> — <role, ≤6 words>` line per agent. Once every agent has reported, failed or been stopped, print `Wave complete — <returned>/<dispatched> agents returned` and one `- <agent>: <STATUS or VERDICT> — <summary, ≤8 words>` line per agent. An agent with no valid final `STATUS:` line is listed as `NO RETURN BLOCK`. Pass each role label as the `Agent` call's `description`, and record each arrival in `state.md`.
- **Tooling.** Resolve the test, lint, format and type-check commands before the first phase that runs one, from CLAUDE.md (or AGENTS.md when there is no CLAUDE.md), then `.mz/tooling.json` when mz-dev-pipe is enabled, then the manifests. Record them with their source in `.mz/task/<task_name>/tooling.md`. With no tests, the orchestrator asks before the first phase that needs them, and a dispatched agent returns `NEEDS_CONTEXT`. Where nobody can answer, a skill whose output is tests stops, any other skill continues or stops as it documents, and the final report says which.
- **Input collectors.** A missing value is collected, not gated: no artifact, no plan message, no Approve and Reject. A closed choice of 2-4 values is one AskUserQuestion call with each value as an option; with more, name the most common as options and list the rest in the question. Confirm-or-customize is one AskUserQuestion call with options such as `Defaults` and `Minimal`, with custom answers through the typed reply. An open value, such as a path or a topic, is a prose question. Collectors run in the main session only. An empty answer means stop, and an invalid one is re-asked once. Record open values in `state.md`.
- **Escalation.** Recover on your own where the skill documents a default, a fallback chain or a degraded mode the final report discloses. Escalate when the remaining choices lead to materially different work or a wrong guess would be unsafe; for a routine judgment call, state the assumption and continue. Never fill a blocker with an invented value. Ask a pick from a set with AskUserQuestion, and name the tool in the instruction, because auto mode otherwise steers Claude away from clarifying questions. Where nobody can answer, finish the work that doesn't depend on the answer, write the blocker and its options to `state.md`, set `Status: blocked` and stop; inside a subagent, return `STATUS: BLOCKED`. An agent that returns nothing usable: wait while it runs, resume a partial one once with `SendMessage`, re-dispatch an empty or malformed one once with something changed, and report an API error or usage limit instead of retrying.
- **Unattended mode** (optional). The user opts in with `MZ_DEV_PIPE_AUTO_APPROVE=1`; a skill never turns it on itself. Check it once during setup with a Bash call and record the result in `state.md` as `unattended: true` or `unattended: false`. A plain gate still emits Surface 1 and skips Surface 2. Log each skipped gate in four places: chat, `state.md` under `## Auto-approvals` (gate label, phase, time), a journal `gate` entry with outcome `auto-approved (unattended)`, `authority: MZ_DEV_PIPE_AUTO_APPROVE=1` and the artifact path rather than its text, and the final report. Variant gates never auto-approve; they take the No-answer path.
