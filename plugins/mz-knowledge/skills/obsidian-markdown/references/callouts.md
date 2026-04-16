# Callout Types Reference

Source: Obsidian Flavored Markdown callouts. Grep this file for the specific callout type you need — do not load the whole file.

## Syntax

```
> [!type] Optional Title
> Content line 1
> Content line 2
```

- Foldable collapsed by default: `> [!type]- Title`
- Foldable expanded by default: `> [!type]+ Title`
- Nested: double the `>` prefix for each additional level.

## All Types and Aliases

| Type     | Aliases            |
| -------- | ------------------ |
| note     | (none)             |
| abstract | summary, tldr      |
| info     | (none)             |
| todo     | (none)             |
| tip      | hint, important    |
| success  | check, done        |
| question | help, faq          |
| warning  | caution, attention |
| failure  | fail, missing      |
| danger   | error              |
| bug      | (none)             |
| example  | (none)             |
| quote    | cite               |

## Notes

- Custom callout types can be created via CSS snippets.
- Title is optional; if omitted, the type name is used, capitalized.
- Content supports full Markdown, including nested callouts, lists, code blocks, and images.
- Aliases render identically to their primary type — choose whichever reads best in context.
