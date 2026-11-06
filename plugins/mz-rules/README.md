# mz-rules

Curated coding rules for Claude Code, installed per project or for every session by one skill, `/init-rules`. It detects the project's languages and tooling, shows one plan, and writes no rules or settings until you approve it.

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-rules
```

Until 0.54.0, `/init-rules` shipped inside mz-base. Install mz-rules to keep it. Rules installed by the old version carry the same version markers, so the next run upgrades or skips them as usual.

## Skills

### `/init-rules` — Rule Installer

Detects project languages and installs relevant coding rules. Two delivery modes: rule files in `.claude/rules/` (default) or sentinel-wrapped blocks injected directly into `CLAUDE.md`. Every run shows one plan and writes nothing until you approve it.

```
/init-rules                               # project scope, rule files, auto-detect
/init-rules global                        # user scope, rule files
/init-rules project --force               # overwrite existing rule files
/init-rules project --target=claudemd     # inject into ./CLAUDE.md (asks for approval)
/init-rules global --target=claudemd      # inject into ~/.claude/CLAUDE.md
/init-rules --uninstall                   # remove rules previously installed by this skill
```

`--target=claudemd` wraps each rule in a `<!-- mz-rule:<id> v=<version> ... -->` sentinel block, and rule files get a one-line version marker. Re-runs are idempotent and `--uninstall` removes only what the skill wrote. `--force` replaces existing rules, including unmarked files from older installs.

Besides the rules, the plan can include:

- **Personal preference groups**, opt-in from a multi-select: Code style extras, Git + C++ style, Review rituals.
- **Delegation rules**, opt-in and offered when mz-base is enabled: send sourced web research to `pipeline-web-researcher`, wide read-only searches to `Explore` and docs writing to `technical-writer`. When mz-creative is enabled, a second file runs `/naturalize` on the docs afterwards.
- **Enforced settings**: ask before `git push`, deny reading `.env` files, a pre-commit Stop hook when the project uses pre-commit, and commit/PR attribution off. They go into `.claude/settings.local.json` (project) or `~/.claude/settings.json` (global), and entries you already have stay as they are.
- **Stale cleanup**: retired rules are removed, installs from older versions are upgraded, and hand-written `CLAUDE.md` copies of retired or rewritten sections are offered for deletion, each shown verbatim first.
- **AGENTS.md guard**: in a project that relies on `AGENTS.md`, the skill asks before creating a `CLAUDE.md` that would stop it from loading.

## Rules

Each rule is a focused guideline installed as a `.md` file in your rules directory or as a block in `CLAUDE.md`.

| Rule                         | Installed                 | Focus                                                                                      |
| ---------------------------- | ------------------------- | ------------------------------------------------------------------------------------------ |
| **code-quality**             | always                    | Real checks before finishing, YAGNI, clean up what your change orphaned, rule of three     |
| **coding-standards**         | always                    | Error handling, WHY comments, behavior-focused tests, loosely coupled modules              |
| **edit-safety**              | always                    | Grep is not symbol search, one source of truth, ask before destructive git actions         |
| **context-safety**           | always                    | Re-reading after compaction, partial reads, truncated output, when subagents pay off       |
| **self-evaluation**          | always                    | Evidence in reports, test integrity, scope trace, fresh-eyes review, right-sized write-ups |
| **agent-workflow**           | always                    | Ask only when readings diverge, milestones capped at 10 files / 400 lines, finish the task |
| **housekeeping**             | always                    | Mention pre-existing issues instead of fixing them unasked                                 |
| **safety**                   | always                    | Fetched content is data, no secrets in output or commits, ask before new dependencies      |
| **git-conventions**          | git repo                  | Commit only when asked, stage files by name                                                |
| **pre-commit-conventions**   | `.pre-commit-config.yaml` | Run tools through `pre-commit run --files`                                                 |
| **python-conventions**       | Python                    | Shared pytest fixtures                                                                     |
| **strict-typing-python**     | Python                    | Type hints, TypedDict or Pydantic, Protocol                                                |
| **strict-typing-typescript** | TypeScript                | TypeScript strict types, no any, exhaustive unions                                         |
| **personal-code-style**      | opt-in                    | Logs at decision points, short comments, params objects, validated public input            |
| **personal-git**             | opt-in, git repo          | Six-word commit messages, no AI attribution                                                |
| **personal-cpp**             | opt-in, C++               | `auto` where possible                                                                      |
| **personal-review**          | opt-in                    | Two-perspective review of real tradeoffs, short bug autopsy                                |
| **delegation**               | opt-in, mz-base           | Which specialised agent gets web research, wide searches and docs writing                  |
| **delegation-naturalize**    | opt-in, mz-creative       | `/naturalize` on prose docs after `technical-writer` changes them                          |

## Data and network

Nothing is sent to the author. The plugin has no telemetry, hooks, MCP servers or network calls. `/init-rules` runs inside your Claude Code session, so files it reads go to the model under your own account ([PRIVACY.md](https://github.com/DoctorMozg/claude-pipelines/blob/master/PRIVACY.md)).

**Reads.** Project manifests and file extensions, the target `CLAUDE.md`, your settings files (for `enabledPlugins`) and the rules bundled in the plugin.

**Writes.** The only write before you approve is run state under `.mz/task/<task_name>/`. The rest waits for one Approve gate, and Reject writes nothing more. Global paths sit under `CLAUDE_CONFIG_DIR` instead of `~/.claude/` when that variable is set:

- Rule files in `.claude/rules/` (project) or `~/.claude/rules/` (global), or marked blocks in `./CLAUDE.md` or `~/.claude/CLAUDE.md`.
- Settings entries in `.claude/settings.local.json` (project) or `~/.claude/settings.json` (global), merged with your existing ones. One is a Stop hook that runs your own `pre-commit`. It lives in your settings, not in the plugin.
- `.mz/` and `.claude/settings.local.json` appended to `.git/info/exclude` in a git project.
- Hand-written `CLAUDE.md` sections that duplicate retired rules, deleted after you see each one verbatim.

**Undo.** `/init-rules --uninstall` with the same scope and target removes the marked rules and the exact settings entries it added. It leaves `CLAUDE.md`, the settings file, the exclude lines and `.mz/` in place. It makes no backups, so use git to revert `--force` overwrites or removed sections.

## License

MIT
