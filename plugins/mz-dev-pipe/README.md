# mz-dev-pipe

Autonomous multi-agent development pipelines for Claude Code. Each skill orchestrates specialized agents through phased workflows — research, plan, implement, review, test — with user approval gates and iterative convergence.

## Pick a skill in 5 seconds

| You want to…                                  | Run                                                          |
| --------------------------------------------- | ------------------------------------------------------------ |
| Fix a known bug                               | `/debug`                                                     |
| Investigate a suspected bug (no fix)          | `/debug certainty:low`                                       |
| Build a new feature end-to-end                | `/build`                                                     |
| Sweep code before opening a PR                | `/audit` (or `/audit depth:deep` for ship)                   |
| Iterate fix-test-review until clean           | `/polish`                                                    |
| Clean up / refactor existing code             | `/cleanup`                                                   |
| Make something measurably faster or smaller   | `/optimize`                                                  |
| Verify the project (tests, lint, types)       | `/verify`                                                    |
| See what breaks if you change X               | `/audit depth:deep scope:branch` (auto-invokes blast-radius) |
| Understand existing code                      | `/explain` (now in `mz-research-pipe`)                       |
| Research a topic across the web               | `/deep-research` (now in `mz-research-pipe`)                 |
| Synthesize prior pipeline output into one doc | `/combine` (now in `mz-research-pipe`)                       |
| Translate files preserving structure          | `/translate` (now in `mz-research-pipe`)                     |

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

### `/debug` — Reactive Bug Investigation & Hypothesis Verification

Two modes selected by the `certainty:` parameter.

**`certainty:high` (default — TDD bug fix)**: given a bug report (error message, stack trace, failing test, or description), reproduces the bug, diagnoses root cause with optional domain research, writes a regression test before the fix (TDD), applies a minimal fix, and verifies.

```
/debug "KeyError: 'user_id' in process_payment"
/debug test_auth_refresh fails
/debug https://github.com/owner/repo/issues/42
/debug scope:branch the WebSocket reconnection fails on timeout
```

**Pipeline**: Reproduce → Diagnose (+ Domain Research) → User Approval → Regression Test (must fail) → Fix (test passes) → Verify & Review

**`certainty:low` (hypothesis investigation — no fix)**: receives a suspected issue or behavioral question, analyzes the code for evidence, runs domain research when complex external behavior is involved, writes exploratory tests to prove or disprove, and reports a verdict. **No code fixes** — output is a report only.

```
/debug certainty:low the caching layer might not invalidate on concurrent writes
/debug certainty:low does the retry logic actually back off exponentially?
/debug certainty:low scope:branch the auth middleware might not handle expired refresh tokens
```

**Pipeline**: Code Analysis → Domain Research (conditional) → Exploratory Tests → Verdict Report (no user-approval gate)

**Verdicts**: confirmed, disproved, inconclusive, partially confirmed. If confirmed, the report suggests running `/debug` (high certainty, the default) to fix it.

**Accepts**: free text, hypotheses, failing test names, stack traces, error messages, GitHub issue URLs.

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

### `/cleanup` — Code Cleanup

Scans a scope, builds an import graph, groups files into parallel-safe chunks, dispatches optimizer agents (up to 6), then runs mirrored code reviewers. Iterates on rejections. Behavior preservation is enforced by tests between every pass.

```
/cleanup src/auth/
/cleanup scope:branch
/cleanup "src/**/*.py"
/cleanup origin/main..HEAD
```

**Pipeline**: Scan & Chunk → Baseline Snapshot → User Approval → Parallel Optimization → Verify → Parallel Review → Handle Verdicts → Summary

______________________________________________________________________

### `/optimize` — Measure-First Performance Optimization

Iteratively and safely makes a target faster, smaller, or cheaper against a measurable goal. Establishes a trusted baseline, profiles the dominant bottleneck, forms falsifiable speedup hypotheses, generates candidate changes in isolated worktrees, and verifies each one by benchmark — banking only a change that measurement proves faster and a correctness check proves safe. Domain-generic: the same loop optimizes source code, container images, LLM hyperparameters, build pipelines, or a composite system, driven by a per-run Optimization Contract. Every speedup number comes from the measurement harness, never from model narration.

```
/optimize make src/parser/tokenizer.py 2x faster, p95 under 120ms
/optimize type:container reduce the api image below 200MB
/optimize type:system scope:branch cut orchestrator end-to-end latency below 400ms
```

**Pipeline**: Goal Declaration → Contract Approval → Baseline → Profile & Classify → Hypothesize → Strategy Approval → Candidate Generation & Verification → Validation → Terminate (re-profile loop or stop)

**Not for** removing dead code or reducing complexity — that is `/cleanup`.

______________________________________________________________________

### `/combine`, `/deep-research`, `/explain`, `/translate` — moved to `mz-research-pipe`

These research and content skills now live in the [`mz-research-pipe`](../mz-research-pipe/README.md) plugin. Install both plugins together for full functionality — `/deep-research`, `/combine`, and `/explain` reuse `pipeline-web-researcher` and `pipeline-researcher` agents from `mz-dev-pipe`.

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

| Agent                             | Role                                                                                                      |
| --------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **pipeline-researcher**           | Codebase exploration + domain research via web search                                                     |
| **pipeline-web-researcher**       | Web-first research with primary-source verification                                                       |
| **pipeline-planner**              | Creates parallelizable implementation plans                                                               |
| **pipeline-plan-reviewer**        | Validates plans for completeness and correctness                                                          |
| **pipeline-coder**                | Implements specific work units from an approved plan                                                      |
| **pipeline-code-reviewer**        | Reviews code for bugs, security, conventions                                                              |
| **pipeline-test-writer**          | Writes unit, edge case, and integration tests                                                             |
| **pipeline-test-reviewer**        | Unified test review — coverage gaps + test quality (assertions, independence, fragility)                  |
| **pipeline-optimizer**            | Removes dead code, simplifies logic, cleans artifacts                                                     |
| **pipeline-completeness-checker** | Final quality gate — verifies 100% task completion                                                        |
| **pipeline-measure-runner**       | Runs a benchmark with warmup and N reps, computes mean/median/CV — the only source of measurement numbers |
| **pipeline-perf-candidate**       | Implements one optimization hypothesis as a diversified candidate change in an isolated worktree          |

## Architecture

Skills follow a consistent pattern:

1. **SKILL.md** — slim orchestrator with setup, approval gates, and phase routing
1. **phases/\*.md** — on-demand phase files loaded only when needed (progressive disclosure)
1. **Agents** — stateless workers dispatched in parallel where safe, sequential where necessary

State is persisted to `.mz/task/<task_name>/` so pipelines can be inspected or resumed. Reports go to `.mz/reports/`.

## License

MIT
