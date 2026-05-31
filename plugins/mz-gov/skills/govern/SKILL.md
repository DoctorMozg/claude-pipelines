---
name: govern
description: ALWAYS invoke for a substantial design or architecture decision — schema/API/dependency/boundary changes. Triggers:"should I","ADR for X","decide between","record this decision". NOT for refactors, trivial fixes, or prototyping.
argument-hint: <decision to govern> [artifact:adr|rfd|design|auto] [rich]
model: sonnet
allowed-tools: Agent(gov-router), Agent(gov-provenance-recorder), Agent(gov-critic-alternatives), Agent(gov-critic-reversibility), Agent(gov-critic-blast-radius), Agent(gov-critic-assumptions), Agent(gov-critic-quick), Agent(gov-discussion-synthesizer), Agent(gov-artifact-writer), AskUserQuestion, Read, Write, Bash, Glob, Grep
---

# Govern — Decision Lifecycle Orchestrator

## Overview

Takes a development decision and runs it through a five-phase lifecycle — route the right artifact (or none), discuss it through an adversarial critic panel scaled to the decision's weight, gate it behind an explicit human sign-off, write the durable record to `docs/`, then link it to the commit/PR and recommend the next step. Every governed decision lands with AI-provenance attached and a human's name on it. An agent proposes; a human approves.

## When to Use

- A substantial, ambiguous design or architecture choice — behavior, public API, data schema, a dependency swap, a module boundary, security posture, or anything hard to reverse with more than one defensible approach.
- Triggers: "should I X or Y", "write an ADR for X", "decide between A and B", "record this decision".

### When NOT to use

- Behavior-preserving refactors, objective improvements (warning removal, a speedup), dev-invisible tweaks — exempt; just build.
- Trivial one-line fixes or throwaway prototype/spike code — the artifact overhead loses.
- Auditing artifacts that already exist — use `gov-review`. Installing the policy block — use `gov-init`.

## Input

- `$ARGUMENTS` — the decision to govern (free text). If empty, ask the user what decision to govern; never guess.
- `artifact:adr|rfd|design|auto` — optional explicit artifact override. `auto` or absent lets the router choose.
- `rich` — optional flag requesting the richer ADR (MADR) variant.

## Constants

- **MAX_DISCUSS_ITERATIONS**: 3 | **MAX_PANEL_AGENTS**: 4 | **TASK_DIR**: `.mz/task/`
- **DECISIONS_DIR**: `docs/decisions/` | **RFCS_DIR**: `docs/rfcs/` | **DESIGN_DIR**: `docs/design/`
- **Default statuses**: ADR `proposed` | RFD `prediscussion` | design `draft`

## Core Process

### Phase Overview

| Phase | Goal                                   | Details             | Loop?              |
| ----- | -------------------------------------- | ------------------- | ------------------ |
| 0     | Setup                                  | inline below        | —                  |
| 1     | Propose — route the artifact (or none) | `phases/propose.md` | —                  |
| 2     | Discuss — weight-scaled critic panel   | `phases/discuss.md` | max 3 (heavy only) |
| 3     | Decide — human sign-off gate           | `phases/decide.md`  | feedback loop      |
| 4     | Record — write durable artifact        | `phases/record.md`  | —                  |
| 5     | Enforce — link commit/PR, recommend    | `phases/enforce.md` | —                  |

### Phase 0: Setup (inline)

1. Parse `$ARGUMENTS`: the decision text, an optional `artifact:` override (`adr`/`rfd`/`design`/`auto`), and the optional `rich` flag. Empty decision → AskUserQuestion; never guess.
1. Derive `task_name` = `<YYYY_MM_DD>_govern_<slug>` where `<YYYY_MM_DD>` is today's date (underscores) and `<slug>` is a snake_case summary of the decision (max 20 chars). On same-day collision append `_v2`, `_v3`.
1. **Resume check** (before creating the directory) — read `.mz/task/<task_name>/state.md` if it exists:
   - **No file** → fresh task; proceed.
   - **Status `complete` or `aborted_by_user`** → auto-suffix `_v2`/`_v3`, log the bump to chat, proceed fresh.
   - **Status `running` or `failed`** → present a Resume gate via AskUserQuestion (`Resume` re-enters at the recorded `Phase`; `Restart` archives the dir to `<task_name>_archived_<YYYY_MM_DD_HHMMSS>/` and starts fresh; `New` suffixes `_v2`). The human sign-off in Phase 3 never auto-resumes — re-present it.
1. Create `.mz/task/<task_name>/`. Write `state.md` per the inline v2 contract (State Management below): first line `schema_version: 2`, then `Status: running`, `Phase: 0`, `PhaseName: setup`, `Started: <ISO>`, `Iteration: 0`, `FilesWritten: []`, `phase_complete: false`, `what_remains: []`, plus `Decision: <text>`, `ArtifactOverride: <value|auto>`, `Rich: <bool>`.
1. Dispatch `gov-provenance-recorder` to write `.mz/task/<task_name>/provenance.md` for *this* run — pass the task dir, the authoring agent (`gov-artifact-writer`, the agent that will write the durable record), the exact model id, the current ISO timestamp, and the trigger origin (`user-prompt` for a direct `/govern`, `automation` when the governance policy directed this invocation). It initializes `human_signoff: pending`. Append `provenance.md` to `FilesWritten`.
1. Emit a setup block: task_name, decision summary, override, rich flag, provenance path + derived trigger.

Read `phases/propose.md` and proceed to Phase 1.

### Phase 1: Propose

Dispatch `gov-router` to run the two-gate selection and write `routing.md`. If `ARTIFACT: none` → record a one-line exemption note, keep provenance, update state, and **stop at Phase 1** (report to the user — no discussion, no gate). Otherwise draft the populated artifact into `.mz/task/<task_name>/draft.md` and carry `WEIGHT` forward. See `phases/propose.md`.

### Phase 2: Discuss

Weight-scaled. `heavy` → four opus critics in one parallel message (manifest first), then `gov-discussion-synthesizer`; loop the draft against the synthesis up to `MAX_DISCUSS_ITERATIONS`, escalating at the cap. `light` → one `gov-critic-quick` pass whose output is the verdict. `ARTIFACT: none` never reaches here. See `phases/discuss.md`.

### Phase 3: Decide

The human sign-off gate — the whole point of the pipeline. This orchestrator (not a subagent) emits the verbatim `draft.md` plus the verdict and the AI-provenance block as a plan-style chat message, then a short Approve/Reject AskUserQuestion selector beneath it. Approve → stamp `human_signoff`, advance status, go to Phase 4. Reject → write nothing to `docs/`. Any other reply is feedback → revise and re-present. **No auto-approve bypass exists on this gate.** See `phases/decide.md`.

### Phase 4: Record

Dispatch `gov-artifact-writer` (only after sign-off is stamped) to write the durable `docs/<dir>/NNNN-slug.md` with sequential numbering, the embedded provenance fence, and an initial status from the configured vocabulary. Append the path to `FilesWritten`. See `phases/record.md`.

### Phase 5: Enforce

Detect git context (commit, branch, optional open PR — read-only), append a `## Provenance / Links` section to the artifact, advance status where appropriate, and recommend the next skill (never auto-invoke). Mark state `complete`, `what_remains: []`. See `phases/enforce.md`.

## Techniques

Techniques: delegated to phase files — see the Phase Overview table above.

## Common Rationalizations

Common Rationalizations: delegated to phase files — `propose.md` (skipping the router), `discuss.md` (skipping the panel), `decide.md` (skipping the human gate).

## Red Flags

- You drafted to `docs/` before the human sign-off gate passed, or while `provenance.md` still read `human_signoff: pending`.
- You routed from memory instead of dispatching `gov-router`, or skipped the discuss panel on a `heavy` decision.
- You auto-approved the Phase 3 gate, or treated critic consensus as the human's approval. There is no auto-approve here.
- You auto-invoked the recommended next skill in Phase 5 instead of recommending it.

## Verification

Verification: delegated to phase files. Each phase emits a visible block; the final enforce block lists the artifact path, status, sign-off signature, git links, and the recommended next step, with `state.md` marked `complete` and `what_remains: []`.

## Error Handling

Detect → escalate via AskUserQuestion → never guess. Empty decision, an unreadable reference/template, an agent returning `BLOCKED` (retry once, then escalate), and `MAX_DISCUSS_ITERATIONS` hit without convergence (offer accept-with-unresolved / guidance / abort) all escalate. Always save state before dispatching agents.

## State Management

State persists to `.mz/task/<task_name>/state.md`. Schema is **v2**: the file's first line is `schema_version: 2`, and alongside the skill's existing `Status` / `Phase` / `Started` keys it carries `phase_complete` (boolean) and `what_remains` (YAML list of strings). Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass; refresh `what_remains` on every phase transition; `what_remains` MUST be `[]` when `Status: complete`. On reading a `schema_version: 1` or unversioned file, add the missing keys, set `schema_version: 2`, and log the upgrade.

Append every produced artifact to `FilesWritten` (routing.md, provenance.md, draft.md, discuss/discussion files, the `docs/` artifact). Record `human_signoff` only after the Phase 3 gate. Never rely on conversation memory for cross-phase state — context compaction destroys specific paths and decisions.
