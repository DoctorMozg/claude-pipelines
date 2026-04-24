#!/usr/bin/env bash
set -euo pipefail

# PreToolUse(Bash) — blocks destructive commands that are nearly always mistakes.
# Exit 2 = block, stdout JSON with additionalContext = warn.

INPUT=$(cat)

CMD=$(jq -r '.tool_input.command // empty' <<< "$INPUT" 2>/dev/null || echo "")

if [[ -z "$CMD" ]]; then
  exit 0
fi

# --- BLOCK patterns (exit 2) ---

# rm -rf on root or home
if printf '%s\n' "$CMD" | grep -qP 'rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)*-[a-zA-Z]*r[a-zA-Z]*\s+[/~](\s|$)' || \
   printf '%s\n' "$CMD" | grep -qP 'rm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+)*-[a-zA-Z]*f[a-zA-Z]*\s+[/~](\s|$)' || \
   printf '%s\n' "$CMD" | grep -qP 'rm\s+-rf\s+/'; then
  jq -n --arg reason "Blocked: rm -rf on root or home directory. This would destroy your filesystem." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
  exit 2
fi

# Force push to main/master
if printf '%s\n' "$CMD" | grep -qP 'git\s+push\s+.*--force(-with-lease)?\s+.*(main|master)' || \
   printf '%s\n' "$CMD" | grep -qP 'git\s+push\s+.*-(f)\s+.*(main|master)' || \
   printf '%s\n' "$CMD" | grep -qP 'git\s+push\s+.*(main|master)\s+.*--force' || \
   printf '%s\n' "$CMD" | grep -qP 'git\s+push\s+.*(main|master)\s+.*-f(\s|$)'; then
  jq -n --arg reason "Blocked: force push to main/master. This rewrites shared history and can destroy teammates' work." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
  exit 2
fi

# git reset --hard
if printf '%s\n' "$CMD" | grep -qP 'git\s+reset\s+--hard'; then
  jq -n --arg reason "Blocked: git reset --hard discards all uncommitted changes irreversibly. Use git stash or commit first." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
  exit 2
fi

# DROP TABLE/DATABASE
if printf '%s\n' "$CMD" | grep -qiP 'DROP\s+(TABLE|DATABASE)'; then
  jq -n --arg reason "Blocked: DROP TABLE/DATABASE is irreversible data destruction. Verify this is intentional." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
  exit 2
fi

# TRUNCATE TABLE
if printf '%s\n' "$CMD" | grep -qiP 'TRUNCATE\s+TABLE'; then
  jq -n --arg reason "Blocked: TRUNCATE TABLE permanently deletes all rows. Verify this is intentional." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
  exit 2
fi

# chmod 777 on root
if printf '%s\n' "$CMD" | grep -qP 'chmod\s+(-R\s+)?777\s+/'; then
  jq -n --arg reason "Blocked: chmod 777 / makes everything world-writable. This is a critical security issue." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
  exit 2
fi

# Fork bomb patterns
if printf '%s\n' "$CMD" | grep -qP ':\(\)\{.*\|.*\}' || printf '%s\n' "$CMD" | grep -qP '\.\s*/dev/stdin'; then
  jq -n --arg reason "Blocked: detected fork bomb pattern. This would crash your system." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
  exit 2
fi

# dd to disk devices
if printf '%s\n' "$CMD" | grep -qP 'dd\s+.*of=/dev/(sd|nvme|hd|vd)'; then
  jq -n --arg reason "Blocked: dd to raw disk device. This overwrites disk data irreversibly." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
  exit 2
fi

# mkfs on devices
if printf '%s\n' "$CMD" | grep -qP 'mkfs\s+.*(/dev/|/)'; then
  jq -n --arg reason "Blocked: mkfs formats a disk device, destroying all data on it." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
  exit 2
fi

# --- WARN patterns (additionalContext, exit 0) ---

# Force push to non-main branch
if printf '%s\n' "$CMD" | grep -qP 'git\s+push\s+.*--(force|f)(\s|$)'; then
  jq -n --arg msg "Warning: force push detected. Make sure this branch is not shared with others." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", additionalContext: $msg}}'
  exit 0
fi

# rm -rf with specific paths (not root/home)
if printf '%s\n' "$CMD" | grep -qP 'rm\s+-rf\s+'; then
  jq -n --arg msg "Warning: rm -rf detected. Double-check the target path is correct." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", additionalContext: $msg}}'
  exit 0
fi

# git clean
if printf '%s\n' "$CMD" | grep -qP 'git\s+clean\s+-[a-zA-Z]*f'; then
  jq -n --arg msg "Warning: git clean -f permanently deletes untracked files. Consider git clean -n (dry run) first." \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", additionalContext: $msg}}'
  exit 0
fi

exit 0
