<p align="center"><img src="https://raw.githubusercontent.com/DoctorMozg/claude-pipelines/master/assets/hero/mz-gov.webp" alt="Mozg Governance: AI-era dev governance" width="100%"></p>

# Mozg Governance (`mz-gov`)

mz-gov turns a substantial design decision into a reviewed, durable record: an ADR, RFD or design doc in `docs/`, with an AI-provenance block and a human's recorded sign-off. It's for solo developers and small teams building with AI coding agents who want the reasoning behind agent-proposed changes written down and approved by a person. `/govern` first asks you what you want from the decision and researches the code and the options, then routes it to the right artifact and pressure-tests it with a critic panel before asking for sign-off. `/gov-init` installs a CLAUDE.md policy that tells Claude to run `/govern` on its own, and `/gov-review` audits the records you already have.

**Works in:** Claude Code and Cowork. Installing mz-gov also installs `mz-base`, whose researchers `govern` dispatches. `govern` and `gov-review` dispatch agents, which claude.ai chat doesn't load. `gov-init` dispatches none but edits `CLAUDE.md` on disk, so run it in Claude Code.

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-gov
```

## How it works

An agent **proposes** a decision, a human **approves** it. Every governed decision carries machine-readable provenance (agent, model, timestamp, trigger) and a recorded sign-off, which closes the rubber-stamp gap that AI-authored changes are prone to.

`govern` first screens the decision. A routine change, such as a behavior-preserving refactor, stops there with a one-line exemption note. For anything else it reads the project, its existing records and the code the decision names, then asks you up to four questions in one go: where the decision stands, which options are in play, what matters most, and whether it replaces an existing record. Researchers look into what your answers point at, and the decision is routed to an ADR, RFC/RFD or design doc, drafted from your answers and the research, critiqued, gated behind your sign-off, and then written to `docs/`.

The artifact follows where the decision will stand when the run ends:

| You want to…                                    | You get    |
| ----------------------------------------------- | ---------- |
| choose between options with govern's help       | ADR        |
| record a decision you already made              | ADR        |
| put an open question to the team for discussion | RFD        |
| specify how a decided change gets built         | design doc |

"Should we use X or Y?" becomes an ADR: govern's critics weigh the options and your sign-off settles the choice. An RFD is for a decision that has to stay open for other people.

`gov-init` installs a concise governance policy into your `CLAUDE.md` so the pipeline fires on the decisions that matter. `gov-review` first runs a script over the records for the mechanical checks (status, provenance and sign-off, missing sections, supersede links, numbering), then scores each one against a six-axis completeness rubric. It never edits them.

## Skills

| Skill          | Command       | Inputs                                                                    | Output                                                          |
| -------------- | ------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------- |
| **govern**     | `/govern`     | A decision/change to govern, optional `artifact:adr\|rfd\|design`, `rich` | A numbered artifact in `docs/` with provenance + human sign-off |
| **gov-init**   | `/gov-init`   | `[project\|global] [--force] [--uninstall]`                               | A sentinel-wrapped governance policy block in `CLAUDE.md`       |
| **gov-review** | `/gov-review` | `[path-or-glob]`                                                          | A rubric-scored audit report in `.mz/reviews/`                  |

## The govern pipeline

```
/govern "switch the session store from in-memory to Redis"
  │
  ├─ Phase 0: Setup + AI-provenance capture
  │     └─ gov-provenance-recorder (haiku) — provenance.md, human_signoff: pending
  ├─ Phase 1: Interview
  │     ├─ gov-router (sonnet) — screen: is any artifact needed? no → exemption note, stop
  │     ├─ up to 4 questions: stage, options, priorities, related record → brief.md
  │     └─ pipeline-researcher (code) + pipeline-web-researcher per outside technology → research.md
  ├─ Phase 2: Propose
  │     └─ gov-router (sonnet) — which artifact, how heavy; draft.md from brief + research
  ├─ Phase 3: Discuss  (scaled by decision weight, max 3 iterations)
  │     ├─ heavy → alternatives / reversibility / blast-radius / assumptions (opus, parallel)
  │     │          └─ gov-discussion-synthesizer (sonnet)
  │     └─ light → gov-critic-quick (sonnet, single pass)
  ├─ Phase 4: Decide
  │     └─ human sign-off gate (verbatim artifact + provenance)
  ├─ Phase 5: Record
  │     └─ gov-artifact-writer (sonnet) — docs/decisions|rfcs|design/NNNN-*.md
  └─ Phase 6: Enforce
        └─ link to commit/PR, advance status where warranted, recommend /build
```

Heavy means an RFD, a design doc, an ADR weighing three or more options, or an ADR whose choice is made during the run. Light is left for recording a decision already made between fewer than three options. When nobody can answer the interview, open points become stated assumptions in the draft; the sign-off still needs a person. Phase 6 only recommends the next skill and never runs it.

## Artifacts and where they live

| Artifact                      | Location                        | When                                                         |
| ----------------------------- | ------------------------------- | ------------------------------------------------------------ |
| ADR (Nygard or MADR)          | `docs/decisions/NNNN-title.md`  | A decision is made, before or during the run: record the why |
| RFC / RFD (Oxide lifecycle)   | `docs/rfcs/NNNN-title.md`       | A decision stays open for the team: structure the debate     |
| Design doc (Google 5-section) | `docs/design/NNNN-title.md`     | A decision is made: specify the build                        |
| AI-provenance (AgDR)          | embedded in the artifact header | Every governed decision                                      |

The plugin writes durable artifacts to `docs/` and leaves committing them to you. Transient pipeline state lives under `.mz/task/`.

## Agents

All agents are pipeline-only: the skills dispatch them, and you don't call them directly. In Phase 1 `govern` also dispatches two agents from `mz-base`: `pipeline-researcher` for the code and `pipeline-web-researcher` for outside technology the decision depends on.

| Agent                        | Model  | Role                                                          |
| ---------------------------- | ------ | ------------------------------------------------------------- |
| `gov-router`                 | sonnet | Decides whether an artifact is required, and which            |
| `gov-provenance-recorder`    | haiku  | Formats the AI-provenance block                               |
| `gov-critic-alternatives`    | opus   | Are the considered options complete? Is the choice justified? |
| `gov-critic-reversibility`   | opus   | One-way or two-way door? Is irreversibility warranted?        |
| `gov-critic-blast-radius`    | opus   | What does this affect downstream?                             |
| `gov-critic-assumptions`     | opus   | What unstated assumptions does this rest on?                  |
| `gov-critic-quick`           | sonnet | All four lenses in one pass, for lightweight decisions        |
| `gov-discussion-synthesizer` | sonnet | Merges the critic panel into one verdict                      |
| `gov-artifact-writer`        | sonnet | Writes the numbered durable artifact to `docs/`               |
| `gov-audit-reviewer`         | opus   | Scores existing artifacts against the review rubric           |

## Usage

Govern a decision. The router picks the artifact type. Add `artifact:adr`, `artifact:rfd` or `artifact:design` to force one, and `rich` for the MADR variant of an ADR:

```
/govern "adopt optimistic locking for the inventory table"
/govern "move session storage to Redis" artifact:rfd
```

Install the governance policy so Claude invokes the pipeline on substantial decisions. `project` is the default, and `global` targets `~/.claude/CLAUDE.md`:

```
/gov-init project
```

Audit your existing decision records. With no argument, `/gov-review` checks `docs/decisions`, `docs/rfcs` and `docs/design`:

```
/gov-review docs/decisions
```

## Data and network

**Decision records and provenance.** `govern` writes to your project's `docs/` only after you approve. Phase 4 shows the full draft, the panel verdict and the provenance block, then asks for Approve or Reject. Approve stamps `human_signoff: <user>@<ISO-8601>` and unlocks `gov-artifact-writer`. Reject writes nothing to `docs/`. There's no auto-approve mode, so an unattended run waits at the gate. Before sign-off, your interview answers (`brief.md`), the research, the draft, routing, critic reviews and `provenance.md` (still `human_signoff: pending`) exist only as scratch files under `.mz/task/`. After sign-off, the record is written to `docs/decisions/`, `docs/rfcs/` or `docs/design/` with the provenance fence in its header, and Phase 6 appends a `## Provenance / Links` section to it.

**CLAUDE.md.** After you approve, `gov-init` writes one block into `./CLAUDE.md` (project scope, the default) or `~/.claude/CLAUDE.md` (global scope). The block sits between `<!-- mz-gov:governance-policy v=<version> start -->` and `<!-- mz-gov:governance-policy end -->` comments, and you see the exact text first. Reject, or no answer, writes nothing. The block is an instruction to Claude: in later sessions that load the file, Claude is told to run `/govern` itself before it builds a substantial, ambiguous design decision into code. `/govern` still stops at the sign-off gate. Global scope puts the instruction in your user-level file, so it applies to every project.

To remove it, run `/gov-init project --uninstall` or `/gov-init global --uninstall`, matching where you installed it. Removal asks for approval too, deletes the block and one adjacent blank line, and never deletes `CLAUDE.md` itself. Re-running without `--force` changes nothing. With `--force`, only the text between the sentinels is replaced.

**GitHub.** Only `govern` touches GitHub, in Phase 6, to find the open PR for the current branch so its URL can go into the artifact. `skills/govern/phases/enforce.md` tries two routes in order: first `gh pr view --json number,url,title`, then a GitHub MCP server if the session has one. The lookup names the repository owner, repository and branch, and no skill reads a token itself. All of it is read-only. The plugin never opens, edits or comments on a PR, and never pushes or commits. If every route fails, or the directory isn't a git repository, the artifact records that no PR was found.

**Local state, hooks and the author.** Task state and scratch files are plain files under `.mz/` at the project root: `.mz/task/<task_name>/` for each run, `.mz/reviews/` for `gov-review` reports, and a `decision` entry appended to `.mz/journal.md` when a decision is recorded. mz-gov ships no hooks. `gov-review` runs `scripts/gov-check.sh`, which only reads the records under review and their folders. **Web.** Only `govern` reaches the web, in Phase 1, and only when the decision depends on outside technology such as a library, a service, a provider's API or a hosted product, whether as an option or as something every option must handle: it dispatches `pipeline-web-researcher`, up to three, which sends search queries and fetches public pages about that technology. The queries name the technology and the questions your priorities raise, and the researcher gets the decision and your answers to work from. Your code isn't sent to search, and a decision that involves only your own code gets no web research. Nothing is sent to the author. As in any Claude Code session, your prompts and the files Claude reads go to the model you use. [PRIVACY.md](https://github.com/DoctorMozg/claude-pipelines/blob/master/PRIVACY.md) covers the details.

## Support

- Issues: https://github.com/DoctorMozg/claude-pipelines/issues
- Email: drmozg@gmail.com
- Privacy: https://github.com/DoctorMozg/claude-pipelines/blob/master/PRIVACY.md

## License

MIT
