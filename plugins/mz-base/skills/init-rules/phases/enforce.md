# Settings Enforcement

Rules in CLAUDE.md are requests the model weighs against everything else in context; permission rules and hooks are enforced by Claude Code itself. This file proposes four settings entries for the approval gate in `phases/run.md` and merges the approved ones with `jq`.

## Entries

The canonical fragment. Every install proposes it; drop the entries that don't apply or that the user removed at the gate.

```json
{
  "attribution": { "commit": "", "pr": "" },
  "permissions": {
    "ask": ["Bash(git push *)"],
    "deny": ["Read(./.env)", "Read(./.env.*)"]
  },
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "shell": "bash",
            "timeout": 300,
            "command": "cd \"${CLAUDE_PROJECT_DIR:-.}\" || exit 0; [ -f .pre-commit-config.yaml ] && command -v pre-commit >/dev/null 2>&1 || exit 0; grep -q '\"stop_hook_active\": *true' && exit 0; { git diff -z --name-only --diff-filter=d HEAD; git ls-files -z --others --exclude-standard; } 2>/dev/null | xargs -0 -r pre-commit run --files 1>&2 || exit 2"
          }
        ]
      }
    ]
  }
}
```

| Entry                                               | Effect                                                                                                                           | Propose when                                                                                                                                |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `attribution`                                       | Claude Code adds no Co-Authored-By trailer to commits and no attribution line to PR descriptions                                 | always                                                                                                                                      |
| `permissions.ask` `Bash(git push *)`                | Prompts before every push, including bare `git push`, compound commands, and auto mode, which otherwise allows pushes            | always                                                                                                                                      |
| `permissions.deny` `Read(./.env)`, `Read(./.env.*)` | The Read tool refuses `.env` files in the working directory, `.env.example` included                                             | always                                                                                                                                      |
| `hooks.Stop` pre-commit check                       | When Claude finishes a turn, runs `pre-commit run --files` on changed and untracked files; a failure sends Claude back to fix it | project scope: `.pre-commit-config.yaml` exists. Global scope: always, since the hook skips projects without a config or without pre-commit |

State these limits in the gate's settings section:

- Ask and deny rules match the command text Claude writes, so `git -C . push` slips past. They stop accidents, not a deliberate bypass.
- The Stop hook checks every changed file in the tree, including the user's own uncommitted edits, and pre-commit fixers may rewrite them. It blocks at most once per turn: when Claude is already continuing because of a stop hook, it lets the turn end.

## Step 1: Plan the settings changes

1. Settings file: project scope → `.claude/settings.local.json` at the repository root (`git rev-parse --show-toplevel`), or in the working directory outside git. Global scope → `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json`.
1. If `command -v jq` fails, mark the settings section `skipped: jq not installed`, and print the fragment in the final report so the user can paste it. Stop here.
1. If the file exists, run `jq empty "<file>"`. On a parse error, stop and AskUserQuestion with the path and jq's message. Never overwrite a file jq can't parse.
1. Install: mark each entry `add` or `already present`. `attribution` counts as present when the key exists with any value, since that value is the user's choice. The Stop hook counts as present when an existing Stop hook has the identical command string.
1. Uninstall: mark each entry `remove` only when an exact match exists; skip the rest silently.
1. Project scope, file missing, inside git: if `git check-ignore -q .claude/settings.local.json` fails, add a plan line to append `.claude/settings.local.json` to `$(git rev-parse --git-path info/exclude)`. That keeps the file out of commits without touching the shared `.gitignore`.

## Step 2: Merge (install)

After the gate approves, write the fragment with the approved entries only to `<PROJECT_ROOT>/.mz/task/<task_name>/settings_fragment.json` using the Write tool, so the hook command never passes through shell quoting. Then:

```bash
F="<settings file>"; FRAG="<PROJECT_ROOT>/.mz/task/<task_name>/settings_fragment.json"
mkdir -p "$(dirname "$F")"
{ [ -f "$F" ] && cat "$F" || echo '{}'; } | jq --slurpfile f "$FRAG" '
  $f[0] as $f
  | if $f.attribution and (has("attribution") | not) then .attribution = $f.attribution else . end
  | reduce ("ask", "deny") as $k (.;
      ($f.permissions[$k] // []) as $new
      | if ($new | length) > 0
        then .permissions[$k] = ((.permissions[$k] // []) + ($new - (.permissions[$k] // [])))
        else . end)
  | reduce ($f.hooks.Stop // [])[] as $g (.;
      if any(.hooks.Stop[]?.hooks[]?; .command == $g.hooks[0].command) then .
      else .hooks.Stop = ((.hooks.Stop // []) + [$g]) end)
' > "$F.tmp" && mv "$F.tmp" "$F" || { rm -f "$F.tmp"; echo "settings merge failed" >&2; }
```

Keys and entries the fragment doesn't name pass through untouched. Running it twice changes nothing. Record each added entry in `state.md` → `SettingsAdded`.

## Step 3: Remove (uninstall)

Write the full fragment to `<PROJECT_ROOT>/.mz/task/<task_name>/settings_fragment.json`, then:

```bash
F="<settings file>"; FRAG="<PROJECT_ROOT>/.mz/task/<task_name>/settings_fragment.json"
jq --slurpfile f "$FRAG" '
  $f[0] as $f
  | [$f.hooks.Stop[]?.hooks[]?.command] as $cmds
  | if $f.attribution and .attribution == $f.attribution then del(.attribution) else . end
  | reduce ("ask", "deny") as $k (.;
      if .permissions[$k] then .permissions[$k] -= ($f.permissions[$k] // []) else . end
      | if .permissions[$k] == [] then del(.permissions[$k]) else . end)
  | if .permissions == {} then del(.permissions) else . end
  | if .hooks.Stop then
      .hooks.Stop |= (map(.hooks |= map(select(.command as $c | $cmds | index($c) | not)))
                      | map(select(.hooks | length > 0)))
      | if .hooks.Stop == [] then del(.hooks.Stop) else . end
      | if .hooks == {} then del(.hooks) else . end
    else . end
' "$F" > "$F.tmp" && mv "$F.tmp" "$F" || { rm -f "$F.tmp"; echo "settings removal failed" >&2; }
```

Only exact matches go; the user's own rules, hooks, and a customized `attribution` stay. Never delete the settings file, even when it ends up as `{}`. Record each removed entry in `state.md` → `SettingsRemoved`.

## Verification

- `jq empty "<file>"` passes after every write.
- Install: `jq -e` finds each `SettingsAdded` entry in the file.
- Uninstall: `jq -e` finds none of the `SettingsRemoved` entries.
- If a merge or removal fails, the original file is unchanged. Report the jq error and mark the settings section failed in the Step 8 report of `phases/run.md`.
