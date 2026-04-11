# Phase 1: TDD Authoring Loop (RED / GREEN / REFACTOR)

This phase walks the author through a test-driven authoring loop for a new skill. The "tests" are the rationalizations the skill will face in the wild; the "implementation" is the 7-section canonical anatomy that rebuts them. Read this file at the start of Phase 1 and do not skip steps.

## Step 1: RED — Find the rationalizations

Before writing any SKILL.md content, enumerate the excuses a future invocation will raise to skip the skill. Writing from the rationalizations backward forces the skill body to earn its invocation instead of assuming it.

### 1.1 Grep the library for domain-relevant seeds

```
grep -A 4 '^### ' references/anti-rationalization-library.md | less
```

Look for entries whose `Skill type` matches the classification from Phase 0 (discipline / collaboration / reference) and whose label relates to the new skill's domain. Copy 2-3 relevant entries to scratch notes as seed patterns — do not paste them verbatim into the SKILL.md unless the rationalization genuinely applies.

### 1.2 Enumerate skill-specific rationalizations

Write ≥3 rationalization/rebuttal pairs that are specific to THIS skill. For each pair:

- **Rationalization**: a verbatim sentence a user or a future Claude run would say to skip the skill. Use first-person ("I", "we"), direct speech, no meta-language.
- **Rebuttal**: a concrete, non-generic counter. Cite a specific failure mode, past incident, or empirical finding. Never write "because it is best practice" — that is not a rebuttal.

Example shape:

```
Rationalization: "the plan is small, we can skip the approval gate"
Rebuttal: "small plans misjudge integration; the gate is the 30-second cost cap on a 3-hour misstep"
```

### 1.3 Classify the persuasion register

Re-read SKILL_GUIDELINES.md Rule 23. Match the skill type (discipline / collaboration / reference) to the register:

- **Discipline** → Authority + Commitment + Social Proof. No Liking. MUST/ALWAYS phrasing. Cite observed incidents.
- **Collaboration** → Unity + Commitment. "We"/"us" framing. Ask the user to commit verbally at gates.
- **Reference** → Neutral / informational only. No persuasive language at all.

Grep `references/persuasion-principles.md` for the recipe that matches. Note which principles will be reflected in the Overview, Core Process, and Common Rationalizations sections.

**RED exit criterion**: you have ≥3 skill-specific rationalization/rebuttal pairs in scratch notes AND a documented persuasion register.

## Step 2: GREEN — Write the counter-arguments into the canonical anatomy

Now write the SKILL.md body using the rationalizations as the pressure that shapes each section. The rationalization table (Section 5) is the literal "tests"; the other sections explain why those tests pass.

### 2.1 Copy the skeleton

Grep `references/canonical-skill-anatomy.md` for the 7-section skeleton. Paste into the new `plugins/<plugin>/skills/<name>/SKILL.md`. Fill every section; never leave a header empty — use `N/A — <reason>` with an explicit rationale if a section genuinely does not apply.

### 2.2 Section-by-section write pass

1. **Frontmatter**: name, description (CSO compliant per Rule 18 — triggers only, ≤250 chars, `ALWAYS invoke when...` lead), argument-hint, allowed-tools, model. Third person. No workflow tail.
1. **Overview**: one paragraph. What the skill does and why the rationalizations from Step 1 would defeat the user without it.
1. **When to Use**: 3-5 concrete trigger phrases. `### When NOT to use` with 2-3 counter-triggers that route to a sibling skill.
1. **Core Process**: for single-step skills, a numbered list. For multi-phase skills, a Phase Overview table with `phases/<file>.md` references (Rule 5).
1. **Techniques**: concrete patterns, tools, decision trees. Pipeline exemption (Rule 16): multi-phase orchestrators may use the single line `Techniques: delegated to phase files — see Phase Overview table above.`
1. **Common Rationalizations**: two-column table with the pairs from Step 1. Discipline skills must have ≥3 rows (Rule 17). Collaboration/reference skills may use `N/A — collaboration skill per Rule 23.` with no table.
1. **Red Flags**: 3+ observable signs the skill is being skipped or misapplied.
1. **Verification**: how to confirm the skill actually ran. Every check must produce visible output (Rule 4).

### 2.3 Cite authority sources

Anchor every non-obvious claim to an authority source. Acceptable citations:

- SKILL_GUIDELINES.md rules by number ("per Rule 18").
- Meincke et al. (2025) N=28,000 LLM persuasion compliance study (for Authority / Commitment / Social-Proof framing claims).
- `obra/superpowers` or `addyosmani/superpowers` for pattern provenance.
- Prior `.mz/reports/` or `.mz/research/` artifacts for repo-internal precedent.

Do not invent citations. If no authoritative source exists, flag the claim as observed-internal and move on.

### 2.4 Apply the persuasion register

Re-read the section text with the persuasion register from Step 1.3 in mind. For discipline skills, convert softening language ("you might want to", "consider") to authority phrasing ("MUST", "ALWAYS"). For collaboration skills, convert "you should" to "let's" / "we". For reference skills, strip any persuasive language — stay neutral.

Grep `references/persuasion-principles.md` for worked examples if uncertain.

**GREEN exit criterion**: all 7 canonical sections filled, all citations real, register matches skill type.

## Step 3: REFACTOR — Re-test under pressure

Re-read the draft as a skeptical user who does not want to invoke the skill. This step catches what writer-brain misses.

### 3.1 Description stress test (Rule 18 CSO check)

Read only the frontmatter description. Ask: "Would this description alone convince Claude to invoke the skill on a matching user turn?"

- Does it lead with `ALWAYS invoke when...`?
- Are there 2-3 concrete trigger phrases?
- Is the total ≤250 characters?
- Does it describe triggers only, with zero workflow summary tail?
- Is it third person?

If any answer is no, rewrite the description and return to this check.

### 3.2 Anatomy anchor check (Rule 16)

Grep the SKILL.md for all 7 anchor headers in order:

```
grep -n '^## ' plugins/<plugin>/skills/<name>/SKILL.md
```

Expected output: `Overview`, `When to Use`, `Core Process`, `Techniques`, `Common Rationalizations`, `Red Flags`, `Verification`. If any is missing or out of order, fix it.

### 3.3 Rationalization table pressure test

For each row in the rationalization table, ask:

- **Is the rationalization verbatim?** It must read like something a user would actually say. Academic paraphrases fail.
- **Is the rebuttal specific?** "Because best practice" fails. "Because the 2025-03-04 prod outage was caused by exactly this" passes.
- **Does the rebuttal actually push back?** If the rebuttal sounds like it agrees with the rationalization with a caveat, rewrite it.

Discipline skills with \<3 rows fail Rule 17. Re-open Step 1 if the table is thin.

### 3.4 Line budget + file reference check

- `wc -l SKILL.md` ≤ 150.
- `wc -l phases/*.md` ≤ 400 each.
- Every `phases/<file>.md` and `references/<file>.md` mentioned in SKILL.md must exist on disk. Dead references fail Rule 24.

### 3.5 Run the Rule 24 pre-publish checklist

Output every bullet from SKILL_GUIDELINES.md Rule 24 as a visible checklist and mark each PASS/FAIL. Block the workflow on any FAIL — return to GREEN or RED as needed.

Expected bullets (all 15):

- [ ] Description follows Rule 3 (third person, directive, front-loaded, trigger phrases)
- [ ] SKILL.md under 150 lines, phase files under 400 lines
- [ ] All phase file references in SKILL.md resolve to existing files
- [ ] Agent names in dispatch prompts match actual agent definitions
- [ ] No nested file references (one level deep from SKILL.md)
- [ ] Consistent terminology across all files in the skill
- [ ] Tested with direct invocation and natural language trigger
- [ ] Canonical 7-section anatomy present (Rule 16)
- [ ] Anti-rationalization table present if discipline skill (Rule 17)
- [ ] Description is CSO-compliant, no workflow summary (Rule 18)
- [ ] Research/review agents declare source hierarchy (Rule 19)
- [ ] Review output uses severity labels (Rule 20)
- [ ] Subagent output uses four-status protocol (Rule 21)
- [ ] references/ directory uses grep-first pattern if present (Rule 22)
- [ ] Language matches skill type per Rule 23

**REFACTOR exit criterion**: every Rule 24 bullet is PASS.

## Step 4: Final approval gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

Present to the user:

```
The new skill draft is ready and passed the Rule 24 pre-publish checklist.

Target: plugins/<plugin>/skills/<name>/SKILL.md
Classification: <discipline | collaboration | reference>
Anatomy sections: all 7 present
Rationalization rows: <N>
Pre-publish checklist: all PASS

<contents of SKILL.md>

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

**Response handling**:

- **"approve"** → save the file to its final location, update state, report completion to the user.
- **"reject"** → delete the draft, update state to `aborted_by_user`, and stop. Do not proceed.
- **Feedback** → incorporate the feedback, re-run the affected RED/GREEN/REFACTOR step, return to this gate, and re-present **via AskUserQuestion** using the same format. This is a loop — repeat until the user explicitly approves. Never publish the skill without explicit approval.

## Error Handling

- Empty arguments → ask the user for skill name, intent, and target plugin. Never guess.
- Target plugin directory does not exist → stop and ask; do not create a new plugin directory as a side effect.
- Rule 24 checklist has a persistent FAIL after two refactor attempts → escalate to the user via AskUserQuestion with the specific failing bullet and the options: (a) accept the exception with a documented reason, (b) rework the skill, (c) abort.
- Description cannot fit under 250 chars without dropping triggers → surface the conflict to the user; do not silently truncate triggers.
