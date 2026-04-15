# Phase 1-4: Analysis Backbone

Detail for the four sub-phases that produce the evidence dossier the persona
agent will read. This file is loaded via progressive disclosure from SKILL.md
at the start of Phase 1 (`Read phases/analyze.md`). Do not pre-load.

All four sub-phases run sequentially in the orchestrator. No approval gate
fires between them — the user already approved the resolved target at Phase
0.5 in SKILL.md. Re-gating would burn user patience without value.

Referenced constants (defined in SKILL.md `## Constants`): `TASK_DIR`,
`RESEARCH_CACHE_DIR`, `MAX_FINDINGS`, `DOSSIER_SEVERITY_LABELS`.

______________________________________________________________________

## Phase 1 preamble — target resolution detail

This is a continuation of the Phase 0.5 target-resolution gate in SKILL.md,
not a new gate. The orchestrator reached this file because the user already
approved a resolved target. This preamble documents the exact resolution
ladder used to produce that target list, so the ladder is reproducible if
the user rejects a resolution and asks for a re-run with feedback.

Apply the ladder in order. Stop at the first branch that produces a non-empty
result. Emit both `resolved_target_kind` and `resolved_target_list` into
`TASK_DIR<task_name>/state.md` before proceeding to Phase 2.

1. **Path-like tokens**. Tokenize the free-form remainder on whitespace. For
   each token, treat it as path-like if it contains `/` or ends in a common
   source extension (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, `.rs`,
   `.java`, `.cpp`, `.c`, `.h`, `.md`, `.json`, `.yaml`, `.toml`). Test each
   with `Glob` (for wildcards) or `Read` (for exact paths). Collect existing
   matches. If at least one matches, set `resolved_target_kind = files` (or
   `dirs` if all matches are directories) and use the matched list.
1. **Branch diff**. If the remainder contains the literal token `--diff <branch>` OR the prefix `branch:<name>`, run `git diff <branch>...HEAD --stat` via Bash and parse the changed file list. Set
   `resolved_target_kind = diff` and use the changed files as the list.
1. **Raw text / stdin**. If the remainder contains `--stdin` OR is wrapped in
   matching quotes (`"..."` or `'...'`), treat the unwrapped content as a raw
   text blob (do NOT look it up on disk). Set `resolved_target_kind = raw_text` and use the blob as `resolved_target_list` (one entry).
1. **Natural language**. Otherwise the remainder is a natural-language
   description like "the auth module". Tokenize on whitespace, lowercase,
   strip English stopwords (a, an, the, of, in, on, at, to, for, with, and,
   or). For each remaining content word, run `Glob` for files whose stem
   matches, then `Grep` for symbol references matching the same word inside
   files. Rank candidates by combined match frequency. Keep the top 5. Set
   `resolved_target_kind = candidates` and use that list.
1. **State emission**. Append to `TASK_DIR<task_name>/state.md`:
   - `resolved_target_kind: <one of: files, dirs, diff, raw_text, candidates>`
   - `resolved_target_list: <newline-indented list of paths or single blob>`
   - `target_ladder_branch: <1-5>` — which rung of the ladder produced the hit

If every rung returns empty and there is no raw text to fall back on, the
orchestrator must emit `STATUS: BLOCKED` and surface the failure to the user
via AskUserQuestion — never guess a target.

______________________________________________________________________

## Phase 2: Static structural / smell analysis

Read-only analysis of the resolved target list. No linters, no type-checkers,
no shell-based analyzers. The user excluded tooling-dependent checks in the
locked requirements — all structural signal must come from `Read`, `Grep`,
and `Glob`.

### Source hierarchy — static analysis tier

Declare the source ladder for this phase before recording any finding. Static
analysis is grounded in the project itself, not external references:

1. **Tier 1**: the file under analysis itself — its text is the canonical
   source of truth for what the code does.
1. **Tier 2**: sibling files in the same package/directory — imports,
   re-exports, and symbol co-occurrence establish how the file is used.
1. **Tier 3**: the top-level `README.md` — documents the project's stated
   shape and can be compared against what the code actually does.
1. **Tier 4**: `docs/` directory if present — only when top-level README is
   silent on the claim being checked.
1. **Tier 5**: language-level official specifications (e.g. PEP docs for
   Python) — only for resolving ambiguous idioms, never for recording
   findings in this phase (Phase 4 owns external references).

**Banned in Phase 2**: Stack Overflow, AI-generated summaries (including
other LLMs' output), undated blog posts, forum threads, linter output
(excluded by user requirements), and any external web source (Phase 4 owns
that).

### Author-attack prohibition (hard rule)

Do NOT run git blame, git log --author, or any command that maps code to
real people. Do NOT include author names, emails, or commit attributions in
the dossier. Author data is prohibited input.

This rule is structural, not advisory. Author data must never enter the
dossier in the first place, so persona agents downstream never see it and
cannot leak it into the roast. If the target file contains an author's name
in a comment header or docstring, strip it before recording any evidence
quote — the quote may appear in the dossier, the name may not.

### Structural signals to record

For each file in the resolved list (or each file chunk if `target_kind = raw_text`), measure and record these signals. Every measurement is sourced
by `Read` and counted by inspection — no tool invocations beyond `Read`,
`Grep`, `Glob`.

- **Total LOC**: whole file line count.
- **Longest function LOC**: scan function boundaries (language-appropriate
  syntax: `def`, `function`, `fn`, `func`, `class` + method body); record
  the highest body line count and its file:line start.
- **Function count**: total number of top-level functions and methods.
- **Max parameter count**: highest parameter count on any function; record
  the function name and file:line.
- **Max nesting depth**: deepest indentation level of control flow inside
  any function body.
- **Dead code**: unreachable blocks after `return`/`raise`/`throw`; unused
  exports (symbols exported but with zero hits from `Grep` across sibling
  files); commented-out code blocks larger than 3 lines.
- **Naming smells**: single-letter arguments in public API surfaces;
  Hungarian-notation prefixes (`strX`, `iX`, `bX`); type-in-name
  duplication (`user_user`, `dataData`); non-English identifiers in a
  project whose other files are English (soft flag).

For each signal that crosses a severity threshold, capture file:line
coordinates and a 1-3 line code excerpt. The excerpt is the evidence the
persona agent will cite — if the excerpt is missing, the finding is not
roastable and must be dropped.

### Severity thresholds (defaults)

- `Critical`: function >100 LOC, nesting >5 deep, function with >6
  parameters, duplicated block >20 lines, dead export referenced zero times
  from the package's own entry points.
- `Nit`: function 50-100 LOC, nesting 4, parameters 5-6, single-letter
  argument in public API, commented-out code block.
- `Optional`: naming smells, non-idiomatic idioms, missing type hints where
  sibling files have them.
- `FYI`: stylistic inconsistencies with sibling files that are not wrong.

Record every signal that crosses a threshold into a running candidate list
keyed by file:line. This candidate list feeds Phase 4b.

______________________________________________________________________

## Phase 3: Docs coherence analysis

Compare documented behavior to actual behavior. Docs are one of the three
prongs of the analysis backbone (structure, docs, web best-practice) per the
locked requirements — a README that lies to the user is as roastable as a
200-line function.

### Inputs

- The top-level `README.md` at repo root.
- Any `README.md` inside the resolved target directory or its ancestors.
- The `docs/` directory if present.
- Module-level docstrings and leading comment blocks on public symbols in
  the resolved target files.

### Procedure

1. Read each input. Extract claimed behaviors: bullet points in feature
   lists, code examples, usage instructions, parameter descriptions,
   "supported" / "returns" / "raises" statements.
1. For each claim, locate the referenced code via `Grep` for the symbol or
   quoted example. Record the search query and the hits.
1. Compare the claim to the located code and assign `coherence_status`:
   - `confirmed` — code matches the claim exactly. No finding.
   - `contradicted` — code does the opposite or a materially different
     thing. Record as `Critical` finding.
   - `missing` — the claim references a symbol that does not exist (or no
     longer exists) in the code. Record as `Critical` or `Nit` depending on
     whether the claim is in user-facing docs vs internal docstring.
   - `ambiguous` — the claim is vague enough that it could match multiple
     behaviors. Record as `Optional` finding so the persona can roast the
     ambiguity itself.
1. Every docs finding must carry the claim quote (from the docs source) and
   the counter-evidence (from the code), each with file:line coordinates.
   The dossier entry uses both as evidence.

Author-attack prohibition from Phase 2 applies here too — if the docs
contain an author byline, the byline never enters the dossier.

______________________________________________________________________

## Phase 4: Web best-practice delta research

Stack-aware one-shot research pass. The goal is to surface findings where
the target code diverges from the current official best practice for its
detected stack. One web pass per invocation, cached across invocations so
repeated roasts of the same repo pay the cost once per week.

### Source hierarchy — web research tier

Declare and enforce the source priority ladder before issuing any
`WebSearch` query. Every finding produced by this phase must trace to a
source at one of these tiers or be emitted as `UNVERIFIED:` and downgraded.

1. **Tier 1**: Official docs (vendor-hosted, versioned). Python.org,
   nodejs.org, react.dev, golang.org, rust-lang.org, official framework
   docs.
1. **Tier 2**: Official vendor blog (vendor-hosted, dated). Release notes,
   migration guides, deprecation announcements.
1. **Tier 3**: Standards-body and curated references. MDN, web.dev,
   caniuse, WHATWG, W3C, PEPs, TC39 proposals.
1. **Tier 4**: Vendor-maintained GitHub wiki. The project's own wiki on the
   vendor's repo.
1. **Tier 5**: Peer-reviewed papers. Only for claims that require academic
   backing (security, complexity bounds, algorithmic correctness).

**Banned sources (hard ban)**: Stack Overflow, AI-generated summaries
(including other LLMs' output), undated blog posts, forum threads, Medium
posts without vendor affiliation, content farms, dev.to posts without
vendor affiliation.

If a query returns only banned sources, record the claim as `UNVERIFIED: <claim> — could not confirm against official source` and do not emit it as
a finding without that token attached.

### Procedure

1. **Stack detection**. Look for manifest files at repo root and inside the
   target directory: `package.json`, `pyproject.toml`, `Cargo.toml`,
   `go.mod`, `Pipfile`, `requirements.txt`, `Gemfile`, `pom.xml`,
   `build.gradle`. For each found, extract primary language, framework, and
   version. Emit the disclosure token:
   `STACK DETECTED: <language>:<version>, <framework>:<version>` (one
   entry per stack component).
1. **Cache check**. Compute `hash = sha256(stack_fingerprint)` where the
   fingerprint is a sorted comma-joined list of `<name>:<version>` pairs.
   Check `RESEARCH_CACHE_DIR/stack_<hash>.md`:
   - If the file exists and its mtime is within 7 days, read it and skip
     the live research pass.
   - If it exists but is older than 7 days, delete (or overwrite) and
     run fresh research.
   - If it does not exist, run fresh research.
1. **Live research (2-4 queries)**. Issue 2-4 `WebSearch` queries targeting
   the detected stack. Example query shape: `<framework> <version> best practice <specific pattern observed in target code>`. Every query must
   be scoped to the stack and the tier 1-5 ladder — never generic
   "javascript best practices 2024" style queries.
1. **Source validation**. For each candidate source returned by a search,
   check the domain against the tier ladder. Use `WebFetch` only on tier 1-5
   domains. If no tier 1-5 source confirms a claim, skip the claim or emit
   it as `UNVERIFIED:`.
1. **Conflict handling**. If two tier 1-5 sources disagree, emit
   `CONFLICT DETECTED: <source A> says X, <source B> says Y` and prefer
   the higher tier or the more recent vendor-dated source. Never silently
   pick one.
1. **Cache write**. Write the research result to
   `RESEARCH_CACHE_DIR/stack_<hash>.md` with this frontmatter:
   ```markdown
   ---
   stack: <fingerprint>
   version: <primary version>
   cached: <ISO8601 timestamp>
   ---
   ```
   Body contains one section per query: query text, source URL, tier,
   extracted best-practice summary, applicable file:line in the target.
1. **Delta comparison**. For each best practice extracted, `Grep` the
   target files for the pattern. Record a delta finding when the target
   code diverges. Severity rule: `Nit` or `Optional` by default; `Critical`
   only for anti-patterns with concrete bug or security potential
   (SQL injection, unvalidated deserialization, known-bad crypto primitive,
   deprecated API with CVE).

Every Phase 4 finding must carry the source URL, the tier number, and the
target file:line evidence. If any of those three fields is missing, drop
the finding.

______________________________________________________________________

## Phase 4b: Dossier writer

This phase consolidates the candidate findings from Phase 2, Phase 3, and
Phase 4 into the single artifact the persona agent will read. The dossier
schema below is THE contract between analysis and persona rendering.
Persona agents cite findings by `(Finding N)` inline. Any deviation from
the schema header format breaks the pipeline — treat the header shape as
immutable.

### Canonical dossier schema

Write the dossier to `TASK_DIR<task_name>/dossier.md` with this exact
structure:

```markdown
# Roast Dossier — <task_name>

**Target**: <resolved_target_list, one line>
**Persona**: <chosen persona, lowercase>
**Stack detected**: <stack fingerprint from Phase 4>
**Analyzed**: <ISO8601 timestamp>

## Finding 1 — <severity> — <file>:<line> — <short description>
**Category**: structure | docs | best-practice
**Evidence**: <1-3 sentences with concrete numbers, quotes, or diff excerpt>
**Why it's roastable**: <1 sentence: the angle the persona can attack>

## Finding 2 — <severity> — <file>:<line> — <short description>
...
```

### Header format is the contract

The `## Finding N — <severity> — <file>:<line> — <description>` header is
referenced by persona agents as `(Finding N)` inline citations. Constraints:

- The marker must be exactly `## Finding N` with a single space between
  `Finding` and the integer. No `##Finding`, no `## Finding:`, no
  `## Finding-1`.
- `N` starts at 1 and increments by 1 with no gaps.
- `<severity>` is drawn from `DOSSIER_SEVERITY_LABELS` and must be one of
  `Critical`, `Nit`, `Optional`, `FYI`. No other labels ever.
  Never `Warning`, `Info`, `Minor`, `Major` — the persona agents match on
  the four canonical labels only.
- `<file>:<line>` must be the single most salient coordinate for the
  finding (the start of the offending function, the claim in the README,
  the diverging call site). For `raw_text` targets, use
  `raw_text:<line_in_blob>`.
- `<short description>` is at most 12 words, no trailing period.

### Body block is the evidence

Every finding must have all three body fields:

- **Category** — one of `structure`, `docs`, `best-practice`. These map to
  the three analysis phases (Phase 2, Phase 3, Phase 4 respectively).
- **Evidence** — concrete, quoted, and traceable. A line count, a
  parameter count, a quoted docs claim alongside the code that contradicts
  it, a URL with the tier number. No vague summaries — "this function is
  too long" is not evidence, "function `handle_request` is 142 LOC at
  `api/handlers.py:47`" is.
- **Why it's roastable** — one sentence describing the angle the persona
  can attack. This is the only field where voice hints are allowed, and
  even here the hint is structural ("the param count is absurd", "the
  docs promise X and the code ships Y"), not persona-specific.

If any field is missing or empty, drop the finding before writing the
dossier. A half-formed finding is worse than no finding because it invites
fabrication at the persona layer.

### Ordering and cap

- Order findings by severity: all `Critical` first, then `Nit`, then
  `Optional`, then `FYI`. Within a severity tier, order by file:line
  ascending for stability.
- Hard cap at `MAX_FINDINGS` (30). If more candidates exist, keep the top
  30 by severity then by line-count cost (longer functions, denser nesting
  rank higher within the same severity). Prefer 10-15 high-quality
  Critical/Nit findings over 30 weak Optional/FYI findings — fewer,
  sharper findings make for a tighter roast and cheaper persona dispatch.

### State update

After writing the dossier, append to `TASK_DIR<task_name>/state.md`:

- `Phase: dossier_complete`
- `dossier_path: <absolute path>`
- `finding_counts: {Critical: N, Nit: N, Optional: N, FYI: N}`
- `stack_fingerprint: <from Phase 4>`
- `cache_hit: true | false` (from Phase 4 cache check)

Control returns to SKILL.md, which then reads `phases/render.md` and
proceeds to Phase 5 (persona dispatch).

______________________________________________________________________

## Exit criteria

Before returning control to SKILL.md, verify all of:

- `TASK_DIR<task_name>/dossier.md` exists and is non-empty.
- Every finding header matches `## Finding N — <severity> — <file>:<line> — <description>` exactly.
- Every severity is one of `Critical`, `Nit`, `Optional`, `FYI`.
- Every finding has all three body fields populated.
- No author name, email, or git blame output appears anywhere in the file.
- `finding_counts` in state matches the actual count in the dossier.

If any check fails, fix it before proceeding. A broken dossier produces a
broken roast, and the whole plugin's value proposition is evidence anchoring.
