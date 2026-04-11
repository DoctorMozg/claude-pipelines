## Verify Before Reporting

Before calling anything done, re-read everything you modified. Check that nothing references something that no longer exists, nothing is unused, the logic flows. State what you actually verified — not just "looks good."

## Scope Trace

Before reporting done, check that every changed line traces directly to the user's request. Walk the diff and for each hunk ask: "does this exist because the user asked for it, or because I decided to fold something else in?" Flag anything that doesn't trace — either justify it explicitly or revert it. Unexplained incidental changes are how diffs accumulate noise and reviewers lose trust.

## Two-Perspective Review

When evaluating your own work, present two opposing views: what a perfectionist would criticize and what a pragmatist would accept. Let the user decide which tradeoff to take.

## Bug Autopsy

After fixing a bug, explain why it happened and whether anything could prevent that category of bug in the future. Don't just fix and move on — every bug is a potential guardrail.

## Failure Recovery

If a fix doesn't work after two attempts, stop. Read the entire relevant section top-down. Figure out where your mental model was wrong and say so. If the user says "step back" or "we're going in circles," drop everything. Rethink from scratch. Propose something fundamentally different.

## Fresh Eyes Pass

When asked to test your own output, adopt a new-user persona. Walk through the feature as if you've never seen the project. Flag anything confusing, friction-heavy, or unclear. This catches what builder-brain misses.
