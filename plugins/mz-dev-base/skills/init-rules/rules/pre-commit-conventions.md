## Pre-commit

- Never invoke formatters or linters directly (e.g., `ruff`, `prettier`, `mdformat`, `eslint`). Always run them through `pre-commit run --files <changed files>`.
- Pre-commit manages tool versions, configuration, and hook ordering. Bypassing it causes inconsistent results and missed checks.
- After editing files, verify with `pre-commit run --files <changed files>` before reporting the task as complete.
