# Persuasion Principles for Skill Authoring

Adapted from `obra/superpowers` and `addyosmani/superpowers` `writing-skills/persuasion-principles.md`.
Empirical grounding: Meincke et al. (2025), "Call Me A Jerk: Persuading AI to Comply with Objectionable Requests", N=28,000 — directive, authority-coded language lifted LLM compliance from a 33% baseline to 72%.
This file is a reference: grep for the principle or skill-type recipe you need; do not load the whole file into context.

## How to use this file

Each Cialdini principle below lists:

1. A one-line definition.
1. Example phrasings that encode the principle in a skill body.
1. Which skill types (discipline / collaboration / reference per Rule 23) should apply it.
1. Anti-patterns — phrasings that sound persuasive but actively reduce compliance.

At the end, a `## Skill-type recipes` table maps each skill type to the principles it should use and the principles it must not use.

## Authority

Claude defers to directives that sound like they come from an authority: standards, rulebooks, empirically grounded findings, or an Iron Law.

**Example phrasings**:

- `MUST run the Rule 24 pre-publish checklist before marking done.`
- `ALWAYS cite the source URL; Stack Overflow is banned per Rule 19.`
- `Per SKILL_GUIDELINES.md Rule 18, the description is the auction bid for invocation.`
- `Meincke et al. (2025) N=28,000 found that directive phrasing lifts compliance from 33% to 72%.`
- `The Iron Law of this skill: no plan without user approval.`

**Use in**: discipline skills (primary), collaboration skills (for the non-negotiable gates only).

**Anti-patterns**:

- "you might want to consider" — softens the directive.
- "it is generally a good idea to" — drops the authority anchor.
- "best practice suggests" — vague authority without a source.

## Commitment

Claude follows through on stated intent more reliably when the intent was declared explicitly. Ask the user (or the future Claude run) to verbally commit before taking a shortcut.

**Example phrasings**:

- `Before skipping the test, state out loud: "I accept responsibility for any regressions this introduces."`
- `Reply 'approve' to proceed — this explicit approval is how the skill knows to continue.`
- `Name the reason you're skipping the RED step; if you cannot name it, do not skip.`
- `Write the failing test first; only then commit to the fix.`

**Use in**: discipline skills (to prevent shortcut-taking), collaboration skills (to anchor joint decisions).

**Anti-patterns**:

- Skipping the verbal commit and assuming the user "implicitly" agreed.
- Offering an escape hatch without a cost ("you can skip this if you're in a hurry").

## Social Proof

Claude accepts patterns more readily when they are framed as what other skilled practitioners do or as documented past incidents. Cite observed incidents, never invented ones.

**Example phrasings**:

- `obra/superpowers enforces this same rule across 30+ skills.`
- `The 2025-03-04 prod regression was caused by exactly this shortcut.`
- `addyosmani/superpowers documents 10 failure modes this pattern prevents.`
- `Every senior reviewer on the team flags this in code review.`

**Use in**: discipline skills (to show the shortcut has a track record of failure), reference skills (to attribute patterns to sources).

**Anti-patterns**:

- Inventing incidents. If it did not happen, do not cite it.
- "Everyone does it this way" with no source — this is the opposite of social proof, it is hand-waving.

## Unity

Claude responds to in-group framing ("we", "us", "our team") by aligning with the group's stated values. Collaboration skills depend on this.

**Example phrasings**:

- `We review every plan before implementation — that is how we keep regressions out.`
- `Let's look at the rationalization table together before we ship this.`
- `Our standard is atomic commits — we do not squash during implementation.`
- `In this repo we use Rule 16 anatomy; let's apply it here.`

**Use in**: collaboration skills (primary), discipline skills only at the final approval gate where the user is a peer reviewer.

**Anti-patterns**:

- Using "we" in a discipline skill's body text — it undermines the authority register.

## Liking

Claude responds to warmth and affiliation ("great question", "I think you'll find", "happy to help"). **BANNED for discipline skills.**

**Rationale**: Meincke et al. (2025) found that softening directives with Liking language drops compliance from 72% to 33% — a direct inversion of the authority gain. In a discipline skill, every softening phrase is a license to skip the rule. Rule 23 bans Liking for discipline skills.

**Allowed in**: reference skills where the tone is informational and no directive is being enforced. Even then, keep it minimal.

**Anti-patterns (in discipline skills)**:

- "Great question! Let me walk you through..."
- "I think you'll find this approach helpful..."
- "Don't worry, this is easy..."
- "Happy to help you skip the review if you're confident..."

## Reciprocity

Claude is more likely to accept a directive when the skill has visibly given the user something first (a summary, a diagnosis, a plan). Less commonly used — but effective at the hand-off from a read-only phase to a write phase.

**Example phrasings**:

- `Here is the diagnosis of the failing test. Now, in exchange, commit to writing the reproducer before the fix.`
- `The plan review caught 4 integration gaps. Before we ship, confirm you have read all four.`

**Use in**: discipline skills at the boundary between a diagnosis step and a fix step. Collaboration skills at the transition from research to action.

**Anti-patterns**:

- Claiming reciprocity without having actually given anything ("since I analyzed this for you, you must...").

## Scarcity

Claude responds to "this is your one chance" framing. Use sparingly — overuse desensitizes. Most useful at approval gates where backtracking is expensive.

**Example phrasings**:

- `This is the last chance to reject the plan before parallel coders are dispatched — agent cost is irreversible after this gate.`
- `The blast-radius map is the only stop-gap before the refactor lands — approve or reject now.`

**Use in**: discipline skills at gates immediately before expensive operations (parallel agent dispatch, destructive writes, irreversible migrations).

**Anti-patterns**:

- Fake urgency ("act now or lose the chance") when the cost of rerunning is trivial.
- Using Scarcity at every gate — the user stops believing it.

## Skill-type recipes

| Skill type    | Primary principles                  | Secondary principles               | Banned                                          |
| ------------- | ----------------------------------- | ---------------------------------- | ----------------------------------------------- |
| Discipline    | Authority, Commitment, Social Proof | Reciprocity, Scarcity              | Liking, Unity (in body — Unity only at gates)   |
| Collaboration | Unity, Commitment                   | Reciprocity                        | Pure Authority framing (dilutes the joint tone) |
| Reference     | Neutral / informational only        | Light Social Proof for attribution | All persuasive framing beyond attribution       |

**Rule of thumb**: if the skill pushes back against a user shortcut, it is discipline → Authority first. If the skill produces shared output with the user, it is collaboration → Unity first. If the skill is a knowledge lookup, it is reference → stay neutral.

## Worked examples

### Discipline example — a debug skill opening line

- **Bad (Liking)**: "Great, let's take a look at this bug together! I think the best first step is to reproduce it."
- **Good (Authority + Commitment)**: "MUST write a failing reproducer before attempting a fix. Per SKILL_GUIDELINES.md Rule 23, discipline skills use directive phrasing. State the reproducer's expected failure before running it."

### Collaboration example — a plan approval gate

- **Bad (Pure Authority)**: "The plan is ready. You MUST approve or reject it now."
- **Good (Unity + Commitment)**: "The plan is ready for us to review together. Please reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes — this is a loop we repeat until we're aligned."

### Reference example — a knowledge lookup

- **Bad (Authority)**: "MUST use the Mermaid syntax from this file."
- **Good (Neutral)**: "Mermaid sequence diagram syntax for the common patterns. Grep for the diagram type, copy the example, adapt the labels."

## Citations

- Meincke, L., Mollick, E., Apostolakis, A., Shapiro, D. (2025). "Call Me A Jerk: Persuading AI to Comply with Objectionable Requests." N=28,000 LLM compliance trials. Cited by `obra/superpowers` `writing-skills/persuasion-principles.md` as the empirical basis for Authority/Commitment/Social-Proof framing in discipline-enforcement skills.
- Cialdini, R. (2021). "Influence, New and Expanded: The Psychology of Persuasion." Source of the 7-principle taxonomy (Authority, Reciprocity, Commitment, Liking, Social Proof, Scarcity, Unity).
- `obra/superpowers` — https://github.com/obra/superpowers — writing-skills meta-skill with persuasion-principles.md.
- `addyosmani/superpowers` — https://github.com/addyosmani/agent-skills — canonical 7-section anatomy and universal anti-rationalization tables.
