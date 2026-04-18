# Scope Parameter

Extract `scope:<mode>` from `$ARGUMENTS` if present (case-insensitive). Remove it from the remaining argument text before parsing the rest of the input.

| Mode      | Resolution                                          | Git command                                                                                                                                                                           |
| --------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `branch`  | Files changed on this branch vs base branch         | Detect base: try `main`, then `master`. Run `git diff $(git merge-base HEAD <base>)..HEAD --name-only`. If on the base branch itself (empty diff), warn the user via AskUserQuestion. |
| `global`  | All source files in the repo                        | Honor `.gitignore`. Apply standard exclusions (vendored, generated, lock files, files >5000 LOC).                                                                                     |
| `working` | Uncommitted changes (staged + unstaged + untracked) | `git diff HEAD --name-only` plus `git ls-files --others --exclude-standard`. If no changes exist, warn the user.                                                                      |

**Default** (no `scope:` parameter): all project files are eligible; skills may layer additional detection (path/glob, free-text, existing argument form) on top.

`scope:` controls **which files** the pipeline focuses on or may edit. Researchers, tests, and linters typically run on the full project regardless of scope so they can surface cross-cutting regressions — individual skills document their own edit/read boundaries below the reference to this document.

Skills may document skill-specific overrides or restrictions (e.g. intersect semantics when `scope:` is combined with an explicit argument, edit-only semantics, required focusing questions for `global` mode) after their reference to this file.
