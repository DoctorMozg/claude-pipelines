#!/usr/bin/env bash
set -euo pipefail
# /naturalize finds its .mz/ root with git, and the eval workspace isn't a repository.
git init -q
cat >newsletter.md <<'EOF'
# Platform Notes — March

Welcome to another edition of Platform Notes! This month has been a pivotal one for the infrastructure team — and we're excited to share the highlights.

First, the big one: the checkout service now runs on Postgres 16. The migration took eleven days; however, the payoff was immediate. Checkout p95 latency fell from 840 ms to 310 ms, and the nightly batch window shrank from 4 hours to 95 minutes. Lena Ortiz led the cutover, and her runbook is worth reading → it covers every rollback step we rehearsed.

Second, we retired the legacy queue workers on March 14. That removed 38 cron jobs… and roughly 2,100 lines of glue code that nobody wanted to own.

Finally, a reminder: on-call rotations change on April 1. If you haven't confirmed your slot, please do so in the scheduling sheet — it only takes a minute.

As always, our door is open. Reach out with questions, ideas, or feedback; we'd love to hear from you!
EOF
