# Interaction Journal Guidelines

Rules for the interaction journal, `.mz/journal.md`: one shared, append-only record of approval gates, input collectors and recorded decisions, written in one format by every plugin. `state.md` tracks where a task is. The journal records what was asked, what was answered and who decided. It is a best-effort record, not a complete one; §3 lists what reaches it and what doesn't.

Claims about Claude Code behavior carry the short source tags described at the top of AGENTS_GUIDELINES.md: a doc page, a changelog version, an issue, or "observed" for behavior seen in a probe. Page tags without a version were checked against v2.1.316 on 2026-11-02. Claims about this repository's code cite the file, such as `plugins/mz-memory/scripts/journal-capture.sh`. A rule marked "Repo convention", or a rule with no tag, is this repository's own choice.

**Owned elsewhere.** These topics are defined in other files; this one only points to them.

- Approval gates, the two-surface pattern and unattended mode: SKILL_GUIDELINES.md, "Approval Gates".
- Input collectors and their three shapes: SKILL_GUIDELINES.md, "Input Parsing".
- Task naming and when to write `state.md`: SKILL_GUIDELINES.md, "State Management".
- `state.md` keys, status values and body sections, including `## Auto-approvals`: `guidelines/STATE_SCHEMA.md`. What mz-memory's SessionEnd harvest reads from `state.md`, and how to write for it: STATE_SCHEMA.md, "Body Sections".
- Writing hooks and their failure handling: `guidelines/HOOKS_GUIDELINES.md`, "Exit Codes and Failure Handling".

## 1. Project Root

Everything under `.mz/` lives under one project root: the journal, the task folders under `.mz/task/`, reports, the tooling cache `.mz/tooling.json` and mz-memory's `.mz/memory/`. A skill resolves the root once, at the start of the run and before any `cd` or worktree switch:

```bash
echo "${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
```

Keep the printed path as the constant `PROJECT_ROOT` and build every `.mz/` path from it, such as `<PROJECT_ROOT>/.mz/journal.md` and `<PROJECT_ROOT>/.mz/task/<task_name>/state.md`. Shell variables don't survive between Bash calls (tools-reference.md), so the orchestrator expands the placeholder to the absolute path in each command, as it does for `<SKILL_DIR>` (SKILL_GUIDELINES.md, "Constants and Paths"). Pass the absolute path to any subagent that writes under `.mz/`. A worktree-isolated agent can't use it, because the Write tool refuses paths in the main checkout. It writes inside its own worktree and returns the path or the content, and the orchestrator copies what it keeps (AGENTS_GUIDELINES.md, "Structural Constraints").

Don't resolve `.mz/` against the Bash working directory. In the main session a `cd` carries over to later Bash calls (tools-reference.md), and a session can start in a subdirectory, so a relative `.mz/journal.md` can create a second `.mz/` that neither the hook nor the harvest reads. Don't use `CLAUDE_PROJECT_DIR` either. It isn't in the Bash tool's environment, and the inline `${CLAUDE_PROJECT_DIR}` a skill body can use names the launch directory, which can be a subdirectory of the repository (plugins-reference.md, hooks.md; observed, 2.1.316).

**How mz-memory finds the root.** Its hooks use `find_project_root` in `plugins/mz-memory/scripts/lib/common.sh`:

1. `MZ_MEMORY_ROOT`, when set, is used as is.
1. Otherwise the hook starts at `CLAUDE_PROJECT_DIR`, or at its own working directory when that variable is unset, and walks up to the first directory that contains a `.git` entry. The `.git` file of a worktree or submodule counts.
1. With no `.git` on the way up, it uses the starting directory.

Any other hook that reads or writes under `.mz/` resolves the root the same way (HOOKS_GUIDELINES.md, "Paths and Environment").

Claude Code sets `CLAUDE_PROJECT_DIR` to the directory the session started in and keeps it there when Claude runs `cd` or enters a worktree; only the `cwd` field of the hook input follows Claude (hooks.md). So the hook's root never follows a `cd` or a switch into a worktree. After `EnterWorktree`, hook entries still go to the journal of the checkout the session started in.

The skill's command and the hook agree when the skill resolves the root from the directory the session started in or from any subdirectory of the same repository. They disagree when the session has already moved into another repository or worktree before the skill starts: `git rev-parse --show-toplevel` then returns that one, while the hook stays at the launch root. From the same starting directory the two agree for a nested repository, a linked worktree and a submodule, and differ only when git can't use a `.git` entry that the walk accepts, such as a stale `.git` file left by a deleted worktree, an empty `.git` directory or a repository git rejects as dubiously owned, or when `git` isn't on PATH (observed, git 2.43). They also differ when `GIT_CEILING_DIRECTORIES` stops git's search, because the walk ignores it, so don't offer that variable as a fix. For runs like these, set `MZ_MEMORY_ROOT`, which both sides honor. A `.git` at HOME, as some dotfiles setups have, puts every project without its own repository at HOME on both sides. Run `git init` in the project, or set `MZ_MEMORY_ROOT` per project (with direnv, for example), since a global value merges every project into one root. The SessionEnd harvest (§6) reads only `<root>/.mz/task/`, so a `state.md` written under any other root is never promoted.

## 2. The Journal File

The journal is `<PROJECT_ROOT>/.mz/journal.md`.

- **One file.** Every skill and task writes the same file. The header of each entry names the skill and task; there are no per-task journals.
- **Append-only.** New entries go at the bottom. Nothing in mz-memory rewrites or prunes the file (`journal_append` in `plugins/mz-memory/scripts/lib/common.sh`), and skills don't either.
- **Markdown.** Each entry is a `###` section, readable without a parser. Hook entries hold compact one-line JSON.
- **Unbounded.** The file grows without limit, and each hook entry stores the questions twice (§4). Nothing reads it back, so deleting it loses the audit trail and nothing else.
- **Ignored by git only when set up.** `.mz/` stays out of git only when init-rules has added it to `.git/info/exclude` or the project's own `.gitignore` lists it. init-rules adds the exclude in project scope inside a git repository when `git check-ignore -q .mz/` fails; the exclude file isn't committed, so it covers that one clone. Without either, the journal, the `journal.md.lock` file the hook creates beside it, and the rest of `.mz/` (memory, state, reports) can be committed like any other file. `git check-ignore -v .mz/journal.md` shows which rule is in place. A team that wants `MEMORY.md` tracked anyway runs `git add -f .mz/memory/MEMORY.md`.
- **Not read for recall.** No mz-memory script reads the journal. Recall memory comes from `state.md` and from `/memory-note` (§6).

## 3. Two-Layer Capture

Two writers fill the journal. They record different things, and neither covers everything.

**Layer A: the mz-memory hook.** mz-memory registers `journal-capture.sh` as a PostToolUse hook with the matcher `AskUserQuestion` (`plugins/mz-memory/hooks/hooks.json`). Approval gates and closed-choice or confirm-or-customize collectors call that tool. When mz-memory is installed and `jq` is on PATH, the hook writes one entry per completed call, holding the questions and the full tool response, including the selected labels and any text typed through the Other row (agent-sdk/user-input.md). Skills need no instruction for it. It still fires after compaction, because the harness runs it on every matching call whatever the model's context holds (hooks.md).

It records nothing for:

- an open-value collector asked in prose (SKILL_GUIDELINES.md, "Input Parsing");
- a gate skipped in unattended mode (`MZ_DEV_PIPE_AUTO_APPROVE=1`), since no AskUserQuestion call happens;
- a dismissed dialog, which returns an error result instead of an answer. PostToolUse runs only after a tool completes successfully (hooks.md); that a dismissal fires no hook is inferred from this, not probed;
- any call made while mz-memory is missing or disabled, `jq` isn't on PATH, or hooks are turned off (§9).

Without `jq` the hook exits 0 and writes nothing, with no error and no `.mz/` folder (`journal-capture.sh`; observed).

The hook can't see the task, the phase or the Surface 1 artifact. Its input carries `session_id`, `cwd` and `transcript_path`, but the script reads only the tool fields (hooks.md; `journal-capture.sh`). The selector's question is one line, so `state.md` is the record of which artifact was approved (SKILL_GUIDELINES.md, "Approval Gates").

**Under Codex.** The Codex package remaps the hook to UserPromptSubmit, drops the matcher, and swaps the script for one that journals every user prompt verbatim (`_hook_event_mappings` and `_hook_script_adapter` in `src/mozg_pipelines/inventory.py`; `src/mozg_pipelines/rendering.py`). The renderer also rewrites `AskUserQuestion` in skill text as "ask the user directly", so Codex skills ask in prose. On Codex the journal therefore holds the user's answers, together with everything else the user typed, but no question text.

**Layer B: the skill's own entries.** The orchestrator knows what the hook can't: the skill, the task, the phase, the artifact under review and what the outcome means. After a gate resolves or a decision is made, it appends an entry carrying that context (§4).

Layer B should be written, but a skill that leaves it out is still compliant, because the hook covers AskUserQuestion calls when mz-memory is installed. Two cases have no hook record:

- A gate skipped in unattended mode requires a `gate` entry, every time (§5).
- A prose collector whose value matters later should get an `input` entry. Its value goes into `state.md` either way.

Repo convention: the baseline comes from the hook because an instruction to log in every gate of a dozen plugins can't be enforced and drifts. Skills add Layer B where the context has lasting value: gates over real artifacts, recorded decisions, and the two cases above.

## 4. Entry Format

Each entry is a markdown section that starts with a `###` header line. Timestamps are UTC in ISO-8601 form, from `date -u +%Y-%m-%dT%H:%M:%SZ`, so entries from concurrent sessions sort in one order. Fields in the header are separated by `·` (a middle dot with a space on each side).

**Header grammar.**

- Hook entries: `### <UTC> · session <session id> · AskUserQuestion`, where the session id is the full UUID. Under Codex the last field is `UserPromptSubmit`. Hook entries carry no event type, because the hook can't tell a gate from a collector.
- Skill entries: `### <UTC> · <skill> · <task name> · <event type>`. The event types are `gate`, `input`, `decision` and `phase`.

**Layer A, written by the hook** (`journal-capture.sh`; observed with a synthetic event):

```
### 2026-06-05T14:32:10Z · session 82ba9d1d-4c1e-4f7a-9a51-3b0c2e6d7f10 · AskUserQuestion

questions (verbatim):
[{"question":"The plan above is ready for review.","header":"Approval","options":[{"label":"Approve","description":"Start implementation"},{"label":"Reject","description":"Stop the run"}],"multiSelect":false}]

response (verbatim):
{"questions":[{"question":"The plan above is ready for review.","header":"Approval","options":[{"label":"Approve","description":"Start implementation"},{"label":"Reject","description":"Stop the run"}],"multiSelect":false}],"answers":{"The plan above is ready for review.":"Approve"},"annotations":{}}
```

`questions (verbatim):` holds the bare `questions` array from the tool input. `response (verbatim):` holds the whole tool response: the questions again, `answers` keyed by question text, and in most responses an `annotations` object added by the dialog, usually empty as above (observed in local transcripts, v2.1.285 to v2.1.316). Typed text replaces the label as the `answers` value (agent-sdk/user-input.md). The hook stores whatever the response contains, so a new field appears without a script change.

Under Codex the body is `prompt (verbatim):` followed by the prompt text.

**Layer B, written by the skill.** A header, a blank line, then short `- key: value` bullets, one key per bullet. Only the artifact may be long.

```
### 2026-06-05T14:32:11Z · build · 2026_06_05_build_oauth_flow · gate

- phase: 6 (implementation)
- gate: plan-approval
- outcome: approve
- artifact: .mz/task/2026_06_05_build_oauth_flow/plan.md, verbatim:

  <full plan.md contents, with each <private>…</private> span replaced by [redacted]>
```

Repo convention for the fields of each event type:

- `gate`: phase, gate label, outcome (`approve`, `reject`, `feedback`, `no answer` or `auto-approved (unattended)`), the artifact path, and the artifact verbatim. An unattended entry also names the authority and carries the path only (§5).
- `input`: phase, what was asked, the resolved value, and why it was needed.
- `decision`: the decision, the options weighed, the reason, and where the durable record lives, such as an artifact path or `state.md` `## Decisions`.
- `phase`: one line naming the phase entered.

**Appending an entry.** Use one Bash call that appends with `>>` to the absolute journal path from §1. A direct append doesn't create the folder, so run `mkdir -p` first when `.mz/` may not exist yet, and end the entry with a blank line, as the hook does. An entry without artifact text, such as a gate skipped in unattended mode, is one `printf`:

```bash
mkdir -p "<PROJECT_ROOT>/.mz" && printf '### %s · <skill> · <task_name> · gate\n\n- phase: <n> (<name>)\n- gate: <label>\n- outcome: auto-approved (unattended)\n- authority: MZ_DEV_PIPE_AUTO_APPROVE=1\n- artifact: <relative path>\n\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"<PROJECT_ROOT>/.mz/journal.md"
```

A gate entry that copies the artifact writes the header with `printf`, then appends the file with the plugin's `shared/journal-artifact.sh`, which replaces each `<private>` span with `[redacted]`, including spans that cross lines, and indents the text under its bullet. The artifact never passes through `printf`, so `%` and `\` in it are safe. The script runs as its own Bash call, because a skill grants it as `Bash(${CLAUDE_PLUGIN_ROOT}/shared/journal-artifact.sh *)` and a grant must match every subcommand of a chained command:

```bash
mkdir -p "<PROJECT_ROOT>/.mz" && printf '### %s · <skill> · <task_name> · gate\n\n- phase: <n> (<name>)\n- gate: <label>\n- outcome: <outcome>\n- artifact: <relative path>, verbatim:\n\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"<PROJECT_ROOT>/.mz/journal.md"
```

```bash
<PLUGIN_ROOT>/shared/journal-artifact.sh "<PROJECT_ROOT>/<relative path>" "<PROJECT_ROOT>/.mz/journal.md"
```

The placeholders are written into the `printf` format, where `printf` silently turns `%` and `\` sequences into other text. A free-text value that may contain them, such as an `input` entry's value, goes in a `%s` argument instead.

When a skill's append creates the journal, the file has no `# Interaction Journal` header, because mz-memory writes that header only into a journal it creates itself (`ensure_journal_file` in `plugins/mz-memory/scripts/lib/common.sh`). Nothing reads the header, so it is optional.

Apart from that script, a direct append isn't redacted; §8 says what to do about other sensitive values. Don't call mz-memory's scripts (§7).

## 5. What to Record

| Interaction                                     | Layer A (hook)                                  | Layer B (skill)                                                                                                                                                                 |
| ----------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Approval gate                                   | When answered in the dialog                     | Should: a `gate` entry with outcome and artifact                                                                                                                                |
| Closed-choice or confirm-or-customize collector | When answered in the dialog                     | Optional: the resolved value, when the context matters later                                                                                                                    |
| Open-value collector asked in prose             | None                                            | Should, when the value matters later: an `input` entry. The value goes into `state.md` either way                                                                               |
| Recorded decision (chose X over Y)              | Only if it went through an AskUserQuestion call | Should: a `decision` entry, and promote it (§6)                                                                                                                                 |
| Phase transition                                | None                                            | Optional: a one-line `phase` entry for long pipelines                                                                                                                           |
| Gate skipped in unattended mode                 | None, since no AskUserQuestion call happens     | Required for every skipped gate: gate label, outcome `auto-approved (unattended)`, task, phase, the authority `MZ_DEV_PIPE_AUTO_APPROVE=1`, and the artifact path, not its text |

"When answered in the dialog" assumes mz-memory is installed, `jq` is on PATH and hooks are on (§3).

An unattended run also logs each skipped gate in chat, under `## Auto-approvals` in `state.md`, and in the final report (SKILL_GUIDELINES.md, "Approval Gates"). Its journal entry names the artifact instead of copying it, since Surface 1 still prints the artifact in chat.

Feedback loops: when the user answers with feedback and the gate is presented again, each pass is its own entry, because each AskUserQuestion call fires its own hook (hooks.md). The journal shows the negotiation, not just the final answer. Feedback typed as a chat message after dismissing the dialog reaches no hook.

## 6. Recall: Promoting Decisions to Memory

Recall doesn't come from the journal. A decision worth recalling in later sessions goes into mz-memory's `.mz/memory/MEMORY.md`, which holds a Pinned section, a Digest and an Activity Log. Two paths lead there, and neither calls another plugin's scripts.

**Automatic: `## Decisions` in `state.md`.** Write the decision under `## Decisions` in the task's `state.md`. This costs one section in `state.md`. When mz-memory is installed, its SessionEnd hook harvests the Decisions and Notes of finished `state.md` files under `<root>/.mz/task/` (§1) into the Activity Log (`plugins/mz-memory/scripts/memory-capture.sh`). `## Lessons` take another path: they are harvested from every `state.md` whatever its `Status` into `.mz/memory/lessons.md`, so they don't age out with the log. Which files it reads, what it extracts and how to write for it are in STATE_SCHEMA.md, "Body Sections". SessionEnd hooks get 1.5 seconds by default (hooks.md). A capture cut short doesn't advance its marker, so the next SessionEnd reads the same files again.

**The Activity Log.** It sits under `## Activity Log` in `MEMORY.md`, between the `<!-- mz-log-start -->` and `<!-- mz-log-end -->` markers, newest first (`plugins/mz-memory/scripts/lib/common.sh`).

- **Entry format.** Each harvested task gets one line, `- [<YYYY-MM-DD>] <task_name> (phase=<Phase>) [<branch>@<short sha>]`, followed by its extracted lines. The date is local, unlike the journal's UTC. `(phase=…)` is left out when the `Phase` value is empty. The branch and SHA come from the root's checkout and are left out when the root isn't a git checkout.
- **Extracted lines.** Each starts with a single space. The capture collapses every run of spaces and tabs to one space, so indentation inside a line doesn't survive (observed).
- **Size cap.** Each capture prepends its new block and prunes the Activity Log to 400 lines, new entries included (`MZ_LOG_MAX_LINES` in `lib/common.sh`). The cap counts lines, not entries, so the oldest entry can lose its extracted lines before its entry line goes. `/memory-note --log` adds one line under the same cap (`memory-note.sh`).
- **Compression.** Once the log passes 300 lines (`MZ_COMPRESS_THRESHOLD`), capture starts `memory-compress.sh` in the background. It keeps about the newest 100 lines verbatim and hands the older entries to the curator that also curates lessons (`lib/curator.sh`). The curator returns edits by item ID (add, merge, supersede, drop, combine) to a `## Digest` section between Pinned and the Activity Log. The script checks them before applying them, allowing at most 40 items of 300 characters each. The old entries leave the log, copied verbatim to `.mz/memory/activity.archive.md`, and each run is recorded in `.mz/memory/activity.ops.jsonl`. The result is applied under the MEMORY.md lock against the live file, so entries another session adds meanwhile survive. A failed run leaves MEMORY.md as it was and is retried at most once a day. A one-time migration, with no model call, turns an old `<!-- mz-compressed -->` summary into Digest items.
- **Background runs.** Compression and lessons curation each start a detached `claude -p` on the user's account at SessionEnd. It uses Sonnet by default (`MZ_MEMORY_CURATOR_MODEL`), is capped at $0.50 and 180 seconds, and runs with hooks and tools off. Both are on by default. `MZ_MEMORY_COMPRESS=0` turns both off, and both are skipped when `claude` or `jq` isn't on PATH. Lessons past the 500-line cap are still evicted without the model.
- **What reaches the model at session start.** At startup, after `/clear` and after compaction (SessionStart matcher `startup|clear|compact`), `memory-inject.sh` injects, in order, the Pinned section, up to 3,000 characters of lessons, up to 3,000 characters of Digest items and the newest 200 log lines. The whole string is cut at 8,000 characters, so the log loses lines first. The lessons are the 12 top curated ones by count, then recency, plus the 3 newest inbox items, under a line saying they never override the user and a hint naming curated lessons seen 3 or more times, and not declined since, as candidates for `/lessons-promote`. Lessons and Digest items lose their metadata and appear as `- [ID] text`.
- **What reaches the model on each prompt.** `memory-prompt-inject.sh` takes up to 12 keywords from the prompt: lowercased runs of ASCII letters and digits, 4 or more characters long, minus common stopwords. It injects the Pinned section, up to 5 lessons in 1,500 characters, and up to 15 Digest items and log lines that share a keyword with the prompt, Digest first, all cut at 4,000 characters. The nudge is one line asking Claude to fix the mistake and save the lesson with `/memory-note --lesson`, placed ahead of the cut. It fires when the prompt's first 500 characters push back on Claude in English; slash commands never fire it. A prompt with neither a keyword nor a nudge gets nothing, Pinned included, so one written entirely in Cyrillic gets nothing unless it holds a number of 4 or more digits.

**Explicit: pinning.** For a decision that must not age out, such as an architectural invariant or a binding convention, recommend that the user pin it with `/memory-note`. Pinned entries are never pruned. They are injected at every session start and with most prompts, namely any prompt that yields a keyword of four or more characters (`memory-prompt-inject.sh`), so pin sparingly. Skills recommend the command; they don't run its script.

**Explicit: lessons from a correction.** Outside a skill run, `/memory-note --lesson` saves what a user's correction taught as one `WHEN … → … — WHY …` line in the Inbox of `.mz/memory/lessons.md`. It has no gate, because the curator reviews the Inbox later. The script refuses a lesson over 400 characters and saves the same text only once a day. A `(review)`, `(failure)` or `(change)` prefix sets the lesson's trigger, which is otherwise `correction`. A typo the user fixed in passing needs only the fix. Inside a skill run, the lesson goes under `## Lessons` in `state.md` instead.

**Explicit: promoting lessons.** `/lessons-promote` turns curated lessons seen 3 or more times, or the lessons named by id, into project rules, at most 5 per run, with an Approve/Reject gate for each. A lesson about particular files goes to `.claude/rules/<topic>.md` with `paths:` globs, and any other to the project's `CLAUDE.md`, never inside init-rules' `<!-- mz-rule:… -->` blocks. An approved lesson moves to `lessons.archive.md` as `<date> promoted_to=<target>: <line>`. A rejected one is recorded in `.mz/memory/.promote-declined`, and neither the hint nor the default list offers it again until it has recurred more times than when it was declined. Both outcomes are logged to `lessons.ops.jsonl`.

A skill that records a substantial decision should write it under `## Decisions` and may recommend pinning it. mz-gov's govern skill does both: it writes the durable artifact under `docs/`, adds a `## Decisions` line, recommends `/memory-note` for load-bearing invariants, and sets `Status: complete` when the run ends (`plugins/mz-gov/skills/govern/phases/record.md`, `enforce.md`).

## 7. Ownership and Dependency

- **Format and rules**: this file. Every plugin follows it.
- **Hook**: mz-memory's `scripts/journal-capture.sh`. It appends through `journal_append` in `scripts/lib/common.sh`, which serializes writers with `flock` when it is available and redacts `<private>` spans.
- **Other plugins** write `.mz/journal.md` and `state.md` directly with Bash and don't call mz-memory's scripts. `${CLAUDE_PLUGIN_ROOT}` is the calling plugin's own installed path (plugins-reference.md), so another plugin has no supported way to locate them.

**Dependency.** Layer A needs mz-memory installed and enabled, and `jq` on PATH. Without `jq` the hook records nothing and reports no error. No plugin in this repository declares mz-memory as a dependency, so a skill can't assume the hook is present. Without it, gates work as usual and Layer B entries still land; only the automatic record is missing. Skill text says the hook records a gate "when mz-memory is installed", not that it "already records every gate".

## 8. Privacy and Redaction

The journal stores interactions verbatim, including artifacts that can hold sensitive content such as outreach drafts, tokens or customer data.

- **mz-memory redacts what it writes.** `journal_append` replaces every `<private>…</private>` span with `[redacted]` and keeps the surrounding whitespace, so code indentation survives (`redact_private` in `plugins/mz-memory/scripts/lib/common.sh`). The hook goes through it. Without perl, the `sed` fallback misses a span that contains `<` or crosses a line.
- **A skill's own append isn't redacted.** A direct `>>` bypasses `journal_append`, so a `<private>` tag would be stored as is, with the secret inside it (observed). A skill writes `[redacted]` in place of each sensitive value itself, and replaces each `<private>…</private>` span with `[redacted]` before appending, for example when it copies an artifact verbatim. The second recipe in §4 does this through `shared/journal-artifact.sh`, which runs the perl expression mz-memory uses and so also handles spans that cross lines.
- **Codex.** The remapped hook journals every user prompt, and only `<private>` spans are redacted.
- **Git.** The journal stays out of git only when the project ignores `.mz/` (§2).

Redaction is best-effort. Claude Code's own transcript keeps the raw answers (observed), so redacting the journal never removes a secret from the machine. Don't route credentials through a gate and rely on the journal to scrub them.

## 9. Verification

- **The hook runs standalone.** Feed `journal-capture.sh` a synthetic PostToolUse event on stdin, with `MZ_MEMORY_ROOT` pointing at a scratch folder. It exits 0 with no stdout or stderr on every path: a valid event, malformed JSON, empty input, a tool other than AskUserQuestion, an unwritable root, no git root, and no `jq` (observed). `guidelines/HOOKS_GUIDELINES.md` covers the failure discipline it follows. `tests/mz_memory/test_journal_capture.py` runs these cases, apart from the unwritable root and the missing git root.
- **A gate leaves an entry.** In an interactive session with mz-memory installed, answering a gate in the dialog adds a Layer A entry. This needs a live session, so it can't run in CI. If no entry appears, check that:
  - mz-memory is installed, and `jq` is on PATH;
  - hooks aren't turned off, and mz-memory is enabled and trusted (AGENTS_GUIDELINES.md, "Agent/Hook Interface", lists every case);
  - the dialog was answered, not dismissed, and the run wasn't in unattended mode;
  - you are reading the right file: the hook writes under the root of the directory the session started in (§1), so a skill that resolved its root after moving into another repository or worktree, or appended to a relative path, has written a second journal elsewhere.
- **Promotion.** A `## Decisions` line reaches the Activity Log at the next SessionEnd when the task's `state.md` sits under the root from §1 and meets the conditions in STATE_SCHEMA.md, "Body Sections". `tests/mz_memory/test_memory_capture.py` covers this path. If a finished task isn't logged, check its `Status` line against the forms STATE_SCHEMA.md, "Body Sections", lists as skipped. A `## Lessons` line reaches the Inbox of `.mz/memory/lessons.md` at the same SessionEnd, whatever the task's `Status`; `tests/mz_memory/test_lessons_capture.py` covers that path.
