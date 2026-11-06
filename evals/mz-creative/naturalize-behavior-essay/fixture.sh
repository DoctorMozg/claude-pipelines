#!/usr/bin/env bash
set -euo pipefail
# /naturalize finds its .mz/ root with git, and the eval workspace isn't a repository.
git init -q
cat >lisbon.md <<'EOF'
Moving to Lisbon in 2019 was, without a doubt, the most transformative decision of my life. It wasn't just a change of address — it was a profound shift in how I approached work, friendship, and time itself.

I arrived with two suitcases and three hundred euros; I had no job, no apartment, and only a few words of Portuguese. The first month was a whirlwind of challenges. I rented a tiny room in Alfama, above a bakery that started work at 4 a.m. The smell of bread became my alarm clock…

Slowly, though, the city began to reveal itself. A neighbor named Rui taught me to order coffee properly, "uma bica, por favor," and to never rush a conversation at the counter. My landlady, Dona Fátima, insisted I eat Sunday lunch with her family for my first six weeks — an act of kindness I still think about.

In the end, Lisbon taught me that belonging isn't something you find; it's something you build, one small ritual at a time. Looking back, I wouldn't trade those uncertain early days for anything → they made me who I am today.
EOF
