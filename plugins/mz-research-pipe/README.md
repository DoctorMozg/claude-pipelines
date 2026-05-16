# mz-research-pipe

Autonomous research and content pipelines — skills that produce reports and rewritten artifacts rather than mutating application code. Spun off from `mz-dev-pipe` so the dev plugin stays focused on build/debug/audit/cleanup/optimize/polish/verify.

## Pick a skill in 5 seconds

| You want to…                                  | Run              |
| --------------------------------------------- | ---------------- |
| Research a topic across the web               | `/deep-research` |
| Synthesize prior pipeline output into one doc | `/combine`       |
| Translate files preserving structure          | `/translate`     |
| Understand existing code                      | `/explain`       |

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-research-pipe
```

## Skills

### `/deep-research` — Multi-Agent Web Research

Splits a research topic into 3-7 independent subtopics, presents the decomposition for approval, then dispatches parallel `pipeline-web-researcher` agents that each scan 20-100 web pages and verify against primary sources. Synthesizes findings into a comprehensive report under `.mz/research/`.

```
/deep-research best practices for gRPC error handling in Go
/deep-research comparison of vector databases for RAG pipelines
```

**Pipeline**: Decompose → User Approval → Parallel Web Research (one agent per subtopic) → Cross-Reference Synthesis → Report

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

## Scope Parameter

`/explain` and `/combine` accept the standard `scope:` parameter — `branch`, `global`, or `working` — to bound which files agents read.

| Mode            | What it includes                                         |
| --------------- | -------------------------------------------------------- |
| `scope:branch`  | Files changed on this branch vs base                     |
| `scope:global`  | All source files (minus vendored, generated, lock files) |
| `scope:working` | Uncommitted changes (staged + unstaged + untracked)      |

## Agents

| Agent                   | Role                                                                                           |
| ----------------------- | ---------------------------------------------------------------------------------------------- |
| **pipeline-translator** | Translates a single file or chunk with Tier-1 structural verification and confidence reporting |

`/deep-research`, `/combine`, and `/explain` reuse `pipeline-web-researcher` and `pipeline-researcher` from `mz-dev-pipe` — install both plugins together for full functionality.

## License

MIT
