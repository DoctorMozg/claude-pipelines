## Logging

- Always add debug/info/warning logs at meaningful decision points and boundaries.
- Don't log trivial operations, hot paths, or simple property accessors.

## Error Handling

- Explicit error handling with try-catch blocks.
- Write meaningful error messages.
- Avoid generic errors if possible.
- Always log errors for debugging.

## Comments

- Use comments for WHY, not WHAT.
- Code should be self-documenting if possible.
- Comments should always explain business logic or non-obvious decisions.
- Comments must be in English.

## Testing

- Focus on behavior, not implementation details.
- Tests should be meaningful and test logic.
- Always come up with corner cases and create tests for them.
- Group into suites by features.
- Testing setup should be done outside of test and reused as much as possible.

## Architecture

- Prefer modular, loosely-coupled design.
- Use dependency injection for testability.
- Separate concerns (Controllers, Services, Repositories, etc).
- Follow SOLID principles.
- Follow DRY — avoid code duplication. Always scan code for reusable parts and extract them before creating new code.
- Write smaller functions with specialized functionality.
- Do not over-engineer.
- Make code structured, separated, isolated, so it is easy to understand.
- Use interface abstractions at module boundaries for testability and decoupling.
- Check modified code for smell (too complicated, too many parameters, etc.) — refactor if possible.
- Functions with >4 parameters suggest a missing abstraction — consider a config/params object.
- When creating a public function, always validate inputs.

## C++

- Use `auto` where possible instead of explicit types.

## Tooling

- Always check changes made using project's linters and formatters.
