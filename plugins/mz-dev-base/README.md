# mz-dev-base

Foundation plugin for Claude Code — standalone agents, coding rules, and utility skills for everyday development workflows.

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-dev-base
```

## Skills

### `/init-rules` — Rule Installer

Detects project languages and installs relevant coding rules. Two delivery modes: rule files in `.claude/rules/` (default) or sentinel-wrapped blocks injected directly into `CLAUDE.md`. Rules cover code quality, typing, git conventions, edit safety, and language-specific patterns.

```
/init-rules                               # project scope, rule files, auto-detect
/init-rules global                        # user scope, rule files
/init-rules project --force               # overwrite existing rule files
/init-rules project --target=claudemd     # inject into ./CLAUDE.md (asks for approval)
/init-rules global --target=claudemd      # inject into ~/.claude/CLAUDE.md
/init-rules --uninstall                   # remove rules previously installed by this skill
```

`--target=claudemd` wraps each rule in a `<!-- mz-rule:<id> ... -->` sentinel block so re-runs are idempotent and `--uninstall` can remove them cleanly. `--force` replaces existing blocks in place.

### `/construct-skill` — Skill Authoring Helper

Helps draft new skills following the conventions in `guidelines/SKILL_GUIDELINES.md`. Walks you through frontmatter, dispatch prompts, approval gates, and progressive disclosure via a TDD-style RED/GREEN/REFACTOR loop.

### `/using-mozg-pipelines` — Routing Map

Loaded into every session via SessionStart hook. Maps natural-language task phrases to the right skill across all `mz-*` plugins. Invoked when the user asks "which skill fits", "route this", or "what plugins do I have".

## Agents

Agents are specialized workers that can be invoked directly or used by skills.

| Agent                | Purpose                                                                                          |
| -------------------- | ------------------------------------------------------------------------------------------------ |
| **code-reviewer**    | Reviews code changes for bugs, security vulnerabilities, performance issues, and maintainability |
| **technical-writer** | Creates and improves technical documentation grounded in actual code                             |

For local branch review (`/review-branch`) and GitHub PR workflows (`/github-review-pr`, `/github-scan-prs`) plus their lens agents and PR collectors, see [`mz-dev-git`](../mz-dev-git/).

## Rules

Available via `/init-rules`. Each rule is a focused guideline installed as a `.md` file in your rules directory.

| Rule                         | Focus                                                   |
| ---------------------------- | ------------------------------------------------------- |
| **code-quality**             | Clean code principles, meaningful naming, function size |
| **coding-standards**         | Project-level conventions and consistency               |
| **strict-typing-python**     | Python type hints, TypedDict, Protocol usage            |
| **strict-typing-typescript** | TypeScript strict types, no any, exhaustive unions      |
| **python-conventions**       | Python-specific patterns, pytest fixtures, Pydantic     |
| **edit-safety**              | Re-read before edit, verify after, no stale context     |
| **context-safety**           | Context decay awareness, file read budgets              |
| **self-evaluation**          | Verify before reporting, two-perspective review         |
| **agent-workflow**           | Sub-agent swarming, phased execution                    |
| **git-conventions**          | Commit messages, branch hygiene                         |
| **housekeeping**             | File hygiene, checkpoint suggestions                    |
| **pre-commit-conventions**   | Pre-commit hook patterns                                |

## License

MIT
