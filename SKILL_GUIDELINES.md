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

- Write in third person ("Processes files..." not "I can help you...")
- Use directive phrasing: "ALWAYS invoke when the user asks about [topic]"
- Front-load the key use case within 250 characters (truncated in listings)
- Include both WHAT the skill does AND WHEN to use it
- Include 2-3 example trigger phrases for activation reliability

## 4. Instruction Framing

- Prefer positive framing: "Use X exclusively" over "Do NOT use Y" — reduces violations by ~50%.
- Anchor critical rules at the top AND bottom of SKILL.md (primacy-recency bias).
- Every verification step must produce visible output. "Check X" → "Output a block showing X, then proceed." Silent checks get skipped.
- See Rule 23 for skill-type-specific language recipes.

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

**Pipeline exemption**: multi-phase orchestrator skills with a Phase Overview table may replace the full `## Techniques` section with a single line: `Techniques: delegated to phase files — see Phase Overview table above.` This avoids duplication with phase files (Rule 2 progressive disclosure) while still satisfying the "every section present" check.

Pattern source: addyosmani/superpowers 7-section canonical anatomy.

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

Canonical seed: `writing-skills/references/anti-rationalization-library.md`.

## 18. CSO (Critical Skill Orientation)

Descriptions describe **trigger conditions only**, never workflow summaries. The description is the skill's auction bid for invocation — every character that isn't a trigger is waste.

- Lead with `ALWAYS invoke when...` phrasing.
- List 2–3 concrete trigger phrases.
- Include explicit "When NOT to use" counter-triggers inline or in the body.
- Ban workflow-summary tails: no `— orchestrates X, Y, Z` after the triggers.
- Max 250 chars (matches Rule 3).

Grounding: Meincke et al. (2025) N=28,000 LLM persuasion compliance study — directive, authority-coded language lifts compliance from 33% baseline to 72%.

## 19. Source-Hierarchy Discipline

Researcher and review agents must declare and enforce a source priority ladder:

1. Official docs (vendor-hosted, versioned)
1. Official blog (vendor-hosted, dated)
1. MDN / web.dev / caniuse (curated, versioned)
1. Vendor-maintained GitHub wiki
1. Peer-reviewed papers (for claims)

**Banned sources**: Stack Overflow, AI-generated summaries (including other LLMs' output), undated blog posts, forum threads.

**Disclosure tokens** (emit in research output so orchestrators can grep):

- `STACK DETECTED: <stack + version>` — before any research query, detect project stack from manifests (package.json, pyproject.toml, Cargo.toml, go.mod).
- `CONFLICT DETECTED: <source A> says X, <source B> says Y` — when sources disagree.
- `UNVERIFIED: <claim> — could not confirm against official source` — when no authoritative source found.

Pattern source: obra/superpowers `source-hierarchy-discipline`.

## 20. Severity-Labeled Review Output

Review agents prefix every finding with a severity label:

- `Critical:` — blocks merge or plan advancement.
- `Nit:` — cosmetic or subjective; advisory.
- `Optional:` — improvement suggestion; advisory.
- `FYI:` — informational; advisory.

Verdict logic: `VERDICT: PASS` if zero `Critical:` findings, regardless of Nit/Optional/FYI count. `VERDICT: FAIL` only if one or more `Critical:` findings exist.

## 21. Four-Status Subagent Escalation

Coder and planner agents emit a terminal `STATUS:` line with one of four values:

- `DONE` — work complete, proceed.
- `DONE_WITH_CONCERNS` — work complete but flagged concerns; orchestrator logs concerns and proceeds.
- `NEEDS_CONTEXT` — cannot proceed without specific info; orchestrator re-dispatches with added context.
- `BLOCKED` — fundamental obstacle (broken env, impossible constraint, ambiguous spec); orchestrator escalates to user via AskUserQuestion. **Never auto-retry the same operation on `BLOCKED`.**

## 22. References Directory

Skills may include an optional `references/` directory containing lazy-loaded knowledge.

- `references/<topic>.md` — per-topic content, ≤400 lines.
- SKILL.md or phase files point at specific reference files: `Reference: grep \`references/<file>.md\` for <topic>.\`
- Agents grep the file for the specific query; they do **not** load the whole file.

Purpose: keeps SKILL.md slim while making deep knowledge available on demand. Examples: `explain/references/mermaid-syntax-by-type.md`, `audit/references/owasp-top-10-checklist.md`.

## 23. Persuasion-Informed Language

Skill type determines the persuasion register (Cialdini principles applied per Meincke et al. 2025):

| Skill type        | Purpose                             | Persuasion register                   |
| ----------------- | ----------------------------------- | ------------------------------------- |
| **Discipline**    | Push back against shortcuts         | Authority + Commitment + Social Proof |
| **Collaboration** | Work with the user on shared output | Unity + Commitment                    |
| **Reference**     | Provide neutral knowledge           | Neutral / informational only          |

**Banned for discipline skills**: Liking ("I think you'll find...", "great question!"). Liking softens directives and cuts compliance.

Grounding: Meincke et al. (2025), N=28,000 — compliance rose from 33% baseline to 72% under directive/authority framing.

## 24. Pre-Publish Checklist

Before merging any new or modified skill:

- [ ] Description follows Rule 3 (third person, directive, front-loaded, trigger phrases)
- [ ] SKILL.md under 150 lines, phase files under 400 lines
- [ ] All phase file references in SKILL.md resolve to existing files
- [ ] Agent names in dispatch prompts match actual agent definitions
- [ ] No nested file references (one level deep from SKILL.md)
- [ ] Consistent terminology across all files in the skill
- [ ] Tested with direct invocation (`/skill-name`) and natural language trigger
- [ ] Canonical 7-section anatomy present (Rule 16)
- [ ] Anti-rationalization table present if discipline skill (Rule 17)
- [ ] Description is CSO-compliant, no workflow summary (Rule 18)
- [ ] Research/review agents declare source hierarchy (Rule 19)
- [ ] Review output uses severity labels (Rule 20)
- [ ] Subagent output uses four-status protocol (Rule 21)
- [ ] references/ directory uses grep-first pattern if present (Rule 22)
- [ ] Language matches skill type per Rule 23
