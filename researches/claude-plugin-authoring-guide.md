# Deep Research: Claude Code Plugin Authoring & Review Guide

**Date**: 2026-04-05
**Subtopics researched**: 6 (plugin distribution, skill authoring, agent authoring, multi-agent orchestration, hooks/commands/MCP, best practices & review criteria)
**Researcher agents dispatched**: 6 (1 replaced after a ~2.5h hang)
**Primary sources cross-referenced**: ~40 Anthropic docs pages and GitHub issues
**Secondary sources consulted**: ~60 community guides, blogs, plugin repositories
**Audience**: maintainers of this `mozg-pipelines` plugin repository — use this as a reference when writing new plugins and when reviewing existing ones.

______________________________________________________________________

## Executive Summary

A Claude Code plugin is a directory containing a `.claude-plugin/plugin.json` manifest (optional since late 2025, name derived from the directory otherwise) plus components in standard subdirectories: `agents/`, `skills/<name>/SKILL.md`, `commands/`, `hooks/hooks.json`, `.mcp.json`. The manifest uses **flat top-level fields** (`name`, `version`, `description`, `agents`, `skills`, `commands`, `hooks`, `mcpServers`, `lspServers`, `outputStyles`, `userConfig`, `channels`), not a wrapping `contents` object — **the three `plugin.json` files in this repo use a non-standard `contents: { agents: [...], skills: [...] }` wrapper that appears in no official schema** and should be migrated to the flat shape before the CLI tightens validation.

Skills and agents are both Markdown-with-YAML-frontmatter files where the body is the full system prompt; their single most load-bearing field is the `description`, which is the only signal Claude uses to decide whether to auto-invoke the component — a vague description is the #1 cause of plugins that silently never trigger. Skills follow a three-level progressive-disclosure model (metadata always loaded ~100 tokens; SKILL.md body loaded on trigger, hard 500-line ceiling; supporting files loaded on demand), and their frontmatter supports Claude-Code-specific fields (`allowed-tools`, `disable-model-invocation`, `user-invocable`, `paths`, `context: fork`, `hooks`) beyond the open Agent Skills standard.

Agents are spawned through the `Agent` tool (renamed from `Task` in v2.1.63) with full context isolation — children inherit nothing from the parent except the `prompt` string, so every subagent prompt must be self-contained; parallel dispatch is achieved by emitting multiple `Agent` tool calls in a single assistant turn with no documented concurrency cap; and subagent output is hard-capped at 32K tokens, which means any non-trivial pipeline must pass results through the filesystem rather than through the return value. Plugin-packaged agents have additional security restrictions: `hooks`, `mcpServers`, and `permissionMode` frontmatter fields are **silently ignored** when loaded from a plugin, so declaring them in this repo's plugin agents is dead configuration. The rest of this document details every field, pattern, anti-pattern, and review criterion needed to write and audit plugins competently against the April 2026 state of Claude Code.

______________________________________________________________________

## Critical Findings for This Repository

Before the reference material, four findings that apply directly to `/home/drmozg/Work/Petproj/claude-mozg-pipelines/` and should be addressed first.

### 1. `plugin.json` files use a non-standard `contents` wrapper (HIGH severity)

**Files affected**:

- `plugins/mz-dev-base/plugin.json`
- `plugins/mz-dev-pipe/plugin.json`
- `plugins/mz-biz-outreach/plugin.json`

**Current shape (non-standard)**:

```json
{
  "name": "mz-dev-base",
  "version": "0.2.0",
  "description": "...",
  "license": "MIT",
  "contents": {
    "agents": [
      { "name": "code-reviewer", "file": "agents/code-reviewer.md", "description": "..." }
    ],
    "skills": [
      { "name": "review-branch", "directory": "skills/review-branch", "description": "..." }
    ]
  }
}
```

**Canonical shape (per [code.claude.com/docs/en/plugins-reference](https://code.claude.com/docs/en/plugins-reference))**:

```json
{
  "name": "mz-dev-base",
  "version": "0.2.0",
  "description": "...",
  "license": "MIT"
}
```

That is — with the current directory layout, the manifest should have **no `contents` field and no `agents`/`skills` fields at all**. Claude Code auto-discovers components by scanning the default directories (`agents/`, `skills/`, `commands/`, `hooks/hooks.json`, `.mcp.json`) at the plugin root. The `contents` wrapper appears nowhere in the official docs, the live Anthropic marketplace, or the community JSON schema at `hesreallyhim/claude-code-json-schema`. The CLI currently tolerates unknown top-level fields so these plugins probably still load via auto-discovery, but the wrapper is dead metadata and will break if the manifest validator becomes strict. The top-level `agents`/`skills`/`commands`/`hooks`/`mcpServers` fields that *are* part of the schema accept a path (string) or array of paths that **replace** the default directories, not per-item metadata.

### 2. Agent file naming mismatch with agent `name` frontmatter (MEDIUM)

Verify each agent file's `name` frontmatter matches what the repo references. The plugin manifest's listed file paths were registered manually — when components are auto-discovered, the `name` field inside each markdown file becomes the canonical identifier, and the containing directory does not need to match.

### 3. Plugin agents declaring `hooks` / `mcpServers` / `permissionMode` (need to audit)

Plugin-loaded agents **silently ignore** these three frontmatter fields. Any agent in this repo that declares them is relying on configuration that doesn't apply. Grep each `agents/*.md` for these keys and either remove them or, if they're needed, move the declarations to `plugin.json` / `hooks/hooks.json` / `.mcp.json` at the plugin root instead.

### 4. Review the `tools:` allowlist on every agent (MEDIUM-HIGH)

Omitting `tools:` inherits **everything**, including MCP tools from the host session. The code-reviewer is read-only and should only list `Read, Grep, Glob, Bash`; pipeline orchestrators should use the `Agent(worker1, worker2, ...)` syntax to lock down which children can be spawned. The outreach enrichment orchestrator already does this correctly — use it as the reference pattern for other orchestrators in the repo.

______________________________________________________________________

## Detailed Findings

### Section A — Plugin Manifest & Directory Layout

#### A.1 Canonical directory structure

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json          # ONLY file that belongs here (common mistake: nesting components here)
├── agents/                  # Subagent markdown files
├── skills/
│   └── <name>/
│       ├── SKILL.md         # Required entrypoint for each skill
│       ├── reference.md     # Optional supporting material, one level deep
│       └── scripts/         # Optional executable scripts
├── commands/                # Legacy slash commands (unified with skills; still supported)
├── hooks/
│   └── hooks.json           # Plugin hook config (wrapped format — see Section F)
├── .mcp.json                # Plugin-bundled MCP server configs
├── .lsp.json                # LSP servers
├── bin/                     # Executables added to Bash PATH while plugin is enabled
└── settings.json            # Plugin-default settings (limited support today)
```

Subdirectories outside `.claude-plugin/` are auto-discovered at the plugin root. Putting `agents/` or `skills/` inside `.claude-plugin/` is a common mistake that the official docs explicitly call out.

#### A.2 `plugin.json` schema (flat top-level fields)

The manifest is **optional** since late 2025 — if omitted, Claude Code derives the plugin `name` from the directory name and discovers all components via default paths. When present, the manifest uses flat top-level fields:

| Field                                           | Type                      | Purpose                                                                                                      |
| ----------------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `name`                                          | string                    | **Required if manifest exists.** Kebab-case, no spaces. Used as namespace prefix (`plugin-name:skill-name`). |
| `version`                                       | string                    | SemVer. **Used to detect updates — forgetting to bump it means users never see changes.**                    |
| `description`                                   | string                    | Shown in plugin manager.                                                                                     |
| `author`                                        | object                    | `{ name, email?, url? }`.                                                                                    |
| `homepage`, `repository`, `license`, `keywords` | —                         | Standard metadata.                                                                                           |
| `commands`                                      | string \| array           | Custom command paths (**replaces** default `commands/`).                                                     |
| `agents`                                        | string \| array           | Custom agent paths (replaces default `agents/`).                                                             |
| `skills`                                        | string \| array           | Custom skill paths (replaces default `skills/`).                                                             |
| `hooks`                                         | string \| array \| object | Path to `hooks.json` or inline config.                                                                       |
| `mcpServers`                                    | string \| array \| object | Path to `.mcp.json` or inline.                                                                               |
| `lspServers`                                    | string \| array \| object | Path to `.lsp.json` or inline.                                                                               |
| `outputStyles`                                  | string \| array           | Custom output style paths.                                                                                   |
| `userConfig`                                    | object                    | Values Claude Code prompts for at enable time. `sensitive: true` routes the value to the OS keychain.        |
| `channels`                                      | array                     | Message-injection channels bound to one of the plugin's MCP servers. Telegram/Slack/Discord-style.           |

**Important**: when you set `commands`/`agents`/`skills` in the manifest, the custom paths **replace** the defaults — to keep the default `skills/` directory and add more paths, list both explicitly.

#### A.3 `marketplace.json` (catalog file, not a plugin)

A marketplace is a separate catalog file at `.claude-plugin/marketplace.json` in a repo root. It lists plugins that live either in the same repo (`"source": "./plugins/x"`) or in external sources.

Required top-level fields:

- `name` — kebab-case, public-facing
- `owner` — object with required `name`, optional `email`, `url`
- `plugins` — array of plugin entries

Optional: `metadata.{description, version, pluginRoot}`. `metadata.pluginRoot` lets you write `"source": "formatter"` instead of `"./plugins/formatter"`.

Plugin `source` field supports **five types**, each with optional `ref` (branch/tag) and `sha` (exact commit) pinning:

| Source type   | Shape                                      | Notes                                                                                         |
| ------------- | ------------------------------------------ | --------------------------------------------------------------------------------------------- |
| Relative path | `"./plugins/x"` (string)                   | Only works when the marketplace is added via git, NOT URL. Resolved against marketplace root. |
| `github`      | `{ source, repo, ref?, sha? }`             | `owner/repo` format.                                                                          |
| `url`         | `{ source, url, ref?, sha? }`              | Any git URL incl. SSH.                                                                        |
| `git-subdir`  | `{ source, url, path, ref?, sha? }`        | Sparse clone for monorepos.                                                                   |
| `npm`         | `{ source, package, version?, registry? }` | Private registries supported.                                                                 |

Reserved names: `claude-plugins-official`, `anthropic-marketplace`, and a few others.

______________________________________________________________________

### Section B — Distribution, Installation & Publishing

#### B.1 CLI command reference

| Command                                  | Purpose                                                                                                                                                              |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/plugin`                                | 4-tab interactive UI (Discover / Installed / Marketplaces / Errors)                                                                                                  |
| `/plugin marketplace add <source>`       | Subscribe to a marketplace. Sources: GitHub shorthand `owner/repo`, git URL, local path, direct URL to `marketplace.json`. Pin with `@ref` (GitHub) or `#ref` (URL). |
| `/plugin marketplace list`               | List subscribed marketplaces                                                                                                                                         |
| `/plugin marketplace update [name]`      | Refresh one or all                                                                                                                                                   |
| `/plugin marketplace remove <name>`      | **Uninstalls all plugins from it**                                                                                                                                   |
| `/plugin install <name>@<marketplace>`   | Install a plugin. `--scope user\|project\|local`                                                                                                                     |
| `/plugin uninstall <name>@<marketplace>` | Uninstall. `--keep-data` preserves `${CLAUDE_PLUGIN_DATA}`                                                                                                           |
| `/plugin enable <name>@<marketplace>`    | Enable without removing                                                                                                                                              |
| `/plugin disable <name>@<marketplace>`   | Disable without removing                                                                                                                                             |
| `/plugin update <name>@<marketplace>`    | Update to latest                                                                                                                                                     |
| `/plugin validate <path>`                | Validate manifest + frontmatter                                                                                                                                      |
| `/reload-plugins`                        | Hot-reload in running session                                                                                                                                        |
| `claude --plugin-dir <path>`             | Load plugin live from disk (development; bypasses cache; repeatable)                                                                                                 |
| `claude plugin <subcommand>`             | Non-interactive equivalents of all `/plugin` commands                                                                                                                |

#### B.2 Cache, persistence, and file resolution

- Installed plugins are **copied** (not symlinked) into `~/.claude/plugins/cache`. Paths like `../shared-utils` in a plugin do NOT survive the copy; symlinks *inside* the plugin dir are followed.
- `${CLAUDE_PLUGIN_ROOT}` — absolute path to the plugin's current cache location. **Changes on every update**; files written here do NOT persist.
- `${CLAUDE_PLUGIN_DATA}` — persistent per-plugin directory at `~/.claude/plugins/data/{id}/` where `{id}` is `plugin-name` with `@marketplace-name` sanitized. Use this for `node_modules`, Python venvs, caches, generated code. Deleted on final uninstall unless `--keep-data` is passed.
- `--plugin-dir /path` bypasses the cache entirely — reads files live from disk, hot-reloadable via `/reload-plugins`. Same-name plugins loaded via `--plugin-dir` take precedence over installed ones.

#### B.3 Version & update mechanics

- Claude Code decides a plugin has a new version by reading the `version` field in `plugin.json`.
- **If code changes but `version` is not bumped, users will not see the update.** The cached copy wins silently.
- If `version` is set in both `plugin.json` and the marketplace entry, `plugin.json` wins. For relative-path plugins set it in the marketplace entry; otherwise in `plugin.json`.
- Auto-update runs at session start. Anthropic's official marketplaces have it ON by default; third-party and `--plugin-dir` have it OFF.
- Kill switches: `DISABLE_AUTOUPDATER=1`, `FORCE_AUTOUPDATE_PLUGINS=1`, `CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE=1`, `CLAUDE_CODE_PLUGIN_GIT_TIMEOUT_MS=<ms>`.

#### B.4 Private repositories & enterprise

- Interactive auth uses the system git credential helper (`gh auth login`, Keychain, etc.).
- Background auto-updates require env vars: `GITHUB_TOKEN`/`GH_TOKEN`, `GITLAB_TOKEN`/`GL_TOKEN`, `BITBUCKET_TOKEN`.
- SSH URLs (`git@github.com:owner/repo.git`) are accepted.
- **Enterprise lockdown**: set `strictKnownMarketplaces` in managed-settings.json to an exact allowlist (or `[]` for total lockdown). Supports `hostPattern` and `pathPattern` regex modes for fleet deployment.
- `enabledPlugins` in settings.json records per-scope on/off state: `{ "plugin@marketplace": true }`.
- Container/CI seed distribution: `CLAUDE_CODE_PLUGIN_SEED_DIR=/path` loads read-only pre-populated plugins at runtime.

#### B.5 Trust model — no signing, no curation

- **There is no curation on the official Anthropic marketplace.** Anthropic maintains the catalog but does not audit plugin contents.
- **No plugin signing, no integrity check, no hash verification.** `anthropics/claude-code` issue #29729 is an open feature request.
- **No "download-only, review-before-run" mode.** Issue #28879 is open. Hooks and MCP servers become active the moment the plugin is enabled.
- [PromptArmor April 2026](https://www.promptarmor.com/resources/hijacking-claude-code-via-injected-marketplace-plugins) and [SentinelOne January 2026](https://www.sentinelone.com/blog/marketplace-skills-and-dependency-hijack-in-claude-code/) have documented real-world supply-chain attacks exploiting this.

______________________________________________________________________

### Section C — Skill Authoring

#### C.1 `SKILL.md` file format

A skill is a directory whose entrypoint is a file literally named `SKILL.md` (case-sensitive). YAML frontmatter between `---` markers, Markdown body after.

**Required fields** (per the open Agent Skills standard):

- `name` — lowercase `[a-z0-9-]`, max 64 chars, cannot contain reserved words `"anthropic"` or `"claude"`. In **Claude Code specifically**, `name` is optional — if omitted, the directory name is used.
- `description` — max 1024 chars, no XML tags, truncated to 250 chars in the skill listing Claude sees for triggering.

**Claude Code extensions** (optional):

| Field                      | Purpose                                                                                                                                                                       |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `argument-hint`            | Autocomplete hint for slash command, e.g. `[issue-number]`                                                                                                                    |
| `disable-model-invocation` | `true` = only the user can invoke via `/name`; Claude cannot auto-invoke                                                                                                      |
| `user-invocable`           | `false` = hidden from `/` menu; only Claude can invoke                                                                                                                        |
| `allowed-tools`            | Tools Claude can use without asking permission while the skill is active. **Note: not always enforced as a hard boundary (issue #18837) — treat as documentation of intent.** |
| `model`                    | Override model when this skill is active                                                                                                                                      |
| `effort`                   | `low`\|`medium`\|`high`\|`max` (max is Opus-4.6-only)                                                                                                                         |
| `context`                  | `fork` — runs in a forked subagent context                                                                                                                                    |
| `agent`                    | Which subagent type to use when `context: fork` is set                                                                                                                        |
| `hooks`                    | Skill-scoped lifecycle hooks                                                                                                                                                  |
| `paths`                    | Glob patterns that gate automatic activation to matching files                                                                                                                |
| `shell`                    | `bash` (default) or `powershell` for \`!`command` blocks                                                                                                                      |

String substitutions inside the body: `$ARGUMENTS`, `$ARGUMENTS[N]`, `$N`, `${CLAUDE_SESSION_ID}`, `${CLAUDE_SKILL_DIR}`, `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_PLUGIN_DATA}`.

Inline shell execution: `` !`gh pr diff` `` single-line and fenced ````  ```! ````\\n...\\n` ` multi-line. Output replaces the placeholder **before** Claude sees the content.

#### C.2 Progressive disclosure — the defining architectural principle

| Level               | When loaded    | Token cost                          | Content                                         |
| ------------------- | -------------- | ----------------------------------- | ----------------------------------------------- |
| **1. Metadata**     | Always         | ~100 tokens / skill                 | `name` + `description` from frontmatter         |
| **2. Instructions** | When triggered | Target **< 500 lines / ~5k tokens** | SKILL.md body                                   |
| **3. Resources**    | On demand      | Effectively unlimited               | Bundled files: `reference.md`, schemas, scripts |

Why it matters:

1. The description is the only thing Claude sees for selection.
1. The body competes with conversation history once loaded.
1. Bundled files are free until read; scripts executed via bash never enter context at all (only stdout does).
1. **Hard ceiling: 500 lines for SKILL.md** — repeated in every authoritative source.

#### C.3 Writing descriptions that actually trigger

The single most common reason a skill never auto-invokes is a vague description. Rules from the official best-practices page and the `skill-creator` meta-skill:

1. **Third person only.** "Processes Excel files" — NOT "I can help you...".
1. **"Use when..." phrasing.** The single most consistent pattern across all official examples.
1. **Be "pushy."** Claude undertriggers by default; descriptions should be explicit about when to fire.
1. **List real trigger phrases** users would actually type.
1. **Front-load the key use case** — past 250 chars it's truncated.
1. **Avoid aggressive language on Claude 4.5/4.6.** "CRITICAL: You MUST ALWAYS use this tool" now causes *overtriggering*. Use normal phrasing plus the `effort` parameter instead.

Good vs bad:

```yaml
# BAD
description: Helps with documents
description: I can help you process Excel files

# GOOD
description: Extract text and tables from PDF files, fill forms, merge documents. Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.
description: Expert code review specialist. Proactively reviews code for quality, security, and maintainability. Use immediately after writing or modifying code.
```

#### C.4 Bundling supporting files

Canonical layout:

```
my-skill/
├── SKILL.md           # Required entrypoint
├── reference.md       # Extra docs, loaded on demand
├── scripts/
│   ├── validate.py    # Executed via bash, never enters context
│   └── helper.sh
└── assets/            # Templates, binary resources
    └── template.docx
```

Rules:

1. **Reference every file from SKILL.md explicitly** — unreferenced files are dead.
1. **Keep references one level deep.** Claude may `head -100` nested references and miss content.
1. **Table of contents at the top of reference files >100 lines.**
1. **Forward slashes in paths**, even on Windows.
1. **Organize by domain** for multi-domain skills (`reference/finance.md`, not `docs/file1.md`).
1. **Unambiguous execution intent** — "Run `analyze_form.py` to extract fields" (execute) vs "See `analyze_form.py` for the algorithm" (read).

#### C.5 Namespacing inside plugins

- Plugin skills live at `plugins/<plugin>/skills/<skill>/SKILL.md`.
- Slash command becomes `/<plugin-name>:<skill-name>`.
- Namespacing is **always enforced** — cannot be disabled.
- Precedence: managed > user (`~/.claude/skills/`) > project (`.claude/skills/`). Plugin skills live in their own namespace.
- Discovery: `.claude/skills/` subdirectories in the current project tree are auto-discovered (monorepo support). `--add-dir` grants file access and discovers skills (but NOT other config types) in those directories.

______________________________________________________________________

### Section D — Agent Authoring

#### D.1 Agent file format

Markdown with YAML frontmatter. Body becomes the full system prompt — it replaces (not supplements) Claude Code's default system prompt for that subagent.

**Required fields**: `name`, `description`.

**Complete frontmatter reference** (from [code.claude.com/docs/en/sub-agents](https://code.claude.com/docs/en/sub-agents)):

| Field             | Purpose                                                                               |
| ----------------- | ------------------------------------------------------------------------------------- |
| `name`            | Kebab-case unique identifier                                                          |
| `description`     | When Claude should delegate. **The single most load-bearing field.**                  |
| `tools`           | Comma-separated allowlist. **Omit = inherit everything, including MCP**               |
| `disallowedTools` | Denylist applied before allowlist                                                     |
| `model`           | `sonnet`\|`opus`\|`haiku`\|full ID (`claude-opus-4-6`)\|`inherit` (default)           |
| `permissionMode`  | `default`\|`acceptEdits`\|`auto`\|`dontAsk`\|`bypassPermissions`\|`plan`              |
| `maxTurns`        | Max agentic turns before stop                                                         |
| `skills`          | Skills preloaded into the subagent's context                                          |
| `mcpServers`      | Inline MCP configs                                                                    |
| `hooks`           | Lifecycle hooks (PreToolUse, PostToolUse, Stop) scoped to this subagent               |
| `memory`          | `user`\|`project`\|`local` — persistent memory directory                              |
| `background`      | `true` forces background execution                                                    |
| `effort`          | `low`\|`medium`\|`high`\|`max`                                                        |
| `isolation`       | Only valid value: `worktree` — runs in a temporary git worktree                       |
| `color`           | UI display only: `red`\|`blue`\|`green`\|`yellow`\|`purple`\|`orange`\|`pink`\|`cyan` |
| `initialPrompt`   | Auto-submitted first user turn when the agent runs as main (`--agent`)                |

**Plugin agent restrictions**: When an agent is loaded from a plugin, the following fields are **silently ignored for security reasons**: `hooks`, `mcpServers`, `permissionMode`. Supported for plugin agents: `name`, `description`, `model`, `effort`, `maxTurns`, `tools`, `disallowedTools`, `skills`, `memory`, `background`, `isolation`.

#### D.2 Tool scoping

- **Omitted `tools` → inherits everything**, including MCP. This is the #1 tool-scoping anti-pattern.
- **Read-only agents** (reviewers, researchers, analyzers): `Read, Grep, Glob` + `WebFetch, WebSearch` if needed. Never `Write` or `Edit`.
- **Test runners**: `Bash, Read, Grep`.
- **Code modifiers**: `Read, Edit, Write, Grep, Glob`.
- **Agent spawn restriction**: `tools: Agent(worker, researcher)` — allowlist of child subagents. `Agent` bare = any subagent. `Agent` omitted = **no subagents can be spawned**. Only applies to main-thread agents (`--agent`) since subagents cannot spawn children.

#### D.3 Model selection

Resolution order (highest wins):

1. `CLAUDE_CODE_SUBAGENT_MODEL` env var
1. Per-invocation `model` parameter from parent
1. Agent definition's `model` frontmatter
1. Main conversation's model

| Model          | Use for                                                                            | Cost relative                               |
| -------------- | ---------------------------------------------------------------------------------- | ------------------------------------------- |
| **Haiku 4.5**  | Read-heavy exploration, log parsing, simple summaries, built-in `Explore` subagent | ~$0.80/$4 per M tok (19× cheaper than Opus) |
| **Sonnet 4.6** | Everyday coding, writing, analysis, debugging                                      | ~$3/$15 per M tok                           |
| **Opus 4.6**   | Architecture, security audits, code review, complex reasoning, research synthesis  | ~$15/$75 per M tok                          |

Community convention (from wshobson/agents four-tier strategy):

- Opus for architecture, security, code review (~23% of agents)
- Inherit (default) (~23%)
- Sonnet for docs, testing, standard dev (~28%)
- Haiku for deployment, SEO, mechanical ops (~10%)

**Anti-pattern**: defaulting every subagent to `inherit` when the session runs Opus — silently 5× the cost for tasks any cheaper model handles.

#### D.4 Context isolation

Each subagent invocation creates a fresh 200K-token context window. The child receives:

- Its own system prompt (the markdown body)
- The parent's `prompt` string — **this is the only channel from parent to child**
- Basic environment (cwd, platform)
- Project `CLAUDE.md`
- Tools (inherited or explicit `tools` list)
- Skills listed in the `skills:` frontmatter (not inherited from parent)

The child does **NOT** receive:

- Parent's conversation history
- Previous tool calls or results
- Parent's system prompt

**Implications**:

- Every subagent prompt must be self-contained. No "as discussed above", no "continue our work".
- Parent must inject file paths, error messages, assumptions, and expected output format into the spawn prompt.
- Only the final message returns to the parent — intermediate tool calls stay in the child.

#### D.5 Body structure pattern (community consensus)

No official style guide, but every high-quality agent repo converges on this shape:

1. **Role statement** — "You are a senior X specializing in Y."
1. **When invoked / Initial steps** — numbered list of first actions.
1. **Core principles / Expertise areas** — domain knowledge bullets.
1. **Process / Workflow** — numbered steps.
1. **Checklists** — one per concern (security, performance, etc.).
1. **Output format** — exact structure of the return value.
1. **Guidelines / Anti-patterns** — things to avoid.
1. **Handoff / HITL rules** — when to stop and ask.

Typical lengths: Anthropic's own example agents are 20-40 lines; production agents in wshobson/agents and VoltAgent are 80-300 lines; extremely detailed ones go 400-600.

______________________________________________________________________

### Section E — Multi-Agent Orchestration

#### E.1 The `Agent` tool

Single spawn primitive (renamed from `Task` in v2.1.63). Schema:

```json
{
  "required": ["description", "prompt", "subagent_type"],
  "properties": {
    "description":   "3-5 word summary shown in UI",
    "prompt":        "Full self-contained instructions for the child",
    "subagent_type": "Agent name (e.g. Explore, code-reviewer, researcher)"
  }
}
```

Optional parameters: `model`, `resume` (for continuing a prior agent by ID), `run_in_background`, `max_turns`. The parent receives only the final `tool_result` — all intermediate reasoning stays in the child. The `agentId` in the result can be passed back via `resume` to continue work.

**Critical constraints**:

- **No nesting.** Subagents cannot spawn other subagents. `Agent(...)` in a subagent's `tools` has no effect.
- **32K output token hard cap** on the final message (issue #25569). `CLAUDE_CODE_MAX_OUTPUT_TOKENS` does NOT apply. **Workaround: write results to a file, return a short summary + path.**
- **Background agents silently fail on writes** (issue #40751). They auto-deny permission prompts, so `Write`/`Edit` operations complete "successfully" without landing.
- **Windows command-line length limit** (8191 chars) affects prompts passed via `--agents` JSON. Use filesystem-defined agents for long prompts.

#### E.2 Parallel dispatch

No special API. The parent emits N `Agent` tool-use blocks in one assistant turn; Claude Code fires them concurrently and waits for all to return before the next turn. Reliable trigger phrasing:

> "Research the authentication, database, and API modules in parallel using separate subagents"
> "Then spawn 4 agents in parallel (single message, 4 tool calls): ..."

**Concurrency limits**:

- **No hardcoded limit**; issue #15487 documented a 24-parallel-agent lockup; feature request for `maxParallelAgents` closed `NOT_PLANNED`.
- Practical: 5-6 agents for light tasks, 3-4 for medium, ~2 for heavy workloads.
- Anthropic's research system uses **3-5 subagents simultaneously** at the lead level.

#### E.3 Token economics

From Anthropic's own post-mortem ([multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)):

> "Agents typically use about 4× more tokens than chat interactions, and multi-agent systems use about 15× more tokens than chats."
> "Token usage by itself explains 80% of the variance" in performance.
> A system with Opus 4 as lead and Sonnet 4 as subagents **outperformed single-agent Opus 4 by 90.2%** on their research eval.

**Decision rule (direct quote)**: *"Multi-agent systems require tasks where the value of the task is high enough to pay for the increased performance."*

Cost optimization patterns:

- Opus orchestrator, Sonnet/Haiku workers (used by Anthropic themselves).
- `CLAUDE_CODE_SUBAGENT_MODEL` env var forces all children to a cheaper model.
- Per-agent `model:` frontmatter sets defaults.

#### E.4 Orchestration pattern catalog

**Pattern 1 — Pipeline (Prompt Chaining)**
`A → B → C → D`. Use when steps have clear dependencies. Orchestrate from main thread (subagents can't chain). Each stage writes artifact to file; next stage reads. Use `SubagentStop` hooks for quality gates.

**Pattern 2 — Map / Map-Reduce (Parallel Sectioning)**
One parent fans out N identical-shaped tasks, then a reducer synthesizes. Use for N files/companies/modules to process independently. Each worker writes to `.out/<slug>/result.json` to avoid 32K cap. **The local `mz-biz-outreach` enrichment orchestrator is a canonical example of this.**

**Pattern 3 — Orchestrator-Workers (Dynamic Decomposition)**
Lead LLM decides at runtime how many workers and what they do. Use Opus for the orchestrator (decomposition is expensive); Sonnet/Haiku for workers. Anthropic's research system is the canonical implementation.

**Pattern 4 — Router / Dispatcher**
Parent classifies and hands off to exactly one specialist. Main-thread agent is the router; subagents are specialists. Use `tools: Agent(specialist-a, specialist-b, ...)` as explicit allowlist.

**Pattern 5 — Evaluator-Optimizer (Review Loop)**
Generator → Evaluator → Generator revises → repeat. Two distinct subagents: `generator` (writes) and `reviewer` (read-only). Main thread runs the loop. **Anti-pattern**: the generator should not review its own output — it retains reasoning context and won't question choices it just made.

**Pattern 6 — Supervisor / Debate**
N workers investigate the same question from different angles. Subagents can't message each other, so with plain subagents you get parallel independent investigation; the main agent synthesizes. True debate requires experimental agent teams (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`).

#### E.5 Prompt construction for subagents

Anthropic's four-piece checklist for every delegation prompt:

1. **Concrete objective** — what to accomplish
1. **Output format** — structured, specific, ideally file-based for large outputs
1. **Tool/source guidance** — which tools, which sources
1. **Clear boundaries** — what NOT to do, scope limits

Plus: include all file paths, error messages, and prior decisions verbatim; specify approximate tool-call budget (simple: 3-10, complex: 10+); ask for structured output explicitly.

#### E.6 Agent teams (experimental)

Separate system from subagents, gated behind `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, requires v2.1.32+. Key differences:

|               | Subagents           | Agent teams                                  |
| ------------- | ------------------- | -------------------------------------------- |
| Scope         | One session         | Separate sessions, shared task list          |
| Communication | Child → parent only | Teammate ↔ teammate direct messaging         |
| Coordination  | Main agent manages  | Shared task list, file-locked claims         |
| Best for      | Focused results     | Discussion, debate, parallel implementation  |
| Cost          | Lower               | Higher (each teammate is a full CC instance) |

Recommend cautiously — known issues with session resumption, shutdown timing, task-status lag.

______________________________________________________________________

### Section F — Hooks, Commands & MCP

#### F.1 Hook events (25+)

Abbreviated list; full reference at [code.claude.com/docs/en/hooks](https://code.claude.com/docs/en/hooks):

| Event                                | Fires                                    | Can block?  |
| ------------------------------------ | ---------------------------------------- | ----------- |
| `SessionStart`                       | Session begins/resume/clear/post-compact | No          |
| `UserPromptSubmit`                   | User submits a prompt                    | Yes         |
| `PreToolUse`                         | Before any tool call                     | Yes         |
| `PermissionRequest`                  | Permission dialog                        | Yes         |
| `PostToolUse` / `PostToolUseFailure` | Tool completes                           | No          |
| `SubagentStart` / `SubagentStop`     | Subagent lifecycle                       | Stop: Yes   |
| `Stop` / `StopFailure`               | Main turn ends                           | Stop: Yes   |
| `FileChanged`                        | Watched file changes on disk             | No          |
| `CwdChanged`                         | cwd changes                              | No          |
| `WorktreeCreate` / `WorktreeRemove`  | git worktree lifecycle                   | Create: Yes |
| `PreCompact` / `PostCompact`         | Context compaction                       | No          |
| `SessionEnd`                         | Session terminates                       | No          |

Handler types: `command` (shell), `http` (POST event JSON), `prompt` (LLM-based decision), `agent` (spawns sub-agent).

#### F.2 Plugin hook declaration — `hooks/hooks.json` uses a wrapper format

**Critical distinction**:

- **Plugin `hooks/hooks.json`** wraps events under `"hooks": { ... }` with optional `"description"`.
- **User `.claude/settings.json`** puts events directly under top-level `"hooks": { ... }` — no wrapper.

```json
// plugin hooks/hooks.json
{
  "description": "Automatic code formatting",
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [{
          "type": "command",
          "command": "${CLAUDE_PLUGIN_ROOT}/scripts/format.sh",
          "timeout": 30
        }]
      }
    ]
  }
}
```

Matcher rules: regex against tool name for `PreToolUse`/`PostToolUse`; session-type strings for `SessionStart`; no matcher for `UserPromptSubmit`, `Stop`, etc.

Decision control via JSON on stdout:

```json
{
  "continue": true,
  "systemMessage": "Visible to user",
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask|defer",
    "permissionDecisionReason": "Why",
    "updatedInput": { "command": "modified" }
  }
}
```

Exit codes: 0 = success, 2 = blocking error (stderr fed back, JSON ignored), other = non-blocking warning.

**Plugin hooks merge with user hooks and run in parallel.** There is no documented deterministic ordering between plugins — reviewers cannot assume plugin A's `deny` beats plugin B's `allow`.

#### F.3 Commands unified with Skills

`.claude/commands/deploy.md` and `.claude/skills/deploy/SKILL.md` both create `/deploy` and work identically. For new development, prefer skills (directory-per-skill, supporting files, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `paths`, dynamic context injection). Legacy `commands/` remains supported.

Plugin slash commands are always namespaced: `/plugin-name:skill-name`.

#### F.4 MCP servers bundled in plugins

Declared in `.mcp.json` at plugin root or inline as `mcpServers` in `plugin.json`. Same format as user-level `~/.claude/mcp.json`. Use `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` substitutions.

```json
{
  "mcpServers": {
    "plugin-api-client": {
      "command": "npx",
      "args": ["@company/mcp-server@1.2.3", "--plugin-mode"],
      "cwd": "${CLAUDE_PLUGIN_ROOT}",
      "env": { "DB_PATH": "${CLAUDE_PLUGIN_DATA}" }
    }
  }
}
```

- Plugin MCP servers start **automatically** when the plugin is enabled — no separate `/mcp` activation.
- They appear as `mcp__<server>__<tool>` alongside user-configured MCP tools.
- **Security**: pin npm package versions. Unpinned `npx @package` pulls latest on every launch — supply-chain risk.

#### F.5 Common hook gotchas

1. **Stop-hook infinite loop** — Stop hooks that always block keep Claude generating forever. Check `stop_hook_active` in input.
1. **External API calls in hooks hang the session** — always wrap with `timeout 30 ...` or set the hook's `timeout` field.
1. **Shell profile pollution** — `~/.zshrc` that prints a welcome message prepends to hook stdout and breaks JSON parsing. Use `set -euo pipefail` and non-interactive shells.
1. **`chmod +x`** — scripts without execute permission silently no-op.
1. **Windows hangs** — shell-based hooks cause 5+ min hangs on Windows (issue #34457). Use `shell: "powershell"` or HTTP hooks.
1. **Version bump required** — changing plugin code without bumping `version` in `plugin.json` leaves users on stale cache.

______________________________________________________________________

## Cross-Cutting Themes

Patterns that emerge when looking across all subtopics together:

### 1. The `description` field is the single most load-bearing piece of every component type

This appeared in every research stream. For skills and agents, `description` is the only signal Claude uses to decide whether to auto-invoke. Every authoritative source converges on:

- Third person, "Use when..." phrasing
- Front-load the key use case (250 char truncation)
- Include real trigger keywords
- No "I can help you..." first-person
- On Claude 4.5/4.6, avoid aggressive "CRITICAL: MUST ALWAYS" language — it now causes overtriggering

### 2. Progressive disclosure is a universal cost-control pattern

Skills formalize it (metadata → body → bundled files), but the principle applies to agents too (lean body, reference code via paths not inlining) and to orchestration (children write to files, return short summaries). The common shape: **keep what Claude always sees small; push detail to on-demand loads**.

### 3. Context isolation dominates prompt design

Subagents see only the `prompt` string. Skills in a subagent's context are not inherited from the parent. Every boundary crossing needs explicit state passing. Any prompt that references "above", "earlier", "our conversation" is broken.

### 4. File-based result passing is the workaround for every output-size limit

The 32K subagent output cap, the description 250-char truncation, the SKILL.md 500-line ceiling — all of them push architecture toward "write rich output to a file, return a short pointer". The outreach enrichment orchestrator in this repo already uses this pattern correctly.

### 5. Least-privilege tool scoping is consistently the #1 reviewable security lever

Every researcher flagged `tools:` omission as a top anti-pattern. Read-only agents must not list `Write`/`Edit`. Orchestrators must use `Agent(name1, name2)` to allowlist children. Plugin-bundled hooks and MCP servers inherit full user privileges and cannot be sandboxed — scope them tightly at authoring time.

### 6. The plugin system evolves rapidly; primary sources are authoritative

Many community blogs reference pre-v2.1.63 behavior (`Task` tool), pre-unification (`commands/` and `skills/` as separate systems), or early field lists missing `color`/`effort`/`isolation`. Whenever this document and a secondary source disagree, **trust the primary source at `code.claude.com/docs/`**.

______________________________________________________________________

## Review Checklist (Ready-to-Use)

Apply this when auditing any plugin component in this repository.

### Plugin manifest (`plugins/<name>/plugin.json` or `.claude-plugin/plugin.json`)

- [ ] Manifest uses **flat top-level fields**, not a `contents` wrapper. (**This repo currently fails this check for all three plugins.**)
- [ ] `name` is kebab-case, ≤64 chars, does not contain "claude" or "anthropic".
- [ ] `version` is semver. **Confirm it gets bumped on every functional change** — otherwise users won't see updates.
- [ ] Manifest does NOT duplicate what auto-discovery already handles. Don't list every agent file manually when they're in `agents/`.
- [ ] If `commands`/`agents`/`skills` fields are set, confirm they replace (not augment) defaults intentionally.
- [ ] `.claude-plugin/` contains ONLY `plugin.json`. All components (`agents/`, `skills/`, `commands/`, `hooks/`, `.mcp.json`) are at plugin root.

### Marketplace manifest (`.claude-plugin/marketplace.json`)

- [ ] Required fields present: `name`, `owner.name`, `plugins[]`.
- [ ] Plugin `source` pinning: use `ref` for branch/tag, `sha` for exact commit when reproducibility matters.
- [ ] No reserved plugin names (`claude-plugins-official`, `anthropic-marketplace`, etc.).
- [ ] If using relative-path plugins, confirm the marketplace is added via git (not raw URL).

### Skill frontmatter (`skills/<name>/SKILL.md`)

- [ ] `name` lowercase kebab-case ≤64 chars, not containing reserved words.
- [ ] `description` is third-person, front-loads use case, includes "Use when..." or trigger phrases, ≤1024 chars.
- [ ] Description contains real user-phrasing keywords that would match the task.
- [ ] If `disable-model-invocation: true` or `user-invocable: false` — confirm the intent matches behavior.
- [ ] No frontmatter field that exists only in secondary sources (`mode` — not documented).
- [ ] Uses forward slashes in any file path references.

### Skill body (`SKILL.md`)

- [ ] Body is **under 500 lines**.
- [ ] Supporting files are **one level deep** from SKILL.md (no nested refs).
- [ ] Every referenced supporting file actually exists.
- [ ] Reference files over 100 lines have a table of contents at the top.
- [ ] Execution intent for scripts is unambiguous ("Run X to..." vs "See X for...").
- [ ] Bundled scripts handle errors explicitly — no "punt to Claude" patterns.
- [ ] No time-sensitive content in the main body ("as of August 2025...").
- [ ] Consistent terminology throughout.
- [ ] No empty placeholder sections (`## Limitations: N/A`).

### Agent frontmatter (`agents/<name>.md`)

- [ ] `name` and `description` present. Description is specific, includes trigger phrasing when automatic invocation is intended.
- [ ] `tools:` field **explicitly set** (not omitted). Every tool listed is justified by the body.
- [ ] Read-only agents (reviewers, researchers) do **not** include `Write` or `Edit`.
- [ ] `model:` set intentionally based on task complexity — not left to inherit from Opus session by default.
- [ ] **For plugin-shipped agents**: does NOT declare `hooks`, `mcpServers`, or `permissionMode` (silently ignored).
- [ ] Tool names are real: `Read`, `Write`, `Edit`, `Bash`, `Grep`, `Glob`, `WebFetch`, `WebSearch`, `Agent`. Not `FileRead`, `ShellExec`, etc.
- [ ] For main-thread agents that spawn children, uses `Agent(worker1, worker2)` allowlist.

### Agent body

- [ ] Role statement in first line ("You are a senior X...").
- [ ] Body would be executable as a standalone prompt — no references to parent conversation.
- [ ] Includes numbered workflow for multi-step tasks.
- [ ] Explicit output format when the parent needs structured results.
- [ ] Positive instructions dominate — negative "DO NOT" only for genuine safety constraints.
- [ ] Includes at least one concrete example when output format matters.
- [ ] No corporate/AI-generated tone (empty adjectives, press-release voice, filler).

### Orchestrator agents

- [ ] Children write large outputs to files and return pointers, not inline data (avoids 32K cap).
- [ ] Parallel dispatch is explicit in the prompt: "spawn N agents in a single message".
- [ ] `tools: Agent(...)` locks down which children can be spawned.
- [ ] Children are never spawned with `run_in_background: true` if they need to `Write`/`Edit`.
- [ ] Uses appropriate tier: Opus for orchestration, Sonnet/Haiku for workers.

### Hooks (`hooks/hooks.json`)

- [ ] Uses the `{ "description": ..., "hooks": { ... } }` wrapper format (plugin-specific).
- [ ] Every `command` hook script has `timeout` set.
- [ ] `SessionStart`, `PreToolUse`, `UserPromptSubmit`, `Stop` hooks are reviewed most carefully — they're the most privileged.
- [ ] Stop/SubagentStop hooks check `stop_hook_active` to avoid loops.
- [ ] Scripts referenced via `${CLAUDE_PLUGIN_ROOT}`, not hardcoded paths.
- [ ] Any persistence uses `${CLAUDE_PLUGIN_DATA}` (survives updates), not `${CLAUDE_PLUGIN_ROOT}` (wiped on update).
- [ ] Scripts have `chmod +x` before commit.
- [ ] Shell scripts use `set -euo pipefail`.

### Bundled MCP servers (`.mcp.json`)

- [ ] `command` uses `${CLAUDE_PLUGIN_ROOT}` for bundled binaries.
- [ ] npm package versions are **pinned** (`@1.2.3`), not unpinned (`@latest` or no version).
- [ ] Env block does not inadvertently leak secrets.
- [ ] Binary or package is actually audited — it runs with user privileges.

### Security review (for PR authors of new plugins)

- [ ] Hook scripts do not `curl` to external URLs without justification.
- [ ] Hook scripts do not write to `~/.claude/settings*.json`, `~/.gitconfig`, `~/.ssh/`, or shell rc files.
- [ ] No hooks return `{"permissionDecision": "allow"}` to auto-bypass user confirmation.
- [ ] MCP server packages are pinned to specific versions.
- [ ] No reference to `GITHUB_TOKEN` or other secret env vars except in documented auth paths.

______________________________________________________________________

## Anti-Pattern Catalog (Named, Searchable)

| Name                       | Description                                                                                                |
| -------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `CONTENTS_WRAPPER`         | `plugin.json` wraps agents/skills in a non-standard `contents` object. **Currently present in this repo.** |
| `VAGUE_DESCRIPTION`        | Description so broad Claude can't tell when to invoke ("Helps with code").                                 |
| `FIRST_PERSON_DESCRIPTION` | "I can help you..." / "You can use this to..." — degrades discovery.                                       |
| `MISSING_TRIGGER`          | No keywords in description that match user phrasing.                                                       |
| `TOOL_SPRAWL`              | `tools:` omitted, silently inheriting everything including MCP.                                            |
| `OVER_CONSTRAINED_TOOLS`   | Allowlist too narrow to complete stated task.                                                              |
| `BLOATED_SKILL`            | SKILL.md over 500 lines with inline reference material.                                                    |
| `NESTED_REFERENCES`        | SKILL.md → a.md → b.md → content — causes incomplete reads.                                                |
| `ORPHAN_REFERENCE`         | SKILL.md links to files that don't exist.                                                                  |
| `DEAD_CROSS_REF`           | References another skill/agent that was removed.                                                           |
| `TIME_SENSITIVE_BODY`      | Hard-coded dates ("as of August 2025...") that rot silently.                                               |
| `WINDOWS_PATHS`            | Backslashes break on Unix hosts.                                                                           |
| `DEAD_FRONTMATTER`         | Plugin agent declares `hooks`/`mcpServers`/`permissionMode` — silently ignored.                            |
| `HALLUCINATED_TOOL`        | Frontmatter lists nonexistent tool names (`FileRead`, `ShellExec`).                                        |
| `INHERIT_BY_DEFAULT`       | Every subagent runs on session-default Opus, silently multiplying cost.                                    |
| `CORPORATE_TONE`           | AI-generated bodies with press-release voice and filler.                                                   |
| `EMPTY_SECTIONS`           | Boilerplate `## Limitations: N/A` / `## Prerequisites: See above`.                                         |
| `AGGRESSIVE_TRIGGER_LANG`  | "CRITICAL: MUST ALWAYS" — causes overtriggering on Claude 4.5/4.6.                                         |
| `CONTEXT_PARENT_REF`       | Body references parent conversation; subagents don't see it.                                               |
| `BACKGROUND_WRITER`        | Background agent with `Write`/`Edit` tools — silently fails.                                               |
| `OUTPUT_OVER_32K`          | Subagent returns large result inline instead of writing to file.                                           |
| `NO_NESTING_VIOLATION`     | Architecture assumes subagents can spawn subagents — they cannot.                                          |
| `STOP_HOOK_LOOP`           | Stop hook that always blocks without checking `stop_hook_active`.                                          |
| `UNPINNED_MCP_NPX`         | MCP server uses `npx @package` without version pin — supply chain risk.                                    |
| `HARDCODED_CACHE_PATH`     | Hook/MCP references absolute paths instead of `${CLAUDE_PLUGIN_ROOT}`.                                     |
| `VERSION_NOT_BUMPED`       | Plugin code changes without `version` bump — users stuck on cache.                                         |
| `PUNT_TO_CLAUDE`           | Scripts that fail and expect Claude to fix them at runtime.                                                |
| `NESTED_COMPONENTS`        | Putting `agents/` or `skills/` inside `.claude-plugin/` instead of plugin root.                            |

______________________________________________________________________

## Risks, Uncertainties & Research Gaps

### What is authoritative

- Every field in the frontmatter tables (Sections C.1, D.1, F.2) comes from `code.claude.com/docs/`.
- Token cost figures (15× for multi-agent, 90.2% quality lift) come from Anthropic's own research system post-mortem and are the only controlled numbers.
- CLI command reference (Section B.1) is cross-verified against `discover-plugins` and `plugin-marketplaces` docs.

### What is convention, not rule

- **Four-tier model strategy** (Opus/Inherit/Sonnet/Haiku split) is wshobson's convention, widely adopted but not Anthropic guidance.
- **Agent body structure** (role → when invoked → principles → process → output) is community consensus; no official style guide.
- **"Keep bodies under 300 lines"** for agents is practical wisdom, not a documented limit.

### Where sources disagree

- Some secondary sources describe skills and slash commands as separate systems — they're now unified. Trust the docs.
- Some community docs use non-canonical field names (`agent-type`, `when-to-use`, `allowed-tools` on dev.to). Canonical names are `name`, `description`, `tools`.
- `effort` vs `effortLevel` — the frontmatter field is `effort`; `effortLevel` is a session-level setting. Different contexts.

### Open gaps

1. **No published hard concurrency limit** for parallel subagent dispatch. Community reports 5-24 in practice. Feature request closed NOT_PLANNED.
1. **No deterministic ordering** between hooks from different plugins for the same event. Treat any "deny" from one plugin as advisory, not enforcing.
1. **No official eval harness** for plugins. Community tools (PluginEval, SkillCheck) exist but none are Anthropic-blessed.
1. **No plugin signing, no integrity verification, no download-only review mode** (issues #29729, #28879 both open).
1. **Trigger reliability is a black box.** Automatic delegation is an LLM decision, not a classifier; descriptions sometimes fail to fire for reasons that can only be fixed by iterating wording.
1. **Rollback path after a broken auto-update is undocumented.** Closest workaround is `CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE=1`, which only protects against fetch failure.
1. **`contents` wrapper tolerance** — we don't know if/when the CLI will start rejecting unknown top-level fields. The local repo's manifests work today but are on borrowed time.
1. **Windows command-line 8191-char limit** affects agents defined via `--agents` JSON but not filesystem-defined agents. Not formally documented.

### Research process caveats

- One of the six researcher agents (plugin architecture & distribution) hung silently for 2.5+ hours after a WebFetch call and had to be killed and replaced with a tighter scope focused on distribution/publishing CLI mechanics. Core manifest and layout material was recovered from the other 5 reports, so this is marked as covered.
- Four of the six researchers flagged a "prompt injection attempt" in their search results — this was actually a legitimate `<system-reminder>` from this session's environment (Crypto.com MCP server instructions), not an attacker payload. They correctly ignored it regardless.

______________________________________________________________________

## Canonical Examples

Reference these when writing new plugins. All are linked and should be consulted, not copied blindly.

### Skills

- **Anthropic's `skill-creator`** ([anthropics/skills/skill-creator/SKILL.md](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md)) — the meta-skill for creating skills. Canonical authoring norms.
- **Anthropic's document skills** (`pdf`, `docx`, `pptx`, `xlsx`) — production-grade progressive disclosure with `FORMS.md`, `REFERENCE.md`, `EXAMPLES.md` splits.
- **Anthropic's official code-review plugin** ([anthropics/claude-code/plugins/code-review](https://github.com/anthropics/claude-code/blob/main/plugins/code-review/commands/code-review.md)) — strict tool allowlist, model tiering per step (Haiku→Sonnet→Opus), explicit DO FLAG / DO NOT FLAG lists, false-positives-erode-trust principle.

### Agents

- **Anthropic's `code-reviewer` docs example** — minimal, read-only tools, numbered workflow, structured output (critical/warnings/suggestions).
- **wshobson/agents** ([github.com/wshobson/agents](https://github.com/wshobson/agents)) — 135+ production agents with four-tier model strategy.
- **VoltAgent/awesome-claude-code-subagents** ([github.com/VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents)) — 100+ agents organized by 10 domains with narrow specialization.
- **Local `plugins/mz-biz-outreach/agents/outreach-enrichment-orchestrator.md`** — canonical local example of the map pattern with `Agent(...)` spawn allowlist and file-based result passing.

### Multi-agent patterns

- **Anthropic multi-agent research system** ([anthropic.com/engineering/multi-agent-research-system](https://www.anthropic.com/engineering/multi-agent-research-system)) — the authoritative reference for 15× token cost, 90.2% quality lift, orchestrator-workers pattern.
- **Anthropic cookbook orchestrator-workers** ([platform.claude.com/cookbook/patterns-agents-orchestrator-workers](https://platform.claude.com/cookbook/patterns-agents-orchestrator-workers)) — `FlexibleOrchestrator` implementation reference.

______________________________________________________________________

## Methodology

- **Topic decomposition**: six independent subtopics — plugin distribution, skill authoring, agent authoring, multi-agent orchestration, hooks/commands/MCP, best practices & review criteria.
- **Researcher agents**: 6 parallel dispatches (1 replaced after a silent hang). Each agent targeted 20-50 web pages across primary and secondary sources, used 5+ distinct search queries, cross-referenced claims across 2+ sources.
- **Primary source bias**: `code.claude.com/docs/`, `platform.claude.com/docs/`, `github.com/anthropics/claude-code`, Anthropic engineering blog.
- **Secondary sources**: Simon Willison, wshobson/agents, VoltAgent, community blogs, security researchers (PromptArmor, SentinelOne).
- **Verification**: every frontmatter field, CLI command, path, and token limit in this document is cited to at least one primary source in the individual researcher reports. Cross-cutting themes are drawn from convergence across multiple reports.
- **Local repo cross-reference**: multiple researchers inspected files in `/home/drmozg/Work/Petproj/claude-mozg-pipelines/` to flag concrete issues (most notably the `contents` wrapper in all three `plugin.json` files).

______________________________________________________________________

## Primary Sources (Deduplicated)

### Anthropic documentation

- [Create custom subagents](https://code.claude.com/docs/en/sub-agents)
- [Create plugins](https://code.claude.com/docs/en/plugins)
- [Plugins reference](https://code.claude.com/docs/en/plugins-reference)
- [Create and distribute a plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces)
- [Discover plugins](https://code.claude.com/docs/en/discover-plugins)
- [Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [Claude Code settings](https://code.claude.com/docs/en/settings)
- [Hooks reference](https://code.claude.com/docs/en/hooks)
- [Model configuration](https://code.claude.com/docs/en/model-config)
- [Agent teams (experimental)](https://code.claude.com/docs/en/agent-teams)
- [Connect Claude Code to tools via MCP](https://code.claude.com/docs/en/mcp)
- [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Agent Skills quickstart](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/quickstart)
- [Subagents in the SDK](https://platform.claude.com/docs/en/agent-sdk/subagents)
- [Plugins in the SDK](https://platform.claude.com/docs/en/agent-sdk/plugins)
- [Prompting best practices (Claude 4)](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-4-best-practices)
- [Orchestrator-workers cookbook pattern](https://platform.claude.com/cookbook/patterns-agents-orchestrator-workers)

### Anthropic engineering

- [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Building effective agents](https://www.anthropic.com/research/building-effective-agents)
- [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [Equipping agents for the real world with Agent Skills](https://claude.com/blog/equipping-agents-for-the-real-world-with-agent-skills)
- [Customize Claude Code with plugins (launch blog)](https://claude.com/blog/claude-code-plugins)

### Anthropic GitHub

- [anthropics/skills](https://github.com/anthropics/skills) — canonical public skills repo
- [anthropics/claude-code plugins directory](https://github.com/anthropics/claude-code/tree/main/plugins) — plugin-dev, code-review, security-guidance, hookify
- [anthropics/claude-code/plugins/plugin-dev/skills/hook-development/SKILL.md](https://github.com/anthropics/claude-code/blob/main/plugins/plugin-dev/skills/hook-development/SKILL.md) — hook authoring reference
- [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official)

### Security research (April 2026)

- [PromptArmor — Hijacking Claude Code via Injected Marketplace Plugins](https://www.promptarmor.com/resources/hijacking-claude-code-via-injected-marketplace-plugins)
- [SentinelOne — Marketplace Skills and Dependency Hijack in Claude Code](https://www.sentinelone.com/blog/marketplace-skills-and-dependency-hijack-in-claude-code/)

### High-signal community repositories

- [wshobson/agents](https://github.com/wshobson/agents) — 135+ production agents, four-tier model strategy
- [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) — 100+ subagents by domain
- [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)
- [rohitg00/awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit) — PluginEval framework
- [hesreallyhim/claude-code-json-schema](https://github.com/hesreallyhim/claude-code-json-schema) — unofficial JSON schemas
- [simonw/claude-skills](https://github.com/simonw/claude-skills)

### Key GitHub issues

- [#25569 — subagent 32K output cap](https://github.com/anthropics/claude-code/issues/25569)
- [#40751 — background agents silently fail on writes](https://github.com/anthropics/claude-code/issues/40751)
- [#15487 — maxParallelAgents feature request (NOT_PLANNED)](https://github.com/anthropics/claude-code/issues/15487)
- [#29677 — Task → Agent rename](https://github.com/anthropics/claude-code/issues/29677)
- [#29729 — plugin signing feature request (open)](https://github.com/anthropics/claude-code/issues/29729)
- [#28879 — download-only install mode (open)](https://github.com/anthropics/claude-code/issues/28879)
- [#18837 — skill `allowed-tools` not always enforced](https://github.com/anthropics/claude-code/issues/18837)
- [#34457 — Windows hook hangs 5+ min](https://github.com/anthropics/claude-code/issues/34457)

### High-signal secondary

- [Simon Willison — Claude Skills tag](https://simonwillison.net/tags/skills/)
- [Mikhail Shilkov — Inside Claude Code Skills](https://mikhail.io/2025/10/claude-code-skills/)
- [Lee Hanchung — Claude Agent Skills First Principles Deep Dive](https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/)
- [PubNub — Best practices for Claude Code sub-agents](https://www.pubnub.com/blog/best-practices-for-claude-code-sub-agents/)
- [Steve Kinney — Sub-agent anti-patterns](https://stevekinney.com/courses/ai-development/subagent-anti-patterns)
- [claudefa.st — Sub-agent best practices](https://claudefa.st/blog/guide/agents/sub-agent-best-practices)
- [Daniel Miessler — When to use Skills vs Commands vs Agents](https://danielmiessler.com/blog/when-to-use-skills-vs-commands-vs-agents)
