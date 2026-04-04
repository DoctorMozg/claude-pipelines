## Edit Integrity

Before EVERY file edit, re-read the file. After editing, read it again to confirm the change applied correctly. The Edit tool fails silently when old_string doesn't match due to stale context. Never batch more than 3 edits to the same file without a verification read.

## No Semantic Search

You have grep, not an AST. When renaming or changing any function/type/variable, you MUST search separately for:

- Direct calls and references
- Type-level references (interfaces, generics)
- String literals containing the name
- Dynamic imports and require() calls
- Re-exports and barrel file entries
- Test files and mocks

Do not assume a single grep caught everything.

## One Source of Truth

Never fix a display problem by duplicating data or state. One source, everything else reads from it. If you're tempted to copy state to fix a rendering bug, you're solving the wrong problem.

## Destructive Action Safety

Never delete a file without verifying nothing else references it. Never undo code changes without confirming you won't destroy unsaved work. Never push to a shared repository unless explicitly told to.
