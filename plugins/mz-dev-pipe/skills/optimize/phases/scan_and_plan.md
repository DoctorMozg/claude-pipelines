# Phases 1-2: Scan, Chunk, and Baseline

Full detail for the pre-optimization phases of the optimize skill. Covers resolving the input scope to a concrete file list, building the import graph via a researcher agent, grouping files into parallel-safe chunks, and capturing the baseline test/lint state that later phases check regressions against.

## Contents

- [Phase 1: Scan & Chunk](#phase-1-scan--chunk)
  - 1.1 Resolve scope
  - 1.2 Build import graph
  - 1.3 Chunk files
  - 1.4 Write scan artifact
- [Phase 2: Baseline Snapshot](#phase-2-baseline-snapshot)
  - 2.1 Detect tooling
  - 2.2 Run baseline
  - 2.3 Write baseline artifact

______________________________________________________________________

## Phase 1: Scan & Chunk

**Goal**: Turn the user's scope argument into an ordered list of parallel-safe chunks ready for optimization.

### 1.1 Resolve scope

**If a `scope:` parameter was extracted by the SKILL.md orchestrator** (branch / global / working), its git commands have already produced a concrete file list. Use that list directly, applying standard exclusions (vendored, generated, lock files, >5000 LOC). If an explicit scope argument was also given (e.g., `scope:branch "src/auth/"`), intersect the two — keep only files that appear in both the scope-parameter list and the explicit scope expansion.

**If no `scope:` parameter was given**, detect the form of `$ARGUMENTS` and resolve it to a concrete file list:

| Form                  | Detection                                | Resolution                                                |
| --------------------- | ---------------------------------------- | --------------------------------------------------------- |
| Glob pattern          | Contains `*`, `?`, `[...]`, `{...}`      | Expand via the Glob tool                                  |
| Directory             | Exists as a directory on disk            | Recursively list source files, honoring `.gitignore`      |
| Git range             | Matches `refA..refB` or a valid ref name | `git diff --name-only <range>` filtered to existing files |
| Free-text description | None of the above                        | Dispatch a `pipeline-researcher` agent to interpret       |

**Free-text resolution**: spawn a `pipeline-researcher` agent (model: **sonnet**) with:

```
The user wants to optimize code matching this description: "<free-text>"

Explore the project and identify the concrete file list that matches. Consider:
1. Directory names, file names, and symbol names that match the description
2. The project's top-level structure (README, package manifest, entry points)
3. Tests that reference the described area — they often reveal the implementation files

Output:
- A concrete list of file paths (repo-relative)
- Confidence: high / medium / low
- If low confidence: list 2-3 alternative interpretations so the orchestrator can ask the user

Do NOT build the import graph yet — that's a separate step.
```

If the researcher returns low confidence or multiple plausible interpretations, **ask the user** which to use via AskUserQuestion. Do not guess.

**Filter the resolved list**:

- Source files only (exclude build artifacts, lock files, generated code, vendored deps)
- Exclude test files unless the scope explicitly targets tests
- Exclude files > 5000 LOC — flag them separately; optimizing files that large is risky and usually needs a targeted pass

If the final list is empty, report to the user and exit.

### 1.2 Build import graph

Spawn a `pipeline-researcher` agent (model: **sonnet**) with:

```
Build an import/dependency graph for this file list:
<resolved file list>

For each file:
1. Identify all files it imports from (within the project — ignore external deps)
2. Identify all files that import from it (reverse dependencies, within the scope)
3. Note if the file is part of a strongly-connected component (circular imports)

Detect the project's language(s) and use the appropriate import syntax:
- Python: `import X`, `from X import Y`
- JS/TS: `import ... from`, `require()`
- Rust: `use X::Y`, `mod X`
- Go: `import "X"`
- C/C++: `#include "X"`
- Java: `import X.Y`

Output as a JSON adjacency list saved to .mz/task/<task_name>/import_graph.json:

{
  "files": {
    "path/to/file.py": {
      "imports": ["path/to/other.py", ...],
      "imported_by": ["path/to/caller.py", ...],
      "scc_id": 0
    }
  },
  "sccs": [
    {"id": 0, "members": ["path/to/file.py", "path/to/other.py"]}
  ]
}

Also return a short textual summary:
- Total files analyzed
- Number of strongly-connected components
- Largest SCC size
- Files with no intra-scope imports (isolates — safe to chunk alone)
- Any files the graph construction failed on, with reason
```

**Fallback**: if the researcher fails to build the graph (unsupported language mix, parse errors on most files), fall back to **directory-based chunking**: group files by their parent directory. Flag the fallback prominently in the Phase 2.5 approval plan so the user knows the chunking is less principled than an import graph.

### 1.3 Chunk files

Using the import graph, group files into chunks under these rules:

**Rule 1 — SCC atomicity**: every file in a strongly-connected component must be in the same chunk. Circular imports are atomic and cannot be split across optimizers.

**Rule 2 — Hard cap**: total chunks ≤ `MAX_OPTIMIZERS = 6`.

**Rule 3 — Balance**: chunks should be roughly balanced by file count (target: within ±30% of mean).

**Algorithm**:

1. Start with one chunk per SCC (isolated files are singleton SCCs).
1. If chunks > 6: greedily merge the two smallest chunks whose union has the fewest cross-chunk imports. Repeat until chunks ≤ 6.
1. If chunks < 2 and total files ≥ 10: split the largest chunk along its weakest internal cut (the edge whose removal produces the most balanced pieces).

**Edge cases**:

- ≤ 5 files total → 1 chunk, skip the SCC algorithm
- 1 giant SCC containing > 80% of files → accept 1 chunk; flag to the user that parallelism isn't possible for this scope
- Multiple disconnected components (isolated subgraphs) → each becomes a separate chunk until the cap is hit

### 1.4 Write scan artifact

Write `.mz/task/<task_name>/scan.md`:

```markdown
# Scan: <scope>

## Resolved scope
- Input form: <glob / directory / git-range / free-text>
- Total files: N
- Excluded (size / generated / test): M files

## Chunks (N)

### Chunk 1: <short name>
- **Rationale**: <why these files are grouped — SCC, directory, etc.>
- **File count**: K
- **Files**:
  - path/to/file1
  - path/to/file2
- **Cross-chunk imports**: list of imports into/out of this chunk

### Chunk 2: ...

## High-coupling warnings
- <file> is imported by N files across N chunks — cross-chunk edits likely
- <SCC> has M members — optimizing this as one unit

## Chunking strategy
- Algorithm used: import-graph SCC grouping (or directory fallback)
- Merges / splits applied: <list>
```

Update state file phase to `scanned` and record the chunk count.

______________________________________________________________________

## Phase 2: Baseline Snapshot

**Goal**: Capture the pre-optimization test and lint state so regressions can be detected unambiguously later.

### 2.1 Detect tooling

Examine the project for:

- **Test command**: look in `pyproject.toml`, `package.json`, `Makefile`, `Cargo.toml`, `go.mod`, `CMakeLists.txt`
- **Lint command**: pre-commit config, ruff, eslint, clippy, golangci-lint, clang-tidy

If neither is found, ask the user how to verify green state before proceeding. Do not skip the baseline — without it, regressions cannot be detected reliably.

### 2.2 Run baseline

Run the test suite scoped to the files in `scan.md` if the test framework supports path filtering; otherwise run the full suite. Run the linters on the scope. Capture:

- Test result: PASS / FAIL / PARTIAL
- Failing tests (if any): names + one-line summary
- Lint result: CLEAN / WARNINGS / ERRORS
- Issue counts
- Duration of each step

### 2.3 Write baseline artifact

Write `.mz/task/<task_name>/baseline.md`:

```markdown
# Baseline

## Test Status
- Command: `<command>`
- Result: PASS / FAIL
- Duration: Xs
- Failing tests (if any):
  - <name>: <one-line summary>

## Lint Status
- Command: `<command>`
- Result: CLEAN / WARNINGS / ERRORS
- Issue count: N

## Notes
- <anything unusual about the project's starting state>
```

**If baseline is RED** (tests failing OR lint errors): flag it prominently in the Phase 2.5 approval plan. The user must explicitly acknowledge the red baseline and decide whether to proceed (optimization may mask or exacerbate the failures) or abort and run `polish` first.

Update state file phase to `baseline_captured`.
