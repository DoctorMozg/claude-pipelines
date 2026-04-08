#!/usr/bin/env bash
set -euo pipefail

# PreToolUse(Bash) — blocks destructive commands that are nearly always mistakes.
# Exit 2 = block, stdout JSON with additionalContext = warn.

INPUT=$(cat)

# Extract the command from JSON input
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
if [[ -z "$CMD" ]]; then
  CMD=$(echo "$INPUT" | grep -oP '"command"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"command"\s*:\s*"//;s/"$//')
fi

if [[ -z "$CMD" ]]; then
  exit 0
fi

# --- BLOCK patterns (exit 2) ---

# rm -rf on root or home
if echo "$CMD" | grep -qP 'rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)*-[a-zA-Z]*r[a-zA-Z]*\s+[/~](\s|$)' || \
   echo "$CMD" | grep -qP 'rm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+)*-[a-zA-Z]*f[a-zA-Z]*\s+[/~](\s|$)' || \
   echo "$CMD" | grep -qP 'rm\s+-rf\s+/'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: rm -rf on root or home directory. This would destroy your filesystem."}}'
  exit 2
fi

# Force push to main/master
if echo "$CMD" | grep -qP 'git\s+push\s+.*--force(-with-lease)?\s+.*(main|master)' || \
   echo "$CMD" | grep -qP 'git\s+push\s+.*-(f)\s+.*(main|master)' || \
   echo "$CMD" | grep -qP 'git\s+push\s+.*(main|master)\s+.*--force' || \
   echo "$CMD" | grep -qP 'git\s+push\s+.*(main|master)\s+.*-f(\s|$)'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: force push to main/master. This rewrites shared history and can destroy teammates'\'' work."}}'
  exit 2
fi

# git reset --hard
if echo "$CMD" | grep -qP 'git\s+reset\s+--hard'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: git reset --hard discards all uncommitted changes irreversibly. Use git stash or commit first."}}'
  exit 2
fi

# DROP TABLE/DATABASE
if echo "$CMD" | grep -qiP 'DROP\s+(TABLE|DATABASE)'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: DROP TABLE/DATABASE is irreversible data destruction. Verify this is intentional."}}'
  exit 2
fi

# TRUNCATE TABLE
if echo "$CMD" | grep -qiP 'TRUNCATE\s+TABLE'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: TRUNCATE TABLE permanently deletes all rows. Verify this is intentional."}}'
  exit 2
fi

# chmod 777 on root
if echo "$CMD" | grep -qP 'chmod\s+(-R\s+)?777\s+/'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: chmod 777 / makes everything world-writable. This is a critical security issue."}}'
  exit 2
fi

# Fork bomb patterns
if echo "$CMD" | grep -qP ':\(\)\{.*\|.*\}' || echo "$CMD" | grep -qP '\.\s*/dev/stdin'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: detected fork bomb pattern. This would crash your system."}}'
  exit 2
fi

# dd to disk devices
if echo "$CMD" | grep -qP 'dd\s+.*of=/dev/(sd|nvme|hd|vd)'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: dd to raw disk device. This overwrites disk data irreversibly."}}'
  exit 2
fi

# mkfs on devices
if echo "$CMD" | grep -qP 'mkfs\s+.*(/dev/|/)'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: mkfs formats a disk device, destroying all data on it."}}'
  exit 2
fi

# --- WARN patterns (additionalContext, exit 0) ---

# Force push to non-main branch
if echo "$CMD" | grep -qP 'git\s+push\s+.*--(force|f)(\s|$)'; then
  echo '{"hookSpecificOutput":{"additionalContext":"Warning: force push detected. Make sure this branch is not shared with others."}}'
  exit 0
fi

# rm -rf with specific paths (not root/home)
if echo "$CMD" | grep -qP 'rm\s+-rf\s+'; then
  echo '{"hookSpecificOutput":{"additionalContext":"Warning: rm -rf detected. Double-check the target path is correct."}}'
  exit 0
fi

# git clean
if echo "$CMD" | grep -qP 'git\s+clean\s+-[a-zA-Z]*f'; then
  echo '{"hookSpecificOutput":{"additionalContext":"Warning: git clean -f permanently deletes untracked files. Consider git clean -n (dry run) first."}}'
  exit 0
fi

exit 0
