# Canonical Skill Anatomy (Rule 16)

The 7-section skeleton every SKILL.md body must follow, with inline annotations for what each section contains.
See `SKILL_GUIDELINES.md` Rule 16 for the authoritative spec and the pipeline exemption for multi-phase orchestrators.
Pattern source: `addyosmani/superpowers` 7-section canonical anatomy.

## How to use this file

Copy the skeleton below into a new `plugins/<plugin>/skills/<name>/SKILL.md`. Replace every `<placeholder>` and delete the HTML-comment annotations before shipping. The comment blocks describe what goes in each section — they are authoring notes, not runtime content.

Every section is mandatory. A section that genuinely does not apply (e.g. `## Common Rationalizations` for a reference skill) must be explicitly marked `N/A — <reason>` with a rule citation. Never leave a section empty or omit the header.

## Skeleton

```markdown
---
name: <kebab-case-name>
description: ALWAYS invoke when <primary trigger>. Triggers: "<trigger 1>", "<trigger 2>", "<trigger 3>". <optional one-line scope clause>.
argument-hint: <what the user should pass>
allowed-tools: <comma-separated tool list>
model: sonnet | opus | haiku
---

# <Skill Title>

<!--
  Optional one-line subtitle under the H1. If present, keep it to a single sentence.
  Do not duplicate the description frontmatter here.
-->

## Overview

<!--
  One paragraph. Answer:
  - What does this skill do?
  - Why does the user need it (what would break without it)?
  No workflow lists. No phase tables. Those belong in Core Process.
  Keep it under ~5 sentences.
-->

<one paragraph — what the skill does and why it exists>

## When to Use

<!--
  Concrete trigger phrases (2-5) that should cause this skill to fire.
  Counter-triggers go under `### When NOT to use` below.
  This section is read by humans; the auction-bid version is in the frontmatter description.
-->

Triggers: "<phrase 1>", "<phrase 2>", "<phrase 3>".

### When NOT to use

<!--
  2-3 bullets. Each counter-trigger must route to a specific sibling skill or tool.
  "Don't use this for X" without a destination is useless.
-->

- <counter-trigger 1> → use `<sibling-skill>` instead.
- <counter-trigger 2> → use `<sibling-skill>` instead.
- <counter-trigger 3> → edit directly, no skill needed.

## Core Process

<!--
  For single-step skills: a numbered list of non-negotiable steps.
  For multi-phase skills: a Phase Overview table (Rule 5) with `phases/<file>.md` references.
  Approval gates go in-phase as `.5` rows (e.g. Phase 1.5) or inline below the table.

  Single-step example:
    1. Read the file at `$ARGUMENTS`.
    2. Extract the <artifact>.
    3. Write to `.mz/<type>/<name>.md`.
    4. Report path + summary.

  Multi-phase example:
    | Phase | Goal              | Details                  |
    | ----- | ----------------- | ------------------------ |
    | 0     | Setup             | Inline below             |
    | 1     | <goal>            | `phases/<file>.md`       |
    | 1.5   | User approval     | Inline below             |
    | 2     | <goal>            | `phases/<file>.md`       |
-->

<numbered list or phase overview table>

## Techniques

<!--
  Concrete patterns, tools, and decision trees the skill applies.
  Code snippets, grep recipes, dispatch prompt shapes, etc.

  PIPELINE EXEMPTION (Rule 16, U1):
    Multi-phase orchestrator skills with a Phase Overview table may replace this
    section's body with a single line:

      Techniques: delegated to phase files — see Phase Overview table above.

    This avoids duplicating content between SKILL.md and phase files and satisfies
    Rule 2's progressive disclosure while still passing the "all 7 sections present"
    check. The header itself (`## Techniques`) must still be present.
-->

<concrete techniques OR pipeline-exemption line>

## Common Rationalizations

<!--
  Mandatory for DISCIPLINE skills per Rule 17 — minimum 3 rows.
  OPTIONAL for collaboration and reference skills — use `N/A — <reason>` with a rule citation.

  Rationalizations must be verbatim user excuses (observed in practice, not invented).
  Rebuttals must be specific — cite a failure mode, past incident, or concrete cost.
  Generic rebuttals ("because it's best practice") are rejected.

  Seed rows live in `writing-skills/references/anti-rationalization-library.md` —
  grep that file for entries matching this skill's domain and type.
-->

| Rationalization | Rebuttal |
| --- | --- |
| "<verbatim excuse 1>" | "<specific counter 1>" |
| "<verbatim excuse 2>" | "<specific counter 2>" |
| "<verbatim excuse 3>" | "<specific counter 3>" |

<!--
  For collaboration/reference skills, replace the table with:

    N/A — collaboration skill per SKILL_GUIDELINES.md Rule 23, not discipline. See Rule 17.
-->

## Red Flags

<!--
  3+ bullets. Observable signs the skill is being skipped, misapplied, or violated.
  These are the heuristics a reviewer uses to catch non-compliance.
  Each bullet should be concrete and checkable — not a generic warning.
-->

- <red flag 1 — concrete and observable>
- <red flag 2 — concrete and observable>
- <red flag 3 — concrete and observable>

## Verification

<!--
  How to confirm the skill actually ran correctly.
  Every check must produce VISIBLE output (Rule 4) — "silent checks get skipped".
  Close with the Rule 24 pre-publish checklist result for skills that author artifacts.
-->

<checklist or explicit verification steps, each producing visible output>
```

## Pipeline exemption — worked example

For a multi-phase orchestrator, the `## Techniques` section collapses to one line:

```markdown
## Techniques

Techniques: delegated to phase files — see Phase Overview table above.
```

This is allowed only when the `## Core Process` section is a Phase Overview table (Rule 5) with at least one phase delegated to a `phases/<file>.md` file. Single-step skills cannot use the exemption — they must list concrete techniques.

## Section order is non-negotiable

Rule 16 requires these 7 sections in this exact order:

1. `## Overview`
1. `## When to Use` (with `### When NOT to use` sub-section)
1. `## Core Process`
1. `## Techniques`
1. `## Common Rationalizations`
1. `## Red Flags`
1. `## Verification`

Grep verification:

```
grep -n '^## ' plugins/<plugin>/skills/<name>/SKILL.md
```

The output must list the seven headers in order. Any deviation fails Rule 24's anatomy check.

## When a section genuinely does not apply

- **Reference skills** often have no `## Common Rationalizations` — use `N/A — reference skill per Rule 23.`
- **Read-only skills** often have no `## Verification` gate beyond "output produced" — use `N/A — read-only skill; output is the verification.`
- **Single-step skills** may have a trivial `## Core Process` — still use a numbered list, not free prose.

Never omit a section header. The header must exist so that Rule 24's grep check passes; the body can be a one-line `N/A` explanation.

## Links

- `SKILL_GUIDELINES.md` Rule 16 — canonical anatomy spec and pipeline exemption.
- `SKILL_GUIDELINES.md` Rule 17 — anti-rationalization table requirements.
- `SKILL_GUIDELINES.md` Rule 18 — CSO description rules.
- `SKILL_GUIDELINES.md` Rule 23 — persuasion-informed language per skill type.
- `writing-skills/references/anti-rationalization-library.md` — seed content for the rationalization table.
- `writing-skills/references/persuasion-principles.md` — which Cialdini principles to apply per skill type.
