#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p services/billing
cat >services/billing/repo.py <<'EOF'
import sqlite3


def find_invoices(conn: sqlite3.Connection, customer_id: str) -> list[tuple]:
    query = f"SELECT id, total_cents FROM invoices WHERE customer_id = '{customer_id}'"
    return conn.execute(query).fetchall()
EOF
cat >services/billing/handlers.py <<'EOF'
from services.billing import repo


def list_invoices(request, conn):
    customer_id = request.args.get("customer_id", "")
    return {"invoices": repo.find_invoices(conn, customer_id)}
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
