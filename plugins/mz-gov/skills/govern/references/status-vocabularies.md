# Status Vocabularies

Each artifact type carries its own status set. These are **configurable per project — not one hardcoded universal enum.** There is no single canonical ADR status enum; the claim that `proposed/accepted/rejected/deprecated/superseded` is *the* universal set is wrong. Treat the sets below as sensible defaults a project can extend or trim, except where a set is explicitly fixed by its source spec.

The router records which set applies in `routing.md`; the writer initializes the new artifact's status from the matching set here.

______________________________________________________________________

## ADR — open-ended (default, configurable)

ADR status is an **open set**, not a closed enum. MADR itself shows an ellipsis in the spec to signal this. Nygard's Status section is free text. Start from these and add project-specific values as needed:

```
proposed | rejected | accepted | deprecated | … | superseded by ADR-NNNN
```

- `proposed` — written, awaiting decision/approval.
- `accepted` — the decision is in force.
- `rejected` — considered and declined (the ADR still stays as a record of *why not*).
- `deprecated` — no longer recommended, but not yet replaced.
- `superseded by ADR-NNNN` — replaced by a later ADR. This is a **relation**, not a bare keyword: it carries the id of the replacement so the chain stays navigable. When you mark an ADR superseded, point the old one forward and (optionally) the new one back.

The `…` is deliberate: a project may add states like `experimental`, `on-hold`, or `accepted (trial)`. That's expected. Do not reject a status just because it isn't in the list above — reject it only if the project's own configured set doesn't include it.

______________________________________________________________________

## RFD — fixed Oxide six-state lifecycle

RFD status is **fixed**, not configurable — it's the Oxide RFD lifecycle and the state names are load-bearing. In order:

```
prediscussion → ideation → discussion → published → committed → abandoned
```

- `prediscussion` — placeholder; the RFD exists but isn't ready for feedback yet.
- `ideation` — only a topic and scope captured; an alternate entry point (an RFD can start here instead of at `prediscussion`).
- `discussion` — active feedback in progress.
- `published` — merged and considered correct; still amendable, and discussion can continue.
- `committed` — fully implemented.
- `abandoned` — deemed non-viable or deliberately never implemented. Terminal.

Notes that matter for validation:

- There is **no `superseded` state** in the RFD lifecycle. Do not add one. If an RFD is replaced, that's expressed through its content/links, not a status — superseding is an ADR concept, not an RFD one.
- The chain is **not strictly linear**: `ideation` is an alternate entry, and `committed` / `abandoned` are both terminal.
- A reviewer should flag any RFD whose status is outside these six values.

______________________________________________________________________

## Design doc — `draft → reviewed → accepted → superseded`

Design-doc status is configurable, with this practical default:

```
draft | reviewed | accepted | superseded
```

- `draft` — being written / circulating for comments.
- `reviewed` — has been through discussion but isn't ratified yet.
- `accepted` — agreed; this is the design being built.
- `superseded` — replaced by a later design doc (carry the replacement reference, same as the ADR relation).

A project can collapse `reviewed` into `draft`, or add states like `implemented`. Keep `accepted` and `superseded` — they're what the review function checks for status hygiene.

______________________________________________________________________

## Why configurable, not hardcoded

A universal status enum doesn't exist and pretending one does breaks on contact with real projects — teams legitimately use `experimental`, `trial`, `on-hold`, `implemented`, and house-specific states. The two rules that *are* firm:

1. **RFD's six states are fixed** by the Oxide spec — don't extend them.
1. **Supersession is a relation**, not a bare word — whenever an artifact is superseded, record the id it was replaced by.

Everything else is a project default the team is free to configure. Store the project's chosen sets wherever the project keeps its governance config; the writer and the reviewer both read from that single source rather than assuming a built-in enum.
