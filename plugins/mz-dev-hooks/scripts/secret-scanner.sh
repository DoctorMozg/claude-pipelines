#!/usr/bin/env bash
set -euo pipefail

# PreToolUse(Write|Edit|MultiEdit) — blocks high-confidence secrets, warns on medium.
# Scans content being written/edited for API keys, tokens, and private keys.

INPUT=$(cat)

FILE_PATH=$(jq -r '.tool_input.file_path // empty' <<< "$INPUT" 2>/dev/null || echo "")

# Allowlist: skip scanning for test/example/mock files
if [[ -n "$FILE_PATH" ]]; then
  LOWER_PATH=$(echo "$FILE_PATH" | tr '[:upper:]' '[:lower:]')
  if [[ "$LOWER_PATH" == *"/test/"* ]] || \
     [[ "$LOWER_PATH" == *"/tests/"* ]] || \
     [[ "$LOWER_PATH" == *"/test_"* ]] || \
     [[ "$LOWER_PATH" == *"_test."* ]] || \
     [[ "$LOWER_PATH" == *".test."* ]] || \
     [[ "$LOWER_PATH" == *".spec."* ]] || \
     [[ "$LOWER_PATH" == *"/fixture"* ]] || \
     [[ "$LOWER_PATH" == *"/mock"* ]] || \
     [[ "$LOWER_PATH" == *"/example"* ]] || \
     [[ "$LOWER_PATH" == *"/sample"* ]] || \
     [[ "$LOWER_PATH" == *".example"* ]] || \
     [[ "$LOWER_PATH" == *".sample"* ]] || \
     [[ "$LOWER_PATH" == *".template"* ]]; then
    exit 0
  fi
fi

CONTENT=$(jq -r '
  (.tool_input.content // empty),
  (.tool_input.new_string // empty),
  ((.tool_input.edits // [])[] | .new_string // empty)
' <<< "$INPUT" 2>/dev/null || echo "")

if [[ -z "$CONTENT" ]]; then
  exit 0
fi

# --- HIGH-CONFIDENCE patterns (exit 2 = block) ---

# AWS Access Key
if echo "$CONTENT" | grep -qP 'AKIA[0-9A-Z]{16}'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: AWS Access Key ID detected (AKIA...). Remove the key and use environment variables or a secrets manager."}}'
  exit 2
fi

# GitHub Personal Access Token
if echo "$CONTENT" | grep -qP 'ghp_[A-Za-z0-9]{36,}'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: GitHub Personal Access Token detected (ghp_...). Remove the token and use environment variables."}}'
  exit 2
fi

# GitHub OAuth / App tokens
if echo "$CONTENT" | grep -qP 'gho_[A-Za-z0-9]{36,}|ghu_[A-Za-z0-9]{36,}|ghs_[A-Za-z0-9]{36,}|ghr_[A-Za-z0-9]{36,}'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: GitHub OAuth/App token detected. Remove the token and use environment variables."}}'
  exit 2
fi

# Private keys (PEM format)
if echo "$CONTENT" | grep -qP '\-\-\-\-\-BEGIN\s+(RSA|DSA|EC|OPENSSH|PGP)?\s*PRIVATE KEY\-\-\-\-\-'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: Private key detected in PEM format. Never commit private keys — use a secrets manager."}}'
  exit 2
fi

# Stripe secret keys
if echo "$CONTENT" | grep -qP 'sk_(test|live)_[A-Za-z0-9]{20,}'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: Stripe secret key detected (sk_...). Remove the key and use environment variables."}}'
  exit 2
fi

# Slack tokens
if echo "$CONTENT" | grep -qP 'xox[baprs]-[A-Za-z0-9\-]{10,}'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: Slack token detected (xox...). Remove the token and use environment variables."}}'
  exit 2
fi

# Google API keys
if echo "$CONTENT" | grep -qP 'AIza[0-9A-Za-z\-_]{35}'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: Google API key detected (AIza...). Remove the key and use environment variables."}}'
  exit 2
fi

# Generic JWT (3-part base64 with valid header)
if echo "$CONTENT" | grep -qP 'eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}'; then
  echo '{"hookSpecificOutput":{"decision":"block","reason":"Blocked: JWT token detected. Tokens should not be hardcoded — use environment variables or a secrets manager."}}'
  exit 2
fi

# --- MEDIUM-CONFIDENCE patterns (warn via additionalContext, exit 0) ---

WARNINGS=""

if echo "$CONTENT" | grep -qiP '(password|passwd|pwd)\s*[=:]\s*["\x27][^"\x27]{8,}'; then
  WARNINGS="${WARNINGS}Possible hardcoded password detected. "
fi

if echo "$CONTENT" | grep -qiP '(api_key|apikey|api-key)\s*[=:]\s*["\x27][^"\x27]{8,}'; then
  WARNINGS="${WARNINGS}Possible hardcoded API key detected. "
fi

if echo "$CONTENT" | grep -qiP '(secret|token|auth_token|access_token)\s*[=:]\s*["\x27][^"\x27]{8,}'; then
  WARNINGS="${WARNINGS}Possible hardcoded secret/token detected. "
fi

if echo "$CONTENT" | grep -qiP '(connection_string|database_url|db_url)\s*[=:]\s*["\x27][^"\x27]{8,}'; then
  WARNINGS="${WARNINGS}Possible hardcoded connection string detected. "
fi

if [[ -n "$WARNINGS" ]]; then
  WARNINGS="${WARNINGS}Consider using environment variables or a secrets manager instead."
  jq -n --arg msg "Warning: $WARNINGS" \
    '{hookSpecificOutput: {additionalContext: $msg}}'
fi

exit 0
