# Scope Parameter

Canonical source: SKILL_GUIDELINES.md, "Scope Parameter" (repository guidelines, not shipped with the plugin).

Skills that edit code accept `scope:branch|global|working`, and skills that analyze a codebase can accept it too. This file holds the mode definitions and git commands; each skill links here instead of restating them.

## Parsing

Extract `scope:<mode>` from `$ARGUMENTS` case-insensitively and remove it before parsing the rest of the input. When Claude invoked the skill itself, `$ARGUMENTS` may be empty or paraphrased, so also honor a scope the user stated in plain words ("only my uncommitted changes" means `working`), and ask when the mapping is unclear.

## Modes

Run the commands from the project root.

| Mode      | Files                                                                 | How to resolve                                                                                                                                                                                                                             |
| --------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `branch`  | Files changed in commits on this branch since it left the base branch | Base: `git symbolic-ref --quiet --short refs/remotes/origin/HEAD`, else `main`, else `master`. Then `git diff --name-only "$(git merge-base HEAD <base>)" HEAD`. This covers committed work only; uncommitted changes belong to `working`. |
| `working` | Uncommitted changes: staged, unstaged and untracked                   | `git diff --name-only HEAD` plus `git ls-files --others --exclude-standard`                                                                                                                                                                |
| `global`  | Every project file git doesn't ignore                                 | `git ls-files --cached --others --exclude-standard`, minus vendored and generated files, lock files and files over 5,000 lines                                                                                                             |

## Empty scope

Zero files in scope includes running `branch` on the base branch itself. A skill that edits then asks whether to widen the scope to `working` or `global`, or to stop. A read-only skill reports that nothing is in scope and exits. Where nobody can answer, a skill that edits stops with `Status: blocked` and the options in `what_remains`.

## What scope bounds

- **Skills that edit**: scope bounds which existing files agents may edit, and any scan that picks edit targets. Investigation, tests and linters run on the full project so they catch regressions elsewhere.
- **Skills that only analyze**: scope bounds which files are analyzed.
- **Default**: each skill states its default for when `scope:` is left out, and its read and edit boundary, next to its link to this file. Without a stated default, every project file is eligible.
- Every writer dispatch prompt states the edit boundary.
- A skill that saves the resolved list to `scope_files.txt` lists in its final report every pre-existing file the run changed outside that list. Prose can't hold a writer to its boundary, so this check is how a breach gets noticed.

A skill may add its own rules after its link, such as how `scope:` combines with an explicit path argument.
