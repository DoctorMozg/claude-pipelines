#!/usr/bin/env bash
set -euo pipefail
# Eval workspaces aren't git repositories, and do-roast resolves .mz/ through git.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

mkdir -p src

# No manifest on purpose: without a detected stack the web best-practice pass has nothing to search for.
cat >src/billing.py <<'EOF'
# Maintainer: Ivan Petrov <ivan.petrov@example.invalid>
TAX_RATE = 0.07


def create_invoice(customer_id, items, currency, tax_rate, discount, notes, due_days):
    total = 0
    for item in items:
        total += item["price"] * item["qty"]
    total = total * (1 - discount)
    return {"customer": customer_id, "total": round(total * (1 + tax_rate), 2), "currency": currency, "notes": notes, "due_days": due_days}


# def old_total(items):
#     total = 0
#     for item in items:
#         total += item["price"]
#     return total
#     # TODO: remove after the 2.0 migration


def format_total(invoice):
    return f"{invoice['total']} {invoice['currency']}"
    print("formatted")
EOF

cat >README.md <<'EOF'
# Billing

- `create_invoice(...)` builds an invoice dict.
- `refund_invoice(invoice_id)` issues a refund and returns the credit note.
EOF
