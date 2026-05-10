"""Synthetic 3-file fixture for /build smoke testing.

Intentionally trivial — the smoke test validates pipeline plumbing, not
algorithmic correctness. /build over this fixture should plan a small
work-unit set, dispatch test-writer and coder, and reach completeness.
"""


def add(a: int, b: int) -> int:
    return a + b


def subtract(a: int, b: int) -> int:
    return a - b
