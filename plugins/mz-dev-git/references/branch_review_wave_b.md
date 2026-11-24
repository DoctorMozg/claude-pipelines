# Branch Review Wave B Procedure

branch-reviewer reads this file before Phase 3.6. It holds the dispatch, partial-completion and merge steps for the blind audit and question review; the invariants in the agent body stay binding.

## Phase 3.6 — Blind Audit (Wave B)

**Dispatch this phase as its own wave after Phase 3.5 returns.** Wave A already fills the six-agent wave cap, and a fork would inherit Wave A's findings along with the whole conversation, so Wave B uses typed agents: three `pipeline-researcher` agents with diff-only prompts and one `pipeline-design-questioner` in ask mode, four agents in all. Phase 3.6 is mandatory — there is no `--no-blind` flag and no opt-out.

### 3.6.1 Read the shared prompts

Read the single source of truth at `${CLAUDE_PLUGIN_ROOT}/shared/blinded_lenses.md`. For each role (`blinded_production`, `blinded_security`, `blinded_ops`), extract the literal text inside the fenced ```` ``` ```` block under that role's `###` header. The dispatch invariants in that file are binding: typed agents with diff-only prompts in their own wave after Wave A, raw diff only, model **opus**, agent `pipeline-researcher` (cross-plugin dispatch from `mz-base`).

Read `${CLAUDE_PLUGIN_ROOT}/shared/question_review.md` as well. Its dispatch invariants, the Step Q, A and G prompt blocks, the file contracts, the severity rule, the partial-completion values and the report section are binding, and you build every question-review prompt from its blocks rather than from memory. Use `<qr_dir>` = `$ARTIFACT_ROOT/.mz/task/<task_name>/question_review/`, created before dispatch, and `<repo root>` = `$CODE_ROOT`.

### 3.6.2 Capture the raw diff

```bash
git -C "$CODE_ROOT" diff <base_branch>...HEAD
```

The three-dot form diffs from the merge base, so commits that landed on the base after the branch forked stay out.

For the questioner, also collect the branch's task text: the PR title and body from a `PR metadata` block, a `Unit spec:` block, or the dispatch prompt's own account of what the branch implements. Leave out commit messages and your Phase 2 summary; they are the author's explanations, and the answerer reads git history itself. With none of those, omit the task block from the Step Q prompt.

### 3.6.3 Dispatch the three blinded researchers and the questioner

In a SINGLE new assistant message, dispatch all three `pipeline-researcher` agents and the `pipeline-design-questioner` in parallel tool-use blocks. For each role, the agent's prompt is the role's extracted block from `blinded_lenses.md` with the literal placeholder `<raw diff output>` replaced by the captured diff (still wrapped inside the existing `<untrusted-content>...</untrusted-content>` envelope from the prompt template). The questioner's prompt is the Step Q block from `question_review.md`, filled with the same diff, the task text from 3.6.2 and the `<qr_dir>` paths. Do not add scope, the Known Concerns Map, Wave A findings, or any consolidated artifact to any of the four — those would defeat the blind.

Emit the pre-dispatch manifest right before the `Agent` calls, and pass each role label as the call's `description`:

```
Dispatching Wave B blind audit — 4 agents in parallel
Purpose: diff-only adversarial audit and design questions on the same branch
- pipeline-researcher — blinded production review
- pipeline-researcher — blinded security review
- pipeline-researcher — blinded ops review
- pipeline-design-questioner — design questions (ask)
```

After Wave B returns, write each researcher's response to:

| Researcher           | Artifact                                                           |
| -------------------- | ------------------------------------------------------------------ |
| `blinded_production` | `$ARTIFACT_ROOT/.mz/task/<task_name>/phase3_blinded_production.md` |
| `blinded_security`   | `$ARTIFACT_ROOT/.mz/task/<task_name>/phase3_blinded_security.md`   |
| `blinded_ops`        | `$ARTIFACT_ROOT/.mz/task/<task_name>/phase3_blinded_ops.md`        |

The questioner writes `questions.md` and `rubric.md` to `<qr_dir>` itself. Check that `questions.md` exists on disk before Step A.

### 3.6.4 Wave B partial-completion contract

Once all four agents have reported, failed or been stopped, emit the post-wave rollup before 3.6.5:

```
Wave complete (Wave B blind audit) — <returned>/4 agents returned
- pipeline-researcher (blinded_production): <STATUS> — <summary, ≤8 words>
- pipeline-researcher (blinded_security): <STATUS> — <summary, ≤8 words>
- pipeline-researcher (blinded_ops): <STATUS> — <summary, ≤8 words>
- pipeline-design-questioner (ask): <STATUS> — <N questions, ≤8 words>
```

An agent that returns no valid final `STATUS:` line is listed as `NO RETURN BLOCK` and counted as not returned. The thresholds below count the three researchers only; the questioner's outcome sets `question_review` in 3.6.5.

- 3 of 3 returned → proceed to Phase 3.7 with `wave_b_completed: 3/3`, `blind_audit: full`.
- 2 of 3 returned → proceed with `wave_b_completed: 2/3`, `blind_audit: partial`.
- 1 of 3 returned → proceed with `wave_b_completed: 1/3`, `blind_audit: degraded`.
- 0 of 3 returned → emit `wave_b_completed: 0/3`, `blind_audit: unavailable`. Skip 3.7.1–3.7.4 and run the rest of Phase 3.7. Wave A's interim verdict stands, apart from question-review findings.

Wave B never blocks the report. It is additive — it can promote findings, surface blind spots, and corroborate Wave A signals; it cannot override Wave A or hide a Wave A `Critical:` already promoted by the two-signal gate.

### 3.6.5 Question review: answer and grade

Run the rest of question review as `question_review.md` lays it out, one agent at a time.

1. **Outcome of the ask step.** A questioner that failed, or left no `questions.md` on disk, sets `question_review: unavailable`; skip the rest of 3.6.5. A `questions.md` that says `No questions.` sets `question_review: full` with `questions: 0`; skip the rest as well.
1. **Step A.** Dispatch `pipeline-design-answerer` (registered by mz-base, so any plugin prefix is `mz-base:`) with the Step A block, filled with the same diff and the `<qr_dir>` paths. Your task folder is `<task dir>`: keep the decisions line when `$ARTIFACT_ROOT/.mz/task/<task_name>/decisions.md` exists and the notes line when `implementation.md` exists there. When that `decisions.md` doesn't exist, apply "Finding the coder notes" in `question_review.md` with the reviewed branch from `branch_info.md` and the merge-base of `<base_branch>` and HEAD, running git as `git -C "$CODE_ROOT"`, and add a decisions line and a notes line per match. Leave out each line whose file doesn't exist. A branch made by a person has none; the answerer then works from the code, the history and the docs. Pass no rubric, grades or findings.
1. **Step G.** Once `answers.md` exists on disk, dispatch `pipeline-design-questioner` again with the Step G block. It is a fresh typed dispatch, not a resume and not a fork.

Emit a manifest before each dispatch and a rollup after it, passing the role label as the call's `description`:

```
Dispatching question review (answer) — 1 agent
Purpose: answer the design questions from the code, history and notes
- pipeline-design-answerer — design answers

Step complete (question review answer) — <returned>/1 agents returned
- pipeline-design-answerer: <STATUS> — <summary, ≤8 words>
```

```
Dispatching question review (grade) — 1 agent
Purpose: grade each answer against the private rubric
- pipeline-design-questioner — design grades (grade)

Step complete (question review grade) — <returned>/1 agents returned
- pipeline-design-questioner (grade): <STATUS> — <sound/unclear/not optimal counts>
```

A failed answerer sets `question_review: unanswered` and a failed grader `question_review: ungraded`, as the shared file's "Partial completion" defines failure; in both cases the questions go to the report as `FYI:` and raise no findings. Otherwise `question_review: full`. Question review never blocks the report.

## Phase 3.7 — Blinded Cross-Reference

For each Wave B finding across the 3 researcher artifacts, attempt to match it against the consolidated Wave A finding set in `phase3_consolidated.md`. Question-review findings merge separately, in 3.7.5.

### 3.7.1 Match criteria

Match a Wave B finding to a Wave A finding when any of:

- **Exact**: same `file` AND `line_start == line_start` (or overlap on `[line_start, line_end]`).
- **Overlap**: same `file` AND ranges overlap.
- **Behavioral**: same `file` AND the Wave B description names the same behavior or mechanism the Wave A finding describes (judgment-based; record `match_basis: behavioral`).

Record on each matched Wave B finding: `match_basis: <exact | overlap | behavioral>`.

### 3.7.2 Apply role-corroboration map (read from `blinded_lenses.md`)

The shared reference's "Role-to-Lens Corroboration Mapping" table is authoritative. For branch-reviewer's lens set, the binding rows are:

- `blinded_production` corroborates: `bugs`
- `blinded_security` corroborates: `security`
- `blinded_ops` corroborates: `performance`, `bugs`

For each Wave B finding that matched a Wave A finding:

1. Append `corroborated_by: blinded_<role>` to the Wave A row (or extend the list if multiple Wave B roles match).
1. If the matched Wave A finding's `category` is in the role's corroborating list above → increment `replication_count` by 1 (Wave B counts as one distinct corroborator) and set `tier_boosted: true`. A finding matched by multiple in-list Wave B roles still increments `replication_count` only ONCE total — record all corroborators in the list, but boost the count once.
1. If the matched Wave A finding's `category` is not in the corroborating list → merge `corroborated_by` only; do not increment `replication_count`. The cross-category match is still informative for the report but does not satisfy the two-signal gate.

### 3.7.3 Re-evaluate Critical eligibility

For every consolidated finding (Wave A or merged) whose `replication_count` increased in 3.7.2, re-apply the two-signal Critical gate from Phase 3.5:

- `confidence >= 80` AND `replication_count >= 2` → promote to `severity: Critical:` (record `critical_promoted_by_wave_b: true` if the promotion required the Wave B corroboration to clear the gate).
- Otherwise: severity stays at the cap from 3.5 (`Nit:` or `Optional:`).

Findings that were already `Critical:` in 3.5 keep that severity — Wave B can only promote upward, never downgrade.

### 3.7.4 Promote unmatched Wave B findings to Blind Spots

Wave B findings with no Wave A match are blind spots — gaps that context-aware analysis missed. Add each as a new row to `phase3_consolidated.md` with:

- `source: blinded_<role>`, `match_basis: none`, `replication_count: 1`
- Severity per the rules in `blinded_lenses.md` "Unmatched Wave B Findings" section: `Optional:` if a `file:line` is cited, `FYI:` if `line unknown`. Never `Critical:` (no independent Wave A signal — by definition the two-signal gate cannot fire).
- All five required fields (severity, file/expected location, TL;DR, description, suggested fix). When the blinded researcher returned `line unknown`, use the changed-file path with `:line unknown` as the file ref and surface the missing-anchor caveat in the description.

### 3.7.5 Merge question-review findings

Run this step when `question_review: full`. Read `<qr_dir>/grades.md` and take each `### Finding` block, one per question graded `unclear` or `not optimal`, and apply the severity rule from `question_review.md`:

- **Not optimal** with all three of a better alternative, a concrete cost and a `file:line` anchored on a changed line → `Critical:` on its own. This source alone is exempt from the two-signal gate. Open the alternative's `file:line` under `$CODE_ROOT` first; when it doesn't hold what the grader says, cap the finding at `Optional:`.
- **Not optimal** missing any of the three → `Optional:` at most.
- **Unclear** → `Optional:` at most; missing rationale is not a defect by itself, so a person's branch with no notes is never failed for it alone.
- A finding anchored outside the changed lines questions a choice that predates the branch → `FYI:`.

Then match each finding against `phase3_consolidated.md` with the 3.7.1 criteria. A match is reported once, as the Wave A row: append `corroborated_by: question_review`, keep the higher of the two severities, and leave `replication_count` as it is. An unmatched finding becomes a new row with `source: question_review`, `match_basis: none`, `replication_count: 1`, its `Q<n>` ID, and the grader's better alternative and cost carried into the description. Every row keeps all five required fields.

### 3.7.6 Update consolidated artifact

Rewrite `phase3_consolidated.md` to include the new columns: `corroborated_by`, `tier_boosted`, `match_basis`, `source`, `critical_promoted_by_wave_b`. Append the Blind Spots rows after the merged Wave A rows, then the unmatched question-review rows. Code Snippets section gains entries for any Blind Spot whose `file:line` is known; for `line unknown` Blind Spots, omit the snippet and note `(snippet unavailable — line not located by blinded reviewer)` in the row.

### 3.7.7 Emit extended consolidation summary

Add to the Phase 3.5 summary line: `wave_b_completed: N/3`, `blind_audit: <full|partial|degraded|unavailable>`, `blind_spots: N`, `corroborated: N`, `critical_promoted_by_wave_b: N`, and the question-review line `questions: N, sound: N, unclear: N, not_optimal: N, question_review: <full|unanswered|ungraded|unavailable>`.
