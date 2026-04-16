---
name: obsidian-cli
description: ALWAYS invoke when using the obsidian CLI tool to interact with a vault from the terminal. Triggers: obsidian CLI, vault command line, obsidian read/create/search from shell.
argument-hint: '[vault operation: read|create|append|search|tags|backlinks|property]'
model: haiku
allowed-tools: Bash, Read
---

## Overview

The `obsidian` CLI is an official command-line interface that requires Obsidian to be running. It allows reading, writing, searching, and inspecting vault notes from a shell.

## When to Use

Invoke when running shell commands against an Obsidian vault, scripting vault operations, or checking note content from the terminal. Trigger phrases: "obsidian CLI", "vault command line", "obsidian read/create/search from shell".

### When NOT to use

- Obsidian is not running — the CLI requires the live Obsidian app to be open.
- Programmatic vault reading without Obsidian running — use direct file reads instead.
- OFM syntax questions with no shell interaction — use `obsidian-markdown`.

## Core Process

1. Verify Obsidian is running before issuing CLI commands.
1. Use `file=<name>` for wikilink-style resolution, or `path=<vault-relative-path>` for exact path resolution.
1. For multi-vault setups, add `vault=<name>` to target a specific vault.

## Techniques

### Parameter conventions

- Parameters use `=` syntax: `file=NoteName`, not `--file NoteName`.
- Flags are boolean with no value: `--copy`, `--silent`, `--total`.
- Multiline content uses `\n` and `\t` escape sequences.

### File resolution

| Form           | Meaning                                        |
| -------------- | ---------------------------------------------- |
| `file=<name>`  | Resolves like a wikilink (search across vault) |
| `path=<path>`  | Exact vault-root-relative path                 |
| `vault=<name>` | Target a specific vault (multi-vault setups)   |

### Read operations

- `obsidian read file=<name>` — print note content.
- `obsidian daily:read` — read today's daily note.
- `obsidian search <query>` — full-text search.
- `obsidian tags` — list all tags.
- `obsidian backlinks file=<name>` — list notes linking to this note.

### Write operations

- `obsidian create file=<name> content=<text>` — create a note.
- `obsidian append file=<name> content=<text>` — append to a note.
- `obsidian daily:append content=<text>` — append to today's daily note.
- `obsidian property:set file=<name> key=<k> value=<v>` — set a frontmatter property.

### Developer / inspection

- `obsidian plugin:reload name=<plugin>` — reload a plugin.
- `obsidian dev:errors` — show console errors.
- `obsidian dev:screenshot` — take a screenshot.
- `obsidian dev:dom` — inspect the DOM.
- `obsidian dev:console` — open the console.
- `obsidian eval code=<js>` — evaluate JavaScript in the Obsidian context.
- `obsidian dev:css` — show applied CSS.

## Common Rationalizations

N/A — reference skill.

## Red Flags

- Using `--file` syntax instead of `file=` — parameters use `=`, not `--`.
- Running CLI commands when Obsidian is not open — the command will hang or error.
- Using `path=` when `file=` would work — `path=` requires an exact vault-root-relative path and is brittle across vault reorganizations.

## Verification

Run `obsidian tags` and confirm output. Obsidian must be running.
