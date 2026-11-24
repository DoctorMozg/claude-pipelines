# Branch Review Report Template

branch-reviewer reads this file before it writes the Phase 6 report. The template is binding: keep every section the body names as mandatory.

**Five-field rule** — every actionable finding in this report (every Critical / Nit / Optional / FYI; new or validated prior or blind spot; in any section: File-by-File Analysis, Findings Found, Validated Prior Concerns, Blind Spots, Codebase Consistency, Improvements, Missing Items, Test Quality Issues, Missing Test Cases) must carry all five of:

1. **Severity** — one of `Critical:`, `Nit:`, `Optional:`, `FYI:`. Always present, either as the section title prefix or as an explicit `Severity:` field.
1. **File** — `path:line_start[-line_end]`. Always present. For "Missing Items" or other forward-looking findings, give the *expected* path even when the file does not yet exist.
1. **TL;DR** — ≤140 characters, `<what's wrong> → <how to fix>` form. If it does not fit in 140 chars, the issue is too vague — sharpen it.
1. **Description** — 2–4 sentences explaining what is wrong (or missing) and why it matters. Quote the relevant code span when one exists.
1. **Suggested fix** — concrete repair steps. For Validated Prior Concerns whose `Status` is `ResolvedWithReply`, replace with `What was done`; for `ResolvedSilently`, replace with `Verification`; for `Outdated`, the field can be omitted.

The table-based "File-by-File Analysis" carries the same five fields as columns. Findings missing any of the five fields are invalid — repair them or drop them; never emit a partial row.

`````markdown
# Branch Review: <branch-name>

**Branch**: <branch> → <base>
**Date Reviewed**: <YYYY-MM-DD>
**Commits**: <N commits>
**Files Changed**: <N files>

## What Is Being Implemented

<3-6 sentences explaining what the branch implements, based on branch name, commits, and code analysis. Include domain context from research if applicable.>

## Domain Research Summary

> Only include if researcher was consulted.

<Key findings from domain research that are relevant to evaluating this implementation. Reference implementations, best practices, known pitfalls.>

## Overall Assessment

<One of: LOOKS GOOD | NEEDS WORK | SIGNIFICANT ISSUES>

<2-3 sentences summarizing the overall quality and readiness of the branch.>

## Verdict

VERDICT: PASS | FAIL

PASS when zero `Critical:` findings exist. FAIL when one or more `Critical:` findings exist.

## Statistics

- Commits: <N>
- Files changed: <N>
- Additions: <N>
- Deletions: <N>

## Lens Telemetry

- lenses_completed: <N>/6
- lenses_dropped: <N>
- wave_b_completed: <N>/3
- blind_audit: <full|partial|degraded|unavailable>
- findings_after_dedup: <N>
- contested: <N>
- critical_promoted: <N>
- critical_promoted_by_wave_b: <N>
- validated_prior: <N>
- new_findings: <N>
- blind_spots: <N>
- corroborated: <N>
- questions: <N>, sound: <N>, unclear: <N>, not_optimal: <N>, question_review: <full|unanswered|ungraded|unavailable>
- path: multi-lens | degraded-single-pass

## File-by-File Analysis

### `<path/to/file.ext>`

**Purpose of changes**: <1-2 sentences>

#### Issues

| # | Severity | Category | Line(s) | TL;DR | Description | Suggested Fix |
|---|----------|----------|---------|-------|-------------|---------------|
| 1 | Critical: | Bug/Architecture/Performance/... | L42-50 | <≤140 chars: what's wrong → how to fix> | <2–4 sentence description> | <Concrete repair steps> |

#### Code Snippets

Numbered to match the # column in the Issues table above.

````markdown
##### Finding 1 — `<file>:<line_start>`
```<lang>
<comment-marker> line <line_start>
<7 lines: from max(1, line_start - 3) through min(eof, line_end + 3)>
```

````

> Repeat for each changed file. Omit sections with no findings. Omit "Code Snippets" if the Issues table is empty. `Optional:` and `FYI:` items belong in the Issues table above (one row each, all five fields populated) — do not list them as a separate sub-bullet list.

## Validated Prior Concerns

> Concerns already raised by prior reviewers, bots, or past reports (from the Known Concerns Map). This run validated each still applies; it did not re-analyze deeply. Grouped by `Status` from the map. Omit empty subsections.

### Still Open

> `Status: Open` — previously reported, still unresolved on the current diff.

#### Critical: <Short issue title>
- **TL;DR**: <what's wrong> → <how to fix> (≤140 chars)
- **Status**: Open
- **File**: `<path/to/file.ext>:<line>`
- **Code**:
  ```<lang>
  <comment-marker> line <line>
  <7 lines of context around the still-open issue>
  ```
- **Category**: Bug | Security | Architecture | Performance | Maintainability
- **Description**: <2-4 concise sentences>
- **Suggested fix**: <Concrete repair steps; carry forward from the prior report when available>
- **Originally reported by**: @<reviewer> or <prior report filename>

### Addressed With Reply

> `Status: ResolvedWithReply` — thread resolved after a back-and-forth; fix was acknowledged in-thread.

#### Optional: <Short issue title>
- **TL;DR**: <what's wrong> → <how to fix> (≤140 chars)
- **Status**: ResolvedWithReply
- **File**: `<path/to/file.ext>:<line>`
- **Originally reported by**: @<reviewer> or <prior report filename>
- **What was done**: <Summary of the fix>

### Resolved Silently

> `Status: ResolvedSilently` — thread marked resolved but only the original comment exists. **Verify before trusting.**

#### FYI: <Short issue title>
- **TL;DR**: <what's wrong> → <how to fix> (≤140 chars)
- **Status**: ResolvedSilently
- **File**: `<path/to/file.ext>:<line>`
- **Originally reported by**: @<reviewer> or <prior report filename>
- **Verification**: <Commit or line-range that addressed the concern, or "unchanged — downgraded to Open" if the anchor code is unchanged>

### Outdated

> `Status: Outdated` — the thread's anchor line is no longer present in the diff. Kept for history only.

#### FYI: <Short issue title>
- **TL;DR**: <what's wrong> → <how to fix> (≤140 chars)
- **Status**: Outdated
- **File**: `<historical path>:<historical line>` (anchor no longer present in current diff)
- **Description**: <2–3 sentences summarizing the original concern, why the anchor is gone (file removed, refactored, code rewritten), and whether the underlying concern is still relevant elsewhere>
- **Originally reported by**: @<reviewer> or <prior report filename>
- **Note**: anchor lost from diff — Suggested fix omitted by design (no actionable line)

## Findings Found

> Consolidated list of **new** findings across files, sorted by severity. Findings already covered by any prior review are in "Validated Prior Concerns" above, not here.

### Critical: <Short title>

- **TL;DR**: <what's wrong> → <how to fix> (≤140 chars)
- **File**: `<path>:<line_start>-<line_end>`
- **Code**:
  ```<lang>
  <comment-marker> line <line_start>
  <7 lines: max(1, line_start-3) through min(eof, line_end+3)>
  ```
- **Description**: <What is wrong and why it matters>
- **Suggested fix**: <How to fix it>
- **Corroborated by**: <e.g. `blinded_security`, `blinded_ops`, `question_review`, or `none — Wave A only`> *(only render when `corroborated_by` is set; cite the Wave B role(s) that independently surfaced the issue)*
- **Source**: `question_review Q<n>` *(only render for a finding raised by question review; its description names the better alternative and the cost of the current choice)*
- **Critical promoted by Wave B**: <yes|no> *(only render `yes` when the two-signal Critical gate fired only after Wave B corroboration; omit otherwise)*

### Nit: <Short title>

- **TL;DR**: <what's wrong> → <how to fix> (≤140 chars)
- **File**: `<path>:<line_start>-<line_end>`
- **Code**:
  ```<lang>
  <comment-marker> line <line_start>
  <7 lines of context>
  ```
- **Description**: <What is wrong>
- **Suggested fix**: <How to fix it>

### Optional: <Short title>

- **TL;DR**: <what's wrong> → <how to fix> (≤140 chars)
- **File**: `<path>:<line_start>-<line_end>`
- **Code**:
  ```<lang>
  <comment-marker> line <line_start>
  <7 lines of context>
  ```
- **Description**: <Non-blocking improvement, 2–4 sentences>
- **Suggested fix**: <Concrete repair steps>

### FYI: <Short title>

- **TL;DR**: <what's wrong> → <how to fix> (≤140 chars)
- **File**: `<path>:<line_start>-<line_end>`
- **Code**:
  ```<lang>
  <comment-marker> line <line_start>
  <7 lines of context>
  ```
- **Description**: <Informational observation, 2–4 sentences>
- **Suggested fix**: <Concrete repair steps, or `n/a — informational only` if no action is recommended>

## Low Confidence

> Findings a lens scored below 60, copied from the `## Low confidence` section of `phase3_consolidated.md`. They never count toward the verdict. Write `None.` when there are none.

- FYI: (possible <severity>, <confidence>) <file>:<line_start> — <tldr>

## Blind Spots

> Findings surfaced only by the blinded adversarial wave (Wave B) — no Wave A lens flagged them. These represent gaps that context-aware analysis missed because of confirmation bias. Severity is capped per `blinded_lenses.md`: `Optional:` when a `file:line` is cited, `FYI:` when the blinded reviewer returned `line unknown`. Never `Critical:` here — by definition the two-signal gate cannot fire without Wave A corroboration. Omit this section if `blind_audit: unavailable` (label the omission in Lens Telemetry instead) or if Wave B produced zero unmatched findings.

#### 1. <Severity prefix — `Optional:` or `FYI:`> <Short title>
- **TL;DR**: <what's wrong> → <how to fix> (≤140 chars)
- **File**: `<path>:<line_start>-<line_end>` *(or `<path>:line unknown` when the blinded reviewer could not locate the anchor)*
- **Source**: `blinded_<production|security|ops>`
- **Code**:
  ```<lang>
  <comment-marker> line <line_start>
  <7 lines of context — omit this entire block when `line unknown`>
  ```
  *(If `line unknown`: replace the Code block with a single line: `(snippet unavailable — line not located by blinded reviewer)`)*
- **Description**: <2–4 sentences: what the blinded reviewer surfaced, why it matters, what failure mode or attack vector or operational concern it implies. Note explicitly that no Wave A lens caught it.>
- **Suggested fix**: <Concrete repair steps. Even with `line unknown`, propose a concrete direction — search target, file or function to inspect, validation to add.>

## Design Questions

> Question review from Phase 3.6, in the format of the "Report section" of `question_review.md`: the summary line `questions: N, sound: N, unclear: N, not_optimal: N, question_review: <value>`, then one `### Q<n>` block per question with its anchor, answer and source, grade, and the label and title of its finding in this report (or `none`). The findings themselves sit in Findings Found or on the Wave A row they matched. With `question_review: unanswered` or `ungraded`, list the questions (and answers) as `FYI:` and link no findings. With `unavailable`, keep the section with the summary line alone.

## Didn't Touch

> Files or areas intentionally omitted from this review — downstream readers use this to know the review's boundary.

- <path or area>: <reason (e.g., generated code, vendored, out of scope per dispatch prompt)>

## Codebase Consistency

> Deviations from established patterns, conventions, or idioms in the rest of the codebase.

#### 1. <Severity prefix — `Nit:` or `Optional:` typically; `Critical:` only when divergence breaks an established module boundary> <Inconsistency title>
- **TL;DR**: <what's wrong> → <how to fix> (≤140 chars)
- **File**: `<path>:<line>`
- **Description**: Codebase convention: <how the rest of the codebase does it, with example file/line reference>. This branch: <how the new code does it differently>. Why it matters: <impact on future contributors / consistency / review load>.
- **Suggested fix**: <Align with existing pattern / Keep as-is with explicit justification — be concrete about which file or helper to mirror>

## Architecture Review

<Assessment of overall architecture decisions. Are patterns consistent? Is coupling appropriate? Are there SOLID violations?>

### Proposed Changes

> Only include if there are meaningful architecture improvements to suggest.

#### 1. <Severity prefix — `Optional:` by default; `Critical:` only when current architecture blocks future change> <Change title>
- **TL;DR**: <what's wrong> → <how to fix> (≤140 chars)
- **File**: `<primary path>:<line>` (additional scope listed in Description)
- **Description**: Scope: <which files/components>. Current: <how it works now>. Proposed: <how it should work>. Rationale: <why this is better — concrete cost or risk>.
- **Suggested fix**: <Concrete migration steps — which file to extract, which protocol to introduce, how to roll out>

## Improvements

> Concrete suggestions for making the code better.

#### 1. <Severity prefix — `Optional:` by default; `Nit:` for very small wins; `FYI:` for forward-looking notes> <Improvement title>
- **TL;DR**: <what's wrong> → <how to fix> (≤140 chars)
- **File**: `<path>:<line>`
- **Description**: Current: <what it does now>. Why suboptimal: <2–3 sentences on the cost — readability, performance, robustness, future change>.
- **Suggested fix**: <What it should do — concrete steps, target API/helper/pattern>

## Missing Items

> Things that appear to be forgotten or incomplete.

#### 1. <Severity prefix — `Critical:` when the gap blocks correctness or integration; `Optional:` when the omission is non-blocking> <Missing item>
- **TL;DR**: <what's missing> → <where to add it> (≤140 chars)
- **File**: `<expected path>:<line>` (the path where the missing piece *should* live; mark `(new file)` if it does not yet exist)
- **Description**: <What is missing, what breaks or stays incomplete without it, and any cross-references to related code that already exists>
- **Suggested fix**: <Concrete steps — register here, export there, add the call site, write the matching helper, etc.>

## Test Coverage Analysis

### Overview

| Metric | Status |
|--------|--------|
| New functions with tests | <N/M> |
| Error paths tested | <Yes/Partial/No> |
| Edge cases tested | <Yes/Partial/No> |
| Integration tested | <Yes/Partial/No> |

### Missing Test Cases

#### 1. <Severity prefix — `Critical:` when an untested path is also a known-defect path; `Optional:` for normal coverage gaps> <Test case description>
- **TL;DR**: <what's untested> → <what test to add> (≤140 chars)
- **File**: `<existing or expected test file>:<line or `(new test)`>` — the test target is `<function/method name>` in `<source file>`.
- **Description**: <2–4 sentences: what scenario should be tested, why it matters, what could go wrong without it (regression, silent corruption, integration break)>
- **Suggested fix**: <Concrete test outline — fixture to reuse, inputs to drive, assertion to make>

### Test Quality Issues

> Only include if there are real problems with test quality.

#### 1. <Severity prefix — `Critical:` when the test masks a real defect; `Nit:` or `Optional:` for general weakness> <Issue>
- **TL;DR**: <what's wrong with the test> → <how to repair> (≤140 chars)
- **File**: `<test_file>:<line>`
- **Description**: <2–4 sentences: what is wrong with the test, why it fails to catch real regressions, whether it produces false confidence>
- **Suggested fix**: <Concrete repair — replace mock with real dependency, tighten assertion, split into independent cases, add the boundary input, etc.>

## Positive Aspects

<List things done well — good patterns, thorough implementation, clean code, good test coverage. Acknowledge good work.>
`````
