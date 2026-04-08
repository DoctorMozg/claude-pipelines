# Phase 1: Discovery & Graph Building

Detail for reference discovery, categorized grep searches, and iterative hop expansion.

## 1.1 Prepare context packet

Read `.mz/task/<task_name>/state.md` for the resolved target, target type, and any scope constraints from the user.

Build a **seed identifier** based on target type:

- **File**: the filename without extension (e.g., `middleware` from `src/auth/middleware.ts`), plus the full relative path for import matching.
- **Function**: the function/method name as given.
- **Module**: the directory name, plus common index/init file patterns.

## 1.2 Dispatch seed researchers

Dispatch **MAX_RESEARCHERS** (4) `pipeline-researcher` agents (model: sonnet) in a **single message** as parallel tool calls. Each covers one reference category:

### Researcher 1: Imports & Direct Calls

```
Task: Find all files that import or directly call the target.

Target: <seed identifier>
Target file: <resolved path>
Scope: <user scope constraints or "entire project">

Search for:
1. Import statements referencing the target file or module path (import/require/from/include)
2. Direct function calls to the target name
3. Method invocations on objects that match the target type
4. Dynamic imports (import(), require(), __import__)

For each match, record:
- File path and line number
- The exact matching line
- Reference type (import | call | dynamic_import)

Use Grep with multiple patterns. Search for:
- The filename/module name in import paths
- The function name as a called identifier
- Re-exports that expose the target

Output as a markdown table: | File | Line | Match | Reference Type |
Be exhaustive — missed references are missed blast radius. Better to over-include than under-include.
```

### Researcher 2: Type-Level References

```
Task: Find all files that reference the target at the type level.

Target: <seed identifier>
Target file: <resolved path>
Scope: <user scope constraints or "entire project">

Search for:
1. Type annotations using the target (TypeScript: `: TargetType`, Python: `-> TargetType`, `param: TargetType`)
2. Generic type parameters (`<TargetType>`, `List[TargetType]`)
3. Interface implementations or class inheritance from the target
4. Type aliases or type unions involving the target
5. Protocol/ABC references if the target defines one
6. Struct/class field types matching the target

For each match, record:
- File path and line number
- The exact matching line
- Reference type (annotation | generic | inheritance | alias)

Output as a markdown table: | File | Line | Match | Reference Type |
```

### Researcher 3: Test Files & Fixtures

```
Task: Find all test files and fixtures that exercise the target.

Target: <seed identifier>
Target file: <resolved path>
Scope: <user scope constraints or "entire project">

Search for:
1. Test files that import the target
2. Test fixtures/factories that create instances of the target
3. Mock/stub/spy references to the target
4. Test file naming conventions that mirror the target (test_<name>, <name>_test, <name>.spec, <name>.test)
5. Parameterized test data referencing the target
6. Integration test configurations mentioning the target

For each match, record:
- File path and line number
- The exact matching line
- Reference type (test_import | fixture | mock | naming_convention | config)

Output as a markdown table: | File | Line | Match | Reference Type |
```

### Researcher 4: Configs, Re-Exports & Barrel Files

```
Task: Find all configuration files, re-export files, and barrel files that reference the target.

Target: <seed identifier>
Target file: <resolved path>
Scope: <user scope constraints or "entire project">

Search for:
1. Barrel files (index.ts, __init__.py, mod.rs) that re-export the target
2. Package manifests referencing the target (package.json exports, setup.py entry_points, Cargo.toml)
3. Build configuration files (webpack, vite, tsconfig paths, CMakeLists.txt)
4. CI/CD configs that reference the target path
5. Documentation files that reference the target
6. Dependency injection registrations or factory patterns that wire the target
7. Router/route registrations pointing to the target
8. Plugin/middleware registration arrays including the target

For each match, record:
- File path and line number
- The exact matching line
- Reference type (barrel | manifest | build_config | ci | docs | di_registration | route)

Output as a markdown table: | File | Line | Match | Reference Type |
```

## 1.3 Collect and merge seed results

As researchers complete, merge all results into a unified graph:

1. Read each researcher's output. Extract the file/line/type tuples.
1. Deduplicate by (file, line) — same line found by multiple researchers keeps all reference types.
1. Build the initial adjacency list:
   - **Center node**: the target (depth 0)
   - **Depth 1 nodes**: all unique files from researcher results

Write the merged graph to `.mz/task/<task_name>/graph_hop_0.md`:

```markdown
# Blast Radius Graph — Hop 0 (Direct References)

Target: <resolved path or identifier>
Direct dependents: <count>

| # | File | Lines | Reference Types | Category |
|---|------|-------|-----------------|----------|
| 1 | path/to/file.ts | 12, 45 | import, call | imports_calls |
| 2 | path/to/other.py | 8 | annotation | type_refs |
[...]
```

## 1.4 Iterative hop expansion

For each hop from 1 to **MAX_DEPTH** - 1 (i.e., hops 1 and 2 for default MAX_DEPTH=3):

1. Take all files discovered in the previous hop.
1. For each file, use Grep to search for imports/references to that file from anywhere in the project. Focus on import statements and direct calls — skip type-level and test references for expansion hops (they add noise without adding blast radius signal).
1. Collect new files not already in the graph.
1. If no new files found, stop expansion early.
1. If total graph nodes exceed **MAX_GRAPH_NODES**, stop expansion and note truncation.

Write each hop to `.mz/task/<task_name>/graph_hop_<N>.md` with the same table format, adding a `Depth` column.

**Performance guard**: For each expansion hop, run Grep searches sequentially (not in parallel agents) to avoid redundant work. Each search is cheap — a single grep per file.

## 1.5 Build consolidated graph

Merge all hop files into `.mz/task/<task_name>/graph.md`:

```markdown
# Consolidated Blast Radius Graph

Target: <resolved path or identifier>
Total nodes: <count>
Max depth reached: <actual depth>
Truncated: <yes/no>

## Depth 0 (Target)
- <target path>

## Depth 1 (Direct Dependents) — <count> files
| # | File | Reference Types | Lines |
|---|------|-----------------|-------|
[...]

## Depth 2 (Transitive) — <count> files
| # | File | Via | Reference Types |
|---|------|-----|-----------------|
[...]

## Depth 3 (Transitive) — <count> files
| # | File | Via | Reference Types |
|---|------|-----|-----------------|
[...]
```

The `Via` column traces the path: "file_at_depth_1 → file_at_depth_2".

Update state: phase → `graph_complete`, node_count → N.
