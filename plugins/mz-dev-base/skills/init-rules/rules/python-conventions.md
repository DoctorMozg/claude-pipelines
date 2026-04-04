---
paths:
  - '**/*.py'
---

## Structural Typing

Use `Protocol` for structural typing where polymorphism is needed. Avoid unnecessary abstract base classes.

## Testing

Use shared pytest fixtures. Avoid duplicating setup logic inside individual test functions.

## Typing

Use type hints for all function parameters and return types. Strictly type all code. Minimize usage of raw `dict` and `tuple` — always use `TypedDict` or Pydantic models for structured data.

## Organization

Group related logic into classes rather than scattering standalone functions across a package. Simple stateless helpers can remain as module-level functions.
