# Iteration Limits — Single Source of Truth

Canonical bounds for every retry / fix / verify loop in mz-dev-pipe skills. Skills MUST resolve their iteration cap through this module, not hardcode in SKILL.md or phase files. Replaces the ~12 hardcoded sites that previously drifted independently.

## Resolution precedence

When a skill needs an iteration cap, it resolves in this order, taking the first hit:

1. **Environment variable** — `MZ_DEV_PIPE_<NAME>` (e.g., `MZ_DEV_PIPE_MAX_FIX_ITERATIONS=10`). Skill-prefixed forms take precedence over bare names — `MZ_DEV_PIPE_DEBUG_MAX_FIX_ITERATIONS=10` overrides only `debug`.
1. **Project config** — `.mz/config.toml` `[iteration_limits]` table. Skill-scoped sub-tables (`[iteration_limits.debug]`) take precedence over top-level keys.
1. **Skill default** — the value from the table below.

The resolved value MUST be written to `state.md` once at task start under `## Resolved iteration limits` and never re-resolved mid-loop. On resume, read from `state.md`, do not re-resolve — environment may have changed between runs.

## Canonical names + skill defaults

| Name                        | Skill               | Default | What it bounds                                                    |
| --------------------------- | ------------------- | ------- | ----------------------------------------------------------------- |
| `MAX_RED_ITERATIONS`        | build               | 2       | RED-verify retries when tests unexpectedly pass against zero impl |
| `MAX_GREEN_ITERATIONS`      | build               | 3       | GREEN coder retries when tests still fail after implementation    |
| `MAX_REVIEW_ITERATIONS`     | build, cleanup      | 3       | Code-review fix-and-rerun cycles                                  |
| `DEBUG_MAX_FIX_ITERATIONS`  | debug               | 3       | Debug fix-verify cycles before escalation                         |
| `POLISH_MAX_FIX_ITERATIONS` | polish              | 5       | Polish fix-test-review cycles before escalation                   |
| `MAX_FIX_ATTEMPTS`          | cleanup             | 3       | Per-chunk fix attempts in the cleanup review loop                 |
| `MAX_APPROVAL_ITERATIONS`   | translate, build    | 3       | Approval-gate revision rounds before escalation                   |
| `MAX_PARALLEL_TRANSLATORS`  | translate           | 6       | Cap on concurrent translator agents per wave                      |
| `MAX_OPTIMIZERS`            | cleanup             | 6       | Cap on concurrent optimizer agents per wave                       |
| `MAX_REVIEWERS`             | cleanup             | 6       | Cap on concurrent reviewer agents per wave                        |
| `MAX_VERIFICATION_ATTEMPTS` | translate           | 2       | Tier-1 + Tier-3 verification retries per chunk                    |
| `MAX_BLAST_DEPTH`           | shared/blast-radius | 3       | Transitive-import depth before truncating blast-radius result     |
| `MAX_BLAST_FILES`           | shared/blast-radius | 200     | File-count truncation cap for blast-radius result                 |

## Why two `MAX_FIX_ITERATIONS`-flavored rows

`debug` and `polish` both call their primary loop "fix iterations" but bound different work — debug is a single-bug fix-verify cycle; polish is a multi-criterion fix-test-review cycle. Different defaults are intentional. To resolve the ambiguity at lookup time, the canonical names are skill-prefixed (`DEBUG_MAX_FIX_ITERATIONS`, `POLISH_MAX_FIX_ITERATIONS`), and the bare `MAX_FIX_ITERATIONS` env var (no prefix) overrides BOTH.

## Cap-reached escalation

Every loop using one of these caps MUST follow the same escalation pattern when it hits the cap:

1. Stop the loop without re-running.
1. Write `cap_reached: <NAME>` to `state.md`.
1. Invoke `AskUserQuestion` with three options:
   - **Continue (extend cap)** → ask for additional iterations as a one-time bump; do not change the default.
   - **Accept current state** → mark the loop's outcome as partial in `state.md` and proceed.
   - **Abort task** → write `Status: failed` and stop.

This pattern is referenced from `shared/retry-policy.md`. Loops MUST NOT silently exit at the cap — that defeats the resume contract.

## Why a single source of truth

Before this module, `MAX_REVIEW_ITERATIONS=3` appeared in `build/SKILL.md` constants block, `cleanup/SKILL.md` constants block, `build/phases/implementation_and_review.md` inline, `cleanup/phases/review_and_finalize.md` inline, and `state-schema.md` example. A change to the cap required hunting all sites; misses were silent. Now the cap is set in one place and skills cite by name.
