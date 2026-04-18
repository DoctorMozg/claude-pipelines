# Hook Authoring Guidelines

Rules for writing Claude Code hooks in this repository. All hook scripts must comply.

Hooks run synchronously inside the harness, block the event they fire on, and can silently corrupt sessions if they emit invalid output. Treat them as production code, not glue.

## 1. Event Output Schema Quick Reference

The single most common bug class is emitting the wrong JSON envelope for the event. Memorize this table before writing any hook.

| Event              | Output mechanism                                                                                                                            | Block?                     |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| `PreToolUse`       | `hookSpecificOutput` with `hookEventName`, optional `permissionDecision`, `permissionDecisionReason`, `updatedInput`                        | Yes (exit 2)               |
| `PostToolUse`      | `hookSpecificOutput` with `hookEventName`, optional `additionalContext`                                                                     | No                         |
| `UserPromptSubmit` | `hookSpecificOutput` with `hookEventName` + **required** `additionalContext`; top-level `decision: "block"` + `reason` to reject the prompt | Yes (top-level `decision`) |
| `SessionStart`     | `hookSpecificOutput` with `hookEventName` + `additionalContext` (accepted in practice)                                                      | No                         |
| `SessionEnd`       | Typically silent. Top-level fields only.                                                                                                    | No                         |
| `Stop`             | Top-level `decision: "approve" \| "block"`, `reason`                                                                                        | Yes (exit 2)               |
| `PostCompact`      | **Plain stdout text** — no `hookSpecificOutput` envelope                                                                                    | No                         |
| `PreCompact`       | **Plain stdout text** — no `hookSpecificOutput` envelope                                                                                    | No                         |

Top-level fields available on every event: `continue` (bool), `suppressOutput` (bool), `stopReason` (str), `systemMessage` (str). When in doubt, prefer `systemMessage` for surfacing notices.

## 2. PostCompact and PreCompact Reject `hookSpecificOutput`

The hook validator only accepts `hookSpecificOutput` for `PreToolUse`, `UserPromptSubmit`, and `PostToolUse` (and `PermissionRequest`). Compaction events do not. Emitting the envelope produces `Hook JSON output validation failed — Invalid input` and the additional context is silently dropped.

- For PostCompact/PreCompact, `printf '%s\n' "$payload"` to stdout — that becomes the additional context.
- If a function is shared across SessionStart and PostCompact (e.g., memory injection), branch on the event name: emit JSON for SessionStart, plain stdout for PostCompact.
- Never assume schema parity between event families. Confirm against the schema in the validation error or the official hooks doc before reusing a payload shape.

## 3. PreToolUse Decision Schema

PreToolUse uses `permissionDecision` inside `hookSpecificOutput`, **not** the top-level `decision` field. Mixing them is a common legacy bug.

```bash
# Correct — block via permissionDecision + exit 2
cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Blocked: rm -rf on /."}}
JSON
exit 2
```

- Valid `permissionDecision` values: `"allow"`, `"deny"`, `"ask"`, `"defer"`.
- The exit code is the source of truth for blocking — `exit 2` blocks the tool call; the JSON only annotates the reason. Without `exit 2`, the tool call proceeds even if the JSON says "deny".
- For soft warnings that don't block, use `additionalContext` and `exit 0`.

## 4. Exit Code Semantics

| Code      | Meaning                                                                          |
| --------- | -------------------------------------------------------------------------------- |
| `0`       | Pass. Stdout is parsed as hook output (JSON or plain text per event).            |
| `2`       | Block. Only meaningful for `PreToolUse` and `Stop`. Stderr is shown to the user. |
| Any other | Error. Hook is reported as failed. Tool call still proceeds in most events.      |

Hooks should `exit 0` on every internal error path (missing file, jq parse failure, unset variable). A hook that `exit 1`s on a stat call will spam the user with hook errors during normal work.

## 5. JSON Output Must Use `jq -n --arg`

Hand-rolled JSON via `echo` or `printf` with embedded variables is the second most common bug class. Quotes inside the variable break the envelope and the validator silently drops the output.

```bash
# Wrong — breaks if $content contains a quote, newline, or backslash
echo "{\"hookSpecificOutput\":{\"additionalContext\":\"$content\"}}"

# Right — jq escapes safely
jq -n --arg event "$event_name" --arg ctx "$content" \
  '{hookSpecificOutput: {hookEventName: $event, additionalContext: $ctx}}'
```

- Use `jq -Rs` to slurp raw stdin into a JSON string when piping file contents.
- Static JSON (no variable interpolation) may use `printf` directly — but lint it through `jq .` first.

## 6. Hook Configuration Shape

Plugin-level hooks live at `plugins/<name>/hooks/hooks.json`. The structure has two nesting levels: an **event group** (with optional `matcher` and `if`) wrapping a list of **commands**.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/scripts/secret-scanner.sh"},
          {"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/scripts/file-safety-guard.sh"}
        ]
      },
      {
        "matcher": "Bash",
        "if": "Bash(git commit*)",
        "hooks": [
          {"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/scripts/commit-quality.sh"}
        ]
      }
    ]
  }
}
```

- `matcher` is a regex against the tool name. Use pipes for unions (`Write|Edit|MultiEdit`), not multiple groups.
- `if` is a richer guard evaluated against the tool input — use it for command-pattern filters like `Bash(git commit*)`.
- `once: true` (per-command flag) makes a hook fire only on the first matching event in a session. Required for SessionStart context injectors so they don't re-inject after every resume.

## 7. Path Variables

Two environment variables are injected by the harness:

- `${CLAUDE_PLUGIN_ROOT}` — absolute path to the plugin directory. Use this in `command` strings and inside scripts that need to find sibling files.
- `${CLAUDE_PROJECT_DIR}` — absolute path to the user's project root (the directory Claude Code was started in). Default to `.` when unset for local smoke tests: `PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"`.

Never hardcode paths to `~/.claude/...` or `plugins/<name>/...`. Plugins move when installed via marketplace.

## 8. Defensive Input Parsing

Tool-tied hooks (`PreToolUse`, `PostToolUse`) receive a JSON event on stdin. Parse it once into a variable, then extract fields with `jq -r` and a `// empty` fallback.

```bash
INPUT=$(cat)
CMD=$(jq -r '.tool_input.command // empty' <<< "$INPUT" 2>/dev/null || echo "")

if [[ -z "$CMD" ]]; then
  exit 0   # Nothing to inspect — let the call through.
fi
```

- Always provide `// empty` and `2>/dev/null || echo ""` so a malformed payload exits cleanly instead of crashing the hook.
- Never trust `tool_input.*` content as safe shell — never `eval` it, never interpolate it into a `bash -c` string. See Rule 14.
- The exact field shape varies per tool. `Bash` exposes `tool_input.command`; `Write`/`Edit` expose `tool_input.file_path` and `tool_input.content` / `tool_input.new_string`.

## 9. SessionStart Idempotence

SessionStart fires on every new session AND on every resume of a compacted session. Without `once: true`, context injectors re-fire on every resume and bloat the conversation.

- Set `"once": true` on every SessionStart hook that injects static context (memory, routing maps, tooling detection).
- Hooks that must re-fire on resume (e.g., to refresh dynamic state) belong on `PostCompact` instead.
- The `once: true` scope is per-session-id, not per-day — restarting Claude resets it.

## 10. Cap Injected Context Size

The harness has no automatic truncation for hook output. Injecting a 50KB file into every session burns the user's context budget invisibly.

```bash
MAX_LINES=200
MAX_CHARS=8000

content=$(head -n "$MAX_LINES" "$MEMORY_FILE")
if [[ ${#content} -gt $MAX_CHARS ]]; then
  content="${content:0:$MAX_CHARS}
...[truncated]"
fi
```

- Cap by lines AND chars. Lines for human-readable docs; chars as the hard backstop.
- Append a visible truncation marker so downstream readers know content was clipped.
- Aim to keep injected context under 8KB per hook. Document the cap as named constants at the top of the script.

## 11. Shared Functions via Sourcing

When two events need the same payload-building logic (e.g., SessionStart and PostCompact both injecting memory), extract a function into one script and `source` it from the other.

```bash
# memory-reinject.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/memory-inject.sh" 2>/dev/null || true
inject_memory "PostCompact" "[PostCompact] Project memory" || exit 0
```

- The sourced script must guard its top-level entry point with `if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then ... fi` so sourcing doesn't trigger its standalone behavior.
- Pass the event name as the first argument so the shared function can branch on schema (see Rule 2).
- Source with `|| true` to avoid `set -e` killing the caller if the source is missing.

## 12. Performance Budget

Hooks run synchronously and block the event. A slow hook is felt as latency on every tool call.

- Target: under 100ms per hook on warm cache. Never invoke network calls, language servers, or full project scans.
- For matchers that fire on every `Bash` call (like `dangerous-cmd-guard.sh`), every regex you add is paid on every shell command. Order patterns most-likely-first and `exit 0` early.
- Linters, type-checkers, and test runners belong in skills or `Stop` hooks — not in `PreToolUse`.

## 13. Failure Discipline

A failing hook should never derail productive work. The default failure mode for any internal error must be `exit 0` with no stdout.

```bash
inject_memory "PostCompact" "..." || exit 0    # Swallow function failure
[[ -f "$FILE" ]] || exit 0                     # Missing file is not an error
jq -r '.x' <<< "$INPUT" 2>/dev/null || exit 0  # Bad input is not an error
```

- Reserve `exit 2` for intentional blocks on `PreToolUse` and `Stop`. Never use it as a generic error code.
- Never write to `stderr` from a passing hook — it surfaces as a hook error in the IDE extension even on `exit 0`.
- Use `set -eo pipefail` (not `set -euo`) when any expected failure path is `cmd || true` — `set -u` will trip on legitimately unset optional vars.

## 14. Security: Never Eval Tool Input

Hooks run with the user's full shell permissions. Treat every field of `tool_input` as adversarial — agent-generated commands have been observed to contain command-substitution attempts that target hook scripts.

- Never `eval "$VAR"`, `bash -c "$VAR"`, or `sh -c "$VAR"` on extracted fields.
- Never `cd "$VAR"` without `[[ "$VAR" == /* ]]` and a sanity-check on path content.
- Avoid `echo "$VAR"` followed by `grep` — use `grep -F -- "$VAR"` or `printf '%s' "$VAR" | grep ...` to prevent flag injection.
- Quote every variable expansion. `$VAR` without quotes is a defect.

## 15. Plugin-Loaded Agents Cannot Carry Hooks

Agents in `plugins/<name>/agents/` silently ignore the `hooks:`, `mcpServers:`, and `permissionMode:` frontmatter fields. Safety guarantees that depend on hooks must live in `plugins/<name>/hooks/hooks.json`, not in the agent file. See [AGENTS_GUIDELINES.md](AGENTS_GUIDELINES.md) for the full silent-ignore list.

Cowork mode (`--setting-sources user`) drops plugin hooks entirely. Any safety check that *must* run regardless of mode needs to be implemented inside the agent or skill itself, not solely as a hook gate.

## 16. Local Smoke Testing

Every hook script must be runnable without the harness. Provide a manual invocation that exercises both the success and the no-op paths.

```bash
# SessionStart smoke
CLAUDE_PROJECT_DIR=. bash plugins/mz-memory/scripts/memory-inject.sh

# PreToolUse smoke — feed a synthetic event on stdin
echo '{"tool_input":{"command":"rm -rf /"}}' \
  | bash plugins/mz-dev-hooks/scripts/dangerous-cmd-guard.sh
echo "exit=$?"
```

- Verify the exit code AND the stdout shape. A passing hook with malformed JSON is the failure mode the validator catches.
- Pipe stdout through `jq .` to confirm the JSON parses before shipping.
- Run `shellcheck` on every hook script. If `shellcheck` is unavailable, state that explicitly in the PR rather than claiming verification.

## 17. Hook Script Header Convention

Every hook script begins with `#!/usr/bin/env bash`, a strict-mode pragma, and a one-line comment naming the event and the matcher.

```bash
#!/usr/bin/env bash
set -euo pipefail

# PreToolUse(Bash) — blocks destructive commands that are nearly always mistakes.
# Exit 2 = block, stdout JSON with additionalContext = warn.
```

- The header tells future readers which `hooks.json` entry wires this script up. Keep it accurate when matchers change.
- Use `set -euo pipefail` by default. Switch to `set -eo pipefail` only if the script intentionally references unset optional variables.

## 18. Versioning and Coordination

Hook scripts live under `plugins/<name>/scripts/` and are bumped by `./set_versions.sh` along with everything else. Do not hand-edit version strings. See [CLAUDE.md](../CLAUDE.md) for the repo-level version-bump rules.

When you change a hook's output schema or matcher pattern, treat it as a behavior change requiring a version bump. Validation failures from a stale schema look identical to user-side misconfiguration and waste hours of debugging.

## 19. Red Flags

- A hook that emits `hookSpecificOutput` for `PostCompact` or `PreCompact`. → Use plain stdout (Rule 2).
- A hook that uses `echo "{...$VAR...}"` to build JSON. → Switch to `jq -n --arg` (Rule 5).
- A hook that calls `exit 1` on missing files or empty input. → Switch to `exit 0` (Rule 13).
- A `PreToolUse` hook with `decision` at the top level instead of `permissionDecision` inside `hookSpecificOutput`. → Migrate to the current schema (Rule 3).
- A `SessionStart` hook without `"once": true`. → Add it unless you intentionally need re-fire on resume (Rule 9).
- A hook that runs `npm test`, `mypy`, `gh api`, or any network call. → Move it to a skill or `Stop` hook (Rule 12).
- A hook that interpolates `tool_input.command` into a shell string without quoting and length-checking. → Refactor (Rule 14).
- An agent file under `plugins/` declaring `hooks:` in frontmatter. → Move to `plugins/<name>/hooks/hooks.json` (Rule 15).
