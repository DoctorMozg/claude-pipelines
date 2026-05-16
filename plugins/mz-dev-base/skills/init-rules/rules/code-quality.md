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

## YAGNI — You Aren't Gonna Need It

Build for the problem in front of you, not the one you imagine. Don't add capabilities, parameters, config knobs, abstraction layers, or extension points for needs nobody has stated — each one is a bet on a future you can't see, and it costs maintenance from the day it lands whether the bet pays off or not. If a solution handles hypothetical future scenarios, strip it back: simple and correct beats elaborate and speculative. When a real need appears it will be clearer and more specific than your guess about it now — build it then.

## No Unrequested Backward Compatibility

Do not preserve backward compatibility unless asked. When you change a signature, rename a symbol, or restructure a module, update every call site and delete the old path — no deprecation shims, no compatibility aliases, no dual code paths, no fields kept "just in case." A clean break in a codebase you control is cheaper to maintain than a compatibility layer nobody needs. If the change has real external consumers — a published API, a persisted data format, another team's code — stop and ask whether a migration path is wanted instead of silently adding one or silently breaking them.

## Rule of Three

Don't abstract on the first occurrence — or the second. Two near-identical blocks of code are cheaper to maintain than the wrong abstraction extracted too early. Wait for the third concrete case: by then the real shape of the variation is visible, and the abstraction fits it instead of guessing at it. This tempers DRY — duplication is a smell, but a premature interface, base class, or generic is a worse one. The same applies to indirection: add a layer, wrapper, or seam when a second caller or implementation actually exists, not in anticipation of one.
