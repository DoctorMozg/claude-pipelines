# Phases 1-3: Scope, Multi-Lens Research, and Consolidation

Full detail for the research phases of the dev-review-and-fix skill. Covers argument parsing (scope + lens selection), dispatching parallel researchers across five lenses, and consolidating their findings into a ranked, severity-capped plan.

## Contents

- [Phase 1: Scope & Lens Selection](#phase-1-scope--lens-selection)
  - 1.1 Parse the argument
  - 1.2 Resolve scope filter
  - 1.3 Select lenses
  - 1.4 Write scope artifact
- [Phase 2: Multi-Lens Research](#phase-2-multi-lens-research)
  - 2.1 Dispatch researchers
  - 2.2 Lens-specific prompts
- [Phase 3: Consolidate & Rank](#phase-3-consolidate--rank)
  - 3.1 Merge and dedupe
  - 3.2 Rank and apply caps
  - 3.3 Write findings artifact

______________________________________________________________________

## Phase 1: Scope & Lens Selection

**Goal**: Turn `$ARGUMENTS` into two concrete filters — which files to scan (scope) and which research lenses to dispatch (lens list).

### 1.1 Parse the argument

**Step 0 — Scope parameter**: if the SKILL.md orchestrator extracted a `scope:` parameter (branch / global / working), its git commands have already produced a concrete file list. That list becomes the scope filter — skip the scope-resolution table in 1.2 and go straight to 1.3 (lens selection). Only classify the remaining argument text (after `scope:` removal) for lens keywords.

**Step 1 — Token classification**: split the remaining argument into tokens and classify each:

- **Path-like** — matches a glob pattern, looks like a directory (contains `/`, matches an actual directory on disk), or matches `refA..refB` for git ranges
- **Lens keyword** — matches the table below
- **Vague keyword** — "bugs", "problems", "issues", "stuff", "things", "improvements" — no lens signal
- **Unknown** — doesn't match anything recognizable

### 1.2 Resolve scope filter

**If a `scope:` parameter was given**: the file list is already resolved. Apply roam-mode exclusions to it and skip the table below.

**If no `scope:` parameter was given**: resolve based on token types:

| Token type found             | Scope resolution                                                                          |
| ---------------------------- | ----------------------------------------------------------------------------------------- |
| One or more path-like tokens | Expand them (Glob or directory walk) into a concrete file list                            |
| No path-like tokens          | Roam scope: entire repo minus `.gitignore`, vendored deps, generated code, and test files |

**Roam-mode exclusions** (always applied):

- Respect `.gitignore` (run `git check-ignore` or read `.gitignore` directly)
- Exclude `node_modules/`, `vendor/`, `.venv/`, `venv/`, `target/`, `build/`, `dist/`, `out/`
- Exclude generated/lock files: `*.lock`, `package-lock.json`, `yarn.lock`, `Cargo.lock`, `poetry.lock`, `*.generated.*`, `*_pb2.py`, `*.pb.go`
- Exclude test files: `test_*.py`, `*_test.py`, `*.test.ts`, `*.spec.ts`, `*_test.go`, `tests/` directories
- Exclude files > 5000 LOC — flag them separately; scanning files that large is rarely productive

If the final file list is empty, report to the user and exit.

### 1.3 Select lenses

Match the argument tokens against this keyword table:

| Lens                | Keywords                                                                                               |
| ------------------- | ------------------------------------------------------------------------------------------------------ |
| **correctness**     | bug, bugs, correctness, logic, off-by-one, null, undefined, concurrency, race, thread, async, deadlock |
| **security**        | security, auth, authz, injection, owasp, vulnerability, xss, csrf, secrets, credential, sanitize       |
| **performance**     | performance, perf, slow, latency, memory, leak, optimize, bottleneck, hot path, n+1                    |
| **maintainability** | maintainability, smell, cleanup, duplication, complexity, refactor, readability, naming, docs          |
| **reliability**     | reliability, error handling, crash, retry, timeout, fallback, edge case, robustness                    |

**Rules**:

1. If ≥ 1 lens keyword is matched → dispatch **only** the matched lenses.
1. If only vague keywords (no specific lens match) → dispatch **all 5 lenses**.
1. If only path-like tokens (no lens keywords at all) → dispatch **all 5 lenses** on the narrowed scope.
1. If argument is empty → dispatch **all 5 lenses** on roam scope.
1. If the argument contains unknown tokens and no recognized lens or path → **ask the user** via AskUserQuestion which lens(es) to use. Never guess.

Example parses:

| Argument                        | Scope           | Lenses                        |
| ------------------------------- | --------------- | ----------------------------- |
| `""` (empty)                    | roam            | all 5                         |
| `"concurrency bugs"`            | roam            | correctness                   |
| `"security audit of src/auth/"` | `src/auth/`     | security                      |
| `"src/payments/"`               | `src/payments/` | all 5                         |
| `"look for performance issues"` | roam            | performance                   |
| `"bugs and cleanup"`            | roam            | correctness + maintainability |
| `"audit the thing"`             | **ask user**    | **ask user**                  |

### 1.4 Write scope artifact

Write `.mz/task/<task_name>/scope.md`:

```markdown
# Scope & Lens Selection

## Argument
- Raw: "<$ARGUMENTS>"
- Interpretation:
  - Path-like tokens: [...]
  - Lens keywords: [...]
  - Vague/unknown: [...]

## Scope
- Mode: roam / narrowed
- Total files: N
- Excluded (gitignore/vendored/generated/tests/>5000 LOC): M files
- File list:
  <collapsed by directory if > 30 files>

## Lenses selected
- [x] correctness
- [x] security
- [ ] performance
- [x] maintainability
- [ ] reliability

## Ask-user events
- <any AskUserQuestion raised during parse, with user's answer>
```

Update state file phase to `scope_selected` and record lens count.

______________________________________________________________________

## Phase 2: Multi-Lens Research

**Goal**: Locate candidate problems across the selected lenses in parallel.

### 2.1 Dispatch researchers

Spawn N `pipeline-researcher` agents (model: **sonnet**) in a **single message** using parallel tool calls — one per selected lens. Each researcher reads `.mz/task/<task_name>/scope.md` for the file list and runs its lens-specific analysis.

Each researcher must output to `.mz/task/<task_name>/findings_<lens>.md` in this structured format:

```markdown
# Lens: <lens name>

## Findings

### Finding 1
- **File**: path/to/file:line
- **Severity**: critical | high | medium | low
- **Confidence**: high | medium | low
- **Category**: <sub-category within the lens>
- **Description**: <one-paragraph explanation of the problem>
- **Evidence**: <code snippet or grep output supporting the claim>
- **Proposed fix**: <one-paragraph description of how to fix it, or "needs investigation">
- **Cross-references**: <other files that interact with this code, if relevant>

### Finding 2
...

## Lens summary
- Files scanned: N
- Findings by severity: critical=X, high=Y, medium=Z, low=W
- Skipped files (reason): <list>
- Lens notes: <anything the researcher wants to flag beyond individual findings>
```

### 2.2 Lens-specific prompts

**Correctness researcher** (`pipeline-researcher`, model: sonnet):

```
You are the CORRECTNESS lens of a multi-lens codebase audit.

## Scope
Read .mz/task/<task_name>/scope.md for the exact file list.

## What to find
Read each file and look for:
1. Off-by-one errors (array indexing, loop bounds, slice/substring arithmetic)
2. Null / None / undefined handling gaps (missing guards before dereference)
3. Race conditions (unsynchronized shared state, check-then-act patterns)
4. Incorrect error handling (caught and ignored, wrong exception types, silent failures)
5. Resource leaks (files, sockets, locks, contexts not released on all paths)
6. Type confusion (implicit conversions, mixed units, stringly-typed state)
7. Logic bugs (inverted conditions, wrong operator, copy-paste errors between similar blocks)
8. Concurrency / async issues (missing await, unresolved promises, deadlocks)

## Rules
1. Only report findings you can point to with file:line.
2. Assign severity:
   - critical: causes data loss, security breach, or crash in common paths
   - high: causes wrong results or crashes in specific conditions
   - medium: causes incorrect behavior in edge cases
   - low: style/clarity issues that could mask future bugs
3. Assign confidence:
   - high: you've verified the bug path by reading the code fully
   - medium: pattern matches a known bug class but you haven't traced every caller
   - low: suspicious pattern that may be intentional
4. For each finding, propose a concrete fix (not "add more tests").
5. Cross-reference callers when the finding affects an API.

Output format: see findings file template. Save to .mz/task/<task_name>/findings_correctness.md.
```

**Security researcher**:

```
You are the SECURITY lens of a multi-lens codebase audit.

## Scope
Read .mz/task/<task_name>/scope.md for the exact file list.

## What to find
1. Input validation gaps — untrusted input reaching queries, shell, eval, filesystem, redirects
2. Injection vectors — SQL, NoSQL, command, LDAP, XPath, template
3. Authentication / authorization flaws — missing checks, broken access control, IDOR
4. Cryptography misuse — weak algos, hardcoded IVs, predictable secrets, wrong mode
5. Hardcoded secrets — API keys, passwords, tokens in source or config
6. XSS / CSRF in web code — unescaped output, missing token validation
7. Path traversal — unchecked user-controlled file paths
8. Insecure deserialization — pickle, yaml.load, unsafe constructors
9. Information disclosure — verbose errors, debug endpoints, stack traces in responses
10. Dependency risks — known-vulnerable patterns visible in the code

## Rules
Same severity and confidence rules as the correctness lens.
For any hardcoded secret, flag as CRITICAL regardless of exploitability.

Save findings to .mz/task/<task_name>/findings_security.md.
```

**Performance researcher**:

```
You are the PERFORMANCE lens of a multi-lens codebase audit.

## Scope
Read .mz/task/<task_name>/scope.md for the exact file list.

## What to find
1. N+1 query patterns (loop with per-iteration DB/API call)
2. Unnecessary work inside hot loops (repeated computation, allocations)
3. Quadratic algorithms on data that can grow
4. Memory leaks / unbounded growth (caches without eviction, subscribers without cleanup)
5. Blocking I/O on async paths
6. Missing batching / pagination on large data operations
7. Redundant work across call sites that could be memoized or cached
8. Expensive operations on initialization / startup that block request handling

## Rules
Severity is driven by hot-path likelihood: critical = on every request; high = on common operations; medium = on occasional paths; low = micro-optimizations.
Do NOT propose changes that require new dependencies or major refactors — mark those as "needs investigation".

Save findings to .mz/task/<task_name>/findings_performance.md.
```

**Maintainability researcher**:

```
You are the MAINTAINABILITY lens of a multi-lens codebase audit.

## Scope
Read .mz/task/<task_name>/scope.md for the exact file list.

## What to find
1. Code duplication (same logic in 3+ places, good candidates for extraction)
2. Functions > 100 lines or cyclomatic complexity > 15
3. Files > 1000 lines that mix concerns
4. Unclear names (single letters outside tight scopes, abbreviations, misleading names)
5. Missing docstrings / comments on public APIs
6. Dead code (unused functions, classes, branches — verify with grep)
7. Inconsistent patterns within the same module (mixed error handling styles, etc.)
8. Magic numbers / strings that should be named constants

## Rules
Severity should reflect cost-of-maintenance, not aesthetic preference.
Do NOT flag style issues already covered by the project's formatter — those are not findings.

Save findings to .mz/task/<task_name>/findings_maintainability.md.
```

**Reliability researcher**:

```
You are the RELIABILITY lens of a multi-lens codebase audit.

## Scope
Read .mz/task/<task_name>/scope.md for the exact file list.

## What to find
1. Missing error handling on external calls (network, filesystem, subprocess)
2. No retry / timeout on flaky operations
3. No fallback on graceful-degradation paths
4. Exceptions that escape where they shouldn't (into event loops, into UI threads)
5. Unhandled edge cases visible in the code (empty input, max size, overflow)
6. Tight coupling to external services without circuit breakers
7. Silent failures (catch blocks that log-and-continue where they should propagate)
8. Missing input bounds (max size, max depth, max count) that could cause OOM or runaway

## Rules
Same severity and confidence rules.
For every finding, specify the failure scenario ("when X happens, Y breaks").

Save findings to .mz/task/<task_name>/findings_reliability.md.
```

Update state file phase to `researched` and record how many findings each lens produced.

______________________________________________________________________

## Phase 3: Consolidate & Rank

**Goal**: Turn per-lens finding files into one ranked, capped plan.

### 3.1 Merge and dedupe

Read all `findings_<lens>.md` files. Dedupe findings that point to the same `file:line` from multiple lenses:

- **Same file:line, same category** → keep one, note that both lenses flagged it (higher confidence)
- **Same file:line, different categories** → keep both; they're different issues coincidentally co-located
- **Overlapping ranges** (e.g., lens A flags lines 42-50, lens B flags lines 45-48) → keep both but link them

Assign each unique finding a stable numeric ID (`F1`, `F2`, ...).

### 3.2 Rank and apply caps

Within each severity tier, sort by confidence (high > medium > low), breaking ties by lens priority (correctness > security > reliability > performance > maintainability).

Apply per-tier caps:

- **Critical**: include ALL (no cap)
- **High**: top `HIGH_CAP = 10`
- **Medium**: top `MEDIUM_CAP = 5`
- **Low**: skip entirely from the fix plan (record the count only)

Findings that exceed a cap are NOT discarded — they move into a "Deferred" section of the summary and are reported to the user at the approval gate as "N additional <severity> findings not included in this plan".

### 3.3 Write findings artifact

Write `.mz/task/<task_name>/findings.md`:

```markdown
# Consolidated Findings

## Summary
- Total findings: N (merged from <X> per-lens raw findings)
- Severity breakdown: critical=A, high=B (of B_total), medium=C (of C_total), low=D (skipped)
- Lenses run: <list>
- Files with findings: M (of K scanned)

## Plan (approved findings will be fixed)

### Critical
#### F1 — <file:line> — <lens> — confidence: <level>
- **Description**: <one paragraph>
- **Proposed fix**: <one paragraph>
- **Affected file**: <file>

#### F2 — ...

### High (top 10 of <total>)
#### F<id> — ...

### Medium (top 5 of <total>)
#### F<id> — ...

## Deferred (not in fix plan)
- N additional high findings not included (below top 10)
- M additional medium findings not included (below top 5)
- K low findings skipped entirely

## Chunk preview
Findings grouped by affected file:

- **Chunk 1** (`path/to/file_a.py`): F1, F4, F7 — 3 findings
- **Chunk 2** (`path/to/file_b.py`): F2 — 1 finding
- **Chunk 3** (`path/to/file_c.py`): F3, F5 — 2 findings
...

Total chunks: C
Waves required: ceil(C / MAX_CODERS) = W
```

Update state file phase to `findings_ranked` and record total findings + chunk count.

**If the plan has zero findings at severity ≥ medium**: report to the user and exit cleanly. Nothing to fix.
