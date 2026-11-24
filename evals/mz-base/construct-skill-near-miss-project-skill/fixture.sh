#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$(dirname 'manage.py')"
cat >'manage.py' <<'MD'
#!/usr/bin/env python
import django
MD
mkdir -p "$(dirname 'requirements.txt')"
cat >'requirements.txt' <<'MD'
Django==5.1
MD
mkdir -p "$(dirname 'apps/billing/migrations/0001_initial.py')"
cat >'apps/billing/migrations/0001_initial.py' <<'MD'
# initial
MD
mkdir -p "$(dirname 'apps/billing/migrations/0002_squashed_0007.py')"
cat >'apps/billing/migrations/0002_squashed_0007.py' <<'MD'
# squashed
MD
