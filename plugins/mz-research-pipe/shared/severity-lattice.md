# Severity Lattice — Single Source of Truth

Canonical severity vocabulary and finding-cap policy for the `audit` skill, in both `depth:standard` and `depth:deep` modes. Only audit uses this file. It replaces the per-skill cap declarations that previously diverged across files.

## Severity levels

Six fixed levels, ordered most-severe → least-severe:

| Level      | Definition                                                                                                       |
| ---------- | ---------------------------------------------------------------------------------------------------------------- |
| `BLOCKING` | Ship-stopper. Data-loss risk, unrecoverable migration, missing rollback story. Resolve before merge.             |
| `CRITICAL` | Confirmed exploit, confirmed correctness defect on a hot path, confirmed broken core invariant. Blocks shipping. |
| `HIGH`     | Likely exploit, plausible correctness defect under realistic conditions, significant performance regression.     |
| `MEDIUM`   | Maintainability burden, design-smell with known fix, minor correctness defect on a cold path.                    |
| `LOW`      | Style nit, micro-optimization, opinionated refactor opportunity.                                                 |
| `INFO`     | Observation with no required action — pattern note, prior-art reference, telemetry suggestion.                   |

Use these exact tokens (uppercase, no synonyms). Any other severity word (`major`, `severe`, `urgent`, `trivial`) isn't on the ladder — re-classify into one of the six.

### Mapping to review labels

The audit has no gate, so it keeps this ladder. It maps onto the four review labels (`Critical:`, `Nit:`, `Optional:`, `FYI:`) like this, for any finding that leaves the audit, such as a hand-off to another agent:

| Level                  | Review label                                                                  |
| ---------------------- | ----------------------------------------------------------------------------- |
| `BLOCKING`, `CRITICAL` | `Critical:`                                                                   |
| `HIGH`                 | `Critical:` when it names a location and a concrete failure, else `Optional:` |
| `MEDIUM`               | `Optional:`                                                                   |
| `LOW`                  | `Nit:`                                                                        |
| `INFO`                 | `FYI:`                                                                        |

## Cap modes

A cap mode controls how many findings of each severity appear in the report body. Findings over a cap aren't dropped: they go to the appendix `findings_capped.md`, next to the report. Two named modes:

### `quick` (default for `/audit`)

| Severity   | Cap                                               |
| ---------- | ------------------------------------------------- |
| `BLOCKING` | ∞                                                 |
| `CRITICAL` | ∞                                                 |
| `HIGH`     | top 10                                            |
| `MEDIUM`   | top 5                                             |
| `LOW`      | 0 (counted in the report, listed in the appendix) |
| `INFO`     | 0 (counted in the report, listed in the appendix) |

Optimized for "show me the things I'd actually fix today". Findings past the HIGH cap of 10 go to the appendix, which keeps the report body scannable.

### `pre-PR` (default for `/audit depth:deep`)

| Severity   | Cap                                               |
| ---------- | ------------------------------------------------- |
| `BLOCKING` | ∞                                                 |
| `CRITICAL` | ∞                                                 |
| `HIGH`     | ∞                                                 |
| `MEDIUM`   | top 10                                            |
| `LOW`      | 0 (counted in the report, listed in the appendix) |
| `INFO`     | 0 (counted in the report, listed in the appendix) |

Optimized for "I'm about to ship — I want every HIGH visible". Cap relaxes one tier so the reviewer cannot hide behind "we capped at 10 HIGHs".

## Sorting within a severity

When a cap forces selection (e.g., HIGH cap-10), rank by:

1. `confidence` (high > medium > low)
1. `evidence_tier` (T0 reproducible > T1 grep-confirmed > T2 inferred)
1. `blast_radius` (impacted-file count from `<PLUGIN_ROOT>/shared/blast-radius.md`)
1. Alphabetical by file path (deterministic tiebreaker)

Top-N after sort is the reported set. Items below the cap are written to `findings_capped.md` in the same order, and the report header says `<count> additional <severity> findings (capped, see findings_capped.md)`.

## Where the caps live

The caps are constants in audit's `SKILL.md` (`HIGH_CAP`, `MEDIUM_CAP`, `LOW_CAP`), each with its reason. Change them there and keep the tables above in step.

## Why a single lattice

Before this module, `audit` (standard) capped HIGH at 10 with no BLOCKING tier and `audit depth:deep` capped HIGH at unlimited with a BLOCKING tier — incommensurable. Cross-comparing two reports required mental translation. Now both depth modes produce findings on the same lattice with the same sort key; only the cap mode differs. Report consumers can compare a `quick` report to a `pre-PR` report and trust the severity column means the same thing in both.
