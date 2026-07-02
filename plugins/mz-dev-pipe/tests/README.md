# mz-dev-pipe — Tests

Lightweight static verification for the plugin. These tests do not invoke real agents — they validate the **contract** between every orchestrator skill and the agents it dispatches: terminal-state tokens, status-protocol references, and structural well-formedness.

The tests are designed to run in CI and locally before any version bump. `set_versions.sh` invokes `run_contract_matrix.sh` as a precondition; a single failed cell blocks the bump.

## Files

| File                     | Purpose                                                                                         |
| ------------------------ | ----------------------------------------------------------------------------------------------- |
| `contract_matrix.md`     | Declarative table — for each pipeline agent, which terminal-state tokens it must emit           |
| `run_contract_matrix.sh` | Bash validator — parses `contract_matrix.md`, greps each agent file, reports per-cell pass/fail |
| `smoke/fixture/`         | Synthetic 3-file Python fixture for `make smoke` (calculator + account + test)                  |
| `smoke/run_smoke.sh`     | Static smoke runner — validates plumbing of the /build pipeline against the fixture             |

## Running

```bash
# Validate the contract matrix against current agent files
make contract-matrix

# Run static smoke against the fixture (writes report to .mz/metrics/smoke/)
make smoke

# Run both
make test

# Version bumps are gated by the contract matrix automatically
./set_versions.sh 0.34.1
```

## What `make smoke` actually checks

A true end-to-end smoke would invoke Claude against `smoke/fixture/` and assert STATUS-line emission from every dispatched agent. That requires a mocked agent harness or a paid Claude API call — neither suitable for a Makefile-driven CI gate.

Instead, the static smoke validates:

1. Every `pipeline-*` agent referenced by `build/SKILL.md` and its phases has a file under any plugin's `agents/` directory.
1. Every `shared/<file>.md` link in the build skill resolves to a real file.
1. The contract matrix passes for all dispatched agents.
1. Every fixture file parses as Python.
1. No skill file writes a non-enum state `Status` token (`completed`, `in_progress`, `complete_with_residuals`) — the schema enum is `pending|running|complete|aborted_by_user|failed` and `resume-protocol` branches on exact tokens.

Output is written to `.mz/metrics/smoke/<YYYY_MM_DD>.json` so CI can compare runs over time. A red cell here means a refactor broke the wiring before any user could trigger the bug.

## Why this exists

Pipeline orchestrators branch on STATUS/VERDICT tokens emitted by sub-agents. If an agent file silently drops a token (e.g., a refactor removes the `STATUS: BLOCKED` documentation), the orchestrator's branch becomes unreachable and bugs surface only at runtime — usually inside a long fan-out, after the user already approved a cost-bearing gate. The contract matrix catches that drift at edit time, before any version is cut.

The matrix is intentionally **declarative** (not exhaustive): it encodes the agent author's intent ("this agent CAN return BLOCKED") rather than runtime behavior. It is not a substitute for `make smoke`, which exercises the actual /build pipeline against a fixture.
