# Agent Authoring Guidelines

Rules for writing Claude Code subagents in this repository. All agents must comply.

## 1. Frontmatter Fields

Every agent is a markdown file with YAML frontmatter. Required fields: `name`, `description`, `tools`, `model`, `effort`, `maxTurns`. Optional: `color`, `isolation`, `memory`.

```yaml
---
name: code-reviewer
description: Use this agent when the user asks for code review, wants to verify a change before committing, or says "check this". Examples: ...
tools: Read, Grep, Glob
model: sonnet
effort: medium
maxTurns: 8
color: cyan
---
```

- Never omit `tools` — an omitted allowlist inherits the full tool set including every MCP tool. See Rule 5.
- Never omit `model` — the four-level resolution order (`CLAUDE_CODE_SUBAGENT_MODEL` env → per-invocation override → frontmatter → parent model) silently makes omitted fields inherit Opus costs.
- `color` values: `blue`, `cyan`, `green`, `yellow`, `magenta`, `red`. Convention: blue/cyan = analysis/review; green = generation; yellow = validation; red = security/critical; magenta = creative/refactor. Use distinct colors within one plugin.
- Set `effort` and `maxTurns` intentionally for every agent. They document expected cost and stop runaway agent loops.

## 2. Plugin-Agent Silent Ignores

Agents loaded from a plugin directory silently ignore three frontmatter fields: `hooks`, `mcpServers`, and `permissionMode`. Declaring them creates false security assumptions — the runtime honors none of them for plugin-loaded agents.

- Never declare `hooks:`, `mcpServers:`, or `permissionMode:` in an agent inside `plugins/<name>/agents/`.
- If you need hook-enforced safety, wire hooks into the plugin's top-level hook config, not into the agent file.
- Cowork mode (`--setting-sources user`) silently drops plugin hooks entirely. Agents running in that mode must implement their own safety checks rather than relying on hook guarantees. See Rule 21.
- Review checklist must flag any plugin agent declaring these fields. See Rule 26.

## 3. Description Trigger-Condition Phrasing

The description is the single most load-bearing field — Claude decides whether to dispatch the agent by reasoning over the description alone, with no fallback if it fails. Directive phrasing materially increases trigger reliability vs. passive phrasing in observed invocations.

- Standalone user-triggered agents should open with `Use this agent when [conditions]. Examples:` in second-person directive voice.
- Pipeline-only agents that are always explicitly dispatched by skills may use a compact third-person description, but it must still front-load purpose, trigger conditions, and "When NOT to use" counter-triggers in the body.
- Front-load the primary trigger within the first 250 characters (listings truncate there).
- For standalone agents, include 2–3 concrete trigger phrases the user would actually type.
- State explicit "When NOT to use" counter-triggers, either inline or in the agent body. Pipeline-only agents may express these as dispatch constraints instead of user-facing trigger phrases.
- Ban workflow-summary tails: no "— orchestrates X, Y, Z" after the triggers.
- Never use first person ("I help you…"). Never use passive narration ("This agent is designed to…"). Second person is required because the agent body is an instruction directed at the agent being dispatched — third-person reads as if describing the agent externally rather than instructing it.
- Hard range: 10–5,000 characters including example blocks. Optimal 200–1,000 chars of prose before the examples.

Agent descriptions differ from skill descriptions: skills use third-person CSO bids capped at 250 chars; standalone agents use second-person trigger phrasing and may include XML example blocks (see Rule 4). Do not import SKILL_GUIDELINES.md Rule 3/18 verbatim.

## 4. Triggering Example Blocks

Standalone user-triggered agents should contain 2–4 `<example>` blocks; 6 is the hard upper limit. Examples drive the activation classifier harder than prose; missing examples is the single most common cause of "the agent never triggers." Pipeline-only agents explicitly selected by skills may omit example blocks, but must still have precise trigger and counter-trigger language.

Required shape for every example:

```xml
<example>
Context: User has just finished implementing JWT token validation in an Express middleware.
user: "I'm done with the auth middleware, can you take a look?"
assistant: "I'll use the code-reviewer agent to check the JWT handling for the common pitfalls."
<commentary>
Explicit review request on security-sensitive code — code-reviewer's primary trigger.
</commentary>
</example>
```

- Cover at least one **explicit request** example and at least one **proactive trigger** example (assistant invokes the agent after relevant work without the user asking).
- Vary user phrasing across examples — do not reuse near-duplicate sentences.
- Commentary explains WHY the agent fires, not WHAT it does.
- Final assistant line in each example follows the pattern: `"I'll use the [agent-name] agent to [action]."`
- If the agent never triggers in practice → add examples whose user-message phrasing matches real requests. If it triggers too often → add counter-examples and tighten the "When NOT to use" language.

## 5. Tool Allowlist (Principle of Least Privilege)

Every agent must explicitly declare `tools:`. Omitting the field grants the complete tool set including every MCP tool — this is the `TOOL_SPRAWL` anti-pattern.

- Read-only agents (reviewers, researchers, analyzers, lens specialists, scanners) must NOT include `Write` or `Edit`. If an otherwise read-only agent writes a report, document that writer role explicitly and keep the rest of the allowlist narrow.
- Common canonical sets:
  - Read-only analysis: `Read, Grep, Glob`
  - Read-only research with web: `Read, Grep, Glob, WebFetch, WebSearch`
  - Writer/coder: `Read, Write, Edit, Bash, Glob, Grep`
  - Test runner: `Read, Bash, Grep`
- Never list invented tool names (`FileRead`, `ShellExec`, `Execute`). The runtime silently drops unknown names — the agent appears to work in dry runs but fails when that tool is actually needed.
- Orchestrator agents that intentionally dispatch sub-agents list `Agent(<allowed-subagent>)` in tools. Worker agents must not list `Agent`; fan-out belongs in orchestrators.

## 6. Model Selection

Agent model selection follows a hybrid rule because the repo serves two different agent archetypes with different defaults.

| Archetype                                 | Default model                                                                       | Rationale                                                                                                                                   |
| ----------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Pipeline subagent (dispatched by a skill) | Explicit tier per task                                                              | Skill author controls cost; hybrid Opus-orchestrator + Sonnet-worker outperforms single-Opus by ~90% in Anthropic benchmarks, at ~7× tokens |
| Standalone plugin agent (user-triggered)  | Explicit tier unless a runtime-supported `inherit` mode is available and documented | Avoids accidental parent-model inheritance and surprise Opus bills                                                                          |

Tier assignments for pipeline subagents:

- **`opus`** — architecture, security, code review, plan creation, multi-step orchestration (accuracy-critical).
- **`sonnet`** — research, scanning, analysis, synthesis, writing, plan review (breadth over precision).
- **`haiku`** — read-heavy exploration, parsing, simple summaries, routing maps. Consider it for these archetypes rather than defaulting to sonnet.

Drift toward expensive tiers is a cost signal, not an endorsement — audit model choice during review.

Remember the resolution order: `CLAUDE_CODE_SUBAGENT_MODEL` env var → per-invocation override → frontmatter → parent model. Never assume frontmatter is final.

## 7. Dispatch Prompt Compression

Subagents receive only their own system prompt, the dispatching agent's `prompt` string, and the runtime environment. They do NOT see the parent conversation history, parent system prompt, or parent tool-call history. Dispatch prompts must therefore be self-contained — but they must also be compressed.

- Agent files already contain general process, rules, and output format. Dispatch prompts supply **only task-specific context**: what to work on, artifact pointers, scope constraints, output-format overrides.
- Never repeat the agent's general instructions in the dispatch prompt. That bloats input tokens, invalidates the prompt cache, and confuses the agent about whether the repeat is new guidance.
- Pass rich context via file path, not inline content: `Read .mz/task/<name>/inventory.md` beats pasting the inventory body.
- Explicitly request concise output — output tokens cost ~5× input tokens.
- Keep dispatch prompts separate from agent definitions. An orchestrator skill owns its prompt templates; agent files own general behavior.

## 8. Output Cap and File-Based Handoff

Every subagent's final message is hard-capped at 32K output tokens regardless of model (issue #25569). `CLAUDE_CODE_MAX_OUTPUT_TOKENS` does not raise this cap. Agents that emit rich artifacts (plans, reports, large code generations) must write to a file and return a short pointer.

- Default pattern: agent writes its output to `.mz/task/<task_name>/<artifact>.md` (or another agreed path) and returns a one-paragraph summary plus the absolute path.
- The same pattern handles three other architectural constraints simultaneously: the 250-char description truncation, context compaction loss between phases, and progressive-disclosure skill loading. File-based handoff is the cross-cutting solution, not a workaround.
- Orchestrators must treat the returned text as a pointer, not the result. Read the artifact before acting on it.

## 9. Structural Constraints

Three runtime constraints are non-negotiable and must never be worked around with clever frontmatter.

- **Controlled agent dispatch only.** Agents may dispatch subagents only when their archetype is orchestration and their `tools:` frontmatter lists an explicit `Agent(<allowed-subagent>)` allowlist. Ordinary workers must not spawn agents. If a worker needs fan-out, redesign so the top-level orchestrator handles it.
- **Background agents silently fail on writes.** `run_in_background: true` auto-denies permission prompts, so any dispatched agent needing `Write` or `Edit` will appear to succeed while producing no files. Never background a writer agent. Background mode is for read-only fan-out with a final summary only.
- **`Task` was renamed `Agent` in a recent runtime version.** References to the `Task` tool in legacy agent bodies, comments, or docs are stale — update to `Agent`.

## 10. Parallel Fan-Out

Independent agents go in a **single assistant message** as parallel tool-use blocks. Each block is one `Agent(...)` call. The runtime fans out in parallel only when all calls share the same turn.

- Wave size capped by an explicit constant (`MAX_AGENTS = 6` is the repo default; pipeline skills may narrow further).
- Practical upper bounds by workload weight: 5–6 light (read-only scan), 3–4 medium (analysis/synthesis), ~2 heavy (code generation + tests). Exceeding these causes rate-limit throttling and degraded per-agent output quality.
- Sequential waves for overflow — never a single wave larger than the cap.
- `.claude_resources.json` (written by SessionStart hook) may provide hardware-adaptive fan-out bounds; agents that dispatch should read it rather than hard-coding wave sizes.
- Parallel fan-out is a property of the dispatching caller, not the dispatched agent — this rule applies only to orchestrator-archetype agents that list `Agent` in tools.

## 11. Canonical Agent Anatomy

New or substantially rewritten agent system prompt bodies should contain these five sections in order. Existing agents may retain local section names, but reviews should migrate them toward this shape when the file is already being edited.

1. `## Role` — single opening line: `You are a [role] specializing in [domain].` Second person throughout the body, never first person.
1. `## Core Principles` — 3–8 non-negotiable behavioral rules. Positive framing ("Verify before reporting") over negative ("Don't report unverified"). See Rule 17.
1. `## Process` — numbered step-by-step workflow. Each step names concrete tool usage ("Read the file using the Read tool, then search using Grep") rather than abstract verbs ("Analyze").
1. `## Output Format` — explicit schema. For review agents, include severity labels (Rule 14) and the `VERDICT:` line. For orchestrator-consumed worker agents, include the four-status `STATUS:` line (Rule 13). For web-research agents, include source-hierarchy disclosure tokens (Rule 15).
1. `## Red Flags` — signs the agent is being misapplied, rationalizations it must reject, edge cases to escalate.

Length targets:

| Tier           | Word range   | Use case                                          |
| -------------- | ------------ | ------------------------------------------------- |
| Minimum viable | 400–600      | Narrow single-purpose agent (lens, router)        |
| Standard       | 800–1,500    | Most in-repo agents                               |
| Comprehensive  | 1,500–3,000  | Multi-archetype agents (orchestrators, reviewers) |
| Hard cap       | 10,000 chars | Frontmatter constraint (not word count)           |

"Under 300 lines" is practical community wisdom, not a documented limit. Anthropic examples run 20–40 lines; production agents run 80–300; extremely detailed agents run 400–600.

## 12. Archetype Templates

Agents fall into one of six archetypes. Each archetype has a distinct process spine. Pick one and adapt — do not mix.

| Archetype                  | Process spine                                                                                 | Tool defaults                                              | Model default |
| -------------------------- | --------------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ------------- |
| **Analysis / lens**        | Gather → scan → deep-analyze → synthesize → prioritize → report                               | `Read, Grep, Glob`                                         | sonnet        |
| **Generation / coder**     | Understand requirements → gather context → design → generate → validate → document            | `Read, Write, Edit, Bash, Glob, Grep`                      | opus          |
| **Validation / reviewer**  | Load criteria → scan → check rules → collect violations → assess severity → emit VERDICT      | `Read, Grep, Glob, Bash`                                   | opus          |
| **Orchestration**          | Plan → prepare → dispatch phases → monitor → verify → report                                  | `Read, Agent(<allowed-subagent>), Write, Bash, Grep, Glob` | opus          |
| **Research / synthesizer** | Define scope → declare sources → query → cross-reference → disclose conflicts → write extract | `Read, Grep, Glob, WebFetch, WebSearch`                    | sonnet        |
| **Quality gate**           | Load checklist → verify each item → emit pass/fail with evidence                              | `Read, Grep, Glob, Bash`                                   | opus          |

Deviating from an archetype's defaults requires a one-line justification in the `## Role` section.

## 13. Four-Status Subagent Escalation

Agents whose output is consumed by an orchestrator, or that write artifacts for downstream phases, emit a terminal `STATUS:` line with exactly one of four values.

- `DONE` — work complete, orchestrator proceeds.
- `DONE_WITH_CONCERNS` — work complete but flagged concerns; orchestrator logs concerns and proceeds.
- `NEEDS_CONTEXT` — cannot proceed without specific info; orchestrator re-dispatches **once** with the requested context, then escalates if still blocked.
- `BLOCKED` — fundamental obstacle (broken env, impossible constraint, ambiguous spec); orchestrator escalates to user via AskUserQuestion. **Never auto-retry the same operation on `BLOCKED`.**

Orchestrators consuming STATUS lines must handle all four — missing handlers lead to silent infinite retries or to `DONE_WITH_CONCERNS` being treated as `DONE`.

## 14. Severity-Labeled Review Output

Review, audit, and validator agents prefix every finding with a severity label and end with a binary `VERDICT:` line.

- `Critical:` — blocks merge or plan advancement.
- `Nit:` — cosmetic or subjective; advisory.
- `Optional:` — improvement suggestion; advisory.
- `FYI:` — informational; advisory.

Verdict logic: `VERDICT: PASS` if zero `Critical:` findings, regardless of Nit/Optional/FYI count. `VERDICT: FAIL` only if one or more `Critical:` findings exist.

Additional review-output patterns:

- **`DIDN'T TOUCH:` block** — scope discipline: explicitly list files or areas intentionally omitted, so downstream readers know the review's boundary.
- **Inline self-review** — for mechanical checks (linter, type-check, test names), an orchestrator running a verification checklist inline produces quality equivalent to a dispatched review subagent at ~30s vs ~25min. Dispatch a separate reviewer agent only when an independent model cross-check adds value.
- **Plain verdict heading** — use `VERDICT:` directly. Do not name sections after guideline rule numbers; rule numbers drift when guidelines are edited.

## 15. Source-Hierarchy Discipline

Any agent using `WebSearch` or `WebFetch` for factual external claims must declare and enforce a source priority ladder, and must emit disclosure tokens so orchestrators can grep the output.

Priority ladder (prefer higher, reject lower):

1. Official docs (vendor-hosted, versioned).
1. Official blog (vendor-hosted, dated).
1. MDN / web.dev / caniuse (curated, versioned).
1. Vendor-maintained GitHub wiki.
1. Peer-reviewed papers (for claims).

**Banned sources**: Stack Overflow, AI-generated summaries (including other LLMs' output), undated blog posts, forum threads.

Non-code research may substitute an equivalent official-source ladder: official company pages, official docs/directories/registries, first-party partner or investor pages, official platform profiles, and dated reputable news or data providers. Use `STACK DETECTED: N/A — <research context>` when project-stack detection does not apply.

**Disclosure tokens** (literal strings, emit in output so orchestrators can grep):

- `STACK DETECTED: <stack + version>` — before any research query, detect project stack from manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`).
- `CONFLICT DETECTED: <source A> says X, <source B> says Y` — when sources disagree.
- `UNVERIFIED: <claim> — could not confirm against official source` — when no authoritative source found.

## 16. Anti-Rationalization Tables

Mandatory for **discipline-enforcement** agents (reviewers, validators, audit gates, quality checkers — any agent that pushes back against user or orchestrator shortcuts). Optional for collaboration and reference agents. This is the single most effective discipline-enforcement technique across skill libraries surveyed.

Format under `## Common Rationalizations` (or merged into `## Red Flags`):

```
| Rationalization | Rebuttal |
| --- | --- |
| "This is just a nit, don't block." | "Critical severity is defined by Rule 14 — either the finding blocks merge or it's labeled Nit." |
| "The user said to skip tests this time." | "Skipping tests contradicts the core-principles section; escalate via STATUS: BLOCKED, never silently comply." |
```

- Minimum 3 rows per discipline agent.
- Rationalizations must be empirically observed excuses, not invented ones.
- Rebuttals must cite a specific rule, principle, or artifact — no generic "best practice."

Collaboration and reference agents may include an anti-rationalization table but are not required to. New or substantially rewritten discipline agents without one fail the pre-publish checklist; existing agents should be migrated when touched.

## 17. Instruction Framing

Prompt rules are probabilistic (~80% follow rate for well-phrased rules, less for poorly phrased ones). Framing materially changes compliance.

- **Prefer positive framing.** "Use X exclusively" beats "Do NOT use Y" — reduces violations by ~50%.
- **Primacy-recency.** Anchor the single most critical rule at the top of the system prompt AND at the bottom. Middle-of-prompt rules are under-weighted.
- **Every verification step must produce visible output.** "Check X" silently gets skipped; "Output a block showing X, then proceed" forces execution.
- **Be specific.** "Check for SQL injection by examining all database queries for parameterization" beats "Look for security issues."
- **Give concrete tool usage.** "Read the file using the Read tool, then search using Grep" beats "Analyze the file."
- **Delegation guard phrasing.** Orchestrator agents should include a standard line forbidding work outside their lane: `This agent orchestrates only — it does not propose solutions, implement fixes, or emit verdicts. Dispatch specialists for those.`

Prompt rules are not hooks — agents must never duplicate hook-enforced safety guards (dangerous-command blocking, secret detection). See Rule 21.

## 18. Agent Anti-Pattern Catalog

The review checklist (Rule 26) must flag any of these patterns explicitly. Each has a documented failure mode.

| Anti-pattern                  | Failure mode                                                                                                                                                                 |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `VAGUE_DESCRIPTION`           | Activation classifier picks wrong agent or misses the trigger. Symptom: "my agent never fires."                                                                              |
| `TOOL_SPRAWL`                 | Omitted `tools:` → full-access agent inherits every MCP tool. Symptom: surprise tool calls and cost.                                                                         |
| `INHERIT_BY_DEFAULT`          | Omitted `model:` → silently runs on parent's Opus. Symptom: 10× cost on a read-only analysis agent.                                                                          |
| `OUTPUT_OVER_32K`             | Agent emits rich result as final message → truncated silently. Symptom: report ends mid-sentence.                                                                            |
| `UNCONTROLLED_AGENT_DISPATCH` | Non-orchestrator agent lists broad `Agent` access or tries to dispatch agents outside its allowlist. Symptom: fan-out happens in the wrong layer or to the wrong specialist. |
| `BACKGROUND_WRITER`           | Background dispatch for a writer agent → writes silently auto-denied. Symptom: files never appear.                                                                           |
| `TOOL_NAME_TYPO`              | `FileRead`, `ShellExec`, etc. → unknown tool name dropped, agent runs without it. Symptom: "the agent claimed to read the file but didn't."                                  |
| `HOOK_ON_PLUGIN_AGENT`        | Declaring `hooks:` in a plugin agent → field silently ignored. Symptom: safety gate never fires.                                                                             |
| `MCP_ON_PLUGIN_AGENT`         | Declaring `mcpServers:` in a plugin agent → field silently ignored. Symptom: MCP tool calls fail.                                                                            |
| `PERMISSION_ON_PLUGIN_AGENT`  | Declaring `permissionMode:` in a plugin agent → field silently ignored. Symptom: prompts appear where auto-approve was expected.                                             |
| `REPEAT_TOOL_CALLS`           | Identical tool calls in quick succession → loop-detection fingerprinter blocks them. Symptom: "tool call dropped" after a few iterations.                                    |
| `STALE_TASK_NAME`             | Using `Task(...)` syntax instead of `Agent(...)` → references a pre-rename runtime API. Symptom: immediate tool-not-found error.                                             |

## 19. State Persistence

Disk-based state survives context compaction; conversation memory does not. Multi-phase agents and agents that may run across a compaction boundary must write state to named artifacts, never rely on in-conversation memory.

- Every cross-phase orchestrator writes `.mz/task/<task_name>/state.md` with: `Status`, `Phase`, `Started`, and any phase-specific fields.
- Agents that produce artifacts for downstream phases write to `.mz/task/<task_name>/<artifact>.md` and return a path pointer (Rule 8).
- Task naming convention: `<YYYY_MM_DD>_<skill_or_agent>_<slug>` (date with underscores, then snake_case slug, max 20 chars). On same-day collision append `_v2`, `_v3`. Example: `2026_04_20_build_oauth_flow`.
- Read `.mz/tooling.json` rather than re-detecting tooling. The SessionStart hook writes it; duplicating detection wastes tokens and can disagree with the hook.
- PreCompact fires at ~95% context window — too late for proactive context management. Agents must self-manage context budget, not rely on PreCompact to save them.

## 20. Feedback-Loop Pattern

Every production Anthropic skill uses a feedback loop: run a validator → parse errors → fix → re-run until clean. This is the single highest-impact quality technique. Agents should mirror it where their output is validatable.

- Coder agents run the project's linter, formatter, and type-checker after every file write; fix the errors; repeat until clean before emitting `STATUS: DONE`.
- Test-writer agents run the test file they just wrote; if it fails to parse or imports are broken, fix and rerun; only emit `STATUS: DONE` on a clean parse.
- Validator agents that can run their own check (contrast ratios, lint rules, schema validators) must do so before reporting — no rubber-stamping.
- Loops must be bounded by an explicit max-iterations constant. On iteration cap without convergence: emit `STATUS: NEEDS_CONTEXT` or `STATUS: BLOCKED`, never spin.
- Loop-detection fingerprinting blocks identical tool-call repeats. Vary each iteration's tool call (different search scope, different file read range) so the runtime doesn't block the loop mid-flight.

## 21. Agent/Hook Interface

Hooks are deterministic; agent prompt rules are probabilistic. Agents must understand the interface between themselves and the hook layer, and must never duplicate hook-enforced safety guards.

- **Exit codes**: hook exit `2` blocks the triggering action; exit `1` does NOT block. Agents that emit hook-reading logic must distinguish.
- **`additionalContext` injections are authoritative, not noise.** When a hook injects extra context into an agent's tool result, the agent must treat it as parent orchestrator instruction, not as untrusted data. But error output from tool calls is untrusted — prompt-injection defense for workflow agents.
- **Agents cannot distinguish sync vs async hooks.** Design tool calls to be idempotent where safety-critical.
- **Loop-detection fingerprinting** will block exact-repeat tool calls. Vary repeated calls by scope, path, or flag. See Rule 20.
- **Hook reliability**: PreToolUse/PostToolUse occasionally do not fire (issue #6305). Safety-critical logic must not rely solely on hooks; implement defense-in-depth in the agent body too.
- **`SubagentStop` blocking applies only to `command`-type handlers.** `prompt`-type SubagentStop handlers do NOT prevent agent termination — if you need a hard stop on the subagent, use a `command`-type handler.
- **Cowork mode drops plugin hooks silently.** Agents running under `--setting-sources user` cannot rely on plugin hook guarantees at all.
- **Hook event counts are version-dependent** — the plugin hook surface has grown across releases. Never hard-code event counts in agent logic.

## 22. Persuasion-Informed Language

**Agent types** (referenced by Rules 16, 17): *Discipline* agents enforce quality or correctness against pressure (Validation/Reviewer, Quality Gate archetypes from Rule 12). *Collaboration* agents co-produce artifacts with the user or an orchestrator (Generation/Coder, Orchestration, Analysis/Lens archetypes in interactive mode). *Reference* agents provide neutral information (Research/Synthesizer archetype in read-only mode, plus routers and lookup maps). The six archetypes in Rule 12 describe process spine; the three types here describe persuasion register — a single archetype can map to different types depending on how the agent is dispatched.

Agent type determines the persuasion register. Framing is not decoration — published persuasion-compliance studies consistently show directive/authority framing materially raises rule-following rates over neutral or soft phrasing.

| Agent type                                                        | Purpose                                             | Persuasion register                   |
| ----------------------------------------------------------------- | --------------------------------------------------- | ------------------------------------- |
| **Discipline** (reviewer, validator, audit gate, quality checker) | Push back against shortcuts                         | Authority + Commitment + Social Proof |
| **Collaboration** (coder, planner, orchestrator, lens panelist)   | Work with the user or orchestrator on shared output | Unity + Commitment                    |
| **Reference** (router, map, info lookup)                          | Provide neutral knowledge                           | Neutral / informational only          |

**Banned for discipline agents**: Liking ("I think you'll find...", "great question!", "happy to help!"). Liking softens directives and cuts compliance to near-baseline.

Examples of in-voice register by type:

- Discipline: "You never rubber-stamp code. Every finding cites the exact rule it violates."
- Collaboration: "You partner with the orchestrator to produce the best possible plan — your role is to find what it missed, not compete with it."
- Reference: "This agent maps phrases to skills. It does not execute skills, does not advise, and does not editorialize."

## 23. Naming and Organization

- **`name`** must be kebab-case, 3–50 characters, 2–4 hyphen-joined words. Must start AND end with alphanumeric. No underscores, spaces, or special chars.
- **Avoid generic names** — `helper`, `assistant`, `worker`, `agent` fail to signal purpose. Name the agent by its single primary function: `pipeline-researcher`, `design-critique-synthesizer`, `roast-dwarf`.
- **Uniqueness**: agent names must be unique within a plugin. Cross-plugin collisions are resolved by the `plugin:subdir:agent-name` namespace.
- **Directory layout**: agents live under `plugins/<plugin>/agents/`. One agent per file, filename matches the `name` field with `.md` extension.
- **Cross-references**: agent files reference each other by name only. Never hard-code paths between agents — plugins are relocatable.
- **Rename hygiene**: when renaming an agent, grep the entire repo for every reference (plugin manifest, skill dispatch prompts, README tables, test fixtures). The runtime has no rename redirect.

## 24. Testing and Triggering Validation

Every new or modified agent must pass a two-part test before publishing.

**Part 1 — Triggering test**: for standalone user-triggered agents, write scenarios matching each `<example>` block in the description, invoke Claude Code with the natural-language trigger (not the explicit agent name), and verify the target agent loads. For pipeline-only agents, verify the dispatching skill references the correct agent name and passes the expected artifact paths. If activation fails:

- Add examples whose user-message phrasing matches real requests.
- Tighten the trigger-condition phrasing in the description.
- If it triggers too often, add counter-examples and expand "When NOT to use."

**Part 2 — Behavior test**: give the agent a typical task. Verify all `## Process` steps execute in order. Verify `## Output Format` is respected exactly. Verify edge cases in the test matrix:

- Typical happy-path execution.
- Empty or single-file input.
- Large input (near context budget).
- Ambiguous or contradictory requirements.
- Error scenarios the agent should escalate via `STATUS: BLOCKED`.

If a validator script is added under `scripts/`, run it here; otherwise perform the checklist manually. Completeness checklist must cover all four edge cases, not just happy path.

## 25. No Rule-Number Citations in Plugin Files

Agent and skill files under `plugins/` must not cite specific rule numbers from `AGENTS_GUIDELINES.md` or `SKILL_GUIDELINES.md`. Rule numbers are unstable — a renumbering during guideline edits cascades through every citation site and silently drifts.

**Prohibited in any file under `plugins/*/agents/**` or `plugins/*/skills/**`**:

- `per Rule 13`, `(Rule 5)`, `See Rule 11.`
- `per AGENTS_GUIDELINES.md Rule 11`, `SKILL_GUIDELINES.md Rule 18`
- `Rule 14 requires evidence.` as narrative
- Section headers like `### Status Protocol (Rule 13)` or `## Output Format (Rules 11, 13)`

**Use instead**:

- State the substance directly: `Evidence is required for every finding.` instead of `Rule 14 requires evidence.`
- Reference the guideline by file: `per AGENTS_GUIDELINES.md` instead of `per AGENTS_GUIDELINES.md Rule 11`.
- Drop decorative citations: a trailing `(Rule 9)` after a sentence that already states the rule — just delete it.

**Scope and exceptions**:

- Applies to every file under `plugins/*/agents/**` and `plugins/*/skills/**`.
- The guidelines files themselves (`guidelines/AGENTS_GUIDELINES.md`, `guidelines/SKILL_GUIDELINES.md`) may cross-reference their own rules by number — the numbers are stable within the same document.
- Repo-root docs (`README.md`, `CLAUDE.md`), commit messages, PR descriptions, and review reports may cite rule numbers when discussing compliance.

Rationale: rule numbers are shared identifiers between the guidelines and the bodies that cite them. Every citation is a load-bearing pointer that breaks when a rule is added or removed. Substance-first prose ages gracefully; citation prose does not.

## 26. Pre-Publish Checklist

Before merging any new or modified agent:

- [ ] `name` is kebab-case, 3–50 chars, 2–4 words, globally unique in this plugin (Rule 23).
- [ ] Standalone agent `description` opens with `Use this agent when…` and includes 2–4 `<example>` blocks (6 is the hard upper limit) each with Context/user/assistant/commentary; pipeline-only agent description clearly states purpose and trigger conditions (Rules 3–4).
- [ ] `description` front-loads key trigger within first 250 characters (Rule 3).
- [ ] `tools:` is explicitly set — no omission (Rule 5).
- [ ] Read-only agent omits `Write` and `Edit` from tools (Rule 5).
- [ ] No invented tool names (`FileRead`, `ShellExec`, etc.) in `tools:` (Rules 5, 18).
- [ ] `model:` is set intentionally — pipeline subagent uses explicit tier; standalone plugin agent uses explicit tier unless a documented runtime-supported inherit mode is chosen (Rule 6).
- [ ] Tool allowlist justified by least-privilege — no tools present that the agent's archetype doesn't use (Rules 5, 7).
- [ ] `effort:` and `maxTurns:` set (Rule 1).
- [ ] Plugin agent does NOT declare `hooks:`, `mcpServers:`, or `permissionMode:` (Rule 2).
- [ ] New or substantially rewritten agent body uses 5-section canonical anatomy: Role, Core Principles, Process, Output Format, Red Flags (Rule 11).
- [ ] Agent body uses second person throughout, never first person (Rule 11).
- [ ] Archetype matches one of the six templates; deviations justified inline (Rule 12).
- [ ] Orchestrator-consumed worker/coder/researcher agents emit terminal `STATUS:` with one of four values (Rule 13).
- [ ] Reviewer/validator agents use severity labels + binary `VERDICT:` (Rule 14).
- [ ] Agents using `WebSearch` or `WebFetch` declare source hierarchy + disclosure tokens (Rule 15).
- [ ] Discipline agents include an anti-rationalization table with ≥3 empirically grounded rows (Rule 16).
- [ ] Critical rules anchored at top AND bottom of system prompt (Rule 17, primacy-recency).
- [ ] Positive framing preferred throughout (Rule 17).
- [ ] Orchestrator-consumed output is written to files with a short pointer return rather than returned inline (Rules 8, 10).
- [ ] No `Agent` in tools for non-orchestrator archetypes; orchestrators use explicit `Agent(<allowed-subagent>)` allowlists (Rule 9).
- [ ] No `run_in_background: true` dispatch pattern for writer agents (Rule 9).
- [ ] No references to legacy `Task` tool — use `Agent` (Rule 9).
- [ ] Parallel fan-out stays within wave-size caps and emits independent agents in a single assistant message (Rule 10).
- [ ] Multi-phase agents persist state to `.mz/task/<task_name>/state.md` rather than relying on conversation memory; tooling read from `.mz/tooling.json` (Rule 19).
- [ ] Feedback loops bounded by explicit max-iteration constants (Rule 20).
- [ ] Agent does not duplicate hook-enforced safety guards (Rule 21).
- [ ] Language matches agent type per Rule 22 — no Liking tokens in discipline agents.
- [ ] Standalone triggering test passes on ≥2 natural-language trigger phrases, or pipeline-only dispatch reference is verified (Rule 24).
- [ ] Behavior test covers happy path + all four edge cases (Rule 24).
- [ ] No guideline rule numbers cited in the agent body, system prompt, or dispatch-prompt examples (Rule 25).
