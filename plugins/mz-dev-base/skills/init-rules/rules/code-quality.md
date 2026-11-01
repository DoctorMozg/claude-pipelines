## Forced Verification

A successful write says nothing about whether the code works. Before finishing, run the project's lint, format, typecheck, and test commands on what you changed. Fix errors your change introduced; report pre-existing ones instead of fixing them unasked. If the project has no type checker or tests, say so rather than implying the code was checked.

## Write Human Code

Write code that reads like a human wrote it. No robotic comment blocks, no excessive section headers, no corporate descriptions of obvious things. If three experienced devs would all write it the same way, that's the way.

## YAGNI — You Aren't Gonna Need It

Build for the problem in front of you. Don't add capabilities, parameters, config knobs, abstraction layers, or extension points for needs nobody has stated; each one costs maintenance whether or not the need ever arrives. When a real need appears it will be clearer than your guess about it now, so build it then.

## Clean Up What You Touch

Delete code your change left unused, such as imports, helpers, and branches. Leave unrelated dead code and design problems alone: mention them at the end with a one-line suggestion, and fix them only when asked.

## No Unrequested Backward Compatibility

Do not preserve backward compatibility unless asked. When you change a signature, rename a symbol, or restructure a module, update every call site and delete the old path — no deprecation shims, no compatibility aliases, no dual code paths, no fields kept "just in case." A clean break in a codebase you control is cheaper to maintain than a compatibility layer nobody needs. If the change has real external consumers — a published API, a persisted data format, another team's code — stop and ask whether a migration path is wanted instead of silently adding one or silently breaking them.

## Rule of Three

Don't abstract on the first occurrence — or the second. Two near-identical blocks of code are cheaper to maintain than the wrong abstraction extracted too early. Wait for the third concrete case: by then the real shape of the variation is visible, and the abstraction fits it instead of guessing at it. This tempers DRY — duplication is a smell, but a premature interface, base class, or generic is a worse one. The same applies to indirection: add a layer, wrapper, or seam when a second caller or implementation actually exists, not in anticipation of one.
