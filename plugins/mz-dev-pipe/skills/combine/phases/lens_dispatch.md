# Phase 2: Parallel Lens Dispatch (and Phase 4: Web Gap-Fill)

**Goal**: Fan out the approved lenses as parallel local-only researchers, collect their extracts, and — only after Phase 3.5 approval — dispatch a single wave of web researchers to fill residual gaps.

## Contents

- 2.1 Dispatch setup
- 2.2 Per-lens dispatch prompt template
- 2.3 Collect extracts
- Phase 4: Web Gap-Fill (conditional)
- Error Handling for this phase

______________________________________________________________________

## Phase 2.1: Dispatch setup

**Goal**: Recover the approved lens list and fan out all lenses in a single parallel wave.

1. **Read the inventory artifact**. Open `.mz/task/<task_name>/inventory.md` and recover the `## Proposed lenses` block — this is the list the user explicitly approved at the Phase 1.5 gate. For each lens you need:
   - Lens name (e.g., `research`, `tasks`, `reports_reviews`, `codebase`, `git_history`, or any custom lens the user accepted).
   - One-line purpose.
   - Exhaustive file list (concrete paths — never globs, never discovery instructions).
1. **Sanity check** the recovered list:
   - Every lens has a non-empty file list. A lens with zero files is a decomposition bug from Phase 1.3 — escalate via AskUserQuestion rather than dispatching an empty agent.
   - Total lens count is between the 3-lens floor (after subtracting any bucket marked `unavailable`) and `MAX_LENSES = 6`. If the count exceeds 6, it is a Phase 1.3 bug — escalate.
1. **Fan out in a single message**. Issue one `Agent` tool call per lens, all in the same message, as parallel tool calls. The wave size is bounded by `MAX_LENSES = 6`. Each dispatch targets the `pipeline-researcher` agent at **model: sonnet**. Sonnet is the right choice because each lens is a bounded, local-only extraction task over a pre-selected file list — opus would be token-wasteful here, and gap-fill is the opus-tier step.
1. **Do not stage the wave.** All lenses launch together; there is no "first lens then the others". Waiting for any single lens to return before dispatching the rest defeats the parallelism and breaks Rule 13.
1. **Update state.md** with `phase: dispatched`, `lenses_dispatched: <N>`, and the ordered lens name list. Include the timestamp so Phase 2.3 can measure wall-clock.

______________________________________________________________________

## Phase 2.2: Per-lens dispatch prompt template

**Goal**: Give every lens researcher a prompt that is unambiguous, exhaustive, and absolutely forbids off-list reads or any web access.

Fill the `<PLACEHOLDERS>` per lens. The template below is copy-ready — do not rewrite it, only substitute.

```
You are the <LENS_NAME> lens of a /combine synthesis run.

## Task
<TASK_TEXT>

## Your scope (exhaustive file list — do not discover more)
<NEWLINE_SEPARATED_FILE_LIST>

## Hard constraints
- LOCAL-ONLY: do NOT use WebSearch or WebFetch. If you need a fact that is not in the listed files, mark it as a gap — do not search the web.
- Read ONLY the listed files. Do not open any file not in the list above, regardless of references found within them.
- Output budget: <=300 lines total. Favor extracts over paraphrase.

## What to extract
1. Every specific fact, decision, finding, or open question from the listed files that is relevant to the task.
2. Per-extract metadata: source file path, file mtime (run `ls -l` once), confidence (high if verbatim, medium if inferred, low if speculative).
3. Contradictions between sources in your own file list — flag them with the token `CONFLICT DETECTED: <file A> says X, <file B> says Y`.
4. Gaps — facts the task seems to need that your files do not cover. Flag as `GAP: <what is missing>`.

## Output format
Write to .mz/task/<TASK_NAME>/extract_<LENS_NAME>.md with sections:
- ## Summary (3-sentence overview of what this lens found)
- ## Extracts (numbered list: fact, source file:line, confidence)
- ## Conflicts (from the CONFLICT DETECTED tokens, or "none")
- ## Gaps (from the GAP tokens, or "none")
- ## Files read (plain list of paths actually opened)
End your response with a final line: STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
```

**Why the ban is absolute**. The "Read ONLY the listed files" line has no escape clause. A prior draft allowed "unless a listed file references another file essential to understanding it" — that clause is banned because it lets the agent follow import chains indefinitely and detonates the context budget. If a referenced file is actually needed, Phase 1.3 should have included it; if Phase 1.3 missed it, the agent reports it as a `GAP` and the user adds it at the next decomposition pass.

### Per-lens customizations

The five structural default lenses each have characteristic inputs and extract priorities. When you fill the template for one of these lenses, replace `<LENS_NAME>` with the lens key (uppercase or lowercase is fine — the extract filename uses the key verbatim) and consult the corresponding paragraph below to decide which extracts to favor.

**research** — The file list is drawn from `.mz/research/*.md` deep-research reports. These are long, externally-sourced, and usually several weeks old. Favor extracts that capture verdicts, confidence levels, source URLs (leave them as citations — do not re-fetch), and the explicit "Decision" or "Recommendation" sections of each report. Ignore background framing and restatements of the prompt. Flag any claim whose cited source has a publication date older than one year as `GAP: needs fresher source` so the gap-fill phase can re-verify it if approved.

**tasks** — The file list is `.mz/task/<selected>/` artifacts — typically `plan.md`, `research.md`, `state.md`, and review files. These are the pipeline's working memory. Favor extracts that capture chosen approaches, explicitly rejected alternatives (with reasons), blocking risks, and any `STATUS:` or phase checkpoints. Cross-check `state.md` status against the plan: if `state.md` says `completed` but `plan.md` describes work that never appears in any `reports/` file, flag that mismatch as a `CONFLICT DETECTED`.

**reports_reviews** — The file list merges `.mz/reports/*.md` with `.mz/reviews/*.md`. Reports are the finished outputs of prior runs; reviews are critique artifacts produced against them. Favor extracts that capture final verdicts, acceptance criteria, and any review-surfaced defects that were or were not addressed. When a review file critiques a specific report, quote the critique verbatim alongside the report's relevant claim — that pairing is often the single most valuable piece of cross-reference evidence the synthesis step will use.

**codebase** — The file list is source files narrowed by the `scope:` parameter if set, otherwise by task-text filename hints from Phase 1.2. Favor extracts that capture concrete function signatures, module boundaries, invariant-bearing constants, and any `TODO` / `FIXME` / `HACK` markers that are relevant to the task. Quote short excerpts with `file:line` citations rather than long copy-pastes — the 300-line output budget is easy to blow here. When the codebase contradicts what the `research` or `tasks` lens says on disk, that is the most load-bearing `CONFLICT DETECTED` the orchestrator will receive; flag it clearly.

**git_history** — The file list is a bounded slice of `git log --oneline` output plus any specific commits the task text references by hash or message. Favor extracts that capture the chronology: who changed what, when, and why (commit messages are first-class extracts here — quote them). If the task is asking "what did we try", the git_history lens is the primary source for the answer. Do NOT run `git show` on every commit; only pull full diffs for commits whose messages the task explicitly names. If the `git_history` bucket was marked unavailable in Phase 1.1, the orchestrator did not dispatch this lens and this paragraph does not apply.

______________________________________________________________________

## Phase 2.3: Collect extracts

**Goal**: Read each returned extract, enforce the four-status protocol, and advance to synthesis.

1. **Read each extract file**. For every lens dispatched in Phase 2.1, open `.mz/task/<task_name>/extract_<lens>.md`. If the file does not exist, see Error Handling below.
1. **Check the final `STATUS:` line** of each extract. The agent is required to end its output with one of four exact tokens:
   - **`DONE`** — Accept the extract as-is. Log the path and lens name in `state.md`. Proceed.
   - **`DONE_WITH_CONCERNS`** — Accept the extract, but also parse any concerns the agent listed and log them in `state.md` under `lens_concerns.<lens>` so Phase 3 can surface them. The extract is still usable.
   - **`NEEDS_CONTEXT`** — The agent is asking for more files. Read the agent's context request, extend that lens's file list by the requested items (only if they actually exist on disk), and re-dispatch **once** with the augmented list. If the second dispatch also returns `NEEDS_CONTEXT`, stop auto-retrying and escalate via `AskUserQuestion` with the agent's two context requests attached. Do not silently loop.
   - **`BLOCKED`** — The agent cannot proceed at all (missing files, permission errors, corrupted input). Never auto-retry a `BLOCKED` status — escalate immediately via `AskUserQuestion` so the user can decide whether to fix the blocker, drop that lens, or abort.
1. **Update `state.md`** after all extracts are processed. Record:
   - `lenses_returned: <N>` — how many extracts came back in any of the four statuses.
   - `extract_paths:` — the list of accepted extract file paths.
   - `lens_concerns:` — any `DONE_WITH_CONCERNS` details, keyed by lens.
   - `blocked_lenses:` — any lens that ended in `BLOCKED` (empty list if none).
   - `needs_context_retries:` — any lens that required a second dispatch (and whether the second dispatch succeeded).
1. **Transition to Phase 3**. Once every lens has either been accepted (`DONE` / `DONE_WITH_CONCERNS`) or escalated, read `phases/synthesis.md` and proceed to Phase 3. Do not attempt to synthesize partial extracts while lenses are still escalated — wait for user input from the escalation first.

______________________________________________________________________

## Phase 4: Web Gap-Fill (conditional)

**Goal**: Fill residual gaps from Phase 3 with a single, bounded wave of web researchers — but only if Phase 3.5 was explicitly approved.

**Entry condition**: Phase 3 produced a non-empty residual gap list AND the Phase 3.5 gate returned approval from the user. If either condition fails, skip this entire section and return control to `phases/synthesis.md §Phase 5` so the synthesis can finish with any remaining gaps marked unresolved.

**Wave cap**: `MAX_GAP_FILL_WAVES = 1`. Exactly one parallel wave. Do not iterate. If the single wave leaves some gaps unresolved, report them as unresolved in the final report — do not dispatch a second wave under any circumstances. The cap exists because web research surfaces new sub-gaps, and without a hard cap the pipeline loops forever.

### 4.1 Dispatch per-gap researchers

1. **Gap intake**. Read the residual gap list that `phases/synthesis.md §Phase 3.4` wrote to `.mz/task/<task_name>/synthesis.md`. Only gaps the user explicitly approved in Phase 3.5 are eligible — any that were dropped or merged by user feedback take effect here, not in the synthesis file.
1. **Cap to MAX_LENSES**. If more than `MAX_LENSES = 6` gaps remain after Phase 3.5, merge the two smallest-scope gaps (shortest gap text, narrowest subject) into one combined gap until the total is ≤6. Record each merge in `state.md` under `gapfill_merges` so the final report can credit the correct source.
1. **Dispatch in a single message**. One `Agent` call per gap, all parallel in a single message. Each dispatch targets the `pipeline-web-researcher` agent (not `pipeline-researcher`) at **model: opus**. Opus is the right choice because web gap-fill is an unbounded synthesis task: the agent must hunt primary sources, weigh conflicting documentation, and detect vendor-spec drift — all work that rewards the stronger model.

### 4.2 Per-gap dispatch prompt template

```
You are filling a single gap for a /combine synthesis run.

## Task (parent)
<TASK_TEXT>

## Gap
<GAP_TEXT>

## Context from local sources
<1-3 sentence quote from the synthesis that surfaced the gap>

## Instructions
1. Use WebSearch and WebFetch following your normal source-hierarchy discipline (official docs > vendor blog > MDN/web.dev > wiki > peer-reviewed papers). Banned: Stack Overflow, AI-generated summaries, undated blogs.
2. Target this single gap only. Do not expand scope.
3. Emit STACK DETECTED / CONFLICT DETECTED / UNVERIFIED tokens per your agent rules.
4. Output budget: <=150 lines.

## Output format
Write to .mz/task/<TASK_NAME>/gapfill_<GAP_ID>.md with sections:
- ## Gap (restated)
- ## Answer (or UNVERIFIED)
- ## Sources (primary sources only, cited with URL and publication date)
- ## Confidence (high/medium/low + one-line reason)
End your response with a final line: STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
```

The `STACK DETECTED` / `CONFLICT DETECTED` / `UNVERIFIED` tokens are contracts defined in the `pipeline-web-researcher` agent rules at `plugins/mz-dev-pipe/agents/pipeline-web-researcher.md`. Do not restate those rules in this prompt — the agent already enforces them. The "per your agent rules" phrasing is deliberate compression (Rule 9).

### 4.3 Collect gap-fills

1. **Read each `gapfill_<GAP_ID>.md`** produced by the wave. Apply the same four-status protocol as Phase 2.3:
   - **`DONE`** / **`DONE_WITH_CONCERNS`** — Accept. The answer (or `UNVERIFIED` marker) is usable.
   - **`NEEDS_CONTEXT`** — A web researcher that needs context from local sources is a design error; escalate via `AskUserQuestion` rather than re-dispatching, because the web researcher does not have the local file list and should not be asked to read it.
   - **`BLOCKED`** — Never auto-retry; escalate, or if the blocker is "no network", see Error Handling below.
1. **Merge by reference, not by copy**. Do NOT inline the full gap-fill text into the synthesis or the final report. Cite only the one-line answer, the primary source URL, and the confidence. The full `gapfill_<GAP_ID>.md` stays on disk as the audit trail. This matters because gap-fills are often long and citation-heavy; copying them in would blow the report length and make it unreadable.
1. **Update `state.md`**:
   - `gapfill_wave: complete`
   - `gaps_resolved: <N>` — gaps whose gap-fill returned `DONE` / `DONE_WITH_CONCERNS` with a non-`UNVERIFIED` answer.
   - `gaps_unresolved: <N>` — gaps that came back `UNVERIFIED`, `BLOCKED`, or were dropped by the wave cap / merging.
   - `gapfill_merges:` — any merges performed in 4.1 step 2.
1. **Transition**. Return to `phases/synthesis.md §Phase 5` (task-adaptive report generation). The synthesis step reads the collected gap-fill answers and surfaces them in the report's `## Gaps` meta-section, split into "Resolved via web gap-fill" and "Unresolved".

______________________________________________________________________

## Error Handling for this phase

- **Lens agent's extract file missing** — If `.mz/task/<task_name>/extract_<lens>.md` does not exist after the agent returns, retry the dispatch for that lens exactly once with the same prompt. If the second dispatch also fails to produce the file, mark the lens as `BLOCKED` in `state.md` and escalate via `AskUserQuestion` so the user can choose to drop that lens or abort the run. Do not fabricate an empty extract.
- **All lens agents return `BLOCKED`** — If every dispatched lens comes back `BLOCKED`, do not attempt Phase 4 gap-fill. There is nothing to fill against. Update `state.md` to `status: aborted_all_blocked`, escalate to the user with the individual block reasons, and stop. Writing a final report over zero extracts would be misleading.
- **Web `pipeline-web-researcher` agent unavailable (no network)** — If the Phase 4 dispatches fail because WebSearch/WebFetch return network errors for every gap, do not retry. Mark all approved gaps as `gaps_unresolved` in `state.md` with the reason `no_network`, still proceed to `phases/synthesis.md §Phase 5`, and let the final report's `## Gaps` section list them under "Unresolved". The /combine output is still useful — the user explicitly approved gap-fill knowing it might fail.
- **Second `NEEDS_CONTEXT` on the same lens** — Per Phase 2.3, do not auto-retry beyond the first re-dispatch. Escalate via `AskUserQuestion` with both context requests attached so the user can decide whether the Phase 1.3 decomposition was wrong (add the missing files, re-run Phase 1) or the lens is unworkable (drop it).
- **Gap list shrinks to zero between Phase 3.5 approval and Phase 4 dispatch** — If the residual gap list is somehow empty by the time Phase 4 starts (e.g., re-classification during state update dropped them all), skip Phase 4 entirely, record `gapfill_wave: skipped_empty` in `state.md`, and return to `phases/synthesis.md §Phase 5`. Do not dispatch zero agents.
