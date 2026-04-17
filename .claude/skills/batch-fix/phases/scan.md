# Phase 1 — Scan + Expand Brief

Full detail for the scan phase. Produces two artifacts: `criteria.md` (numbered check+fix list derived from the free-form brief) and `candidates.md` (per-file relevance scoring to reduce downstream dispatch cost).

## Contents

- [1.1 Enumerate files](#11-enumerate-files)
- [1.2 Quick relevance pre-scan](#12-quick-relevance-pre-scan)
- [1.3 Expand brief into criteria](#13-expand-brief-into-criteria)
- [1.4 Write artifacts](#14-write-artifacts)

______________________________________________________________________

## 1.1 Enumerate files

Run `Glob` for each pattern in `SCAN_GLOBS`, merge the results, deduplicate, and sort alphabetically. The three patterns are:

- `plugins/*/skills/**/SKILL.md`
- `plugins/*/skills/**/phases/*.md`
- `plugins/*/agents/*.md`

Files outside these globs are out of scope for this skill. Do not add `plugin.json`, `marketplace.json`, `references/*.md`, `scripts/*.sh`, or `rules/*.md` to the candidate set without an explicit argument override — those file types have separate ownership and tooling.

Record the raw count in `state.md` as `raw_candidates: N`.

## 1.2 Quick relevance pre-scan

For each enumerated file, perform a cheap heuristic pass so Phase 2 can skip obviously-irrelevant files without paying for a haiku dispatch. The goal is a coarse filter, not a decision — the proposer will still make the final call.

Heuristic procedure per file:

1. `Read` the first 60 lines (frontmatter + intro) using the `limit` parameter.
1. Extract keywords from the brief (anchors the user emphasized: "gate", "description", "STATUS", "approval", "VERDICT", "trigger phrase", etc.).
1. If any keyword appears in the first 60 lines OR in the filename, tag `likely_relevant`.
1. If the file is a SKILL.md or agent.md and the brief mentions structural elements (gate, frontmatter, anatomy) the file obviously has, tag `likely_relevant`.
1. If the file is a phase file and the brief targets SKILL-level shapes (frontmatter, top-level gate), tag `likely_skip`.
1. Otherwise tag `unclear`.

Tag vocabulary is exactly three values: `likely_relevant`, `unclear`, `likely_skip`. No other tag.

Only `likely_relevant` and `unclear` are dispatched in Phase 2. `likely_skip` files are listed in `candidates.md` for transparency but not scanned.

## 1.3 Expand brief into criteria

Produce a numbered check+fix list from the free-form brief. This is the single most important artifact — proposers read it verbatim.

Expansion procedure:

1. Parse the brief for distinct checks. A single brief may encode multiple criteria (e.g., "every gate must end with X AND every gate must have a delegation guard"). Do not collapse — emit one criterion per check.
1. For each criterion, fill in:
   - `id` — `c1`, `c2`, ... (stable across re-runs within the same task)
   - `check` — the condition that must be true **after** fix (positive framing)
   - `detect` — how to recognize a file that fails the check (regex, substring, structural cue). Concrete enough that haiku can apply it deterministically.
   - `fix` — how to rewrite when the check fails. Specify either an exact replacement template or a rule ("replace the trailing sentence with: `<literal>`").
   - `applies_to` — which file types this criterion applies to (`skill`, `phase`, `agent`, or `any`). Use this to avoid telling the proposer to apply skill-level checks to agent files and vice versa.
   - `reference` — optional: path to a guideline section (e.g., `guidelines/SKILL_GUIDELINES.md#1-approval-gates-must-loop`). Include this whenever the criterion comes from a written guideline; omit when the brief is freeform.
1. If the brief is vague (e.g., "make everything comply with the guidelines"), escalate via AskUserQuestion with concrete candidate criteria — never auto-expand a vague brief into an open-ended criteria list. The proposer cannot apply "comply" as a rule.

**Grounding rule**: When the brief cites a guideline (`SKILL_GUIDELINES.md`, `AGENTS_GUIDELINES.md`, `HOOKS_GUIDELINES.md`), Read the relevant section before writing the criterion. Quote the binding phrase verbatim in the `check` or `fix` field so the proposer is matching the authoritative text, not the orchestrator's paraphrase.

## 1.4 Write artifacts

### `criteria.md`

YAML, one criterion per list entry:

```yaml
task_brief: "<verbatim $ARGUMENTS>"
expansion_notes: |
  <one paragraph: how the orchestrator interpreted the brief,
   any ambiguities resolved, which guideline sections were consulted>
criteria:
  - id: c1
    check: "<positive post-fix condition>"
    detect: "<how to recognize a failing file>"
    fix: "<rewrite rule or template>"
    applies_to: skill|phase|agent|any
    reference: "<optional guideline path + anchor>"
  - id: c2
    ...
```

### `candidates.md`

Markdown table, one row per enumerated file:

```
| # | path | type | tag | rationale |
| - | ---- | ---- | --- | --------- |
| 1 | plugins/mz-knowledge/skills/vault-health/SKILL.md | skill | likely_relevant | "matches keyword 'gate'" |
| 2 | plugins/mz-knowledge/skills/vault-health/phases/collect.md | phase | unclear | "no keyword hit; kept as unclear" |
| 3 | plugins/mz-knowledge/agents/triage-scorer.md | agent | likely_skip | "brief targets skills only; agent flagged as skip" |
```

Append a summary line:

```
Summary: <N> total, <N> likely_relevant, <N> unclear, <N> likely_skip
Will dispatch in Phase 2: <N> (relevant + unclear)
```

### State update

Update `state.md`:

- `Phase: 1_complete`
- `raw_candidates: N`
- `dispatch_candidates: N` (relevant + unclear)
- `criteria_count: N`

Emit a one-line visible summary to the user before returning to the SKILL.md orchestrator for Gate 1:

```
Scan complete: <N> candidates, <N> criteria. Gate 1 incoming.
```
