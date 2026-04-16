# Properties Reference

Source: Obsidian Flavored Markdown frontmatter properties. Grep this file for the specific property type you need — do not load the whole file.

## Default Built-in Properties (Obsidian 1.9+)

- `tags` — list of strings. Use plural; singular `tag:` is deprecated.
- `aliases` — list of strings. Use plural; singular `alias:` is deprecated.
- `cssclasses` — list of strings. Use plural; singular `cssclass:` is deprecated.

## Property Types

| Type        | YAML example                      | Notes                      |
| ----------- | --------------------------------- | -------------------------- |
| Text        | `key: "value"`                    | String value               |
| Number      | `key: 42`                         | Integer or float           |
| Checkbox    | `key: true`                       | Boolean `true` or `false`  |
| Date        | `key: 2026-04-16`                 | ISO 8601 date only         |
| Date & Time | `key: 2026-04-16T14:30`           | ISO 8601 datetime          |
| List        | `key: [a, b, c]`                  | YAML list; also multi-line |
| Links       | `key: ["[[Note1]]", "[[Note2]]"]` | List of wikilinks          |

## Tag Rules

- Valid characters: letters, numbers (but not as the first character), underscores, hyphens, forward slashes.
- Nested tags: `#parent/child` — forward slash creates hierarchy.
- Cannot start with a number.
- Tags are case-insensitive for matching but preserve their original casing for display.

## Multi-line List Syntax

```yaml
tags:
  - tag1
  - tag2
aliases:
  - "Alternative Name"
  - "Another Alias"
```

## Notes

- Frontmatter must be at the very start of the file, delimited by `---` lines above and below.
- Property names are case-sensitive in some contexts — use lowercase by convention.
- The `cssclasses` property applies CSS classes to the note's container element, enabling per-note styling via CSS snippets.
- Links inside list values must be quoted strings: `["[[Note]]"]` not `[[[Note]]]`.
