# Artifact Router — Gate A / Gate B Decision Logic

The `gov-router` agent reads this file to answer two questions in order:

1. **Gate A — does this change need a governance artifact at all?**
1. **Gate B — if yes, which one (ADR / RFD / design doc)?**

Work the gates top-to-bottom. Stop at the first definite answer. The router modifies nothing — its only output is the routing file described at the end.

## Contents

- Gate A — Is an artifact required?
- Gate B — Which artifact?
- Weight label
- Output contract

______________________________________________________________________

## Gate A — Is an artifact required?

An artifact is required only when the change is **substantial AND ambiguous**. Both must hold. This is the Rust substantial-vs-exempt boundary combined with the Google "is the solution ambiguous?" cost/benefit test — neither alone is sufficient.

```
required = substantial(change) AND ambiguous(change)
```

If either side is false, the answer is `ARTIFACT: none` — take the exemption path below.

### Substantial signals (any one makes it substantial)

A change is substantial when it does any of these:

- Changes externally observable **behavior**
- Touches a **public API** / contract / wire format that callers depend on
- Changes a **data schema**, migration, or persisted format
- Adds, removes, or swaps a **dependency**
- Moves a **module boundary** or changes how components are wired
- Alters the **security posture** (authn/authz, secrets handling, trust boundary, exposure surface)
- Is **hard to reverse** — a one-way door (data loss risk, externally published contract, expensive-to-unwind migration)

### Ambiguous signals (the decision is genuinely open)

Ambiguous means there is real design uncertainty — more than one reasonable approach a competent engineer could defend:

- **Problem complexity** — the requirements themselves are unclear or contested
- **Solution complexity** — the path is non-obvious; reasonable people would pick differently
- There are **≥2 defensible options** with different trade-offs

If there is exactly one sensible way to do it, it is **not** ambiguous even if it is substantial — record nothing, just build.

### Exempt list (these short-circuit Gate A to `none`)

Even if something looks big, it is exempt when it is purely:

- A **behavior-preserving refactor** — changing shape without changing meaning
- An **objective improvement** along a numeric axis — warning removal, speedup, broader platform coverage, dependency bump with no API change
- **Dev-invisible / tool-internal** — visible only to developers of the tool, not to users or downstream callers
- A throwaway **prototype / spike** where the overhead is not worth it (Google: for rapid iteration the doc cost usually loses)

### Exemption path (`ARTIFACT: none`)

When Gate A returns false, the router does **not** select a template. Instead it:

1. Sets `ARTIFACT: none`.
1. Records which side failed in the rationale — e.g. "substantial but unambiguous (single sensible approach)" or "behavior-preserving refactor — exempt".
1. Writes `routing.md` with `WEIGHT`, `STAGE` and `STATUS_VOCAB` all `n/a`.

The orchestrator stops the governance flow after this — no interview, no discussion panel, no sign-off gate, just the one-line exemption note plus the run's provenance block.

> When in doubt, lean toward requiring the artifact for genuinely substantial changes — the exemption note is cheap, an undocumented one-way door is not. But do not manufacture ambiguity that isn't there.

______________________________________________________________________

## Gate B — Which artifact?

Reached only when Gate A is true. Pick exactly one. The distinction is **where the decision will stand when this govern run ends**, not how big it is. Govern critiques the options and ends at a human sign-off, so a choice the user asks govern to help make is a *made* decision by the time it is recorded.

### The stage decides

On the Phase 2 dispatch the brief carries the user's `Stage`. Map it directly:

| Stage     | The user said                              | Artifact                                            |
| --------- | ------------------------------------------ | --------------------------------------------------- |
| `choose`  | "Help me choose"; the panel weighs, I sign | **ADR**: Nygard, or MADR with three or more options |
| `decided` | "Already decided, record why"              | **ADR**: Nygard, or MADR with three or more options |
| `debate`  | "The team debates it first; outcome open"  | **RFD**                                             |
| `build`   | "Decided, I need the build spec"           | **Design doc**                                      |

With no `Stage` (the Phase 1 screen, or an assumption in the brief), infer it from the text: a question such as "should we X or Y" or "decide between A and B" is `choose`, so an ADR. Pick an RFD only when the text asks for team discussion, a proposal or an RFC, and a design doc only when it asks how to build something already chosen.

| Artifact       | Use when                                                                                           | One-line test                                    | Template                                                            |
| -------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------- |
| **ADR**        | The decision **is made**, before or during this run — you are recording *why*, for future readers. | "We chose X over Y. Here's the reasoning."       | `adr-nygard-template.md` (default) or `adr-madr-template.md` (rich) |
| **RFD**        | The decision **stays open** after this run — the team must debate and reach consensus first.       | "Team, should we do X or Y? Let's discuss."      | `rfd-template.md`                                                   |
| **Design doc** | The decision is **made** and you now need to **specify the build** in enough detail to implement.  | "We're doing X — here's exactly how it's built." | `design-doc-template.md`                                            |

### Boundary clarifications

- **ADR vs design doc** — both describe a decision that's been made. Reach for an **ADR** when the artifact is the *record of the choice and its trade-offs* (small, focused, one decision). Reach for a **design doc** when the artifact must also *carry the implementation plan* (component layout, data flow, cross-cutting concerns). An ADR answers "why this"; a design doc answers "how we build this".
- **ADR vs RFD** — an ADR records a settled choice; an RFD exists precisely *because the choice must stay open* for others to debate. Weighing options with no front-runner is not enough for an RFD: govern's panel and sign-off settle that, and the result is an ADR. Pick an RFD only when someone other than the person signing must take part in the decision. The moment it converges it can graduate into an ADR or design doc.
- **RFD vs design doc** — an RFD is a debate container with an open outcome; a design doc presumes the outcome and details construction. Don't write a design doc for something the team hasn't agreed to do yet.

### Nygard vs MADR (within ADR)

- Default to **Nygard** — minimal four sections, fast to write.
- Use **MADR** when the caller passed `rich`, **or** when the decision weighs **≥3 considered options** that each deserve explicit pros/cons. MADR's Considered Options + Pros-and-Cons sections exist for exactly that case.

### Explicit override

If the caller passed `artifact:adr|rfd|design`, honor it. If the override contradicts what the gates would pick, emit a `Nit:` note recording the disagreement (e.g. "router would pick RFD — decision looks open — but proceeding with requested ADR"), then proceed with the caller's choice. The user's explicit instruction wins; the note preserves the disagreement for the record.

______________________________________________________________________

## Weight label

The router emits a `weight` that scales the downstream discussion panel. Compute it after Gate B:

| Weight  | Condition                                                                                                                                       | Downstream effect                                                                  |
| ------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `heavy` | artifact is **RFD** OR **design doc** OR an **ADR with ≥3 considered options** OR an **ADR whose choice is made in this run** (`Stage: choose`) | Full opus critic panel (alternatives / reversibility / blast-radius / assumptions) |
| `light` | an **ADR recording a decision already made** (`Stage: decided`) with fewer than 3 options                                                       | Single quick critic, one pass                                                      |
| `n/a`   | Gate A returned `none`                                                                                                                          | No discussion phase at all                                                         |

Heavy means the decision space is wide enough, or the choice still open enough, that parallel adversarial lenses earn their cost: when govern is helping the user choose, the panel *is* the help. Light means one focused pass is enough. Don't inflate weight to look thorough — recording a two-option decision already made is `light`.

______________________________________________________________________

## Output contract

The router writes `.mz/task/<task_name>/routing.md` in exactly this shape:

```markdown
# Routing Decision — <short change summary>

ARTIFACT: none | adr-nygard | adr-madr | rfd | design
GATE_FIRED: A-exempt | A-required → B-<artifact>
STAGE: choose | decided | debate | build | inferred-<stage>
WEIGHT: light | heavy | n/a
STATUS_VOCAB: <the status set this artifact uses, named from status-vocabularies.md; n/a when ARTIFACT: none>
OVERRIDE: none | honored (<requested> over inferred <inferred>)

## Rationale
<one paragraph: which substantial/ambiguous signals fired (or the exemption reason), why this artifact and this weight>

<Nit: ... — only when the override contradicts the inferred routing>
```

Field notes:

- **GATE_FIRED** records whether the run stopped at Gate A (exemption) or went through Gate B, which makes the routing auditable after the fact.
- **STAGE** is the brief's answer, or `inferred-<stage>` when the router read it from the text.
- **STATUS_VOCAB** names the right block in `status-vocabularies.md`: ADR open-ended, RFD fixed six-state, or the design-doc set.
- For `ARTIFACT: none`, `STAGE`, `WEIGHT` and `STATUS_VOCAB` are `n/a`.

The router does not draft the artifact and does not write to `docs/`. Selection only.
