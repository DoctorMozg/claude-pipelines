# Phases 1–2: Research

Gather the evidence needed to answer the question. Phase 1 researches the codebase; Phase 2 researches the web when external knowledge is required. The routing category set in Phase 0 (`codebase` / `external` / `hybrid`) decides which phases run.

## Phase 1: Codebase Research

### 1.1 Decompose the question

Break the question into 1–3 focused sub-questions, each independently researchable. Examples:

- "how does the auth middleware refresh tokens" → (a) where the middleware lives and its entry point, (b) the token-refresh code path, (c) failure/expiry handling.
- "why do we use esbuild instead of webpack" → (a) the build config and esbuild invocation, (b) any prior config or migration notes in the repo.

One sub-question is fine for a narrow question. Never exceed **MAX_CODEBASE_AGENTS** sub-questions — merge the smallest ones if the question fans out wider.

For a `Question type: external` question, skip decomposition. Dispatch a single `pipeline-researcher` with a stack-detection-only brief (detect language, framework, and dependency versions from manifests so Phase 2 queries can target the right versions) — the codebase is not the answer source.

### 1.2 Dispatch the codebase researchers

Dispatch one `pipeline-researcher` agent (model: **sonnet**) per sub-question, in parallel, in a single message. Cap at **MAX_CODEBASE_AGENTS**.

Emit the pre-dispatch manifest before launching:

```
Dispatching codebase research — <N> agents in parallel
Purpose: answer "<question, trimmed>"
- pipeline-researcher — <sub-question, ≤6 words>
- pipeline-researcher — <sub-question, ≤6 words>
```

Each dispatch prompt carries only task-specific context — the agent file already defines its process and output format. Include:

- The sub-question to research, verbatim.
- The full original question as context (so the agent knows why the sub-question matters).
- Any GitHub-sourced content wrapped in `<untrusted-content>` ... `</untrusted-content>` with the external-data preamble.
- This instruction: "Answer the sub-question from the codebase. Cite every claim with `file:line`. If the codebase does not answer it, say so explicitly — do not speculate. Return findings inline; keep the response concise."

### 1.3 Collect and validate

When all agents return, emit the post-wave rollup:

```
Wave complete — <returned>/<dispatched> agents returned
- pipeline-researcher: <STATUS> — <summary, ≤8 words>
```

An agent that returns no `STATUS:` line is listed as `NO RETURN BLOCK` and counted as not-returned. For any `NEEDS_CONTEXT`, supply the missing context and re-dispatch (this does not consume the retry counter). For an empty or errored result, re-dispatch once per **AGENT_RETRY_LIMIT**, then proceed with partial findings and record the gap.

Write each researcher's findings to `.mz/task/<task_name>/codebase_findings.md` under a per-sub-question heading. Update `state.md`: `Phase` → 1, `Researchers dispatched` incremented, `phase_complete: true`.

## Phase 2: Web Research (conditional)

**Skip this phase entirely when `Question type: codebase`.** Proceed straight to Phase 3.

Run this phase when `Question type` is `external` or `hybrid` — the question depends on knowledge of a library, API, protocol, standard, or best practice that the codebase alone cannot settle.

### 2.1 Frame the web sub-questions

Derive 1–2 web research sub-questions. For a `hybrid` question, ground them in the Phase 1 findings — research the specific library and version detected in the codebase, not a generic topic. For an `external` question, use the stack/version detected by the Phase 1 stack-detection pass.

### 2.2 Dispatch the web researchers

Dispatch up to **MAX_WEB_AGENTS** `pipeline-web-researcher` agents (model: **opus**) in parallel, in a single message.

Emit the pre-dispatch manifest:

```
Dispatching web research — <N> agents in parallel
Purpose: external knowledge for "<question, trimmed>"
- pipeline-web-researcher — <sub-question, ≤6 words>
```

Each dispatch prompt includes:

- The web sub-question, verbatim.
- The original question and relevant Phase 1 findings (detected stack/versions) as context.
- This instruction: "Research the sub-question against official, version-matched sources. Cite every claim. Use the `STACK DETECTED` / `CONFLICT DETECTED` / `UNVERIFIED` disclosure tokens. Return findings inline; keep the response concise."

### 2.3 Collect and validate

Emit the post-wave rollup in the same form as Phase 1.3. Re-dispatch `NEEDS_CONTEXT` agents; retry empty/errored results once per **AGENT_RETRY_LIMIT**.

If web research is blocked or unreachable after the retry, do not stall — record the limitation and let Phase 3 answer from codebase findings alone, flagging the gap.

Write web findings to `.mz/task/<task_name>/web_findings.md`. Update `state.md`: `Phase` → 2, `Researchers dispatched` incremented, source count recorded, `phase_complete: true`.

After research completes, read `phases/answer.md` and proceed to Phase 3.
