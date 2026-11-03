# Claude Code Plugin Repository

This repository is a public plugin registry for Claude Code. It provides agents and skills that can be imported via `claude plugin marketplace add`.

## Structure

- `.claude-plugin/marketplace.json` — Top-level registry manifest: one entry per plugin (`name`, `source`, `category`, `keywords`), the marketplace `metadata.version`, and `renames`, which maps a former plugin name to its current one. Add a `renames` entry whenever a plugin is renamed or removed (plugins/marketplace-reference.md)
- `plugins/<name>/` — Each plugin is a self-contained directory
- `plugins/<name>/.claude-plugin/plugin.json` — Per-plugin manifest: `name`, `version`, `description`, `license`, `author`, and `dependencies` when the plugin dispatches another plugin's agents
- `plugins/<name>/agents/` — Agent definition files (markdown with YAML frontmatter)
- `plugins/<name>/skills/` — Skill definitions (standard Claude Code skill format)
- `plugins/<name>/hooks/hooks.json` — Optional lifecycle hooks; the scripts they run, and any scripts the plugin's skills call, live in `plugins/<name>/scripts/`
- `plugins/mz-base/shared/` — Rule files shared across plugins. Each consumer plugin carries a generated copy at `shared/` in its root, because Anthropic's directory blocks symlinks. Edit only mz-base's copy, then run `make vendor-shared`; `tests/plugin_lint/test_shared_copies.py` fails on drift

## Adding a New Plugin

1. Create a new directory under `plugins/`
1. Add `.claude-plugin/plugin.json` with `name`, `version` (the marketplace's current `metadata.version`), `description`, `license` and `author`, plus `dependencies` if it dispatches another plugin's agents
1. Add agent/skill files in their respective subdirectories
1. Register the plugin in `.claude-plugin/marketplace.json` with `name`, `source`, `category` and `keywords`
1. Give each skill a row in the routing table of `plugins/mz-base/skills/using-mozg-pipelines/SKILL.md`, with its plugin in the last column. Skills marked `user-invocable: false` or `disable-model-invocation: true` are exempt. `tests/plugin_lint/test_router_table.py` fails until every other skill has a row, and fails on a row whose skill no longer ships
1. Add a `[[packages]]` entry for it to `data/codex_migration.toml`, with the same `dependencies` as its manifest. `tests/codex_migration/test_inventory.py` pins the plugin list, the dependency map and the skill and agent counts, so update it in the same change
1. Run `make validate`, which runs `claude plugin validate --strict` on the repo and every plugin, and `make test`, which runs the Python tests as well as the contract matrix and smoke test.

## Bumping Versions

Use the repo-root helper script to bump every version field in one shot: `version` in each `plugins/*/.claude-plugin/plugin.json` and `metadata.version` in `.claude-plugin/marketplace.json`. Marketplace entries carry no version; when both set one, `plugin.json` wins at install time (plugins/marketplace-reference.md). The script runs the agent contract matrix first, checks that each file has exactly one `"version"` field, and fails loudly on drift. Don't hand-edit version strings; they have to stay in sync.

```bash
./set_versions.sh 0.3.0
```

The argument must be semver (`MAJOR.MINOR.PATCH`).

## Agent Format

```yaml
---
name: agent-name
description: "What the agent does. Use when <situation>. Do not use for <near miss>."
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
effort: medium
maxTurns: 20
---

Agent instructions here...
```

See [AGENTS_GUIDELINES.md](guidelines/AGENTS_GUIDELINES.md) for the rules, including: frontmatter fields, tool allowlists, model and effort, descriptions, dispatch prompts, parallel waves, body anatomy and archetypes, the status protocol, review output, instruction wording, the agent/hook interface, naming and dependencies, the citation ban, and the pre-publish checklist.

## Skill Format

Standard Claude Code skill structure: a `SKILL.md` with YAML frontmatter and instructions, plus optional phase and reference files. See [SKILL_GUIDELINES.md](guidelines/SKILL_GUIDELINES.md) for the rules, including: approval gates, phase and reference files, descriptions, the scope parameter, constants and paths, state, error handling, report naming, wave observability, tooling detection, input parsing, skill anatomy, and the pre-publish checklist.

## Hook Format

Plugin hooks live at `plugins/<name>/hooks/hooks.json` and dispatch shell scripts under `plugins/<name>/scripts/`. See [HOOKS_GUIDELINES.md](guidelines/HOOKS_GUIDELINES.md) for the rules, including: configuration and matchers, which output takes effect on each event, exit codes and failure handling, SessionStart sources (context lost to compaction is re-injected from SessionStart with the `compact` matcher), building JSON with `jq`, injected-context limits, defensive input parsing, paths and environment, the time budget, security, testing, and red flags.

## Plugin Authoring Conventions

Cross-cutting preferences that span both agent and skill authoring. These are the items most often forgotten mid-task and most expensive to fix in bulk later.

- **No rule-number citations inside `plugins/`.** No file under `plugins/` cites a guideline by rule or section number (`Rule 17`, `(Rule 20)`, `§7`, `per SKILL_GUIDELINES.md Rule 16`), because the numbers shift whenever a guideline is reorganized. State the substance directly. Where a plugin needs a rule's full text, ship it once in `plugins/mz-base/shared/` and reach it through the plugin's own `shared/` copy. Don't point plugin files at `guidelines/`, which an installed plugin can't read. A guideline file may cite its own sections by number; references between guideline files use section titles. See AGENTS_GUIDELINES.md, "No Rule-Number Citations".
- **Every `gh` call needs a tiered fallback.** Agents and skills that use GitHub CLI document the chain `gh` → GitHub MCP → REST via `curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/...` before emitting `STATUS: BLOCKED`. The MCP tier is reachable only when the agent's `tools` has a matching entry, and repo convention lists both `mcp__github__*` and `mcp__plugin_github_github__*`; for a server with another name, the agent tells the user to copy it into `.claude/agents/` and add that entry. `gh api` filters port to REST unchanged, but `gh pr ... --json` field names don't. See `github-pr-scanner`, `github-pr-reviewer` and `github-pr-data-fetcher` for the canonical pattern.
- **Zero results from a GitHub query are ambiguous.** When a full fan-out returns no PRs, run a one-row smoke test (`gh pr list --state all --limit 1`) before trusting the empty result. Emit one of the disclosure tokens: `ZERO RESULTS VERIFIED`, `ZERO RESULTS UNVERIFIED`, or `ZERO RESULTS GLOBAL`.
- **State lives at `.mz/task/<task_name>/state.md`** under the project root (JOURNAL_GUIDELINES.md, "Project Root"), not the Bash working directory. The task-name pattern is `<YYYY_MM_DD>_<skill>_<slug>` (e.g. `2026_04_20_build_oauth_flow`); on a same-day collision append `_v2`, `_v3`. Write it after every phase transition and before every approval gate. Don't rely on conversation memory for cross-phase state: a compaction summary may drop paths and decisions. Keys, status values and compaction rules are in `guidelines/STATE_SCHEMA.md`.
- **Reports are named after the task.** A report lives at `.mz/<dir>/<task_name>.md` under the project root, where `<dir>` is `reports`, `reviews`, `research`, `design` or `outreach`. A run with several final files gets a `.mz/<dir>/<task_name>/` folder. Files that persist across runs keep their fixed names, such as `.mz/reports/audit_ledger.md`, the cards in `.mz/outreach/active/` and `.mz/outreach/_history/*.json`. See SKILL_GUIDELINES.md, "Report Naming".
- **Interaction journal at `.mz/journal.md`** under the project root: one append-only record of approval gates, input prompts and recorded decisions. When mz-memory is installed, its `PostToolUse` hook on `AskUserQuestion` records every completed call, gates and collectors alike, provided hooks are on and `jq` is on PATH. It never records the artifact, and questions asked in plain prose aren't captured at all. Skills should add an enrichment entry (skill, phase, gate, outcome, artifact), and must add one for every gate skipped in unattended mode; a direct append bypasses the redactor, so write `<private>` values as `[redacted]`. Promote substantial decisions to a `## Decisions` section in `state.md`, which mz-memory harvests into `.mz/memory/MEMORY.md` at SessionEnd once the task's `Status` is `complete`. A `## Lessons` line (`- (<trigger>) WHEN … → … — WHY …`), written when a review finding is accepted and fixed, a step fails, gate feedback corrects a mistake or an approved approach is reversed, goes to `.mz/memory/lessons.md` whatever the `Status` (`guidelines/STATE_SCHEMA.md`, "Body Sections"). See `guidelines/JOURNAL_GUIDELINES.md`.
- **Parallel agent dispatch is capped at 6 concurrent agents per wave.** Split overflow into sequential waves. Subagents spawned from the main conversation run in the background by default, so wait for every agent in the wave to report, then check that each artifact exists on disk before using it. In `claude -p` runs, pre-approve the tools that writer agents need, since nobody is there to answer their permission prompts. See AGENTS_GUIDELINES.md, "Parallel Waves".
- **Approval gates use the two-surface pattern.** Write `state.md` first. Then emit the artifact verbatim as an ordinary markdown chat message (Surface 1), and call AskUserQuestion as a short selector (Surface 2) with exactly two named options, **Approve** and **Reject**. The artifact never goes inside the AskUserQuestion body. There is no "Feedback" option: any other answer, such as text typed in the `Other` row, is feedback, and the orchestrator overwrites the artifact and re-emits the whole plan message from scratch. A missing answer, when AskUserQuestion is denied or unavailable, is never approval: set `Status: blocked` and stop. Variant gates (menus with extra named actions) present each action as `**<Name>** — <one-sentence summary>`. See SKILL_GUIDELINES.md, "Approval Gates", and the reference implementation at `plugins/mz-design/skills/design-document/phases/finalization.md` Step 4.1.
