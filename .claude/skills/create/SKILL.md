---
name: create
description: ALWAYS invoke when the user wants to create a new plugin, skill, or agent in this repository. Triggers: "create a skill", "add a new agent", "new plugin", "scaffold", "create component". Reads authoring guidelines and research first, then scaffolds the component following all conventions.
argument-hint: <plugin|skill|agent> <name> [description]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, AskUserQuestion, WebFetch, WebSearch
---

# Component Creator

You create new plugins, skills, and agents in this plugin repository. You MUST read the guidelines and research before writing anything.

## Input

`$ARGUMENTS` — what to create. Expected formats:

- `skill <name> <description>` — create a new skill in an existing plugin
- `agent <name> <description>` — create a new agent in an existing plugin
- `plugin <name> <description>` — scaffold a new plugin with manifest

If the component type, target plugin, or purpose is unclear, ask via AskUserQuestion. Never guess.

## Process

### 1. Read guidelines and research

Before creating anything, read these files in order:

1. `SKILL_GUIDELINES.md` — the 16 rules all skills must follow
1. `researches/claude-plugin-authoring-guide.md` — detailed reference on plugin structure, frontmatter fields, anti-patterns, and review criteria
1. `.mz/research/research_2026_04_07_claude_plugin_best_practices.md` — latest research on description quality, activation patterns, token efficiency, and testing

Extract the relevant rules for the component type being created. For skills: Rules 1-16. For agents: frontmatter conventions, model selection, tools allowlist, maxTurns. For plugins: manifest format, directory layout.

### 2. Examine existing patterns

Read 2-3 existing examples of the same component type in the target plugin to learn the local conventions:

- **Skills**: read SKILL.md + one phase file from the target plugin
- **Agents**: read 2-3 agent files from the target plugin, noting frontmatter pattern
- **Plugins**: read plugin.json + directory layout from an existing plugin

### 3. Plan the component

Present the plan to the user via AskUserQuestion before writing any files:

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

For skills, present:

- Proposed file structure (SKILL.md + phase files if multi-phase)
- Draft description (following Rule 3: directive, third person, WHAT+WHEN, triggers)
- Phase overview (if multi-phase)
- Which agents it will dispatch and their models
- Estimated SKILL.md line count (target 100-150)

For agents, present:

- Proposed frontmatter (name, description, model, effort, maxTurns, tools)
- Role summary and when it would be dispatched

For plugins, present:

- Directory structure
- plugin.json manifest
- Planned skills and agents

Use AskUserQuestion with:

```
Component plan ready. Please review:

<plan details>

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

**Response handling**:

- **"approve"** — proceed to creation.
- **"reject"** — stop. Do not proceed.
- **Feedback** — revise the plan, then return to this gate and re-present **via AskUserQuestion** using the same format. This is a loop — repeat until the user explicitly approves. Never create files without explicit approval.

### 4. Create the component

Write all files following the guidelines. Key rules to enforce:

**For skills:**

- Description: directive phrasing ("ALWAYS invoke when..."), third person, WHAT+WHEN, 2-3 trigger phrases, front-load within 250 chars
- SKILL.md: 100-150 lines max. Frontmatter + input + constants + phase table + inline setup/gates + error handling + state mgmt
- Phase files: under 400 lines each. Read on-demand, never pre-loaded
- Approval gates: delegation guard, approve/reject/feedback, loop language (Rule 1)
- Positive framing over negative. Critical rules at top and bottom (Rule 4)
- Named constants for all bounds. State persisted to disk, not conversation (Rules 7, 8)
- Model selection: opus for accuracy-critical, sonnet for breadth (Rule 12)

**For agents:**

- Description: clear, concise, what it does + when to use it. No plugin-scope noise
- Model: opus for code writing/review/planning, sonnet for research/analysis
- Effort: high for complex tasks, medium for review/scanning
- maxTurns: 25 (reviewers), 40 (researchers), 60 (coders/writers), 80 (orchestrators)
- Tools: explicit allowlist. Read-only agents get Read, Grep, Glob, Bash only. Never omit tools field

**For plugins:**

- Flat plugin.json: only name, description, version, license. No `contents` wrapper
- Auto-discovery: agents/, skills/, commands/, hooks/ at plugin root
- Version must match other plugins (use `set_versions.sh`)

### 5. Verify

After creating all files:

- Check SKILL.md line count (must be ≤ 150)
- Check phase file line counts (must be ≤ 400)
- Verify all phase references in SKILL.md resolve to existing files
- Verify agent names in dispatch prompts match actual agent definitions
- Verify description length and 250-char truncation point
- Verify YAML frontmatter parses (proper `---` delimiters)

Report results to the user.
