# mozg-pipelines

Multi-agent plugins for [Claude Code](https://claude.com/claude-code). Autonomous development pipelines, code review, deep research, and business intelligence — all as slash commands.

## Quick Start

```bash
# Add the marketplace
claude plugin marketplace add DoctorMozg/claude-pipelines

# Install the plugins you need
claude plugin install mz-dev-base       # Standalone agents + rules
claude plugin install mz-dev-pipe       # Autonomous dev pipelines
claude plugin install mz-dev-hooks      # Safety gates + workflow hooks
claude plugin install mz-memory         # Cross-session project memory
claude plugin install mz-biz-outreach   # Business lead generation
```

After installation, skills are available as slash commands:

```
/build implement OAuth2 PKCE flow for the auth module
/audit scope:branch security
/debug "KeyError: 'user_id' in process_payment"
/review-branch
/lead-gen find AI startups in Berlin for consulting partnerships
```

## Plugins

### [`mz-dev-base`](plugins/mz-dev-base/) — Foundation

Standalone agents and skills for everyday development. No pipeline orchestration — each tool works independently.

| Skill             | Command                         | What it does                                                        |
| ----------------- | ------------------------------- | ------------------------------------------------------------------- |
| **review-branch** | `/review-branch`                | Reviews all changes on the current branch against main              |
| **review-pr**     | `/review-pr <URL>`              | Deep-reviews a GitHub PR for bugs and architecture issues           |
| **scan-prs**      | `/scan-prs [repos]`             | Scans repos for PRs needing your attention, produces a daily report |
| **deep-research** | `/deep-research <topic>`        | Multi-agent web research with parallel domain experts               |
| **init-rules**    | `/init-rules [project\|global]` | Installs curated coding rules based on detected languages           |

6 agents (code-reviewer, branch-reviewer, pr-reviewer, pr-scanner, researcher, technical-writer) and 11 coding rules.

**[Full documentation →](plugins/mz-dev-base/)**

______________________________________________________________________

### [`mz-dev-pipe`](plugins/mz-dev-pipe/) — Autonomous Dev Pipelines

Multi-agent orchestration skills that run full development workflows. Each skill coordinates specialized agents through phased pipelines with user approval gates.

| Skill            | Command                     | What it does                                                                                               |
| ---------------- | --------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **build**        | `/build <task>`             | Research → plan → code → review → test                                                                     |
| **audit**        | `/audit [focus]`            | Multi-lens codebase scan (correctness, security, performance, maintainability, reliability) → ranked fixes |
| **debug**        | `/debug <bug report>`       | Reproduce → diagnose → regression test (TDD) → fix → verify                                                |
| **investigate**  | `/investigate <hypothesis>` | Code analysis → domain research → exploratory tests → verdict                                              |
| **verify**       | `/verify [scope]`           | Tests + linters + type checks + coverage analysis + failure diagnosis                                      |
| **polish**       | `/polish <criteria>`        | Iterative fix-test-review loop until criteria are met                                                      |
| **optimize**     | `/optimize <scope>`         | Import-graph chunking → parallel optimization → mirrored review                                            |
| **blast-radius** | `/blast-radius <target>`    | Maps the change graph: what breaks if you touch X                                                          |
| **explain**      | `/explain <scope>`          | Multi-angle research → comprehensive report with Mermaid diagrams                                          |
| **combine**      | `/combine <task>`           | Local-first synthesis: harvests `.mz/research/`, `.mz/task/`, `.mz/reports/`, git → task-adaptive report   |

11 specialized agents (researcher, web-researcher, planner, plan-reviewer, coder, code-reviewer, test-writer, test-coverage-reviewer, test-quality-reviewer, optimizer, completeness-checker).

All pipeline skills support `scope:branch|global|working` to constrain which files agents may edit.

**[Full documentation →](plugins/mz-dev-pipe/)**

______________________________________________________________________

### [`mz-biz-outreach`](plugins/mz-biz-outreach/) — Business Intelligence

Autonomous lead generation pipeline that discovers companies, scans reputations, enriches with contacts and intelligence, scores leads, and produces executive reports.

| Skill        | Command            | What it does                                                        |
| ------------ | ------------------ | ------------------------------------------------------------------- |
| **lead-gen** | `/lead-gen <goal>` | Strategy → source research → scout → scan → enrich → score → report |

11 specialized agents covering strategy, source research, company discovery, reputation scanning, contact finding, news monitoring, growth analysis, tech stack analysis, enrichment orchestration, card writing, and reporting.

**[Full documentation →](plugins/mz-biz-outreach/)**

______________________________________________________________________

### [`mz-creative`](plugins/mz-creative/) — Creative Brainstorming

Multi-personality brainstorming with 10 AI thinkers (engineer, artist, philosopher, mathematician, scientist, economist, storyteller, futurist, psychologist, historian). A curated panel of 5 generates ideas from diverse lenses, a synthesizer merges them, and the panel votes iteratively until consensus.

| Skill          | Command               | What it does                                                    |
| -------------- | --------------------- | --------------------------------------------------------------- |
| **brainstorm** | `/brainstorm <topic>` | Panel selection → parallel ideation → synthesis → voting rounds |

10 personality agents available as standalone creative consultants.

**[Full documentation →](plugins/mz-creative/)**

______________________________________________________________________

### [`mz-memory`](plugins/mz-memory/) — Project Memory

Cross-session project memory that persists knowledge automatically. SessionStart injects, SessionEnd captures completed tasks, PostCompact re-injects after compaction.

| Hook                | Event        | What it does                                           |
| ------------------- | ------------ | ------------------------------------------------------ |
| **Memory inject**   | SessionStart | Loads `.mz/memory/MEMORY.md` into context              |
| **Memory capture**  | SessionEnd   | Captures completed task summaries, prunes to 200 lines |
| **Memory reinject** | PostCompact  | Re-injects memory after context compaction             |

Pairs with `mz-dev-pipe` agents that have native `memory: project` for per-agent persistent memory.

**[Full documentation →](plugins/mz-memory/)**

______________________________________________________________________

### [`mz-dev-hooks`](plugins/mz-dev-hooks/) — Development Workflow Hooks

Deterministic safety gates. Shell scripts block dangerous actions at zero token cost.

| Hook                    | Event      | Type    | Behavior                                               |
| ----------------------- | ---------- | ------- | ------------------------------------------------------ |
| Dangerous command guard | PreToolUse | command | **Blocks** rm -rf /, force push main, DROP TABLE, etc. |
| Secret scanner          | PreToolUse | command | **Blocks** API keys, tokens, private keys in code      |
| File safety guard       | PreToolUse | command | **Blocks** edits to lock files, .env, vendor dirs      |
| Commit quality          | PreToolUse | command | **Warns** on non-conventional commit messages          |

No configuration required — hooks activate automatically on install.

**[Full documentation →](plugins/mz-dev-hooks/)**

## How It Works

Each plugin provides **agents** (specialized worker processes) and **skills** (orchestrator prompts that coordinate agents through multi-phase pipelines).

```
User runs /build "add rate limiting to the API"
  │
  ├─ Phase 1: Researcher agent explores codebase
  ├─ Phase 2: Planner agent creates implementation plan
  │    └─ Plan reviewer validates the plan
  ├─ Phase 3: User approves the plan
  ├─ Phase 4: Coder agents implement in parallel (1-8 workers)
  │    └─ Code reviewers validate each chunk
  ├─ Phase 5: Test writer adds tests
  │    └─ Coverage + quality reviewers validate tests
  ├─ Phase 6: Completeness checker verifies everything
  └─ Final: Summary report
```

Pipelines are designed around:

- **Parallel fan-out**: independent work units run simultaneously across multiple agents
- **User approval gates**: no code changes without your sign-off on the plan
- **Iterative convergence**: fix → verify → review loops with bounded retries
- **Progressive disclosure**: orchestrators load phase files on-demand to minimize token cost

## Contributing

See [CLAUDE.md](CLAUDE.md) for repository structure and conventions.

## Credits

Some rules in `mz-dev-base` were inspired by [iamfakeguru/claude-md](https://github.com/iamfakeguru/claude-md).

## License

MIT
