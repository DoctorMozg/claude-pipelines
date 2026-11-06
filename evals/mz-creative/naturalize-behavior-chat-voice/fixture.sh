#!/usr/bin/env bash
set -euo pipefail
# /naturalize finds its .mz/ root with git, and the eval workspace isn't a repository.
git init -q
cat >voice.md <<'PROFILE'
# Voice: Sam, work chat

Measured from Sam's own Slack messages to colleagues over a year.

- Short messages, median 9 words. One thought per message, so a longer reply is 2 or 3 short messages.
- About 20% of messages end with a period. Most end bare or with 👍.
- No em dashes and no ellipsis character. Asides use a spaced hyphen " - ".
- Light commas: "Thanks Ana", no comma before the name.
- Writes "ok", never "okay".
- Acronyms stay bare between colleagues: PR, CI, prod.
- No sign-off. A greeting only opens a thread, as "Hey!" with the point in the same message.
- Don't copy: two spaces after a period, a keyboard habit.
PROFILE
cat >reply.md <<'REPLY'
Hi Ana,
Thank you so much for flagging the deployment issue — I truly appreciate it.
I've taken a thorough look, and it's important to note that the failing CI job is caused by the expired staging certificate; renewing it should resolve the problem.
I'll open a Pull Request (PR) with the fix by 3 PM today.
In the meantime, the production environment is unaffected… so there is no need to roll back.
Okay, please let me know if you have any further questions or concerns.
Best regards,
Sam
REPLY
