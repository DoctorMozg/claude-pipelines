# Phase 4: Record — Write the Durable Artifact

The human signed off. Commit the approved decision to the project's durable record under `docs/` — the right directory, the next sequential number with no collision, the AI-provenance fence embedded in the header, and a valid initial status. This phase only runs after Phase 3 stamped a real `human_signoff`.

## Precondition

`.mz/task/<task_name>/provenance.md` must carry a real `human_signoff: <user>@<ISO>` — not `pending`. If it still reads `pending`, the sign-off gate did not pass; stop and return to Phase 3. `gov-artifact-writer` will itself refuse to write an unsigned decision, but do not even dispatch it without the signature.

## Inputs (from Phase 3)

- `.mz/task/<task_name>/draft.md` — the approved artifact body.
- `.mz/task/<task_name>/provenance.md` — `human_signoff` now set to a real signature.
- The artifact type (`adr` / `rfd` / `design`) and `STATUS_VOCAB`, recorded in `state.md`.

## Step 4.1 — Resolve the target directory

Map the artifact type to its directory:

| Artifact type | Target directory  |
| ------------- | ----------------- |
| `adr`         | `docs/decisions/` |
| `rfd`         | `docs/rfcs/`      |
| `design`      | `docs/design/`    |

These are the user's project `docs/` paths — a deliberate departure from the `.mz/` scratch convention. ADRs, RFDs, and design docs are durable project memory and follow the long-standing sequential-numbering convention, not the leading-date scratch naming.

## Step 4.2 — Dispatch the artifact writer

Dispatch `gov-artifact-writer` (sonnet). It computes the next `NNNN` by globbing the target dir, re-checks the exact path at write time to survive a concurrent run, embeds the provenance fence from `provenance.md` verbatim, and initializes status from `references/status-vocabularies.md`. Single-agent dispatch. Your prompt carries the pointers and the resolved dir — not the writer's own numbering or status logic:

```
Write the approved decision as a durable, numbered artifact.

## Task Directory
.mz/task/<task_name>/

## Approved draft
.mz/task/<task_name>/draft.md

## Provenance (human_signoff is now a real signature — verify it is not pending)
.mz/task/<task_name>/provenance.md

## Artifact type and target directory
type: <adr | rfd | design>
target_dir: <docs/decisions/ | docs/rfcs/ | docs/design/>

## Template and status vocabulary
template: skills/govern/references/<adr-nygard|adr-madr|rfd|design-doc>-template.md
status set: skills/govern/references/status-vocabularies.md  (initialize status for this type)

## Numbering
Sequential NNNN — glob the target dir for the max, zero-pad to four, and
re-check the exact path immediately before writing (collision-safe).

## Also
Append the written path to .mz/task/<task_name>/state.md FilesWritten.
Report the absolute path, the number, and the initialized status, then STATUS:.
```

## Step 4.3 — Handle the writer's status

- `DONE` / `DONE_WITH_CONCERNS` → record the returned `docs/` path and initialized status in `state.md` (log any concern, e.g. the number was bumped past a collision). Append the path to `FilesWritten` if the writer did not.
- `NEEDS_CONTEXT` → a required input was missing (draft, template, provenance, or target dir). Supply it and re-dispatch.
- `BLOCKED` → a hard obstacle — `provenance.md` still `pending` (return to Phase 3), the collision bound exhausted, an unreadable status vocabulary, or an unwritable target path. Escalate via AskUserQuestion; do not retry the same operation blindly.

The writer must **create** a new file, never clobber an existing numbered artifact. If it reports an overwrite risk it could not resolve, treat that as `BLOCKED`.

## Step 4.4 — Update state, promote to recall, advance

Record in `state.md`: the durable artifact path, its number, and its initialized status. Set `Phase: 5`, `phase_complete: true` for Phase 4, refresh `what_remains` (e.g. "link commit/PR", "recommend next skill").

**Promote the decision into recall memory.** Add (or append to) a `## Decisions` section in `state.md` with a one-line summary of what was decided and where it landed:

```
## Decisions
- <decision title> → <docs path> (<one-way | two-way> door, signed <approver>)
```

`mz-memory`'s SessionEnd capture harvests `## Decisions` into the Activity Log, so the decision resurfaces in the next session's injected context with no cross-plugin call. For a load-bearing invariant the user will want enforced for the life of the project, also recommend pinning it via `/memory-note`.

**Record the decision in the interaction journal.** The sign-off gate's question and answer were already captured by the `AskUserQuestion` hook; append a `decision` entry to `.mz/journal.md` that ties the decision to its durable artifact and signature. Wrap any sensitive span in `<private>`:

```bash
printf '### %s · govern · <task_name> · decision\n- artifact: <docs path> (#<NNNN>, status <status>)\n- door: <one-way | two-way> · signed: <approver>@<ISO>\n\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>.mz/journal.md
```

Emit a visible block — the written path, number, status, and the promoted decision line — then read `phases/enforce.md`.

## Notes

- Exactly one provenance fence travels into the artifact header, copied verbatim from `provenance.md` including the real `human_signoff`. The writer embeds it; it is not re-formatted here.
- Numbering is best-effort without a lock — the writer's glob-then-recheck handles the common case; two concurrent `govern` runs racing for the same number are an accepted edge, resolved by the write-time recheck bumping one of them.
- The initialized committed status comes from the vocabulary file, not a hardcoded enum — RFD's six states are fixed by the Oxide spec; ADR and design-doc sets are project-configurable defaults.
