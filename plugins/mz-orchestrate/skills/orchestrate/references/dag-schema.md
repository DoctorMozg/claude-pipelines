# DAG Schema

`dag.json` is the one source of truth for an orchestration run. The compiler writes it, `scripts/dag.sh` is the only thing that changes it afterwards, and every gate shows `dag.sh render` of it.

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
- `source.kind`: `markdown`, `build-plan`, `adr`, `design` or `conversation`.

## Unit fields

| Field                                                                                | Set by        | Value                                                                                                          |
| ------------------------------------------------------------------------------------ | ------------- | -------------------------------------------------------------------------------------------------------------- |
| `id`                                                                                 | compiler      | `WU-1`, `WU-2`, …; a build plan's own ids are kept                                                             |
| `title`                                                                              | compiler      | a few words                                                                                                    |
| `kind`                                                                               | compiler      | `change` (commits on its own branch) or `review` (read-only, returns findings)                                 |
| `repo`                                                                               | compiler      | absolute path of the repository the unit works in                                                              |
| `skill`                                                                              | compiler      | a skill from the run's `skills.md` catalog, or `direct`                                                        |
| `spec`                                                                               | compiler      | the self-contained brief the worker gets, in markdown                                                          |
| `owns`                                                                               | compiler      | path globs, relative to `repo`, that the unit may create or change, its tests included; `[]` for a review unit |
| `depends_on`                                                                         | compiler      | ids of units whose merged work this one needs                                                                  |
| `verify`                                                                             | compiler      | a shell command run in the unit's worktree that proves the unit; required for `change`                         |
| `backend`                                                                            | compiler      | `auto`, `subagent`, `session` or `peer:<name>`                                                                 |
| `status`                                                                             | `dag.sh`      | `pending`, `running`, `done`, `merged`, `blocked`, `failed` or `skipped`                                       |
| `attempts`                                                                           | `dag.sh`      | how many times the unit was dispatched                                                                         |
| `base_commit`, `branch`, `head_commit`, `worktree`, `backend_used`, `result`, `note` | `dag.sh mark` | set while the unit runs                                                                                        |

A `review` unit counts as satisfied for its dependents once it is `done`; a `change` unit once it is `merged`.

## Writing a good unit

- **One worker context.** A unit is what one `build` or `debug` run finishes well: about 10 files and 400 changed lines at most. Split anything larger along a seam the plan already names.
- **The spec stands alone.** The worker sees only `spec`, never the plan. Include the goal, the decisions from the plan that bind this unit, the files and interfaces it touches, what its dependencies provide (names, signatures, paths), acceptance criteria, and what is out of scope.
- **`owns` is exact.** List every path the unit changes, including tests, fixtures and shared files such as a router, a registry, a manifest or a lockfile. Two units that could run at the same time may not own overlapping paths in one repo: `dag.sh lint` rejects that, and the fix is a `depends_on` edge or a split. Globs overlap when one's literal prefix starts with the other's, so `src/api/*` and `src/api/v2.py` clash but `src/api/*` and `src/apiv2/*` don't.
- **Open decisions block.** When the plan leaves a choice open that this unit can't make, the spec names the question and the options and tells the worker to stop with `STATUS: BLOCKED` before writing code. Workers have no other way to ask; `NEEDS_CONTEXT` is not a worker status.
- **`depends_on` follows real needs.** Add an edge when a unit imports, calls, migrates or tests what another unit creates, or when both must touch one shared file. Don't chain units that are independent; parallelism is the point.
- **`verify` proves this unit.** A non-interactive command that finishes in minutes, such as `uv run pytest tests/test_invoice.py -q` or `npm test -- invoice`, using the repository's own test runner. It runs on the unit's branch, which holds the merged dependencies, so it may rely on them. `true` is only for a `review` unit.
- **`skill` by intent.** New behavior → `mz-dev-pipe:build`. A defect with a reproduction → `mz-dev-pipe:debug`. Cleanup, dead code, or getting tests and CI green → `mz-dev-pipe:polish`. Documentation → `mz-creative:document`. A read-only check → `mz-dev-git:review-branch` or `mz-dev-pipe:audit` with `kind: review`. A mechanical edit of a few lines that needs no tests → `direct`. Only skills present in `skills.md` may be used.
- **`backend` stays `auto`** unless the plan or the user names where a unit runs. The scheduler routes `auto` units to an attached peer whose role fits, then to a subagent for the project repository, then to a fresh session. `subagent` works only in `project`. `peer:<name>` needs a peer in `peers.json` whose role covers the unit.

## Example

```json
{
  "id": "WU-2",
  "title": "Invoice API endpoint",
  "kind": "change",
  "repo": "/home/me/work/app",
  "skill": "mz-dev-pipe:build",
  "spec": "## Goal\nAdd `POST /invoices` ...\n\n## Given by WU-1\n`Invoice` model in `app/models/invoice.py` ...\n\n## Acceptance\n- 201 with the invoice id ...\n\n## Out of scope\nPDF rendering (WU-4).",
  "owns": ["app/api/invoices.py", "app/api/__init__.py", "tests/api/test_invoices.py"],
  "depends_on": ["WU-1"],
  "verify": "uv run pytest tests/api/test_invoices.py -q",
  "backend": "auto",
  "status": "pending"
}
```
