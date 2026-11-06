#!/usr/bin/env bash
set -euo pipefail
# /naturalize finds its .mz/ root with git, and the eval workspace isn't a repository.
git init -q
cat >refinancing.md <<'EOF'
Subject: Q3 refinancing — next steps

Hi Marta,

I hope this email finds you well! I wanted to reach out regarding the Q3 refinancing discussion — there are a few key takeaways worth highlighting.

First, our leverage is higher than the board would like; net debt to EBITDA closed the quarter at 3.1x, against a covenant ceiling of 3.5x. Second, the €2.4M term loan matures in November, so we need a decision on rolling it over by October 15.

I've put together a comparison of the three lender offers → you'll find it in the shared drive under Treasury/2026. The Northbank offer is the cheapest on paper… but its prepayment penalty is steep.

Could we find 30 minutes this week to align? Please don't hesitate to reach out if you have any questions or concerns.

Best regards,
Tom
EOF
