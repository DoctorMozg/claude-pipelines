# Phase 1: Scan Claims in the Note

## Goal

Dispatch the `provenance-tracer` agent against the resolved note, collect its YAML classification artifact into `.mz/task/<task_name>/claims_analysis.md`, validate the artifact's shape, and hand control back to the Phase 1.5 approval gate in `SKILL.md`.

## Preconditions

Phase 0 has already resolved:

- `note_path` — absolute path to the single vault note under audit.
- `task_name` — the orchestrator task identifier.
- `state.md` — written under `.mz/task/<task_name>/` with `Status: running`, `Phase: 0`.

If `note_path` does not resolve to a readable file, Phase 0 must have escalated via AskUserQuestion. Do not enter Phase 1 without a readable note.

## Actions

### 1. Dispatch `provenance-tracer` agent

Dispatch the `provenance-tracer` agent with this task-specific prompt:

```
Note path: <note_path>
Output path: .mz/task/<task_name>/claims_analysis.md
Task name: <task_name>
Vocabulary: [first-hand, cited, inferred, received, unmarked]
Max claims: 25

Read the single note at the provided path. Extract declarative factual claims (not questions, hedges, or procedural text). For each claim, classify against the closed five-value vocabulary, cite the exact phrase that triggered the classification, propose sources from in-body citations, wikilinks, or existing sources frontmatter, and record confidence and reasoning.

Write the full YAML report to the output path. Return a one-line summary and STATUS.
```

Do not repeat the agent's general process, vocabulary semantics, or output schema — those already live in the agent body.

### 2. Validate the artifact shape

After the agent completes, Read `.mz/task/<task_name>/claims_analysis.md` using the Read tool. Confirm:

- The file exists and is non-empty.
- The top-level YAML contains a `claims:` list and a `summary:` map.
- Every entry in `claims:` carries all six required keys: `claim_text`, `line_range`, `proposed_status`, `proposed_sources`, `confidence`, `reasoning`.
- Every `proposed_status` value is one of `first-hand | cited | inferred | received | unmarked` — any other value is a shape failure.
- Every `confidence` value is one of `high | medium | low`.
- `summary` contains `total`, `by_status` (with the five vocabulary keys), `unmarked_ratio`, and `capped`.

If any check fails, re-dispatch `provenance-tracer` **once** with an explicit format-correction instruction appended to the prompt:

```
Previous dispatch produced an invalid report shape: <summary of the failure>.
Re-emit the full YAML with every required key on every claim entry.
Vocabulary is closed — do not invent values outside [first-hand, cited, inferred, received, unmarked].
Confidence is closed — do not invent values outside [high, medium, low].
```

If the second attempt still fails validation, halt and escalate via AskUserQuestion with the offending field(s) named. Never fabricate a report or silently retry beyond the single re-dispatch.

### 3. Update state

Patch `.mz/task/<task_name>/state.md`:

- `Status: scan_complete`
- `Phase: 1`
- `ClaimsAnalysisPath: .mz/task/<task_name>/claims_analysis.md`
- `ClaimsCount: <summary.total>`
- `UnmarkedRatio: <summary.unmarked_ratio>`
- `Capped: <summary.capped>`

### 4. Return to SKILL Phase 1.5 approval gate

Hand control back to `SKILL.md` Phase 1.5. The gate is responsible for the Read + verbatim presentation of `claims_analysis.md` — do not present classifications from inside this phase file.

## Error handling

- **Tracer returns `STATUS: NEEDS_CONTEXT`** — re-dispatch once with the missing field explicitly named in the prompt. If the second attempt still returns `NEEDS_CONTEXT`, escalate via AskUserQuestion.
- **Tracer returns `STATUS: BLOCKED`** — read the reason, update `state.md` with `Status: blocked`, and escalate via AskUserQuestion. Never auto-retry a blocked dispatch.
- **Tracer returns `STATUS: DONE_WITH_CONCERNS`** (note has \<3 claims — low signal) — proceed to Phase 1.5 but surface the low-signal flag in the state file as `LowSignal: true`. The approval gate still runs so the user sees the sparse classification and decides whether to proceed.
- **Report shape invalid after re-dispatch** — do not proceed to Phase 1.5. The approval gate requires a valid classification artifact; a malformed report is a failed phase, not an approvable artifact.

## Notes for the approval gate

The Phase 1.5 approval gate inside `SKILL.md` will Read `claims_analysis.md` and present its full verbatim contents via AskUserQuestion. This phase file's job ends once the artifact is written and its shape is verified — the presentation belongs to the orchestrator, never to a subagent.
