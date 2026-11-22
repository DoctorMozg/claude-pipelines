#!/usr/bin/env bash
set -euo pipefail
# A run whose one unit is merged: the integration branch holds it, and main has moved on since it was cut.
task=2026_11_22_orchestrate_calc
root=$PWD
base=$(basename "$root")
commit() { git commit -q -m "$1"; }

# The eval workspace may already hold a repository, so name the branch after the first commit.
git init -q
# The sandbox has no git identity, and the final phase's sync merge commits.
git config user.name eval
git config user.email eval@example.invalid
mkdir -p calc tests
touch calc/__init__.py tests/__init__.py
printf 'def add(a: int, b: int) -> int:\n    return a + b\n' >calc/ops.py
printf 'import unittest\n\nfrom calc.ops import add\n\n\nclass AddTest(unittest.TestCase):\n    def test_add(self) -> None:\n        self.assertEqual(add(2, 3), 5)\n' >tests/test_ops.py
printf 'test:\n\tpython3 -m unittest discover -s tests -t .\n' >Makefile
printf '.mz/\n' >.gitignore
printf '# calc\n' >README.md
git add -A
commit base
git branch -M main

wt=$root/.mz/worktrees/$task/$base
git worktree add -q -b "orchestrate/$task" "$wt" main
printf 'def mul(a: int, b: int) -> int:\n    return a * b\n' >"$wt/calc/mul.py"
printf 'import unittest\n\nfrom calc.mul import mul\n\n\nclass MulTest(unittest.TestCase):\n    def test_mul(self) -> None:\n        self.assertEqual(mul(2, 3), 6)\n' >"$wt/tests/test_mul.py"
git -C "$wt" add -A
git -C "$wt" commit -q -m "orch merge WU-1: multiply"

printf '# calc\n\nSmall arithmetic helpers.\n' >README.md
git add README.md
commit "describe calc"

dir=$root/.mz/task/$task
mkdir -p "$dir"
printf '# Plan\n\n1. Add calc/mul.py with mul(a, b) and a unittest test.\n' >"$dir/source_plan.md"
cat >"$dir/dag.json" <<EOF
{"task": "$task", "project": "$root", "source": {"path": "$dir/source_plan.md", "kind": "markdown"},
 "units": [{"id": "WU-1", "title": "Multiply", "kind": "change", "repo": "$root", "skill": "mz-dev-pipe:build",
  "spec": "Add calc/mul.py with mul(a, b) and tests/test_mul.py.", "owns": ["calc/mul.py", "tests/test_mul.py"],
  "depends_on": [], "verify": "make test", "backend": "auto", "status": "merged", "attempts": 1}]}
EOF
cat >"$dir/state.md" <<EOF
schema_version: 2
Status: running
Phase: final
Started: 2026-11-22T10:00:00Z
phase_complete: false
what_remains: [final review, final gate]
source: $root/PLAN.md
source_kind: markdown
repos:
  - $root
dag: $dir/dag.json
review_round: 1
unattended: false
final_round: 1
integration:
  - repo: $root
    start_branch: main
    start_checkout: $root
    integration_branch: orchestrate/$task
    worktree: $wt
    tip: $(git -C "$wt" rev-parse HEAD)

## Decisions

- DAG approved: $dir/dag.json (1 units), 2026-11-22
EOF
