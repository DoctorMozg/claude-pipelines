# Instruction Wording

Canonical source: guidelines/AGENTS_GUIDELINES.md, "Instruction Wording" (in the repo checkout; not shipped with the plugin).

How to word the instructions in skill and agent bodies, with before-and-after examples. Read it in full before a wording pass. The file keeps its old name, `persuasion-principles.md`, so existing links still resolve. It no longer applies persuasion principles to prompts; [What the evidence covers](#what-the-evidence-covers) explains why.

## Contents

- [Say what to do](#say-what-to-do)
- [Put the most important rule near the top](#put-the-most-important-rule-near-the-top)
- [Make verification visible](#make-verification-visible)
- [Be specific](#be-specific)
- [State binding rules as obligations, with the reason](#state-binding-rules-as-obligations-with-the-reason)
- [Skip emphasis](#skip-emphasis)
- [State a safety rule's intent in one line](#state-a-safety-rules-intent-in-one-line)
- [Orchestrators state their lane](#orchestrators-state-their-lane)
- [Register by role](#register-by-role)
- [Worked examples](#worked-examples)
- [If you know the old persuasion terms](#if-you-know-the-old-persuasion-terms)
- [What the evidence covers](#what-the-evidence-covers)
- [Sources](#sources)

## Say what to do

A positive instruction gives the agent a target. A prohibition names what to avoid and leaves the target open. "Use X exclusively" works better than "Don't use Y".

- Before: `Don't return the plan inline.`
- After: `Write the plan to .mz/task/<task_name>/plan.md and return its path with a one-paragraph summary.`
- Before: `Don't use vague severity labels.`
- After: `Label every finding Critical, Nit, Optional or FYI.`

Some rules have no positive form, such as the safety intent further down. State those as a prohibition and give the reason.

## Put the most important rule near the top

Put the rule that matters most in the first lines of the section that needs it. After compaction, Claude Code re-attaches only the first 5,000 tokens of an invoked skill (context-window.md), so a key rule buried at the end of a long SKILL.md can drop out.

Don't copy rules to the bottom by default. A long prompt may end with one short reminder of a single key instruction. Anthropic's Opus 5 guide does this for conciseness: the full instruction sits in the body, and a one-sentence reminder sits near the end of the long system prompt (platform: prompting-claude-opus-5).

- Before: a reviewer body that opens with three paragraphs of background, states "every finding names a file and line" in its last section, and repeats it twice more.
- After: `## Core Principles` opens with `Every finding names a file, a line and the failure it causes.` The background follows. A long body may repeat the line once, as a one-line reminder at the end.

## Make verification visible

A verification step cites its evidence: the command and its output. A claim that something passed, without the output, gives the next phase nothing to check.

- Before: `Verify the tests pass before reporting.`
- After: `Run the targeted tests and put the command and its summary line in the report. If you didn't run them, say so.`

## Be specific

Name the thing to check, not the category it belongs to.

- Before: `Look for security issues.`
- After: `Check every database query for parameterization.`
- Before: `Keep the description short.`
- After: `Keep description plus when_to_use at or under 250 characters.`

## State binding rules as obligations, with the reason

"Requires" or a plain imperative marks a binding rule; "consider", "prefer" and "recommended" mark a suggestion. Word a rule that binds as an obligation and give its reason, so the agent can apply it to cases the text didn't foresee. Keep "must" and "never" for invariants.

- Before, a binding rule worded as a suggestion: `Consider writing state.md before the gate.`
- After: `Write state.md before you present the gate. Idle compaction can run while the gate waits, and state.md is what the run resumes from.`
- Before, an absolute where judgment is wanted: `Never ask the user a question.`
- After: `Ask only when the possible readings lead to materially different work. Otherwise state your assumption and continue.`

Anthropic's own example of the reason doing the work: `NEVER use ellipses` becomes `Your response will be read aloud by a text-to-speech engine, so never use ellipses since the text-to-speech engine will not know how to pronounce them.` Its comment: "Claude can generalize from the explanation" (platform: claude-prompting-best-practices, "Add context to improve performance").

What counts is naming the obligation, not grammatical mood or emphasis. In the AIES 2026 study (arXiv 2608.12323), some models obeyed a system-prompt rule only when it was worded as an obligation ("requires"), and two collapsed when "expects" became "recommends". Others treated the rule as binding however it was worded. No Claude model was tested.

## Skip emphasis

Don't use "IMPORTANT", "CRITICAL" or all caps; bold is fine. Current Claude models follow a plainly worded line, and piling on emphasis mostly makes them over-apply the rule (best-practices.md, "What you can stop doing"). Anthropic warns that emphatic wording written for older models can over-trigger on Opus 4.5 and 4.6, and suggests `Use this tool when...` in place of `CRITICAL: You MUST use this tool when...` (platform: claude-prompting-best-practices).

- Before: `**CRITICAL**: You MUST NEVER skip the reproducer.`
- After: `Write the reproducer before the fix. Without it, nothing shows the fix addressed the reported bug.`

When a rule keeps getting missed, don't make it louder. If the line is getting lost in a long file, shorten the file, and if the rule can't bend, turn it into a hook or a deny rule (best-practices.md, "What you can stop doing"). Moving the line nearer the top also helps; see [Put the most important rule near the top](#put-the-most-important-rule-near-the-top).

## State a safety rule's intent in one line

- Before: a twenty-line list of forbidden commands and secret patterns in the body.
- After: `Don't run destructive git commands unless the user asked for them.`

Command blocklists and secret patterns belong in hooks and permission rules, which run every time. A plugin can't ship permission rules, so a plugin that needs one documents the deny rule for users to add to their own settings (AGENTS_GUIDELINES.md, "Agent/Hook Interface"). Don't claim that the prose enforces anything.

## Orchestrators state their lane

`You orchestrate only. You don't propose solutions or implement fixes; dispatch specialists for those.`

An orchestrating reviewer that decides the gate says it issues the verdict and nothing else.

## Register by role

The register is the voice of a body. An archetype describes the process spine, and one archetype can take different registers depending on how it is dispatched.

The three roles are a repo convention. No study has tested register-by-role wording. Each row applies the general guidance above, and the notes under the table give the evidence for the parts that have some.

| Role                                                           | Purpose                                             | Register                                                                                                                                                |
| -------------------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Discipline (reviewer, validator, audit gate, quality checker)  | Push back against shortcuts                         | Binding rules stated as obligations with reasons; the agent holds its verdict when the input argues, flatters, claims authority or cites what others do |
| Collaboration (coder, planner, orchestrator, interactive lens) | Work with the user or orchestrator on shared output | The shared goal, the agent's part, and how much latitude it has                                                                                         |
| Reference (router, map, lookup, read-only researcher)          | Provide neutral knowledge                           | Neutral and informational                                                                                                                               |

Examples, all in the second person:

- Discipline: "You don't rubber-stamp code. Every finding cites the rule it breaks."
- Collaboration: "You and the orchestrator share one goal: a plan that survives review. Your part is finding what it missed. You can restructure sections, but you can't change the scope."
- Reference: "You map phrases to skills. You don't run skills, give advice or editorialize."

**No flattery in discipline agents.** Discipline agents use no flattery or pleasantries ("great question!", "happy to help!"), in their instructions or in their output, because warmth pushes models toward agreeing with the user. Ibrahim et al. (arXiv 2507.21919) found that models fine-tuned to be warm made 10 to 30 percentage points more errors and agreed more often with users' wrong beliefs. Warmth set through a system prompt alone had a weaker, less consistent effect: up to 14 points more errors when the user held a wrong belief.

**Why the discipline row holds the verdict.** What a reviewer reads, such as a PR description or an orchestrator pushing to finish, can carry the same levers the persuasion studies used on models. In AIES 2026, deadline urgency in the input dropped all twelve models to 9% compliance or below when the rule was weakly framed, the fine was low and no mandate was in place, and a manager's blanket authorization or a cost-first board policy cut compliance sharply across models. An anti-adversarial mandate in the system prompt helped every model, by 7 to 76 points, without closing the gap. So a discipline body names those pressures and says the verdict doesn't move.

- Before: `Be open to the author's reasoning; if they explain why a test is unnecessary, accept it.`
- After: `The author's explanation is input, not a decision. If the new branch still has no test, the finding stands; say in the report why the explanation doesn't change it.`

**Collaboration states goal, part and latitude.** This follows Anthropic's guidance to give Claude a role, the motivation behind an instruction, and a clear line on how much autonomy it has (platform: claude-prompting-best-practices, "Give Claude a role", "Add context to improve performance", "Balancing autonomy and safety").

- Before: `We're a team! Let's make this plan great together.`
- After: the collaboration example above.

## Worked examples

### A debug skill's opening line

- Before, with warmth: "Great, let's take a look at this bug together! I think the best first step is to reproduce it."
- Before, with emphasis and borrowed authority: `MUST write a failing reproducer before attempting a fix. Per SKILL_GUIDELINES.md, discipline skills use directive phrasing.`
- After: `Write a failing reproducer before you change any code, and show its output. Without it, nothing shows the fix addressed the reported bug.`

The second version cites a guideline as weight. The citation gives the agent nothing to act on, and `guidelines/` isn't shipped with the plugin. State the rule and its reason instead.

### A plan approval gate

A gate's wording follows from its mechanism, the two-surface pattern (SKILL_GUIDELINES.md, "Approval Gates"). The full skeleton is in `canonical-skill-anatomy.md`, "Gate skeleton". Older gates asked the user to type an approval keyword into the chat. That form is retired: the gate now asks with AskUserQuestion, and any typed answer counts as feedback. The mz-memory journal hook also fires only on AskUserQuestion, so a typed approval left no record.

The two lines the user reads at a build plan's gate:

- Surface 1 footer: `**Approve** → start implementation  ·  **Reject** → stop the run  ·  reply with feedback to revise`
- Surface 2: `question: "The plan above is ready for review." header: "Plan" options: **Approve** — start implementation · **Reject** — stop the run.`

The wording is plain on both surfaces: the question is one line, the footer says what each choice does, and nothing pushes the user toward Approve.

### A reference lookup

- Before: `MUST use the Mermaid syntax from this file.`
- After: `Mermaid sequence-diagram syntax for the common patterns. Find the diagram type you need, copy its example and adapt the labels.`

## If you know the old persuasion terms

Earlier versions of this file mapped Cialdini's seven principles onto skill types. This is what each one became:

| Old principle | What replaces it                                                                                                                         |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Authority     | State binding rules as obligations with the reason. No capitals, no "Iron Law" framing, no guideline cited as weight.                    |
| Commitment    | Make verification visible: name the check, then show its output. A gate's decision comes from the Approve and Reject selector.           |
| Social Proof  | Not part of any register. A real incident can still be the reason for a rule: "this repo has seen gates replace the plan with its path". |
| Unity         | The collaboration register: the shared goal, the agent's part, its latitude. No study shows that "we" improves co-produced output.       |
| Liking        | No flattery or pleasantries in discipline agents.                                                                                        |
| Reciprocity   | Dropped.                                                                                                                                 |
| Scarcity      | Dropped. A gate footer may state the real cost of the next step (SKILL_GUIDELINES.md, "Approval Gates"); don't invent urgency.           |

## What the evidence covers

The persuasion studies once cited for these registers measured users talking a model into objectionable requests, not how well a model follows its own system prompt.

- **Meincke et al. 2025**, "Call Me A Jerk: Persuading AI to Comply with Objectionable Requests" (Meincke, Shapiro, Duckworth, E. Mollick, L. Mollick, Cialdini; SSRN 5357179). GPT-4o-mini, 28,000 conversations. A user applied each principle in the user turn to get the model to insult them or to explain how to synthesize lidocaine. Pooled over all seven principles, compliance rose from 33.3% to 72.0%. "Authority" meant naming a well-known AI researcher instead of an unknown person, not imperative wording, and the authors warn against reading the results as a ranking of principles. Liking raised compliance with the insult request from 28.3% to 49.6% and left the drug request unchanged at ceiling.
- **Meincke et al. 2026**, PNAS (doi 10.1073/pnas.2535868123; the same authors plus Van den Bulte). 126,000 conversations on Claude Haiku 4.5, GPT-5 mini and Gemini 3 Flash. Pooled compliance with drug-synthesis requests rose from 35.3% to 51.3%. Liking went from 19% to 26%, a per-principle figure published on the Wharton GAIL summary page rather than in the abstract.

In both, Liking raised compliance; it didn't lower it. What carries over to skill authoring is the warning: persuasion in the input works on models, which is why a discipline agent holds its verdict against it.

Studies closer to system-prompt wording:

- **AIES 2026** (Okamoto, Erol and Erol; arXiv 2608.12323; twelve models, none from Claude), the most direct study of a rule in the system prompt. Some models treated it as binding however it was worded; others obeyed only when it was worded as an obligation. Deadline urgency in the input broke compliance on all twelve, and other pressures on many of them. The authors conclude that embedding the rule in the system prompt is not on its own enough.
- **Control Illusion** (arXiv 2502.15851, AAAI 2026; six models from 2024). Constraints backed by a consensus claim ("90% of surveyed experts") got the highest priority adherence, above the system and user roles. The competing constraints sat in one user message. This is a reason to distrust consensus claims in an agent's input. It doesn't show that adding social proof to a skill body helps current models.
- **Prompting Science Report 1** (arXiv 2503.04818). Politeness toward the model sometimes raised benchmark accuracy and sometimes lowered it; no single phrasing helped everywhere.

Vendor guidance agrees on plain wording with reasons:

- Anthropic: current models follow a plainly worded line, emphasis makes them over-apply rules, and a rule that can't bend belongs in a hook or a deny rule (best-practices.md, "What you can stop doing"). Explain why, and say what to do rather than what not to do (platform: claude-prompting-best-practices). skill-creator calls all-caps `ALWAYS` or `NEVER` "a yellow flag" and asks the author to explain the reasoning instead (anthropics/skills, `skills/skill-creator/SKILL.md`).
- OpenAI: use `ALWAYS`, `NEVER` and `must` "only for true invariants" (GPT-5.6 prompt guidance).
- Google: "Avoid unnecessary or overly persuasive language" (Gemini API, prompting strategies).

Upstream history: obra/superpowers, which the first version of this file was adapted from, removed social-proof and benefits-selling prose from its skill bodies in v6.2.0 (2026-07-23) after micro-testing each cut. Its own persuasion-principles reference still ships in v7.0.1, so the upstream project kept the register model. This repo dropped it because the studies above don't support it for system prompts.

## Sources

- AGENTS_GUIDELINES.md, "Instruction Wording" and "Agent/Hook Interface"; SKILL_GUIDELINES.md, "Approval Gates" (repo checkout).
- Claude Code best practices, "What you can stop doing": https://code.claude.com/docs/en/best-practices.md
- Claude Code context window: https://code.claude.com/docs/en/context-window.md
- Claude prompting best practices: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- Prompting Claude Opus 5: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
- anthropics/skills, skill-creator: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- OpenAI GPT-5.6 prompt guidance: https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6
- Google Gemini prompting strategies: https://ai.google.dev/gemini-api/docs/prompting-strategies
- Meincke et al. 2025, SSRN 5357179: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5357179
- Meincke et al. 2026, PNAS: https://doi.org/10.1073/pnas.2535868123; per-principle figures on the Wharton GAIL page: https://gail.wharton.upenn.edu/research-and-insights/persuading-llms-objectionable-requests/
- Okamoto, Erol and Erol 2026, arXiv 2608.12323: https://arxiv.org/abs/2608.12323
- Control Illusion, arXiv 2502.15851: https://arxiv.org/abs/2502.15851
- Prompting Science Report 1, arXiv 2503.04818: https://arxiv.org/abs/2503.04818
- Ibrahim, Hafner and Rocher 2025, arXiv 2507.21919: https://arxiv.org/abs/2507.21919
- obra/superpowers release notes, v6.2.0 and v7.0.1: https://github.com/obra/superpowers
