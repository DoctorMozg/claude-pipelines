# Approval Gates

Canonical source: SKILL_GUIDELINES.md, "Approval Gates" (repository guidelines, not shipped with the plugin).

Every approval gate shows the artifact as an ordinary markdown chat message (Surface 1) and asks for the decision with a short AskUserQuestion selector (Surface 2). The user approves, rejects, or keeps sending feedback until satisfied.

## Where gates go

Put a gate before an irreversible or expensive step, such as changing code, launching a large agent wave, or sending something outside the repository. Web research runs without a gate, and read-only skills such as `explain` need none.

## Elements, in order

1. **Delegation guard.** `**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.` Custom subagents don't get AskUserQuestion, and the answer has to reach the orchestrator that acts on it.
1. **Pre-read.** Read the artifact by its exact path and capture its full contents, for example `Read <PROJECT_ROOT>/.mz/task/<task_name>/plan.md and capture the full contents`.
1. **State first.** Write `state.md` before presenting the gate: the phase, the artifact path, and a `what_remains` entry `awaiting approval: <gate>`. `Status` stays `running` while the gate waits. The conversation can compact while it waits, and `state.md` is what survives.
1. **Surface 1, the plan message.** A normal chat message, not a tool call, holding the artifact verbatim (template below). Don't replace the body with a path, a line count, a status summary or a placeholder.
1. **Surface 2, the selector.** Call AskUserQuestion right after the plan message. `question` is one line pointing at the message above, such as `The plan above is ready for review.`, and doesn't repeat the artifact. `header` is at most 12 characters. The options are exactly **Approve** and **Reject**. There's no Feedback option, because the user can always type an answer.
1. **Response handling**, below.
1. **Journal entry**, recommended, below.

## Plan message template

```text
## Plan for review: <skill name>

<verbatim artifact contents>

---
**Approve** → <what happens next>  ·  **Reject** → <abort outcome>  ·  reply with feedback to revise
```

A gate may add one cost line under the footer:

```text
Approve cost (estimated): <N> agents × ~<X>k tokens ≈ ~$<Y.YY> on <model tier>
```

`<N>` counts the dispatches between this gate and the next one. `<X>k` is a rough per-agent budget for the dominant agent type. `<Y.YY>` is `<N> × <X> × <price per million tokens> / 1000`, using the dominant tier's price, and `<model tier>` names that tier, or `mixed`. The estimate is order-of-magnitude: its job is to make a 30-agent fan-out look different from a 3-agent one. For a variant gate, estimate the most likely option and add `Cost varies by selection; estimate shown for <option>`.

## Selector

```text
question: "The plan above is ready for review."
header: "<12 chars max>"
options:
  - Approve — <what happens next>
  - Reject — <abort outcome>
```

## Response handling

- **Approve**: record the approved artifact path in `state.md` as a `## Decisions` line, such as `- plan approved: .mz/task/<task_name>/plan.md`. Remove the `awaiting approval` entry and proceed. The journal hook sees only the one-line selector, so `state.md` is the record of what was approved. A milestone such as `plan_approved` goes in `Phase`, not in `Status`.
- **Reject**: set `Status: aborted_by_user` and stop. Don't dispatch another agent.
- **Any other answer is feedback.** That includes typed text, a "Chat about this" reply, and an Approve whose note asks for a change. Apply the feedback, and run the upstream phase or agent again when the change needs it. Overwrite the artifact, re-read it, and re-emit the whole plan message from scratch before presenting the selector again. Don't send a diff or a summary. The user approves the artifact as it now stands, and after compaction earlier versions survive only as a summary. The gate loops until the user explicitly approves.
- **No answer.** AskUserQuestion is denied or unavailable in `dontAsk` mode, in `claude -p` without a permission host, with `--permission-prompts none`, and in `claude -p --channels`. With the opt-in `askUserQuestionTimeout`, a result can also carry the away signal while naming the preselected option. Neither case is approval, whatever option the result names. Set `Status: blocked`, keep `awaiting approval: <gate>` in `what_remains`, leave the plan message in place, and stop.

A missing answer is never approval.

## Variant gates

A variant gate offers more actions than Approve and Reject. AskUserQuestion takes 2-4 options per question. Each option's `label` is the action name and comes back as the answer, and its `description` is one sentence. Present each action as `**<Name>** — <one-sentence summary>`, both in the options and in the Surface 1 footer. With more than four actions, keep the four most common as options and list the rest in the footer as typed replies. Or ask in two calls: first the category, then the action. Feedback still rides the typed answer.

The resume gate, a cap-reached menu and any other gate that asks for a choice rather than a sign-off count as variant gates.

## Unattended mode

A user opts in to unattended runs, for CI or scheduled jobs, by setting `MZ_DEV_PIPE_AUTO_APPROVE=1`. Skills don't turn it on themselves.

- During setup, check the variable once with a Bash call, such as `printenv MZ_DEV_PIPE_AUTO_APPROVE`, and record the result in `state.md` as `unattended: true` or `unattended: false`.
- At an Approve/Reject gate, still write state first and emit Surface 1. Then skip Surface 2 and continue as on Approve.
- Log every skipped gate in four places:
  - a chat line, `auto-approved (unattended): <gate>`;
  - a line under `## Auto-approvals` in `state.md`, with the gate label, the phase and the UTC time;
  - a journal entry (below);
  - the final report, which lists every `## Auto-approvals` entry.
- Variant gates don't auto-approve, because they need an explicit choice. In an unattended run they take the No-answer path.

## Journal entry

After the gate resolves, append an entry to `<PROJECT_ROOT>/.mz/journal.md`. `<PROJECT_ROOT>` is the absolute project root the skill resolved during setup, `${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}`. Don't append to a path relative to the Bash working directory. When mz-memory is installed, its hook records the selector's question and answer but never the artifact. Journaling never delays the gate.

The entry is a header line, a blank line, then `- key: value` bullets, one key per bullet:

- The header is `### <UTC time> · <skill> · <task_name> · gate`, with the time from `date -u +%Y-%m-%dT%H:%M:%SZ`.
- `phase`, `gate` (the label) and `outcome`. The outcome is `approve`, `reject`, `feedback`, `no answer` or `auto-approved (unattended)`.
- `artifact`: the path relative to the project root, followed by the artifact verbatim. In unattended mode the entry carries the path only and adds `authority: MZ_DEV_PIPE_AUTO_APPROVE=1`.

A direct `>>` append bypasses the journal's redactor. The first recipe streams the artifact through perl, which replaces each `<private>…</private>` span with `[redacted]`. Anywhere else, write a sensitive value as `[redacted]` yourself. Placeholders go into the `printf` format, which turns `%` and `\` sequences into other text, so pass a free-text value as a `%s` argument instead.

Gate with the artifact:

```bash
mkdir -p "<PROJECT_ROOT>/.mz" && {
  printf '### %s · <skill> · <task_name> · gate\n\n- phase: <n> (<name>)\n- gate: <label>\n- outcome: <outcome>\n- artifact: <relative path>, verbatim:\n\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  perl -0777 -pe 's|<private>.*?</private>|[redacted]|gs; s/^(?=.)/  /gm' "<PROJECT_ROOT>/<relative path>"
  printf '\n'
} >>"<PROJECT_ROOT>/.mz/journal.md"
```

Gate skipped in unattended mode:

```bash
mkdir -p "<PROJECT_ROOT>/.mz" && printf '### %s · <skill> · <task_name> · gate\n\n- phase: <n> (<name>)\n- gate: <label>\n- outcome: auto-approved (unattended)\n- authority: MZ_DEV_PIPE_AUTO_APPROVE=1\n- artifact: <relative path>\n\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"<PROJECT_ROOT>/.mz/journal.md"
```

Each feedback pass is its own entry. Also record a substantial decision under `## Decisions` in `state.md`, so it reaches recall memory once the task is `complete`. The skill writes these entries itself and doesn't call mz-memory's scripts.
