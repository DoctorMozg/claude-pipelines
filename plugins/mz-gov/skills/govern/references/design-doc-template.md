# Design Doc Template — Google (informal)

Use a design doc when the decision is **made** and you now need to **specify the build** in enough detail to implement it — component layout, data flow, the concerns that cut across the whole thing. (If you're still deciding *whether* to do it, that's an RFD. If you only need to record *why* you chose it, that's an ADR.)

This follows the Google informal design-doc model. It is deliberately **not a strict template** — write it in whatever form makes the most sense for the problem. The five sections below have proven useful across many docs; treat them as a strong default, not a rigid form.

> **The quality test:** the whole point of a design doc is capturing the key decisions and the **trade-offs and alternatives** considered. If this doc basically says "this is how we're going to implement it" with no trade-offs and no alternatives, you should have just written the code — skip the doc and ship the program.

Copy the block below and fill the placeholders. Drop or merge sections that genuinely don't apply; don't invent content to fill a heading.

______________________________________________________________________

```markdown
# <design doc title>

<!-- mz-gov:agdr start -->
agdr_id: <agdr-NNNN>
timestamp: <YYYY-MM-DDThh:mm:ssZ>
agent: <agent-name>
model: <exact-model-id>
trigger: <user-prompt | hook | automation>
status: <draft | reviewed | accepted | …>
human_signoff: <pending | approver@YYYY-MM-DDThh:mm:ssZ>
<!-- mz-gov:agdr end -->

## Context and scope

<What's the situation, and what are the boundaries of this design? Enough
background that a reader new to it understands the landscape — current
state, the constraints, what's in scope and what this design touches.
Brief and factual; not a sales pitch.>

## Goals and non-goals

**Goals**
- <what this design must achieve — observable, ideally measurable>

**Non-goals**
- <what we are explicitly NOT solving here — the things a reader might
  assume are in scope but aren't. Non-goals are as important as goals;
  they bound the discussion.>

## The actual design

<The heart of the doc. How it works: the components, how they fit together,
the data flow, the interfaces, the storage, the failure handling. Use
diagrams where a picture beats paragraphs. Go deep enough that someone
could build from this — but lead with the decisions and their trade-offs,
not just a description of the end state.>

## Alternatives considered

<The approaches you weighed and rejected, and *why* each lost. This is what
separates a design doc from a description. For each alternative: what it
was, and the trade-off that ruled it out. If this section is empty, ask
whether you needed a doc at all.>

## Cross-cutting concerns

<The things that touch the whole design and are easy to forget: security,
privacy, observability/monitoring, performance, operability, cost,
migration/rollout, backwards compatibility. Address each that applies; say
"n/a — <reason>" for ones that genuinely don't.>
```

______________________________________________________________________

## Filled-skeleton example (abbreviated)

```markdown
# Moving sessions to Redis

<!-- mz-gov:agdr start -->
agdr_id: agdr-0003
timestamp: 2026-05-31T14:50:00Z
agent: gov-artifact-writer
model: claude-opus-4-8
trigger: user-prompt
status: accepted
human_signoff: drmozg@2026-05-31T15:30:00Z
<!-- mz-gov:agdr end -->

## Context and scope

Sessions live in process memory today, which blocks horizontal scaling.
This design covers moving session storage to Redis and making the app
stateless w.r.t. sessions. It does not cover the auth/login flow itself.

## Goals and non-goals

**Goals**
- Any app instance can serve any authenticated request.
- Session reads add < 2ms p99 to request latency.

**Non-goals**
- Replacing the cookie/token format.
- A Redis HA / failover story (tracked separately).

## The actual design

Session id stays in the existing cookie. On each request, the session
middleware reads `session:<id>` from Redis (TTL = session expiry) and
hydrates the request. Writes go through the same key on mutation...
[components, key schema, TTL handling, failure-mode behavior here]

## Alternatives considered

- **Postgres session table** — durable and already backed up, but every
  request would hit the primary DB; ruled out on latency and load.
- **Stateless signed cookies** — no server store, but revocation is hard
  and secret rotation is awkward; ruled out on the inability to
  force-invalidate.

## Cross-cutting concerns

- **Security** — session payloads now cross the wire to Redis; keep them
  minimal and ensure the Redis link is on the private network.
- **Observability** — add Redis hit/miss and latency metrics on the auth
  path.
- **Operability** — Redis is now in the auth critical path; alert on it.
- **Migration** — dual-read during rollout, then cut over; in-memory path
  removed after one stable release.
```
