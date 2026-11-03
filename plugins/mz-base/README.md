<p align="center"><img src="../../assets/hero/mz-base.webp" alt="mz-base: everyday dev foundations" width="100%"></p>

# mz-base

Foundation plugin for Claude Code — standalone agents and utility skills for everyday development workflows. The `/init-rules` rule installer lives in the separate mz-rules plugin.

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-base
```

## Skills

### `/construct-skill` — Skill Authoring Helper

Drafts a new skill for a plugin in this marketplace repo, following its skill guidelines. Walks you through the description, anatomy, state, approval gates and the pre-publish checklist in a RED/GREEN/REFACTOR loop. It doesn't write `.claude/skills` skills or review existing ones.

### `/using-mozg-pipelines` — Routing Map

Maps natural-language task phrases to the right skill across all `mz-*` plugins. Invoked when the user asks "which skill fits", "route this", or "what plugins do I have".

## Agents

Agents are specialized workers. `code-reviewer`, `technical-writer` and `pipeline-web-researcher` can be invoked directly. `pipeline-web-researcher`, `pipeline-researcher` and `code-lens-over-engineering` live here because skills in several plugins dispatch them.

| Agent                          | Purpose                                                                                                                                                |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **code-reviewer**              | Reviews code changes for bugs, security vulnerabilities, performance issues, and maintainability                                                       |
| **technical-writer**           | Creates and improves technical documentation grounded in actual code                                                                                   |
| **pipeline-researcher**        | Pipeline-only. Codebase exploration and domain research for the planning and review pipelines                                                          |
| **pipeline-web-researcher**    | Sourced web research on a technical question, such as a version change or a tool comparison; also shared by the research, review and docs pipelines    |
| **code-lens-over-engineering** | Pipeline-only. Flags code that should not exist or should be smaller; dispatched by branch-reviewer and the build, polish, cleanup and optimize skills |

For local branch review (`/review-branch`) and GitHub PR workflows (`/github-review-pr`, `/github-scan-prs`) plus their lens agents and PR collectors, see [`mz-dev-git`](../mz-dev-git/).

## License

MIT
