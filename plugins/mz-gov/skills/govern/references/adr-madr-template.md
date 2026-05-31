# ADR Template — MADR (rich)

MADR is a strict superset of the minimal Nygard ADR. Reach for it when the decision weighs **three or more real options** that each deserve explicit pros and cons, or whenever the caller asked for the `rich` form. For a quick one-decision record, the Nygard template (`adr-nygard-template.md`) is enough.

MADR keeps the metadata in YAML frontmatter and adds the sections that make a multi-option decision legible: the drivers, the options compared, and the pros/cons of each. The AI-provenance fence sits directly under the frontmatter, above the body.

Copy the block below and fill the placeholders. Sections marked *optional* can be dropped when they'd be empty — don't pad.

______________________________________________________________________

```markdown
---
status: "{proposed | rejected | accepted | deprecated | … | superseded by ADR-NNNN}"
date: <YYYY-MM-DD when the decision was last updated>
deciders: <who made the call>
consulted: <whose input was sought — two-way conversation>
informed: <who was kept in the loop — one-way>
---

# <short decision title>

<!-- mz-gov:agdr start -->
agdr_id: <agdr-NNNN>
timestamp: <YYYY-MM-DDThh:mm:ssZ>
agent: <agent-name>
model: <exact-model-id>
trigger: <user-prompt | hook | automation>
status: <proposed | accepted | …>
human_signoff: <pending | approver@YYYY-MM-DDThh:mm:ssZ>
<!-- mz-gov:agdr end -->

## Context and Problem Statement

<What's the situation and the question it raises? Describe the forces and
frame the problem, ideally as a question. Two or three sentences.>

## Decision Drivers

- <a force / criterion / concern that the decision must answer to>
- <another>
- <…>

## Considered Options

- <option 1>
- <option 2>
- <option 3>
- <…>

## Decision Outcome

Chosen option: "<option N>", because <the deciding justification — which
drivers it satisfies that the others don't>.

### Consequences

- Good, because <positive outcome>.
- Bad, because <cost / trade-off we accept>.
- <…>

### Confirmation <!-- optional -->

<How we'll confirm the decision is implemented and honored — a test, a
review checkpoint, an architecture-fitness check, a lint rule. Drop this
subsection if there's nothing concrete to point at.>

## Pros and Cons of the Options

### <option 1>

- Good, because <…>.
- Neutral, because <…>.
- Bad, because <…>.

### <option 2>

- Good, because <…>.
- Bad, because <…>.

### <option 3>

- Good, because <…>.
- Bad, because <…>.

## More Information <!-- optional -->

<Links to related ADRs, the RFD this graduated from, design docs, tickets,
or external references. Any context a future reader would want. Drop if
empty.>
```

> **`status` is open-ended.** The frontmatter shows `{proposed | rejected | accepted | deprecated | … | superseded by ADR-NNNN}` with a literal ellipsis — that is intentional. There is no closed five-state enum; a project may add its own states. `superseded by ADR-NNNN` is a relation carrying the replacement's id, not a bare keyword. See `status-vocabularies.md`.

______________________________________________________________________

## Filled example

```markdown
---
status: "accepted"
date: 2026-05-31
deciders: drmozg
consulted: backend-on-call
informed: whole-team
---

# Session storage backend

<!-- mz-gov:agdr start -->
agdr_id: agdr-0002
timestamp: 2026-05-31T14:40:00Z
agent: gov-artifact-writer
model: claude-opus-4-8
trigger: user-prompt
status: executed
human_signoff: drmozg@2026-05-31T15:20:00Z
<!-- mz-gov:agdr end -->

## Context and Problem Statement

In-memory sessions block horizontal scaling — a user's session is stranded
on whichever instance created it. We're scaling out, so where should
session state live so any instance can serve any request?

## Decision Drivers

- Must survive a single app-instance restart and multi-instance routing.
- Low added operational burden — prefer infra we already run.
- Read/write latency on the auth hot path must stay negligible.

## Considered Options

- Redis (shared in-memory store)
- Postgres table (sessions row per session)
- Signed stateless cookies (no server-side store)

## Decision Outcome

Chosen option: "Redis", because it satisfies the latency driver and reuses
infra we already operate for rate-limiting, with the least new surface.

### Consequences

- Good, because any instance can serve any request — true horizontal scale.
- Good, because we add no new datastore technology.
- Bad, because Redis is now on the auth critical path; an outage logs
  everyone out.

### Confirmation

Integration test asserts a session created on one instance is readable
from another against a shared Redis.

## Pros and Cons of the Options

### Redis

- Good, because sub-millisecond reads on the hot path.
- Good, because already in our stack.
- Bad, because it's a new single point of failure for auth.

### Postgres table

- Good, because it's durable and already backed up.
- Neutral, because we already run Postgres.
- Bad, because every request hits the primary DB; adds load and latency.

### Signed stateless cookies

- Good, because zero server-side store to operate.
- Bad, because revocation is hard — can't force-invalidate a session.
- Bad, because payload size and the secret-rotation story get awkward.

## More Information

Supersedes the in-memory approach assumed in ADR-0001. Implementation
tracked in PROJ-412.
```
