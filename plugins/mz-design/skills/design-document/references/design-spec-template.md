# Canonical Design Document Template

This is the section skeleton the `design-document-writer` agent must follow. Every section is mandatory unless marked optional. Subsections are required where listed.

Grep-first reference: writers can pull just the section they are currently drafting.

## 1. Overview

- **Problem statement** — what user pain or business need this design addresses
- **Target audience** — primary and secondary user personas
- **Success metrics** — measurable signals the design is working (task completion, time-to-action, error rate, NPS, etc.)
- **Non-goals** — explicitly out of scope

## 2. User Flows

- **Primary flow** — the happy path from entry to completion for the main task
- **Secondary flows** — at least 2 common variations (edit, delete, skip)
- **Error/recovery flows** — what happens when the user hits validation, auth, or network errors
- Each flow must include a Mermaid `flowchart` diagram

## 3. Information Architecture

- **Sitemap / structure tree** — Mermaid graph showing screen hierarchy
- **Navigation model** — top-nav, sidebar, tabs, stacked views, etc. State which and why
- **Content inventory** — what information lives where, grouped by section

## 4. Layout & Grid

- **Grid system** — column count, gutter, margin, baseline (e.g., 12-col, 24px gutter, 8px baseline)
- **Container widths** — max content width, fluid vs fixed regions
- **Alignment rules** — what anchors to what; left-aligned text, centered callouts, etc.

## 5. Components

For every distinct component introduced in the design, document:

- **Purpose** — what job the component does in the UI
- **Anatomy** — labeled parts (container, leading icon, label, trailing action, etc.) — use an ASCII diagram
- **Variants** — size (sm/md/lg), emphasis (primary/secondary/tertiary), tone (neutral/success/warning/danger)
- **States** — default, hover, active, focus, disabled, loading, error, empty
- **Usage rules** — when to use, when not to, pairing constraints

## 6. Color System

- **Palette** — every semantic token listed: `text.primary`, `text.muted`, `text.on_accent`, `surface.bg`, `surface.raised`, `border.default`, `accent.primary`, `accent.primary.hover`, `state.success`, `state.warning`, `state.danger`, `state.info` (as a minimum)
- **Hex values** — exact values for light and dark themes if both supported
- **Role mapping** — which token applies to which use (body text, link, button background, etc.)
- **Harmony rationale** — why this palette (complementary, analogous, triadic, monochrome-with-accent, etc.)

## 7. Typography

- **Type families** — primary (body), secondary (display or monospace if used), with fallback stacks
- **Type scale** — 6–8 sizes with line-heights and letter-spacing (e.g., `display/48/56/-0.02`, `h1/32/40/-0.01`, `body/16/24/0`, `caption/12/16/0.01`)
- **Weights** — which weights are used and when
- **Pairing rationale** — why these families complement each other

## 8. Spacing & Sizing

- **Spacing scale** — `4, 8, 12, 16, 24, 32, 48, 64` (or chosen equivalent)
- **Component sizing** — touch target minimum (44×44 per Apple HIG, 48×48 per Material), button heights, input heights
- **Density options** — compact/cozy/comfortable if multi-density

## 9. Motion & Interaction

- **Easing curves** — which curves are used (standard, decelerate, accelerate, sharp) with values
- **Durations** — micro-interaction (80–120ms), component transition (160–240ms), page transition (240–360ms)
- **Micro-interactions** — hover, focus, click, drag, drop feedback — specify what changes and how
- **Gestures** (if touch/mobile) — tap, long-press, swipe, pinch, drag targets
- **Motion-reduction** — what is preserved and what is disabled when `prefers-reduced-motion` is set

## 10. Responsive Strategy

- **Breakpoints** — table of breakpoints with names (e.g., `xs < 480`, `sm 480–767`, `md 768–1023`, `lg 1024–1439`, `xl ≥ 1440`)
- **Per-breakpoint layout shifts** — what changes at each breakpoint (column count, nav collapse, font scale)
- **Touch vs pointer** — how hover affordances degrade on touch
- **Orientation handling** — if relevant

## 11. States

Document these states explicitly wherever they apply:

- **Loading** — skeleton, spinner, progressive reveal
- **Empty** — zero-data state with a clear next action
- **Error** — inline error, toast, full-page error
- **Disabled** — why, and how the user learns why
- **Focus** — visible focus ring that meets 3:1 non-text contrast
- **Hover** — pointer-only; must not be the only affordance for an action
- **Active / pressed** — click/tap feedback
- **Selected** — for toggle, tab, option components

## 12. Accessibility

- **Conformance target** — WCAG 2.2 AA (default) or AAA
- **Keyboard map** — tab order, arrow-key navigation within components, escape behavior, enter behavior
- **Screen reader semantics** — landmark roles, ARIA labels, live regions for dynamic content
- **Focus management** — where focus goes on route change, modal open/close, error surfacing
- **Color independence** — no information conveyed by color alone
- **Motion sensitivity** — `prefers-reduced-motion` support
- **Target sizes** — minimum interactive target size per platform (see §8)

## 13. Design Rationale

- **Key decisions and the alternatives rejected** — for each non-obvious choice, list what you considered and why the chosen option wins
- **Constraints honored** — how the design respects the codebase, brand, or platform constraints identified in research
- **Open trade-offs** — tensions the design leaves unresolved and why

## 14. Open Questions

- Unresolved questions for product, engineering, or the user
- Explicit "needs decision" items before implementation can start
