#!/usr/bin/env bash
set -euo pipefail

# SessionStart hook (once: true) — detects project tooling and writes .mz/tooling.json.
# Language-agnostic: checks for ecosystem config files, then parses them for specific tools.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
OUTPUT_DIR="${PROJECT_DIR}/.mz"
OUTPUT_FILE="${OUTPUT_DIR}/tooling.json"

mkdir -p "$OUTPUT_DIR"

# Validate a command string sourced from project manifests against a conservative
# allowlist. Untrusted values that fail validation are replaced with a placeholder
# before being written to tooling.json to prevent downstream command injection.
# Length is checked separately because bash 3.2 (ships with macOS) caps regex
# bounded-repetition quantifiers at 255, so `{1,300}` in the character-class
# regex silently fails there.
validate_command() {
    local val="$1"
    if (( ${#val} < 1 || ${#val} > 300 )); then
        return 1
    fi
    # Allow: alphanumeric, space, common path chars, flags, env vars
    if [[ "$val" =~ ^[a-zA-Z0-9\ ./_@:\-]+$ ]]; then
        return 0
    fi
    return 1
}

# Emit a JSON-escaped string literal for an arbitrary shell value. Falls back to
# a minimal manual escape if jq is unavailable on the host.
json_string() {
  local val="$1"
  if command -v jq &>/dev/null; then
    jq -n --arg val "$val" '$val'
  else
    # Minimal fallback: escape backslashes, double quotes, and control chars.
    local escaped="${val//\\/\\\\}"
    escaped="${escaped//\"/\\\"}"
    printf '"%s"' "$escaped"
  fi
}

# Start building JSON
echo '{' > "$OUTPUT_FILE"
echo '  "detected_at": "'"$(date -Iseconds)"'",' >> "$OUTPUT_FILE"
echo '  "ecosystems": {' >> "$OUTPUT_FILE"

FIRST_ECO=true

add_ecosystem() {
  local name="$1"
  local test_cmd="$2"
  local lint_cmd="$3"
  local fmt_cmd="$4"
  local type_cmd="$5"
  local install_cmd="$6"

  # Validate any non-empty command value; reject unsafe characters so that
  # attacker-controlled manifest values cannot be executed downstream.
  local field
  for field in test_cmd lint_cmd fmt_cmd type_cmd install_cmd; do
    if [[ -n "${!field}" ]] && ! validate_command "${!field}"; then
      printf -v "$field" '%s' "[UNSAFE_VALUE_REJECTED]"
    fi
  done

  if [[ "$FIRST_ECO" == "true" ]]; then
    FIRST_ECO=false
  else
    echo ',' >> "$OUTPUT_FILE"
  fi

  # Use JSON-escaped literals so that even validated values cannot break JSON
  # structure (e.g. stray quotes or backslashes).
  local name_json test_json lint_json fmt_json type_json install_json
  name_json=$(json_string "$name")
  test_json=$(json_string "$test_cmd")
  lint_json=$(json_string "$lint_cmd")
  fmt_json=$(json_string "$fmt_cmd")
  type_json=$(json_string "$type_cmd")
  install_json=$(json_string "$install_cmd")

  cat >> "$OUTPUT_FILE" <<ENTRY
    ${name_json}: {
      "test": ${test_json},
      "lint": ${lint_json},
      "format": ${fmt_json},
      "typecheck": ${type_json},
      "install": ${install_json}
    }
ENTRY
}

# --- Python ---
if [[ -f "$PROJECT_DIR/pyproject.toml" ]] || [[ -f "$PROJECT_DIR/setup.py" ]] || [[ -f "$PROJECT_DIR/setup.cfg" ]]; then
  PY_TEST="pytest"
  PY_LINT=""
  PY_FMT=""
  PY_TYPE=""
  PY_INSTALL=""

  if [[ -f "$PROJECT_DIR/pyproject.toml" ]]; then
    # Detect test runner
    grep -q 'pytest' "$PROJECT_DIR/pyproject.toml" 2>/dev/null && PY_TEST="pytest"
    grep -q 'unittest' "$PROJECT_DIR/pyproject.toml" 2>/dev/null && PY_TEST="python -m unittest"

    # Detect linter
    grep -q '\[tool\.ruff\]' "$PROJECT_DIR/pyproject.toml" 2>/dev/null && PY_LINT="ruff check"
    grep -q 'flake8' "$PROJECT_DIR/pyproject.toml" 2>/dev/null && PY_LINT="flake8"
    grep -q 'pylint' "$PROJECT_DIR/pyproject.toml" 2>/dev/null && PY_LINT="pylint"

    # Detect formatter
    grep -q '\[tool\.ruff\.format\]' "$PROJECT_DIR/pyproject.toml" 2>/dev/null && PY_FMT="ruff format"
    grep -q '\[tool\.black\]' "$PROJECT_DIR/pyproject.toml" 2>/dev/null && PY_FMT="black"
    grep -q 'autopep8' "$PROJECT_DIR/pyproject.toml" 2>/dev/null && PY_FMT="autopep8"
    [[ -z "$PY_FMT" ]] && grep -q 'ruff' "$PROJECT_DIR/pyproject.toml" 2>/dev/null && PY_FMT="ruff format"

    # Detect type checker
    grep -q '\[tool\.mypy\]' "$PROJECT_DIR/pyproject.toml" 2>/dev/null && PY_TYPE="mypy"
    grep -q 'pyright' "$PROJECT_DIR/pyproject.toml" 2>/dev/null && PY_TYPE="pyright"
    grep -q 'pytype' "$PROJECT_DIR/pyproject.toml" 2>/dev/null && PY_TYPE="pytype"

    # Detect package manager
    if [[ -f "$PROJECT_DIR/uv.lock" ]] || grep -q '\[tool\.uv\]' "$PROJECT_DIR/pyproject.toml" 2>/dev/null; then
      PY_INSTALL="uv sync"
    elif grep -q '\[tool\.poetry\]' "$PROJECT_DIR/pyproject.toml" 2>/dev/null; then
      PY_INSTALL="poetry install"
    elif grep -q '\[tool\.pdm\]' "$PROJECT_DIR/pyproject.toml" 2>/dev/null; then
      PY_INSTALL="pdm install"
    elif grep -q '\[project\]' "$PROJECT_DIR/pyproject.toml" 2>/dev/null; then
      PY_INSTALL="pip install -e ."
    fi
  fi

  [[ -f "$PROJECT_DIR/requirements.txt" ]] && [[ -z "$PY_INSTALL" ]] && PY_INSTALL="pip install -r requirements.txt"

  add_ecosystem "python" "$PY_TEST" "$PY_LINT" "$PY_FMT" "$PY_TYPE" "$PY_INSTALL"
fi

# --- JavaScript/TypeScript ---
if [[ -f "$PROJECT_DIR/package.json" ]]; then
  JS_TEST=""
  JS_LINT=""
  JS_FMT=""
  JS_TYPE=""
  JS_INSTALL="npm install"

  # Detect package manager
  [[ -f "$PROJECT_DIR/yarn.lock" ]] && JS_INSTALL="yarn install"
  [[ -f "$PROJECT_DIR/pnpm-lock.yaml" ]] && JS_INSTALL="pnpm install"
  [[ -f "$PROJECT_DIR/bun.lockb" ]] && JS_INSTALL="bun install"

  # Parse package.json for tools. $DEPS is manifest-sourced (untrusted) — always
  # wrap in "$DEPS" to avoid word-splitting on attacker-chosen content.
  if command -v jq &>/dev/null; then
    DEPS=$(jq -r '(.dependencies // {}) + (.devDependencies // {}) | keys[]' "$PROJECT_DIR/package.json" 2>/dev/null || echo "")

    echo "$DEPS" | grep -qx 'vitest' && JS_TEST="vitest"
    echo "$DEPS" | grep -qx 'jest' && JS_TEST="${JS_TEST:-jest}"
    echo "$DEPS" | grep -qx 'mocha' && JS_TEST="${JS_TEST:-mocha}"

    echo "$DEPS" | grep -qx 'eslint' && JS_LINT="eslint"
    echo "$DEPS" | grep -qx 'biome' && JS_LINT="biome check"
    echo "$DEPS" | grep -qx '@biomejs/biome' && JS_LINT="biome check"

    echo "$DEPS" | grep -qx 'prettier' && JS_FMT="prettier --write"
    echo "$DEPS" | grep -qx 'biome' && JS_FMT="${JS_FMT:-biome format}"
    echo "$DEPS" | grep -qx '@biomejs/biome' && JS_FMT="${JS_FMT:-biome format}"

    echo "$DEPS" | grep -qx 'typescript' && JS_TYPE="tsc --noEmit"
  fi

  add_ecosystem "javascript" "$JS_TEST" "$JS_LINT" "$JS_FMT" "$JS_TYPE" "$JS_INSTALL"
fi

# --- Rust ---
if [[ -f "$PROJECT_DIR/Cargo.toml" ]]; then
  RS_LINT="cargo clippy"
  RS_FMT="cargo fmt"

  add_ecosystem "rust" "cargo test" "$RS_LINT" "$RS_FMT" "" "cargo build"
fi

# --- Go ---
if [[ -f "$PROJECT_DIR/go.mod" ]]; then
  GO_LINT=""
  command -v golangci-lint &>/dev/null && GO_LINT="golangci-lint run"

  add_ecosystem "go" "go test ./..." "$GO_LINT" "gofmt -w" "" "go mod tidy"
fi

# --- Java (Gradle) ---
if [[ -f "$PROJECT_DIR/build.gradle" ]] || [[ -f "$PROJECT_DIR/build.gradle.kts" ]]; then
  add_ecosystem "java-gradle" "./gradlew test" "./gradlew check" "" "" "./gradlew build"
fi

# --- Java (Maven) ---
if [[ -f "$PROJECT_DIR/pom.xml" ]]; then
  add_ecosystem "java-maven" "mvn test" "mvn verify" "" "" "mvn install"
fi

# --- C/C++ ---
if [[ -f "$PROJECT_DIR/CMakeLists.txt" ]]; then
  add_ecosystem "cpp-cmake" "ctest" "" "clang-format -i" "" "cmake --build build"
elif [[ -f "$PROJECT_DIR/Makefile" ]] && grep -q '\.cpp\|\.cc\|\.c\b' "$PROJECT_DIR/Makefile" 2>/dev/null; then
  add_ecosystem "cpp-make" "make test" "" "clang-format -i" "" "make"
fi

# --- Ruby ---
if [[ -f "$PROJECT_DIR/Gemfile" ]]; then
  RB_TEST="bundle exec rspec"
  [[ -d "$PROJECT_DIR/test" ]] && RB_TEST="bundle exec rake test"

  add_ecosystem "ruby" "$RB_TEST" "bundle exec rubocop" "" "" "bundle install"
fi

# Close ecosystems, start cross-cutting tools
{
  echo ''
  echo '  },'
  echo '  "tools": {'
} >> "$OUTPUT_FILE"

FIRST_TOOL=true

add_tool() {
  local name="$1"
  local cmd="$2"
  local config="$3"

  # Reject unsafe command strings so that manifest-derived values cannot be
  # injected into shells that later execute `command` from tooling.json.
  if [[ -n "$cmd" ]] && ! validate_command "$cmd"; then
    cmd="[UNSAFE_VALUE_REJECTED]"
  fi

  if [[ "$FIRST_TOOL" == "true" ]]; then
    FIRST_TOOL=false
  else
    echo ',' >> "$OUTPUT_FILE"
  fi

  local name_json cmd_json config_json
  name_json=$(json_string "$name")
  cmd_json=$(json_string "$cmd")
  config_json=$(json_string "$config")

  cat >> "$OUTPUT_FILE" <<ENTRY
    ${name_json}: {
      "command": ${cmd_json},
      "config": ${config_json}
    }
ENTRY
}

# pre-commit
if [[ -f "$PROJECT_DIR/.pre-commit-config.yaml" ]]; then
  add_tool "pre-commit" "pre-commit run --all-files" ".pre-commit-config.yaml"
fi

# Close JSON
{
  echo ''
  echo '  }'
  echo '}'
} >> "$OUTPUT_FILE"

# Output additionalContext so Claude knows about detected tooling
if command -v jq &>/dev/null; then
  ECOSYSTEMS=$(jq -r '.ecosystems | keys[]' "$OUTPUT_FILE" 2>/dev/null | tr '\n' ', ' | sed 's/,$//' || echo "")
  if [[ -n "$ECOSYSTEMS" ]]; then
    jq -n --arg eco "$ECOSYSTEMS" \
      '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: ("Project tooling detected: " + $eco + ". Full details in .mz/tooling.json")}}'
  fi
fi

exit 0
