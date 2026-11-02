# Phase 6: Verification Summary

After Phase 5 completes, emit a visible block:

```
Outreach enrich-company done.
Source (read from):     <source_path>
Card (final):           <target_path = .mz/outreach/active/<today>_<slug>.md>
Relocated:              <yes | no>     # yes if source_path != target_path
Task dir:               .mz/task/<task_name>/
Enrichment mode:        <both | only | skip>
Subagents dispatched:   <N>    (capped at 5)
Subagents failed:       <M>
Deeper-intel fields:    <list of populated subsections (e.g. news, tech, growth, reputation, contacts)>
Contacts drafted:       <N>   (channels: <breakdown>)   # 0 if enrich_mode == only
Contacts skipped:       <M>   (no contact route)
Light web calls:        <K>   (cap 6)
Naturalize reverted:    <R>   (drafts where naturalize was rolled back)
Reader profiles:        <P>   (footprint: <F>, role-priority: <RP>)   # absent if personality:off
Strategy source:        <strategy.json | default | sender_override>
STATUS: <DONE | DONE_WITH_CONCERNS>
```

`STATUS: DONE_WITH_CONCERNS` whenever any of: `strategy_source == default`, any contact was skipped, any draft was naturalize-reverted, any copywriter dispatch failed, any web call returned an error, any enrichment subagent returned `NEEDS_CONTEXT`/`BLOCKED`, the light-pass cap was hit and contacts had to drop, the relocation failed to delete the source file.
