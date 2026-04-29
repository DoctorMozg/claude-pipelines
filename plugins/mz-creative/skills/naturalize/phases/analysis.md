# Phase 1: Pattern Analysis

The orchestrator runs this phase directly (no subagent for the main analysis). Optionally dispatches `pipeline-web-researcher` if `research:yes` was set. Output: `.mz/task/<task_name>/analysis.md`.

## 1.1 Optional web research (when `research:yes`)

If the user passed `research:yes`, dispatch `pipeline-web-researcher` (mz-dev-pipe plugin) with this brief:

```
Topic: Current high-frequency AI-generated text patterns (single words, phrases, structural patterns, punctuation tells) — 2025–2026 data
Sources to prioritize:
  - Wikipedia: Signs_of_AI_writing
  - Pangram Labs blog
  - GPTZero news
  - FSU / OpenAlex / arXiv corpus studies (peer-reviewed)
  - Practitioner ban lists (jodiecook.com, contentbeta.com)
Banned: AI-generated detection lists, undated blogs, social posts
Output: a list of patterns NOT in the embedded vocabulary list (provided below) — focus on what's NEW since 2024
Embedded list (do not repeat these): <copy the avoid lists from expert-naturalizer.md, abbreviated>
Output path: .mz/task/<task_name>/web_research.md
```

Wait for completion. Append findings to a new section in the analysis (or note the supplementary file path).

If `research:yes` is not set, skip this step.

## 1.2 Read the input

Read `.mz/task/<task_name>/input.md` (written during Phase 0 setup). Compute:

- Word count
- Sentence count (rough split on `.!?` followed by space + capital)
- Approximate average sentence length
- Approximate sentence-length variance (burstiness estimator)
- Em-dash count per 1000 words
- Code-block count and total code-block words (these are excluded from rewriting)
- Heading count

## 1.3 Pattern detection — vocabulary

Scan input against the embedded avoid lists from `expert-naturalizer`. Record per-pattern hits:

- **Decorative single words**: count occurrences of each flagged word. Cluster red-flag: vital + crucial + essential + paramount in same paragraph.
- **Decorative verbs**: count.
- **Decorative affirmatives**: count when used as conversational filler.
- **Filler openers**: scan paragraph starts for "It is important to note...", "Having said that...", etc.
- **Corporate buzzwords**: "actionable insights", "key takeaways", etc.
- **Pseudo-depth phrases**: "at its core", "shed light on", etc.
- **Vague attribution**: "experts argue", "studies show", "research suggests".
- **Mechanical antithesis**: "Not only X but also Y", "It's not X. It's Y."
- **Self-posed rhetorical closers**: "Curious what others think?"

If `research:yes` returned new patterns, scan for those too.

## 1.4 Pattern detection — opening sentence

Scan the first sentence of each paragraph for AI opening templates:

- "In today's [adjective] world..."
- "In an era where..."
- "In the realm of..."
- "Have you ever wondered...?"
- "Imagine if..."
- "Picture this:..."
- "Consider this:..."

## 1.5 Pattern detection — closing/CTA

Scan the last sentence of each paragraph (and document end) for:

- Inclusivity brackets ("Whether you're a beginner or...")
- Invitation-to-act ("Ready to take your X to the next level?")
- Vague-positive wrap-ups ("The future is bright for...")
- "Challenges and Future Directions" section
- False-directness sign-offs ("At the end of the day...")

## 1.6 Pattern detection — title/header

Scan H1–H6 headers for:

- "\[Topic\]: A Comprehensive Guide" pattern
- "Understanding X: A Comprehensive Guide"
- "Everything You Need to Know About X"
- "The Ultimate Guide to X"

## 1.7 Pattern detection — punctuation

- Em dash density per 1000 words. Flag if >2 per page (~500 words).
- Semicolon-before-however count.
- Colon-followed-by-bulleted-list rhythm (every 2–3 paragraphs is suspicious).
- Smart-quote presence.
- Contraction count vs full-form count ("do not" vs "don't"). AI default: 0% contractions.

## 1.8 Pattern detection — structural

- Paragraph length variance: very low variance (3–5 sentences every paragraph) is a tell.
- Five-paragraph essay template: intro + 3 body + restated conclusion.
- Fractal summaries: intro restates topic, each section restates itself, conclusion restates everything.
- "Despite its challenges" section: dismisses problems with vague optimism.
- Rule-of-three default: lists of exactly three.
- Bolded-noun-phrase list-item pattern: every list item starts with **Bold:** explanation.
- Knowledge-cutoff disclaimer.

## 1.9 Severity classification

Classify the document overall:

- **Light AI** (1–10 patterns total, burstiness >0.5): minor rewrite, vocabulary swap-only may be enough.
- **Medium AI** (10–30 patterns, burstiness 0.3–0.5): standard rewrite — vocabulary + structural fixes.
- **Heavy AI** (>30 patterns, burstiness \<0.3): full rewrite — break templates, rhythm, vocabulary, restore opinion and specificity.

## 1.10 Identify preserve list

Scan for:

- Code blocks (auto-preserve — naturalizer skips)
- Tables (auto-preserve)
- Proper names (project names, library names, person names, company names)
- File paths, URLs, version strings (auto-preserve via regex)
- Technical terms that match the avoid list but are domain-specific (e.g., "robust" in security context, "leverage" in finance, "harness" in mechanical engineering). Flag these for the user to confirm.

## 1.11 Write `analysis.md`

Structure:

```markdown
# AI Pattern Analysis — <task_name>

## Input metrics
- Source: <inline | file:<path>>
- Word count: <N>
- Sentence count: <N>
- Avg sentence length: <N> words
- Burstiness estimate: <0.x> (target ≥0.6)
- Em-dash density: <N>/1000 words (target ≤2/1000)
- Code blocks: <count> (preserved)
- Headers: <count>
- Contraction usage: <count> contractions vs <count> full-forms

## Severity: <Light|Medium|Heavy> AI

## Detected patterns

### Vocabulary
- "<word>": <count> hits
- ...

### Opening templates
- <template>: <count>

### Closing/CTA
- <template>: <count>

### Title/header patterns
- <pattern>: <header text>

### Punctuation
- Em-dash overuse: <yes|no>
- Semicolon-however: <count>
- Colon-list rhythm: <yes|no>
- 100% Oxford comma: <yes|no>
- Smart quotes: <yes|no>

### Structural
- Five-paragraph template: <yes|no>
- Fractal summaries: <yes|no>
- Despite-its-challenges section: <yes|no>
- Rule-of-three default: <count of 3-item lists out of total lists>
- Bolded-noun-phrase list items: <yes|no>
- Uniform paragraph length: <variance metric>

## Preserve list (proposed)
- Code blocks: <count>
- Tables: <count>
- Proper names: <list of detected names>
- File paths/URLs/versions: <count of regex matches>
- Technical terms flagged on avoid list but kept (domain-specific): <list> — please confirm

## Web research findings (when research:yes)
<copy from .mz/task/<task_name>/web_research.md, or "skipped">

## Proposed rewriting strategy
<2–4 sentences describing the approach: which patterns get top priority, what target burstiness, what word-count delta to aim for, whether to chunk by section>

## Estimated word-count delta
<expected ±N% change>
```

Keep it under 250 lines.

## 1.12 Hand off to Phase 1.5

Update `state.md`: phase → `analysis_complete`, append `analysis.md` to `FilesWritten`. Phase 1.5 (approval gate) runs next, defined inline in SKILL.md.
