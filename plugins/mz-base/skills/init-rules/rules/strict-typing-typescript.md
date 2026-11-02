---
paths:
  - '**/*.{ts,tsx}'
---

## Strict Typing Rules (TypeScript)

- Enable `strict: true` in `tsconfig.json`.
- No `any` — use `unknown` and narrow with type guards.
- Prefer `interface` for object shapes, `type` for unions and intersections.
- All function parameters and returns must be explicitly typed (no reliance on inference for public APIs).
- Use `as const` for literal objects and `satisfies` for type-safe assignments.

### General

- Prefer explicit types at module boundaries (function signatures, class fields, exports).
- Internal variables can use inference when the type is obvious from context.
- Generic type parameters should have meaningful names (`TItem`, not `T`) when there are multiple.
