# Retry Policy

Canonical source: SKILL_GUIDELINES.md, "Error Handling and Escalation", and the repository CLAUDE.md, "Plugin Authoring Conventions" (repository guidelines, not shipped with the plugin).

What an orchestrator does when a dispatched agent returns nothing usable, when a loop reaches its cap, and when a search comes back empty. `agent-status-protocol.md` covers the four `STATUS:` values.

## An agent returns nothing usable

| What happened                                                          | What to do                                                                                                                                                                                               |
| ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| It is still running                                                    | Wait for its completion notification.                                                                                                                                                                    |
| Its output is marked partial (`maxTurns`)                              | Resume it once with `SendMessage` and say what is left. Explore and Plan agents can't be resumed; re-dispatch them once with a narrower task.                                                            |
| Its output is empty or malformed, or has no valid final `STATUS:` line | Re-dispatch once with something changed: a clarified prompt, a narrower scope or the missing input. Say what was wrong with the last output. The same prompt gets the same result.                       |
| It failed with an API error or a usage limit, or the user stopped it   | Don't resume or re-dispatch it. Claude Code already retries transient API errors, up to 10 times with exponential backoff, and a new dispatch doesn't refill a quota. Treat it as `BLOCKED` and say why. |
| The wave doesn't need its output                                       | Continue, and flag the gap in the wave summary and the final report.                                                                                                                                     |
| A tool call was denied                                                 | Don't retry the same call. In an interactive session the denial is the user's answer.                                                                                                                    |

A second empty or malformed result after the one re-dispatch is `BLOCKED`.

## Stalls and caps

- If the same check fails with the same error after two different fix attempts, change the approach or stop with `BLOCKED`, reporting the attempts and the last output.
- Every loop has a named cap in SKILL.md, with a reason. It keeps its counter in `state.md`, so a resumed run continues from it.
- At the cap, summarize the attempts and the last check output, and offer named options in a variant gate (`approval-gate.md`): **Accept** the current result and record what is unresolved, **Extend** by one more round, or **Abort**, which sets `Status: aborted_by_user`. Where nobody can answer, take the No-answer path: `Status: blocked`, with the cap and the options in `what_remains`.

## Zero results

An empty result is ambiguous: nothing exists, the query is wrong, or the agent has no access. Before trusting an empty result for a whole source, run one smoke test that should return something if the query path works. For GitHub that is a one-row listing of the repository's PRs in any state; for a web source it is a widened bare-keyword query. Each agent names its smoke test and what each outcome means. Then emit one disclosure token per empty source:

- `ZERO RESULTS VERIFIED`: the smoke test shows the empty result is real.
- `ZERO RESULTS UNVERIFIED`: the smoke test failed, was blocked, or left access in doubt. Say which.
- `ZERO RESULTS GLOBAL`: every source in the run came back empty, or the source itself is down. The agent returns `DONE_WITH_CONCERNS`.

The orchestrator reports a verified source as having nothing to show. It keeps an unverified source in the report with the reason instead of dropping it. On a global result, it skips the dispatches that depend on results, opens the report with a warning, and asks the user to check the inputs, such as the username, the repository list or the query.
