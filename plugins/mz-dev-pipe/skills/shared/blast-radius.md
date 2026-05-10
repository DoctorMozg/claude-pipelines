# Blast Radius — Shared Module

Callable module that computes the downstream impact set of a target file or directory using import-graph walking, git-age overlay, and risk scoring. Auto-invoked by `audit` whenever scope is bounded (`scope:branch`, `scope:working`, or path-list) and by `optimize` on every run. NOT auto-invoked when scope is `global` (everything is in scope already).

## Status

Active. The standalone `/blast-radius` skill was demoted in v0.33.x; this module is the only source of truth for impact analysis. Calling skills execute the import-graph walk inline using `Grep` / `Read` / `Bash` per the Algorithm below — no subagent fan-out, no token cost beyond the calling agent's window.

## Invocation contract

### Input

A list of file paths representing the bounded scope:

- `scope:branch` → output of `git diff --name-only <base>..HEAD`
- `scope:working` → output of `git status --porcelain | awk '{print $2}'`
- Explicit path-list → as supplied
- Standalone target (file/function/module) → resolve to single-element list

### Output

A YAML block written to `.mz/task/<task_name>/blast_radius.yml`:

```yaml
generated_at: 2026-05-10T14:32:00Z
input_files:
  - src/auth/middleware.py
  - src/auth/jwt.py
impacted:
  - path: src/services/auth_service.py
    distance: 1               # direct importer
    via: src/auth/middleware.py
    confidence: high          # high = static import resolved; medium = dynamic import; low = string match
    reference_types: [import, call]
    staleness: low            # low | medium | high | critical (last-modified bucket)
    coverage: tested          # tested | partially_tested | untested
    risk_score: 0.5           # coupling × staleness × coverage_gap
    risk_level: medium        # low | medium | high | critical
  - path: tests/test_auth.py
    distance: 1
    via: src/auth/middleware.py
    confidence: high
    reference_types: [test_import]
    staleness: low
    coverage: tested
    risk_score: 0.25
    risk_level: low
cap_reached: false             # true if MAX_BLAST_DEPTH or MAX_BLAST_FILES forced truncation
truncated_at: null             # one of: depth | files | null
languages_skipped:             # languages present in the scope that this module cannot analyze
  - shell
verdict: SAFE                  # SAFE | CAUTION | RISKY | DANGEROUS
```

When the calling skill needs a human-readable narrative (e.g., for a /blast-radius-style report), it can additionally render the YAML using the **Report Template** below.

## Scope of analysis

| Language   | Resolver                                                                                                |
| ---------- | ------------------------------------------------------------------------------------------------------- |
| Python     | `import X` / `from X import Y` — resolve via `sys.path` heuristic (project root + first-party packages) |
| TypeScript | `import … from "X"` / `require("X")` — resolve via `tsconfig.json` `paths` and relative paths           |
| JavaScript | Same as TypeScript minus type-only imports                                                              |
| Rust       | `use X` — resolve via `Cargo.toml` workspace members + `mod` declarations                               |
| Go         | `import "X"` — resolve via `go.mod` module path                                                         |
| Other      | Skipped — listed under `languages_skipped` in output                                                    |

Vendored, generated, lockfile, and build-output paths are excluded (same exclusions as `scope:global`).

### Confidence values

- `high` — static import statement resolved to a real file in the project.
- `medium` — dynamic import (e.g., Python `importlib.import_module`, JS dynamic `import()`) where the target name is a string literal.
- `low` — grep-only match for the target symbol's name (could be a coincidence). Skills SHOULD treat low-confidence impacted files as advisory rather than authoritative.

## Bounds

Resolved per `shared/iteration-limits.md`:

- `MAX_BLAST_DEPTH` — default 3. Stop walking transitive imports past this depth.
- `MAX_BLAST_FILES` — default 200. Stop adding to the impacted list past this count.

When either bound is hit, mark `cap_reached: true`, record which bound in `truncated_at`, and return what fits.

## Algorithm

The calling skill executes these steps inline. No agent dispatch is needed — Grep + Read + Bash on the orchestrator are sufficient.

### Step 1: Build seed identifiers

For each input file, derive matchers:

- **Filename without extension** (e.g., `middleware` from `src/auth/middleware.ts`)
- **Full relative path** for import-statement matching (e.g., `src/auth/middleware`)
- **Top-level public symbols** declared in the file (functions, classes, exported types) — extracted via Grep on language-specific patterns (`^def `, `^class `, `^export (function|class|const|interface|type) `, `^pub fn `, `^func `).

### Step 2: Discover direct dependents (Depth 1)

For every seed identifier, run targeted Grep across the project (excluding vendored/generated dirs). Capture results in four categories:

1. **Imports & direct calls** — import statements referencing the file/module path; direct function calls to top-level public symbols; method invocations.
1. **Type-level references** — type annotations, generics, inheritance, type aliases, Protocol/ABC implementations.
1. **Test files & fixtures** — test files importing the target; mocks/stubs/spies; naming-convention test files (`test_<name>`, `<name>_test`, `<name>.spec`, `<name>.test`).
1. **Configs, re-exports & barrels** — barrel files (`index.ts`, `__init__.py`, `mod.rs`); package manifests; build/CI configs; route registrations; DI/factory wires.

For each match, record `(file_path, line, matched_text, reference_type, confidence)`. Deduplicate by `(file, line)`; same line found by multiple categories merges its reference_types into a list. Tag confidence per the `confidence values` table above.

The set of unique files at this point is **Depth 1**.

### Step 3: Iterative hop expansion (Depth 2 → MAX_BLAST_DEPTH)

For each hop from 2 to `MAX_BLAST_DEPTH`:

1. Take all files discovered in the previous hop.
1. For each file, Grep for imports/references targeting it from anywhere in the project. Skip type-level and test references on expansion hops (they add noise without adding blast-radius signal — keep the walk focused on call/import edges).
1. Add new files (not already in the graph) to the current hop, recording `via: <previous-hop-file>`.
1. If no new files found, stop expansion early.
1. If total graph nodes exceed `MAX_BLAST_FILES`, stop expansion and set `cap_reached: true`, `truncated_at: files`.
1. If hop reaches `MAX_BLAST_DEPTH` and there are still unexpanded files, set `cap_reached: true`, `truncated_at: depth`.

**Performance guard**: Run Grep searches sequentially within an expansion hop. Each Grep is cheap; agent dispatch is not.

### Step 4: Git-age overlay

For each unique file in the graph (including the input files), batch git queries — DO NOT run one Bash call per file:

```bash
for f in "file1.ts" "file2.py" "file3.rs"; do
  echo "FILE:$f"
  echo "LAST_MODIFIED:$(git log -1 --format='%ai|%an' -- "$f" 2>/dev/null || echo 'N/A')"
  echo "COMMITS:$(git log --oneline -- "$f" 2>/dev/null | wc -l)"
  echo "AUTHORS:$(git log --format='%an' -- "$f" 2>/dev/null | sort -u | wc -l)"
  echo "CREATED:$(git log --reverse --format='%ai' -- "$f" 2>/dev/null | head -1)"
  echo "---"
done
```

Batch in groups of ≤10 files per Bash invocation.

**Staleness classification** (days since last modification):

- `low` — within 30 days
- `medium` — 30-180 days
- `high` — 180-365 days
- `critical` — over 365 days untouched

### Step 5: Test coverage estimation

For each non-test file in the graph:

- `tested` — a dedicated test file exists AND imports the file (matched by Step 2 researcher 3 results)
- `partially_tested` — file referenced inside test files but no dedicated test file matches its name
- `untested` — no test references found

### Step 6: Risk scoring

For each file:

```
risk_score = coupling_depth_weight × staleness_weight × coverage_gap_weight
```

Weights:

- **coupling_depth_weight**: depth 1 = 1.0, depth 2 = 0.6, depth 3 = 0.3
- **staleness_weight**: low = 0.5, medium = 1.0, high = 1.5, critical = 2.0
- **coverage_gap_weight**: tested = 0.5, partially_tested = 1.0, untested = 2.0

**Risk classification** from final score:

- `critical` — score ≥ 2.0 (high coupling + stale + untested → likely silent breakage)
- `high` — 1.0 ≤ score < 2.0 (manual verification recommended)
- `medium` — 0.5 ≤ score < 1.0 (tests should catch issues)
- `low` — score < 0.5 (well-tested, recently maintained)

Sort the impacted list by risk_score descending before writing the YAML.

### Step 7: Safety verdict

Aggregate verdict over the whole graph (assigned to `verdict:` in the YAML):

- `SAFE` — all depth-1 files are tested, no critical-risk nodes, total graph < 20 nodes
- `CAUTION` — some untested depth-1 files OR any high-risk nodes OR graph 20-50 nodes
- `RISKY` — multiple untested depth-1 files OR any critical-risk nodes OR graph > 50 nodes
- `DANGEROUS` — majority of depth-1 files untested AND stale, OR graph > 80 nodes with critical-risk nodes

## Auto-invocation rules

| Skill      | When                                                   | What the calling skill does with the output                                                                                              |
| ---------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `audit`    | Phase 1, only if scope is `branch`/`working`/path-list | Add `impacted[].path` files to the lens-research file set so reviewers see downstream risk; surface `verdict` in the final report header |
| `optimize` | Phase 1, always (optimize is always bounded)           | Use `impacted[]` to identify high-blast-radius targets that need extra-careful review; gate Phase 2.5 user-approval on the verdict       |

`scope:global` skips invocation — by definition everything is already in scope.

## Report Template (optional human-readable rendering)

Skills MAY render the YAML as a markdown report when surfacing impact analysis to the user. Suggested template (matches the legacy `/blast-radius` report so existing consumers remain compatible):

```markdown
# Blast Radius: <input or target>

**Date**: <YYYY-MM-DD>
**Scope**: <files in input>
**Safety verdict**: <SAFE | CAUTION | RISKY | DANGEROUS>
**Total impact**: <N> files across <max_depth_reached> dependency layers

## Summary
<2-3 sentence overview>

## Risk-Ranked Impact

| # | Risk | File | Depth | Staleness | Test Coverage | Score | Reference Types |
|---|------|------|-------|-----------|---------------|-------|-----------------|
| 1 | critical | path/to/old_untested.py | 1 | critical | untested | 4.0 | import, call |
[...]

## Dependency Layers

### Layer 1: Direct Dependents (<count> files)
### Layer 2: Transitive (<count> files)
### Layer 3: Transitive (<count> files)

## Risk Hotspots
<Top 3-5 highest-risk files>

## Age Profile
- Newest dependent: <file>
- Oldest dependent: <file>
- Single-author files: <count> (bus factor risk)

## Test Coverage Gaps
- Untested direct dependents: <list>

## Suggested Refactor Order
1. First: <highest-risk untested files> — add tests
2. Then: <target>
3. Then: <depth-1 dependents>
4. Finally: <transitive dependents> via integration tests
```

## Why auto-invoke instead of a flag

A flag like `--impact-of=<target>` requires the user to remember it exists. The 5-lens expert panel observation: scope-bounded skills produce reports that read like complete answers ("we audited the branch — here's what we found") but silently miss downstream callers the change might break. Auto-invocation makes downstream-risk part of the inspection by default, removing the foot-gun without adding a flag the user has to know about.

`scope:global` is the explicit opt-out: if the user asks to audit the world, blast-radius is already implicit in "the world".
