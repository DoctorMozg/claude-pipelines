# Phase 1: Scope Intelligence Gate

**Goal**: Materialise the changed file list, classify each file into a blast-radius tier, identify trust boundary mutations at T2+, assign reversibility classes, and write `scope.md` — the shared context artifact for all downstream phases.

## 1.1 Parse the scope argument

Extract the `scope:` parameter from `$ARGUMENTS`. If no `scope:` is provided, default to `scope:branch`.

Scope modes:

- `scope:branch` — files changed on the current branch vs `origin/main`
- `scope:working` — files with uncommitted changes (`git diff --name-only` + untracked)
- `scope:global` — full repository (use audit's roam-mode exclusions)

Remove the `scope:` token from `$ARGUMENTS` before passing to subsequent argument parsing.

## 1.2 Materialise the file list

For `scope:branch` (default):

```bash
git diff $(git merge-base HEAD origin/main)...HEAD --name-only --diff-filter=ACM
```

For `scope:working`:

```bash
git diff --name-only && git ls-files --others --exclude-standard
```

For `scope:global`: use the roam-mode exclusions from the existing audit skill (`.gitignore`, `node_modules/`, `vendor/`, `.venv/`, generated files, lock files, test files, files > 5000 LOC).

If the file list is empty after materialisation, report to the user and exit. Do NOT proceed with an empty scope — this is almost always a scope resolution error.

## 1.3 Classify files by blast-radius tier

Read `references/blast-radius-tier-rules.md` for the full tier definitions.

For each file in the list:

1. Check T3 signals first (highest tier, short-circuits further checks)
1. Check T2 signals
1. Check T1 signals (default for any source file)
1. Check T0 signals (docs, tests, config, lock files)

Assign each file the highest matching tier. Compute:

```
overall_tier = max(tier(f) for f in file_list)
```

## 1.4 Identify trust boundary delta (T2+ only)

If `overall_tier >= T2`, read `references/trust-boundary-patterns.md` and scan each T2+ file for matching patterns.

For each matching pattern:

- Record the file path, line reference, boundary type (from the pattern table)
- Mark the boundary as "mutated" — it is being changed, not just read

Group into categories: Auth, Crypto, Network Egress, PII, IAM.

At T0/T1: set `trust_boundary_delta: none`.

## 1.5 Assign reversibility classes

For each changed file, assign one of:

| Class               | Criteria                                                                                     |
| ------------------- | -------------------------------------------------------------------------------------------- |
| `reversible`        | Change can be rolled back with `git revert` and no state migration                           |
| `forward-only`      | Logic change that can't be trivially inverted (e.g., algorithm swap, new field with default) |
| `data-migrating`    | Database migration, schema change, data backfill — requires a down-migration to reverse      |
| `contract-breaking` | Protobuf, OpenAPI, or public API change — downstream consumers must be updated               |

Use the file path and content signals:

- Files under `migrations/`, `alembic/versions/`, `db/migrate/` → `data-migrating`
- Files named `*.proto`, `openapi.yaml`, `schema.graphql` with field removals/type changes → `contract-breaking`
- Dependency manifest changes → `forward-only`
- All others → `reversible` (default)

## 1.6 Compute cognitive-load metrics

Collect:

- `file_count`: total files in scope
- `diff_LOC`: total lines added + removed across the diff (run `git diff --stat` and sum the changes column)
- `distinct_concern_count`: number of distinct directories or top-level modules touched

These are passed to `scope.md` for Phase 3's cognitive-load budget calculation.

## 1.7 Write scope.md

Write `.mz/task/<task_name>/scope.md`:

```markdown
# Scope — Deep Audit

## Argument
- Raw: "<$ARGUMENTS>"
- Scope mode: branch / working / global

## Blast-Radius Tier
- **Overall tier**: T0 / T1 / T2 / T3
- Rationale: <which file(s) drove the highest tier and why>

## Files by Tier

### T3 — Regulated / Critical Infrastructure
- (none) / <file list>

### T2 — Security-Relevant
- (none) / <file list>

### T1 — Application Code
- (none) / <file list>

### T0 — Documentation / Tests / Config
- (none) / <file list>

## Trust Boundary Delta
*(T2+ only — empty at T0/T1)*

| File | Line | Boundary type | Pattern matched |
|------|------|---------------|-----------------|
| ... | ... | Auth | `OAuth2PasswordBearer` |

## Reversibility Map

| File | Class |
|------|-------|
| path/to/file.py | reversible |
| db/migrations/0042.py | data-migrating |

## Cognitive-Load Metrics
- File count: N
- Diff LOC: M
- Distinct concerns (top-level modules/dirs): K

## Findings Output Format

Each researcher saves findings to `.mz/task/<task_name>/findings_<lens>.md` using this structure:

### Finding N
- **File**: path/to/file:line
- **Severity**: critical | high | medium | low
- **Confidence**: high | medium | low
- **Evidence tier**: T0 | T1 | T2 | T3
- **Category**: <sub-category within the lens>
- **Description**: <one-paragraph explanation>
- **Evidence**: <code snippet or grep output>
- **Proposed fix**: <how to fix, or "needs investigation">
- **Cross-references**: <other interacting files>

### Lens summary
- Files scanned: N
- Findings by severity: critical=X, high=Y, medium=Z, low=W
- Skipped files (reason): <list>

## Severity Scale
- critical: data loss, security breach, or crash on common paths
- high: wrong results or crash on specific conditions
- medium: incorrect behavior in edge cases
- low: style/clarity issues that could mask future bugs

## Confidence Scale
- high: verified by reading the full code path
- medium: pattern matches known bug class but callers not fully traced
- low: suspicious pattern that may be intentional
```

Update state file phase to `scope_classified`.
