# mz-dev-pipe

Autonomous multi-agent development pipelines for Claude Code. Each skill orchestrates specialized agents through phased workflows — research, plan, implement, review, test — with user approval gates and iterative convergence.

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-dev-pipe
```

## Skills

### `/build` — Full Development Pipeline

End-to-end autonomous development: researches the codebase, creates a parallelizable plan, dispatches coder agents, runs code review, writes tests, and checks completeness.

```
/build implement OAuth2 PKCE flow for the auth module
/build add rate limiting middleware with Redis backing
```

**Pipeline**: Research → Plan → Plan Review → User Approval → Parallel Implementation → Code Review → Tests → Test Review → Completeness Check

______________________________________________________________________

### `/audit` — Multi-Lens Codebase Audit

Scans code through 5 independent lenses — correctness, security, performance, maintainability, reliability — then ranks findings by severity, gets your approval, and dispatches parallel coders to fix them. Critical and high-severity fixes get regression tests.

```
/audit                                    # full roam — scan everything
/audit security review                    # single lens
/audit src/auth/                          # narrow scope, all lenses
/audit scope:branch concurrency bugs      # branch files, specific lens
```

**Pipeline**: Scope → 1-5 Parallel Researchers → Consolidate & Rank → User Approval → Parallel Fix → Verify → Review → Regression Tests

**Severity caps**: all critical, top 10 high, top 5 medium. Low findings are reported but not fixed.

______________________________________________________________________

### `/debug` — Reactive Bug Investigation

Given a bug report (error message, stack trace, failing test, or description), reproduces the bug, diagnoses root cause with optional domain research for external dependencies, writes a regression test before the fix (TDD), applies a minimal fix, and verifies.

```
/debug "KeyError: 'user_id' in process_payment"
/debug test_auth_refresh fails
/debug https://github.com/owner/repo/issues/42
/debug scope:branch the WebSocket reconnection fails on timeout
```

**Pipeline**: Reproduce → Diagnose (+ Domain Research) → User Approval → Regression Test (must fail) → Fix (test passes) → Verify & Review

**Accepts**: free text, failing test names, stack traces, error messages, GitHub issue URLs.

______________________________________________________________________

### `/investigate` — Hypothesis-Driven Investigation

Receives a suspected issue or behavioral question, analyzes the code for evidence, runs domain research when complex external behavior is involved, writes exploratory tests to prove or disprove, and reports a verdict. No code fixes — output is a report only.

```
/investigate the caching layer might not invalidate on concurrent writes
/investigate does the retry logic actually back off exponentially?
/investigate scope:branch the auth middleware might not handle expired refresh tokens
```

**Pipeline**: Code Analysis → Domain Research (conditional) → Exploratory Tests → Verdict Report

**Verdicts**: confirmed, disproved, inconclusive, partially confirmed. If confirmed, the report suggests running `/debug` to fix it.

______________________________________________________________________

### `/verify` — Deep Verification

Runs the full test suite, linters, formatters, type checkers, analyzes test coverage and quality, checks examples and samples, and diagnoses any failures. Produces a comprehensive pass/fail report.

```
/verify                                # full project
/verify scope:branch                   # branch changes only
/verify src/auth/                      # specific directory
/verify test_payments.py               # specific test file
```

**Pipeline**: Tooling Detection → Tests → Lint → Type Check → Coverage Review → Quality Review → Failure Diagnosis → Report

______________________________________________________________________

### `/polish` — Iterative Code Polisher

Takes existing code and iterates fix-test-review cycles until specific completion criteria are met. Unlike `/build` which builds from scratch, `/polish` works with what's already there.

```
/polish all tests pass and pre-commit is clean
/polish scope:branch fix all failing tests and clean up the implementation
/polish the WebSocket reconnection must handle timeout correctly
```

**Pipeline**: Assessment → Quick Fixes → Research (if needed) → Fix-Test-Review Loop (max 5 iterations) → Optimization → Final Verification

______________________________________________________________________

### `/optimize` — Code Optimization

Scans a scope, builds an import graph, groups files into parallel-safe chunks, dispatches optimizer agents (up to 6), then runs mirrored code reviewers. Iterates on rejections. Behavior preservation is enforced by tests between every pass.

```
/optimize src/auth/
/optimize scope:branch
/optimize "src/**/*.py"
/optimize origin/main..HEAD
```

**Pipeline**: Scan & Chunk → Baseline Snapshot → User Approval → Parallel Optimization → Verify → Parallel Review → Handle Verdicts → Summary

______________________________________________________________________

### `/explain` — Code Explainer

Researches a scope across structure, execution flow, and domain context, then produces a comprehensive report with Mermaid diagrams documenting how the code works, design rationale, and observations.

```
/explain src/auth/
/explain how does the payment flow work
/explain scope:branch
/explain output:docs/architecture.md the event bus module
```

**Pipeline**: Scope Analysis → Parallel Researchers (structure, flow, domain) → Synthesis → Report with Diagrams

______________________________________________________________________

### `/combine` — Local Source Combiner

Synthesizes prior pipeline output — `.mz/research/` reports, `.mz/task/*/` artifacts, `.mz/reports/`, `.mz/reviews/`, codebase files, git history — into a unified report with task-derived sections (or user-supplied sections via `sections:`). Local-first: only calls web research to fill residual gaps, and only after your approval.

```
/combine consolidate what we learned about the auth refactor
/combine sections:Context,Findings,Risks synthesize our findings on the WebSocket reconnection work
/combine output:docs/caching_summary.md pull together everything about cache invalidation
```

**Pipeline**: Inventory → Lens Decomposition → User Approval → Parallel Lens Dispatch → Synthesis → (optional) Gap-Fill Approval → Web Gap-Fill → Task-Adaptive Report

______________________________________________________________________

### `/translate` — Translation & Localization Pipeline

Parses a natural-language request to identify source files, target language, and output mode. Seeds a glossary from the source, presents a translation plan for approval, then dispatches parallel `pipeline-translator` agents that preserve markdown structure, code blocks, and i18n placeholders. Verification is always on and organized into three tiers: Tier-1 structural checks inside the translator agent, Tier-2 LLM-as-Judge on every chunk (wave-split), and Tier-3 uncertainty-driven deep verification (Wiktionary + MyMemory + back-translation) on flagged chunks only.

```
/translate README.md to Russian
/translate locales/en.json to fr mode:i18n
/translate docs/**/*.md to Japanese
/translate CHANGELOG.md to de mode:inplace
```

**Pipeline**: Discovery → Language Detect → Glossary Seed → Plan → User Approval → Parallel Translation + Tier-1 → Cross-File Consistency → Tier-2 Judge → Tier-3 Deep Verify (flagged chunks only) → Re-Translation Loop → Summary

**Output modes**: `sidecar` (default, writes `README.ru.md`), `i18n` (rewrites `locales/<lang>/…`), `inplace` (overwrites — destructive, requires explicit flag).

## Scope Parameter

All pipeline skills support an optional `scope:` parameter that constrains which files agents may edit:

| Mode            | What it includes                                         |
| --------------- | -------------------------------------------------------- |
| `scope:branch`  | Files changed on this branch vs base                     |
| `scope:global`  | All source files (minus vendored, generated, lock files) |
| `scope:working` | Uncommitted changes (staged + unstaged + untracked)      |

Scope restricts edits, not investigation — researchers and tests always read the full project.

## Agents

Specialized worker agents used by the pipeline skills. You don't invoke these directly — the skills orchestrate them.

| Agent                               | Role                                                                                           |
| ----------------------------------- | ---------------------------------------------------------------------------------------------- |
| **pipeline-researcher**             | Codebase exploration + domain research via web search                                          |
| **pipeline-web-researcher**         | Web-first research with primary-source verification                                            |
| **pipeline-planner**                | Creates parallelizable implementation plans                                                    |
| **pipeline-plan-reviewer**          | Validates plans for completeness and correctness                                               |
| **pipeline-coder**                  | Implements specific work units from an approved plan                                           |
| **pipeline-code-reviewer**          | Reviews code for bugs, security, conventions                                                   |
| **pipeline-test-writer**            | Writes unit, edge case, and integration tests                                                  |
| **pipeline-test-coverage-reviewer** | Identifies untested functions and missing code paths                                           |
| **pipeline-test-quality-reviewer**  | Evaluates test meaningfulness and independence                                                 |
| **pipeline-optimizer**              | Removes dead code, simplifies logic, cleans artifacts                                          |
| **pipeline-completeness-checker**   | Final quality gate — verifies 100% task completion                                             |
| **pipeline-translator**             | Translates a single file or chunk with Tier-1 structural verification and confidence reporting |

## Architecture

Skills follow a consistent pattern:

1. **SKILL.md** — slim orchestrator with setup, approval gates, and phase routing
1. **phases/\*.md** — on-demand phase files loaded only when needed (progressive disclosure)
1. **Agents** — stateless workers dispatched in parallel where safe, sequential where necessary

State is persisted to `.mz/task/<task_name>/` so pipelines can be inspected or resumed. Reports go to `.mz/reports/`.

## License

MIT
