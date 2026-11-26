# DAG Schema

`dag.json` is the one source of truth for an orchestration run. The compiler, or `orchestrate-planner` for `/orchestrate-plan`, writes it, `scripts/dag.sh` is the only thing that changes it afterwards, and every gate shows `dag.sh render` of it.

## Contents

- Top level
- Unit fields
- Writing a good unit
- Example

## Top level

```json
{
  "task": "2026_11_22_orchestrate_billing_v2",
  "project": "/home/me/work/app",
  "source": {"path": ".mz/task/2026_11_22_orchestrate_billing_v2/source_plan.md", "kind": "build-plan"},
  "units": []
}
```

- `project`: the orchestrating repository, absolute.
- `task`: the task that wrote the DAG, the orchestration itself or the `/orchestrate-plan` task it came from.
- `source.kind`: `markdown`, `build-plan`, `adr`, `design`, `conversation` or `orchestrate-plan`.

## Unit fields

| Field                                                                                | Set by        | Value                                                                                                                                      |
| ------------------------------------------------------------------------------------ | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `id`                                                                                 | compiler      | the plan's reference for the unit and a short name, such as `WU-2_Invoice_Api` or `Q8a1a_Calendar_Facts`; see "Naming a unit"              |
| `title`                                                                              | compiler      | a few words                                                                                                                                |
| `kind`                                                                               | compiler      | `change` (commits on its own branch), `review` (read-only, returns findings) or `context` (read-only, returns a report its dependents get) |
| `repo`                                                                               | compiler      | absolute path of the repository the unit works in                                                                                          |
| `skill`                                                                              | compiler      | a skill from the run's `skills.md` catalog, or `direct`                                                                                    |
| `spec`                                                                               | compiler      | the self-contained brief the worker gets, in markdown                                                                                      |
| `owns`                                                                               | compiler      | path globs, relative to `repo`, that the unit may create or change, its tests included; `[]` for a review unit                             |
| `depends_on`                                                                         | compiler      | ids of units whose merged work this one needs                                                                                              |
| `verify`                                                                             | compiler      | a shell command run in the unit's worktree that proves the unit; required for `change`                                                     |
| `backend`                                                                            | compiler      | `auto`, `subagent`, `session`, `codex` or `peer:<name>`                                                                                    |
| `exclusive`                                                                          | compiler      | `true` runs the unit alone, with no other unit beside it; required for `mz-dev-pipe:optimize`, and set on a checkpoint fix unit            |
| `status`                                                                             | `dag.sh`      | `pending`, `running`, `done`, `merged`, `blocked`, `failed` or `skipped`                                                                   |
| `attempts`                                                                           | `dag.sh`      | how many times the unit was dispatched                                                                                                     |
| `base_commit`, `branch`, `head_commit`, `worktree`, `backend_used`, `result`, `note` | `dag.sh mark` | set while the unit runs                                                                                                                    |
| `started_at`, `ended_at`                                                             | `dag.sh mark` | epoch seconds when the last attempt started and stopped running; `dag.sh summary` estimates the time left from them                        |

A `review` or `context` unit counts as satisfied for its dependents once it is `done`; a `change` unit once it is `merged`. When a unit is dispatched, the report of each `context` unit it depends on is pasted into its spec under `## Context from <id>`, so a context unit is useful only with a dependent, and `dag.sh lint` rejects one without.

## Writing a good unit

- **Naming a unit.** The id names the unit's branch, its worktree and every status line, so it says what the unit is: the plan's own reference for it, then `_` and two or three words in title case, such as `WU-2_Invoice_Api`, `Q3a_Vector_Lookup` or `Q8a1a_Calendar_Facts`. A plan without references numbers its units `U1`, `U2`, …. The reference holds letters, digits and `-`; the words hold letters and digits; the whole id is at most 32 characters. `dag.sh lint` rejects any other shape.
- **One worker context.** A unit is what one `build` or `debug` run finishes well: about 10 files and 400 changed lines at most. Split anything larger along a seam the plan already names.
- **The spec stands alone.** The worker sees only `spec`, never the plan. Include the goal, the decisions from the plan that bind this unit, the files and interfaces it touches, what its dependencies provide (names, signatures, paths), acceptance criteria, and what is out of scope.
- **`owns` is exact.** List every path the unit changes, including tests, fixtures and shared files such as a router, a registry, a manifest or a lockfile. Two units that could run at the same time may not own overlapping paths in one repo: `dag.sh lint` rejects that, and the fix is a `depends_on` edge or a split. Globs overlap when one's literal prefix starts with the other's, so `src/api/*` and `src/api/v2.py` clash but `src/api/*` and `src/apiv2/*` don't.
- **Open decisions block.** When the plan leaves a choice open that this unit can't make, the spec names the question and the options and tells the worker to stop with `STATUS: BLOCKED` before writing code. Workers have no other way to ask; `NEEDS_CONTEXT` is not a worker status.
- **`depends_on` follows real needs.** Add an edge when a unit imports, calls, migrates or tests what another unit creates, or when both must touch one shared file. Don't chain units that are independent; parallelism is the point.
- **`verify` proves this unit.** A non-interactive command that finishes in minutes, such as `uv run pytest tests/test_invoice.py -q` or `npm test -- invoice`, using the repository's own test runner. It runs on the unit's branch, which holds the merged dependencies, so it may rely on them. `true` is only for a `review` unit.
- **`skill` by intent.** New behavior → `mz-dev-pipe:build`. A defect with a reproduction → `mz-dev-pipe:debug`. Cleanup, dead code, or getting tests and CI green → `mz-dev-pipe:polish`. Documentation → `mz-creative:document`. A read-only check → `mz-dev-git:review-branch` or `mz-dev-pipe:audit` with `kind: review`. A mechanical edit of a few lines that needs no tests → `direct`. Only skills present in `skills.md` may be used.
- **The newer skills need more in the spec.** `mz-dev-pipe:optimize` (a measured speedup or size cut): the target, the measurement command, the metric and its direction, and `exclusive: true`. `mz-research-pipe:translate`: the target language, the source files and `mode:`, one unit per language, each owning its own locale directory. `mz-creative:naturalize` (humanizing prose, usually after a `document` unit): the files, each inside `owns`. `mz-creative:copywrite` (release notes, landing or launch copy): `format:`, the product facts and one literal target path in `owns`. `mz-research-pipe:deep-research` (web research later units need) and `mz-research-pipe:explain` (a walkthrough of existing code later units change): `kind: context`, `owns: []`, `verify: "true"`, the question the dependents need answered, and for deep-research the depth, such as 2 subtopics of about 5 pages, since its default is several times that.
- **`backend` stays `auto`** unless the plan or the user names where a unit runs. `codex` is set only when they name Codex for that unit; its skill must be a mozg plugin skill or `direct`, since Codex runs it from its own install. The scheduler routes `auto` units to an attached peer whose role fits, then to a subagent for the project repository, then to a fresh session. `subagent` works only in `project`. `peer:<name>` needs a peer in `peers.json` whose role covers the unit.

## Example

```json
{
  "id": "WU-2_Invoice_Api",
  "title": "Invoice API endpoint",
  "kind": "change",
  "repo": "/home/me/work/app",
  "skill": "mz-dev-pipe:build",
  "spec": "## Goal\nAdd `POST /invoices` ...\n\n## Given by WU-1_Invoice_Model\n`Invoice` model in `app/models/invoice.py` ...\n\n## Acceptance\n- 201 with the invoice id ...\n\n## Out of scope\nPDF rendering (WU-4_Invoice_Pdf).",
  "owns": ["app/api/invoices.py", "app/api/__init__.py", "tests/api/test_invoices.py"],
  "depends_on": ["WU-1_Invoice_Model"],
  "verify": "uv run pytest tests/api/test_invoices.py -q",
  "backend": "auto",
  "status": "pending"
}
```
