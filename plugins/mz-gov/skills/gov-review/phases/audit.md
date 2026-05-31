# Phase 1 — Audit

Resolve the artifact set, fan `gov-audit-reviewer` out across it in bounded parallel waves, collect each artifact's verdict, and write one review report. Read-only throughout — no artifact is edited.

## Contents

- [1.1 Resolve the artifact set](#11-resolve-the-artifact-set)
- [1.2 Batch into waves](#12-batch-into-waves)
- [1.3 Dispatch each wave](#13-dispatch-each-wave)
- [1.4 Collect verdicts](#14-collect-verdicts)
- [1.5 Write the report](#15-write-the-report)
- [1.6 Report to the user](#16-report-to-the-user)

______________________________________________________________________

## 1.1 Resolve the artifact set

Turn the Phase 0 artifact source into a concrete file list.

- **A path/glob/dir was parsed in Phase 0** → expand it with Glob (or list the directory). A single file resolves to a one-element list.
- **No path/glob token** → glob the default set from the SKILL constant **ARTIFACT_DIRS**: `docs/decisions/*.md`, `docs/rfcs/*.md`, `docs/design/*.md`. Union the matches.

Drop obvious non-artifacts from the list so reviewers are not dispatched against scaffolding: a `README.md`, `index.md`, `template*.md`, or a `0000-template.md` sitting in an artifact directory is not a decision record. Keep everything else.

**Zero artifacts found** (the glob matched nothing, or only filtered-out files remained): stop here. Emit to the user:

```
No governance artifacts found at <resolved source>.
Checked: <the globs or path that were tried>.
Nothing to review — the directories may be empty, or the path/glob may be too narrow.
```

Update `state.md` (`Status: complete`, `phase_complete: true`, `what_remains: []`, note `artifacts_found: 0`) and return. Do **not** fabricate artifacts or findings.

Record the resolved count in `state.md` as `artifacts_found: <N>` before dispatching.

## 1.2 Batch into waves

`gov-audit-reviewer` reviews **exactly one artifact per dispatch**. Split the file list into waves of at most **MAX_REVIEWERS** (6) agents:

- `N ≤ 6` → one wave.
- `N > 6` → `ceil(N / 6)` sequential waves; each wave runs its agents in parallel, and the next wave launches only after the current one has fully returned.

Number the waves `1..K` so the per-wave manifest and rollup can be told apart.

## 1.3 Dispatch each wave

For **every** wave (including a lone wave of one or more), follow this loop. The manifest and rollup are required whenever a wave carries two or more agents; for a single-artifact run (one agent total) the manifest/rollup may be collapsed to a one-line "Reviewing `<path>`" note.

**Pre-dispatch manifest** — emit immediately before launching the wave:

```
Dispatching gov-audit review — wave <w>/<K>, <n> agents in parallel
Purpose: score each artifact against the 6-axis governance rubric
- gov-audit-reviewer — <artifact filename>
- gov-audit-reviewer — <artifact filename>
...
```

Use the artifact's filename (not its absolute path) as the role label — paths must not appear in the manifest.

**Launch the wave**: in a **single message**, issue one `Agent(gov-audit-reviewer)` call per artifact in the wave (parallel tool calls). Each dispatch prompt carries only task-specific context — the agent already owns its process, rubric-loading discipline, severity rules, and output format:

```
Audit this governance artifact against the six-axis review rubric.

Artifact:      <absolute path to the one artifact>
Rubric:        skills/gov-review/references/review-rubric.md
Status vocab:  skills/govern/references/status-vocabularies.md  (for Axis 6 status validity)

Read the rubric in full, score all six axes against the artifact's own text, and return your per-axis table, severity-labeled findings, the VERDICT: line, and STATUS:. Keep findings concrete and self-contained — they are collected into an aggregate report. Be concise.
```

One artifact path per dispatch — never hand a reviewer a directory or more than one file.

**Post-wave rollup** — emit once every agent in the wave has returned, before launching the next wave:

```
Wave <w>/<K> complete — <returned>/<dispatched> agents returned
- <artifact filename>: <VERDICT or STATUS> — <≤8-word summary of the worst finding>
```

The `<returned>/<dispatched>` ratio is exact. A reviewer that returns no `VERDICT:` / `STATUS:` line is listed as `<artifact filename>: NO RETURN BLOCK` and counts as **not returned** — never silently dropped from the count.

**Empty / failed dispatch**: if a reviewer returns nothing usable, no `VERDICT:`, `BLOCKED`, or `NEEDS_CONTEXT`, retry that single dispatch **once**. If the retry also fails, mark that artifact `unscored` (with the reason) and move on — one bad reviewer does not sink the wave.

## 1.4 Collect verdicts

From each reviewer's response capture, per artifact:

- the `VERDICT:` line (`PASS` | `FAIL`) — an `unscored` artifact has no verdict and is tallied separately, never as a pass;
- the `Critical:`-labeled findings (these are what drive a `FAIL` and what the report's "top Critical findings" column shows);
- the terminal `STATUS:` line.

Compute the aggregate: `N` artifacts reviewed, `M` failing (one or more `Critical:`), plus the count of any `unscored` artifacts. `M` counts only artifacts that returned a `FAIL` verdict; `unscored` artifacts are reported on their own line and excluded from both the pass and fail tallies.

Do **not** re-derive or second-guess a reviewer's verdict — the rubric's rule is mechanical (`PASS` iff zero `Critical:`), and the reviewer already applied it. The orchestrator aggregates; it does not re-judge.

## 1.5 Write the report

Write the report to **REPORT_DIR** using the leading-date convention: `.mz/reviews/<YYYY_MM_DD>_gov_review_<slug>.md`, where `<YYYY_MM_DD>` is today's date with underscores and `<slug>` matches the task-name slug. On same-day collision append `_v2`, `_v3`.

Use this structure:

```markdown
# Governance Artifact Review — <YYYY-MM-DD>

## Aggregate
- Artifacts reviewed: <N>
- Passing: <N − M − unscored>
- Failing (≥1 Critical): <M>
- Unscored (reviewer error): <U>
- Source: <the path/glob or "default ARTIFACT_DIRS">
- Rubric: in-house 6-axis governance heuristic (not an industry standard)

## Per-Artifact

| Artifact | Verdict | Top Critical findings |
| --- | --- | --- |
| docs/decisions/0003-session-store.md | FAIL | Axis 1: zero alternatives on an ambiguous decision; Axis 6: human_signoff is `pending` |
| docs/decisions/0004-log-format.md | PASS | — |
| docs/rfcs/0002-api-versioning.md | FAIL | Axis 3: irreversible URL-versioning choice not classified |
| docs/design/0001-ingest.md | unscored | reviewer returned NEEDS_CONTEXT (status vocabulary unreadable) |

## Failing Artifacts — detail

### docs/decisions/0003-session-store.md — FAIL
- **Axis 1 (alternatives)** — `Critical:` <one-line finding, quoting the artifact>
- **Axis 6 (status/provenance)** — `Critical:` <one-line finding>
- Advisory: <any Nit:/Optional:/FYI: worth surfacing, condensed>

### docs/rfcs/0002-api-versioning.md — FAIL
- ...

## Passing Artifacts
- docs/decisions/0004-log-format.md — clean across all six axes (advisory notes, if any: …)

## Unscored
- docs/design/0001-ingest.md — <reviewer status + reason; what input was missing>
```

Keep each finding to one or two sentences and quote or cite the artifact's own text where the reviewer did. The per-artifact table is the at-a-glance surface; the "Failing Artifacts — detail" section carries the Critical findings in full. Passing artifacts need only a one-liner; do not pad them.

Append the report path to `state.md` (`FilesWritten`), set `Status: complete`, `phase_complete: true`, `what_remains: []`, and record `artifacts_reviewed: <N>`, `artifacts_failing: <M>`.

## 1.6 Report to the user

Do **not** dump the full report into chat. Emit a compact closing block and point at the file:

```
Governance review complete — <N> artifacts reviewed, <M> failing, <U> unscored.
Report: .mz/reviews/<YYYY_MM_DD>_gov_review_<slug>.md

Failing:
- docs/decisions/0003-session-store.md — Axis 1 (no alternatives), Axis 6 (signoff pending)
- docs/rfcs/0002-api-versioning.md — Axis 3 (irreversible, unclassified)
```

If `M > 0`, list the failing artifacts with their axis tags (as above) so the worst problems are visible without opening the file. If `M = 0` and `U = 0`, say so plainly ("all <N> artifacts passed"). If any artifact is `unscored`, name it and its reason — an unscored artifact is an open question, not a silent pass. Recommend the next step where useful ("re-decide a failing record with `/govern`, or fix the artifact by hand") — recommend, never auto-invoke.
