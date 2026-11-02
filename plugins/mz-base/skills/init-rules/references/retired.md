# Retired and Rewritten Rule Content

Lookup tables for the stale scan in `phases/run.md` Step 5. Update them whenever a rule id is retired or a section is renamed or rewritten.

## Retired rule ids

| Id                              | Retired in | Why                                                                                          |
| ------------------------------- | ---------- | -------------------------------------------------------------------------------------------- |
| `internal-artifact-compression` | 0.50.0     | Described mozg pipeline internals; the guidance now lives in the repo's authoring guidelines |
| `memory-hygiene`                | 0.50.0     | Article-dropping compression had no evidence behind it; prune memory files instead           |

## Sections

These tables catch hand-written copies in CLAUDE.md, outside sentinel blocks. Normalize both the heading and the table entries before comparing: lowercase, drop the leading `#` marks and a trailing colon, delete hyphens and apostrophes, collapse whitespace. A heading matches its Title or any Alias. When Fingerprint is set, the section body must also contain it (case-insensitive). That stops generic headings such as "Logging" or "Testing" from matching the user's own sections.

**Now in**: `retired` means the content is gone, so the section is always proposed for removal. A rule id means that rule carries the current version. Propose removal only when that rule is selected in this run, so the user never loses guidance that isn't installed.

| Title                                   | Aliases                 | Fingerprint            | Now in                   |
| --------------------------------------- | ----------------------- | ---------------------- | ------------------------ |
| Senior Dev Override                     | The Senior Dev Override |                        | retired                  |
| Sub-Agent Swarming                      |                         |                        | retired                  |
| Edit Integrity                          |                         |                        | retired                  |
| Proactive Guardrails                    |                         |                        | retired                  |
| Parallel Batch Changes                  |                         |                        | retired                  |
| Memory File Hygiene                     |                         |                        | retired                  |
| Compressed Style for Internal Artifacts |                         |                        | retired                  |
| Delete Before You Build                 | Delete Before Build     |                        | `code-quality`           |
| Forced Verification                     |                         |                        | `code-quality`           |
| Don't Over-Engineer                     | Do Not Over-Engineer    |                        | `code-quality`           |
| Tooling                                 |                         | linters and formatters | `code-quality`           |
| Context Decay Awareness                 | Context Decay Awarness  |                        | `context-safety`         |
| File Read Budget                        |                         |                        | `context-safety`         |
| Tool Result Blindness                   |                         |                        | `context-safety`         |
| No Semantic Search                      |                         |                        | `edit-safety`            |
| Destructive Action Safety               |                         |                        | `edit-safety`            |
| File Hygiene                            |                         |                        | `housekeeping`           |
| Pre-Implementation Clarity              |                         |                        | `agent-workflow`         |
| Planning                                |                         | questions              | `agent-workflow`         |
| Phased Execution                        |                         |                        | `agent-workflow`         |
| Plan and Build Are Separate Steps       |                         |                        | `agent-workflow`         |
| Information Verification                |                         |                        | `agent-workflow`         |
| Verify Before Reporting                 |                         |                        | `self-evaluation`        |
| Fresh Eyes Pass                         |                         |                        | `self-evaluation`        |
| Error Handling                          |                         | try-catch              | `coding-standards`       |
| Comments                                |                         | why, not what          | `coding-standards`       |
| Testing                                 |                         | focus on behavior      | `coding-standards`       |
| Architecture                            |                         | SOLID                  | `coding-standards`       |
| Commit Messages                         | Git                     | co-authored-by         | `personal-git`           |
| Pre-commit                              |                         | pre-commit run         | `pre-commit-conventions` |
| Testing                                 |                         | pytest fixtures        | `python-conventions`     |
| Structural Typing                       |                         |                        | `strict-typing-python`   |
| Typing                                  |                         | TypedDict              | `strict-typing-python`   |
| Python                                  |                         | Protocol               | `strict-typing-python`   |
| Logging                                 |                         | decision points        | `personal-code-style`    |
| Organization                            |                         | classes                | `personal-code-style`    |
| C++                                     |                         | auto                   | `personal-cpp`           |
| Two-Perspective Review                  |                         |                        | `personal-review`        |
| Bug Autopsy                             |                         |                        | `personal-review`        |
