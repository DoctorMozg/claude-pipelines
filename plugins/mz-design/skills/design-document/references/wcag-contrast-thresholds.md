# WCAG 2.2 Contrast Thresholds

Grep-first reference file. Agents retrieve the specific value they need; do not load the whole file.

## Thresholds (Success Criterion 1.4.3 and 1.4.6)

| Level | Text type   | Minimum ratio |
| ----- | ----------- | ------------- |
| AA    | Normal text | **4.5:1**     |
| AA    | Large text  | **3:1**       |
| AAA   | Normal text | **7:1**       |
| AAA   | Large text  | **4.5:1**     |

## Non-text contrast (Success Criterion 1.4.11)

UI components, graphical objects, focus indicators, and state borders must maintain at least **3:1** contrast against adjacent colors, at AA and above.

## Large-text definition

Text is considered "large" when any of the following holds:

- **18 point** or larger (≈ **24 px** at 96 dpi)
- **14 point bold** or larger (≈ **18.66 px** bold)

Anything smaller is "normal" and must meet the 4.5:1 threshold for AA.

## Luminance formula

Relative luminance `L` of a sRGB color is computed from its linearized channels:

```
R_sRGB = R_8bit / 255
G_sRGB = G_8bit / 255
B_sRGB = B_8bit / 255

R_lin = (R_sRGB <= 0.03928) ? R_sRGB / 12.92 : ((R_sRGB + 0.055) / 1.055) ** 2.4
G_lin = (G_sRGB <= 0.03928) ? G_sRGB / 12.92 : ((G_sRGB + 0.055) / 1.055) ** 2.4
B_lin = (B_sRGB <= 0.03928) ? B_sRGB / 12.92 : ((B_sRGB + 0.055) / 1.055) ** 2.4

L = 0.2126 * R_lin + 0.7152 * G_lin + 0.0722 * B_lin
```

## Contrast-ratio formula

```
contrast = (L_lighter + 0.05) / (L_darker + 0.05)
```

where `L_lighter` is the greater of the two relative luminances and `L_darker` the lesser.

## Worked examples

| Foreground | Background | L1     | L2     | Ratio  | AA normal  | AA large |
| ---------- | ---------- | ------ | ------ | ------ | ---------- | -------- |
| `#000000`  | `#FFFFFF`  | 1.0000 | 0.0000 | 21:1   | ✅         | ✅       |
| `#767676`  | `#FFFFFF`  | 1.0000 | 0.1821 | 4.54:1 | ✅ (tight) | ✅       |
| `#777777`  | `#FFFFFF`  | 1.0000 | 0.1832 | 4.48:1 | ❌         | ✅       |
| `#0066CC`  | `#FFFFFF`  | 1.0000 | 0.1328 | 5.57:1 | ✅         | ✅       |
| `#CCCCCC`  | `#FFFFFF`  | 1.0000 | 0.6038 | 1.61:1 | ❌         | ❌       |

`#767676` on white is the classic "just barely AA-normal" gray.

## Output table format expected in `wcag-report.md`

The writer must produce a table shaped like this:

```markdown
| Token pair                     | FG        | BG        | Role            | Ratio  | AA normal | AA large | AAA normal | AAA large |
| ------------------------------ | --------- | --------- | --------------- | ------ | --------- | -------- | ---------- | --------- |
| `text.primary` / `surface.bg`  | `#1A1A1A` | `#FFFFFF` | body            | 16.1:1 | ✅         | ✅        | ✅          | ✅         |
| `text.muted` / `surface.bg`    | `#767676` | `#FFFFFF` | meta, helper    | 4.54:1 | ✅         | ✅        | ❌          | ✅         |
| `accent.primary` / `text.on_accent` | `#0066CC` | `#FFFFFF` | buttons   | 5.57:1 | ✅         | ✅        | ❌          | ✅         |
```

Every distinct foreground-on-background pair used by the design system must appear in the table. Missing pairs count as a `Critical:` finding from the accessibility-specialist.

## Hard-gate rule

`WCAG_GATE: FAIL` is emitted if **any** pair with role `body`, `heading`, or any text-bearing component fails the AA-normal threshold (4.5:1). Large-text components must meet 3:1. Non-text UI components must meet 3:1.

## Source

- W3C: Web Content Accessibility Guidelines (WCAG) 2.2, Success Criteria 1.4.3, 1.4.6, 1.4.11
  - https://www.w3.org/TR/WCAG22/
  - https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html
- WebAIM: Contrast and Color Accessibility — https://webaim.org/articles/contrast/
