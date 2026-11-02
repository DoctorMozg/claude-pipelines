# Anti-Rationalization Library

Canonical source: guidelines/AGENTS_GUIDELINES.md, "Anti-Rationalization Tables" (in the repo checkout; not shipped with the plugin).

Seed rows for the `Rationalization | Rebuttal` tables in skills and agents. This file is a lookup catalog. Search it for the area heading or a keyword from the rule you are guarding, then copy only the rows whose excuse your agent actually makes, and drop the Source column. A seed row is a lead: keep it only once a run shows the agent making that excuse.

## Contents

- [When a table helps](#when-a-table-helps)
- [Format and placement](#format-and-placement)
- [Writing a row](#writing-a-row)
- [What the evidence shows](#what-the-evidence-shows)
- [Source tags](#source-tags)
- [Seed rows](#seed-rows)
  - [Tests and verification](#tests-and-verification)
  - [Debugging](#debugging)
  - [Review and severity](#review-and-severity)
  - [Status and artifacts](#status-and-artifacts)
  - [Approval gates](#approval-gates)
  - [Planning and commits](#planning-and-commits)
  - [Refactoring and cleanup](#refactoring-and-cleanup)
  - [Performance](#performance)
  - [Authoring skills and agents](#authoring-skills-and-agents)
- [Adding a row](#adding-a-row)

## When a table helps

Add a table when the skill or agent guards a rule that agents know and skip under pressure: running the tests again, labeling a finding `Critical:`, not reporting a failure as done. The rule being guarded decides this, not the skill's role. A reference skill that guards no such rule has no table.

A table is the wrong tool for output in the wrong shape. For that, write a positive output contract that says what the output is, part by part (obra/superpowers v6.0.0, "Match the Form to the Failure"). In that project's wording tests, a prohibition list produced more of the unwanted content than a recipe did. For example, when dispatch prompts keep pasting whole files:

- Instead of a row: `"Pasting the inventory is clearer than a pointer." | "It costs tokens; point to the file."`
- Write a contract: `The dispatch prompt holds the goal, what is already ruled out, the paths to read and the output path. It names files by path instead of pasting them.`

When the user explicitly chooses to skip a step, that is a decision, not a rationalization. State the risk once in the report and follow the choice.

## Format and placement

Two columns, each cell quoted:

```markdown
## Common Rationalizations

| Rationalization | Rebuttal |
| --- | --- |
| "The tests passed before this edit, no need to rerun." | "The edit can break them, and an unrun test is no evidence. Rerun and cite the output." |
```

- Put the table under `## Common Rationalizations`, or merge its rows into `## Red Flags`. In a skill, `## Common Rationalizations` sits after `## Techniques` and before `## Red Flags` (see `canonical-skill-anatomy.md`, "Sections"). In an agent, `## Red Flags` is the last body section and already lists the rationalizations the agent rejects (AGENTS_GUIDELINES.md, "Agent Body Anatomy").
- Include the section only when it has rows. Leave the heading out rather than writing `N/A` or a line that points elsewhere.
- There is no minimum row count. One row for a shortcut you have seen is worth more than three written to fill a table.

## Writing a row

- The excuse is the agent's own, in its own words, as seen in a run, a transcript or an eval. Excuses from the user don't go in the table.
- The rebuttal states a concrete cost, or the rule the step protects, by its substance. Name the rule by what it says, not by a rule or section number.
- Where it helps, the rebuttal ends with what to do instead ("Rerun and cite the output.").
- No invented statistics. A figure or threshold in a rebuttal needs a source the reader can check.

| Weak rebuttal                                           | Why it fails                                                        | Concrete rebuttal                                                                           |
| ------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| "Because it's best practice."                           | Names no cost                                                       | "An unrun test is no evidence. Rerun and cite the output."                                  |
| "Hot loops are 5% of the code and 80% of the CPU time." | Invented statistic                                                  | "Reading code doesn't tell you where time goes. Profile it and let the measurement decide." |
| "See the severity rule in the guidelines."              | Points at a rule instead of stating it; `guidelines/` isn't shipped | "If it blocks merge it's Critical; otherwise label it Nit, Optional or FYI."                |

## What the evidence shows

- **Rebuttal content matters.** In obra/superpowers v6.2.0 (2026-07-23), deleting the TDD skill's prose "Why Order Matters" rebuttals lowered test-first behavior under "tests after" pressure from 8 of 10 runs to 5 of 10, on Claude and Codex. The project then restored the rebuttals as table rows. This is a small maintainer eval, not a peer-reviewed study. It removed prose, not table rows, so it doesn't compare the table format with anything else.
- **The form follows the failure.** superpowers v6.0.0 (2026-06-16) scopes "prohibition + rationalization table + red flags" to an agent that "knows better, does it anyway". Its writing-skills guide adds that when a run without the guidance doesn't show the failure, there is nothing to fix.
- **No study isolates the tables.** Nothing measured supports calling them the most effective technique.
- **A prompt rule alone is weak against a shortcut the agent knows is invalid.** In BAITBENCH (arXiv 2608.30724, seven agents), a validity instruction cut reward hacking by about 6 percentage points against a base rate above 50%, and agents often submitted exploits they recognized as invalid. That tested one instruction, not a table, so it is indirect evidence. Treat a table as one layer: a rule that has to hold every time belongs in `tools` or `disallowedTools`, a permission rule, or a hook (AGENTS_GUIDELINES.md, "Agent/Hook Interface").

## Source tags

Each seed row carries one of these tags:

- `obra/superpowers v7.0.1` plus a file: the excuse appears in that upstream file.
- `guideline` plus a file and section: the rebuttal restates that section. `(observed)` means the guideline records the failure as seen in this repo; without it, the excuse itself is untraced.
- `observed` plus a path: seen in a recorded run, transcript or eval in this repo. No row carries this tag yet; new rows added the way [Adding a row](#adding-a-row) describes will.
- `repo convention`: written in this repo, with no run, transcript or eval on record. Most rows carried over from the earlier library are in this group. Before you copy one, check in a run that your agent actually makes the excuse.

## Seed rows

### Tests and verification

| Rationalization                                        | Rebuttal                                                                                                                                                       | Source                                                                        |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| "The tests passed before this edit, no need to rerun." | "The edit can break them, and an unrun test is no evidence. Rerun and cite the output."                                                                        | guideline: AGENTS_GUIDELINES.md, "Anti-Rationalization Tables"                |
| "I'll test after."                                     | "A test written after the code passes on its first run, which proves nothing. Write it first and watch it fail for the expected reason."                       | obra/superpowers v7.0.1, `skills/writing-skills/references/bulletproofing.md` |
| "Type-check is slow, skip."                            | "A type error the check would catch shows up later as a runtime failure that takes longer to trace. Type-check the files you touched and cite the output."     | repo convention                                                               |
| "Coverage is a vanity metric."                         | "Coverage doesn't show the tests are good, but an uncovered line is certainly untested. Read the uncovered paths and test the ones that carry logic."          | repo convention                                                               |
| "The test is flaky, just retry."                       | "A retry that passes hides the failure without explaining it. Record the failing output and find the cause, or report the test as flaky with that output."     | repo convention                                                               |
| "Fix works locally, done."                             | "Your machine isn't where it failed. Add a regression test that pins the behavior and run it the way the failing run did."                                     | repo convention                                                               |
| "The linter is too strict."                            | "Lint rules record decisions the project already made. Fix the finding. If a rule is wrong for this project, say so in the report rather than suppressing it." | repo convention                                                               |
| "I don't need types on this one."                      | "Each untyped exception makes the next one easier to justify. Add the types, or say in the report why this case can't have them."                              | repo convention                                                               |

### Debugging

| Rationalization                             | Rebuttal                                                                                                                         | Source          |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| "I know what the bug is, I'll just fix it." | "A bug diagnosed by reading tends to survive in a similar code path. Write the reproducer first, watch it fail, then fix."       | repo convention |
| "Can't reproduce, probably flaky."          | "'Flaky' names no cause. Record the conditions of each failing run and narrow them until the failure reproduces."                | repo convention |
| "The stack trace doesn't make sense."       | "The trace records what actually ran. When it contradicts your reading of the code, the reading is wrong somewhere; find where." | repo convention |

### Review and severity

| Rationalization                         | Rebuttal                                                                                                                       | Source                                                         |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------- |
| "This is just a nit, don't block."      | "Severity comes from impact, not size. If it blocks merge it's Critical; otherwise label it Nit, Optional or FYI and say why." | guideline: AGENTS_GUIDELINES.md, "Anti-Rationalization Tables" |
| "Severity is subjective, label later."  | "An unlabeled finding can't be weighed: the orchestrator can't tell whether it blocks. Label each finding now."                | repo convention                                                |
| "The PR is too big to review properly." | "That is a reason to recommend splitting it, not to skim it. Review what you can in full and list the files you didn't read."  | repo convention                                                |
| "One-pass scan is enough."              | "Each lens looks for a different class of defect. One pass covers one class and reports the rest as clean."                    | repo convention                                                |
| "Nobody will run into this edge case."  | "An edge case you skip is somebody's normal input. Test it, or list it as untested in the report."                             | repo convention                                                |

### Status and artifacts

| Rationalization                                               | Rebuttal                                                                                                                                                                                  | Source                                                                                          |
| ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| "I'll report DONE and mention the lint failure in passing."   | "DONE_WITH_CONCERNS exists for this. A buried failure costs the next phase a debugging round."                                                                                            | guideline: AGENTS_GUIDELINES.md, "Anti-Rationalization Tables"                                  |
| "The agent said it wrote the file, so the artifact is there." | "A denied write may not show up in the agent's report. Check that the artifact exists on disk before you use it; a missing artifact means the dispatch failed, whatever the report says." | guideline: AGENTS_GUIDELINES.md, "Structural Constraints" and "Anti-Pattern Catalog" (observed) |

### Approval gates

| Rationalization                                                               | Rebuttal                                                                                                                                                                                                                              | Source                                                      |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| "Findings look obvious, skip approval."                                       | "The gate sits before an expensive step so the user decides whether to pay for it. An obvious plan takes one selection to approve."                                                                                                   | repo convention                                             |
| "The plan is long; a path and a summary will do."                             | "The user approves the artifact as it stands. Emit it verbatim as a chat message; a path, line count or summary in its place is the failure this repo has seen."                                                                      | guideline: SKILL_GUIDELINES.md, "Approval Gates" (observed) |
| "Plan mode shows the plan in its dialog, so the plan can go in the selector." | "Gates borrow plan mode's loop, not its display. Here, a long artifact in the AskUserQuestion body has come back as a bare path or a one-line status. Put the artifact in the chat message and ask one line with Approve and Reject." | guideline: SKILL_GUIDELINES.md, "Approval Gates" (observed) |
| "The user typed 'looks good', so that's approval."                            | "Only the Approve option approves. Typed text is feedback: apply it, overwrite the artifact, re-emit the whole plan message and ask again."                                                                                           | guideline: SKILL_GUIDELINES.md, "Approval Gates"            |
| "No answer came back, so the preselected option counts."                      | "A missing answer is never approval, whatever option the result names. Set `Status: blocked`, keep `awaiting approval: <gate>` in `what_remains`, and stop."                                                                          | guideline: SKILL_GUIDELINES.md, "Approval Gates"            |

### Planning and commits

| Rationalization                    | Rebuttal                                                                                                                          | Source          |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| "The plan is fine without review." | "Review is where a missing integration point is cheap to fix. Found after coding starts, each one costs a code-and-review round." | repo convention |
| "One big commit is easier."        | "Small commits let `git bisect` find a regression in a few steps. Commit each working unit on its own."                           | repo convention |

### Refactoring and cleanup

| Rationalization                        | Rebuttal                                                                                                                                      | Source          |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| "Dead code is harmless, leave it."     | "Dead code costs every reader time and every agent context, and it hides which path is live. Delete it; git keeps the history."               | repo convention |
| "I'll just comment it out for now."    | "Commented-out code is dead code that still looks like a reference. Delete it and rely on git."                                               | repo convention |
| "Small refactor, skip the caller map." | "A small diff gets a light review, so a missed caller ships unnoticed. Find every caller and import before you change the signature."         | repo convention |
| "I know what this touches."            | "You know the call graph you remember. Search for the callers and imports, and work from the results."                                        | repo convention |
| "The tests will catch it."             | "Tests catch only what they cover. Check that each affected caller has a test, and list the ones that don't."                                 | repo convention |
| "Refactor is too risky to do now."     | "The longer it waits, the more code depends on the current shape. Name the specific risk and the check that would cover it."                  | repo convention |
| "The old code worked fine."            | "Working so far shows only that it handled the inputs it has seen. Check it against the case in front of you."                                | repo convention |
| "Tests are green, refactor can wait."  | "Green tests are the safe moment to refactor, because the suite will catch a behavior change. Later, more code depends on the current shape." | repo convention |
| "Good enough, ship."                   | "'Good enough' isn't one of the criteria. Show the check output for each criterion, or name the one that still fails."                        | repo convention |

### Performance

| Rationalization                                   | Rebuttal                                                                                    | Source          |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------- | --------------- |
| "This loop is fine."                              | "Reading code doesn't tell you where time goes. Profile it and let the measurement decide." | repo convention |
| "Premature optimization is the root of all evil." | "So is leaving a measured hot path alone. Profile first, then decide."                      | repo convention |

### Authoring skills and agents

| Rationalization                                                                  | Rebuttal                                                                                                                                                                                                                                                      | Source                                                                       |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| "Citing the rule number is shorter than restating the rule."                     | "Rule numbers change when a guideline is reorganized, and `guidelines/` doesn't ship with the plugin, so the citation goes stale unseen. State the substance, or name the guideline file and section title."                                                  | guideline: AGENTS_GUIDELINES.md, "No Rule-Number Citations"                  |
| "This rule matters, so I'll write it as `MUST` in capitals."                     | "Current Claude models over-apply emphasized rules. State it once as an obligation with its reason. If it has to hold every time, back it with `tools`, a permission rule or a hook."                                                                         | guideline: AGENTS_GUIDELINES.md, "Instruction Wording"                       |
| "Leaving an agent's `model` out, or writing `inherit`, lets the session decide." | "Both run the agent on the session's model at that model's cost, and in a Fable session on Fable. Set the tier the work needs; this repo doesn't allow `inherit`. A skill is different: it leaves `model:` out unless the whole run benefits from one model." | guideline: AGENTS_GUIDELINES.md, "Frontmatter Fields" and "Model and Effort" |

## Adding a row

1. Run the task without the guidance and record the agent's excuse verbatim, with where you saw it: the run, transcript or eval.
1. If that run doesn't show the shortcut, stop. There is nothing for a row to fix.
1. Write the rebuttal: the concrete cost or the rule by its substance, then, where it helps, what to do instead.
1. Add the row under the matching area heading, tagged `observed` with the path to the run or transcript.

A rebuttal that only says "because it is best practice" or "because the docs say so" gets rewritten until it names a cost or a failure.
