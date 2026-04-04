# Claude Code Plugin Repository

This repository is a public plugin registry for Claude Code. It provides agents, rules, and skills that can be imported via `claude plugin marketplace add`.

## Structure

- `.claude-plugin/marketplace.json` — Top-level registry manifest listing all available plugins
- `plugins/<name>/` — Each plugin is a self-contained directory
- `plugins/<name>/plugin.json` — Per-plugin metadata describing contents
- `plugins/<name>/agents/` — Agent definition files (markdown with YAML frontmatter)
- `plugins/<name>/rules/` — Rule fragments (markdown with YAML frontmatter)
- `plugins/<name>/skills/` — Skill definitions (standard Claude Code skill format)

## Adding a New Plugin

1. Create a new directory under `plugins/`
1. Add a `plugin.json` with name, version, description, and contents listing
1. Add agent/rule/skill files in their respective subdirectories
1. Register the plugin in `.claude-plugin/marketplace.json`

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

## Skill Format

Standard Claude Code skill structure with `SKILL.md` containing YAML frontmatter and instructions.
