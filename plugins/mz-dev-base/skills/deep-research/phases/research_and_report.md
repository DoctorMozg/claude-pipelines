# Steps 2-5: Research and Report

Detail for the researcher dispatch, synthesis, report writing, and user reporting steps of the deep-research skill.

## Step 2: Dispatch parallel domain-researcher agents

For each subtopic, launch a `domain-researcher` agent **in parallel** with a detailed prompt. Each agent's prompt must include:

```
Research the following subtopic exhaustively: "<subtopic name>"

Context: This is part of a larger research on "<original topic>".

Requirements:
- Search at least 20 different web pages. Target 100 pages if the topic has enough material.
- Use multiple search queries with different angles and phrasings (at least 5 distinct queries).
- Prioritize primary sources: official documentation, research papers, conference talks, engineering blogs from practitioners.
- For each key claim, cross-reference across at least 2 independent sources.
- Capture specific data points: numbers, dates, version numbers, benchmarks, quotes.
- Note contradictions between sources explicitly.
- Track every URL consulted.

Output format:
- Start with a 3-sentence summary of this subtopic.
- List all key findings with evidence and source URLs.
- Rate confidence for each finding (high/medium/low).
- End with a "Sources consulted" section listing every URL visited with a one-line description of what it contributed.
- End with "Gaps" — what you could NOT find or verify.
```

IMPORTANT: Launch ALL domain-researcher agents in a single message using parallel tool calls. Do not launch them sequentially.

## Step 3: Collect and synthesize

After all agents complete:

1. **Read all agent outputs** carefully.
1. **Cross-reference between subtopics** — identify findings that appear in multiple agents' results (higher confidence) and contradictions between them.
1. **Identify emergent patterns** — themes that span multiple subtopics but that no single agent would see.
1. **Assess overall coverage** — note gaps where agents couldn't find information.

## Step 4: Write the report

Write the final report to `.mz/research/` using the naming convention: `<YYYY_MM_DD>_research_<slugified_topic><_vN>.md` (append `_v2`, `_v3` etc. if a report with the same base name already exists):

```markdown
# Deep Research: <Topic>

**Date**: YYYY-MM-DD
**Subtopics researched**: N
**Total sources consulted**: N (aggregate from all agents)

## Executive Summary

3-5 paragraphs covering the most important findings across all subtopics.
Highlight surprising findings, strong consensus points, and key uncertainties.

## Detailed Findings

### <Subtopic 1>

#### Key findings
- Finding with evidence and [source](url). **Confidence: high/medium/low**
- ...

#### Notable data points
- Specific numbers, benchmarks, quotes with attribution.

---

### \<Subtopic 2>

...

## Cross-Cutting Themes

Patterns and insights that emerge when looking across all subtopics together.

## Contradictions and Uncertainties

Where sources disagree or information is incomplete.

## Research Gaps

What could not be determined from available sources. Suggestions for further investigation.

## Methodology

- Number of domain-researcher agents dispatched: N
- Approximate pages consulted per agent: N
- Search strategy summary

## All Sources

Deduplicated list of all URLs consulted across all agents, grouped by subtopic.

```

## Step 5: Report to user

Display:

- Path to the saved report
- Total number of sources consulted
- Number of subtopics covered
- Top 3-5 most significant findings as a preview
