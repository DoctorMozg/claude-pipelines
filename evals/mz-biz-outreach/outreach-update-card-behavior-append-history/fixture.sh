#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repo and HOME is, so without this the skill's .mz/ root resolves to HOME.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

run=.mz/outreach/2026_10_28_outreach_research_logistics
mkdir -p "$run/companies" .mz/outreach/active

# Dated today so the skill's target equals its source: no relocation, and no rm (the eval sandbox refuses it).
today=$(date +%Y-%m-%d)

# Stale baseline the user will point at; the active card below holds the accumulated history and must win.
cat >"$run/companies/kestrel-marine.md" <<'EOF'
# Kestrel Marine

**Sector**: Marine manufacturing | **Location**: Aberdeen, UK | **Founded**: 2003
**Size**: 140 | **Score**: 74/100
**Domain**: kestrel-marine.example

---

## Overview

Kestrel Marine builds aluminium workboats in Aberdeen. Baseline research pass.

## Key Contacts

1. **Mikael Dahl** — Operations Director — [LinkedIn](https://www.linkedin.com/in/mikael-dahl-example) — signs off yard tooling spend

- **Emails**: mikael.dahl@kestrel-marine.example
- **Phone**: None found
- **Company LinkedIn**: https://www.linkedin.com/company/kestrel-marine-example

## Outreach Recommendation

Mikael Dahl controls yard tooling spend, and a new workboat order book makes weld rework a live cost.

**Best contact**: Mikael Dahl (Operations Director) via email
**Best angle**: Cutting weld-inspection rework
**Timing**: Neutral, the order book is full until spring

---
*Generated: 2026-10-14 | Sources: Kestrel site, LinkedIn*
EOF

# Target: an active card with letters and a two-entry history.
cat >".mz/outreach/active/${today}_kestrel-marine.md" <<'EOF'
# Kestrel Marine

**Sector**: Marine manufacturing | **Location**: Aberdeen, UK | **Founded**: 2003
**Size**: 140 | **Score**: 74/100
**Domain**: kestrel-marine.example

---

## Overview

Kestrel Marine builds aluminium workboats in Aberdeen. Overview refreshed after the intro call.

## Key Contacts

1. **Mikael Dahl** — Operations Director — [LinkedIn](https://www.linkedin.com/in/mikael-dahl-example) — signs off yard tooling spend

- **Emails**: mikael.dahl@kestrel-marine.example
- **Phone**: None found
- **Company LinkedIn**: https://www.linkedin.com/company/kestrel-marine-example

## Outreach Recommendation

Mikael Dahl controls yard tooling spend, and a new workboat order book makes weld rework a live cost.

**Best contact**: Mikael Dahl (Operations Director) via email
**Best angle**: Cutting weld-inspection rework
**Timing**: Neutral, the order book is full until spring

---
*Generated: 2026-10-14 | Sources: Kestrel site, LinkedIn*

## Outreach Letters

### Mikael Dahl: Email

**Subject**: Fewer weld reworks at Kestrel

Hi Mikael,

Your yard is full until spring, which is when weld rework hurts most. We cut inspection rework on aluminium hulls, and I would like to show you how in 20 minutes.

Thanks,
Sam

*Letters generated: 2026-10-18 | naturalized: yes | light queries: 3 | reverted: 0*

## Interaction History

- **2026-10-03** — Sent intro email to Mikael Dahl
- **2026-10-20** — Mikael replied, asked for a pricing sheet
EOF

# Bystander: another active card plus its sibling baseline, both for other companies.
cat >.mz/outreach/active/2026-10-15_fjordline-shipping.md <<'EOF'
# Fjordline Shipping

**Sector**: Maritime logistics | **Location**: Bergen, Norway | **Founded**: 2011
**Size**: 120 | **Score**: 71/100
**Domain**: fjordline-shipping.example

---

## Overview

Fjordline Shipping runs coastal container feeders between Bergen and Rotterdam.

## Key Contacts

1. **Lars Hovland** — Head of Fleet Operations — [LinkedIn](https://www.linkedin.com/in/lars-hovland-example) — owns vessel tooling decisions

- **Emails**: lars.hovland@fjordline-shipping.example
- **Phone**: None found
- **Company LinkedIn**: https://www.linkedin.com/company/fjordline-shipping-example

## Outreach Recommendation

Lars Hovland decides on vessel tooling, and the winter timetable change opens a window for a short pilot.

**Best contact**: Lars Hovland (Head of Fleet Operations) via email
**Best angle**: Fuel-burn reporting for the winter timetable
**Timing**: Good, timetable planning starts in November

---
*Generated: 2026-10-10 | Sources: Fjordline site, LinkedIn*

## Interaction History

- **2026-10-15** — Called Lars, he wants a demo in two weeks
EOF

cat >"$run/companies/brightline-logistics.md" <<'EOF'
# Brightline Logistics

**Sector**: Freight and logistics | **Location**: Leeds, UK | **Founded**: 2014
**Size**: 85 | **Score**: 78/100
**Domain**: brightline-logistics.example

---

## Overview

Brightline Logistics runs refrigerated trailers for UK grocery chains and is rolling out telematics across its fleet.

## Key Contacts

1. **Priya Nair** — Head of Fleet Technology — [LinkedIn](https://www.linkedin.com/in/priya-nair-example) — owns the telematics rollout

- **Emails**: priya.nair@brightline-logistics.example
- **Phone**: None found
- **Company LinkedIn**: https://www.linkedin.com/company/brightline-logistics-example

## Outreach Recommendation

Priya Nair is the buyer for the telematics rollout, and the autumn peak-season dispatch crunch makes a pilot easy to justify.

**Best contact**: Priya Nair (Head of Fleet Technology) via email
**Best angle**: A pilot that shortens peak-season dispatch
**Timing**: Good, the rollout budget is open until December

---
*Generated: 2026-10-28 | Sources: Brightline site, LinkedIn*
EOF
