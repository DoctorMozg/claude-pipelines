# Phase 2: Analysis & Report

Detail for git age overlay, risk scoring, safety verdict, and final report generation.

## 2.1 Git age analysis

Read `.mz/task/<task_name>/graph.md` to get the list of all files in the graph.

For each unique file in the graph (including the target), run these git commands via Bash:

```bash
# Last modified date and author
git log -1 --format="%ai|%an" -- "<file_path>"

# Total commit count (activity level)
git log --oneline -- "<file_path>" | wc -l

# Unique author count (knowledge distribution)
git log --format="%an" -- "<file_path>" | sort -u | wc -l

# First commit date (file age)
git log --reverse --format="%ai" -- "<file_path>" | head -1
```

**Performance guard**: Batch files into groups of 10 per Bash call using a loop. Do not run one Bash call per file — that wastes tool invocations.

Example batch command:

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

Parse results into a structured table. Write to `.mz/task/<task_name>/age_data.md`:

```markdown
# Age Analysis

| File | Last Modified | Commits | Authors | Age (days) | Staleness |
|------|--------------|---------|---------|------------|-----------|
| path/to/file.ts | 2026-03-15 | 42 | 3 | 180 | low |
[...]
```

**Staleness classification**:

- **low**: modified within 30 days
- **medium**: 30-180 days since last modification
- **high**: 180-365 days
- **critical**: over 365 days untouched

## 2.2 Test coverage estimation

For each file in the graph, estimate test coverage using heuristics:

1. Check if a corresponding test file exists (from Phase 1 researcher 3 results).
1. Count the number of test references found for this file.
1. Check if the file is in a directory that has any test files at all.

Classify each file:

- **tested**: dedicated test file exists AND imports the file
- **partially_tested**: referenced in tests but no dedicated test file
- **untested**: no test references found

Write to `.mz/task/<task_name>/coverage_estimate.md`.

## 2.3 Risk scoring

For each file in the graph, compute a risk score:

```
risk_score = coupling_depth_weight * staleness_weight * coverage_gap_weight
```

Where:

- **coupling_depth_weight**: depth 1 = 1.0, depth 2 = 0.6, depth 3 = 0.3 (deeper = less direct impact)
- **staleness_weight**: low = 0.5, medium = 1.0, high = 1.5, critical = 2.0 (stale code is riskier to break)
- **coverage_gap_weight**: tested = 0.5, partially_tested = 1.0, untested = 2.0 (untested code breaks silently)

**Risk classification** based on final score:

- **critical** (>= 2.0): High coupling + stale + untested — likely to break silently
- **high** (1.0 - 1.99): Significant risk — manual verification recommended
- **medium** (0.5 - 0.99): Moderate risk — tests should catch issues
- **low** (< 0.5): Low risk — well-tested and recently maintained

Sort all files by risk score descending.

## 2.4 Safety verdict

Assess overall refactor safety based on the graph:

- **SAFE**: All depth-1 files are tested, no critical-risk nodes, total graph < 20 nodes.
- **CAUTION**: Some untested depth-1 files OR any high-risk nodes OR graph has 20-50 nodes.
- **RISKY**: Multiple untested depth-1 files OR any critical-risk nodes OR graph > 50 nodes.
- **DANGEROUS**: Majority of depth-1 files are untested AND stale, OR graph > 80 nodes with critical nodes.

## 2.5 Generate report

Write the final report to `.mz/reports/blast_radius_<YYYY_MM_DD>_<target_slug>.md` (append `_v2`, `_v3` if exists).

```markdown
# Blast Radius: <target>

**Date**: <YYYY-MM-DD>
**Target**: `<resolved path or identifier>`
**Target type**: <file | function | module>
**Safety verdict**: <SAFE | CAUTION | RISKY | DANGEROUS>
**Total impact**: <N> files across <max_depth> dependency layers

## Summary

<2-3 sentence overview: what the target is, how widely it's used, and the key risk factors>

## Risk-Ranked Impact

| # | Risk | File | Depth | Staleness | Test Coverage | Score | Reference Types |
|---|------|------|-------|-----------|---------------|-------|-----------------|
| 1 | critical | path/to/old_untested.py | 1 | critical | untested | 4.0 | import, call |
| 2 | high | path/to/stale.ts | 1 | high | partial | 1.5 | type_ref |
[...]

## Dependency Layers

### Layer 1: Direct Dependents (<count> files)
<list of files with their reference types and risk levels>

### Layer 2: Transitive (<count> files)
<list with "via" paths showing the dependency chain>

### Layer 3: Transitive (<count> files)
<list with full dependency chains>

## Risk Hotspots

<Top 3-5 highest-risk files with explanation of why they're risky and what could go wrong>

## Age Profile

- **Newest dependent**: <file> (modified <date>)
- **Oldest dependent**: <file> (last modified <date>, <N> days ago)
- **Average staleness**: <days>
- **Single-author files**: <count> (bus factor risk)

## Test Coverage Gaps

- **Untested direct dependents**: <list>
- **Partially tested**: <list>
- **Well tested**: <list>

## Suggested Refactor Order

Based on risk analysis, if you proceed with changes to `<target>`:

1. **First**: Update <highest-risk untested files> — add tests before changing anything
2. **Then**: Modify <the target itself>
3. **Then**: Update <depth-1 dependents> in order of risk score
4. **Finally**: Verify <transitive dependents> via integration tests

## Methodology

- **Graph construction**: Multi-pass grep across imports, calls, type refs, tests, configs, re-exports
- **Expansion depth**: <actual depth reached> of <MAX_DEPTH> configured
- **Age data**: git log analysis per file (commit count, author count, last modified, creation date)
- **Test coverage**: Heuristic — presence of dedicated test files + import references
- **Risk formula**: coupling_depth_weight * staleness_weight * coverage_gap_weight
```

## 2.6 Present to user

Update state to `completed`. Present a summary including:

- The safety verdict (prominently)
- Total impact count
- Top 3 risk hotspots with 1-line explanations
- The report file path
- The suggested refactor order (abbreviated)

Keep the summary concise — the full report has the details.
