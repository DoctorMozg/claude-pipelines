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

## 16. Pre-Publish Checklist

Before merging any new or modified skill:

- [ ] Description follows Rule 3 (third person, directive, front-loaded, trigger phrases)
- [ ] SKILL.md under 150 lines, phase files under 400 lines
- [ ] All phase file references in SKILL.md resolve to existing files
- [ ] Agent names in dispatch prompts match actual agent definitions
- [ ] No nested file references (one level deep from SKILL.md)
- [ ] Consistent terminology across all files in the skill
- [ ] Tested with direct invocation (`/skill-name`) and natural language trigger
