#!/usr/bin/env bash
set -euo pipefail
# A small calculator package with one function and its test, so the goal has real code to plan against.
git init -q
git config user.name eval
git config user.email eval@example.invalid
mkdir -p calc tests
touch calc/__init__.py tests/__init__.py
printf 'def add(a: int, b: int) -> int:\n    return a + b\n' >calc/ops.py
printf 'import unittest\n\nfrom calc.ops import add\n\n\nclass AddTest(unittest.TestCase):\n    def test_add(self) -> None:\n        self.assertEqual(add(2, 3), 5)\n' >tests/test_ops.py
printf 'test:\n\tpython3 -m unittest discover -s tests -t .\n' >Makefile
printf '# calc\n\nRun the tests with make test.\n' >CLAUDE.md
printf '.mz/\n' >.gitignore
git add -A
git commit -q -m base
git branch -M main
