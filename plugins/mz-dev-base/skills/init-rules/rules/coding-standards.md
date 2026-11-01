## Error Handling

- Catch only errors you can meaningfully handle; let unexpected ones propagate and fail loudly.
- Never swallow an exception — an empty `except` or catch-then-`return None` turns a clear crash into a silent bug found far later.
- Validate input where it enters the system (user input, network, files, external APIs). Don't re-validate the same value in every internal call.
- Error messages say what failed and with which value. Prefer specific error types over generic ones.

## Comments

- Use comments for WHY, not WHAT.
- Code should be self-documenting if possible.
- Comments should explain business logic or non-obvious decisions.
- Comments must be in English.

## Testing

- Test behavior, not implementation details. Assertions check outcomes, not merely that code ran or a mock was called.
- Cover the corner cases your change introduces.
- Group tests into suites by feature, and share setup instead of repeating it in each test.
- Size new tests like the neighboring ones; don't add tests nobody needs.

## Architecture

- Keep modules loosely coupled, each with one clear responsibility. Keep I/O, business logic, and presentation apart.
- Prefer small functions that do one thing.
- Pass dependencies in where that makes code testable. Add an interface or layer only when a second implementation or caller exists; a test double counts.
