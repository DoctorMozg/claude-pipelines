# Severity Lattice — Single Source of Truth

Canonical severity vocabulary and finding-cap policy for every mz-dev-pipe skill that reports findings (`audit` in both `depth:standard` and `depth:deep` modes, `verify`, and any future scanner). Replaces the per-skill cap declarations that previously diverged across files.

## Severity levels

Six fixed levels, ordered most-severe → least-severe:

| Level      | Definition                                                                                                         |
| ---------- | ------------------------------------------------------------------------------------------------------------------ |
| `BLOCKING` | Ship-stopper. Data-loss risk, unrecoverable migration, missing rollback story. MUST be resolved before merge.      |
| `CRITICAL` | Confirmed exploit, confirmed correctness defect on a hot path, confirmed broken core invariant. SHOULD ship-block. |
| `HIGH`     | Likely exploit, plausible correctness defect under realistic conditions, significant performance regression.       |
| `MEDIUM`   | Maintainability burden, design-smell with known fix, minor correctness defect on a cold path.                      |
| `LOW`      | Style nit, micro-optimization, opinionated refactor opportunity.                                                   |
| `INFO`     | Observation with no required action — pattern note, prior-art reference, telemetry suggestion.                     |

Skills MUST use these exact tokens (uppercase, no synonyms). Any other label (`major`, `severe`, `urgent`, `nit`, `trivial`) is a contract violation — re-classify into one of the six.

## Cap modes

A cap mode controls how many findings of each severity make it into the final report. Two named modes:

### `quick` (default for `/audit`)

| Severity   | Cap                                                 |
| ---------- | --------------------------------------------------- |
| `BLOCKING` | ∞                                                   |
| `CRITICAL` | ∞                                                   |
| `HIGH`     | top 10                                              |
| `MEDIUM`   | top 5                                               |
| `LOW`      | 0 (count only — listed in summary, not report body) |
| `INFO`     | 0                                                   |

Optimized for "show me the things I'd actually fix today". Anything above HIGH cap-10 is dropped to keep the report scannable.

### `pre-PR` (default for `/audit depth:deep`)

| Severity   | Cap            |
| ---------- | -------------- |
| `BLOCKING` | ∞              |
| `CRITICAL` | ∞              |
| `HIGH`     | ∞              |
| `MEDIUM`   | top 10         |
| `LOW`      | 0 (count only) |
| `INFO`     | 0              |

Optimized for "I'm about to ship — I want every HIGH visible". Cap relaxes one tier so the reviewer cannot hide behind "we capped at 10 HIGHs".

## Sorting within a severity

When a cap forces selection (e.g., HIGH cap-10), rank by:

1. `confidence` (high > medium > low)
1. `evidence_tier` (T0 reproducible > T1 grep-confirmed > T2 inferred)
1. `blast_radius` (impacted-file count from `shared/blast-radius.md`)
1. Alphabetical by file path (deterministic tiebreaker)

Top-N after sort is the reported set. Items below the cap are summarized as `<count> additional <severity> findings (capped)` in the report header.

## Override precedence

Skills that need to widen or tighten a cap MAY override at task start in this order:

1. **Environment variable** — `MZ_DEV_PIPE_HIGH_CAP=20`, `MZ_DEV_PIPE_MEDIUM_CAP=0`, etc.
1. **Project config** — `.mz/config.toml` `[severity_caps]` table.
1. **Skill default** — `quick` or `pre-PR` per the table above.

Document the resolved cap set in `state.md` once at task start; never re-resolve mid-report.

## Why a single lattice

Before this module, `audit` (standard) capped HIGH at 10 with no BLOCKING tier and `audit depth:deep` capped HIGH at unlimited with a BLOCKING tier — incommensurable. Cross-comparing two reports required mental translation. Now both depth modes produce findings on the same lattice with the same sort key; only the cap mode differs. Report consumers can compare a `quick` report to a `pre-PR` report and trust the severity column means the same thing in both.
