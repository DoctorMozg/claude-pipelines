# Phase 1: Authoring Loop (RED, GREEN, REFACTOR)

Canonical sources: guidelines/SKILL_GUIDELINES.md, "Skill Descriptions" for Steps 2.2 and 3.1, and "Pre-Publish Checklist" for Step 3.5, which copies it item for item (in the repo checkout; not shipped with the plugin).

The new skill is written test-first. The "tests" are the failures the skill has to prevent, observed before any text is written. The "implementation" is a SKILL.md that answers each of them. Read this file at the start of Phase 1, and re-read it after compaction.

Track the step in `Phase` (`1_red`, `1_green`, `1_refactor`, `1_approval`) and write `state.md` as each step starts. Append every file this run writes to `FilesWritten` as it is written.

## Step 1: RED — find the failures

Before writing any SKILL.md text, collect what goes wrong when the task runs without the skill. Writing backward from real failures keeps each section earning its place.

### 1.1 Gather evidence

Use these sources, strongest first:

- **A run of the task without the skill.** The new skill doesn't exist yet, so any fresh subagent given the task as a user would phrase it is a run without it. Use worktree isolation when the task edits files. Record what it returned, and its transcript path when the session shows one.
- **Reports or transcripts of earlier runs** under `<PROJECT_ROOT>/.mz/`.
- **The seed library.** Search `<SKILL_DIR>/references/anti-rationalization-library.md` for the area heading that matches the rule the new skill guards (its Contents list names the areas), or for a keyword from that rule, rather than reading all of it. A seed row is a lead: keep it only once a run shows the agent making that excuse.

### 1.2 Record each failure

Record each failure in `<PROJECT_ROOT>/.mz/task/<task_name>/red.md`: what the agent did, its excuse verbatim where it skipped a rule, the source (transcript or report path, or the seed row), and the form chosen in 1.3. Don't invent failures; an excuse no agent was seen making tests nothing.

When nothing fails, because the run showed no shortcut, or no run was possible and no earlier transcript or report shows one, write `no observed failures` in `red.md`. The skill then gets no rationalization table: write it from the task's steps and output contract, and mark the checklist's table item n/a with that reason.

### 1.3 Match the form to the failure

Pick the form for each failure as the library's "When a table helps" section sets out:

- **A rule agents know and skip under pressure**: a row in an anti-rationalization table under `## Common Rationalizations`, or merged into `## Red Flags`. Write it as the library's "Format and placement" and "Writing a row" sections describe.
- **Output in the wrong shape**: a positive output contract in Core Process instead of a table.
- **A step the user explicitly chooses to skip**: no row. The skill states the risk once in its report and follows the choice.

**RED exit criterion**: `red.md` records each failure with its source and its form (a table row, an output contract or a Core Process step), or says `no observed failures`.

## Step 2: GREEN — write the skill around the failures

### 2.1 Start from the skeleton

Read `<SKILL_DIR>/references/canonical-skill-anatomy.md` in full and copy its skeleton into `<TARGET_DIR>/SKILL.md`. Before the first write, check that `TARGET_DIR` starts with `<REPO_ROOT>/plugins/`. Put phase files in `<TARGET_DIR>/phases/` and reference files in `<TARGET_DIR>/references/`.

### 2.2 Section pass

1. **Frontmatter.** `name` is `SkillName` from Phase 0. `description` opens with a third-person clause naming what the skill produces or covers, then "Use when…". It covers the phrases users type, at least one request that doesn't name the domain, and the nearest sibling skill as a counter-trigger, because the body loads only after the skill is picked. It has no workflow summary, no "I" or "you", and no all-caps unless `claude plugin eval` shows a gain without firing on near misses. Keep `description` plus any `when_to_use` within `DESCRIPTION_MAX_CHARS`, leave out `<` and `>`, and quote it if it contains `: ` or starts with `[` or `"`. Quote an `argument-hint` that starts with `[`. Add `model:` only when the whole run benefits from that model.
1. **Overview.** One paragraph on what the skill does.
1. **When to Use.** One scope line plus redirects to the nearest sibling skills, or `## When NOT to Use` holding only the redirects. Trigger phrases go in the description, not here. Skip the redirects when no sibling is a near miss.
1. **Core Process.** The steps, or a phase table under `### Phase Overview` for a multi-phase skill (two or more phase files, or any approval gate). Be prescriptive where the task is fragile: gates, irreversible actions and output contracts. Elsewhere state the goal. Place gates as the anatomy reference's "Gate skeleton" says, and follow its skeleton.
1. **Techniques, Common Rationalizations, Red Flags, Verification.** Write each only when Step 1 or the task gives it content, and otherwise leave the heading out. Every Verification check cites its evidence: the command and its output.
1. **Supporting sections**, in the places the anatomy reference's "Sections" gives them. Constants for every bound and path, each bound with a short reason. A References list naming each reference file with what it holds and when to read it. `## Error Handling` with each predictable failure and its response, including the case where nobody can answer. `## State Management` with the state block from the anatomy reference. A skill that edits or analyzes code accepts `scope:`. A skill that writes reports, dispatches waves, runs project tooling, collects input or runs unattended follows the anatomy reference's "Supporting rules".

### 2.3 Sources

Don't invent sources, authors or figures. A claim about Claude Code behavior names its doc page, and a repo precedent names its file. Name a guideline by its filename and section title, never by rule or section number; the skill may number its own steps and refer to them. A skill can't read `guidelines/` at runtime, because no installed plugin reaches that folder; rule text the skill needs ships inside the skill, or in the shared folder the new skill reads as `<PLUGIN_ROOT>/shared/<file>.md`. Delete a citation that trails a sentence which already states the rule.

### 2.4 Wording pass

Read `<SKILL_DIR>/references/persuasion-principles.md`, then re-read the draft against each of its sections, from "Say what to do" to "Register by role", using the role noted in Phase 0. The sections cover positive instructions, the key rule near the top, visible verification, specificity, binding rules with reasons, no emphasis, safety intent in one line, orchestrator lanes and the register for the role.

**GREEN exit criterion**: Overview, When to Use and Core Process are written, no section is empty, `N/A` or a pointer line, every source is real, and the wording matches the role.

## Step 3: REFACTOR — re-test under pressure

Re-read the draft as a skeptic who doesn't want to invoke the skill. This catches what the writing pass missed.

### 3.1 Description stress test

Read only `description` and any `when_to_use`, and ask whether they alone would make Claude pick the skill for a matching request. Check them against Step 2.2 item 1, then:

- Take one near-miss request. Would the description wrongly fire on it?
- Is it within `DESCRIPTION_MAX_CHARS`, counted with the command in Step 3.4 rather than by eye?

If any answer is no, rewrite the description and run this check again.

### 3.2 Check that SKILL.md has every required section heading

List the `## ` headings of `<TARGET_DIR>/SKILL.md`. Overview, When to Use (or When NOT to Use) and Core Process are required. Techniques, Common Rationalizations, Red Flags and Verification may be absent; any that are present follow that relative order and carry real content. Supporting sections sit where the anatomy reference's "Sections" places them. Fix a missing heading, one out of order, or one whose body is empty, `N/A` or a pointer line.

### 3.3 Rationalization table pressure test

Skip this step when the skill has no table. For each row:

- Is the excuse in `red.md` with its source, as an agent's own words rather than invented or taken from the user?
- Is the rebuttal specific: a concrete cost or the rule it protects, with no invented figures?
- Does it push back, rather than agree with a caveat?

Rewrite or drop a row that fails. If no observed row is left, drop the table or go back to Step 1 for evidence.

### 3.4 Run the mechanical checks

Run each check and keep its output for the checklist:

- `claude plugin validate --strict <REPO_ROOT>/plugins/<plugin>`.

- A strict YAML parse of the frontmatter, which also prints the `description` plus `when_to_use` character count. Claude Code accepts some YAML that the repo's Codex renderer rejects, so validate doesn't replace this check:

  ```bash
  python3 -c 'import sys,yaml; fm=yaml.safe_load(open(sys.argv[1]).read().split("---")[1]); print(len(fm["description"])+len(fm.get("when_to_use","")))' "<TARGET_DIR>/SKILL.md"
  ```

- Line and character counts of every markdown file in the skill: `find "<TARGET_DIR>" -name '*.md' -exec wc -lm {} +`.

- Every path in SKILL.md and the phase files resolves inside the plugin, including through its `shared` link.

### 3.5 Run the pre-publish checklist

Print every item as a visible list marked PASS, FAIL or n/a (with the reason), with the command output behind each mechanical item. Mark an item the run can't check itself as open, with what the user has to do: for the invocation test, invoke the skill both ways; for the eval suite, write the cases and run `claude plugin eval`. A FAIL sends the draft back to GREEN or RED. When the same item fails after `MAX_REFACTOR_ATTEMPTS` passes, follow Error Handling in SKILL.md.

**Mechanical checks**

- [ ] `claude plugin validate --strict` passes on the plugin, and the frontmatter parses with a strict YAML parser ("Skill Descriptions").
- [ ] `description` plus any `when_to_use` is at most 250 characters; `description` contains no `<` or `>` and is quoted if it contains `: ` or starts with `[` or `"` ("Skill Descriptions").
- [ ] An `argument-hint` that starts with `[` is quoted ("Input Parsing").
- [ ] SKILL.md is under about 20,000 characters and 500 lines, phase files are under about 400 lines, and reference files over 100 lines open with a table of contents ("Phase and Reference Files").
- [ ] Every path in SKILL.md and the phase files resolves inside the plugin, including through its `shared` link. No path reaches into another plugin's directory ("Phase and Reference Files").
- [ ] Every reference file is listed in SKILL.md ("Phase and Reference Files").
- [ ] Each AskUserQuestion call has 2-4 options and a `header` of at most 12 characters. A plain gate has exactly Approve and Reject, with no Feedback option ("Approval Gates").
- [ ] The phase table, if present, sits under `### Phase Overview` and has its delimiter row ("Phase Overview Table").
- [ ] No anatomy section is empty, `N/A` or a pointer line ("Skill Anatomy").
- [ ] Agent names in dispatch prompts are bare names that match real agent definitions. When a dispatched agent belongs to another plugin, this plugin's `.claude-plugin/plugin.json` lists that plugin in `dependencies` (AGENTS_GUIDELINES.md, "Naming, Organization and Dependencies").
- [ ] The skill cites no guideline rule or section numbers (AGENTS_GUIDELINES.md, "No Rule-Number Citations").

**Review checks**

- [ ] The description opens with a capability clause and "Use when…", covers real phrasings and one request that doesn't name the domain, names the nearest sibling as a counter-trigger, uses plain directives with caps only where an eval backs them, and has no workflow summary ("Skill Descriptions").
- [ ] Gates sit before irreversible or expensive steps. Each has the delegation guard, the pre-read, state written first, the verbatim plan message, the selector, and response handling covering Approve, Reject, feedback (looping) and no answer ("Approval Gates").
- [ ] A variant gate with more than four actions lists the extra ones as typed replies or asks in two calls ("Approval Gates").
- [ ] Unattended mode, if supported, logs every skipped gate to chat, `state.md`, the journal and the final report, and never auto-approves a variant gate ("Approval Gates").
- [ ] Phase files are read at the start of their phase, and the current one is re-read after compaction ("Phase and Reference Files").
- [ ] The phase table is present for a multi-phase skill ("Phase Overview Table").
- [ ] A code-editing or analysis skill accepts `scope:`, documents its default and its read and edit boundary, links the shared scope file, and states the edit boundary in every writer dispatch ("Scope Parameter").
- [ ] Bounds and paths are named constants with reasons. Phase files use `<SKILL_DIR>`, `<PLUGIN_ROOT>` and `<PROJECT_ROOT>` placeholders, expanded before use ("Constants and Paths").
- [ ] `state.md` follows STATE_SCHEMA.md, as copied in the anatomy reference's state blocks, uses the task-name convention, and is written after every phase and before every gate ("State Management").
- [ ] Predictable failures are listed under `## Error Handling` with their responses. Escalation follows "Error Handling and Escalation", including the case where nobody can answer.
- [ ] Reports use `.mz/<root>/<task_name>.md`, and the skill passes report paths to agents ("Report Naming").
- [ ] Every wave of two or more agents has a manifest and a rollup, and stays within the wave cap ("Wave Observability"; AGENTS_GUIDELINES.md, "Parallel Waves").
- [ ] Tooling is resolved in order (project instructions, then `.mz/tooling.json`, then the manifests) and recorded in `tooling.md`, with the no-tests behavior stated ("Tooling Detection").
- [ ] Input formats are documented. Missing, ambiguous and omitted arguments follow "Input Parsing". Input collectors are kept apart from gates, and open values are recorded in `state.md`.
- [ ] Overview, When to Use and Core Process are present, and what must survive compaction sits in the first 5,000 tokens ("Skill Anatomy").
- [ ] Dispatch prompts follow AGENTS_GUIDELINES.md, "Dispatch Prompts". A dispatch that overrides `model` or `effort` gives a one-line reason (AGENTS_GUIDELINES.md, "Model and Effort").
- [ ] Wording follows AGENTS_GUIDELINES.md, "Instruction Wording". A skill that guards a rule agents skip under pressure has an anti-rationalization table (AGENTS_GUIDELINES.md, "Anti-Rationalization Tables").
- [ ] Terms are used consistently across SKILL.md, phase files and references.
- [ ] The skill works when invoked directly as `/<plugin>:<skill>` and from a natural-language request. A skill Claude can invoke on its own (no `disable-model-invocation: true`) has a `claude plugin eval` suite of at least three cases. Each case has a result grader plus a `tool_used: Skill` grader; in two-arm runs the `tool_used` grader is shown as an indicator rather than scored, and a should-not-trigger case uses `min: 0, max: 0` with `arm: both`.

Section names in parentheses are in SKILL_GUIDELINES.md unless another file is named. The rule text these checks need ships in the anatomy reference: its "Supporting rules" cover reports, waves, tooling, input collectors, escalation and unattended mode. Two rules aren't copied into this skill and are only in the repo checkout: what a dispatch prompt carries (AGENTS_GUIDELINES.md, "Dispatch Prompts") and the eval suite format (Claude Code's plugin-evals docs).

**REFACTOR exit criterion**: no item is FAIL.

## Step 4: Draft approval gate

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `<TARGET_DIR>/SKILL.md` and every phase and reference file this run wrote, and capture their full contents.

**State**: write `state.md` with `Phase: 1_approval`, the target path and `awaiting approval: skill draft gate` in `what_remains`. `Status` stays `running` while the gate waits.

**Surface 1: emit the plan message.** Output the draft verbatim as a normal chat message, one heading per file. Wrap each file in a `markdown` fence one backtick longer than the longest backtick run inside it (four backticks for most files), so its frontmatter and headings show as source:

`````
## Skill draft for review: construct-skill

Target: <TARGET_DIR> · Role: <discipline | collaboration | reference> · Checklist: <n> PASS, <n> open

### SKILL.md

````markdown
<verbatim contents of <TARGET_DIR>/SKILL.md>
````

### phases/<file>.md

````markdown
<verbatim contents; one heading and fence per phase file>
````

### references/<file>.md

````markdown
<verbatim contents; one heading and fence per reference file>
````

---
**Approve** → keep the files and finish  ·  **Reject** → move the draft into the task folder and stop  ·  reply with feedback to revise
`````

Emit the full verbatim contents, never a path, summary or placeholder. A draft too long for one message goes out as consecutive messages, whole files each, before the selector.

**Surface 2: call AskUserQuestion.** question: "The skill draft above is ready for review." header: "Skill draft". options: **Approve** — keep the files and finish · **Reject** — move the draft into the task folder and stop.

**Response handling**:

- **Approve** → record the approved `TARGET_DIR` under `## Decisions` in `state.md`, clear `awaiting approval`, set `phase_complete: true`, `what_remains: []` and `Status: complete`, and report completion with any open checklist items.
- **Reject** → append the journal entry first. Then check that `TargetDir` in `state.md` ends in `/skills/<SkillName>/` with a non-empty `SkillName`, that it sits under `<REPO_ROOT>/plugins/<plugin>/skills/`, and that every file under it is listed in `FilesWritten`, which shows this run created it. If all three hold, run `mv "<TARGET_DIR>" "<PROJECT_ROOT>/.mz/task/<task_name>/rejected_draft"`, so the plugin tree is clean and the draft can be recovered, and record the new path in `state.md`. If a check fails or the move is refused, leave the directory where it is and name it in the report. Set `Status: aborted_by_user` and stop.
- **Any other answer** is feedback, including typed text and an Approve whose note asks for a change. Apply it, re-running the RED, GREEN or REFACTOR step it touches, overwrite the files, re-read them, and re-emit the whole plan message from scratch before presenting the selector again. Don't send a diff or a summary: the user approves the draft as it now stands. Loop until the user explicitly approves.
- **No answer** (the call is denied or unavailable, or its result carries the away signal, whatever option it names) → set `Status: blocked`, keep `awaiting approval: skill draft gate` in `what_remains`, leave the plan message in place, and stop. A missing answer is never approval.

**Journal**: once the gate resolves, and on Reject before the move, append a `gate` entry with the command under "Gate skeleton" in the anatomy reference: skill `construct-skill`, phase `1_approval`, gate `skill draft`, and one set of artifact lines per draft file. Journaling never delays the gate.
