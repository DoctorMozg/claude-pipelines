# Phase 1: Codebase Research

The orchestrator runs this phase directly (no subagent). The goal is to ground the writer in real code so it does not invent API signatures, file paths, or behaviors. Output: `.mz/task/<task_name>/research.md`.

## 1.1 Resolve scope

Convert `scope:` modifier to a file list:

- `scope:working` — files in `git status --porcelain` (modified, added, untracked tracked patterns)
- `scope:branch` — files in `git diff --name-only $(git merge-base HEAD master)..HEAD` (or `main` if `master` doesn't exist)
- `scope:global` — entire repo, respecting `.gitignore`

If the resolved list is empty, escalate via AskUserQuestion: offer to widen scope or proceed without research.

## 1.2 Stack detection

Read project manifests in this order: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Gemfile`, `pom.xml`, `build.gradle`. For each detected stack, emit a `STACK DETECTED:` line with concrete versions:

```
STACK DETECTED: Python 3.11 + FastAPI 0.115 + SQLAlchemy 2.0 + Postgres 15
STACK DETECTED: TypeScript 5.4 + Next.js 14 (app router) + Tailwind 3.4
```

If no manifest is found, emit `STACK DETECTED: unknown — no manifest found` and continue. The writer needs to know what assumptions are safe.

## 1.3 Identify public surface

Find the set of public APIs, exported functions, CLI commands, configuration flags, environment variables, or HTTP routes that the documentation will need to describe.

Strategies:

- **Library**: grep for `export`, `__all__`, `pub fn`, `pub struct` markers
- **CLI**: read the entry point, scan for argument parsers (`argparse`, `click`, `commander`, `clap`)
- **HTTP service**: scan for route registration (`@app.route`, `router.get`, `app.use`)
- **Config**: scan for environment variable reads, settings classes, dotenv files

Capture: name, signature or shape, file path, one-line description from existing docstring or first usage.

## 1.4 Existing documentation inventory

List existing documentation in the repo. Look for:

- `README.md`, `README.rst`, `README.txt` at root and in subdirs
- `docs/`, `documentation/`, `doc/` directories
- `CONTRIBUTING.md`, `ARCHITECTURE.md`, `CHANGELOG.md`
- Inline docstrings (sample 5–10 to gauge style)
- Comments at the top of major modules

Note: format used (Markdown, RST, AsciiDoc), tone (formal/conversational), depth (one-line / multi-paragraph), structural conventions (heading style, code-block fence style, link format).

## 1.5 Conventions and style

Capture project conventions the writer must respect:

- Naming style (snake_case / camelCase / kebab-case)
- Heading style (sentence case / title case)
- Code-block language tags
- Quote style (smart / straight)
- Contraction usage in existing docs
- Use of badges, callouts, admonitions

## 1.6 Prior art

Search git log for documentation-related commits: `git log --all --oneline | grep -iE 'doc|readme|tutorial|guide'`. Note any prior doc rewrites and the commit messages that explain why. Documentation rewrites that were rolled back signal something the writer should avoid.

## 1.7 Constraints from code

Capture hard constraints visible in the code that the documentation must reflect:

- Version compatibility (what Python / Node / Java versions are supported)
- Required environment (OS, runtime, dependencies)
- Public API surface that has stability guarantees
- Deprecated paths the docs should call out

## 1.8 Diátaxis structure proposal

Based on the brief and the `type:` modifier, propose a Diátaxis structure:

- `type:readme` → README structure (title, description, install, usage, contributing, license)
- `type:api` or `type:reference` → reference structure (synopsis, parameters, returns, errors, examples)
- `type:tutorial` → linear tutorial (prerequisites, step 1..N, recap)
- `type:howto` → goal-oriented how-to (when to use, steps, troubleshooting)
- `type:explanation` → conceptual explanation (problem, approaches, design, trade-offs)
- `type:all` → split into multiple sections, one per Diátaxis type, each labeled

For polish jobs (`@doc:` provided), read the existing doc and propose what to keep, change, or split into separate Diátaxis types.

## 1.9 Write `research.md`

Write `.mz/task/<task_name>/research.md` using this structure:

```markdown
# Research — <one-line task title>

## Scope
<scope value, file count>

## Stack
STACK DETECTED: ...
STACK DETECTED: ...

## Public surface
- `<symbol>` (`<file>:<line>`) — <one-line description>
- ...

## Existing documentation
- <path> — <format, tone, depth>
- ...

## Conventions
- <convention category>: <observed style>
- ...

## Prior art
- <commit hash> — <commit message> — <relevance>
- ...

## Constraints
- <constraint>
- ...

## Proposed Diátaxis structure
**Type(s)**: <e.g., reference + how-to>

**Outline**:
1. <H2 heading> [<Diátaxis type>]
2. <H2 heading> [<Diátaxis type>]
...

**Polish notes** (only if `@doc:` was provided):
- Keep: <sections to preserve>
- Change: <sections to rewrite>
- Split: <sections to break out>
```

Keep it tight. Aim for 100–200 lines.

## 1.10 Hand off to Phase 1.5

Update `state.md`: phase → `research_complete`, append `research.md` to `FilesWritten`. Phase 1.5 (approval gate) runs next, defined inline in SKILL.md.
