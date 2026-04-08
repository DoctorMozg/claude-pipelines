#!/usr/bin/env bash
set -euo pipefail

# SessionStart hook (once: true) — detects project tooling and writes .mz/tooling.json.
# Language-agnostic: checks for ecosystem config files, then parses them for specific tools.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
OUTPUT_DIR="${PROJECT_DIR}/.mz"
OUTPUT_FILE="${OUTPUT_DIR}/tooling.json"

mkdir -p "$OUTPUT_DIR"

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

  if [[ "$FIRST_ECO" == "true" ]]; then
    FIRST_ECO=false
  else
    echo ',' >> "$OUTPUT_FILE"
  fi

  cat >> "$OUTPUT_FILE" <<ENTRY
    "$name": {
      "test": "$test_cmd",
      "lint": "$lint_cmd",
      "format": "$fmt_cmd",
      "typecheck": "$type_cmd",
      "install": "$install_cmd"
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

  # Parse package.json for tools
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

  if [[ "$FIRST_TOOL" == "true" ]]; then
    FIRST_TOOL=false
  else
    echo ',' >> "$OUTPUT_FILE"
  fi

  cat >> "$OUTPUT_FILE" <<ENTRY
    "$name": {
      "command": "$cmd",
      "config": "$config"
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
ECOSYSTEMS=$(jq -r '.ecosystems | keys[]' "$OUTPUT_FILE" 2>/dev/null | tr '\n' ', ' | sed 's/,$//')
if [[ -n "$ECOSYSTEMS" ]]; then
  echo "{\"hookSpecificOutput\":{\"additionalContext\":\"Project tooling detected: ${ECOSYSTEMS}. Full details in .mz/tooling.json\"}}"
fi

exit 0
