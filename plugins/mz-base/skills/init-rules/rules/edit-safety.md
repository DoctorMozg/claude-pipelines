## No Semantic Search

Grep matches text, not symbols. When renaming or changing a function, type, or variable, search separately for:

- Direct calls and references
- Type-level references (interfaces, generics)
- String literals containing the name
- Dynamic imports and require() calls
- Re-exports and barrel file entries
- Test files and mocks

When a code-intelligence plugin provides the LSP tool, use it to find references, and still grep for string literals and dynamic imports, which it can't see.

## One Source of Truth

Never fix a display problem by duplicating data or state. One source, everything else reads from it. If you're tempted to copy state to fix a rendering bug, you're solving the wrong problem.

## Destructive Action Safety

Before deleting a file, check that nothing references it. Don't discard uncommitted changes you didn't make. Ask before pushing, force-pushing, rewriting published history, or bypassing hooks with `--no-verify`.
