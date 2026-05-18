---
name: do-roast
description: ALWAYS invoke when the user wants a code roast, character-voice critique, or funny review grounded in real findings. Triggers: "roast this code", "do-roast", "make fun of", "character roast of".
argument-hint: <persona> <freeform target — path, branch, text, or natural-language scope>
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Glob, Grep, AskUserQuestion, WebFetch, WebSearch
---

# Evidence-Anchored Character Roasting Pipeline

## Overview

You orchestrate a character-voice code roast. Static analysis, docs coherence, and web best-practice research produce a structured dossier of numbered findings; the user's chosen persona agent renders a roast that may embellish tone but may not invent substance. Every roast line must cite a real finding.

## When to Use

Invoke when the user wants funny pushback, team levity, a character-voice review, or a mock review of a PR. Trigger phrases: "roast this code", "do-roast", "make fun of", "character roast of".

### When NOT to use

- Actual code review — use `/review-branch` or `/audit`.
- Actual planning — use `/build`.
- Serious architecture critique — use `/explain`.
- The target does not exist or cannot be resolved to concrete files or text.

## Input

`$ARGUMENTS` is split on first whitespace. Token 1 = persona (validated against `PERSONA_ALLOWLIST`, case-insensitive). Remainder = free-form target prompt. Empty `$ARGUMENTS` → ask. Unknown persona → ask with allowlist. Empty remainder → ask.

## Constants

- **PERSONA_ALLOWLIST**: `["caveman", "wh40k-ork", "pirate", "viking", "dwarf", "drill-sergeant", "yoda"]` (lowercase canonical)
- **MAX_PERSONAS**: 7 (allowlist bound; single-persona dispatch per invocation)
- **TASK_DIR**: `.mz/task/`
- **REPORT_DIR**: `.mz/reports/`
- **RESEARCH_CACHE_DIR**: `.mz/research/` (stack-wide web cache, 7-day staleness)
- **MAX_FINDINGS**: 30 (upper bound on dossier entries per invocation)
  - Note: `MAX_FINDINGS=30` is the upper bound. Analysis should prefer 10-15 high-quality Critical/Nit findings over 30 weak Optional/FYI — reduces dispatch token cost and improves voice focus.
- **DOSSIER_SEVERITY_LABELS**: `["Critical", "Nit", "Optional", "FYI"]`

## Available Personas

<!-- verify: every value in PERSONA_ALLOWLIST must appear in this table -->

| Persona        | Voice                         | Best for roasting                                           |
| -------------- | ----------------------------- | ----------------------------------------------------------- |
| caveman        | Hulk-speak, pre-linguistic    | Over-engineered abstractions — "me no understand, me smash" |
| wh40k-ork      | Greenskin dakka warrior       | Weedy/overclever code ("dat code iz weedy")                 |
| pirate         | Robert-Newton West-Country    | Ships that won't sail — bloated files, leaks, "Davy Jones"  |
| viking         | Skald with kennings           | Forgettable code, no sagas, "argr" / ignoble logic          |
| dwarf          | Scottish brogue + Dammaz Kron | Shoddy craftsmanship — "umgak", grudge book additions       |
| drill-sergeant | FMJ Gunnery-Sergeant cadence  | Discipline failures, fitness metaphors, profanity allowed   |
| yoda           | OSV-inverted disappointment   | Clouded logic, "much to learn" disappointment register      |

## Core Process

### Phase Overview

| #   | Phase                      | Details             |
| --- | -------------------------- | ------------------- |
| 0   | Setup + arg parse          | Inline below        |
| 0.5 | Target resolution gate     | Inline below        |
| 1   | Structural/smell analysis  | `phases/analyze.md` |
| 2   | Docs coherence analysis    | `phases/analyze.md` |
| 3   | Web best-practice research | `phases/analyze.md` |
| 4   | Dossier writer             | `phases/analyze.md` |
| 5   | Persona dispatch           | `phases/render.md`  |
| 6   | Report assembly + teaser   | `phases/render.md`  |

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                                                                                | Rebuttal                                                                                                                |
| ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| "Just this once, the persona can riff on something not in the dossier — it's funnier."         | The whole plugin's value is evidence anchoring. One fabricated line poisons every future roast's credibility. Cut it.   |
| "The code probably has this bug even though analysis didn't find it — persona can mention it." | If analysis missed it, analysis gets re-run. The persona may not invent findings. Re-run Phase 1-4, do not extrapolate. |
| "The user will never notice a made-up line if the rest is grounded."                           | The user will grep the roast for `Finding N` citations. Fabrication is detectable and contractually forbidden.          |

## Red Flags

- Dossier contains fewer than 3 findings but persona roast is >200 lines — embellishment exceeded substance.
- Roast mentions a file path that does not appear in the dossier — fabrication.
- Persona agent was dispatched without the dossier inlined in the prompt.
- Any author name, git blame output, or real-person reference in the dossier or report.
- Approval gate at Phase 0.5 was skipped.

## Verification

Output a visible block showing: task name, resolved target, persona chosen, finding count by severity, report path, and the rendered teaser paragraph. Confirm the report file exists and is non-empty. Confirm every `Finding N` in the dossier has at least one reference in the rendered roast (soft check).

## Phase 0: Setup

Parse `$ARGUMENTS`: split on first whitespace; validate token 1 against `PERSONA_ALLOWLIST` (lowercase compare). Unknown → AskUserQuestion listing allowed personas. Empty remainder → AskUserQuestion asking what to roast. Skill name `do-roast` → task dir prefix `do_roast` (snake_case). Derive task name: `<YYYY_MM_DD>_do_roast_<slug>` where slug is a snake_case summary (max 20 chars) of the resolved target or first 3 words of the remainder, and `<YYYY_MM_DD>` is today's date with underscores. Create `TASK_DIR<task_name>/`. Write `state.md` with `schema_version: 2` as the first line, then `Status: started`, `Phase: setup`, `Started: <ISO8601>`, `Persona: <chosen>`, `Target_raw: <remainder>`.

## Phase 0.5: Target Resolution Gate

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Capture the resolved target candidates produced by the target resolution ladder in `phases/analyze.md` — file list, directory list, branch diff command, or raw-text blob (truncated to 1000 chars) — into context.

**Surface 1 — emit the plan message.** Output the resolved target as a normal markdown chat message. Emit the full verbatim contents — do not substitute a path, summary, or placeholder. Structure:

```
## Target resolution ready for review — do-roast

Resolved "<target_raw>" to the following target as <persona>:

<verbatim resolved target list or blob (truncated to 1000 chars if raw text)>

---
**Approve** → proceed to Phase 1 (structural/smell analysis)  ·  **Reject** → abort the roast, no analysis performed  ·  reply with feedback to adjust the target scope
```

**Surface 2 — call AskUserQuestion.** After the plan message, call AskUserQuestion. The question must NOT re-embed the resolved target — it lives in the plan message above.

- question: `The resolved target above is ready for review.`
- options:
  - **Approve** — proceed to Phase 1 (structural/smell analysis)
  - **Reject** — abort the roast, no analysis performed

**Response handling**:

- **Approve** → update state `Phase: target_approved`, proceed to Phase 1.
- **Reject** → update state `Status: aborted_by_user` and stop. Do not proceed.
- **Any other reply (feedback)** → re-resolve per feedback, update state, return to Surface 1, re-read and re-emit the full updated plan message from scratch, re-present the selector. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 1 without explicit approval.

## Error Handling

- Empty `$ARGUMENTS` → AskUserQuestion (never guess).
- Unknown persona → AskUserQuestion with `PERSONA_ALLOWLIST`.
- Target resolves to 0 files AND is not raw text → escalate with `STATUS: BLOCKED` and prompt user.
- Persona agent returns empty → retry once with clarified prompt; still empty → write state `DONE_WITH_CONCERNS` and include raw dossier in report.

## State Management

Update `TASK_DIR<task_name>/state.md` after every phase transition. Track: current phase, persona, resolved target list, finding counts by `DOSSIER_SEVERITY_LABELS`, report path.

State persists to `.mz/task/<task_name>/state.md` with `schema_version: 2` as its first line. This is a single-dispatch skill (setup → dispatch → report in one turn), so the `phase_complete` / `what_remains` progress-ledger fields are not required. On reading a `schema_version: 1` or unversioned file, add `schema_version: 2` and log the upgrade.

Critical: every line of the rendered roast must trace to a numbered Finding in the dossier. No invention. No real-person attacks. No git blame. If the persona cannot find something to roast within the evidence, it says so — it does not fabricate.
