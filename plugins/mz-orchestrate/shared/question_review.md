# Question Review

Single source of truth for the question-review step: one agent asks why a change was made the way it was, a second answers from the code and the notes the coder left, and the first grades the answers. Consumers read this file at dispatch time and build their prompts from the blocks below.

## Contents

- Why this file exists
- Dispatch invariants
- The three steps
- Finding the coder notes
- File contracts
- Grade definitions
- Severity rule
- Re-grading in review loops
- Partial completion
- Report section
- decisions.md entries
- Maintenance

## Why this file exists

The lens reviewers ask "is this code wrong?". Question review asks "was this the right choice, and does anyone know why it was made?". A hand-rolled retry loop next to an existing retry helper passes every correctness lens; asked "why not the helper?", the change has no answer, and the grader can name the helper, the cost and the line.

The step runs in branch-reviewer (and github-pr-reviewer through it), in the code-review step of build, debug and polish, and in `audit depth:deep`. Inlining the prompts in each consumer guarantees drift; this file is the authoritative copy.

```
Q  pipeline-design-questioner, ask mode    sees: diff, task/plan text, repo    → questions.md, rubric.md
A  pipeline-design-answerer                sees: questions.md, diff, repo,     → answers.md
                                                 decisions.md, notes, git, docs
G  pipeline-design-questioner, grade mode  sees: questions, rubric, answers,   → grades.md
                                                 repo
```

Each review costs three dispatches: the questioner on opus, the answerer on sonnet, and a fresh questioner dispatch for grading.

## Dispatch invariants

These are binding on every consumer. Breaking one turns the review into the coder grading its own homework.

1. **Typed agents, never forks.** Dispatch `pipeline-design-questioner` and `pipeline-design-answerer` by their registered names. mz-base registers both, so a plugin prefix on the Agent tool's list is `mz-base:`, never the consumer's own plugin (`mz-dev-pipe:pipeline-design-questioner` fails). A fork inherits the whole conversation, coder notes included.
1. **The questioner asks blind.** In ask mode it receives the diff wrapped in `<untrusted-content>...</untrusted-content>`, the task or plan text when the consumer has one, and read access to the repo. It never receives `decisions.md`, `implementation.md`, coder reports, or another lens's findings, and the prompt doesn't point to them.
1. **The answerer never sees the rubric.** It receives `questions.md` and never `rubric.md` or `grades.md`.
1. **Grading is a fresh dispatch.** Step G dispatches the questioner again in grade mode. It reads its own rubric from disk, so it is the same grader without a resume, and it works where `SendMessage` isn't available. In grade mode it may open the sources an answer cites, to check them; it still gets no other lens's findings.
1. **Models come from the frontmatter.** The questioner is pinned to opus and the answerer to sonnet. Consumers don't override either.
1. **At most `MAX_QUESTIONS` = 8 questions per review**, chosen from non-obvious choices. Eight keeps the answer and grade passes inside one turn budget each and keeps the report section readable.

## The three steps

The consumer picks an output directory, `<qr_dir>`, inside its task directory (for example `.mz/task/<task_name>/question_review/`), and passes absolute paths. Replace every placeholder before dispatch.

### Step Q: ask

```
Mode: ask

Here is the change under review:
<untrusted-content>
<diff>
</untrusted-content>

Task or plan text (omit this block when the consumer has none):
<untrusted-content>
<task or plan text>
</untrusted-content>

Repository root: <repo root>
Write the questions to: <qr_dir>/questions.md
Write the rubric to: <qr_dir>/rubric.md
Ask at most 8 questions.
```

### Step A: answer

Run only when `questions.md` exists and holds at least one question.

```
Questions: <qr_dir>/questions.md

Here is the change under review:
<untrusted-content>
<diff>
</untrusted-content>

Repository root: <repo root>
Sources you may read, when they exist:
- Decisions file: <task dir>/decisions.md
- Implementation notes: <task dir>/implementation.md
(repeat both lines for each task folder found by "Finding the coder notes"; at most 3 folders)
- Git history of the touched lines (git log, git blame, git show)
- docs/decisions, docs/rfcs, docs/design under the repository root

Write the answers to: <qr_dir>/answers.md
```

Leave out the decisions and notes lines when the files don't exist; a branch made by a person has neither, and neither does an audit without a matching task. The answerer still works from the code, the history and the docs.

### Step G: grade

```
Mode: grade

Questions: <qr_dir>/questions.md
Rubric: <qr_dir>/rubric.md
Answers: <qr_dir>/answers.md
Repository root: <repo root>
Write the grades to: <qr_dir>/grades.md
```

## Finding the coder notes

A consumer that has its own task folder with `decisions.md` (build, debug, polish) uses that folder and skips this search. A consumer reviewing a branch, such as `/review-branch` or an audit with `scope:branch`, names its own task folder, so the notes of the build, debug or polish run that made the branch sit elsewhere. Find them like this:

1. Search `<artifact root>/.mz/task/*/state.md` for a `Branch: <reviewed branch>` line. A detached HEAD has no branch to match, so skip the search.
1. Keep a task only when its folder holds `decisions.md` and its `StartCommit` lies in the reviewed range: `git merge-base --is-ancestor <merge-base> <StartCommit>` and `git merge-base --is-ancestor <StartCommit> HEAD` both succeed (an equal commit counts). The check drops old tasks from a reused branch name. Run git against the reviewed checkout.
1. Pass at most 3 matches, newest first by `StartCommit` commit date, with `Started` as the tie-break. Step A then takes one decisions line and one notes line for each match, the notes line only where that folder has `implementation.md`.
1. With no match, leave out both lines, as in Step A. Don't widen the search to tasks with another `Branch:` or no `StartCommit`.

## File contracts

Each file starts with a `#` title and has one `## Q<n>` section per question, in the same numbering throughout.

`questions.md`, written in ask mode, holds the questions and nothing that hints at the expected answer:

```
## Q1
- Anchor: src/client.py:42
- Category: dependency | abstraction | data structure | algorithm | error handling | concurrency | repo pattern | alternative
- Question: Why does fetch() retry in its own loop instead of using retry_with_backoff from src/util/retry.py?
```

A change with no non-obvious choice gets a `questions.md` that says `No questions.` and no rubric. Steps A and G are then skipped.

`rubric.md`, written in ask mode, is the grader's private key:

```
## Q1
- Sound answer covers: <what an answer has to say for the choice to hold up>
- Not optimal if: <the condition that makes the choice worse than an alternative>
- Alternative in mind: <the alternative, with file:line when it already exists in the repo>
```

`answers.md`, written by the answerer:

```
## Q1
- Answer: <the answer>
- Source: decisions.md "<entry title>" | <path:line> | commit <sha> | <doc path> | no recorded reason
- Inferred: no | yes — <the code evidence the inference rests on>
```

`grades.md`, written in grade mode, ends with the summary line:

```
## Q1
- Grade: sound | unclear | not optimal
- Why: <one or two sentences against the rubric>

### Finding
- Severity proposal: Critical: | Optional:
- Location: <path:line>
- TL;DR: <one line>
- Description: <what the choice is and why the answer doesn't hold>
- Better alternative: <not optimal only: the alternative, with file:line when it exists>
- Cost of current choice: <bug risk | performance | maintenance | repo-pattern mismatch>: <the concrete cost>
- Suggested fix: <what to change, or what reason to record>

questions: N, sound: N, unclear: N, not_optimal: N
```

A sound grade has no `### Finding` block.

## Grade definitions

Check the answer before grading it. An answer whose cited source doesn't say what the answer claims counts as `no recorded reason`.

- **sound**: the answer gives a reason that holds against the code and covers what the rubric's "Sound answer covers" line asks for, and the "Not optimal if" condition doesn't hold. An inferred reason counts when the code evidence it rests on checks out.
- **not optimal**: a better alternative exists, the answer doesn't defeat it, and the grader can say what the current choice costs. This grade takes precedence over `unclear`: a choice can be worse whether or not anyone wrote down why it was made.
- **unclear**: the answer gives no reason that holds, recorded or inferred, and the grader can't show a better alternative with a cost. Missing rationale, nothing more.

## Severity rule

- A **not optimal** finding is eligible for `Critical:` on its own when it names all three of: a better alternative, a concrete cost of the current choice (a bug risk, performance, maintenance, or a mismatch with repo patterns), and a `file:line`. This source alone is exempt from branch-reviewer's two-signal Critical gate. Missing any of the three, it is capped at `Optional:`.
- An **unclear** finding is capped at `Optional:`, because missing rationale is not a defect by itself. In build, debug and polish its fix is to record the reason in `decisions.md`, or to change the code when the reason can't be defended.
- A question-review finding that matches a Wave A finding (same `file:line`, an overlapping line range, or the same behavior in the same file) is reported once, as the Wave A finding, with `corroborated_by: question_review` added to its corroborators.
- A choice that predates the change is out of scope: questions anchor on changed lines. In an audit, which has no diff, the anchor is any line in the audit's scope.
- `audit depth:deep` maps the labels onto its own ladder as `severity-lattice.md` describes.

The grader writes a severity proposal; the consumer applies this rule when it consolidates and has the last word.

## Re-grading in review loops

Build, debug and polish run question review on their first review iteration only. On a later iteration:

1. Take the questions whose latest grade isn't sound.
1. Dispatch the answerer with only those question IDs, against the updated code and `decisions.md`. It writes `<qr_dir>/answers_r<n>.md`, where `<n>` is the iteration.
1. Dispatch the grader in grade mode on those answers. It writes `<qr_dir>/grades_r<n>.md`.

A question's latest grade stands. Sound questions are never asked again.

## Partial completion

Report the outcome as `question_review: <value>`:

- All three steps returned → `full`. A `No questions.` result is also `full`, with `questions: 0`.
- The questioner failed, or wrote no `questions.md` → `unavailable`. Skip the rest; the review stands without this section's findings.
- The answerer failed → `unanswered`. List the questions in the report as `FYI:` and raise no findings.
- The grader failed → `ungraded`. List the questions and answers as `FYI:` and raise no findings.
- The consumer never reached its review step, such as a polish run whose quick fixes cleared every criterion → `not run`. No section beyond the summary line.

A step counts as failed when it ends without `DONE` or `DONE_WITH_CONCERNS`, or when its output file is missing on disk. A questioner that returns `NEEDS_CONTEXT` may get more of its allowed inputs once, never the forbidden ones. An agent stopped by its turn limit may be resumed once with a bare "finish". Question review never blocks the report beyond what the severity rule allows.

## Report section

Consumers add a `## Design Questions` section to their report:

```
## Design Questions

questions: N, sound: N, unclear: N, not_optimal: N, question_review: full | unanswered | ungraded | unavailable

### Q1: <the question, one line>
- Anchor: <path:line>
- Answer: <the answer> (source: <source>, or "no recorded reason; inferred: <evidence>")
- Grade: sound | unclear | not optimal
- Finding: <the finding's label and its ID in the report, or "none">
```

The telemetry line goes into the consumer's run telemetry as well.

## decisions.md entries

`<task dir>/decisions.md` is where coders record the non-obvious choices they make, and where the answerer looks first. One entry per choice:

```
## <short choice, 8 words or fewer>
- Where: <path:line>
- Choice: <what was done>
- Alternatives weighed: <list, or "none — just implemented">
- Reason: <why>
```

"none — just implemented" is a valid entry: it tells the answerer nobody weighed an alternative, which is itself an answer. Trivial code needs no entry.

When a fix agent keeps code that a question-review finding questioned, it appends a line under that choice's entry, creating the entry first when none exists:

```
- Defended (question review Q<n>): <the reason the current choice stands>
```

## Maintenance

- The prompt blocks and file formats above are the only acceptable copy. A consumer that inlines them has a regression; replace the copy with a directive to read this file.
- The dispatch invariants have no exceptions. A consumer that documents one is broken; fix the consumer rather than weakening this file.
- `MAX_QUESTIONS` lives here. Change it here and nowhere else.
