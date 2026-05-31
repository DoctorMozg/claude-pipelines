# Development Governance Policy

This project records the *why* behind substantial design decisions and keeps AI-proposed decisions traceable and human-approved. The `govern` pipeline does the work; this policy says when to reach for it.

## When governance applies

Run `/govern <the decision>` for a change that is **substantial AND ambiguous** — both must hold.

- **Substantial** — it changes externally observable behavior, a public API or wire format, a data schema or migration, a dependency, a module boundary, or the security posture; or it is **hard to reverse** (a one-way door).
- **Ambiguous** — more than one reasonable approach a competent engineer could defend.

**Exempt** (no artifact needed): a behavior-preserving refactor; an objective improvement along a numeric axis (speedup, warning removal, dependency bump with no API change); a dev-invisible / tool-internal change; a throwaway prototype or spike.

When in doubt, run `/govern` — it tells you if no artifact is needed and records a one-line exemption note. Manufacturing ambiguity that isn't there is not the goal; skipping a genuine one-way door is the failure.

## Where artifacts live

Durable governance artifacts are committed to the repository:

- `docs/decisions/` — ADRs (a decision made; record the why)
- `docs/rfcs/` — RFC/RFD (a decision still open; structure the debate)
- `docs/design/` — design docs (a decision made; specify the build)

Transient pipeline state lives under `.mz/task/` and is not committed.

## AI-provenance and human sign-off (non-negotiable)

Every governed decision carries an AI-provenance block — the proposing **agent**, the exact **model id**, a **timestamp**, and the **trigger** — and a recorded **human sign-off**. An agent **proposes**; a human **approves**. A decision artifact without a recorded sign-off is **not done**.

## How to act (be proactive)

Before you encode a substantial, ambiguous design choice into code, invoke `/govern <the decision>` yourself. Do not silently bake such a decision into a diff and leave the reasoning unrecorded — surface it through the pipeline so it gets a real artifact and a human's name on it.
