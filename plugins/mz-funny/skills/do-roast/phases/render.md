# Phases 5-6: Persona Dispatch + Report Assembly

Detail for persona agent dispatch, report assembly, inline teaser, and state finalization. Loaded on demand at Phase 5 start via `Read phases/render.md`.

**Preconditions** (enforced before entering this file):

- `TASK_DIR<task_name>/dossier.md` exists and is non-empty.
- State `Phase: dossier_complete` with populated `finding_counts`.
- `persona` field in state matches an entry in `PERSONA_ALLOWLIST`.

If any precondition fails, halt and emit `STATUS: BLOCKED` with the missing artifact name — never enter Phase 5 on incomplete analysis.

______________________________________________________________________

## Phase 5: Persona Dispatch

### 5.1 Load dossier into orchestrator context

Read the full dossier from `TASK_DIR<task_name>/dossier.md` using the `Read` tool. The entire file body is required verbatim for the dispatch prompt — do not summarize, do not paraphrase, do not pass by reference.

Capture:

- `dossier_body` — the full file contents (string).
- `finding_count` — count of `## Finding ` headings in the dossier (integer).
- `resolved_target` — one-line summary from the dossier `**Target**:` line.

If `finding_count == 0`, halt with `STATUS: BLOCKED` and the message "Dossier has zero findings — nothing to roast. Re-run analysis with a broader target." Do not invent work for the persona.

### 5.2 Compute and validate the agent name

`agent_name = "roast-" + persona` (persona is already lowercased during Phase 0).

Validate:

1. `persona` must appear in `PERSONA_ALLOWLIST` (defensive re-check — Phase 0 already validated, but state may have been edited).
1. The agent file `plugins/mz-funny/agents/<agent_name>.md` should be registered. If the `Agent` tool reports "unknown subagent_type" at dispatch time, halt with `STATUS: BLOCKED` and the message "Persona agent `<agent_name>` is not registered. Check `plugins/mz-funny/agents/`."

### 5.3 Construct the dispatch prompt

The dispatch prompt is a **task-specific context packet only** (Rule 9). The persona agent already has its Evidence Contract, Safety Floor, and Voice Reference in its system prompt — do NOT repeat those instructions here.

Use this exact template, substituting the bracketed fields:

```
Target: <resolved_target>
Task: Roast the following findings in your voice. Every line must cite at least one Finding by number. You may embellish tone, rhythm, and metaphor — you may NOT invent findings, file paths, or bugs that are not in the dossier below.

## Dossier (inlined — do not re-read, do not trust your memory)

<dossier_body>

## Output format

Return a single markdown block with:
- An opening line in character addressing the user.
- One roast paragraph per Finding (in severity order: Critical first, then Nit, Optional, FYI), each paragraph citing the finding inline as `(Finding N)`.
- A closing line in character.

Be concise. Aim for 3-6 sentences per finding. Output tokens are expensive.

End with a terminal STATUS line: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED.
```

**Critical substitution rule**: `<dossier_body>` must be replaced with the **complete verbatim contents** of `dossier.md`. This is not a path. This is not a summary. It is the full file body inlined as a context packet, per research.md §Evidence enforcement layer 3 and the brainstorm `ideation.md:9-25` context-packet pattern. Inlining is what prevents the "forgot to read" fabrication mode.

### 5.4 Dispatch the persona agent

Single-agent, single-message dispatch using the `Agent` tool:

- `subagent_type`: `<agent_name>` (e.g. `roast-pirate`).
- `description`: `Roast ${finding_count} findings as ${persona}` (one short line for the dispatch log).
- `prompt`: the full dispatch prompt from 5.3.

Panel mode (all 7 personas in parallel) is deferred to v1.1 — Rule 13 parallel fan-out does not apply in v1 because there is exactly one agent per invocation.

### 5.5 Collect the response

Read the agent's full response text. If the body is wrapped in a leading triple-backtick fence (with or without a language hint like `markdown`) and a trailing triple-backtick fence, strip both fences. Capture:

- `roast_raw` — the stripped markdown body.
- `agent_status` — the terminal `STATUS:` line reported by the agent.

### 5.6 Empty-response handling

Define "empty" as: `roast_raw` is whitespace-only, OR fewer than 2 non-empty lines, OR zero `(Finding ` citations.

If empty on the first attempt:

1. Log `Phase 5 retry — persona agent returned empty, re-dispatching with clarified prompt` to the visible output.
1. Re-dispatch the same `agent_name` with a prompt prefixed by:
   ```
   The previous attempt returned empty. Re-run, producing at least one line per finding.
   ```
   followed by the original dispatch prompt body from 5.3 unchanged.
1. Collect the second response.

If the second response is also empty:

1. Build a **skeleton roast** from the dossier. For each `## Finding N` heading, extract the `**Why it's roastable**:` line and emit:
   ```
   (Finding N) <Why it's roastable line, unchanged>
   ```
1. Wrap the list in a short in-character header and footer derived from the persona's name only (no improvisation beyond "<persona> reporting. <list>. <persona> out."). This is an emergency fallback — it is not a creative artifact.
1. Set a flag `persona_fallback = true`. The final state will escalate to `DONE_WITH_CONCERNS`.
1. Log `Phase 5 fallback — persona agent returned empty twice, skeleton roast built from dossier Why-it's-roastable fields` to visible output.

### 5.7 Persist raw persona output

Write `roast_raw` (or the skeleton) to `TASK_DIR<task_name>/roast_raw.md` using the `Write` tool. This file is the evidence trail for Phase 6 assembly and for any post-mortem debugging of fabrication incidents.

Update state:

- `Phase: persona_rendered`
- `persona_fallback: <true|false>`
- `persona_retry_count: <0|1|2>`

______________________________________________________________________

## Phase 6: Report Assembly + Teaser + File Write

### 6.1 Compute the report path

Inputs:

- `today` = current date as `YYYY_MM_DD`.
- `persona` = chosen persona, already lowercase.
- `target_slug` = snake_case slug from Phase 0 (`state.md`), max 20 chars, already sanitized (alphanumeric + underscore).

Base path:

```
REPORT_DIR + "roast_" + today + "_" + persona + "_" + target_slug + ".md"
```

### 6.2 Collision handling (Rule 11)

If the base path does not exist, use it. Otherwise, walk the suffix ladder:

1. Try `<base>_v2.md`. If free, use it.
1. Try `<base>_v3.md`. If free, use it.
1. Continue through `_v4` ... `_v10`.
1. If `_v10` is also taken, halt and escalate via `AskUserQuestion`:
   ```
   10 roast report versions already exist for <persona> + <target_slug> today.
   Options: (1) overwrite v10, (2) switch persona or target slug, (3) abort.
   ```
   Do not silently overwrite. Do not invent `_v11`. Wait for user input.

Record the final chosen path as `report_path` (absolute form preferred in state).

### 6.3 Assemble the report body

Re-read `dossier.md` and `roast_raw.md` at assembly time — do not trust any earlier in-memory snapshot (context compaction can silently corrupt it). From the dossier, extract `**Stack detected**:` from the frontmatter, and grep finding bodies for any `UNVERIFIED: <claim>` tokens emitted by Phase 4 (these live inside findings as per-claim downgrades, not in the frontmatter).

Build the report exactly in this shape (substitute bracketed fields):

```markdown
# Roast — <persona> — <target_summary>

**Persona**: <persona>
**Target**: <resolved_target>
**Date**: <YYYY-MM-DD>
**Finding counts**: Critical: <C> / Nit: <N> / Optional: <O> / FYI: <F>

## The Roast

<contents of roast_raw.md>

## Dossier (evidence trail)

<contents of dossier.md>

## Source disclosure

- STACK DETECTED: <value from dossier frontmatter>
- Source hierarchy: static-reading → docs-coherence → web best-practice (tier-1 official docs preferred, see `phases/analyze.md` §4 for the full ladder)
- UNVERIFIED claims: <grep result from dossier finding bodies — list each `UNVERIFIED:` line with its finding number, or "none">

---
*Generated by the `mz-funny` plugin's `/do-roast` skill. Every line is supposed to be evidence-grounded — if you spot fabrication, that's a bug: file it.*
```

`<target_summary>` is a short human-readable form of the resolved target for the H1 heading only (e.g. `src/auth/`, `branch:feature-x`, or `raw text (1000 chars)`). Do not use the full resolved list in the H1 — it is for the `**Target**:` metadata line.

Finding counts come from state `finding_counts` recorded in Phase 4b. If any severity is missing from state, read it back from the dossier by counting `## Finding N — <severity> —` headings per severity.

### 6.4 Write the report file

Use the `Write` tool with `file_path = report_path` and `content = <assembled body>`. Re-read the file immediately after writing to confirm the write succeeded and matches the assembled body — silent write failures would destroy the Phase 6 visible verification later.

If the post-write read does not match the assembled body, halt with `STATUS: BLOCKED` and the message "Report write verification failed at `<report_path>`. Investigate Write tool state before retrying."

### 6.5 Layer-4 soft citation-density check (Nit #8, plan-review)

**Purpose**: early warning against fabrication drift. The persona agent contract requires every line to cite a `(Finding N)`. A roast that barely cites the dossier is a signal that the persona improvised. This check is **non-blocking** — it does not fail the skill, it flags the state file so downstream audit tooling can spot drift.

Procedure:

0. **Initialize `concerns_flag = false`** at the start of this check. Only set it to `true` on the low-density branch below; leave it untouched on the OK branch. Downstream section 6.9 reads this flag to decide between `STATUS: DONE` and `STATUS: DONE_WITH_CONCERNS`, so the default must be explicit.
1. Read the rendered roast body from `roast_raw.md` — this is the persona agent's direct output, NOT the assembled report. Grepping the assembled report would also hit the `## Dossier (evidence trail)` section, and while the dossier headers use `## Finding N —` without a paren (so `(Finding ` would not false-match them today), relying on that is fragile — grep the actual persona output instead.
1. Count occurrences of the literal substring `(Finding ` in `roast_raw.md`. Call this `citation_count`.
1. Compute `threshold = ceil(finding_count / 3)`. Use integer ceiling — for `finding_count = 10`, threshold is `4`; for `finding_count = 1`, threshold is `1`.
1. If `citation_count < threshold`:
   - Log a visible warning: `Layer-4 soft check: citation_count=<N>, threshold=<T>, finding_count=<F> — low citation density, possible fabrication drift.`
   - Append to state:
     ```
     layer4_warning: low citation density — possible fabrication drift
     layer4_citation_count: <citation_count>
     layer4_threshold: <threshold>
     ```
   - Set `concerns_flag = true`.
1. If `citation_count >= threshold`:
   - Log `Layer-4 soft check: citation_count=<N>, threshold=<T> — OK` to visible output.
   - Leave `concerns_flag` at its default `false`.

This check runs **before** the final state update and terminal STATUS line so its verdict can influence whether the skill terminates with `DONE` or `DONE_WITH_CONCERNS`. It never blocks — `BLOCKED` is reserved for structural failures, not citation density.

Reference: research.md §Evidence enforcement layer 4. The plan originally deferred this to v1.1, but plan-review Issue 8 upgraded it to v1.

### 6.6 Build the inline teaser

The teaser is a single paragraph, 3-5 sentences, in the chosen persona's voice, paraphrasing the top 1-3 findings by severity. It is **printed to the user**, NOT written to the report file.

Procedure:

1. Read `roast_raw.md` and pick the first 1-3 `(Finding N)`-citing sentences that correspond to the highest severity in state (Critical if any exist, else the first Nit).
1. Concatenate those sentences into one paragraph.
1. If the concatenation exceeds 5 sentences, keep only the first 5.
1. If it is below 3 sentences, append a short in-character sign-off from the persona's dossier (one sentence — do not generate new voice, only reuse lines already present in `roast_raw.md`).

**Do not paraphrase the persona's voice yourself** — reuse lines the agent already produced. The orchestrator is not a creative actor in this skill; it is a packager.

If `persona_fallback == true` from Phase 5.6, the teaser is replaced with a fixed one-line notice:

```
<persona> went quiet — skeleton roast only. See `<report_path>` for the dossier-derived fallback.
```

### 6.7 Verification block (Rule 4 — visible output)

Print this block to the user verbatim. Every field must be populated; no `TBD` placeholders.

```
=== /do-roast verification ===
Task name: <task_name>
Persona: <persona>
Agent dispatched: roast-<persona>
Target: <resolved_target>
Finding counts: Critical=<C> Nit=<N> Optional=<O> FYI=<F>
Total findings: <finding_count>
Citation count: <citation_count>
Citation threshold: <threshold>
Layer-4 status: <OK | LOW_DENSITY>
Persona retry count: <0|1|2>
Persona fallback: <true|false>
Report path: <report_path>

--- Teaser (persona voice, top findings) ---
<teaser paragraph>
==============================
```

This is the Rule 4 visible-output requirement for the skill — every check above has a printed result, no silent steps.

### 6.8 Final state update

Update `TASK_DIR<task_name>/state.md`:

- `Status: complete`
- `Phase: report_written`
- `report_path: <absolute report_path>`
- `citation_count: <citation_count>`
- `citation_threshold: <threshold>`
- `layer4_warning: <present only if concerns_flag == true>`

Preserve all fields written in earlier phases (do not rewrite the file from scratch — append / update in place).

### 6.9 Terminal STATUS line (Rule 21)

Emit exactly one terminal STATUS line, chosen per the four-status protocol:

- `STATUS: DONE` — all of:
  - persona dispatched successfully on the first attempt,
  - `persona_fallback == false`,
  - `concerns_flag == false` (layer-4 check passed),
  - report written and verified,
  - no user-visible warnings.
- `STATUS: DONE_WITH_CONCERNS` — work complete but at least one of:
  - persona retry fired (`persona_retry_count >= 1`),
  - skeleton fallback was used (`persona_fallback == true`),
  - layer-4 citation density was below threshold (`concerns_flag == true`).
    In this case, list the concerns in a preceding `## Concerns` section so the orchestrator log captures them.
- `STATUS: NEEDS_CONTEXT` — reserved for the case where the dispatch prompt could not be constructed due to missing dossier fields (e.g. `**Target**:` line not found). Include a `## Required Context` section listing exactly which fields were missing.
- `STATUS: BLOCKED` — reserved for unrecoverable failures only: dossier read failed, Write tool verification failed in 6.4, `_v10` collision escalation rejected by the user, or unknown-subagent error at dispatch time. Never retry the same operation after `BLOCKED` — the orchestrator escalates to the user.

The STATUS line is the last line of output emitted by this skill. Nothing follows it.
