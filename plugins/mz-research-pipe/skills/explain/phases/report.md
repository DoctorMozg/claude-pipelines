# Phase 3: Report Generation

Full detail for Phase 3 of the explain skill. Covers compiling researcher findings, mandatory mermaid diagrams with per-type authoring rules, the report template, and quality checks.

## Contents

- [Phase 3: Report Generation](#phase-3-report-generation)
  - 3.1 Compile findings
  - 3.2 Diagram requirements
  - 3.3 Report template
  - 3.4 Quality checks

______________________________________________________________________

## Phase 3: Report Generation

### 3.1 Compile findings

Read all `research_*.md` files from `.mz/task/<task_name>/`. Merge into a single coherent report:

- **Deduplicate**: if multiple researchers noted the same observation, keep the most detailed version
- **Cross-reference**: link structure findings to flow findings (e.g., "this middleware chain (Architecture) processes requests as traced in Execution Flow §2")
- **Resolve conflicts**: if researchers disagree on purpose or behavior, note both interpretations
- **Answer the question**: if the user asked a specific question, ensure the report directly addresses it — front-load the answer in the Overview, then let the detail sections support it

### 3.2 Diagram requirements

Every report MUST include at minimum:

**1. High-Level Architecture Diagram** (mandatory) — mermaid `graph TD` or `graph LR`:

- All modules/files in scope as nodes (use short names, full path in tooltip or label)
- Import/dependency edges between them (directed arrows, labeled if the relationship is non-obvious)
- External systems (databases, APIs, queues, caches) as distinctly-shaped nodes (cylinder for DB, cloud for API, etc.)
- Architectural layers as `subgraph` blocks if the code has clear layering
- **Hard limit**: ≤ 20 nodes. Collapse sibling files into their parent directory as a subgraph when the count would exceed this.
- **Subgraph usage**: one `subgraph` block per architectural layer (controller/service/repository) or per directory. Label the subgraph with a human-readable name in quotes. Do not nest subgraphs more than 2 levels deep.
- **Node shapes**: cylinder `[(name)]` for databases, stadium `([name])` for external APIs, hexagon `{{name}}` for queues/brokers, rectangle `[name]` for code modules, rounded `(name)` for configuration sources.
- **Node IDs**: alphanumeric and underscore only. Display labels containing special characters (`()`, `[]`, `-`, `:`, `|`) MUST be wrapped in double quotes.
- **Edge labels**: required when the relationship is non-obvious ("reads from", "invalidates", "publishes to"). Bare arrows are acceptable only for plain imports.

**2. Primary Execution Flow Diagram** (mandatory) — mermaid `sequenceDiagram` or `flowchart`:

- The main entry point through processing to output/side-effect
- All major branching points as `alt`/`opt` blocks (sequence) or diamond nodes (flowchart)
- Error paths as distinct flows (not just a single "error" box)
- External call-outs (DB queries, API calls) as interactions with named external participants
- **Hard limit**: ≤ 15 participants, ≤ 30 messages per `sequenceDiagram`. Summarize repetitive sections with `Note over` blocks.
- **Activation lifecycle**: use `activate`/`deactivate` around any async or long-running operation. Pairs must balance.
- **Side effects**: use `Note over <participant>: <effect>` for DB writes, cache mutations, or state changes that aren't a direct message.
- **Alt/opt blocks**: every error path gets its own `alt` branch — no single "error" box. For guard-only branches, use `opt`.
- **Flowchart alternative**: decision diamonds `{condition?}`, ≤ 30 nodes, edge labels on both branches of every decision.

**Additional diagrams** — include ALL that apply to the scope:

| #   | Type       | Mermaid syntax    | When to include                                                | Authoring rules                                                                                                                 |
| --- | ---------- | ----------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| 3   | Data Flow  | `flowchart LR`    | Data undergoes significant transformations                     | Input → transform nodes with type annotations in labels → output. Validation as `{diamond}`. ≤ 20 nodes.                        |
| 4   | Sequence   | `sequenceDiagram` | Multi-component interactions (API chains, event flows)         | ≤ 15 participants, ≤ 30 messages. One participant per module/service. `alt` for error paths, `activate`/`deactivate` balanced.  |
| 5   | Class/Type | `classDiagram`    | Meaningful type hierarchies or composition                     | ≤ 12 classes. Interfaces at top, key implementations below. Show only public methods relevant to the explanation.               |
| 6   | ER         | `erDiagram`       | Code manages structured data with relationships                | Only entities the scope interacts with. Cardinality on every relationship. Key fields only — not full column lists.             |
| 7   | State      | `stateDiagram-v2` | Code manages explicit state transitions                        | ≤ 15 states. Transitions labeled with trigger and guard. Mark `[*]` start/end states.                                           |
| 8   | Mindmap    | `mindmap`         | Scope > 10 files AND reader needs module hierarchy orientation | OPTIONAL supplement to architecture diagram, not a replacement. Root = scope name. Branches = top-level directories. ≤ 4 depth. |

**Cross-diagram references**: when a component or flow appears in multiple diagrams, reference it explicitly in the surrounding prose — e.g., "the cache layer shown in the Architecture diagram coordinates with the refresh sequence in §Execution Flow". This ties diagrams together instead of leaving the reader to correlate them.

### 3.3 Report template

Write the report to the resolved output path:

```markdown
# Code Explanation: <scope summary>

> <User's question, if one was asked. Omit this block if no question.>

## Overview

<2-3 paragraph executive summary. What this code does. Its role in the larger system. The key insight a reader should take away. If the user asked a question, lead with a direct answer. Written for someone who has never seen this code.>

## Diagram Guide

Navigation aid — each diagram in this report answers one question. Use this table to jump to the right view first.

| Diagram | Question it answers | Section |
|---|---|---|
| Architecture | How are the modules organized and what talks to what? | §Architecture |
| Execution Flow | What happens when the primary entry point is invoked? | §Execution Flow |
| <Data Flow, if present> | How is data shaped and transformed end-to-end? | §Data Flow |
| <additional diagrams — list each with its question and section anchor> |  |  |

## Architecture

### High-Level Diagram

<One sentence explaining what this diagram shows — e.g., "Module topology with external systems and architectural layers.">

` ``mermaid
<architecture diagram — MANDATORY>
` ``

### Component Breakdown

<One subsection per module/file in scope, ordered by architectural layer or call hierarchy:>

#### `<file path>` — <one-line purpose>

- **Responsibility**: <single responsibility description>
- **Public API**: <exported functions/classes with one-line descriptions>
- **Depends on / Depended on by**: <import relationships with purpose>
- **Configuration**: <env vars, config keys read>
- **Layer**: <handler / service / repository / utility / etc.>

## Execution Flow

### Primary Flow

<One sentence explaining what this diagram traces — e.g., "End-to-end request lifecycle from HTTP handler through the service layer to the database, including error paths.">

` ``mermaid
<execution flow diagram — MANDATORY>
` ``

### Step-by-Step Walkthrough

<One subsection per entry point or major operation. Order by importance — the most common/critical path first:>

#### <Operation name> (`<entry file:line>`)

**Trigger**: <what initiates this flow — HTTP request, CLI command, event, cron>
**Input**: <what data enters — type, source, validation applied>

1. `<file:function>` (line N) — <what happens, in plain language>
2. → calls `<file:function>` (line M) with `<key args>` — <what happens>
3. → **branch**: <condition at file:line>
   - **If <condition A>**: → `<file:function>` — <what happens>
   - **If <condition B>**: → `<file:function>` — <what happens>
4. → **side effect**: <DB write / API call / file write> at `<file:line>`
5. ...

**Result**: <what the operation produces — response body, return value, state change>
**Error path**: <what happens on failure — which exceptions, how they propagate, what the caller sees>

## Data Flow

<Include this section if data undergoes significant transformations. Omit if trivial.>

` ``mermaid
<data flow diagram>
` ``

### Data Transformations

| Stage | Location | Input type | Output type | What changes |
|---|---|---|---|---|
| Entry | `file:line` | `<type>` | — | <validation, parsing> |
| Transform | `file:line` | `<type>` | `<type>` | <what changes and why> |
| Output | `file:line` | `<type>` | `<type>` | <serialization, formatting> |

<Additional mermaid diagrams as applicable — sequence, class, ER, state, mindmap. Each diagram MUST have a one-sentence prose intro immediately above the code fence, and MUST appear in the Diagram Guide table above.>

## Design Decisions

<One subsection per significant design choice. Order by impact:>

### <Decision: e.g., "Middleware chain for request processing">
- **What**: <what was chosen — the pattern, library, approach>
- **Why**: <rationale — inferred from code patterns, comments, git history, domain knowledge>
- **Trade-off**: <what was gained vs. what was sacrificed>
- **Alternatives**: <what else could have been done and why it likely wasn't — too complex, wrong guarantees, historical reasons>

## External Context

<Include this section only if domain research was performed. Omit entirely if no external dependencies.>

### Dependencies

<One subsection per significant external dependency:>

#### `<library/service name>`
- **Role here**: <what it does in this codebase>
- **Key abstractions**: <library concepts the code relies on>
- **Configuration choices**: <non-default settings and rationale>
- **Idiomatic alignment**: <follows or diverges from recommended patterns, and why>

### Protocol / Standard Notes
<Relevant protocol details that explain code structure. Only what's needed to understand THIS code.>

## Observations

> These are observations about code quality and potential concerns — context for understanding the codebase's current state, not an audit or bug report.

### Strengths
<What's well-designed and why. file:line references.>

### Potential Issues
- **`<file:line>`** — <what could go wrong, under what conditions, impact>

### Design Debt
<Complexity, coupling, structural issues. Each with file:line.>

### Missing Pieces
<Gaps in error handling, validation, edge cases. Context, not a to-do list.>

## Appendix

### File Manifest

| File | LOC | Purpose | Entry points | Key exports |
|---|---|---|---|---|
| `<path>` | N | <one-line purpose> | <list or "—"> | <key functions/classes> |

### Glossary

<Domain-specific terms, abbreviations, or project-specific naming conventions used in the code. Only include if there are non-obvious terms.>
```

### 3.4 Quality checks

Before writing the final report:

1. **Reference integrity**: verify every `file:line` reference actually exists — read the file and confirm the line contains what you claim.
1. **Mermaid syntax validity** — for every diagram block:
   - Node IDs use only alphanumeric characters and underscores.
   - Labels containing `()`, `[]`, `-`, `:`, `|`, or pipe characters are wrapped in double quotes.
   - No unicode characters in node IDs or labels (emoji, non-ASCII punctuation).
   - No bare `&` in edge chains (use separate edge lines instead).
   - Every `subgraph` has a matching `end`. Nesting does not exceed 2 levels.
   - In `sequenceDiagram`, every `activate` has a matching `deactivate`.
   - Arrow syntax is valid for the diagram type (`-->`/`-->>` for sequence, `-->` for flowchart, `-->` or `<|--` for classDiagram).
1. **Diagram semantic quality** — for every diagram block:
   - Stays within the hard limit for its type (see §3.2).
   - Has a one-sentence prose intro immediately before the code fence explaining what question it answers.
   - Edge/message labels are present where the relationship is non-obvious.
   - Nodes reference real modules, functions, or systems — not placeholder names.
1. **Mandatory diagrams present**: architecture diagram AND execution flow diagram both exist.
1. **Diagram Guide present**: the front-matter Diagram Guide subsection lists every diagram in the report with its rendered question.
1. **Question answered**: if the user asked a specific question, verify the Overview section directly answers it.
1. **No fabrication**: every claim about code behavior must be traceable to a specific file and line — do not describe behavior you inferred but didn't verify by reading the code.

Write the report to the output path. Update state to `completed`. Report to the user: one-paragraph summary of what the report covers, plus the path to the full report.
