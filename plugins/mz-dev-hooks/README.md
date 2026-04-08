# mz-dev-hooks

Development workflow hooks for [Claude Code](https://claude.com/claude-code). Deterministic safety gates and intelligent workflow reminders that work with any project type.

## Install

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-dev-hooks
```

Hooks activate automatically on install — no configuration needed.

## Hooks

### Safety Gates (shell scripts, zero token cost)

| Hook                        | Event                   | Action | What it catches                                                                                                                                                         |
| --------------------------- | ----------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Dangerous command guard** | PreToolUse(Bash)        | Block  | `rm -rf /`, force push to main/master, `git reset --hard`, `DROP TABLE`, `chmod 777 /`, fork bombs, `dd` to disk devices                                                |
| **Secret scanner**          | PreToolUse(Write\|Edit) | Block  | AWS keys (AKIA...), GitHub tokens (ghp\_), private keys (PEM), Stripe keys (sk\_), Slack tokens (xox), Google API keys, JWTs. Warns on generic password/secret patterns |
| **File safety guard**       | PreToolUse(Write\|Edit) | Block  | Lock files (package-lock.json, yarn.lock, etc.), `.env` files, vendor directories (node_modules, \_\_pycache\_\_, .venv)                                                |
| **Commit quality**          | PreToolUse(Bash)        | Warn   | Non-conventional commit messages, subject lines over 72 chars                                                                                                           |

Safety gates use regex pattern matching — they're fast, deterministic, and cost zero API tokens.

The secret scanner has an **allowlist**: files in test/fixture/mock/example/sample directories are not blocked, only warned.

### Workflow Reminders (Haiku prompts, language-agnostic)

| Hook                 | Event                    | What it does                                                     |
| -------------------- | ------------------------ | ---------------------------------------------------------------- |
| **Format reminder**  | PostToolUse(Write\|Edit) | Reminds to run the project formatter after modifying source code |
| **Test reminder**    | PostToolUse(Write\|Edit) | Reminds to add/update tests when new public functions are added  |
| **Dependency alert** | PostToolUse(Edit)        | Reminds to run install command after dependency manifest changes |

Prompt hooks use Haiku to understand context — they work with any programming language without hardcoding tool names. They only fire when relevant (not for config edits, docs, or minor changes).

## Design Principles

- **Block only when certain**: Only 3 hooks block (dangerous commands, high-confidence secrets, protected files). Everything else warns via `additionalContext`.
- **Shell for safety, prompts for intelligence**: Regex catches secrets deterministically. LLM understands whether a code change needs tests.
- **Zero configuration**: Works out of the box with Python, JavaScript/TypeScript, Rust, Go, Java, Ruby, C/C++, and any other language.

## Exit Code Reference

| Code | Meaning                                               |
| ---- | ----------------------------------------------------- |
| 0    | Allow (with optional warning via `additionalContext`) |
| 2    | Block the action with a reason message                |

Note: exit code 1 is a hook error, NOT a block. This is the #1 mistake in hook implementations.
