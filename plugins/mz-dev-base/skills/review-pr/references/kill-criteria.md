# Kill Criteria — Multi-Lens PR Review

**Status**: active (multi-lens fan-out enabled in branch-reviewer Phase 3).

## Numeric thresholds (pre-registered)

Source: `.mz/reports/2026_04_13_expert_pr_reviewer_multi.md` (expert panel R3 convergence).

| Metric               | Kill threshold                     | Measurement window |
| -------------------- | ---------------------------------- | ------------------ |
| precision@critical   | < +10pp over single-agent baseline | Rolling 20 PRs     |
| p95 wallclock        | > 120 seconds on diffs \<= 500 LOC | Rolling 20 PRs     |
| cost p95             | > 2.5x single-agent baseline       | Rolling 20 PRs     |
| consolidator failure | > 1% of dispatches                 | Rolling 100 runs   |
| lenses_dropped       | > 5% of runs                       | Rolling 100 runs   |

If any threshold fires, **disable the multi-lens path** (see Rollback mechanism below) pending a named owner's decision.

## Retro requirement

A 20-PR labeled retro with an **independent labeler** (not on the team that built the multi-lens pipeline) must run before declaring the feature stable. The retro spec lives in `eval/pr_review_v1.md` (to be created when the retro runs) and must pre-register: corpus hash, labeler identity, TP definition, scoring function, baseline precision@critical, decision threshold, date.

## Calendar trigger

Review date: TBD — set to 6 months after the first production PR reviewed via the multi-lens path.

## Owner

TBD — must be a maintainer **independent** of the builder(s) of this pipeline. Name assigned at first production dispatch.

## Rollback mechanism

Revert `pr-reviewer.md` to the pre-multi-lens contract: restore the legacy three-stage in-agent analysis (recover from git history at commit preceding this pipeline's merge) and remove `branch-reviewer` from its `tools:` allowlist. The lens agent files and `branch-reviewer` fan-out remain in place so the feature can be re-enabled via a single frontmatter + Phase-2 edit once thresholds recover.
