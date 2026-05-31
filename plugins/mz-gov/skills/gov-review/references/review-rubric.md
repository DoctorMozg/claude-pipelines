# Governance Artifact Review Rubric — 6 Axes

The `gov-audit-reviewer` agent scores one governance artifact (ADR, RFD, or design doc) against the six axes below. Grep this file for the axis under examination; do not load it whole.

> **In-house heuristic, not an industry standard.** This rubric was synthesized from first principles for `mz-gov`. The research behind the plugin found **no external governance-review rubric that survived verification** — there is no Nygard/Oxide/Google "score your ADR" checklist to defer to. These axes encode what a careful reviewer looks for; treat them as a working heuristic, not a certified standard, and revise them as the team learns what actually catches problems.

## How to score

Each axis yields zero or more findings. Tag every finding with a severity label:

- `Critical:` — the artifact fails its purpose on this axis; a reader cannot trust or act on it as written.
- `Nit:` — a real but minor gap; worth fixing, not blocking.
- `Optional:` — a suggestion that would improve the artifact but is genuinely discretionary.
- `FYI:` — an observation for the record, no action implied.

The verdict is mechanical:

```
VERDICT: PASS   iff the artifact has zero Critical: findings
VERDICT: FAIL   if one or more Critical: findings exist
```

Nits, Optionals, and FYIs never change the verdict — they are recorded so the author can act, but they do not block. Do not soften a genuine `Critical:` to a `Nit:` to let an artifact pass; the verdict is only meaningful if the severity is honest.

Emit one severity-labeled finding per real issue, then a single `VERDICT:` line at the end. Quote the offending line or section so the author can find it. Keep each finding to one or two sentences.

______________________________________________________________________

## Axis 1 — Missing alternatives

**Question:** Does the artifact present **at least two real options** with their trade-offs, or does it assert a single choice as if no alternative existed?

A decision recorded with no alternatives is indistinguishable from a decision made by reflex. The value of a governance artifact is the *comparison* — the reader needs to see what was rejected and why.

| Finding                                                                                                                                        | Severity    |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| The decision is **ambiguous** (more than one defensible approach existed) and the artifact lists **zero** alternatives — only the chosen path. | `Critical:` |
| Exactly one alternative is named but dismissed in a clause, with no trade-off stated.                                                          | `Nit:`      |
| Two-plus options are present but one is a transparent straw man (named only to be knocked down).                                               | `Nit:`      |
| The decision is genuinely unambiguous (one sensible approach) and alternatives are reasonably absent.                                          | no finding  |

For an obviously-single-path decision the absence of alternatives is fine — but such a decision usually should not have been governed at all (the router exempts it). If a governed ADR shows no alternatives, that is a strong signal something is wrong: either an alternative was omitted, or the decision did not need an artifact.

## Axis 2 — Unstated assumptions

**Question:** What is this decision silently resting on — load, scale, team size, a library's behavior, an upstream contract — that is **not written down**?

Assumptions that live only in the author's head are the assumptions that break a decision six months later when they quietly stop holding.

| Finding                                                                                                                                                                                                               | Severity                                      |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| The decision depends on a load-bearing assumption (e.g. "traffic stays under X", "we keep using vendor Y", "the schema won't need field Z") that is **nowhere stated**, and if it were false the decision would flip. | `Critical:`                                   |
| A relevant assumption is implied but not made explicit; the decision survives if it's wrong, but the reader has to infer it.                                                                                          | `Nit:`                                        |
| The artifact lists its assumptions and they are reasonable.                                                                                                                                                           | no finding (note `FYI:` if one looks fragile) |

Look hardest at performance, scale, security boundaries, and external dependencies — those are where unstated assumptions hide and where being wrong is expensive.

## Axis 3 — Reversibility / one-way-door classification

**Question:** Does the artifact classify the decision as **reversible (two-way door)** or **irreversible (one-way door)**, and if irreversible, is that **justified**?

One-way doors deserve more scrutiny than two-way doors. An artifact that does not say which kind of door it is leaves the reader unable to calibrate how much the decision should have been pressure-tested.

| Finding                                                                                                                                                                                                         | Severity    |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| The decision is **hard to reverse** (data loss risk, externally published contract, expensive-to-unwind migration) and the artifact **neither classifies it as a one-way door nor justifies committing to it**. | `Critical:` |
| The door class is stated but the justification for an irreversible choice is thin (asserted, not argued).                                                                                                       | `Nit:`      |
| Door class is stated and, if one-way, the commitment is justified (why now, why this, what we lose if wrong).                                                                                                   | no finding  |
| Reversibility is genuinely irrelevant to this decision and its absence is reasonable.                                                                                                                           | no finding  |

A two-way door does not need elaborate justification — the point is that the artifact *recognizes* which kind it is. The failure is silence on an irreversible commitment.

## Axis 4 — Blast radius stated

**Question:** Does the artifact say **what this decision affects downstream** — which modules, services, data, callers, or teams feel the change?

Blast radius is the reader's map of consequences. An artifact that records a decision without its reach forces every future reader to re-derive what it touches.

| Finding                                                                                                                                                    | Severity    |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| The change clearly has non-trivial downstream reach (public API, shared schema, cross-module boundary) and the artifact states **no blast radius at all**. | `Critical:` |
| Blast radius is mentioned but partial — names the obvious caller, misses a class of affected consumers.                                                    | `Nit:`      |
| Blast radius is stated and matches the scope of the change.                                                                                                | no finding  |
| The change is genuinely self-contained and the artifact says so.                                                                                           | no finding  |

Distinguish a stated-but-narrow blast radius (a `Nit:`) from a *missing* one (potentially `Critical:`). The failure is the absent map, not an imperfect one.

## Axis 5 — Considered-options completeness

**Question:** For the alternatives that *are* present (Axis 1), are they actually **compared** — each with pros/cons or trade-offs — or merely **asserted** and listed without analysis?

This axis is the depth check on Axis 1's breadth. Two options named with no comparison is a list, not a decision rationale.

| Finding                                                                                                                                     | Severity    |
| ------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| Multiple options are listed but **none carry pros/cons or trade-offs** — the choice is asserted with no comparative reasoning.              | `Critical:` |
| Options carry trade-offs but the comparison is lopsided — the chosen option's cons are omitted while rejected options' cons are emphasized. | `Nit:`      |
| The "Considered Options" / "Pros and Cons" structure is present (MADR-style) but one option's analysis is noticeably thinner than the rest. | `Nit:`      |
| Each option is compared on consistent criteria and the choice follows from the comparison.                                                  | no finding  |

Axis 1 asks *were alternatives offered*; Axis 5 asks *were they weighed*. A rich-format artifact (MADR / design doc) is held to the higher bar — its Considered Options section exists precisely to make this comparison.

## Axis 6 — Status hygiene and provenance

**Question:** Is the artifact's **status** valid and current, and does it carry a complete **AI-provenance block with a real human sign-off**?

This axis catches the failure the whole plugin exists to prevent: an AI-authored artifact that was never actually approved by a human, or a decision that has been superseded but still reads as live.

| Finding                                                                                                                                                          | Severity    |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| The AI-provenance block is **missing**, or `human_signoff` is still `pending` (or absent) on an artifact presented as decided/executed.                          | `Critical:` |
| The status value is **not from the artifact's configured vocabulary** (an invented or stale status that no longer maps to the lifecycle).                        | `Critical:` |
| A decision that has clearly been **superseded** by a later one is **not marked** superseded — it still reads as the current decision.                            | `Critical:` |
| The provenance block is present and signed, but a field is malformed (e.g. `model` is a family name like `opus` rather than an exact id like `claude-opus-4-8`). | `Nit:`      |
| Status is valid, provenance is complete, `human_signoff` records a real approver and timestamp.                                                                  | no finding  |

**What a valid `human_signoff` looks like:** `<approver>@<ISO-8601>` (e.g. `drmozg@2026-05-31T15:10:00Z`) — a named human and the moment they signed. The literal `pending` means the human gate never closed: on an artifact that claims to be decided, that is `Critical:`. An agent proposing a decision is provenance; a human approving it is accountability — this axis verifies the second half actually happened.

The configured status vocabulary depends on the artifact type (ADRs use an open-ended set; RFDs use a fixed six-state lifecycle). Check the status against the vocabulary the artifact declares, not a hardcoded enum — an unfamiliar-but-declared status is valid; an undeclared one is not.

______________________________________________________________________

## Output format

The reviewer returns, for one artifact:

```
## <artifact path>

Axis 1 (alternatives):       <finding(s) or "clear">
Axis 2 (assumptions):        <finding(s) or "clear">
Axis 3 (reversibility):      <finding(s) or "clear">
Axis 4 (blast radius):       <finding(s) or "clear">
Axis 5 (options depth):      <finding(s) or "clear">
Axis 6 (status/provenance):  <finding(s) or "clear">

VERDICT: PASS|FAIL
```

Each non-clear axis line carries its severity-labeled finding(s). The `VERDICT:` line is `PASS` if and only if zero `Critical:` findings appear across all six axes.

## Common false positives — do NOT flag

- A genuinely unambiguous, single-path decision with no alternatives (Axis 1) — absence is correct here, not a gap.
- A two-way door that does not elaborately justify itself (Axis 3) — recognizing it as reversible is enough.
- A self-contained change that states a narrow blast radius (Axis 4) — narrow-but-stated is fine; only *missing* is a finding.
- A still-`open` RFD whose `human_signoff` is `pending` (Axis 6) — an open RFD has not been decided yet, so `pending` is the correct state, not a failure. The `Critical:` only applies when an artifact claims to be **decided/executed** with no sign-off.
- A valid status the reviewer simply does not recognize but that **is** declared in the artifact's vocabulary (Axis 6) — unfamiliar is not the same as invalid.
