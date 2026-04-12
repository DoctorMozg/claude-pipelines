---
name: translate
description: ALWAYS invoke when the user wants to translate files, docs, or i18n resources. Triggers - "translate X to Y", "localize", "i18n to <lang>". When NOT to use - single-sentence phrase translation (answer inline).
argument-hint: <natural language request — e.g. "translate README.md to Russian" or "translate locales/en.json to fr mode:i18n">
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch
---

# Translate & Localize Pipeline

## Overview

Orchestrates a plan-approve-translate-verify flow for translating documents, READMEs, and i18n resources. Discovery produces a reviewable plan; an approval gate blocks every dispatch until the user confirms; parallel `pipeline-translator` waves produce output with Tier-1 structural checks inside each agent; an LLM-as-Judge sweep runs Tier-2 semantic review across all chunks; uncertainty-driven Tier-3 probes (Wiktionary, MyMemory, back-translation) spend budget only on chunks the earlier tiers flagged. Verification is always on.

## When to Use

- Translate or localize documents, READMEs, docs directories, or i18n resource files into another language.
- Triggers: "translate X to Y", "localize this to <lang>", "i18n to <lang>", "render the README in Russian".
- Supported formats: `md`, `mdx`, `json`, `yaml`/`yml`, `po`, `properties`, `strings`, `xliff`, `txt`.

### When NOT to use

- Single-sentence phrase lookup — answer inline, do not orchestrate a pipeline.
- Code comments or string-literal polish — use the `polish` skill.
- Live machine-translation chat — out of scope for a file-oriented pipeline.
- Binary formats (`.docx`, `.pdf`, images) — unsupported; escalate via AskUserQuestion.

## Input

`$ARGUMENTS` is a natural-language request. Accepted forms: `translate <path> to <lang>` and `translate <path> to <lang> mode:<sidecar|inplace|i18n>`. There is no verification opt-in flag in the grammar — tiered verification is always on and its fixed cost is shown to the user at the approval gate. Source language defaults to auto-detect; output mode defaults to `sidecar`. Empty or ambiguous arguments escalate via AskUserQuestion — never guess.

## Constants

- **MAX_PARALLEL_TRANSLATORS**: 6 | **MAX_CHUNK_LINES**: 500 | **MAX_VERIFICATION_ATTEMPTS**: 2 | **MAX_APPROVAL_ITERATIONS**: 3
- **MAX_JUDGE_BATCH**: 6 (chunks per parallel judge dispatch)
- **MAX_WIKTIONARY_LOOKUPS**: 10 (per-run cap across all chunks)
- **MAX_MYMEMORY_QUERIES**: 9 (per-run cap, under MyMemory 5K-char/day free tier)
- **TASK_DIR**: `.mz/task/`

## Core Process

### Phase Overview

| #   | Phase                                                                    | Reference                                | Loop?                           |
| --- | ------------------------------------------------------------------------ | ---------------------------------------- | ------------------------------- |
| 0   | Setup                                                                    | inline below                             | —                               |
| 1   | Discovery + planning                                                     | `phases/discovery_and_planning.md`       | —                               |
| 1.5 | User approval gate                                                       | inline below                             | re-plan on feedback             |
| 2   | Parallel translation + Tier-1 structural verification (inside agent)     | `phases/translation_and_verification.md` | wave loop                       |
| 3   | Cross-file consistency scan + glossary delta merge                       | `phases/translation_and_verification.md` | —                               |
| 4   | Tier-2 semantic verification (LLM-as-Judge, all chunks, wave-split)      | `phases/translation_and_verification.md` | bounded                         |
| 5   | Tier-3 uncertainty-driven verification (Wiktionary / MyMemory / back-tr) | `phases/translation_and_verification.md` | bounded                         |
| 6   | Bounded re-translation loop on chunks with `Critical:` findings          | `phases/translation_and_verification.md` | max `MAX_VERIFICATION_ATTEMPTS` |
| 7   | Finalization + summary                                                   | inline below                             | —                               |

### Phase 0: Setup

- Derive task name `translate_<slug>_<HHMMSS>` where `<slug>` is a snake_case summary of the raw argument (max 20 chars).
- Create `TASK_DIR/<task_name>/` on disk.
- Write initial `state.md` with `Status: running`, `Phase: setup`, `Started: <ISO 8601>`, `approval_iterations: 0`.
- TaskCreate a top-level task for the run so progress is visible to the user.

### Phase 1: Discovery + Planning

Read `phases/discovery_and_planning.md` at phase entry and run steps 1.1 through 1.8 in order. Output: `<task_dir>/translation_plan.md`, `<task_dir>/discovery.md`, `<task_dir>/glossary.json`. State → `discovery_complete`.

### Phase 1.5: User Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated. Full detail in `phases/discovery_and_planning.md` under `Phase 1.5`; the five load-bearing elements are:

- Show `<task_dir>/translation_plan.md` verbatim plus the verification cost block (chunks, judge batches via `MAX_JUDGE_BATCH`, Tier-3 caps via `MAX_WIKTIONARY_LOOKUPS` / `MAX_MYMEMORY_QUERIES`, wall-clock range, `INPLACE_DESTRUCTIVE` highlight).
- Ask via AskUserQuestion ending literally with: `Reply 'approve' to proceed with translation, 'reject' to abort, or provide feedback for changes.`
- **"approve"** → state `plan_approved`, proceed to Phase 2.
- **"reject"** → state `aborted_by_user`, stop. Do not proceed.
- **Feedback** → re-run affected Phase 1 sub-steps, overwrite the plan, re-present **via AskUserQuestion**. Increment `approval_iterations`; bounded by `MAX_APPROVAL_ITERATIONS`. **This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.**

### Phases 2–6

Read `phases/translation_and_verification.md` on entry to Phase 2 and keep it loaded through Phase 6. Each phase ends with a state transition:

- **Phase 2** — parallel `pipeline-translator` waves, each running Tier-1 structural verification before returning. State → `translation_complete`.
- **Phase 3** — merge every `glossary_delta_<chunk_id>.json`, sweep for cross-file term drift, re-dispatch drifted chunks. State → `consistency_complete`.
- **Phase 4** — LLM-as-Judge on every chunk via `ceil(total_chunks / MAX_JUDGE_BATCH)` parallel `pipeline-code-reviewer` dispatches. State → `judge_complete`.
- **Phase 5** — Tier-3 only on chunks flagged uncertain or carrying a Tier-2 `Critical:`. Wiktionary and MyMemory bounded by their constants; back-translation only on chunks with a Tier-2 `Critical:`. State → `deep_verify_complete`.
- **Phase 6** — bounded re-translation on chunks with an unresolved `Critical:` finding, capped per chunk by `MAX_VERIFICATION_ATTEMPTS` across all phases. State → `retranslation_complete`.

### Phase 7: Finalization

- Write `<task_dir>/summary.md` per the Phase 7.1 shape in `phases/translation_and_verification.md`.
- Update `state.md` phase to `complete` with `ended_at`, `final_outputs`, `escalations`, `phase_history`, `tier3_ledger_path`.
- Print the summary block to the user as the terminal orchestrator message.

## Techniques

Delegated to phase files (see Phase Overview table). Reference material: grep `references/placeholder-patterns.md`, `references/markdown-preservation-rules.md`, `references/language-codes.md`.

## Common Rationalizations

| Rationalization                               | Rebuttal                                                                                                                                    |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| "skip the plan gate, it's just a translation" | "sidecar vs inplace is the difference between a review diff and a destroyed original; the gate costs seconds and prevents days of cleanup." |
| "LLM translation is good enough, skip Tier-1" | "an LLM will silently drop `{{user.name}}` and your app will crash in production; `grep -c` costs nothing."                                 |
| "only judge the headings; skip full Tier-2"   | "the prioritized rubric already front-loads headings — the rest of the chunk is judged in the same pass; the savings are illusory."         |

## Red Flags

- You dispatched translators without user approval.
- You used `mode:inplace` without showing the destructive warning.
- You marked a chunk `DONE` without running Tier-1 verification.
- You skipped Tier-2 on any chunk (judge must run on every chunk).
- You ran Tier-3 on every chunk instead of only those flagged uncertain.

## Verification

On completion, print the summary block from `<task_dir>/summary.md` covering files translated, Tier-1 pass/fail, Tier-2 verdicts and finding counts, Tier-3 lookup counts (`<used> / MAX_*`), glossary seeded/added/conflict counts, Phase 6 re-translation count, and every `DONE_WITH_CONCERNS` chunk surfaced for human review.
