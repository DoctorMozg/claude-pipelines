# Skill Authoring Guidelines

Rules for writing skills in this repository. All skills must comply.

## 1. Approval Gates Must Loop

Every approval gate uses the **two-surface plan pattern**, modeled on Claude Code's plan mode (`ExitPlanMode`): the artifact is rendered as an ordinary markdown chat message — exactly the way a plan appears in plan mode — and `AskUserQuestion` is only the short Approve/Reject selector beneath it. `ExitPlanMode` itself carries no plan content; the plan is a normal message the user reads inline. Gates mirror that split.

Every gate must contain these elements, in order:

1. **Delegation guard**: `**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.`
1. **Mandatory pre-read**: Before emitting the gate, the gate text must instruct the orchestrator to Read the artifact and capture its full contents into context (e.g., `Read .mz/task/<task_name>/plan.md and capture the full contents`). Name the exact artifact path (`plan.md`, `strategy.json`, `findings.md`, etc.) — do not say "the artifact" generically.
1. **Surface 1 — the plan message** (a normal markdown chat message, not a tool call): After the pre-read, the orchestrator emits the artifact's **full verbatim contents** as an ordinary chat message so its markdown renders fully and survives in scrollback. The gate text must spell out the structure with a fenced template:

   ```
   ## Plan for review — <skill name>

   <verbatim artifact contents>

   ---
   **Approve** → <what happens next>  ·  **Reject** → <abort outcome>  ·  reply with feedback to revise
   ```

   The verbatim requirement is absolute: never substitute a path, line count, status summary, or `<placeholder>` token for the artifact body. State it explicitly in the gate: `Emit the full verbatim contents of <artifact_path> as a chat message — do not substitute a path, summary, or placeholder.`
1. **Surface 2 — the AskUserQuestion selector**: Immediately after the plan message, the orchestrator calls AskUserQuestion. The selector is short: `question` is a single orientation line pointing at the plan message above (e.g., `The plan above is ready for review.`). The `question` must NOT re-embed the verbatim artifact — that lives in Surface 1. Named `options` are exactly two: **Approve** and **Reject**. Do not add a third "Feedback" option — AskUserQuestion always exposes a free-text reply field, and feedback rides that field.
1. **Variant gates** (conditional): if the gate offers selectable named actions beyond Approve/Reject — for example a per-note review menu (`Done | Skip | Edit | Promote | Archive | Abort`) or a strategy picker — each named action becomes an `options` entry presented as `**<Name>** — <one-sentence summary of what choosing it means>`. Feedback still rides the free-text reply field; never add an explicit "Feedback" option. The canonical variant gate lives in `plugins/mz-knowledge/skills/vault-review/phases/review_session.md` (per-note review action gate).
1. **Response handling** as a labeled section:
   - **Approve** → update state, proceed to the next phase.
   - **Reject** → update state to `aborted_by_user` and stop. Do not proceed.
   - **Any other reply (feedback)** → incorporate it, re-run the upstream phase if needed, overwrite the artifact, then return to this gate: re-read the updated artifact and **re-emit the entire plan message from scratch** (full verbatim — never a diff, never a summary, since context compaction may have destroyed the user's memory of earlier iterations), then re-present the selector. Explicitly state: "This is a loop — repeat until the user explicitly approves. Never proceed to Phase N without explicit approval."

All elements are required (element 5 only when variant actions exist). Do not omit the delegation guard, the pre-read, the verbatim plan message, the two-option selector, the reject path, or the loop language.

**Why the plan message is a chat message, not the AskUserQuestion body**: The AskUserQuestion body truncates in chat history and is optimized for a short question. Burying a multi-thousand-character artifact inside it renders cramped and, in practice, gets silently replaced by a bare path or one-line status — defeating the gate. A normal chat message renders markdown fully, mirrors how plan mode surfaces a plan, and survives in scrollback. Keeping the artifact in Surface 1 and the selector short in Surface 2 fixes both problems at once.

**Why feedback has no named option**: AskUserQuestion always exposes a free-text reply field. An explicit "Feedback" option duplicates it. Two named options (Approve, Reject) plus the always-present free-text field cover every path — any reply that is not Approve or Reject is feedback.

**Canonical gate skeleton**:

```
**This orchestrator** (not a subagent) presents this gate. Interactive — do not delegate.

**Pre-read**: Read `<artifact_path>` and capture its full contents into context.

**Surface 1 — emit the plan message.** Output the artifact verbatim as a chat message:

    ## Plan for review — <skill name>

    <verbatim contents of <artifact_path>>

    ---
    **Approve** → <next phase>  ·  **Reject** → <abort outcome>  ·  reply with feedback to revise

Emit the full verbatim contents — never a path, summary, or placeholder.

**Surface 2 — call AskUserQuestion.** question: "The plan above is ready for review."
options: **Approve** — <next phase> · **Reject** — <abort outcome>.

**Response handling**:
- **Approve** → <state update>, proceed to <next phase>.
- **Reject** → set state `aborted_by_user`, stop.
- **Any other reply** → apply the feedback, overwrite `<artifact_path>`, return to Surface 1, re-emit the full updated plan message, re-present. Loop until explicit Approve.
```

Reference implementation: `plugins/mz-design/skills/design-document/phases/finalization.md` (Step 4.1).

Add gates before: code changes, expensive agent dispatches, web research. Read-only skills (like `explain`) don't need gates.

## 2. Progressive Disclosure

SKILL.md competes with a shared ~150-instruction budget (system prompt uses ~50, leaving ~100 for CLAUDE.md + skills combined). Phase files are free until read.

- **SKILL.md**: slim orchestrator (100-150 lines) — frontmatter, input, scope, constants, phase table, inline setup/gates, error handling, state mgmt.
- **Phase files** (`phases/*.md`): detailed prompts and process. Under 400 lines each. Read on-demand: `Read phases/<file>.md` at phase start. Never pre-load all.

## 3. Skill Descriptions

Description is the single most important field — Claude uses pure LLM reasoning on it to decide whether to invoke the skill. No fallback if the description fails.

- Write in third person ("Processes files..." not "I can help you..."). Third person because the skill description is shown to Claude as a registry entry, not as an instruction directed at Claude — second-person `you` reads as if the description itself is the task.
- Use directive phrasing: "ALWAYS invoke when the user asks about [topic]"
- Front-load the key use case within 250 characters (truncated in listings)
- Include 2-3 example trigger phrases for activation reliability
- See Rule 19 (CSO) for the complete description format spec.

## 4. Instruction Framing

- Prefer positive framing: "Use X exclusively" over "Do NOT use Y" — reduces violations by ~50%.
- Anchor critical rules at the top AND bottom of SKILL.md (primacy-recency bias).
- Every verification step must produce visible output. "Check X" → "Output a block showing X, then proceed." Silent checks get skipped.
- See Rule 21 for skill-type-specific language recipes.

## 5. Phase Overview Table

Required in SKILL.md for multi-phase skills. Use `.5` for inline approval gates.

```
| Phase | Goal           | Details              |
| 0     | Setup          | Inline below         |
| 1     | <goal>         | `phases/<file>.md`   |
| 1.5   | User approval  | Inline below         |
| 2     | <goal>         | `phases/<file>.md`   |
```

## 6. Scope Parameter

Code-editing skills must support `scope:branch|global|working`. Extract from `$ARGUMENTS`, case-insensitive. Scope constrains **edits only** — researchers and tests read the full project. Document the default when omitted.

## 7. Constants

Define all bounds and paths as named constants in SKILL.md. Every loop must reference its constant by name — never hardcode limits inline.

## 8. State Management

Multi-phase skills persist state to `.mz/task/<task_name>/state.md`. Its required keys, `schema_version`, the progress-ledger fields (`phase_complete`, `what_remains`), the minimal example, and the migration discipline are defined canonically in `guidelines/STATE_SCHEMA.md` — treat that file as the single source of truth. Skills mirror its compact contract; they do not invent their own key set. Update the state file after every phase transition. Critical: never rely on conversation memory for cross-phase state — context compaction destroys specific paths and decisions.

**Task naming convention**: `<YYYY_MM_DD>_<skill>_<slug>` where `<YYYY_MM_DD>` is the current date (underscores, not dashes), `<skill>` is the skill name, and `<slug>` is a snake_case summary of the argument (max 20 chars). On same-day collision append `_v2`, `_v3`. Example: `2026_04_20_build_oauth_flow`, `2026_04_20_debug_payment_err`.

## 9. Dispatch Prompt Compression

Agent files already contain general process/rules/format. Dispatch prompts provide **only** task-specific context: what to work on, artifact pointers, scope constraints, output format overrides. Don't repeat agent instructions. Explicitly request concise output — output tokens cost 5x input.

When compressing prose in dispatch prompts (or any internal artifact), preserve verbatim:

- Code blocks and inline code
- URLs, file paths, command lines, flags, environment variables
- Frontmatter (YAML), JSON, structured data
- Version strings, dates, proper nouns, technical terms
- Headings, list markers, table structure

Compression applies to articles, hedging, pleasantries, and connective fluff — never to load-bearing identifiers or structured data. The init-rule `memory-hygiene.md` (memory files) and `internal-artifact-compression.md` (pipeline scratch artifacts) cover the same discipline outside dispatch prompts; cross-reference them rather than restating the rules in skill bodies.

## 10. Error Handling

Detect → escalate via AskUserQuestion → never guess. Handle: empty args, missing test framework, zero-file scope, empty agent results (retry once then escalate), max iterations hit (summarize attempts + offer options).

## 11. Report Naming

`.mz/reports/<YYYY_MM_DD>_<type>_<detail>.md` — leading date (underscores, not dashes). On same-day collision append `_v2`, `_v3`. Example: `2026_04_20_debug_auth_bug.md`.

## 12. Model Selection

**opus**: code writing, code review, test writing, plan creation (accuracy-critical). **sonnet**: research, scanning, analysis, plan review (breadth over precision). **haiku**: exploration, file reading, boilerplate generation.

## 13. Parallel Fan-Out

Independent agents go in a **single message** as parallel tool calls. Wave size bounded by a constant (max 6). Sequential waves for overflow.

## 14. Fan-Out Wave Observability

When a skill dispatches a wave of parallel agents, the orchestrator must make the wave visible: a manifest before launching it, a rollup after it returns. A silent fan-out leaves the user unable to tell what was dispatched, what came back, or what failed.

**Pre-dispatch manifest** — emitted by the orchestrator immediately before launching the wave:

```
Dispatching <wave label> — <N> agents in parallel
Purpose: <one line>
- <agent> — <role, ≤6 words>
- <agent> — <role, ≤6 words>
```

**Post-wave rollup** — emitted once every agent in the wave has returned, before synthesis begins:

```
Wave complete — <returned>/<dispatched> agents returned
- <agent>: <STATUS or VERDICT> — <summary, ≤8 words>
```

**When to emit**: both blocks for every wave of 2 or more parallel agents. Skip for a single-agent dispatch — there is no wave to summarize. A skill that runs sequential waves emits a fresh manifest and rollup per wave, each labeled so the user can tell them apart.

**Validating returned blocks**: the rollup is the wave's validation surface. An agent that returns no `STATUS:`/`VERDICT:` line, or a malformed one, is listed as `<agent>: NO RETURN BLOCK` — never silently dropped from the count. The `<returned>/<dispatched>` ratio must be exact: if 5 agents were dispatched and 1 came back empty, the rollup reads `4/5` and names the missing agent.

**Privacy**: the manifest and rollup carry agent names, short role labels, and status only. They must not print secrets, tokens, absolute filesystem paths, or raw user data — a role label reads `security scan of auth module`, not the module's contents.

## 15. Tooling Detection

Detect test/lint/type-check tooling before first use. Save to `.mz/task/<task_name>/tooling.md`. Missing test framework → ask user, never skip silently.

## 16. Input Parsing

Document accepted input formats in SKILL.md. Empty or ambiguous args → ask, never guess.

When a skill must collect missing input from the user, it uses an **input collector**, not an approval gate. The two are different transactions and must not be conflated: an approval gate (Rule 1) presents a pipeline-produced artifact for Approve/Reject; an input collector gathers a value the pipeline needs before it can run. A collector therefore has **no artifact to render, no plan message, no Approve/Reject, and no "pre-gate block"** — that vocabulary belongs to gates only. A collector is single-surface: state the context and the question in one place and read the answer. Never emit a separate fenced block before the question.

Three collector shapes:

- **Closed choice** — one pick from a fixed set (output format, tone, scope mode, capture modality). When the set has 2–4 values, use one `AskUserQuestion` call with each value a named `option` (`**<Name>** — <one-line meaning>`). When the set is larger than AskUserQuestion's 4-option cap, name the most common values as `options` and enumerate the remainder in the question text for a free-text answer.
- **Confirm-or-customize** — accept defaults or supply detail (a bootstrap interview). One `AskUserQuestion` call with named `options` such as `Defaults` / `Minimal`; custom answers ride the free-text reply.
- **Open value** — a path, topic, or other free-text answer with no menu. Ask a direct prose question stating what is needed and why, then read the user's reply. `AskUserQuestion` is built for menus and is a poor fit here — do not force it.

Across all three: state the context with the question (never in a preceding block), never guess a value, and re-ask once on an invalid answer before failing per Rule 10. Call these "input collectors" or "intake questions" — never "pre-gate block".

## 17. Canonical Skill Anatomy

Every SKILL.md body must contain these 7 sections in order:

1. `## Overview` — 1 paragraph: what the skill does.
1. `## When to Use` — triggers plus `### When NOT to use` counter-triggers.
1. `## Core Process` — the non-negotiable steps or phase table.
1. `## Techniques` — concrete patterns and tools the skill applies.
1. `## Common Rationalizations` — anti-rationalization table (see Rule 18).
1. `## Red Flags` — signs the skill is being skipped or misapplied.
1. `## Verification` — how to confirm the skill actually ran.

**Pipeline exemption**: multi-phase orchestrator skills with a Phase Overview table may delegate sections **4 (Techniques), 5 (Common Rationalizations), 6 (Red Flags), and 7 (Verification)** to phase files by replacing each with a single pointer line: `<Section>: delegated to phase files — see Phase Overview table above.` Sections **1 (Overview), 2 (When to Use), and 3 (Core Process)** must remain fully inline in SKILL.md — they are load-bearing for invocation and orientation. This avoids duplication with phase files (Rule 2 progressive disclosure) while still satisfying the "every section present" check.

Pattern source: addyosmani/superpowers 7-section canonical anatomy.

**Skill types** (referenced by Rules 18, 21): *Discipline* skills enforce process and push back against shortcuts (build, debug, audit, verify, polish, cleanup, optimize, blast-radius). *Collaboration* skills work with the user on shared output (deep-research, outreach-research, brainstorm, expert, design-document, combine). *Reference* skills provide neutral knowledge (using-mozg-pipelines, construct-skill). These types are orthogonal to the model-tier archetypes in Rule 12 — a discipline skill may use any tier depending on its task.

## 18. Anti-Rationalization Tables

Mandatory for **discipline-enforcement** skills (build, debug, audit, verify, polish, cleanup, optimize, blast-radius — any skill that pushes back against user shortcuts). Optional for collaboration and reference skills.

Format under `## Common Rationalizations`:

```
| Rationalization | Rebuttal |
| --- | --- |
| "..."           | "..."    |
```

- Minimum 3 rows per discipline skill.
- Rationalizations must be empirically grounded (observed user excuses), not invented.
- Rebuttals must be specific — no generic "because it's best practice".

Canonical seed: `plugins/mz-dev-base/skills/construct-skill/references/anti-rationalization-library.md`.

## 19. CSO (Critical Skill Orientation)

Descriptions describe **trigger conditions only**, never workflow summaries. The description is the skill's auction bid for invocation — every character that isn't a trigger is waste.

- Lead with `ALWAYS invoke when...` phrasing.
- List 2–3 concrete trigger phrases.
- Include explicit "When NOT to use" counter-triggers inline or in the body.
- Ban workflow-summary tails: no `— orchestrates X, Y, Z` after the triggers.
- Max 250 chars (matches Rule 3).

Grounding: published LLM persuasion-compliance studies consistently show directive, authority-coded framing lifts compliance substantially over neutral phrasing.

## 20. References Directory

Skills may include an optional `references/` directory containing lazy-loaded knowledge.

- `references/<topic>.md` — per-topic content, ≤400 lines.
- SKILL.md or phase files point at specific reference files: `Reference: grep \`references/<file>.md\` for <topic>.\`
- Agents grep the file for the specific query; they do **not** load the whole file.

Purpose: keeps SKILL.md slim while making deep knowledge available on demand. Examples: `explain/references/mermaid-syntax-by-type.md`, `audit/references/owasp-top-10-checklist.md`.

## 21. Persuasion-Informed Language

Skill type determines the persuasion register (Cialdini principles applied to LLM compliance):

| Skill type        | Purpose                             | Persuasion register                   |
| ----------------- | ----------------------------------- | ------------------------------------- |
| **Discipline**    | Push back against shortcuts         | Authority + Commitment + Social Proof |
| **Collaboration** | Work with the user on shared output | Unity + Commitment                    |
| **Reference**     | Provide neutral knowledge           | Neutral / informational only          |

**Banned for discipline skills**: Liking ("I think you'll find...", "great question!"). Liking softens directives and cuts compliance.

Grounding: published persuasion-compliance studies consistently show directive, authority-coded framing lifts LLM compliance over neutral phrasing.

## 22. No Rule-Number Citations in Plugin Files

Skill and agent files under `plugins/` must not cite specific rule numbers from `SKILL_GUIDELINES.md` or `AGENTS_GUIDELINES.md`. Rule numbers are unstable — a renumbering during guideline edits cascades through every citation site and silently drifts.

**Prohibited in any file under `plugins/*/skills/**` or `plugins/*/agents/**`**:

- `per Rule 17`, `(Rule 20)`, `See Rule 11.`
- `per SKILL_GUIDELINES.md Rule 16`, `AGENTS_GUIDELINES.md Rule 13`
- `Rule 14 requires evidence.` as narrative
- Section headers like `## Skeleton (Rule 16)` or `### Status Protocol (Rule 13)`

**Use instead**:

- State the substance directly: `Discipline skills must not use Liking framing.` instead of `Rule 20 bans Liking for discipline skills.`
- Reference the guideline by file: `per SKILL_GUIDELINES.md` instead of `per SKILL_GUIDELINES.md Rule 16`.
- Drop decorative citations: a trailing `(Rule 9)` after a sentence that already states the rule — just delete it.

**Scope and exceptions**:

- Applies to every file under `plugins/*/skills/**` and `plugins/*/agents/**`.
- The guidelines files themselves (`guidelines/SKILL_GUIDELINES.md`, `guidelines/AGENTS_GUIDELINES.md`) may cross-reference their own rules by number — the numbers are stable within the same document.
- Repo-root docs (`README.md`, `CLAUDE.md`), commit messages, PR descriptions, and review reports may cite rule numbers when discussing compliance.

Rationale: rule numbers are shared identifiers between the guidelines and the bodies that cite them. Every citation is a load-bearing pointer that breaks when a rule is added or removed. Substance-first prose ages gracefully; citation prose does not.

## 23. Pre-Publish Checklist

Before merging any new or modified skill:

- [ ] Description follows Rule 3 (third person, directive, front-loaded, trigger phrases)
- [ ] Every approval gate uses the two-surface plan pattern: full verbatim artifact as a chat message, then a short AskUserQuestion selector with exactly **Approve**/**Reject** options (Rule 1)
- [ ] Variant gates (multi-option menus) present each named action as `**<Name>** — <summary>`; feedback rides the free-text field, no separate Feedback option (Rule 1)
- [ ] SKILL.md under 150 lines, phase files under 400 lines
- [ ] Scope parameter accepted with documented default if code-editing skill (Rule 6)
- [ ] All bounds and paths declared as named constants, no inline hardcoded limits (Rule 7)
- [ ] State persisted to `.mz/task/<task_name>/state.md` with task-naming convention (Rule 8)
- [ ] Dispatch prompts carry only task-specific context, no agent-instruction repetition (Rule 9)
- [ ] Error paths escalate via AskUserQuestion, never silently guess (Rule 10)
- [ ] Model tier (opus/sonnet/haiku) chosen per Rule 12 for each agent dispatch
- [ ] Tooling (test/lint/type) detected on first use and recorded to `tooling.md` (Rule 15)
- [ ] Input formats documented in SKILL.md; empty or ambiguous args ask, never guess (Rule 16)
- [ ] All phase file references in SKILL.md resolve to existing files
- [ ] Agent names in dispatch prompts match actual agent definitions
- [ ] No nested file references (one level deep from SKILL.md)
- [ ] Consistent terminology across all files in the skill
- [ ] Tested with direct invocation (`/skill-name`) and natural language trigger
- [ ] Canonical 7-section anatomy present (Rule 17)
- [ ] Anti-rationalization table present if discipline skill (Rule 18)
- [ ] Description is CSO-compliant, no workflow summary (Rule 19)
- [ ] references/ directory uses grep-first pattern if present (Rule 20)
- [ ] Language matches skill type per Rule 21
- [ ] No guideline rule numbers cited in SKILL.md, phase files, or references (Rule 22)
