#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p docs units
cat >docs/cache.md <<'MD'
# Cache Guide

In today's fast-paced digital landscape, it is crucial to leverage a robust and seamless caching layer. Moreover, this guide will delve into how the cache works and empower you to unlock its full potential.

The cache keeps entries for 90 seconds by default. Set `CACHE_TTL` to change it.
MD
cat >docs/notes.md <<'MD'
# Notes

It is important to note that this file is not part of the unit. Furthermore, it must stay exactly as it is.
MD
cat >units/WU-3.md <<'MD'
# Unit WU-3: Humanize the cache guide

- task: 2026_11_22_orchestrate_eval
- kind: change
- skill: mz-creative:naturalize
- owns: docs/cache.md
- verify: test -s docs/cache.md

## Spec

Rewrite `@file:docs/cache.md` in place so it reads as written by a person. Keep the 90 second default and the `CACHE_TTL` setting exactly. No other choices: no preserved terms, no voice profile, default punctuation rules.
MD
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
