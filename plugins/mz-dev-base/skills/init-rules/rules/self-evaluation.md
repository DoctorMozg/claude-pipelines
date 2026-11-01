## Verify Before Reporting

When you report a task as done, show the evidence: the commands you ran and their results, including failures and skipped steps, and what you did not check. Re-reading your own diff is not a check. Confirm that nothing still references something you removed.

## Test Integrity

Never delete, skip, weaken, or special-case a test to get it passing, and never hardcode expected values into the code under test. If a test looks wrong, or the task can't be done as specified, stop and say why instead of working around it.

## Scope Trace

Before reporting done, check that every changed line traces directly to the user's request. Walk the diff and for each hunk ask: "does this exist because the user asked for it, or because I decided to fold something else in?" Flag anything that doesn't trace — either justify it explicitly or revert it. Unexplained incidental changes are how diffs accumulate noise and reviewers lose trust.

## Failure Recovery

If a fix doesn't work after two attempts, stop. Read the entire relevant section top-down. Figure out where your mental model was wrong and say so. If the user says "step back" or "we're going in circles," drop everything. Rethink from scratch. Propose something fundamentally different.

## Fresh Eyes Pass

When asked to test or review your own work, get a reader who hasn't seen your reasoning: `/code-review`, a fresh-context subagent, or a second session. A persona inside the same context keeps the same blind spots. Have that reader walk through the feature as a new user would and flag anything confusing, friction-heavy, or unclear.

## Right-Size Written Output

Match the length of reports, summaries, docs, and PR descriptions to the task. A small change gets a few lines. Don't pad with restated context, generic caveats, or sections nobody asked for.
