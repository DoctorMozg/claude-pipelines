#!/usr/bin/env bash
set -euo pipefail
# Eval workspaces aren't git repositories, and gov-review resolves .mz/ through git.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

mkdir -p docs/decisions

record() {
  cat >"docs/decisions/$1" <<EOF
# $2

<!-- mz-gov:agdr start -->
agdr_id: agdr-$3
timestamp: 2026-10-0${3}T10:00:00Z
agent: gov-artifact-writer
model: claude-opus-5-5
trigger: user-prompt
status: accepted
human_signoff: drmozg@2026-10-0${3}T11:00:00Z
<!-- mz-gov:agdr end -->

## Status

$4

## Context

The API needs somewhere to keep login sessions.

## Decision

$5

## Consequences

$6
EOF
}

record 0001-sessions-in-memory.md "1. Keep sessions in memory" 1 Accepted \
  "Sessions live in a dict inside the API process; we rejected Redis for now." \
  "A restart logs everyone out; one API instance only."
record 0002-sessions-in-redis.md "2. Move sessions to Redis" 2 "Accepted. Supersedes ADR-0001." \
  "Sessions move to Redis, chosen over a Postgres table for TTL support." \
  "Restarts keep sessions; Redis becomes a dependency we must run."
record 0002-rate-limits.md "2. Rate-limit login" 3 Accepted \
  "Login is limited to 5 tries a minute per IP, chosen over per-account limits." \
  "Shared NATs hit the limit sooner."
