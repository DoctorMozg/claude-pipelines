#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p scripts
cat >README.md <<'EOF'
# ops-scripts

Small maintenance scripts for the log server.
EOF
cat >scripts/rotate_logs.py <<'EOF'
import gzip
import shutil
from pathlib import Path


def rotate(log_dir: str, keep: int = 5) -> list[str]:
    archived = []
    for log in sorted(Path(log_dir).glob("*.log"))[:-keep]:
        target = log.with_suffix(".log.gz")
        with log.open("rb") as src, gzip.open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
        log.unlink()
        archived.append(str(target))
    return archived
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
