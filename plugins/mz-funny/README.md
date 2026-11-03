# mz-funny

mz-funny roasts your code in a character voice (a pirate, a drill sergeant, a hilltop oracle and four others) and ties every joke to a real finding. `/do-roast` first reads the target, measures its structure, checks the docs against the code and compares it with current best practice for your stack. Only then does a persona write the roast, and it may embellish tone but not invent a bug. It is for developers who want a funny read of their code, with receipts.

**Works in:** Claude Code and Cowork. `do-roast` hands the writing to a `roast-<persona>` agent, and claude.ai chat loads skills but ignores agents, so nobody is there to deliver the roast.

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-funny
```

## Usage

```text
/do-roast <persona> <freeform target — path, branch, text, or natural-language scope>
```

The persona is one of the seven below, case-insensitive. A missing persona or target gets a question, not a guess. The target can be:

- **Files or directories.** Any path that exists.
- **A branch diff.** `branch:main` or `--diff main` roasts what your current branch changed since it split from `main`.
- **Raw text.** Wrap it in quotes.
- **A description.** "the session manager" works. The skill offers up to four candidate files and asks which to roast.

There is no PR fetching. To roast a PR, check out its branch and diff it against its base.

```text
/do-roast pirate src/billing/invoice.py
/do-roast drill-sergeant branch:main
/do-roast oracle the session manager
/do-roast caveman "if x == True: return True else: return False"
```

You get a short teaser in the chat and a full report at `.mz/reports/<date>_roast_<persona>_<slug>.md`: the roast, the numbered dossier behind it, and a source disclosure. Each roast paragraph cites `(Finding N)`, so you can check it against the evidence. A target with nothing to find gets no roast. The run stops and says so.

## Characters

| Persona          | Voice                                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------------------------ |
| `caveman`        | Pre-linguistic Hulk-speak that smashes anything abstract.                                              |
| `goblin`         | Cockney scrapyard goblin who bolts more on everything, shouts MORE BOLTS and calls clever code dainty. |
| `pirate`         | West Country sea-dog in the Robert Newton tradition, judging whether the code sails or sinks.          |
| `viking`         | Skald who speaks in kennings and asks whether the code will be sung in any hall or forgotten.          |
| `dwarf`          | Scottish-brogue master craftsman who enters every flaw in the clan's grudge book.                      |
| `drill-sergeant` | Gunnery Sergeant drill instructor who barks insults in CAPS. Profanity allowed.                        |
| `oracle`         | Disappointed hilltop seer in inverted syntax, reading every bug as an ill omen.                        |

All seven roast code, never people: no author names, no git blame, no slurs.

## Data and network

**Reads.** The files you point it at, their siblings, the top-level `README.md`, `docs/` if present, and dependency manifests such as `package.json` or `pyproject.toml` to detect your stack. For a branch target it runs `git diff <branch>...HEAD --stat`. Its shell access is limited to `git rev-parse`, `git diff`, `mkdir`, `date`, `printf`, `sha256sum` and `shasum`, so no linters and no `git blame`.

**Writes.** Plain files under `.mz/` at the project root: task state, dossier and raw roast in `.mz/task/<task_name>/`, the report in `.mz/reports/`, and a web-research cache in `.mz/research/` that expires after seven days. No step in the skill edits your source, and the persona agents have only Read, Grep and Glob.

**Network.** The best-practice check runs two to four `WebSearch` queries and fetches pages with `WebFetch`, limited to official and standards sources. Queries name your detected stack and versions, and may mention a pattern seen in your code. A fresh cache for the same stack skips them. The skill has no `gh` and no MCP tools.

**Hooks and the author.** The plugin ships no hooks, scripts or MCP servers. Nothing is sent to the author and there is no telemetry. As in any Claude Code session, your prompts and the files Claude reads go to the model you use. [PRIVACY.md](https://github.com/DoctorMozg/claude-pipelines/blob/master/PRIVACY.md) has the details.

## Support

- Issues: https://github.com/DoctorMozg/claude-pipelines/issues
- Email: drmozg@gmail.com
- Privacy: https://github.com/DoctorMozg/claude-pipelines/blob/master/PRIVACY.md

## License

MIT
