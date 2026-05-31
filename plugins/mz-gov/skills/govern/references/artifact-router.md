# Artifact Router — Gate A / Gate B Decision Logic

The `gov-router` agent reads this file to answer two questions in order:

1. **Gate A — does this change need a governance artifact at all?**
1. **Gate B — if yes, which one (ADR / RFD / design doc)?**

Work the gates top-to-bottom. Stop at the first definite answer. The router is read-only — its only output is the routing file described at the end.

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

1. Sets `artifact: none`.
1. Records which side failed in the rationale — e.g. "substantial but unambiguous (single sensible approach)" or "behavior-preserving refactor — exempt".
1. Writes `routing.md` with `weight: none` and `status-vocab: n/a`.

The orchestrator stops the governance flow after this — no discussion panel, no sign-off gate, just the one-line exemption note plus the run's provenance block.

> When in doubt, lean toward requiring the artifact for genuinely substantial changes — the exemption note is cheap, an undocumented one-way door is not. But do not manufacture ambiguity that isn't there.

______________________________________________________________________

## Gate B — Which artifact?

Reached only when Gate A is true. Pick exactly one. The distinction is **where the decision stands**, not how big it is.

| Artifact       | Use when                                                                                          | One-line test                                    | Template                                                            |
| -------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------- |
| **ADR**        | The decision **is already made** — you are recording *why*, for future readers.                   | "We chose X over Y. Here's the reasoning."       | `adr-nygard-template.md` (default) or `adr-madr-template.md` (rich) |
| **RFD**        | The decision is **still open** — you need to structure debate and reach consensus first.          | "Should we do X or Y? Let's discuss."            | `rfd-template.md`                                                   |
| **Design doc** | The decision is **made** and you now need to **specify the build** in enough detail to implement. | "We're doing X — here's exactly how it's built." | `design-doc-template.md`                                            |

### Boundary clarifications

- **ADR vs design doc** — both describe a decision that's been made. Reach for an **ADR** when the artifact is the *record of the choice and its trade-offs* (small, focused, one decision). Reach for a **design doc** when the artifact must also *carry the implementation plan* (component layout, data flow, cross-cutting concerns). An ADR answers "why this"; a design doc answers "how we build this".
- **ADR vs RFD** — an ADR is written *after* the choice is settled; an RFD exists precisely *because the choice isn't settled* and needs discussion. If you're still weighing options with no front-runner, that's an RFD. The moment it converges it can graduate into an ADR or design doc.
- **RFD vs design doc** — an RFD is a debate container with an open outcome; a design doc presumes the outcome and details construction. Don't write a design doc for something the team hasn't agreed to do yet.

### Nygard vs MADR (within ADR)

- Default to **Nygard** — minimal four sections, fast to write.
- Use **MADR** when the caller passed `rich`, **or** when the decision weighs **≥3 considered options** that each deserve explicit pros/cons. MADR's Considered Options + Pros-and-Cons sections exist for exactly that case.

### Explicit override

If the caller passed `artifact:adr|rfd|design`, honor it. If the override contradicts what the gates would pick, emit a `Nit:` note recording the disagreement (e.g. "router would pick RFD — decision looks open — but proceeding with requested ADR"), then proceed with the caller's choice. The user's explicit instruction wins; the note preserves the disagreement for the record.

______________________________________________________________________

## Weight label

The router emits a `weight` that scales the downstream discussion panel. Compute it after Gate B:

| Weight  | Condition                                                                      | Downstream effect                                                                  |
| ------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| `heavy` | artifact is **RFD** OR **design doc** OR an **ADR with ≥3 considered options** | Full opus critic panel (alternatives / reversibility / blast-radius / assumptions) |
| `light` | a **simple ADR** (fewer than 3 options)                                        | Single quick critic, one pass                                                      |
| `none`  | Gate A returned `none`                                                         | No discussion phase at all                                                         |

Heavy means the decision space is wide enough that parallel adversarial lenses earn their cost. Light means one focused pass is enough. Don't inflate weight to look thorough — a two-option ADR is `light`.

______________________________________________________________________

## Output contract

The router writes `.mz/task/<task_name>/routing.md`. Exactly these fields:

```markdown
# Routing

- **artifact**: <adr-nygard | adr-madr | rfd | design-doc | none>
- **gate-that-fired**: <Gate A exempt | Gate B>
- **weight**: <heavy | light | none>
- **status-vocab**: <pointer to the status set in status-vocabularies.md, or n/a>
- **rationale**: <one paragraph — why this artifact and weight, citing the
  substantial/ambiguous signals (or the exemption reason) in plain language>
```

Field notes:

- **gate-that-fired** records whether the run stopped at Gate A (exemption) or proceeded through Gate B (selection). It makes the routing auditable after the fact.
- **status-vocab** points at the right block in `status-vocabularies.md` — ADR open-ended, RFD fixed 6-state, or design-doc set. `n/a` when artifact is `none`.
- **rationale** is one paragraph, not a list. State the deciding signals concretely (which substantial signal, why it's ambiguous, why this weight) so a reviewer can sanity-check the routing without re-deriving it.

The router does not draft the artifact and does not write to `docs/`. Selection only.
