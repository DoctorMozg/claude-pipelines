#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repo and HOME is, so without this the skill's .mz/ root resolves to HOME.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

mkdir -p .mz/outreach/active
cat >.mz/outreach/active/2026-10-15_fjordline-shipping.md <<'CARD'
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
CARD
