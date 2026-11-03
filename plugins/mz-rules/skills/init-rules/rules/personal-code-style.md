## Logging

- Add debug, info, and warning logs at meaningful decision points and boundaries, and log errors where they are handled.
- Don't log trivial operations, hot paths, or simple property accessors.

## Comment Length

Keep every comment, including doc comments, to one or two lines.

## Function Signatures

- More than four parameters suggests a missing abstraction; consider a config or params object.
- Treat every public function as a boundary and validate its inputs.

## Python Organization

Group related logic into classes rather than scattering standalone functions across a package. Simple stateless helpers can remain module-level functions.
