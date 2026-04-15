# Skill Authoring Guidelines

Rules for writing skills in this repository. All skills must comply.

## 1. Approval Gates Must Loop

Every approval gate must follow this exact structure:

1. **Delegation guard**: `**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.`
1. **Presentation**: what to show the user (plan, findings, diagnosis, decomposition).
1. **AskUserQuestion prompt**: ends with `Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.`
1. **Response handling** as a labeled section with three bullets:
   - **"approve"** → update state, proceed to next phase.
   - **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
   - **Feedback** → incorporate, re-run upstream phase if needed, return to this gate, re-present **via AskUserQuestion** (same format). Explicitly state: "This is a loop — repeat until the user explicitly approves. Never proceed to Phase N without explicit approval."

All five elements are required. Do not omit the delegation guard, reject option, or loop language.

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
- See Rule 18 (CSO) for the complete description format spec.

## 4. Instruction Framing

- Prefer positive framing: "Use X exclusively" over "Do NOT use Y" — reduces violations by ~50%.
- Anchor critical rules at the top AND bottom of SKILL.md (primacy-recency bias).
- Every verification step must produce visible output. "Check X" → "Output a block showing X, then proceed." Silent checks get skipped.
- See Rule 20 for skill-type-specific language recipes.

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

Multi-phase skills persist state to `.mz/task/<task_name>/state.md`. Required fields: Status, Phase, Started. Update after every phase transition. Critical: never rely on conversation memory for cross-phase state — context compaction destroys specific paths and decisions.

**Task naming convention**: `<skill>_<slug>_<HHMMSS>` where `<skill>` is the skill name, `<slug>` is a snake_case summary of the argument (max 20 chars), and `<HHMMSS>` is wall-clock time. This prevents collisions across skills and re-runs. Example: `build_oauth_flow_143022`, `debug_payment_err_150511`.

## 9. Dispatch Prompt Compression

Agent files already contain general process/rules/format. Dispatch prompts provide **only** task-specific context: what to work on, artifact pointers, scope constraints, output format overrides. Don't repeat agent instructions. Explicitly request concise output — output tokens cost 5x input.

## 10. Error Handling

Detect → escalate via AskUserQuestion → never guess. Handle: empty args, missing test framework, zero-file scope, empty agent results (retry once then escalate), max iterations hit (summarize attempts + offer options).

## 11. Report Naming

`.mz/reports/<type>_<YYYY_MM_DD>_<detail>.md` — append `_v2`, `_v3` if exists.

## 12. Model Selection

**opus**: code writing, code review, test writing, plan creation (accuracy-critical). **sonnet**: research, scanning, analysis, plan review (breadth over precision). **haiku**: exploration, file reading, boilerplate generation.

## 13. Parallel Fan-Out

Independent agents go in a **single message** as parallel tool calls. Wave size bounded by a constant (max 6). Sequential waves for overflow.

## 14. Tooling Detection

Detect test/lint/type-check tooling before first use. Save to `.mz/task/<task_name>/tooling.md`. Missing test framework → ask user, never skip silently.

## 15. Input Parsing

Document accepted input formats in SKILL.md. Empty or ambiguous args → ask, never guess.

## 16. Canonical Skill Anatomy

Every SKILL.md body must contain these 7 sections in order:

1. `## Overview` — 1 paragraph: what the skill does.
1. `## When to Use` — triggers plus `### When NOT to use` counter-triggers.
1. `## Core Process` — the non-negotiable steps or phase table.
1. `## Techniques` — concrete patterns and tools the skill applies.
1. `## Common Rationalizations` — anti-rationalization table (see Rule 17).
1. `## Red Flags` — signs the skill is being skipped or misapplied.
1. `## Verification` — how to confirm the skill actually ran.

**Pipeline exemption**: multi-phase orchestrator skills with a Phase Overview table may delegate sections **4 (Techniques), 5 (Common Rationalizations), 6 (Red Flags), and 7 (Verification)** to phase files by replacing each with a single pointer line: `<Section>: delegated to phase files — see Phase Overview table above.` Sections **1 (Overview), 2 (When to Use), and 3 (Core Process)** must remain fully inline in SKILL.md — they are load-bearing for invocation and orientation. This avoids duplication with phase files (Rule 2 progressive disclosure) while still satisfying the "every section present" check.

Pattern source: addyosmani/superpowers 7-section canonical anatomy.

**Skill types** (referenced by Rules 17, 20): *Discipline* skills enforce process and push back against shortcuts (build, debug, audit, verify, polish, optimize, blast-radius). *Collaboration* skills work with the user on shared output (deep-research, lead-gen, brainstorm, expert, design-document, combine). *Reference* skills provide neutral knowledge (using-mozg-pipelines, writing-skills). These types are orthogonal to the model-tier archetypes in Rule 12 — a discipline skill may use any tier depending on its task.

## 17. Anti-Rationalization Tables

Mandatory for **discipline-enforcement** skills (build, debug, audit, verify, polish, optimize, blast-radius — any skill that pushes back against user shortcuts). Optional for collaboration and reference skills.

Format under `## Common Rationalizations`:

```
| Rationalization | Rebuttal |
| --- | --- |
| "..."           | "..."    |
```

- Minimum 3 rows per discipline skill.
- Rationalizations must be empirically grounded (observed user excuses), not invented.
- Rebuttals must be specific — no generic "because it's best practice".

Canonical seed: `plugins/mz-dev-base/skills/writing-skills/references/anti-rationalization-library.md`.

## 18. CSO (Critical Skill Orientation)

Descriptions describe **trigger conditions only**, never workflow summaries. The description is the skill's auction bid for invocation — every character that isn't a trigger is waste.

- Lead with `ALWAYS invoke when...` phrasing.
- List 2–3 concrete trigger phrases.
- Include explicit "When NOT to use" counter-triggers inline or in the body.
- Ban workflow-summary tails: no `— orchestrates X, Y, Z` after the triggers.
- Max 250 chars (matches Rule 3).

Grounding: published LLM persuasion-compliance studies consistently show directive, authority-coded framing lifts compliance substantially over neutral phrasing.

## 19. References Directory

Skills may include an optional `references/` directory containing lazy-loaded knowledge.

- `references/<topic>.md` — per-topic content, ≤400 lines.
- SKILL.md or phase files point at specific reference files: `Reference: grep \`references/<file>.md\` for <topic>.\`
- Agents grep the file for the specific query; they do **not** load the whole file.

Purpose: keeps SKILL.md slim while making deep knowledge available on demand. Examples: `explain/references/mermaid-syntax-by-type.md`, `audit/references/owasp-top-10-checklist.md`.

## 20. Persuasion-Informed Language

Skill type determines the persuasion register (Cialdini principles applied to LLM compliance):

| Skill type        | Purpose                             | Persuasion register                   |
| ----------------- | ----------------------------------- | ------------------------------------- |
| **Discipline**    | Push back against shortcuts         | Authority + Commitment + Social Proof |
| **Collaboration** | Work with the user on shared output | Unity + Commitment                    |
| **Reference**     | Provide neutral knowledge           | Neutral / informational only          |

**Banned for discipline skills**: Liking ("I think you'll find...", "great question!"). Liking softens directives and cuts compliance.

Grounding: published persuasion-compliance studies consistently show directive, authority-coded framing lifts LLM compliance over neutral phrasing.

## 21. No Rule-Number Citations in Plugin Files

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

## 22. Pre-Publish Checklist

Before merging any new or modified skill:

- [ ] Description follows Rule 3 (third person, directive, front-loaded, trigger phrases)
- [ ] SKILL.md under 150 lines, phase files under 400 lines
- [ ] Scope parameter accepted with documented default if code-editing skill (Rule 6)
- [ ] All bounds and paths declared as named constants, no inline hardcoded limits (Rule 7)
- [ ] State persisted to `.mz/task/<task_name>/state.md` with task-naming convention (Rule 8)
- [ ] Dispatch prompts carry only task-specific context, no agent-instruction repetition (Rule 9)
- [ ] Error paths escalate via AskUserQuestion, never silently guess (Rule 10)
- [ ] Model tier (opus/sonnet/haiku) chosen per Rule 12 for each agent dispatch
- [ ] Tooling (test/lint/type) detected on first use and recorded to `tooling.md` (Rule 14)
- [ ] Input formats documented in SKILL.md; empty or ambiguous args ask, never guess (Rule 15)
- [ ] All phase file references in SKILL.md resolve to existing files
- [ ] Agent names in dispatch prompts match actual agent definitions
- [ ] No nested file references (one level deep from SKILL.md)
- [ ] Consistent terminology across all files in the skill
- [ ] Tested with direct invocation (`/skill-name`) and natural language trigger
- [ ] Canonical 7-section anatomy present (Rule 16)
- [ ] Anti-rationalization table present if discipline skill (Rule 17)
- [ ] Description is CSO-compliant, no workflow summary (Rule 18)
- [ ] references/ directory uses grep-first pattern if present (Rule 19)
- [ ] Language matches skill type per Rule 20
- [ ] No guideline rule numbers cited in SKILL.md, phase files, or references (Rule 21)
