# Contract Matrix — Pipeline Agent Terminal-State Tokens

Declarative table — for each pipeline agent dispatched by an orchestrator skill, which terminal-state tokens it must document. The validator (`run_contract_matrix.sh`) parses this table and greps each agent file; a missing token in any required cell fails the validation.

## Token categories

- **STATUS** tokens are emitted by every dispatched agent (per `skills/shared/agent-status-protocol.md`). The protocol defines four canonical values: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, `BLOCKED`. An agent file documents support either by naming the token literally or by the canonical bar-separated form `STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED`.
- **VERDICT** tokens (`PASS`, `FAIL`) are emitted only by review-style agents that branch the orchestrator on a binary judgment.

## Matrix

Cell legend: `X` = required (the agent file MUST mention this token), `.` = not applicable.

| Agent                         | DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED | VERDICT: PASS | VERDICT: FAIL |
| ----------------------------- | :--: | :----------------: | :-----------: | :-----: | :-----------: | :-----------: |
| pipeline-coder                |  X   |         X          |       X       |    X    |       .       |       .       |
| pipeline-test-writer          |  X   |         X          |       X       |    X    |       .       |       .       |
| pipeline-planner              |  X   |         X          |       X       |    X    |       .       |       .       |
| pipeline-researcher           |  X   |         .          |       X       |    X    |       .       |       .       |
| pipeline-web-researcher       |  X   |         .          |       X       |    X    |       .       |       .       |
| pipeline-optimizer            |  X   |         X          |       X       |    X    |       .       |       .       |
| pipeline-code-reviewer        |  X   |         X          |       X       |    X    |       X       |       X       |
| pipeline-test-reviewer        |  X   |         X          |       X       |    X    |       X       |       X       |
| pipeline-plan-reviewer        |  X   |         X          |       X       |    X    |       X       |       X       |
| pipeline-completeness-checker |  X   |         X          |       X       |    X    |       X       |       .       |
| pipeline-tooling-detector     |  X   |         X          |       X       |    X    |       .       |       .       |
| pipeline-test-runner          |  X   |         X          |       X       |    X    |       .       |       .       |
| pipeline-lint-runner          |  X   |         X          |       X       |    X    |       .       |       .       |

Cell count: 64 (12 agents × 4 STATUS + 4 reviewer rows × 2 VERDICT — minus N/A cells).

## Notes

- **Researchers** (`pipeline-researcher`, `pipeline-web-researcher`) typically return either `DONE` (findings ready) or `NEEDS_CONTEXT` (missing source material). They rarely flag soft concerns; `DONE_WITH_CONCERNS` is intentionally not required.
- **`pipeline-completeness-checker`** is the final quality gate. It can emit `VERDICT: PASS` to signal the task is complete, but it does not emit `VERDICT: FAIL` — instead it triggers a pipeline restart from a specific phase via `STATUS: NEEDS_CONTEXT` or `BLOCKED`. The cell for `VERDICT: FAIL` is therefore N/A.
- **Skill-specific overrides** (per `skills/shared/agent-status-protocol.md` last section) do not relax the matrix — an agent that participates in a wave-merge override must still document the base tokens it could emit.

## Maintenance

When adding a new agent that participates in a pipeline:

1. Document its terminal-state tokens in the agent file (literal mentions are fine).
1. Add a row to the matrix above.
1. Run `./plugins/mz-dev-pipe/tests/run_contract_matrix.sh` and confirm the row passes.

When deprecating an agent:

1. Delete the agent file.
1. Remove its row from this matrix.

The validator does not auto-discover agents — drift between the filesystem and this matrix is intentional, surface-level documentation that the human author must keep in sync.
