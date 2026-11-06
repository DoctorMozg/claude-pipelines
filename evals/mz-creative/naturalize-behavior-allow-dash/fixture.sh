#!/usr/bin/env bash
set -euo pipefail
# /naturalize finds its .mz/ root with git, and the eval workspace isn't a repository.
git init -q
cat >cover_letter.md <<'LETTER'
Dear Hiring Team,

I am writing to express my strong interest in the Staff Engineer role at Northwind — a position that aligns seamlessly with my experience. Over the past six years at Brightline, I led the migration from MongoDB to Postgres; the result was a drop in p95 latency from 900 ms to 120 ms. Moreover, I built the data-access layer that made the migration possible — and I mentored four engineers along the way.

I would welcome the opportunity to discuss how my expertise can contribute to Northwind's continued success. Thank you for your time and consideration.

Sincerely,
Alex Morgan
LETTER
