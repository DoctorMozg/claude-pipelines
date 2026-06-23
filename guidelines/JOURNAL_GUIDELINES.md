# Interaction Journal Guidelines

Rules for the cross-cutting **interaction journal** — the durable, append-only record of how agents and the user actually interacted during a run: every approval gate, every input prompt, and every recorded decision. All plugins share one journal and one format.

The journal answers a question no other artifact does: *what was asked, what was decided, and who decided it* — across the whole pipeline, surviving context compaction. `state.md` tracks where a task is; the journal tracks how it got there.

## 1. One Journal, One File

The journal lives at `.mz/journal.md` in the project root (resolved by walking up to the nearest `.git`, the same root `mz-memory` uses). It is:

- **Global** — one file for every skill and every task. Entries are tagged by task and skill, not split into per-task files.
- **Append-only** — newest entries at the bottom. Never rewritten, never pruned by the pipeline (it is local scratch, not a curated store).
- **Gitignored scratch** — `.mz/` is gitignored. The journal never reaches git history or a teammate's checkout. It is a local audit trail and a recall feeder, not a published artifact.
- **Markdown** — human-readable at rest. No parser is required to audit it.

Because it is scratch, the journal may grow without bound. That is acceptable: it is disposable. A reader who wants only durable decisions reads `.mz/memory/MEMORY.md` (see §5), not the journal.

## 2. Two-Layer Capture

The journal is written by two layers that complement each other. Neither alone is sufficient.

**Layer A — deterministic (the hook).** `mz-memory` ships a `PostToolUse` hook matched to `AskUserQuestion`. Every approval gate and every input collector goes through `AskUserQuestion`, so the hook records the **verbatim question and the verbatim answer** for every interaction, automatically, with no per-skill instruction. This layer is the audit guarantee: it fires even when context is compacted and the model has forgotten it is mid-gate. It cannot see anything that is not in the tool call — not the task name, not the phase, not the Surface-1 artifact.

**Layer B — semantic (the skill).** The orchestrator knows what the hook cannot: which skill and task this is, which phase, which artifact was under review, and what the outcome means. After a gate resolves or a decision is made, the skill appends an **enrichment** entry carrying that context plus the verbatim artifact. This layer is a **SHOULD**, not a MUST — the hook already satisfies the audit-trail requirement on its own, so a skill that omits enrichment is still compliant. Add enrichment where the semantic context has lasting value: approval gates over real artifacts, and recorded decisions.

This split is deliberate. Requiring every one of the ~12 plugins' inline gates to log by instruction would be unenforceable and would rot. The hook makes logging free and total; enrichment is additive polish.

## 3. Entry Format

Entries are markdown sections. Each starts with `### ` and a tagged header line. Keep enrichment compact; the artifact is the only part allowed to be long.

**Layer A — hook baseline** (written automatically; shape is illustrative — the hook dumps whatever `tool_input` / `tool_response` actually contain):

```
### 2026-06-05T14:32:10Z · session 82ba9d1d · AskUserQuestion

questions (verbatim):
{"questions":[{"question":"The plan above is ready for review.","header":"Approval","options":[{"label":"Approve"},{"label":"Reject"}]}]}

response (verbatim):
{"The plan above is ready for review.":"Approve"}
```

**Layer B — skill enrichment** (written by the orchestrator after the gate resolves):

```
### 2026-06-05T14:32:11Z · build · 2026_06_05_build_oauth_flow · gate

- phase: 6 (implementation)
- gate: plan-approval · outcome: APPROVE
- model: claude-opus-4-8
- artifact (.mz/task/2026_06_05_build_oauth_flow/plan.md, verbatim):

  <full plan.md contents — <private>…</private> regions redacted to [redacted]>

- promoted: state.md ## Decisions → Activity Log (auto at SessionEnd)
```

Header grammar: `### <ISO-8601 UTC> · <skill|session id> · <task name|tool> · <event type>`. Event types: `gate`, `input`, `decision`, `phase`. Use UTC (`date -u`) so entries from concurrent sessions sort coherently.

## 4. What to Record

| Interaction                             | Layer A (hook)                | Layer B (skill SHOULD)                                                                                                                     |
| --------------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Approval gate (Approve/Reject/feedback) | always                        | outcome + verbatim artifact                                                                                                                |
| Input collector / intake question       | always                        | the resolved value + why it was needed                                                                                                     |
| Recorded decision (chose X over Y)      | only if it ran through a gate | the decision, options, rationale — and promote it (§5)                                                                                     |
| Phase transition                        | —                             | optional one-liner for long pipelines                                                                                                      |
| Auto-approval (unattended mode)         | —                             | required: log that the gate was auto-approved and on whose authority (the existing `state.md ## Auto-approvals` entry plus a journal line) |

Feedback loops: when a gate is rejected with feedback and re-presented, each pass is its own entry. The journal shows the negotiation, not just the final answer.

## 5. Recall: Promoting Decisions to Memory

The journal is write-mostly audit. Decisions worth *recalling* in future sessions graduate into `mz-memory`, which injects them at SessionStart. Two promotion paths, no cross-plugin script calls required:

- **Automatic (default).** Write the decision into a `## Decisions` section of the task's `state.md`. `mz-memory`'s SessionEnd capture harvests `## Decisions` / `## Lessons` / `## Notes` (first 10 lines) into the **Activity Log** with a `[branch@sha]` tag. The Activity Log is a rolling FIFO (cap 200), so routine decisions surface for a while, then age out. Every multi-phase skill already maintains `state.md`, so this path is free.
- **Explicit (load-bearing invariants).** For a decision that must never roll off — an architectural invariant, a binding convention — promote it to the **Pinned** section via `/memory-note` (or `memory-note.sh`). Pinned is never auto-pruned. Use this sparingly; pinned memory is injected into every session.

A skill that records a substantial decision SHOULD write it to `## Decisions` (automatic recall) and MAY recommend pinning it. `mz-gov` does both: it records the durable artifact under `docs/` and writes the decision summary to its state so it feeds recall.

## 6. Ownership and Dependency

The journal is a **shared primitive**, not owned by any one workflow:

- The **format and rules** are this file. All plugins follow it.
- The **capture hook and the append helper** live in `mz-memory` (`scripts/journal-capture.sh`, `scripts/journal-append.sh`), because `mz-memory` already owns the hook lifecycle and the recall store the journal feeds.
- **Consumers** (e.g. `mz-gov`, `mz-dev-pipe` gates) follow the convention: they append enrichment and promote decisions. They do not reach into `mz-memory`'s scripts; they write `.mz/journal.md` and `state.md` directly, which any skill can do with its normal tools.

**Dependency note:** deterministic capture (Layer A) requires `mz-memory` installed, since it hosts the hook. Without `mz-memory`, gates still work and the instruction layer still appends — the audit trail just loses its automatic guarantee and depends on skills following the convention. State this honestly; do not assume the hook is present.

## 7. Privacy and Redaction

The journal captures interactions verbatim, including artifacts that may carry sensitive content (outreach drafts, tokens, customer data). Two protections:

- **It is local gitignored scratch.** It never leaves the machine through git.
- **`<private>…</private>` is honored.** The append helper replaces any `<private>…</private>` region with `[redacted]` before writing — preserving surrounding formatting (unlike `mz-memory`'s whitespace-collapsing `strip_private`, the journal redactor keeps code indentation intact). Wrap secrets you never want at rest in `<private>` tags. The hook redacts the question/answer it captures; skills are responsible for wrapping sensitive spans in the artifacts they append.

Redaction is best-effort defense in depth, not a guarantee. Do not deliberately route credentials through a gate and rely on the journal to scrub them.

## 8. Verification

- The capture hook must be runnable standalone with a synthetic event on stdin and must `exit 0` on every path (missing file, malformed JSON, non-`AskUserQuestion` tool). See `HOOKS_GUIDELINES.md` for the failure discipline it inherits.
- After a gate runs, `.mz/journal.md` must contain a new entry. A gate that produced no journal entry means the hook is not installed (check `mz-memory`) or the tool was not `AskUserQuestion`.
- Promotion is verified by presence: a decision written to `state.md ## Decisions` appears in `.mz/memory/MEMORY.md` after the next SessionEnd.
