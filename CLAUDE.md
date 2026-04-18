# Claude Code Plugin Repository

This repository is a public plugin registry for Claude Code. It provides agents and skills that can be imported via `claude plugin marketplace add`.

## Structure

- `.claude-plugin/marketplace.json` — Top-level registry manifest listing all available plugins
- `plugins/<name>/` — Each plugin is a self-contained directory
- `plugins/<name>/plugin.json` — Per-plugin metadata (name, version, description, license)
- `plugins/<name>/agents/` — Agent definition files (markdown with YAML frontmatter)
- `plugins/<name>/skills/` — Skill definitions (standard Claude Code skill format)
- `plugins/<name>/hooks/` — Optional `hooks.json` + `scripts/` for lifecycle hooks

## Adding a New Plugin

1. Create a new directory under `plugins/`
1. Add a `plugin.json` with name, version, description, and license
1. Add agent/skill files in their respective subdirectories
1. Register the plugin in `.claude-plugin/marketplace.json`

## Bumping Versions

Use the repo-root helper script to bump all version fields in one shot (all `plugins/*/plugin.json` and `.claude-plugin/marketplace.json` `metadata.version` + per-plugin entries). The script verifies the expected number of `"version"` fields in each file and fails loudly on drift. Do not hand-edit version strings across files — they must stay in sync.

```bash
./set_versions.sh 0.3.0
```

The argument must be semver (`MAJOR.MINOR.PATCH`).

## Agent Format

```yaml
---
name: agent-name
description: "When to use this agent"
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

Agent instructions here...
```

See [AGENTS_GUIDELINES.md](guidelines/AGENTS_GUIDELINES.md) for detailed authoring rules covering frontmatter fields, tool allowlisting, model tiers, status/verdict protocols, and archetype templates.

## Skill Format

Standard Claude Code skill structure with `SKILL.md` containing YAML frontmatter and instructions. See [SKILL_GUIDELINES.md](guidelines/SKILL_GUIDELINES.md) for detailed authoring rules covering approval gates, progressive disclosure, dispatch prompts, error handling, and more.

## Hook Format

Plugin hooks live at `plugins/<name>/hooks/hooks.json` and dispatch shell scripts under `plugins/<name>/scripts/`. See [HOOKS_GUIDELINES.md](guidelines/HOOKS_GUIDELINES.md) for detailed authoring rules covering per-event output schemas (PostCompact requires plain stdout, not `hookSpecificOutput`), exit-code semantics, JSON escaping with `jq`, defensive input parsing, performance budget, and security caveats.

## Plugin Authoring Conventions

Cross-cutting preferences that span both agent and skill authoring. These are the items most often forgotten mid-task and most expensive to fix in bulk later.

- **No rule-number citations inside `plugins/`.** Skill and agent files must not reference `Rule 17`, `(Rule 20)`, or `per SKILL_GUIDELINES.md Rule 16`. State the substance directly or reference the guideline by filename only. The guideline documents themselves may cross-reference their own rules by number; plugin files may not.
- **Every `gh` call needs a tiered fallback.** Agents and skills that use GitHub CLI must document the chain `gh` → GitHub MCP (if session exposes `mcp__*github*` tools) → REST via `curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/...` before emitting `STATUS: BLOCKED`. See `pr-scanner`, `pr-reviewer`, and `github-pr-data-fetcher` for the canonical pattern.
- **Zero results from a GitHub query are ambiguous.** When a full fan-out returns no PRs, run a one-row smoke test (`gh pr list --state all --limit 1`) before trusting the empty result. Emit one of the disclosure tokens: `ZERO RESULTS VERIFIED`, `ZERO RESULTS UNVERIFIED`, or `ZERO RESULTS GLOBAL`.
- **State lives at `.mz/task/<task_name>/state.md`.** The task-name pattern is `<skill>_<slug>_<HHMMSS>`. Never rely on conversation memory for cross-phase state — context compaction destroys it.
- **Parallel agent dispatch is capped at 6 concurrent agents per wave.** Split overflow into sequential waves. Never background writer agents (pr-reviewer, coders, writers) — their file writes are silently dropped.
- **Approval gates use the two-surface pattern.** Every user approval gate must emit a separate, chat-visible pre-gate block (bold title + 1–2 sentence summary + **Approve** / **Reject** / **Feedback** bullet list) BEFORE the AskUserQuestion call, then the AskUserQuestion body carries the verbatim artifact content and closes with `Type **Approve** to proceed, **Reject** to cancel, or type your feedback.` — never the old lowercase `Reply 'approve'…` form. Variant gates (menus with >3 selectable options) must present each option as `**<Name>** — <one-sentence summary>`. See `guidelines/SKILL_GUIDELINES.md` §1 and the reference implementation at `plugins/mz-design/skills/design-document/phases/finalization.md` Step 4.1.
