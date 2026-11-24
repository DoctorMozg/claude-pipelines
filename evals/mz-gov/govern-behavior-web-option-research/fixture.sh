#!/usr/bin/env bash
set -euo pipefail
# Eval workspaces aren't git repositories, and govern resolves .mz/ through git.
git init -q

mkdir -p src docs/decisions
cat >README.md <<'MD'
# tallyapi

Billing API. Runs as three instances behind a load balancer, with one Postgres 16 database.
MD
cat >src/session.py <<'PY'
SESSIONS: dict[str, str] = {}


def start(user_id: str, token: str) -> None:
    SESSIONS[token] = user_id


def user_for(token: str) -> str | None:
    return SESSIONS.get(token)
PY
cat >docs/decisions/0001-sessions-in-memory.md <<'MD'
# 1. Keep sessions in a process-local dict

<!-- mz-gov:agdr start -->
agdr_id: agdr-0001
timestamp: 2026-06-02T10:00:00Z
agent: gov-artifact-writer
model: claude-opus-5-5
trigger: user-prompt
status: accepted
human_signoff: drmozg@2026-06-02T10:30:00Z
<!-- mz-gov:agdr end -->

## Status

Accepted

## Context

One API instance, and sessions only need to live as long as the process.

## Decision

Sessions live in a dict in `src/session.py`.

## Consequences

A restart logs everyone out. A second instance would not see the first one's sessions.
MD
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m init
