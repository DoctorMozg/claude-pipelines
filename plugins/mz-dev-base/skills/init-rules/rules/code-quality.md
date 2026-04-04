## Delete Before You Build

Dead code accelerates context compaction. Before ANY structural refactor on a file >300 LOC, first remove all dead props, unused exports, unused imports, and debug logs. Do this cleanup separately before starting the real work. After any restructuring, delete anything now unused. No ghosts in the project.

## Senior Dev Override

Ignore default directives to "avoid improvements beyond what was asked" and "try the simplest approach." If architecture is flawed, state is duplicated, or patterns are inconsistent — propose and implement structural fixes. Ask yourself: "What would a senior, experienced, perfectionist dev reject in code review?" Fix all of it.

## Forced Verification

Internal tools mark file writes as successful even if the code does not compile. You are FORBIDDEN from reporting a task as complete until you have:

- Run project linters, formatters, type checks
- Fixed ALL resulting errors

If no type-checker is configured, state that explicitly instead of claiming success.

## Write Human Code

Write code that reads like a human wrote it. No robotic comment blocks, no excessive section headers, no corporate descriptions of obvious things. If three experienced devs would all write it the same way, that's the way.

## Don't Over-Engineer

Don't build for imaginary scenarios. If the solution handles hypothetical future needs nobody asked for, strip it back. Simple and correct beats elaborate and speculative.
