# RFD Template — Request for Discussion (Oxide)

Use an RFD when the decision is **still open** — you need to structure a debate and reach consensus before anyone commits to a direction. (Once the outcome is settled, an ADR records the *why* and a design doc specifies the *how*. An RFD is the container for the part where it isn't settled yet.)

This follows the Oxide RFD model. The lifecycle states are **fixed** — they're load-bearing, not a project preference. Copy the block below and fill the placeholders.

______________________________________________________________________

```markdown
---
rfd: <NNNN>
title: <short title of the thing under discussion>
state: <prediscussion | ideation | discussion | published | committed | abandoned>
authors: <owner(s) of this RFD>
discussion: <link to the discussion thread / PR, once one exists>
---

# RFD <NNNN> — <title>

<!-- mz-gov:agdr start -->
agdr_id: <agdr-NNNN>
timestamp: <YYYY-MM-DDThh:mm:ssZ>
agent: <agent-name>
model: <exact-model-id>
trigger: <user-prompt | hook | automation>
status: <proposed | …>
human_signoff: <pending | approver@YYYY-MM-DDThh:mm:ssZ>
<!-- mz-gov:agdr end -->

## Summary

<One paragraph: what is being proposed for discussion, and why now.>

## Problem statement

<What problem or question are we trying to resolve? Why does it need a
group decision rather than a quick call?>

## Proposal / options on the table

<The approach(es) under consideration. Unlike an ADR, the outcome is open
— lay out the candidate directions and the trade-offs you see, without
pre-deciding. Invite the reader to push back.>

## Open questions

- <what's genuinely undecided and needs input>
- <…>

## Determinations

<Filled in as discussion converges: the decisions reached, and the
reasoning. Empty while the RFD is in `discussion`.>
```

______________________________________________________________________

## The six-state lifecycle

States, in order:

```
prediscussion → ideation → discussion → published → committed → abandoned
```

- **prediscussion** — placeholder; the RFD exists but isn't ready for feedback.
- **ideation** — only topic and scope captured. An alternate entry point — an RFD can start here.
- **discussion** — active feedback in progress.
- **published** — merged and considered correct. Still amendable; discussion can continue.
- **committed** — fully implemented.
- **abandoned** — non-viable or deliberately never built. Terminal.

There is **no `superseded` state** — that's an ADR concept, not an RFD one. The chain isn't strictly linear: `ideation` is an alternate start, and `committed`/`abandoned` are terminal.

______________________________________________________________________

## How RFDs are actually run (practice notes)

These are the conventions that keep an RFD low-ceremony and consensus-favoring. They're guidance, not mechanism:

- **The comment window is a guideline, not a rule.** A 3–5 business-day window for comments is *recommended* to give people a fair chance to weigh in — but it's a guideline you flex to the situation, not a hard gate. A small, low-stakes RFD doesn't need to sit open for a week.
- **The owner decides which comments to accept.** Discussion gathers input; it doesn't bind the author. The RFD owner retains final authority over which comments to incorporate — "the comments you choose to accept are up to you as the owner of the RFD." Consensus is the goal, not unanimity.
- **Discussion can continue after `published`.** Publishing isn't a lock. A published RFD is "merged and correctable" — people can keep commenting and the document can be amended. Moving to `published` means the debate has converged enough to write it down, not that it's frozen.

The async, comment-driven shape is the point: it structurally favors reaching consensus over forcing a vote, and reserves anyone's calendar time for only the heaviest debates.
