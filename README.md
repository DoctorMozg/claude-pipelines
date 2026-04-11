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
claude plugin install mz-design         # UI/UX design documents
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

| Skill            | Command                     | What it does                                                                                                                              |
| ---------------- | --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **build**        | `/build <task>`             | Research → plan → code → review → test                                                                                                    |
| **audit**        | `/audit [focus]`            | Multi-lens codebase scan (correctness, security, performance, maintainability, reliability) → ranked fixes                                |
| **debug**        | `/debug <bug report>`       | Reproduce → diagnose → regression test (TDD) → fix → verify                                                                               |
| **investigate**  | `/investigate <hypothesis>` | Code analysis → domain research → exploratory tests → verdict                                                                             |
| **verify**       | `/verify [scope]`           | Tests + linters + type checks + coverage analysis + failure diagnosis                                                                     |
| **polish**       | `/polish <criteria>`        | Iterative fix-test-review loop until criteria are met                                                                                     |
| **optimize**     | `/optimize <scope>`         | Import-graph chunking → parallel optimization → mirrored review                                                                           |
| **blast-radius** | `/blast-radius <target>`    | Maps the change graph: what breaks if you touch X                                                                                         |
| **explain**      | `/explain <scope>`          | Multi-angle research → comprehensive report with Mermaid diagrams                                                                         |
| **combine**      | `/combine <task>`           | Local-first synthesis: harvests `.mz/research/`, `.mz/task/`, `.mz/reports/`, git → task-adaptive report                                  |
| **translate**    | `/translate <request>`      | NL request → discovery → glossary seed → plan → parallel translation → tiered verification (structural + judge + uncertainty-driven deep) |

12 specialized agents (researcher, web-researcher, planner, plan-reviewer, coder, code-reviewer, test-writer, test-coverage-reviewer, test-quality-reviewer, optimizer, completeness-checker, translator).

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

### [`mz-creative`](plugins/mz-creative/) — Multi-Perspective Panels

Two panel-driven skills sharing a unified roster of **16 lens agents** (engineer, artist, philosopher, mathematician, scientist, economist, storyteller, futurist, psychologist, historian, cto, data, devops, product, security, seo). Each lens is a fixed intellectual personality; per-dispatch behavior (ideation vs. critique) is injected by the calling skill. **Brainstorm** picks 5 lenses and runs them through a vote-to-consensus ideation loop. **Expert** picks 5 lenses and runs a Delphi-style 3-round critique with inter-round synthesis and a final written report.

| Skill          | Command               | What it does                                                                  |
| -------------- | --------------------- | ----------------------------------------------------------------------------- |
| **brainstorm** | `/brainstorm <topic>` | Panel selection → parallel ideation → synthesis → voting rounds               |
| **expert**     | `/expert <idea>`      | Panel selection → 3 rounds (view → summary → react) → dedicated report writer |

19 agents total: 16 lens personas (shared between brainstorm and expert) plus 3 support agents (researcher, round-synthesizer, report-writer).

**[Full documentation →](plugins/mz-creative/)**

______________________________________________________________________

### [`mz-funny`](plugins/mz-funny/) — Character-Voice Code Roasting

Evidence-anchored code roasting in 7 character voices. Each persona is a first-class agent that can only embellish real findings from a static-analysis-plus-docs-plus-web-research dossier — no fabrication. Pick a voice, point at a file or a branch, get roasted.

| Skill        | Command                        | What it does                                                                            |
| ------------ | ------------------------------ | --------------------------------------------------------------------------------------- |
| **do-roast** | `/do-roast <persona> <target>` | Resolve target → analyze → dossier → persona dispatch → roast report with inline teaser |

7 persona agents (roast-caveman, roast-wh40k-ork, roast-pirate, roast-viking, roast-dwarf, roast-drill-sergeant, roast-yoda) — each standalone-invocable as a creative consultant.

**[Full documentation →](plugins/mz-funny/)**

______________________________________________________________________

### [`mz-design`](plugins/mz-design/) — UI/UX Design Documents

Iterative design-specification skill that drafts a UI/UX document then refines it through four parallel specialist critics (visual layout, UX flows, color/typography, accessibility) with a WCAG 2.2 AA hard gate. Up to 5 critique iterations until all critics approve and zero contrast violations remain.

| Skill               | Command            | What it does                                                                    |
| ------------------- | ------------------ | ------------------------------------------------------------------------------- |
| **design-document** | `/design-document` | Intake → research → draft → 4-critic loop → WCAG-gated approval → final summary |

8 specialized agents (researcher, document-writer, revision-writer, critique-synthesizer, ui-designer, ux-designer, art-designer, accessibility-specialist) and 3 lazy-loaded reference files (Nielsen heuristics, WCAG thresholds, canonical spec template).

**[Full documentation →](plugins/mz-design/)**

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
