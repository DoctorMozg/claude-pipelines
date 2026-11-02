#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib/fixture.sh"
init_project
write_memory "- [2026-10-01] Use UTC timestamps everywhere." ""
write_lessons "" ""
# The misplaced file the correction is about, next to one that already follows the convention.
mkdir -p migrations db/migrations
printf 'CREATE INDEX orders_created_at_idx ON orders (created_at);\n' > migrations/20261101_add_orders_index.sql
printf 'CREATE TABLE orders (id bigint PRIMARY KEY, created_at timestamptz NOT NULL);\n' > db/migrations/MIG-20261020-create-orders.sql
