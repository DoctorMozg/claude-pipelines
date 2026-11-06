#!/usr/bin/env bash
set -euo pipefail
# Eval workspaces aren't git repositories, and gov-review resolves .mz/ through git.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

mkdir -p docs/decisions src

cat >docs/decisions/0001-session-store.md <<'EOF'
# 1. Keep sessions in a process-local dict

<!-- mz-gov:agdr start -->
agdr_id: agdr-0001
timestamp: 2026-09-14T10:02:00Z
agent: gov-artifact-writer
model: claude-opus-4-8
trigger: user-prompt
status: executed
human_signoff: pending
<!-- mz-gov:agdr end -->

## Status

Accepted

## Context

The API needs somewhere to keep login sessions.

## Decision

We will keep sessions in a dict inside `src/session.py`.

## Consequences

Sessions are fast to read. A restart logs everyone out.
EOF

cat >docs/decisions/README.md <<'EOF'
# Decision records

- [0001 Keep sessions in a process-local dict](0001-session-store.md)
EOF

cat >docs/decisions/0000-template.md <<'EOF'
# N. Title

## Status

Proposed

## Context

## Decision

## Consequences
EOF

cat >src/session.py <<'EOF'
SESSIONS: dict[str, str] = {}


def start(user_id: str, token: str) -> None:
    SESSIONS[token] = user_id
EOF
