# Deep Review — Dev Pipeline Plugins & Guidelines

**Date**: 2026-07-02
**Scope**: `plugins/mz-dev-pipe` (10 skills, 17 agents, hooks, tests), `plugins/mz-dev-base` (3 skills, 2 agents, 14 rules, hooks), `plugins/mz-dev-git` (3 skills, 12 agents), and all five `guidelines/` documents. ~20,000 lines reviewed in full by five parallel review passes plus a dedicated guidelines pass; mechanical checks (budgets, frontmatter, citations, versions) run repo-wide.

**Verdict**: The architecture is genuinely strong — file-based handoff, four-status contracts, two-surface gates, tiered models, blinded adversarial lenses, prompt-injection envelopes. The dominant debt is a single failure class expressed ~30 different ways: **hand-maintained copies of one truth that have drifted**. Every Critical below traces to duplication-with-drift or to paths/contracts that were never exercised as an *installed* plugin. Fix the mechanics before adding any new skill.

Totals: **13 Critical, ~45 Major, ~60 Minor/Nit** findings.

---

## 1. Critical defects (ship-blockers)

### 1.1 Portability: repo-relative paths break every marketplace install

Runtime prompts hard-code `plugins/mz-dev-pipe/...` paths that only resolve inside this development repo. Installed plugins live under the plugin root, not the user's cwd.

- `agents/pipeline-decomment-proposer.md:57` + `skills/decomment/phases/dispatch.md:43` — proposer greps a repo-relative reference path; **/decomment is dead on arrival for installed users** (every file returns BLOCKED).
- `agents/expert-leftover-cleaner.md:34,57-60` + `skills/clean-leftovers/phases/cleanup.md:21` — catalog path and safety rails protect paths that don't exist in the user's project.
- `skills/audit/phases/research_deep.md:207`, `mz-dev-git` `branch-reviewer.md:214` + `review-branch/SKILL.md:57` — Wave B blinded-lens prompts read `plugins/mz-dev-pipe/skills/audit/references/blinded_lenses.md` cross-plugin by repo path.
- `mz-dev-base construct-skill` (`SKILL.md:11`, `phases/authoring.md:33,125`) — core loop requires repo-root `guidelines/SKILL_GUIDELINES.md`, which does not ship.

**Fix**: dispatch prompts pass `${CLAUDE_PLUGIN_ROOT}`-resolved absolute paths; agents take paths only from the dispatch prompt; cross-plugin file reads become explicit, documented dependencies with a degraded path. Add a CI grep banning `plugins/<name>/` literals in any runtime prompt.

### 1.2 State `Status` tokens violate the schema enum — resume is broken

`shared/state-schema.md` / `STATE_SCHEMA.md` define `pending|running|complete|aborted_by_user|failed`. `shared/resume-protocol.md` branches only on those exact tokens. But:

- `completed` written by: build `finalization.md:188`, debug `fix_and_verify.md:339` + `explore_test_and_report.md:236`, verify `SKILL.md:76`, audit `final_report.md:55` + `final_report_deep.md:95`, cleanup `SKILL.md:126` + `review_and_finalize.md:228`, polish `fix_review_and_finalize.md:305`, decomment (4 sites).
- `in_progress`: decomment `SKILL.md:58`, `apply.md:22` (a pre-flight *asserts* it).
- `complete_with_residuals` (invented value): clean-leftovers `verification.md:91,149`.

A file with `Status: completed` matches neither the "finished" nor the "resumable" branch. **Fix**: mechanical batch-replace to `complete`/`running`; model residuals as a skill-specific key. Then add the enum to the contract-matrix test so it can never drift again.

### 1.3 Cross-plugin agent dependency, undeclared

`code-lens-over-engineering` lives in **mz-dev-git**, but **mz-dev-pipe** dispatches it from build `finalization.md:47`, cleanup `review_and_finalize.md:88`, polish `fix_review_and_finalize.md:237`, optimize `validate_and_results.md:51`. Install mz-dev-pipe alone → four skills fail mid-pipeline. Symmetrically, mz-dev-git's mandatory Wave B requires mz-dev-pipe's `blinded_lenses.md` and `pipeline-researcher`, while its README calls the dependency "optional... no hard failure."

**Fix**: either vendor the lens into mz-dev-pipe, or make every cross-plugin dispatch conditional ("if unavailable, note the skipped lens and continue") and declare hard dependencies in plugin.json/README truthfully.

### 1.4 Orchestrator↔agent schema/contract mismatches

- **mz-dev-git lens schema**: `branch-reviewer.md:163-170` demands a `map_match` column; all six lens files declare their 10-column schema "fixed" without it → every validated prior concern silently classified "new".
- **decomment proposals**: agent emits `file_path:`; `consolidate.md:26,62` requires `file:`; BLOCKED stubs use `concerns:` where the consolidator expects `block_reason:` → every proposal lands in the malformed table.
- **Report filenames**: skills verify `<date>_github_review_pr_...` / `<date>_github_scan_prs_...`; agents write `<date>_review_pr_...` / `<date>_pr_scan_...` → Verification steps fail, prior-report greps miss history.
- **`task_name` never passed**: all three mz-dev-git skills create `.mz/task/<task_name>/state.md` but no dispatch prompt passes `task_name` → agents invent their own directory, orphaning state.
- **Contract matrix vs reality**: `tests/contract_matrix.md:25,37` claims completeness-checker has no `VERDICT: FAIL`; the agent defines it and build branches on it. Two dispatched agents (decomment-proposer, expert-leftover-cleaner) have no matrix row and the runner's regex can't even represent the latter.

### 1.5 Loop counters that reset inside the loop — caps never bind

- build `testing.md:176`: `Set red_iteration = 0` is re-executed on every "jump back to 5.2" pass → `MAX_RED_ITERATIONS` can never trigger. (debug `fix_and_verify.md:169` has the correct "initialize BEFORE the loop" wording — copy it.)
- cleanup `review_and_finalize.md:25`: same defect in the 6→3→4→5 rejection loop; also violates resume-protocol's "read the counter from state.md; do not reset."

### 1.6 mz-dev-base ships broken injections and drifted copies

- `scripts/session-start.sh:8,15`: injected routing SKILL.md is 10,850 chars against `MAX_CHARS=8000` → **every session receives a routing map cut mid-table**, no truncation marker. Inject only the routing table.
- `construct-skill/phases/authoring.md:127-148`: hardcoded "all 20" pre-publish checklist vs the guideline's current 23 items — missing exactly the newest rules (two-surface gates, variant gates, no-rule-citations).
- Shipped authoring residue: `audit/phases/consolidate_deep.md:219` tells a *user's audit run* to `pre-commit run --files plugins/mz-dev-pipe/...` — batch-fix leftovers in a repo that ships a leftover-cleaning skill.

### 1.7 The documented MCP fallback tier is unreachable

CLAUDE.md mandates `gh` → GitHub MCP → REST. Every mz-dev-git agent documents the chain, but no agent's `tools:` allowlist contains any `mcp__github__*` tool, so the runtime never exposes tier 2. In practice the chain is gh → REST. **Fix**: add the specific MCP tools to allowlists, or honestly document a two-tier chain.

---

## 2. Systemic diagnosis (the principal-level view)

### 2.1 Duplication-with-drift is the failure mode; everything else is a symptom

Quantified across the review:

| Duplication site | Size | Drift already observed |
| --- | --- | --- |
| Status-protocol restated in all 17 mz-dev-pipe agents | ~2,800 words, 14 distinct wordings | wording variance; two output templates end on VERDICT with no STATUS |
| 6 code-lens agents (mz-dev-git) | ~430–460 duplicated lines (~60-65% of each file) | `map_match` schema divergence, inconsistent turn-cap policies, vestigial "Stage 2" labels |
| audit standard vs deep phase files | ~200 lines ~90% identical | severity caps contradict each other (§3.1) |
| Approval-gate boilerplate restated at 8+ gate sites | ~250 lines | build's phase-file copy lost the cost preview and points at the wrong next phase |
| branch-reviewer vs github-pr-reviewer report machinery | ~200 lines | separate drift in verdict systems |
| Guideline rules duplicated between SKILL_ and AGENTS_GUIDELINES | ~8 rule pairs, ~150 of 764 lines | compression "preserve verbatim" list verbatim ×2; no-rule-citations rule near-verbatim ×2 |
| State schema: canonical vs mz-dev-pipe mirror | reworded, not copied | **cannot be diff-verified at all** |
| construct-skill references vs guidelines | ~200–230 lines (~25% of the skill) | checklist 20 vs 23 |
| decomment vs clean-leftovers | ~1,400 parallel lines, 4 of 5-6 categories overlap | zero mutual counter-triggers |
| strict-typing-python vs python-conventions (init-rules) | near-verbatim, installed under the same condition | — |

**Recommendation (highest leverage in the whole review)**: adopt a *generate, don't hand-sync* stance. Concretely:
1. A canonical-snippet stamp: keep one canonical block (status protocol, source hierarchy, generic red flags, gate skeleton) and a small script that stamps it into agent files and **verifies byte-identity in CI** (the `set_versions.sh` pattern already proves this works here).
2. Make the state-schema mirror a verbatim copy with a one-line header, so `diff` catches drift; wire that diff into `run_smoke.sh`.
3. Generate the README agent/skill tables and the using-mozg-pipelines routing table from the marketplace manifest.

### 2.2 The shared/ protocol layer is half aspirational

Four shared modules are load-bearing and referenced (approval-gate, state-schema, resume-protocol, scope-parameter). Three declare MUST-level contracts that **no skill obeys**:

- `shared/iteration-limits.md` — "Skills MUST resolve their cap through this module": zero references from any skill; canonical constant names (`DEBUG_MAX_FIX_ITERATIONS`) don't match what skills declare (`MAX_FIX_ITERATIONS`); the registry table is stale; its `MAX_APPROVAL_ITERATIONS (build, 3)` contradicts the gate's mandated unbounded loop.
- `shared/retry-policy.md` — unreferenced; contradicted by build ("retry once") and ask (`AGENT_RETRY_LIMIT: 1`) vs its transient=2; clean-leftovers auto-retries BLOCKED, which both this file and agent-status-protocol forbid.
- `shared/severity-lattice.md` — verify mandates emitting `Nit:` findings the lattice calls "a contract violation"; audit hardcodes caps (`HIGH_CAP = 10`, and deep caps High at 10 where pre-PR mode says ∞) with a 4-level lowercase scale against the lattice's 6 uppercase tokens.

**Fix**: for each module, decide — wire it in (skills reference it and delete their local restatements) or demote its MUST to guidance. A shared module that reads like a guarantee while enforcing nothing is worse than no module.

### 2.3 The repo violates its own budgets

- **SKILL.md ≤150 lines**: 5 of 16 over — optimize **287 (+91%)**, build 195, debug 190, cleanup 162, polish 156. Root cause in every case: fully inlined gate machinery that `shared/approval-gate.md` already specifies. A gate site needs ~8–15 lines (artifact path, header, Approve/Reject outcomes, cost formula) + a pointer; that alone brings all five under budget.
- **Phase ≤400 lines**: audit `research.md` at 421 (fixed for free by extracting the duplicated lens prompts); verify `checks.md` at 399 — one edit from breaking.
- **Description ≤250 chars**: 10 of 16 skills over (audit ~460, debug ~430), several with the explicitly banned workflow-summary tails. Either enforce the cap or change the rule — a rule violated by 60% of its subjects is a worse signal than no rule.

### 2.4 Tests enforce documentation, not behavior

`run_contract_matrix.sh` and `run_smoke.sh` pass green today (verified live) but check that tokens are *mentioned*, not that contracts *hold*: Form B matches a token anywhere in a file; column mapping is never validated against the header; phantom agents can be harvested from prose; the matrix contradicts an agent's actual verdict contract. None of the Critical classes above (status enums, path portability, agent-name resolution, schema column lists, line budgets, description lengths) is mechanically checked, and every one is mechanically checkable.

**Recommendation**: extend the test layer into a real repo linter run in CI:
1. Status-enum grep (`Status: completed|in_progress|complete_with_residuals` → fail).
2. Dispatched-agent-name resolution against `agents/` across declared plugin dependencies.
3. Ban `plugins/<name>/` literal paths in runtime prompt files.
4. Line budgets + description lengths from frontmatter.
5. Mirror byte-diff (state schema, stamped blocks).
6. Generated-table freshness (README, routing map).

---

## 3. Redundancy — the consolidation axe list

1. **Merge `decomment` + `clean-leftovers`** (mz-dev-pipe). Two parallel ~700-line stacks; 4 of the categories overlap almost entirely; neither's "When NOT to use" mentions the other, so dispatch is a coin flip. Keep decomment's propose→gate→apply architecture (safer), absorb clean-leftovers' catalog + dead-code category. Also strip `pipeline-optimizer` categories 1–3 (debug artifacts/dead code/redundant comments), which triple-implement the same cruft removal with a third rule set. Saves ~700 lines and, more importantly, removes three divergent safety models for one job. Minimum fallback: mutual counter-triggers in both descriptions.
2. **One parameterized code-lens agent** (mz-dev-git). ~60-65% of each of the six lens files is a shared contract; genuinely lens-specific content is ~35–45 lines each. branch-reviewer already composes a per-lens dispatch — move the lens focus block there (or into per-lens reference stubs). Runtime tokens are unchanged; maintenance goes 6×→1 and the three observed drift bugs become impossible. Second-best: keep six files, stamp the shared block by script.
3. **Slim `github-pr-reviewer` to a PR-context collector** and let `branch-reviewer` own analysis + the single report format. Today a PR review is a 4-deep chain (~12 agents, 3+ opus contexts holding the same diff) with ~200 lines of duplicated report machinery and an ambiguous nesting contract (nothing disables branch-reviewer's own Phase 2 research and Phase 6 report when nested → potentially two reports per run).
4. **Merge `pipeline-researcher` + `pipeline-web-researcher`** — identical tools, limits, and a byte-identical 272-word source-hierarchy block; a `mode:` line in the dispatch covers the difference. (If kept separate: justify web-researcher's unexplained `opus` — it's the /deep-research fan-out workhorse, so the tier multiplies across every wave.)
5. **init-rules: 14 files → ~6** (mz-dev-base). Merge strict-typing-python + python-conventions (installed under the same condition); quality + standards; workflow + self-eval; git + pre-commit. Move `internal-artifact-compression` (mz-pipeline-specific, references `.mz/task/` and expert agents) out of the universal set. Target ~150 lines for the always-installed set — these lines are paid in *every session of every project* they're installed into, the highest token-cost surface in all three plugins.
6. **Delete or wire the dead governance**: `github-review-pr/references/kill-criteria.md` (zero inbound references, owner "TBD", measuring nothing — while its own 2.5× cost threshold would likely be tripped by the current architecture); iteration-limits/retry-policy MUSTs (§2.2).
7. **Guidelines**: extract the ~8 duplicated rule pairs into one shared "common authoring rules" section referenced by both docs, or pick one owner per rule with a one-line pointer from the other. Within AGENTS_GUIDELINES, each rule is currently stated up to three times (body → anti-pattern catalog → checklist); keep the body as the single normative statement and make the catalog/checklist reference-only.

---

## 4. Token-efficiency improvements

1. **Gate instantiation shorthand** in `shared/approval-gate.md`: ~200 lines saved across 8+ sites, and it fixes the budget violations (§2.3) and the build gate drift (its duplicated copy lost the cost preview and names the wrong next phase).
2. **Pass diffs by path, not inline**. branch-reviewer pastes the full diff into its own dispatch, then 6 lens dispatches, then 3 Wave B dispatches — ~10 inline copies per PR review while `branch_info.md` already holds it on disk. Wave A lenses should read from the artifact path (Wave B legitimately needs 3 inline copies for blinding). Same pattern: build `finalization.md:53-58` pastes the full implementation diff into the over-engineering lens dispatch — pass the `git diff` command instead.
3. **Never dispatch a paid no-op**: audit deep sends the STRIDE researcher a prompt saying `SKIP … return an empty findings list` at T0/T1 — an opus agent whose job is to return nothing. Record `stride_delta: skipped` in the rollup instead.
4. **Hook injection discipline**: session-start.sh should inject the routing table only (~2 KB of frontmatter/Overview/Verification noise currently rides along, and the whole thing is truncated anyway — §1.6).
5. **Boilerplate stamping** (§2.1) converts ~2,800 words of divergent restatement into one canonical ~90-word block — a maintenance win that is also a quality win.
6. **Arithmetic in Bash, not in the model**: pipeline-measure-runner (haiku) is told to compute mean/median/stddev/CV itself — exactly how fabricated statistics enter a measurement pipeline. One `awk` line fixes it.
7. **Cache clean-leftovers' web research** (currently a fresh web fan-out per run for watermark strings that change "every few months") with a 30-day staleness window in `.mz/`.
8. **Descriptions**: trim the 10 over-cap descriptions to triggers + counter-triggers; every character is paid in every session's skill listing.

---

## 5. Guidelines review

The five docs are unusually good as a body of institutional knowledge — HOOKS_GUIDELINES in particular is concrete, schema-accurate, and battle-scarred. Issues:

1. **Cross-file duplication** (~8 rule pairs, ~150/764 lines) and triple-statement within AGENTS_GUIDELINES — see §3.7.
2. **A guideline example that violates a guideline**: AGENTS Rule 16's canonical anti-rationalization row rebuts with "Critical severity is defined by Rule 14 —…". Copied into any plugin agent (as canonical examples are), it violates Rule 25's rule-number ban. Reword the example to cite substance.
3. **Unsourced numeric claims presented as fact**: "reduces violations by ~50%", "~80% follow rate", "outperforms single-Opus by ~90% … at ~7× tokens", GitHub issue numbers (#25569, #6305). Downstream, mz-dev-base's persuasion reference has already *inverted* the Meincke et al. figure (claiming Liking "drops compliance from 72% to 33%" — the study showed persuasion *raising* compliance 33%→72%). Either cite with links/dates or drop the numbers; misquoted precision is worse than none.
4. **The 250-char CSO cap is dead on arrival** (10/16 skills over, including well-regarded ones). Decide: enforce mechanically or raise the cap and keep only the "no workflow-summary tails" substance.
5. **Rule 2's budget rationale is muddled**: SKILL.md bodies load on invocation, not always — the "~150-instruction budget" applies to always-loaded descriptions/CLAUDE.md, not phase-file-vs-SKILL.md placement. State the real reason (invocation-time cost + orientation) so authors optimize the right thing.
6. **Runtime-claim rot risk**: `effort`/`maxTurns` as *required* frontmatter, `once: true`, hooks `if` guards, the 32K output cap, "PreCompact fires at ~95%" — all version-dependent behaviors stated as timeless fact. Add a "verified against Claude Code vX.Y" stamp per doc so staleness is detectable.
7. **STATE_SCHEMA key-case inconsistency** (`Status`/`Phase`/`Started` vs `phase_complete`/`what_remains`/`last_verified`) — cosmetic but every skill copies it; standardizing later gets more expensive by the week. Also: designate the mz-dev-pipe mirror as a *verbatim* copy so drift is `diff`-detectable (§2.1).
8. **SKILL Rule 20 has malformed backtick markup** in its reference-pointer example — the one line authors copy-paste.
9. **Missing rule the evidence demands**: nothing in either guideline requires *portability testing as an installed plugin* — the single largest defect class found. Add it to both pre-publish checklists ("no repo-relative `plugins/` paths in runtime prompts; cross-plugin dependencies declared and degradable").

---

## 6. What is genuinely well done (keep, and hold the line)

- **Frontmatter hygiene is flawless across all 31 agents** — every required field present, zero forbidden fields, zero invented tool names, zero stale `Task` references (verified mechanically).
- **Zero rule-number citations** anywhere under `plugins/` — full compliance with the repo's hardest convention.
- **build's RED-phase TDD discipline** anticipates every classic LLM failure (stubbing, mocking-the-implementation, assertion-weakening, test-editing) and closes the loop with an actual diff audit.
- **mz-dev-git's prompt-injection discipline** (`<untrusted-content>` at every trust boundary) and its end-to-end zero-results protocol are exemplary; the two-signal Critical gate + blinded Wave B is a thoughtful anti-confirmation-bias design.
- **optimize's measurement discipline** is principal-grade: harness-only numbers, Amdahl-bounded predictions, diminishing-returns stop, artifacts required for every number.
- **decomment's propose→gate→apply architecture** is the safest editing design in the repo — which is exactly why it should survive the merge in §3.1.
- **The two-surface approval gate** and its written rationale; **resume-protocol's idempotency rules**; **the sentinel design in init-rules**; **references/blinded_lenses.md** as the model single-source-of-truth file.
- **A test layer exists at all** and gates version bumps — extend it (§2.4) rather than replace it.

---

## 7. Prioritized action plan

**P0 — correctness, cheap, mechanical (do first, mostly batch-fixable):**
1. Status-enum batch fix (`completed`/`in_progress`/`complete_with_residuals` → schema tokens) + CI grep.
2. Fix the two loop-counter re-initializations (build testing.md, cleanup review loop).
3. Fix decomment's `file:`/`file_path:`/`block_reason:` schema mismatch and the mz-dev-git `map_match` column.
4. Align report filenames between mz-dev-git skills and agents; pass `task_name` in all three dispatch prompts.
5. Delete the shipped pre-commit authoring residue (consolidate_deep.md:219); fix `${CLAUDE_PLUGIN_ROOT}/../plugin.json` in init-rules.
6. Fix session-start.sh truncation (inject table only, add marker) and detect-tooling.sh's inverted Python precedence.

**P1 — portability and contracts:**
7. Replace all repo-relative `plugins/...` paths in runtime prompts with dispatch-supplied `${CLAUDE_PLUGIN_ROOT}` paths; declare or degrade every cross-plugin dependency (code-lens-over-engineering, Wave B, construct-skill's guideline reads).
8. Wire-or-demote the three aspirational shared modules (iteration-limits, retry-policy, severity-lattice) and fix audit's cap contradictions.
9. Make the MCP fallback tier reachable or document the chain as two-tier.
10. Extend the test layer into the repo linter (§2.4) — this is what keeps P0 fixed.

**P2 — consolidation and token economy:**
11. Gate-instantiation shorthand; bring the five over-budget SKILL.mds under 150.
12. Merge decomment + clean-leftovers; parameterize the code lenses; slim github-pr-reviewer; merge the two researchers; consolidate init-rules to ~6 files.
13. Canonical-snippet stamping + generated tables (README, routing map, checklist) with CI freshness checks.
14. Guidelines dedup, citation hygiene, CSO-cap decision, portability rule added to both checklists.
