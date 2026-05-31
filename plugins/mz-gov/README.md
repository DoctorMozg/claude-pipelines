# mz-gov

Lightweight development governance for solo devs and small teams building **with AI coding agents**. Generates, discusses, enforces, and reviews the decisions behind your code — and records which were proposed by an agent and approved by a human.

## What it does

`mz-gov` turns a substantial design decision into a durable, reviewed artifact. The `govern` pipeline routes a decision to the right artifact (ADR, RFC/RFD, or design doc), pressure-tests it with a critic panel, gates it behind an explicit human sign-off, then writes it to `docs/` with an AI-provenance block (which agent, which model, proposed-vs-approved). `gov-init` installs a concise governance policy into your `CLAUDE.md` so the pipeline fires on the decisions that matter. `gov-review` audits existing artifacts against a completeness rubric.

The distinguishing idea: an agent **proposes** a decision, a human **approves** it. Every governed decision carries machine-readable provenance and a recorded sign-off — closing the rubber-stamp gap that AI-authored changes are prone to.

## Skills

| Skill          | Command       | Inputs                                                                    | Output                                                          |
| -------------- | ------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------- |
| **govern**     | `/govern`     | A decision/change to govern; optional `artifact:adr\|rfd\|design`, `rich` | A numbered artifact in `docs/` with provenance + human sign-off |
| **gov-init**   | `/gov-init`   | `[project\|global] [--force] [--uninstall]`                               | A sentinel-wrapped governance policy block in `CLAUDE.md`       |
| **gov-review** | `/gov-review` | `[path-or-glob]`                                                          | A rubric-scored audit report in `.mz/reviews/`                  |

## The govern pipeline

```
/govern "switch the session store from in-memory to Redis"
  │
  ├─ Phase 0: Setup + AI-provenance capture
  ├─ Phase 1: Propose
  │     └─ gov-router (sonnet) — is an artifact required? which one?
  ├─ Phase 2: Discuss  (scaled by decision weight)
  │     ├─ heavy → alternatives / reversibility / blast-radius / assumptions (opus, parallel)
  │     │          └─ gov-discussion-synthesizer (sonnet)
  │     └─ light → gov-critic-quick (sonnet, single pass)
  ├─ Phase 3: Decide
  │     └─ human sign-off gate (verbatim artifact + provenance)
  ├─ Phase 4: Record
  │     └─ gov-artifact-writer (sonnet) — docs/decisions/NNNN-*.md
  └─ Phase 5: Enforce
        └─ link to commit/PR, set status, recommend /build
```

## Artifacts & where they live

| Artifact                      | Location                        | When                                      |
| ----------------------------- | ------------------------------- | ----------------------------------------- |
| ADR (Nygard or MADR)          | `docs/decisions/NNNN-title.md`  | A decision is made — record the why       |
| RFC / RFD (Oxide lifecycle)   | `docs/rfcs/NNNN-title.md`       | A decision is open — structure the debate |
| Design doc (Google 5-section) | `docs/design/NNNN-title.md`     | A decision is made — specify the build    |
| AI-provenance (AgDR)          | embedded in the artifact header | Every governed decision                   |

Durable artifacts are committed to `docs/`. Transient pipeline state lives under `.mz/task/`.

## Agents

| Agent                        | Model  | Role                                                          |
| ---------------------------- | ------ | ------------------------------------------------------------- |
| `gov-router`                 | sonnet | Decides whether an artifact is required, and which            |
| `gov-provenance-recorder`    | haiku  | Formats the AI-provenance block                               |
| `gov-critic-alternatives`    | opus   | Are the considered options complete? Is the choice justified? |
| `gov-critic-reversibility`   | opus   | One-way or two-way door? Is irreversibility warranted?        |
| `gov-critic-blast-radius`    | opus   | What does this affect downstream?                             |
| `gov-critic-assumptions`     | opus   | What unstated assumptions does this rest on?                  |
| `gov-critic-quick`           | sonnet | All four lenses in one pass, for lightweight decisions        |
| `gov-discussion-synthesizer` | sonnet | Merges the critic panel into one verdict                      |
| `gov-artifact-writer`        | sonnet | Writes the numbered durable artifact to `docs/`               |
| `gov-audit-reviewer`         | opus   | Scores existing artifacts against the review rubric           |

## Install

```bash
claude plugin install mz-gov
```

## Usage

Govern a decision and record it as an ADR:

```
/govern "adopt optimistic locking for the inventory table"
```

Install the governance policy so Claude invokes the pipeline on substantial decisions:

```
/gov-init project
```

Audit your existing decision records:

```
/gov-review docs/decisions
```
