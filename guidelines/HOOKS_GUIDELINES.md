# Hook Authoring Guidelines

Rules for writing Claude Code hooks in this repository.

Claims about Claude Code behavior carry the short source tags described at the top of AGENTS_GUIDELINES.md: a doc page, a changelog version, an issue, or "observed" for behavior seen in a probe. Pages live under `code.claude.com/docs/en/` unless the tag starts with `platform:` or `claude.com:`, and page tags without a version were checked against v2.1.316 on 2026-11-02. A rule marked "Repo convention", or a rule with no tag, is this repository's own choice.

By default a hook holds up the action that fired it until the hook exits. An `async` command hook runs in the background instead, and hooks that match the same event run in parallel (hooks.md). Unparseable or schema-invalid JSON is a non-blocking error with a hook-error notice on events such as PreToolUse; stray text before the JSON, or a field at the wrong level, is ignored with no error at all (hooks.md; hooks-guide.md). Test the output shape of every hook.

**Owned elsewhere.** These topics are defined in other files; this one only points to them.

- What hooks decide from an agent's point of view, hook output as context, where hard guarantees live, and hooks that see subagents: AGENTS_GUIDELINES.md, "Agent/Hook Interface".
- When plugin hooks don't run (claude.ai chat, Cowork's shell tool, `--bare`, safe mode, `disableAllHooks`, disabled or untrusted plugins, open firing bugs): AGENTS_GUIDELINES.md, "Agent/Hook Interface".
- `hooks:` and the other frontmatter fields plugin agents ignore: AGENTS_GUIDELINES.md, "Fields Plugin Agents Ignore".
- Stating a safety rule in an agent or skill body: AGENTS_GUIDELINES.md, "Instruction Wording".
- The journal capture hook and its record format: `guidelines/JOURNAL_GUIDELINES.md`.
- The project root that everything under `.mz/` lives in: JOURNAL_GUIDELINES.md, "Project Root".
- The version bump command: CLAUDE.md, "Bumping Versions".

## 1. Configuration

Plugin hooks live in `plugins/<name>/hooks/hooks.json`. A `hooks` key in the plugin manifest is loaded together with that file (plugins-reference.md); this repo uses only `hooks/hooks.json`.

The file has three levels: an event, its matcher groups, and each group's handlers (hooks.md).

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "AskUserQuestion",
        "hooks": [
          {"type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}\"/scripts/journal-capture.sh"}
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "startup|clear|compact",
        "hooks": [
          {"type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}\"/scripts/memory-inject.sh"}
        ]
      }
    ]
  }
}
```

- **Handler types.** `command`, `http`, `mcp_tool`, `prompt` and `agent` (hooks.md). This repo uses `command`. Every handler accepts `type`, `if`, `timeout`, `statusMessage` and `once`. Command handlers add `command`, `args`, `async`, `asyncRewake`, `shell` and `onFailure`. `async` exists only on command handlers, and `onFailure` only on command and HTTP handlers (hooks.md).
- **Shell form is the default here.** Write `"command": "\"${CLAUDE_PLUGIN_ROOT}\"/scripts/x.sh"`. The quotes keep a path with spaces as one word, and `claude plugin validate` warns when they're missing (plugins-reference.md). Shell form runs through `sh -c` on macOS and Linux and through Git Bash on Windows; without Git Bash it runs in PowerShell, where a bash script fails (hooks.md).
- **Exec form** (`args` present) spawns `command` with no shell, and the docs prefer it for path placeholders. On Windows, `command` has to resolve to a real executable such as `node.exe`, so a `.sh` path can't start there (hooks.md). Use exec form for real executables, as in `"command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/scripts/x.js"]`, or when Windows is out of scope.
- **Scripts are executable.** Commit each script with its executable bit. In shell form, a script that isn't executable or doesn't exist fails to start, which is a non-blocking error (hooks.md).
- **`if`** sits on a handler and holds exactly one permission rule, such as `Bash(git commit *)`. It's evaluated only on PreToolUse, PostToolUse, PostToolUseFailure, PermissionRequest and PermissionDenied; on any other event a handler with `if` never runs. Matching is best-effort, and Claude Code runs the hook anyway when it can't tell which commands a Bash input runs (hooks.md). Enforce a hard deny with permission rules.
- **`once`** is honored only in skill frontmatter and ignored in hooks.json (hooks.md). §5 covers what SessionStart hooks use instead.
- **`timeout`** is in seconds; §11 lists the defaults and the SessionEnd budget.

## 2. Matchers

- **Exact names or a regex.** A matcher made only of letters, digits, `_`, `-`, spaces, `,` and `|` is an exact name or a list of exact names: `Write|Edit` matches those two tools and nothing else. Any other character makes it an unanchored JavaScript regex, so `Edit.*` also matches `NotebookEdit`; anchor it as `^Edit$` (hooks.md).
- **Match all.** `*`, an empty string or no matcher fires on every occurrence of the event (hooks.md).
- **Each event matches its own field.** Tool events match `tool_name`, SessionStart matches `source`, PreCompact and PostCompact match `trigger` (`manual` or `auto`), and SubagentStart and SubagentStop match the agent type. UserPromptSubmit, Stop and several other events have no matcher support and fire every time (hooks.md).
- **One group per union.** Write `Write|Edit` in one group rather than one group per tool. Repo convention.
- **Shell guards.** A hook that inspects shell commands matches `Bash|PowerShell|mcp__workspace__bash`. Where the PowerShell tool is enabled on Windows, Claude routes shell commands through it, and a `Bash`-only matcher misses them (hooks.md). Cowork runs shell commands through `mcp__workspace__bash` (AGENTS_GUIDELINES.md, "Agent/Hook Interface").
- **Name tools that exist.** `MultiEdit` is gone from the tools reference (tools-reference.md), so an exact matcher on it never fires.

## 3. Output by Event

Before writing a hook, look up its event here. For an event not listed, read its rows in the hooks reference's "Exit code 2 behavior per event" and "Decision control" tables (hooks.md).

| Event                  | Output that takes effect                                                                                                                                                                                                                                                                                                                                                                                        | Exit 2                                                                             |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `SessionStart`         | Context from plain stdout or `additionalContext`. Also `sessionTitle`, `watchPaths`, `reloadSkills`, and `initialUserMessage` (`-p` only). No decision control                                                                                                                                                                                                                                                  | Can't block. Stderr reaches the user as a hook-error notice; Claude doesn't see it |
| `UserPromptSubmit`     | Context from plain stdout or an optional `additionalContext`. `decision: "block"` with `reason` rejects the prompt, and the reason goes to the user, not to Claude. Also `sessionTitle` and `suppressOriginalPrompt`                                                                                                                                                                                            | Blocks the prompt. Stderr goes to the user only                                    |
| `PreToolUse`           | `hookSpecificOutput.permissionDecision`: `allow`, `deny`, `ask`, or `defer` (`-p` only). `deny` at exit 0 blocks the call and shows Claude the `permissionDecisionReason`. `updatedInput` replaces the whole input; `additionalContext` lands next to the result. Deny and ask rules still apply after an `allow`. Across hooks, precedence is deny, defer, ask, allow. Top-level `decision` is deprecated here | Blocks the call. Stderr goes to Claude as the denial reason                        |
| `PostToolUse`          | Fires only after the tool succeeds; failures go to PostToolUseFailure. `additionalContext`; `decision: "block"` with `reason` adds the reason next to the result, because the tool already ran; `updatedToolOutput` replaces the result                                                                                                                                                                         | Can't block. Stderr goes to Claude, which is the way to show it a warning          |
| `Stop`, `SubagentStop` | `decision: "block"` with a required `reason` keeps Claude working; omit `decision` to let it stop, since `"block"` is the only value. `hookSpecificOutput.additionalContext` also keeps it working, shown as feedback rather than an error (changelog 2.1.163). Both count toward the cap of 8 continuations in a row (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`); check `stop_hook_active` to avoid loops              | Blocks the stop. Stderr goes to Claude as the reason                               |
| `SessionEnd`           | No decision control; JSON fields are discarded. All SessionEnd hooks share a 1.5-second budget. A plugin hook's `timeout` doesn't raise it; `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS` does (hooks.md; env-vars.md)                                                                                                                                                                                              | Can't block. Stderr goes to the user                                               |
| `PreCompact`           | `decision: "block"` blocks compaction (changelog 2.1.105). Nothing it prints is documented as reaching Claude, and `systemMessage` and `continue` are discarded. Blocking a compaction that recovers from a context-limit error makes the current request fail                                                                                                                                                  | Blocks compaction. On a manual `/compact`, stderr goes to the user                 |
| `PostCompact`          | No decision control; side effects only, such as logging the `compact_summary` it receives. Its printed output goes to the debug log, and `systemMessage` and `continue` are discarded                                                                                                                                                                                                                           | Can't block. Stderr goes to the user                                               |

- **Plain text** on stdout becomes context only on UserPromptSubmit, UserPromptExpansion, SessionStart and PostModelSwitch. On every other event it goes to the debug log (hooks.md).
- **Re-inject context after compaction** from a SessionStart hook matched on `compact`, the docs' own recipe (hooks-guide.md). Compaction hooks can't add context.
- **`hookSpecificOutput`** needs `hookEventName` set to the event name. Use it only for the fields the event's section documents (hooks.md).
- **Universal fields.** `continue: false` stops Claude entirely and shows `stopReason` to the user. `systemMessage` is a warning for the user, not for Claude. `terminalSequence` emits a desktop notification, window title or bell. `suppressOutput` has no effect. SessionEnd, PreCompact, PostCompact and Notification discard `systemMessage` and `continue`, and other events drop fields too, so check the event's section (hooks.md).

**Other blocking events.** Exit 2 blocks on 16 events: the five in the table above that can block (UserPromptSubmit, PreToolUse, Stop, SubagentStop and PreCompact) and these eleven (hooks.md):

| Event                 | Exit 2 effect                                                               | Where stderr goes                                                                                       |
| --------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `UserPromptExpansion` | Blocks the command's expansion                                              | To the user, like a JSON `reason`                                                                       |
| `PostToolBatch`       | Stops the agentic loop before the next model call                           | To the user as a warning. It stays in the conversation, so Claude sees it if the conversation continues |
| `TaskCreated`         | Rolls back the task: Claude Code deletes it                                 | To Claude, as the tool's error                                                                          |
| `TaskCompleted`       | The task isn't marked completed                                             | To Claude, as feedback                                                                                  |
| `TeammateIdle`        | The teammate keeps working instead of going idle                            | To the teammate, as feedback                                                                            |
| `ConfigChange`        | The new settings aren't applied. `policy_settings` changes can't be blocked | Only to the debug log; neither the user nor Claude sees a message                                       |
| `PreModelSwitch`      | Cancels the model switch                                                    | To the user                                                                                             |
| `Elicitation`         | Declines the request, and no dialog appears                                 | Shown to neither the user nor the MCP server                                                            |
| `ElicitationResult`   | Blocks the response; the server receives `decline`                          | Shown to neither the user nor the MCP server                                                            |
| `WorktreeCreate`      | Creation fails with an error                                                | Not documented                                                                                          |
| `WorktreeRemove`      | Removal fails if the directory still exists afterward                       | To the debug log. Agent view quotes its start when the removal came from deleting a background session  |

The worktree events fail on any non-zero exit, not only on 2 (hooks.md).

## 4. Exit Codes and Failure Handling

| Exit  | Effect (hooks.md)                                                                                                                                                                                |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 0     | Success. JSON fields on stdout apply; with plain text or nothing, the action goes ahead                                                                                                          |
| 2     | Blocks on events that can block (§3). Stderr is the message, unless JSON on stdout makes a blocking decision, whose reason is used instead. JSON can't override the block                        |
| Other | Non-blocking error. The action goes ahead, and on events such as PreToolUse a hook-error notice shows the first line of stderr. Valid JSON on stdout still decides, and the exit code is ignored |

**Pick one approach per hook**: exit codes alone, or exit 0 with JSON (hooks.md). A PreToolUse deny needs no exit 2:

```bash
jq -n --arg reason "Blocked: rm -rf on /" \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
exit 0
```

**Advisory hooks** exit 0 with no stdout on every internal error: a missing file, bad input, a missing `jq`. Every hook in this repo is meant to be advisory; §15 lists the patterns that break it. A hook that exits 1 on a missing file puts a hook-error notice in front of the user during normal work (hooks.md).

```bash
[[ -f "$MEMORY_FILE" ]] || exit 0
command -v jq >/dev/null 2>&1 || exit 0
printf '%s' "$BLOCK" | journal_append "$JOURNAL_FILE" 2>/dev/null || exit 0
```

**Policy hooks fail closed.** Set `"onFailure": "block"` (changelog 2.1.295), so that a hook that can't start, times out, exits with another code or prints invalid JSON blocks the action the way exit 2 would. It applies to command and HTTP hooks and has no effect on Stop, SubagentStop, TaskCompleted, TeammateIdle or async hooks. With it set, exit 1 counts as a failure even when the JSON allows the action. Without it, a timed-out PreToolUse hook lets the call through (hooks.md). The exception is Windows without Git Bash: there a shell-form PreToolUse or PermissionRequest hook that fails with `onFailure` unset can block the call, so an advisory hook on those events sets `"onFailure": "continue"` (hooks.md).

- **Exit 2** is for blocking, or for feedback on events that honor it, such as a warning from PostToolUse. Use it for nothing else.
- **Stderr at exit 0** goes only to the debug log; Claude never sees it (hooks.md). Use it for diagnostics.
- **Background work.** Print the decision first, then start the background process with its stdout and stderr redirected. An unredirected background process keeps the output open, and after an allow Claude Code blocks the call (hooks.md). `memory-capture.sh` detaches its compressor with `nohup … >/dev/null 2>&1 &`.
- **One rule, several layers.** The agent or skill body states a safety rule's intent in one line; hooks and permission rules enforce it. Keep the hook's patterns in the hook, and describe prose as guidance, not enforcement. A plugin can't ship permission rules (plugins-reference.md), so a plugin that needs a deny rule documents it in its README for users to add to their own settings.

## 5. SessionStart Sources

SessionStart fires with `source` set to `startup`, `resume`, `clear`, `compact` or `fork`, and its matcher filters on that value. `compact` fires after every compaction, in the middle of a session (hooks.md).

- **Context injectors** use `"matcher": "startup|clear|compact"`. Resume and fork reuse a transcript that already holds the text, so another copy would only duplicate it. Repo convention; every SessionStart hook in the repo uses this matcher.
- **Hooks whose whole job is a small, volatile value**, such as a timestamp or the current branch, add `resume`, and `fork` if needed; SessionStart reruns on resume so such a hook can refresh it (hooks.md). Larger injectors such as `memory-inject.sh` accept stale text on resume rather than add a second copy. Repo convention.
- **`once` does nothing here** (§1). The matcher controls re-firing.
- **Keep it fast.** SessionStart runs on every session and accepts only `command` and `mcp_tool` handlers. At launch it runs in the background, but Claude's first reply waits for it (hooks.md).

## 6. Building JSON Output

Build JSON with `jq -n --arg`. Interpolating a value into an `echo` string breaks the envelope as soon as the value holds a quote, newline or backslash, and the result is a parse failure: a non-blocking error, and the output has no effect (hooks.md).

```bash
# Wrong: breaks on quotes, newlines and backslashes in $content
echo "{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",\"additionalContext\":\"$content\"}}"

# Right: jq escapes the value
jq -n --arg ctx "$content" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
```

- **Print one JSON object and nothing else.** Text in front of it, such as a line a shell profile echoes, turns the output into plain text, and the decision silently has no effect (hooks-guide.md).
- **Raw text.** `jq -Rs` slurps raw stdin into one JSON string.
- **Static JSON** with no variables may use `printf`; check it once with `jq .`.
- **The no-op path prints nothing.** Repo convention. An empty `additionalContext` is valid but adds nothing.
- **A hook that needs `jq`** checks for it before the first call and exits 0 when it's missing: `command -v jq >/dev/null 2>&1 || exit 0`, as in `vault-context.sh`. Without the guard, a machine without `jq` gets a non-blocking hook error on every run (§4). Repo convention.

## 7. Injected Context

Claude Code caps each `additionalContext`, `systemMessage` and `initialUserMessage` string, and a hook's plain stdout, at 10,000 characters, measured per string even when several hooks fire. Longer text is saved to a file and replaced by its path and the first 2,000 characters, and Claude isn't asked to read the file (hooks.md; changelog 2.1.89). That cuts both ways: up to 10,000 characters per hook land in full every time the hook fires, and anything longer shrinks to a preview.

Repo convention: keep each hook's injected text to about 8,000 characters, cap line-oriented content by lines as well, name both caps as constants at the top of the script, and append a visible marker when you cut. A minimal version:

```bash
MAX_LINES=200
MAX_CHARS=8000

content=$(head -n "$MAX_LINES" "$SOURCE_FILE")
if [[ ${#content} -gt $MAX_CHARS ]]; then
  content="${content:0:$MAX_CHARS}
...[truncated]"
fi
```

`memory-inject.sh` sets the same two caps as `MAX_LOG_LINES` and `MAX_CHARS`, and marks a cut with `...[memory truncated]`.

- **Write facts, not orders.** "This repo uses `bun test`" reads as project information. Text framed as an out-of-band system command can trigger Claude's prompt-injection defenses, and Claude then shows it to the user instead of using it (hooks.md).
- **Static instructions belong in CLAUDE.md**, which loads without running a script (hooks.md). Use hooks for state that changes: memory, today's note, detected tooling.
- **Context adds up.** When several hooks add context for one event, Claude receives every value (hooks.md), so each plugin's share counts against the same window.

## 8. Reading Input

Every command hook receives one JSON object on stdin: the common fields (`session_id`, `transcript_path`, `cwd`, `hook_event_name`, and on many events `permission_mode` and `effort`) plus the event's own fields (hooks.md). Read it once, then extract fields with `jq -r`, a `// empty` fallback and `|| echo ""`, so a malformed payload exits cleanly. From `journal-capture.sh`:

```bash
INPUT=$(cat)
TOOL=$(jq -r '.tool_name // empty' <<<"$INPUT" 2>/dev/null || echo "")
[[ "$TOOL" == "AskUserQuestion" ]] || exit 0
```

- **Field shapes.** Bash and PowerShell put the command in `tool_input.command`. Write and Edit put the path in `tool_input.file_path`, always absolute, and the text in `content` or `new_string`. On Windows the path uses backslashes, so a check written as `/src/` never matches (hooks.md).
- **Re-check `tool_name`** in the script even when the matcher should guarantee it, so the script stays safe when run directly or wired to the wrong matcher. Repo convention.
- **`cwd` follows Claude** into a worktree and after `cd`, while `CLAUDE_PROJECT_DIR` stays where the session started (hooks.md). Read `cwd` when the hook needs Claude's current directory.
- **Subagents.** Tool events also fire inside subagents, with `agent_id` and `agent_type` in the input (hooks.md). Matching on them is covered in AGENTS_GUIDELINES.md, "Agent/Hook Interface".
- **UserPromptSubmit isn't only typed prompts.** It also fires when a scheduled task or `/loop` iteration runs, when a background subagent reports back, and when another session sends a message (hooks.md). `memory-prompt-inject.sh` sees those texts too.
- **Every input field is untrusted** (§12).

## 9. Paths and Environment

Hook processes receive these variables (plugins-reference.md):

- `CLAUDE_PLUGIN_ROOT`: the plugin's installed directory. It changes when the plugin updates, so keep state elsewhere.
- `CLAUDE_PLUGIN_DATA`: `~/.claude/plugins/data/<id>/`, kept across updates and deleted by default when the plugin is uninstalled everywhere. Use it for caches and installed dependencies.
- `CLAUDE_PROJECT_DIR`: the directory the session started in, which the docs call the project root (hooks.md). It can be a subdirectory of the repository (observed, 2.1.316), so it isn't this repo's project root (JOURNAL_GUIDELINES.md, "Project Root"). A hook that reads or writes under `.mz/` resolves the root the way mz-memory's `find_project_root` in `plugins/mz-memory/scripts/lib/common.sh` does: `MZ_MEMORY_ROOT` when set; otherwise the first directory with a `.git` entry, walking up from `${CLAUDE_PROJECT_DIR:-$PWD}`; and that starting directory when no `.git` turns up. Repo convention.
- `CLAUDE_PLUGIN_OPTION_<KEY>`: the plugin's user options.

Claude Code also sets `CLAUDE_CODE_SESSION_ID`, which matches `session_id`, and `CLAUDE_EFFORT` in hook processes (env-vars.md). Find sibling files through `${BASH_SOURCE[0]}` or `CLAUDE_PLUGIN_ROOT`. An installed plugin doesn't live at its repo path, so a hard-coded `~/.claude/...` or `plugins/<name>/...` path breaks.

## 10. Script Conventions

Repo convention.

```bash
#!/usr/bin/env bash
set -euo pipefail

# PostToolUse(AskUserQuestion): appends each question and answer to .mz/journal.md.
# Logging only: prints nothing and exits 0 on every path.
```

- **Header.** A shebang, `set -euo pipefail`, and a one-line comment naming the event and matcher, so a reader can find the hooks.json entry. Update the comment when the matcher changes.
- **Optional variables** are written as `${VAR:-}` or `${VAR:-default}`. Under `set -u`, `cmd "$UNSET" || true` still dies with "unbound variable"; only the default expansion helps.
- **Pipelines cut short.** `head` and `grep -q` can close a pipe early, which `pipefail` turns into a failure. A `grep` that finds nothing exits 1 as well, so under `set -e` an assignment such as `x=$(grep … | head -1)` ends the script. End such a pipeline with `|| true`, as `vault-context.sh` does: `x=$(grep … | head -1 || true)`.
- **Shared code** lives in a library under `scripts/lib/` that defines functions and runs nothing when sourced, like `plugins/mz-memory/scripts/lib/common.sh`. Source it without `|| true`: a missing library means a broken install, and the hook-error notice is the right signal. A script that is both run and sourced guards its entry point with `if [[ "${BASH_SOURCE[0]}" == "$0" ]]`.

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
```

## 11. Performance

Each hook run spawns a process, and a synchronous hook holds up its event until it exits (hooks.md).

- **Hot events stay fast.** PreToolUse, PostToolUse, UserPromptSubmit and SessionStart hooks finish in under 100 ms on a warm cache, with no network calls, language servers or full project scans. Repo convention.
- **Skip the spawn.** Narrow with `matcher` and then `if`, so the script never starts; a failed `if` avoids the process spawn entirely (hooks.md). Inside the script, test the cheapest condition first and `exit 0` early.
- **Move slow work elsewhere**: to an `async: true` command hook, a skill, or a Stop or TaskCompleted hook. The docs name async hooks as the route for test suites and external API calls. An async hook can't block or decide anything, delivers its `additionalContext` and `systemMessage` on the next turn, and is killed when a `-p` run ends. `asyncRewake: true` wakes Claude when the hook exits 2 (hooks.md).
- **Hard limits.** Command handlers time out after 600 seconds by default and after 30 on UserPromptSubmit, where a stuck hook stalls the session. All SessionEnd hooks share 1.5 seconds (hooks.md; §3).
- **Measure.** `claude --debug` writes a `Hooks:` line to the debug log with the duration of each command hook on tool events, UserPromptSubmit, SessionStart, Stop and several other events (hooks.md; changelog 2.1.296). On SessionEnd, PreCompact and Notification the line has no duration; time those hooks with `time` on a smoke run (§13).

## 12. Security

Command hooks run with the user's full permissions (hooks.md). Treat every input field as untrusted, and treat project files the hook reads, such as manifests, the same way.

- **Pass input values only as quoted arguments.** Keep them out of `eval`, `bash -c` and `sh -c`.
- **Quote every expansion**: `"$VAR"`, not `$VAR` (hooks.md).
- **Stop flag injection** with `grep -F -- "$VAR"` or `printf '%s' "$VAR" | grep …`.
- **Check paths** from input before `cd` or any file operation: no `..` segment (hooks.md), and absolute (repo convention).
- **Skip sensitive files** such as `.env`, `.git/` and keys (hooks.md).
- **Validate values from project files** before writing them where a later step may run them. `detect-tooling.sh` replaces manifest commands that fail an allowlist with a placeholder. A `-p` or SDK session never shows the workspace trust dialog (hooks.md), so hooks can run over a repository nobody has reviewed.

## 13. Testing

**Automated tests.** Repo convention: a new or changed hook script with real logic gets pytest coverage that runs the script through `subprocess` with a synthetic event on stdin and a temporary root, then asserts the exit code and the output shape. `tests/mz_knowledge/test_vault_context.py` and `tests/mz_memory/` (`memory-inject.sh`, `memory-capture.sh`) are the models. Run them with `pytest tests/mz_knowledge tests/mz_memory` from the repo's dev environment. Neither `make test` nor CI runs them, so run them by hand before committing a hook change.

**Smoke runs.** Every hook script runs without the harness. Feed a full event, with `hook_event_name`, `session_id`, `cwd` and the event's own fields, and point the script at a temporary root:

```bash
root=$(mktemp -d)

# SessionStart: expect one JSON object with additionalContext
jq -n --arg cwd "$root" '{hook_event_name: "SessionStart", source: "compact", session_id: "smoke", cwd: $cwd}' |
  MZ_MEMORY_ROOT="$root" bash plugins/mz-memory/scripts/memory-inject.sh | jq .

# PostToolUse: expect exit 0, no stdout, and a new journal entry
jq -n --arg cwd "$root" '{hook_event_name: "PostToolUse", tool_name: "AskUserQuestion", session_id: "smoke",
  cwd: $cwd, tool_input: {questions: [{question: "Proceed?"}]}, tool_response: {answers: {"Proceed?": "Yes"}}}' |
  MZ_MEMORY_ROOT="$root" bash plugins/mz-memory/scripts/journal-capture.sh
echo "exit=$?"
cat "$root/.mz/journal.md"
```

Run the no-op path as well, such as a missing file or the wrong tool: exit 0 and no stdout.

**Lint.** `pre-commit run --files <script>` runs shellcheck and shfmt (`-i 2 -ci`) as configured in `.pre-commit-config.yaml`; shellcheck doesn't need to be on PATH. That config turns off SC2086 and SC2046, so shellcheck doesn't flag unquoted expansions (§12); check them by eye.

**Validator.** Run `claude plugin validate --strict plugins/<name>`. It checks hooks.json for invalid JSON, unknown event names, a wrong nesting level and an unquoted `${CLAUDE_PLUGIN_ROOT}` in shell form, and `--strict` fails on any of them. It stays silent on `once`, on `if` for a non-tool event, on a missing or non-executable script, on an invalid regex matcher, on unknown handler fields, and on `async` or `onFailure` where they have no effect (observed on 2.1.316). Check those by hand against §15.

**Live check.** `/hooks` lists every configured hook with its source. `claude --debug` logs each run and its output to `~/.claude/debug/<session-id>.txt`; `claude --debug-file <path>` writes the same log to a path you choose. On a new hook's first run, watch for a hook-error notice: a wrong path means the hook never runs (hooks.md).

## 14. Versioning

Hook scripts carry no version of their own. `./set_versions.sh` rewrites the `version` field in every `plugins/<name>/.claude-plugin/plugin.json` and the marketplace's `metadata.version`. Bump the version for any change to a hook or a script: a set `version` pins installed copies, so users keep the old files until it changes (plugins-reference.md). A plugin loaded in place from a marketplace added by local path isn't pinned (plugins-reference.md), so a local test can pass while installed users still run the old script.

## 15. Red Flags

- A PreCompact or PostCompact hook meant to give Claude context. Move it to SessionStart with `compact` (§3, §5).
- A context-injecting SessionStart hook without a matcher, or any `once` in hooks.json. Use `startup|clear|compact` (§5).
- An unquoted `${CLAUDE_PLUGIN_ROOT}` in shell form, or exec form pointing at a `.sh` file where Windows matters (§1).
- `if` on a non-tool event, where the handler never runs, or `if` used as a hard deny (§1).
- A hooks.json entry whose script is missing or not executable, whose matcher isn't a valid JavaScript regex, or whose handler has a field §1 doesn't list. The validator doesn't catch these (§13).
- A shell-command guard that matches only `Bash`. Match `Bash|PowerShell|mcp__workspace__bash` (§2).
- JSON built with `echo "{...$VAR...}"`. Use `jq -n --arg` (§6).
- A PreToolUse hook with a top-level `decision`. Use `hookSpecificOutput.permissionDecision` (§3).
- A Stop hook that returns a `decision` other than `"block"`, or blocks without checking `stop_hook_active` (§3).
- An advisory hook that can exit non-zero: it exits 1 on a missing file or empty input, calls `jq` without a `command -v jq` guard, or lets a `grep` that matches nothing end the script under `set -e`. Exit 0 with no stdout (§4, §6, §10).
- A policy hook without `onFailure: "block"`, or one that relies on it for Stop, SubagentStop or an async hook (§4).
- `npm test`, `mypy`, `gh api` or any network call in a synchronous hook. Make it async, or move it to a skill or a Stop hook (§11).
- Injected text that can exceed about 8,000 characters with no truncation marker (§7).
- A hook that writes under `.mz/` relative to `CLAUDE_PROJECT_DIR` or the working directory. Resolve the project root first (§9).
- `tool_input` interpolated into a shell string or passed to `eval` (§12).
- `hooks:` in a plugin agent's frontmatter. Put the hook in the plugin's `hooks/hooks.json` (AGENTS_GUIDELINES.md, "Fields Plugin Agents Ignore").
