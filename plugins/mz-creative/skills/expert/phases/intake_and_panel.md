# Phase 1: Intake + Optional Research + Panel Selection

Full detail for intake, the optional codebase scan (when `scope:` is set), panel selection, and the approval gate.

## Goal

Produce `intake.md`, optionally `research.md`, and a user-approved `panel.md` listing the 5 selected experts. No expert is dispatched for critique until the panel is explicitly approved.

## Inputs

From Phase 0:

- Brief text
- Optional modifiers: `scope:branch|global|working`, `@doc:<path>`
- Task name and working directory

## Step 1.1 — Write `intake.md`

**This orchestrator** writes `intake.md` directly. Do not delegate intake authoring — the orchestrator already has the brief in its context.

Template:

```markdown
# Intake

## Brief
<verbatim brief text>

## Modifiers
- scope: <branch|global|working|none>
- doc refs: <list of @doc: paths, or "none">

## Doc summaries (if @doc: refs present)
### <path>
<2-3 sentence summary of the doc contents — orchestrator reads each referenced file and summarises>

## Detected framing
- Problem type: <technical | product | business | design | strategic | mixed>
- Decision scope: <architecture | feature | platform | process | branding | policy | other>
- Urgency signal: <none | implied | explicit>
```

The "Detected framing" section biases panel selection. Be specific but brief.

## Step 1.2 — Optional codebase scan (when `scope:` is set)

If the user provided `scope:`, dispatch `expert-researcher` (model: **sonnet**) with this prompt:

```
You are researching codebase context for an expert panel review.

## Brief
<verbatim brief>

## Scope
<branch|global|working>

## Task Directory
.mz/task/<task_name>/

## Your Job
Scan the codebase within the declared scope and write research.md. Capture:
1. Stack detection (languages, frameworks, major libraries) — emit STACK DETECTED: lines
2. Relevant modules/directories that the brief's idea would touch
3. Existing patterns, conventions, naming, test infrastructure
4. Prior art: has anything similar been attempted in the repo? Any dead branches, old spike code, relevant commits?
5. Constraints visible from code: version pinning, protocol assumptions, public interfaces that must remain stable

Emit disclosure tokens where applicable:
- STACK DETECTED: <stack + version>
- CONFLICT DETECTED: <when codebase contradicts the brief's assumptions>
- UNVERIFIED: <when a claim cannot be grounded in code>

Focus on what an expert panel would need to critique the idea realistically — not an implementation plan. Do NOT propose solutions.

Terminal status line: STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
```

### 1.2.1 Handle researcher status

- `DONE` — proceed to panel selection.
- `DONE_WITH_CONCERNS` — log concerns to `state.md` and proceed.
- `NEEDS_CONTEXT` — escalate specific question via `AskUserQuestion`, then re-dispatch with added context.
- `BLOCKED` — escalate immediately. Offer: clarify the brief, proceed without scan (downgrade to pure idea analysis), abort.

### 1.2.2 Verify `research.md`

```bash
test -s .mz/task/<task_name>/research.md
```

If missing or empty, retry once with explicit instruction. If still missing, escalate.

## Step 1.3 — Panel selection

**This orchestrator** (not a subagent) selects the panel. The orchestrator already has the brief + research in context, so delegating panel selection would just burn tokens.

### Selection heuristic

From the 16-lens pool, pick **5** lenses that:

1. **Cover the primary lens** the brief demands (e.g., a tech idea must include `lens-cto` or `lens-engineer`; an SEO/content idea must include `lens-seo`).
1. **Cover 1–2 adjacent lenses** (e.g., a tech idea should also include `lens-security` or `lens-product` for adjacent risk).
1. **Include at least one "productive tension" lens** — a perspective that will likely challenge the dominant view. For a tech idea, add `lens-philosopher` (ethics) or `lens-historian` (precedent). For a business idea, add `lens-scientist` (evidence) or `lens-data` (measurement).
1. **Mix styles** — include at least one generative/creative-family lens (e.g. `lens-artist`, `lens-storyteller`, `lens-futurist`) alongside operational lenses. A balanced panel surfaces more failure modes than an all-operational or all-creative panel.
1. **Never duplicate a lens** — e.g., don't pick both `lens-engineer` and `lens-cto` on the same panel; their lenses overlap too much.

### Write `panel.md`

```markdown
# Panel

## Topic
<the brief, one paragraph>

## Selected (5)

### <agent 1 name>
- **Lens**: <one-line lens from the SKILL.md roster>
- **Why this panel**: <one sentence explaining why this lens matters for the brief>

[repeat for all 5]

## Not selected (11)
<comma-separated list of the 11 agents not picked, no justification needed>

## Selection rationale
<2-3 sentences on overall panel balance — what tension was introduced, which lens is dominant, which lens is adversarial>
```

Update state: `Phase: 1`, `PhaseName: panel_selected`.

## Step 1.4 — User approval gate (Phase 1.5)

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `.mz/task/<task_name>/panel.md` and capture the full contents into context.

**Surface 1 — emit the plan message.** Output the full verbatim contents of `.mz/task/<task_name>/panel.md` as a normal markdown chat message. Emit the full verbatim contents — do not substitute a path, summary, or placeholder. Structure:

```
## Panel ready for review — expert

<verbatim contents of .mz/task/<task_name>/panel.md>

---
**Approve** → begin 3 rounds of expert critique  ·  **Reject** → cancel task, no rounds will run  ·  reply with feedback to revise
```

**Surface 2 — call AskUserQuestion.** After the plan message, call AskUserQuestion. The question must NOT re-embed the panel — it lives in the plan message above.

- question: `The panel above is ready for review.`
- options: **Approve** — begin 3 rounds of expert critique · **Reject** — cancel task, no rounds will run

### Response handling

- **Approve** → update state to `panel_approved`, proceed to Phase 2.
- **Reject** → update state to `aborted_by_user`. Stop. Do not run rounds.
- **Any other reply (feedback)** → apply the swap to `panel.md`, return to Surface 1, re-read `panel.md`, and re-emit the entire plan message from scratch with the full new contents. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

### Swap rules

- The user can swap up to all 5 members; the orchestrator may push back in the presentation block if a swap breaks the "at least 1 from each class" rule, but must still honor an explicit user choice.
- If the user removes the only technical lens from a technical brief, warn in the next presentation block but obey the user.

## Step 1.5 — Verify and hand off

Before leaving Phase 1, verify:

- `intake.md` exists and is non-empty
- `research.md` exists (if `scope:` was set)
- `panel.md` exists and lists exactly 5 selected agents
- `state.md` shows `Status: running`, `Phase: 1.5`, `PhaseName: panel_approved`

Proceed to Phase 2 (Round Loop).

## Notes

- Phase 1 is not gated against the user before panel-selection (the researcher is read-only). The gate sits at Phase 1.5.
- Image references (`@image:`) are intentionally unsupported — `/expert` is text-only by design. If the user provides one, note in intake.md and continue.
- Panel selection is orchestrator-owned on purpose: delegating it to an agent would require loading the brief + research into a second context and re-reading the agent roster. Inline selection saves 1 agent call per run.
