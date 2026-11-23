#!/usr/bin/env bash
set -euo pipefail
# deep-research finds its .mz/ root with git; the workspace may already be a repo.
git init -q
mkdir -p units
echo "# eval workspace" >README.md
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m init
# A narrow, stable question; the depth line keeps the wave small and cheap.
cat >units/CX1-rfc-429.md <<'MD'
# Unit CX1-rfc-429: Rate-limit response semantics

- task: 2026_11_23_orchestrate_eval
- kind: context
- skill: mz-research-pipe:deep-research
- owns:
- verify: true

## Spec

Research this question: what HTTP status code and headers does RFC 9110 specify for a 429 response, and does it define Retry-After for it? Cover what the RFC says and where it defers to other documents. Prefer the RFC text itself over blog posts.

Keep it to the smallest depth: 2 subtopics, about 5 pages each, no more than 2 search queries per subtopic.
MD
