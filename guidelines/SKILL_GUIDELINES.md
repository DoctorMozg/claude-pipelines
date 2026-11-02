# Skill Authoring Guidelines

Rules for writing skills in this repository.

Claims about Claude Code behavior carry the short source tags described at the top of AGENTS_GUIDELINES.md: a doc page, a changelog version, an issue, or "observed" for behavior seen in a probe. Pages live under `code.claude.com/docs/en/` unless the tag starts with `platform:` or `claude.com:`, and page tags without a version were checked against v2.1.316 on 2026-11-02. A rule marked "Repo convention", or a rule with no tag, is this repository's own choice.

**Owned elsewhere.** These topics are defined in other files; this one only points to them.

- Model tiers, effort, and a skill's own `model:` field: AGENTS_GUIDELINES.md, "Model and Effort".
- What a dispatch prompt carries and how to compress it: AGENTS_GUIDELINES.md, "Dispatch Prompts".
- Issuing waves and the 6-agent cap: AGENTS_GUIDELINES.md, "Parallel Waves".
- `STATUS:` values and how an orchestrator handles them: AGENTS_GUIDELINES.md, "Status Protocol".
- Severity labels and `VERDICT:`: AGENTS_GUIDELINES.md, "Review Output".
- Anti-rationalization tables, for skills as well as agents: AGENTS_GUIDELINES.md, "Anti-Rationalization Tables".
- Instruction wording, emphasis and registers by role, for skill bodies as well: AGENTS_GUIDELINES.md, "Instruction Wording".
- The ban on rule-number citations in plugin files: AGENTS_GUIDELINES.md, "No Rule-Number Citations".
- `state.md` keys and status values: `guidelines/STATE_SCHEMA.md`. The journal: `guidelines/JOURNAL_GUIDELINES.md`. Hooks: `guidelines/HOOKS_GUIDELINES.md`.

## 1. Approval Gates

Every approval gate uses the two-surface pattern. It borrows plan mode's loop, in which the user approves or keeps sending feedback until satisfied, but not plan mode's display. Plan mode keeps the plan in a file and shows it inside the `ExitPlanMode` approval dialog, and approving that dialog switches the session's permission mode (permission-modes.md, "Review and approve a plan"; hooks.md). Skill gates don't use that dialog. A gate shows the artifact as an ordinary markdown chat message (Surface 1) and asks for the decision with a short `AskUserQuestion` selector (Surface 2).

**Where gates go.** Repo convention: put a gate before an irreversible or expensive step, such as changing code, launching a large agent wave, or sending something outside the repo. A read-only skill may put one gate before its main agent wave when that wave is large or costly, as deep-research, expert, brainstorm, outreach-brief and combine do; a later step such as a gap-fill wave doesn't get another. A single search or lookup runs without a gate, and read-only skills such as `explain` need none.

**Elements, in order:**

1. **Delegation guard.** `**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.` Custom subagents don't get AskUserQuestion; only forks keep it (sub-agents.md). The answer also has to reach the orchestrator that acts on it.

1. **Pre-read.** The gate tells the orchestrator to Read the named artifact and capture its full contents, for example `Read .mz/task/<task_name>/plan.md and capture the full contents`. Name the exact path, not "the artifact".

1. **State first.** Write `state.md` before presenting the gate: the phase, the artifact path, and a `what_remains` entry `awaiting approval: <gate>`. `Status` stays `running` while the gate waits. Idle compaction can run while a gate waits (§7).

1. **Surface 1, the plan message.** A normal chat message, not a tool call, holding the artifact verbatim:

   ```
   ## Plan for review: <skill name>

   <verbatim artifact contents>

   ---
   **Approve** → <what happens next>  ·  **Reject** → <abort outcome>  ·  reply with feedback to revise
   ```

   Show the artifact verbatim. Don't replace the body with a path, a line count, a status summary or a placeholder; that substitution is the failure this repo has actually seen.

1. **Surface 2, the selector.** Call AskUserQuestion right after the plan message. `question` is one line pointing at the message above, such as `The plan above is ready for review.`, and doesn't repeat the artifact. `header` is at most 12 characters. The named options are exactly **Approve** and **Reject**, with no "Feedback" option. In Claude Code's dialog the user can always type an answer through the `Other` row, and some questions also show a notes field (tools-reference.md). Agent SDK hosts have to add the Other choice themselves (agent-sdk/user-input.md), and the Codex renderer turns the selector into a plain question (`src/mozg_pipelines/rendering.py`).

1. **Variant gates** (only when the gate offers more actions than Approve and Reject). AskUserQuestion accepts 2-4 options per question and 1-4 questions per call. Each option has a `label`, which is the action name and comes back as the answer, and a one-sentence `description` (agent-sdk/user-input.md). Present each action as `**<Name>** — <one-sentence summary>`. With more than four actions, keep the four most common as options and list the rest in the Surface 1 footer as typed replies, or ask in two calls in a row: first the category, then the action. `plugins/mz-knowledge/skills/vault-review/phases/review_session.md` is the reference: four options, with Edit and abort as typed replies.

1. **Response handling**, as a labeled section:

   - **Approve**: record the approved artifact path in `state.md` as a `## Decisions` line and remove the `awaiting approval` entry, then proceed. The journal hook sees only the one-line selector, so `state.md` is the record of what was approved.
   - **Reject**: set `Status: aborted_by_user` and stop.
   - **Any other answer is feedback.** That includes typed text, a "Chat about this" reply, and an Approve whose note asks for a change. Apply the feedback, running the upstream phase or agent again when the change needs it. Then overwrite the artifact, re-read it, and re-emit the whole plan message from scratch before presenting the selector again. Don't send a diff or a summary: the user approves the artifact as it now stands, earlier versions may no longer be on screen, and after compaction Claude holds only a summary of them. The gate loops until the user explicitly approves.
   - **No answer**: AskUserQuestion is denied or unavailable in `dontAsk` mode, in `claude -p` without a permission host, with `--permission-prompts none`, and in `claude -p --channels`. With the opt-in `askUserQuestionTimeout`, a result can also carry the away signal while naming whichever option was preselected (tools-reference.md; settings-reference.md; permission-modes.md; headless.md; channels.md; changelog 2.1.200). Neither case is approval, whatever option the result names. Set `Status: blocked`, keep `awaiting approval: <gate>` in `what_remains`, leave the plan message in place, and stop.

   A missing answer is never approval.

1. **Journal** (should). After the gate resolves, append a Layer B enrichment entry to `.mz/journal.md` at the project root, not relative to the Bash working directory: skill, task, phase, gate label, outcome, and the artifact, with each `<private>` span replaced by `[redacted]`, since a direct append isn't redacted. When mz-memory is installed, its hook records the selector's question and answer, but never the artifact. Record a substantial decision under `## Decisions` in `state.md` as well, so it reaches recall memory. The entry format is in `guidelines/JOURNAL_GUIDELINES.md`. Journaling never delays the gate.

Every element is required except the variant gate (only when variant actions exist) and the journal entry (recommended).

**Unattended mode.** A user can opt in to unattended runs by setting `MZ_DEV_PIPE_AUTO_APPROVE=1`, for CI or scheduled jobs. Skills never turn it on themselves. The orchestrator checks the variable once during setup with a Bash call and records the result in `state.md` as `unattended: true` or `unattended: false`. In this mode it still emits Surface 1 and skips Surface 2. It logs every skipped gate in four places: chat, `state.md` under `## Auto-approvals`, a Layer B journal entry at the project root that names the authority (`MZ_DEV_PIPE_AUTO_APPROVE=1`) and carries the artifact path rather than its text, and the final report. No hook fires without an AskUserQuestion call, so the skill appends the journal entry itself, writing sensitive values as `[redacted]`. A raw `>>` append bypasses the journal's redactor, so a `<private>` span would be written as is. Variant gates never auto-approve, because they need an explicit choice; in an unattended run they take the No-answer path.

**Cost line.** A gate may add a one-line cost estimate for the next step to the Surface 1 footer.

**Why the artifact is a chat message.** A chat message renders markdown in full and stays in scrollback. In this repo, a long artifact placed inside the AskUserQuestion body has been replaced by a bare path or a one-line status. No doc states a length limit, so that is a repo observation.

**Canonical skeleton:**

```
**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `<artifact_path>` and capture its full contents into context.
**State**: write `state.md` with the artifact path and `awaiting approval: <gate>`.

**Surface 1: emit the plan message.** Output the artifact verbatim as a chat message:

    ## Plan for review: <skill name>

    <verbatim contents of <artifact_path>>

    ---
    **Approve** → <next phase>  ·  **Reject** → <abort outcome>  ·  reply with feedback to revise

Emit the full verbatim contents, never a path, summary or placeholder.

**Surface 2: call AskUserQuestion.** question: "The plan above is ready for review." header: "<12 chars max>"
options: **Approve** — <next phase> · **Reject** — <abort outcome>.

**Response handling**:
- **Approve** → record the approved artifact path as a `## Decisions` line in `state.md`, clear `awaiting approval`, proceed to <next phase>.
- **Reject** → set `Status: aborted_by_user`, stop.
- **Any other answer** → apply the feedback (re-run the upstream phase if needed), overwrite `<artifact_path>`, return to Surface 1, re-emit the full updated plan message, re-present. Loop until explicit Approve.
- **No answer** → set `Status: blocked` with `awaiting approval: <gate>`, stop. A missing answer is never approval.
```

Reference implementation: `plugins/mz-design/skills/design-document/phases/finalization.md`, Step 4.1.

## 2. Phase and Reference Files

**How skill text loads** (skills.md; context-window.md):

- The skill listing is sent every turn, within a budget of 1% of the context window. `skillListingBudgetFraction` and `skillListingMaxDescChars` change the limits, and skills with `disable-model-invocation: true` are left out.
- An invoked SKILL.md body stays in context for later turns, so every line is a recurring token cost. Longer instruction files also lower adherence (memory.md, said of CLAUDE.md files).
- A subagent's `skills:` field injects the full body of each listed skill at launch, so preloading a skill into an agent costs its whole length (sub-agents.md).
- Compaction re-attaches the most recent invocation of each skill, keeping the first 5,000 tokens of each within a 25,000-token total. The oldest invoked skills can be dropped entirely.
- A phase file costs nothing until it is read. After compaction, Claude Code re-reads up to five of the files read or edited in the session, choosing the most recently modified, and a file over 5,000 tokens comes back as a path only (context-window.md). A phase file that was only read is rarely among them.

**SKILL.md** is the slim orchestrator: frontmatter, input, scope, constants, the phase table, gates or pointers to them, error handling and state. Aim for about 150 lines. Stay under about 20,000 characters, which is where Claude Code's 5,000-token estimate (characters divided by 4) truncates a skill at compaction (observed in the 2.1.316 binary). The official ceiling is 500 lines (skills.md). Keep anything that has to survive compaction in that first part.

**Phase files** (`phases/*.md`) hold the detailed process for one phase. Read each at the start of its phase with `Read <SKILL_DIR>/phases/<file>.md`, never all of them up front. Repo convention: under about 400 lines each. A phase file may hold a gate. After compaction, re-read the current phase file before continuing.

**Reference files** (`references/*.md`) hold knowledge loaded on demand.

- List every reference file in SKILL.md with what it holds and when to read it, as `${CLAUDE_SKILL_DIR}/references/<file>.md`. Phase files may name it again as `<SKILL_DIR>/references/<file>.md`. Give dispatched agents absolute paths, and don't add an `@` prefix. A bare relative path usually resolves in the main session, because Claude Code adds a base-directory line to each invoked skill (observed, undocumented), but it fails in subagent prompts and across plugins.
- References stay one level deep from SKILL.md: the platform guide asks that every reference be linked directly from SKILL.md (platform: skills best-practices). Listing each file in SKILL.md meets that even when a phase file names it too.
- Grep lookup catalogs for the entry you need. Read templates, rubrics, threshold tables and short rule sets in full. An agent told to grep a file needs Grep or Bash in its `tools`.
- A reference file over 100 lines opens with a table of contents (platform: skills best-practices). Repo convention: at most about 400 lines.
- Example: `explain/references/mermaid-syntax-by-type.md`.

**Shared files.** Repo convention: a file that several plugins use lives once, in `plugins/mz-base/shared/`. Each consumer plugin has a `shared` symlink at its root pointing to `../mz-base/shared`. Skills reach it as `<PLUGIN_ROOT>/shared/<file>.md` and agent bodies as `${CLAUDE_PLUGIN_ROOT}/shared/<file>.md`.

- Claude Code copies a marketplace plugin into its own cache directory and dereferences a symlink whose target is elsewhere in the same marketplace (plugins/host-marketplace.md). The doc says installs from a local path, or from a `command` source in copy mode, keep only links inside the plugin. A probe of an install from a locally added marketplace on 2.1.316 found the link dereferenced anyway (observed). `--plugin-dir` loads the plugin in place, so the link resolves directly (plugins/loading.md). Test an install after changing the layout.
- Don't write a path into another plugin's directory (`../other-plugin/...`) in skill or agent text. Only the `shared` link crosses plugins, because Claude Code resolves it at install time; a path written in prose finds nothing in the cache (plugins/loading.md).
- Keep directory symlinks out of `skills/`: `claude plugin validate --strict` refuses them, while a link at the plugin root passes (observed on 2.1.316).
- On claude.ai only the skill's own folder may be present (claude.com: skills how-to; anthropics/claude-code#103509). A file that a skill needs on every surface stays inside that skill's folder.

## 3. Skill Descriptions

The description is the main signal Claude uses to invoke a skill on its own. If it doesn't match, the skill still runs when the user types `/name` or names the skill, and the bare name stays in the listing. Three things hide a description entirely: malformed frontmatter, an over-budget listing (the least-used skills drop to name only), and `paths`, which keeps a skill out of the listing until Claude touches a matching file (skills.md; listing behavior observed in the 2.1.316 binary).

**Shape.** Open with a third-person clause naming what the skill produces or covers, then "Use when…". Name a capability, not the skill's steps, and never end with a workflow summary such as "— orchestrates X, Y, Z". Avoid "I" and "you": the description is injected into the system prompt, and a mixed point of view hurts discovery (platform: skills best-practices).

**Wording.** State when to use the skill in plain directive terms, a little pushy, because Claude still tends to under-trigger skills (anthropics/skills skill-creator; agentskills.io, optimizing descriptions). Don't use all caps unless `claude plugin eval` shows a gain without firing on near misses. skill-creator calls all-caps ALWAYS and NEVER a yellow flag. Current models over-apply emphasized rules (best-practices.md, "What you can stop doing"), and Anthropic warns that emphatic wording written for older models can over-trigger on Opus 4.5 and 4.6 (platform: claude-prompting-best-practices). A prefix that every skill shares, such as "ALWAYS invoke when", tells Claude nothing about which skill to pick.

**Triggers.** Cover what the user is trying to do:

- phrases users actually type;
- at least one request that doesn't name the domain;
- the nearest sibling skill, as a counter-trigger.

Counter-triggers that must prevent a wrong invocation go in the description, because the body loads only after the skill is picked. Fix a miss by revising the wording in general terms, not by pasting in that query's keywords.

**Length.** Put the skill's distinctive domain words in the first sentence. Claude Code cuts `description` plus `when_to_use` at 1,536 characters (skills.md; changelog 2.1.105), and the Agent Skills spec and claude.ai uploads allow 1,024 (agentskills.io specification). When the listing goes over its budget, Claude Code drops whole descriptions, least-used skills first. Repo convention: keep `description` plus any `when_to_use` at or under 250 characters. This protects the shared listing budget; it isn't a platform limit.

**Characters and quoting.** Leave out `<` and `>`, which the listing shows as `&lt;` and `&gt;` (skills.md). Keep `description` on one line; repo convention, enforced by the `skill-description-shape` pre-commit hook, rules out a block scalar such as `>-` or `|`. Quote a description that contains `: ` or starts with `[` or `"`. Claude Code accepts unquoted colons (changelog 2.1.69), but strict YAML parsers, such as the PyYAML loader in the repo's Codex renderer, reject them.

```yaml
description: "Builds a feature end to end, from plan to tested code. Use when the user asks to build, implement or add a feature or module. Not for bug fixes (use debug) or polishing working code (use polish)."
```

**Measure before bulk changes.** Run `claude plugin eval` on a few skills before rewriting many descriptions (plugin-evals.md; changelog 2.1.269). A should-not-trigger case needs `min: 0, max: 0` and `arm: both`.

Agent descriptions follow AGENTS_GUIDELINES.md, "Descriptions and Trigger Scenarios".

## 4. Phase Overview Table

A multi-phase skill, meaning one with two or more phase files or any approval gate, has a phase table under `### Phase Overview` in SKILL.md. Inline approval gates take a `.5` number, and a gate that lives in a phase file is listed with that file. The Loop column is optional. Keep the delimiter row; without it, mdformat turns the table into a paragraph.

```
| Phase | Goal          | Details            | Loop                   |
| ----- | ------------- | ------------------ | ---------------------- |
| 0     | Setup         | Inline below       |                        |
| 1     | <goal>        | `phases/<file>.md` |                        |
| 1.5   | User approval | Inline below       | until approved         |
| 2     | <goal>        | `phases/<file>.md` | up to `MAX_ITERATIONS` |
```

## 5. Scope Parameter

Skills that edit code accept `scope:branch|global|working`, and skills that analyze a codebase should accept it too.

- Extract the token from `$ARGUMENTS` case-insensitively and remove it before parsing the rest of the input. When Claude invoked the skill itself, `$ARGUMENTS` may be empty or paraphrased, so also honor a scope the user stated in plain words, and ask when the mapping is unclear.
- The mode definitions and git commands live once, in `<PLUGIN_ROOT>/shared/scope-parameter.md` (§2, "Shared files"). Skills link to it instead of restating them.
- Scope narrows the skill's target set. In a skill that edits, it bounds which existing files agents may edit and any scan that picks edit targets; investigation, tests and linters default to the full project so they catch regressions elsewhere. In a skill that only analyzes, it bounds which files are analyzed.
- Each skill states its own read and edit boundary, and its default when `scope:` is omitted, next to its link to the shared file. Every writer dispatch prompt states the edit boundary.
- Where the skill saves `scope_files.txt`, the final report lists any pre-existing file the run changed outside it.

Prose can't hold a writer to its edit boundary, and plugin agents ignore frontmatter `hooks` (AGENTS_GUIDELINES.md, "Fields Plugin Agents Ignore"). The final-report check above is how a breach gets noticed.

## 6. Constants and Paths

Define every bound and path as a named constant in SKILL.md, and give each bound a short reason. Every loop refers to its constant by name instead of repeating the number.

**Path variables.** Claude Code substitutes `${CLAUDE_SKILL_DIR}`, `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` in the skill's markdown content and in Bash rules in `allowed-tools` (skills.md; changelog 2.1.69). In practice that means SKILL.md only: a phase file opened with Read arrives with the variables still literal (observed on 2.1.316). None of these variables is set in the Bash environment (plugins/manifest-reference.md).

Repo convention since commit 97944fb:

- SKILL.md defines `SKILL_DIR: ${CLAUDE_SKILL_DIR}`, and `PLUGIN_ROOT: ${CLAUDE_PLUGIN_ROOT}` when it needs plugin-level files.
- Phase files write `<SKILL_DIR>/...` and `<PLUGIN_ROOT>/...`.
- The orchestrator expands a placeholder to the absolute path before reading a file, running a command, or passing a path to an agent.

The reason is that Bash runs from the session's working directory, and Read doesn't substitute variables. Claude Code doesn't require this pattern. Paths relative to the skill root are the documented cross-tool convention and still work for Read.

Repo convention for `.mz/` paths: a skill that writes under `.mz/` resolves `PROJECT_ROOT` once during setup, before any `cd` or worktree switch, with the command in `guidelines/JOURNAL_GUIDELINES.md`, "Project Root". It keeps the printed path and writes `<PROJECT_ROOT>/...` in phase files, because neither the Bash working directory nor `CLAUDE_PROJECT_DIR` reliably names the repository root.

**Portability.** On claude.ai chat, `${CLAUDE_SKILL_DIR}` isn't promised, and files outside the skill's folder may be missing (claude.com: skills how-to; anthropics/claude-code#103509). Keep a file the skill needs on every surface inside its own folder.

Outside Claude Code (claude.ai uploads, the Skills API, `package_skill.py`), frontmatter may hold only `name`, `description`, `license`, `compatibility`, `metadata` and `allowed-tools`. Any other field fails with a hard error (skills.md, "Using skill frontmatter outside Claude Code"). A skill meant for those surfaces drops `model`, `when_to_use`, `argument-hint` and the other Claude Code fields.

## 7. State Management

A multi-phase skill keeps its cross-phase state in `.mz/task/<task_name>/state.md`, under the project root defined in `guidelines/JOURNAL_GUIDELINES.md` rather than the Bash working directory. Its keys, status values, progress ledger, body sections and compaction rules are defined in `guidelines/STATE_SCHEMA.md`, the single source. Skills mirror its compact contract and add their own keys below the schema keys, never renaming or replacing one.

- **Task name**: `<YYYY_MM_DD>_<skill>_<slug>`. The date is today's, written with underscores. `<slug>` is a snake_case summary of the argument, at most 20 characters. On a same-day collision, append `_v2`, `_v3`. Examples: `2026_04_20_build_oauth_flow`, `2026_04_20_debug_payment_err`.
- **Status values** (mirrors STATE_SCHEMA.md): `pending | running | blocked | complete | aborted_by_user | failed`. `blocked` means the run stopped for an answer or an obstacle, with the reason in `what_remains`. Milestones go in `Phase`.
- **When to write**: after every phase transition, and before every approval gate. A compaction summary can drop specific paths and decisions. A main conversation over 200K tokens can also compact after sitting idle for about an hour, which can happen while a gate waits (settings-reference.md, `idleCompaction`; changelog 2.1.299). Read cross-phase facts back from `state.md`, not from conversation memory.
- **Size**: keep `state.md` under about 5,000 tokens, and put a one-line resume pointer near the top of SKILL.md (`guidelines/STATE_SCHEMA.md`, "Compaction").
- **Decisions**: a decision worth remembering across sessions goes under `## Decisions`, where mz-memory harvests it once the task is `complete` (`guidelines/STATE_SCHEMA.md`, "Body Sections").

## 8. Error Handling and Escalation

This section is the one escalation rule. Approval gates (§1), tooling detection (§11), input parsing (§12) and the "Status Protocol" section of AGENTS_GUIDELINES.md all follow it.

Check for the failures the skill can predict during input parsing, before the first dispatch. List each one with its response under `## Error Handling` in SKILL.md.

- **Recover on your own** where the skill documents a way. That can be a default, a fallback chain such as `gh` → GitHub MCP → REST (CLAUDE.md, "Plugin Authoring Conventions"), or a degraded mode that the final report discloses.
- **Escalate** when the remaining choices would lead to materially different work, or when continuing on a wrong guess would be unsafe. For a routine judgment call, state the assumption and continue.
- **Never fill a blocker with an invented value.**

**How to escalate:**

- In an interactive main session, ask. Use AskUserQuestion when the answer is a pick from a set, and name the tool in the instruction: auto mode, the starting mode since v2.1.283, steers Claude away from clarifying questions unless a skill explicitly relies on one (permission-modes.md). Ask for an open value, such as a path or a topic, as a plain prose question (§12).
- Sometimes nobody can answer: in a custom subagent (including a skill with `context: fork`, which runs as a regular agent type), in `claude -p` without a permission host, with `--permission-prompts none`, in `dontAsk` mode, or in a skill that sets `disallowed-tools: AskUserQuestion` (sub-agents.md; skills.md; headless.md; permission-modes.md). First finish the work that doesn't depend on the answer. Then write the blocker and the options to `state.md`, set `Status: blocked`, and stop. A skill running inside a subagent returns `STATUS: BLOCKED`.
- An unanswered question is not an answer. Take the documented safe default, or stop.

**Cases:**

- **Empty arguments.** If the skill documents a default, use it and say so. Otherwise ask.
- **Missing tools.** No test framework: ask (§11). No linter or type checker: report it and continue.
- **Zero files in scope.** A code-editing skill asks whether to widen the scope. A read-only skill reports and exits.
- **An agent returns nothing usable:**
  - If it is still running, wait.
  - If its output is marked partial (`maxTurns`), resume it once with `SendMessage`. Only resumable agents qualify; Explore and Plan can't be resumed (sub-agents.md; changelog 2.1.246).
  - If its output is empty or malformed, re-dispatch once with something changed.
  - If it failed with an API error or a usage limit, or the user stopped it, report or escalate. Re-dispatching doesn't fix an exhausted quota.
  - If the wave doesn't need its output, continue and flag the gap.
- **A denied tool call.** Don't retry the same call. In an interactive session the denial is the user's answer; where nobody can answer, Claude Code tells Claude that nobody can approve it (headless.md).
- **Iteration cap reached.** Summarize the attempts and the last check output, and offer named options.

## 9. Report Naming

A report lives at `.mz/<root>/<task_name>.md`. `<task_name>` is the `<YYYY_MM_DD>_<skill>_<slug>` name stored in `state.md`, including any `_vN`. `<root>` is `reports` (skill reports), `reviews` (reviews and audits), `research`, `design` or `outreach`.

A run that writes several final files gets a folder, `.mz/<root>/<task_name>/`, as design-document does. Files that persist across runs keep their documented fixed names, such as `.mz/reports/audit_ledger.md`, the cards in `.mz/outreach/active/` and `.mz/outreach/_history/source_quality.json`.

- **Date.** Use the date already in `task_name`, fixed in Phase 0. Don't work out the date again when writing the report.
- **Collisions.** Before writing, check the report path itself. If a file is already there, append the next free `_vN`.
- **Agents.** When a skill dispatches the agent that writes the final report, it passes the full report path; agents don't compose the name. An agent the user runs directly names the report after itself, `<YYYY_MM_DD>_<agent>_<slug>`.
- **Format.** Use `.md` unless the user asks for another format. In that case keep the base name and change only the extension. /combine's lens globs read only `.md`.

## 10. Wave Observability

When a skill dispatches a wave of parallel agents, the orchestrator makes the wave visible: a manifest before launching it, and a rollup once all of its agents have reported. In the terminal, Claude Code shows each dispatch as a tool-call row, lists running subagents in the panel below the prompt and in `/tasks`, and posts a notification when each one finishes. The panel and `/tasks` are transient: a row disappears as soon as its agent succeeds, and `/tasks` keeps finished work for about 30 seconds. None of these views groups agents by wave or checks that an agent returned a valid `STATUS:` line (sub-agents.md; statusline.md). The manifest and rollup record the wave in the skill's own terms.

**Pre-dispatch manifest**, emitted right before the wave's `Agent` calls:

```
Dispatching <wave label> — <N> agents in parallel
Purpose: <one line>
- <agent> — <role, ≤6 words>
- <agent> — <role, ≤6 words>
```

**Post-wave rollup**, emitted once every agent of the wave has reported, failed or been stopped, and before synthesis begins:

```
Wave complete — <returned>/<dispatched> agents returned
- <agent>: <STATUS or VERDICT> — <summary, ≤8 words>
```

- **When.** Emit both blocks for every wave of two or more agents. Skip them for a single dispatch. A skill that runs sequential waves labels each manifest and rollup so they can be told apart.
- **Arrivals.** By default, subagents spawned from the main conversation run in the background, so their reports arrive as separate notifications over later turns (changelog 2.1.198, 2.1.232). Record each arrival in `state.md`.
- **Validity.** An agent counts as returned only with a valid final `STATUS:` line and no partial marking (AGENTS_GUIDELINES.md, "Status Protocol"). Otherwise list it as `<agent>: NO RETURN BLOCK`, and when Claude Code reports why it ended (an API error, a usage limit, a stop), name the cause. The `<returned>/<dispatched>` ratio is exact: if 1 of 5 agents came back empty, the rollup reads `4/5` and names the missing agent.
- **Labels.** Pass each agent's role label as the `Agent` call's `description`, so the terminal rows match the manifest.
- **Privacy.** The manifest, the rollup and each `description` carry agent names, short role labels and status only. They don't print secrets, tokens, absolute paths or raw user data: a label reads `security scan of auth module`, not the module's contents.
- **Unverified.** On Opus 5.5, text written between tool calls may come back as a summarized progress update rather than verbatim (platform: prompting-claude-opus-5-5; not yet checked in Claude Code), so don't treat the manifest as a lasting record. `state.md` is the record.

## 11. Tooling Detection

Resolve the test, lint, format and type-check commands before the first phase that runs one. Use these sources in order:

1. the project instructions Claude Code loaded: CLAUDE.md, or AGENTS.md when there is no CLAUDE.md (best-practices.md; memory.md);
1. `.mz/tooling.json`, when mz-dev-pipe is enabled;
1. the manifests.

Record the result and its source in `.mz/task/<task_name>/tooling.md`.

**No tests.** Treat a missing test command and a command that finds no tests the same way.

- The orchestrator asks before the first phase that needs tests. A dispatched agent returns `NEEDS_CONTEXT` instead.
- When nobody can answer (§8), the skill continues or stops. Skills whose output is tests stop.
- The final report says which.

## 12. Input Parsing

Document the accepted input formats in SKILL.md.

- **Required argument missing:** ask.
- **Ambiguous argument:** resolve what you can from the repo first. Ask only if the readings would lead to materially different work.
- **Optional argument omitted:** take its documented default and say which.
- **Never invent a required value.**

**Argument mechanics** (skills.md; changelog 2.1.19, 2.1.210):

- `$ARGUMENTS` is the full argument string. `$N` and `$ARGUMENTS[N]` are 0-based, and an indexed placeholder with no matching argument stays literal.
- Write `\$` before a digit for a literal dollar sign.
- Quote an `argument-hint` that starts with `[`. Claude Code turns the list form into a string (changelog 2.1.47), but a strict parser reads `[issue]` as a list and rejects `[file] [format]`.
- `argument-hint`, `arguments` and `when_to_use` are Claude Code fields; an upload outside Claude Code that includes them fails (§6).

**Input collectors.** When a skill has to collect missing input, it uses an input collector, not an approval gate. A gate presents an artifact the pipeline produced, for Approve or Reject. A collector gathers a value the pipeline needs before it can run. So a collector has no artifact, no plan message, no Approve/Reject and no block printed before the question. It states the context and the question in one place and reads the answer. Call these "input collectors" or "intake questions".

Collectors come in three shapes:

- **Closed choice**: one pick from a fixed set, such as output format, tone or scope mode. With 2-4 values, use one AskUserQuestion call with each value as a named option (`**<Name>** — <one-line meaning>`). With more, name the most common values as options and list the rest in the question for a typed answer.
- **Confirm or customize**: accept the defaults or supply detail, as in a bootstrap interview. One AskUserQuestion call with options such as `Defaults` and `Minimal`; custom answers come through the typed reply.
- **Open value**: a path, a topic or other free text. Ask a direct prose question that says what is needed and why, then read the reply. AskUserQuestion is built for menus and fits poorly here.

For every shape: collectors run only in the main session, and an empty answer means stop. Re-ask once after an invalid answer, then handle it as in §8.

**Journal.** Closed-choice and confirm-or-customize collectors call AskUserQuestion, so the mz-memory capture hook journals them when that plugin is installed. An open-value collector asked in prose isn't captured. Record the value in `state.md`. When it matters for a later audit, append an `input` entry to `.mz/journal.md` at the project root, in the Layer B format, writing sensitive values as `[redacted]`. Don't call mz-memory's scripts (`guidelines/JOURNAL_GUIDELINES.md`).

## 13. Skill Anatomy

Use these section names, in this relative order, for the content the skill has:

1. `## Overview`: one paragraph on what the skill does. Required.
1. `## When to Use`: one scope line plus redirects to the nearest sibling skills, or the heading `## When NOT to Use` holding only the redirects. Required. Trigger phrases belong in `description` or `when_to_use`, because the body loads only after the skill is picked. A skill with no near-miss sibling doesn't need a redirect list.
1. `## Core Process`: the steps, or the phase table. Required. Be prescriptive where the task is fragile (gates, irreversible actions, output contracts); elsewhere state the goal (agentskills.io, "Calibrate each part independently").
1. `## Techniques`: concrete patterns and tools the skill applies.
1. `## Common Rationalizations`: see AGENTS_GUIDELINES.md, "Anti-Rationalization Tables".
1. `## Red Flags`: signs the skill is being skipped or misapplied.
1. `## Verification`: how to confirm the skill ran.

Sections 4-7 appear only when they carry content. Leave a heading out rather than writing `N/A` or a pointer line. Repo convention for the supporting sections: `## Input`, `## Scope Parameter` and `## Constants` go between When to Use and Core Process; `## References`, `## Error Handling` and `## State Management` go after Verification. Keep anything that has to survive compaction in the first 5,000 tokens (§2).

The pattern comes from addyosmani/agent-skills, `docs/skill-anatomy.md`, which calls itself "a recommended pattern, not a rigid template". The voice of a skill body follows its role (discipline, collaboration or reference) as set out in AGENTS_GUIDELINES.md, "Instruction Wording".

## 14. Pre-Publish Checklist

Run this before merging a new or changed skill.

**Mechanical checks.** These suit a script. Pre-commit already runs two of them, `skill-description-shape` and `skill-reference-path` in `.pre-commit-config.yaml`; check the rest by hand until a repo script runs them in `make test`. The script calls `claude plugin validate --strict` for what Claude Code accepts. A strict YAML parse is a separate check, for the repo's Codex renderer (PyYAML); it doesn't replace validate.

- [ ] `claude plugin validate --strict` passes on the plugin, and the frontmatter parses with a strict YAML parser (§3).
- [ ] `description` plus any `when_to_use` is at most 250 characters; `description` is one line, contains no `<` or `>`, and is quoted if it contains `: ` or starts with `[` or `"` (§3).
- [ ] An `argument-hint` that starts with `[` is quoted (§12).
- [ ] SKILL.md is under about 20,000 characters and 500 lines, phase files are under about 400 lines, and reference files over 100 lines open with a table of contents (§2).
- [ ] Every path in SKILL.md and the phase files resolves inside the plugin, including through its `shared` link. No path reaches into another plugin's directory (§2).
- [ ] Every reference file is listed in SKILL.md (§2).
- [ ] Each AskUserQuestion call has 2-4 options and a `header` of at most 12 characters. A plain gate has exactly Approve and Reject, with no Feedback option (§1).
- [ ] The phase table, if present, sits under `### Phase Overview` and has its delimiter row (§4).
- [ ] No anatomy section is empty, `N/A` or a pointer line (§13).
- [ ] Agent names in dispatch prompts are bare names that match real agent definitions. When a dispatched agent belongs to another plugin, this plugin's `.claude-plugin/plugin.json` lists that plugin in `dependencies` (AGENTS_GUIDELINES.md, "Naming, Organization and Dependencies").
- [ ] The skill cites no guideline rule or section numbers (AGENTS_GUIDELINES.md, "No Rule-Number Citations").

**Review checks**

- [ ] The description opens with a capability clause and "Use when…", covers real phrasings and one request that doesn't name the domain, names the nearest sibling as a counter-trigger, uses plain directives with caps only where an eval backs them, and has no workflow summary (§3).
- [ ] Gates sit before irreversible or expensive steps. Each has the delegation guard, the pre-read, state written first, the verbatim plan message, the selector, and response handling covering Approve, Reject, feedback (looping) and no answer (§1).
- [ ] A variant gate with more than four actions lists the extra ones as typed replies or asks in two calls (§1).
- [ ] Unattended mode, if supported, logs every skipped gate to chat, `state.md`, the journal and the final report, and never auto-approves a variant gate (§1).
- [ ] Phase files are read at the start of their phase, and the current one is re-read after compaction (§2).
- [ ] The phase table is present for a multi-phase skill (§4).
- [ ] A code-editing or analysis skill accepts `scope:`, documents its default and its read and edit boundary, links the shared scope file, and states the edit boundary in every writer dispatch (§5).
- [ ] Bounds and paths are named constants with reasons. Phase files use `<SKILL_DIR>`, `<PLUGIN_ROOT>` and `<PROJECT_ROOT>` placeholders, expanded before use (§6).
- [ ] `state.md` follows STATE_SCHEMA.md, uses the task-name convention, and is written after every phase and before every gate (§7).
- [ ] Predictable failures are listed under `## Error Handling` with their responses. Escalation follows §8, including the case where nobody can answer.
- [ ] Reports use `.mz/<root>/<task_name>.md`, and the skill passes report paths to agents (§9).
- [ ] Every wave of two or more agents has a manifest and a rollup, and stays within the wave cap (§10; AGENTS_GUIDELINES.md, "Parallel Waves").
- [ ] Tooling is resolved in the §11 order and recorded in `tooling.md`, with the no-tests behavior stated.
- [ ] Input formats are documented. Missing, ambiguous and omitted arguments follow §12. Input collectors are kept apart from gates, and open values are recorded in `state.md`.
- [ ] Overview, When to Use and Core Process are present, and what must survive compaction sits in the first 5,000 tokens (§13).
- [ ] Dispatch prompts follow AGENTS_GUIDELINES.md, "Dispatch Prompts". A dispatch that overrides `model` or `effort` gives a one-line reason ("Model and Effort").
- [ ] Wording follows AGENTS_GUIDELINES.md, "Instruction Wording". A skill that guards a rule agents skip under pressure has an anti-rationalization table ("Anti-Rationalization Tables").
- [ ] Terms are used consistently across SKILL.md, phase files and references.
- [ ] The skill works when invoked directly as `/<plugin>:<skill>` and from a natural-language request. A skill Claude can invoke on its own (no `disable-model-invocation: true`) has a `claude plugin eval` suite of at least three cases. Each case has a result grader plus a `tool_used: Skill` grader; in two-arm runs the `tool_used` grader is shown as an indicator rather than scored, and a should-not-trigger case uses `min: 0, max: 0` with `arm: both` (plugin-evals.md; platform: skills best-practices).
