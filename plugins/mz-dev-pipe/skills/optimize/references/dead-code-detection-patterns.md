# Dead-Code Detection Patterns

Sources (official docs):

- Python `ruff`: https://docs.astral.sh/ruff/rules/
- Python `vulture`: https://github.com/jendrikseipp/vulture
- TypeScript `tsc`: https://www.typescriptlang.org/tsconfig
- `ts-prune`: https://github.com/nadeesha/ts-prune
- `knip`: https://knip.dev/
- Rust `cargo`: https://doc.rust-lang.org/cargo/commands/cargo-check.html
- Rust `cargo-udeps`: https://github.com/est31/cargo-udeps
- Go `goimports`: https://pkg.go.dev/golang.org/x/tools/cmd/goimports
- Go `deadcode`: https://pkg.go.dev/golang.org/x/tools/cmd/deadcode
- `jscpd`: https://github.com/kucherenko/jscpd
- `simian`: https://simian.quandarypeak.com/

Use via grep — locate the pattern, run the command, read the confidence level. Do not load the whole file.

## unused imports

Per-language detection commands and false-positive behavior.

**Python (`ruff`)**:

```bash
ruff check --select F401 path/to/src/
ruff check --select F401 --fix path/to/src/
```

- Rule `F401` = "imported but unused". Confidence: **high** for straightforward imports, **low** for `__init__.py` re-exports — ruff honors `__all__` if present.
- False positives: imports used only in `TYPE_CHECKING` blocks (use `from __future__ import annotations` or guard with `if TYPE_CHECKING:`).
- Related rules: `F811` (redefined unused name), `F841` (unused local variable).

**Python (broader, `pyflakes` + `autoflake`)**:

```bash
autoflake --remove-all-unused-imports --recursive --in-place path/
```

- Confidence: high. Safer than `ruff --fix` for legacy code because it touches only imports and clearly-unused vars.

**TypeScript (`tsc`)**:

```bash
tsc --noUnusedLocals --noUnusedParameters --noEmit
```

- `noUnusedLocals` catches unused imports + locals, `noUnusedParameters` catches unused function params.
- Confidence: **high**. Compiler-level, no false positives outside of declaration merging.
- For per-file rules: ESLint `@typescript-eslint/no-unused-vars` with `argsIgnorePattern: "^_"`.

**TypeScript (`knip`)**:

```bash
npx knip
```

- Better than `tsc` for multi-entry projects because it follows the dependency graph from `package.json` `main`/`exports`/`bin`.
- Confidence: high. Flags unused imports, exports, files, dependencies, devDependencies.

**Rust (`cargo`)**:

```bash
cargo check --message-format=short 2>&1 | grep "unused import"
```

- The compiler emits `warning: unused import` by default.
- Confidence: **very high** — compiler-level analysis.
- Related warnings: `dead_code` (unreachable functions), `unused_variables`.
- Fix with `cargo fix --allow-dirty` (applies suggestions automatically).

**Rust (`cargo-udeps`)** — unused *dependencies* in `Cargo.toml`:

```bash
cargo +nightly udeps
```

- Confidence: medium-high. Requires nightly. False positives on deps only used in examples or doctests.

**Go (`goimports`)**:

```bash
goimports -l -d ./...           # list + diff
goimports -w ./...              # write in place
```

- Removes unused imports and adds missing ones. Confidence: **high** — Go forbids unused imports at compile time, so `go build` will also catch them.
- For dead functions: `golang.org/x/tools/cmd/deadcode` (see "dead exports" below).

**Multi-language fallback**: most modern LSP servers surface unused imports as warnings in real time — a clean editor view is the cheapest signal.

## unreachable branches

Control-flow analysis to find code that can never execute.

**Python (`vulture`)**:

```bash
vulture path/to/src/ --min-confidence 80
```

- Confidence scale: `100` = definitely unused, `60` = possibly unused. Start at `80` and lower if needed.
- Detects: unused classes, methods, functions, unreachable code after `return`/`raise`.
- False positives: dynamic dispatch (getattr, plugin systems), test-discovered fixtures. Whitelist via `vulture src/ whitelist.py`.

**TypeScript (`tsc` + ESLint)**:

```bash
tsc --noFallthroughCasesInSwitch --noImplicitReturns --noEmit
npx eslint --rule '{"no-unreachable": "error"}' src/
```

- `no-unreachable` flags statements after `return`/`throw`/`break`/`continue`.
- `no-constant-condition` flags `if (false)`, `while (0)`.
- For pattern-match exhaustiveness: use `never` type in default branches — compiler errors on missing cases.

**Rust**:

```bash
cargo check
cargo clippy -- -W unreachable_code -W unreachable_patterns
```

- Compiler emits `unreachable_code` warnings natively. Clippy adds pattern-level checks: `unreachable_patterns`, `match_single_binding`.
- Confidence: **very high**. Rust's match exhaustiveness checking is the gold standard.

**Go**:

```bash
go vet ./...
staticcheck ./...      # https://staticcheck.dev/
```

- `staticcheck` has `U1000` (unused code) and `SA4006` (value assigned but never used).
- Confidence: high. Go's simple control flow makes unreachable branches rare but staticcheck catches them.

**AST-walking fallback** (any language): for custom rules, walk the AST and find:

- Statements after `return`/`throw`/`raise`/`break`/`continue` in the same block.
- `if (literal_false)` / `if (literal_true)` arms.
- Functions called from nowhere (cross-reference against call graph).

Tools: `tree-sitter` (multi-language), `ast` module (Python), `ts-morph` (TypeScript), `syn` (Rust).

## dead exports

An export that no one imports is dead weight — SKILL.md can slim down without it.

**TypeScript (`ts-prune`)**:

```bash
npx ts-prune
npx ts-prune --error    # exit non-zero if any dead exports found
```

- Uses the TS program graph. Confidence: high for app code, **lower for libraries** because consumers are outside the repo.
- Mark intentionally-unused-but-exported symbols with `// ts-prune-ignore-next`.

**TypeScript (`knip`)** — recommended replacement for `ts-prune`:

```bash
npx knip
npx knip --dependencies --exports --files
```

- Flags unused files, exports, types, members, dependencies, devDependencies, binaries.
- Config via `knip.json`. More accurate than `ts-prune` and actively maintained.

**Python (`vulture`)**:

```bash
vulture src/ --min-confidence 70
```

- Finds unused module-level names, unused methods, unused classes.
- Limitations: can't see dynamic imports (`importlib`), plugin-discovery systems, Django URL routing, pytest fixture collection. Whitelist those.

**Rust**:

```bash
cargo check 2>&1 | grep "dead_code"
```

- `#[allow(dead_code)]` silences per-symbol; the compiler native `dead_code` lint catches unused `pub(crate)` items.
- For truly unused `pub` items across crates: use `cargo-machete` or `cargo-udeps` + manual review.

**Go (`deadcode`)**:

```bash
go install golang.org/x/tools/cmd/deadcode@latest
deadcode ./...
```

- Whole-program reachability analysis from `main`. Finds unreachable functions.
- Confidence: **very high** for binaries (whole-program). **Low** for libraries (exported = reachable by definition).

**Multi-language heuristic**: an export is a contract. Before deleting, grep the whole monorepo + any published consumers for the symbol name *and* for dynamic lookups (`getattr`, `require`, `import()` with computed paths).

## orphan files

Files that exist on disk but are never imported anywhere — pure dead weight.

**Generic recursive-grep approach** (works for any language):

```bash
# 1. List all source files
fd -e py -e ts -e tsx src/ > /tmp/all_files.txt

# 2. For each file, grep the repo for its module name
while read -r path; do
    module=$(basename "$path" | sed 's/\.[^.]*$//')
    count=$(grep -rE "(import|from|require).*$module" --include='*.py' --include='*.ts' -l | wc -l)
    [ "$count" -eq 0 ] && echo "orphan: $path"
done < /tmp/all_files.txt
```

- False positives: entry points (`main.py`, `index.ts`, `cli.ts`), test files (pytest auto-discovers by filename), Django `views.py` / `urls.py` referenced by path string.
- Confidence: **medium**. Always double-check before deleting.

**TypeScript (`knip`)**:

```bash
npx knip --files
```

- Reports unused files via dep graph from `package.json` entries. Confidence: high with correct config.

**Python (`unimport` + grep)**:

```bash
unimport --check --diff src/
```

- `unimport` is narrower than `vulture` — focused on imports only — but faster for the "is anything importing this?" question.

**Language-agnostic strategy**:

1. Identify entry points (CLI binaries, server mains, test files, config-referenced files).
1. Build the reachability closure from entry points (BFS through import statements).
1. Any file outside the closure is orphan — but verify against test-discovery and dynamic-import patterns before deleting.

## duplicated logic heuristics

Clone detection — identical or near-identical code blocks scattered across files.

**AST-based (`jscpd`)**:

```bash
npx jscpd src/ --min-lines 5 --min-tokens 50 --reporters console,html
npx jscpd src/ --min-lines 10 --min-tokens 100 --threshold 5 --format javascript,typescript,python
```

- Multi-language (30+). Token-based: catches renamed-variable clones.
- Thresholds: `--min-lines` (default 5), `--min-tokens` (default 50). Raise both for fewer false positives.
- Output: HTML report with side-by-side diffs. Confidence: **high** for structural duplication.

**Token-stream (`simian`)**:

```bash
java -jar simian.jar -threshold=6 -language=java src/**/*.java
```

- Java-based; supports Java, C#, C, C++, COBOL, Python, JS. Older but battle-tested.
- Token-level similarity — ignores whitespace and comments.

**Python-specific (`flake8-duplicates`, `radon`)**:

```bash
radon raw src/            # lines, LOC, comments
radon mi src/             # maintainability index
radon cc src/ -s          # cyclomatic complexity (clone hotspots)
```

- `radon` doesn't detect clones directly, but high-complexity + high-maintainability-index files are where clones live. Pair with `jscpd`.

**TypeScript (`jscpd` or `copy-paste-detector`)**:

```bash
npx jscpd --threshold 3 --min-tokens 50 src/
```

**Rust**:

```bash
cargo clippy -- -W clippy::similar-names -W clippy::too_many_arguments
```

- No first-party clone detector. Use `jscpd` (supports Rust via tokenizer) or manual review via `cargo bloat`.

**Go**:

```bash
dupl -threshold 50 ./...
```

- `dupl` (github.com/mibk/dupl). Syntax-tree based. Threshold is minimum token count.

**Line-window grep (last resort, any language)**:

```bash
# Find 5-line blocks repeated anywhere
for f in $(fd -e py); do
    awk 'NR>=5 { for (i=0;i<5;i++) line = line $(NR-i); print line > "/tmp/windows.txt"; line="" }' "$f"
done
sort /tmp/windows.txt | uniq -c | sort -rn | head -20
```

- Crude but language-agnostic. Catches verbatim clones only; renamed variables escape.

**Confidence ladder**:

- AST-based (`jscpd`, `simian`) — high confidence, low false positive rate.
- Token-stream — high confidence for renamed clones.
- Line-window grep — low confidence, useful as a first pass.

**Remediation rule of thumb**: three occurrences = extract a function; two is fine. Always extract before the fourth.
