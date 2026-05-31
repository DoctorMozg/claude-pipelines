# ADR Template — Nygard (minimal)

The minimal four-section ADR. Use this when a decision is **already made** and you just need to record *why* — fast, focused, one decision per file. For decisions weighing three or more options that each need explicit pros/cons, use the richer MADR template instead (`adr-madr-template.md`).

Each section is framed as the question it answers. Keep it short — an ADR is a record, not an essay. The AI-provenance fence goes **above** the Status section so a reader sees who proposed it and whether a human signed off before reading the decision itself.

Copy everything in the block below and fill the placeholders.

______________________________________________________________________

```markdown
# <NNNN>. <short decision title>

<!-- mz-gov:agdr start -->
agdr_id: <agdr-NNNN>
timestamp: <YYYY-MM-DDThh:mm:ssZ>
agent: <agent-name>
model: <exact-model-id>
trigger: <user-prompt | hook | automation>
status: <proposed | accepted | …>
human_signoff: <pending | approver@YYYY-MM-DDThh:mm:ssZ>
<!-- mz-gov:agdr end -->

## Status

<What is the standing of this decision? — e.g. accepted, proposed,
superseded by ADR-NNNN. Free text; see status-vocabularies.md.>

## Context

<What is the situation forcing a decision? The facts, constraints, and
pressures — technical and organizational — that are true regardless of
the choice we make. State the forces in tension. Value-neutral: anyone
should agree this is the situation.>

## Decision

<What did we decide to do? State it in active voice: "We will …".
One clear decision. This is the answer to the context above.>

## Consequences

<What becomes true once this decision is in force? Both the good and the
bad and the neutral — the new context this creates, the trade-offs we
accepted, the follow-on work it implies. Future readers come here to
understand what they're now living with.>
```

______________________________________________________________________

## Filled example

```markdown
# 0001. Use Redis for session storage

<!-- mz-gov:agdr start -->
agdr_id: agdr-0001
timestamp: 2026-05-31T14:32:00Z
agent: gov-artifact-writer
model: claude-opus-4-8
trigger: user-prompt
status: accepted
human_signoff: drmozg@2026-05-31T15:10:00Z
<!-- mz-gov:agdr end -->

## Status

Accepted.

## Context

Sessions currently live in process memory. That breaks the moment we run
more than one app instance — a user pinned to instance A loses their
session if the load balancer routes them to instance B. We're about to
scale horizontally, so session state has to move out of process. We
already run Redis for rate-limiting, so the operational surface is known.

## Decision

We will store sessions in Redis, keyed by session id, with a TTL matching
the session-expiry policy. The app becomes stateless with respect to
sessions; any instance can serve any request.

## Consequences

- Horizontal scaling works — no sticky sessions needed at the LB.
- Redis is now in the critical path for auth; a Redis outage logs
  everyone out. We accept this and will revisit with a fallback if it
  bites.
- One more thing to back up and monitor, but it's infra we already run.
- Session payloads must stay serializable and small (they cross the wire
  now), which constrains what we stash in a session.
```
