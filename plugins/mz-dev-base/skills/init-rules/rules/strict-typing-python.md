---
paths:
  - '**/*.py'
---

## Strict Typing Rules (Python)

- All function parameters and return types must have type hints.
- Use `TypedDict` or Pydantic models instead of raw `dict` for structured data.
- Use `Protocol` for structural typing where polymorphism is needed.
- Avoid `Any` unless interfacing with untyped third-party code — add a comment explaining why.
- Use `tuple[str, int]` style (lowercase) over `Tuple[str, int]` for Python 3.10+.

### General

- Prefer explicit types at module boundaries (function signatures, class fields, exports).
- Internal variables can use inference when the type is obvious from context.
- Generic type parameters should have meaningful names (`TItem`, not `T`) when there are multiple.
