# Markdown Preservation Rules — Translator Reference

This file is the authoritative rule set for what a translator agent may and may not rewrite inside a Markdown (or MDX / frontmatter-wrapped) source document. It covers two tables (NEVER translate, ALWAYS translate), frontmatter handling policy, code-fence boundary discipline, the exact Tier-1 structural parity checks the verifier runs, known gotchas that break naive line-based parsers, and grep hints for locating any one section fast. Agents grep this file for the specific element they need (e.g., `rg -A5 'fenced code'`), not read it in full.

## Table A — NEVER Translate

Elements whose content must be preserved byte-identical across source and output. A single altered character here breaks runtime, routing, or the document's machine-readable contract.

| Element                               | Detection                                                                                 | Rationale                                           |
| ------------------------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------- |
| Fenced code blocks (` ` \`\`\`)       | regex ```` ^```[a-zA-Z0-9_+-]*$ ```` open, ```` ^```$ ```` close                          | Code is executable; translating it breaks runtime.  |
| Indented code blocks                  | 4-space or tab-indented lines forming a block                                             | Same rationale.                                     |
| Inline code (`` `code` ``)            | single backtick spans                                                                     | Same rationale.                                     |
| URLs in links                         | `[text](URL)` — the URL part only                                                         | URLs are identifiers; translation invalidates them. |
| URLs in images                        | `![alt](URL)` — the URL part only                                                         | Same rationale.                                     |
| Autolinks                             | `<https://example.com>`                                                                   | Same rationale.                                     |
| HTML tag names                        | `<tag ...>` open and `</tag>` close                                                       | Tag names are part of the document structure.       |
| HTML attribute names                  | `attr=` within a tag                                                                      | Attribute names are part of the schema.             |
| YAML frontmatter keys                 | key side of `key: value` in `---` frontmatter blocks                                      | Keys are programmatic identifiers.                  |
| YAML frontmatter non-prose values     | `date`, `slug`, `draft`, `tags`, `layout`, `permalink`, `author`, `id`, `order`, `weight` | Metadata consumed by build tools, not prose.        |
| JSON/YAML object keys (in i18n files) | key side of `key: value` pairs                                                            | Same rationale as YAML frontmatter.                 |
| Reference link labels                 | `[label]: url "title"` — the `[label]` part                                               | Labels are re-used in `[text][label]` elsewhere.    |
| Footnote markers                      | `[^1]`, `[^note]`                                                                         | Matching pairs must stay aligned.                   |
| Shortcodes / directives               | `:::note`, `{% if %}`, `{{< partial >}}`                                                  | Framework-specific syntax.                          |

### Table A — Concrete Examples

Each row of Table A corresponds to a pattern the agent will actually see in the wild. Match these shapes, then apply the rule. (The outer tilde fence below lets us nest triple-backtick samples without fence ambiguity.)

````markdown
```python
def translate(text: str) -> str:   <-- body stays byte-identical
    return call_llm(text)
```

    # indented code block — four spaces or a hard tab opens it
    for x in items:                <-- body stays byte-identical
        print(x)

Here is `inline_code()` in a paragraph — the backtick span is atomic.

[display label](https://example.com/path?q=1#frag)   <-- URL half frozen
![company logo](/static/img/logo.svg)                 <-- URL half frozen
<https://example.com/rss.xml>                         <-- autolink frozen

<button type="submit" aria-label="submit">Go</button>
^tag   ^attr-name   ^attr-value-id        ^translatable text node

[^1]: Footnote body.    <-- `[^1]` marker frozen; body translatable

:::note                 <-- directive frozen
This is note content.
:::

[api-ref]: https://api.example.com/v1   <-- `[api-ref]` label frozen
````

## Table B — ALWAYS Translate

Elements whose textual content is the human-readable content of the document. These are the agent's target surface.

| Element                          | Detection                                                                            | Rationale                        |
| -------------------------------- | ------------------------------------------------------------------------------------ | -------------------------------- |
| Heading text                     | text after `#` / `##` / etc. markers (not the `#` itself)                            | Human-readable section titles.   |
| Paragraph text                   | top-level prose blocks not inside code or HTML                                       | The primary content.             |
| List item text                   | text after `-`/`*`/`1.` markers                                                      | Prose content.                   |
| Blockquote content               | text after `>` marker on each line                                                   | Prose content.                   |
| Link display text                | `[text]` part of `[text](URL)`                                                       | The visible label users read.    |
| Image alt text                   | `alt` part of `![alt](URL)`                                                          | Accessibility content.           |
| Table cell content               | text between \`                                                                      | `delimiters (not separator rows` |
| HTML content text                | text nodes between HTML tags                                                         | Prose wrapped in markup.         |
| YAML frontmatter prose values    | `title`, `description`, `summary`, `excerpt`, `subtitle`, `caption`, `intro`, `lead` | Human-readable metadata.         |
| JSON/YAML values (in i18n files) | value side of `key: value` pairs                                                     | The whole point of i18n.         |

### Table B — Concrete Examples

The translatable surface, with the preservation boundary marked inline. Everything to the left of the `<--` is the agent's target text.

```markdown
## Section title goes here     <-- translatable (text after `##`)

Paragraph of prose goes here.  <-- translatable (full line)

- First bullet                 <-- translatable (after `-` marker)
- Second bullet

1. First numbered item         <-- translatable (after `1.`)
2. Second numbered item

> Blockquoted prose.           <-- translatable (after `>`)
>> Nested quote prose.         <-- translatable (after `>>`)

[display label](https://example.com)   <-- `display label` translatable
![product screenshot](/img/p.png)       <-- `product screenshot` translatable

| Header A | Header B |         <-- cells translatable
| --- | --- |                    <-- separator row frozen
| Cell 1   | Cell 2   |          <-- cells translatable

<p>HTML-wrapped prose.</p>      <-- text node translatable; `<p>` frozen
```

## Frontmatter Handling

Frontmatter (`---`-delimited YAML at the top of a Markdown file) is split into programmatic keys that must not move and prose values that must be translated. The rules below resolve any key the translator encounters.

- **Default translatable keys**: `title`, `description`, `summary`, `excerpt`, `subtitle`, `caption`, `intro`, `lead`.
- **Default non-translatable keys**: `date`, `slug`, `draft`, `tags`, `layout`, `permalink`, `author`, `id`, `order`, `weight`, `aliases`, `type`.
- **Unknown keys default to non-translatable** — the safer direction. A skipped prose translation is a noticeable miss; a translated slug silently breaks routing.
- **Orchestrator override**: the pipeline-translator dispatch prompt may ship an explicit allowlist of translatable keys that supersedes the defaults for a given task. When present, follow the allowlist verbatim; do not merge with defaults.
- **Value-type guardrail**: boolean (`true` / `false`), integer (`42`), and date (`2026-04-11`, ISO 8601) values are NEVER translated regardless of key name. Translate only when the value is a quoted or bare string of natural-language prose.

Example:

```yaml
---
title: "Getting Started"        # translate
description: "A short intro."    # translate
date: 2026-04-11                 # never translate (date type)
draft: false                     # never translate (bool type)
tags: [docs, intro]              # never translate (list of identifiers)
slug: getting-started            # never translate (routing id)
---
```

## Code-Block Boundary Preservation

Fences are the single highest-risk surface: one dropped backtick and the rest of the document is parsed as code. Enforce these rules before emitting any translation.

- **Byte-identical fence count**: the source fence count must equal the output fence count. The Tier-1 verifier runs ```` rg -c '^```' <src> ```` against `<dst>`; mismatch → fail.
- **Language tags preserved byte-identically**: the trailing identifier on an opening fence (```` ```python ````, ```` ```json ````, ```` ```bash ````, ```` ```tsx ````) is part of the tooling contract — syntax highlighters and doc builders key off it. Copy it character-for-character from source to output.
- **Nested fences are atomic**: a code block may itself contain markdown that contains another fence (e.g., a tutorial showing how to write markdown). Treat the outer fence as atomic: do not descend, do not translate the inner content, do not re-parse it as prose. If the surrounding prose implies a translation is needed, emit an `FYI:` concern and leave the block byte-identical.
- **Indented code blocks are ambiguous**: a 4-space indent can be a code block or a continuation line of a list item depending on context. Prefer fenced blocks wherever possible; when the source uses indented code, leave it byte-identical and emit an `FYI:` concern recommending manual review. Never attempt to translate content that might be code.
- **Tilde fences count too**: `~~~` is valid CommonMark. The fence-count check must run for both fence styles — see the check list in the next section.

## Structural Parity Checks (Tier-1 Verifier)

These checks run automatically against every translated chunk. Any single failure fails Tier-1, and the translator agent retries up to `MAX_VERIFICATION_ATTEMPTS`. Counts are exact integers; only the line-count ratio is a range.

````bash
# Fence count parity (backtick fences).
[ "$(rg -c '^```' <src>)" = "$(rg -c '^```' <dst>)" ]

# Heading count parity (ATX only — see gotchas for setext).
[ "$(rg -c '^#+\s' <src>)" = "$(rg -c '^#+\s' <dst>)" ]

# Bullet list count parity.
[ "$(rg -c '^\s*[-*]\s' <src>)" = "$(rg -c '^\s*[-*]\s' <dst>)" ]

# Numbered list count parity.
[ "$(rg -c '^\s*\d+\.\s' <src>)" = "$(rg -c '^\s*\d+\.\s' <dst>)" ]

# Blockquote line count parity.
[ "$(rg -c '^>' <src>)" = "$(rg -c '^>' <dst>)" ]

# Table row count parity.
[ "$(rg -c '^\|' <src>)" = "$(rg -c '^\|' <dst>)" ]

# Line count delta ≤10% (ratio in [0.9, 1.1]).
src_lines=$(wc -l < <src>); dst_lines=$(wc -l < <dst>)
ratio=$(awk -v s=$src_lines -v d=$dst_lines 'BEGIN { print d / s }')
awk -v r=$ratio 'BEGIN { exit !(r >= 0.9 && r <= 1.1) }'
````

Any parity failure → Tier-1 fails → agent retries up to `MAX_VERIFICATION_ATTEMPTS`. After exhaustion the chunk is flagged `DONE_WITH_CONCERNS` and lifted to Tier-2 for human-readable judgment. Never silently pass a chunk whose structural count diverges.

## Known Gotchas

Line-based grep is fast and exact for most of Markdown but fails on these edge cases. Check for them when a parity count looks suspicious.

- **HTML blocks inside Markdown** can contain unescaped `<` / `>` characters, inline `<br>` with no closing tag, and attributes split across multiple lines. Line-based greps may overcount or undercount tags. Use multiline-aware checks (`rg -U` with a `[\s\S]` pattern) when validating HTML regions — do not trust a single `^<tag` count.
- **Setext-style headings** (`Title\n=====` or `Subtitle\n-----`) do not match `^#+\s`. An author who converts ATX to setext during translation will silently pass the heading count check while reducing the ATX count to zero. Agents must handle both ATX and setext: run `rg -c '^#+\s' || rg -cU '^[A-Za-z].*\n[=-]+$'` and compare the sums.
- **Nested blockquotes** (`>> text`, `> > text`, `>>> text`) can shift line counts when the LLM normalizes spacing inside the quote. Parity on the `^>` count may hold while the nesting depth silently changes — spot-check the max depth by counting leading `>` runs.
- **Tilde fences** (`~~~python ... ~~~`) are valid CommonMark but do not match ```` ^```$ ````. Run a second parity check: `rg -c '^~~~' <src>` == `rg -c '^~~~' <dst>`. Fail Tier-1 if either fence style disagrees.
- **Hard line breaks** encoded as `text  \n` (trailing double space) are fragile. LLMs routinely strip trailing whitespace during generation, collapsing `text  ` into `text` and merging two visual lines. Add a spot check: `rg -c ' {2,}$' <src>` should equal the destination count, or flag a `Nit:` if the delta is small and layout-only.
- **Escaped characters** such as `\*`, `\_`, `\[` must survive verbatim — LLMs tend to "helpfully" unescape them. A count of `rg -c '\\[*_\[\]()]' <src>` should match the destination; a drop indicates semantic corruption in inline markup.
- **Table separator rows** (`|---|---|` or `| :--- | ---: |`) must never be translated and must be counted separately from prose rows so a translator can distinguish "header row" from "body row" in parity checks.
- **Reference-style link definitions** (`[label]: https://…`) live at the bottom of the document and their labels must match `[text][label]` references elsewhere. A label rename in one place and not the other silently breaks the link.

## Grep Access Hints

Use these greps to jump straight to the rule you need; do not load the whole file into context. Run from the worktree root.

```bash
# Jump to the NEVER-translate table.
rg -A30 'Table A' plugins/mz-dev-pipe/skills/translate/references/markdown-preservation-rules.md

# Jump to the ALWAYS-translate table.
rg -A20 'Table B' plugins/mz-dev-pipe/skills/translate/references/markdown-preservation-rules.md

# Find the exact fenced-code rules.
rg -A5 'fenced code' plugins/mz-dev-pipe/skills/translate/references/markdown-preservation-rules.md

# Pull the Tier-1 parity check block.
rg -A25 'Structural Parity Checks' plugins/mz-dev-pipe/skills/translate/references/markdown-preservation-rules.md

# Look up frontmatter policy only.
rg -A15 'Frontmatter Handling' plugins/mz-dev-pipe/skills/translate/references/markdown-preservation-rules.md
```
