# Phases 2-3: Research and Report Generation

Full detail for the research and report phases of the explain skill. Covers adaptive researcher dispatch, role-specific analysis prompts, and the comprehensive report template with mandatory mermaid diagrams.

## Contents

- [Phase 2: Research Dispatch](#phase-2-research-dispatch)
  - 2.1 Detect dispatch configuration
  - 2.2 External dependency detection
  - 2.3 Researcher prompts
- [Phase 3: Report Generation](#phase-3-report-generation)
  - 3.1 Compile findings
  - 3.2 Diagram requirements
  - 3.3 Report template
  - 3.4 Quality checks

______________________________________________________________________

## Phase 2: Research Dispatch

### 2.1 Detect dispatch configuration

Count files in scope and scan for external dependencies to decide how many researchers to dispatch.

**External dependency detection**: quickly scan the scope files (read imports, first 50 lines of each) for:

- Import statements referencing non-stdlib external packages
- API calls to external services (HTTP clients, gRPC stubs, message queue producers/consumers)
- Protocol implementations (WebSocket, OAuth, custom wire formats)
- Database/ORM usage (query builders, model definitions, migrations)
- Configuration referencing external systems (connection strings, API URLs, service endpoints)

**Dispatch matrix**:

| Scope size | External deps detected? | Researchers | Configuration                                        |
| ---------- | ----------------------- | ----------- | ---------------------------------------------------- |
| ≤ 10 files | No                      | 1           | Single comprehensive analyst                         |
| ≤ 10 files | Yes                     | 2           | Comprehensive analyst + Domain researcher            |
| > 10 files | No                      | 2           | Structure analyst + Flow analyst                     |
| > 10 files | Yes                     | 3           | Structure analyst + Flow analyst + Domain researcher |

Spawn all researchers in a **single message** using parallel tool calls.

### 2.2 Researcher artifacts

Each researcher writes findings to `.mz/task/<task_name>/research_<role>.md`:

- `research_comprehensive.md` — when a single analyst handles everything
- `research_structure.md` — static structure and design analysis
- `research_flow.md` — runtime execution and data flow tracing
- `research_domain.md` — external dependency and domain knowledge

### 2.3 Researcher prompts

#### Single Comprehensive Analyst

Used when scope ≤ 10 files and no significant external dependencies. Spawn one `pipeline-researcher` agent (model: **sonnet**):

```
You are performing a deep code analysis for a comprehensive explanation report.

Read .mz/task/<task_name>/scope.md for the file list and user's question.

## Analysis Checklist

Read every file in scope line by line. For each file:

**Structure**: purpose and system role, public API (exports, endpoints), internal organization, dependencies (imports and importers), configuration (env vars, config files, feature flags)

**Execution Flow**: entry points (handlers, main, event listeners, CLI), call chains step-by-step with file:line, ALL branches (not just happy path), data transformations with types at each stage, side effects (DB writes, I/O, cache mutations, logging), concurrency (async/await, threads, locks, ordering)

**Design Rationale**: design patterns used and WHY they fit, trade-offs made (performance vs readability, flexibility vs simplicity), defensive coding (validation, retries, timeouts), historical context (git blame for surprising patterns, TODOs, workarounds)

**Observations** (document, don't fix): potential issues (bugs, races, missing error handling), design debt (complexity, duplication, leaky abstractions), missing pieces (unhandled paths, validation gaps), strengths (clean abstractions, good coverage)

## Output

Write to .mz/task/<task_name>/research_comprehensive.md with sections:
- Per-File Analysis (purpose, API, key functions with file:line, deps)
- Execution Flow Traces (per entry point, numbered steps with file:line, branching as sub-lists)
- Data Flow Map (input type → stages → output type, all with file:line)
- Design Decisions (choice, rationale, trade-off, alternatives)
- Observations (strengths, issues, debt, gaps — all with file:line)
- Diagram Suggestions (type, key nodes/edges — descriptions, not mermaid syntax)

Be thorough. Do not skip complexity — explain it.
```

______________________________________________________________________

#### Code Structure Analyst

Used for large scopes (> 10 files). Handles static structure and design. Spawn a `pipeline-researcher` agent (model: **sonnet**):

```
You are the STRUCTURE analyst for a deep code explanation report.

Read .mz/task/<task_name>/scope.md for the file list and user's question. Do NOT trace runtime execution — another researcher handles that.

## Analysis Checklist

Read every file in scope:

**Architecture**: module purposes and responsibility boundaries, public APIs (contracts each module offers), dependency graph (circular deps, hub/leaf modules), layering (controller/service/repository) and boundary respect, seam files (interfaces with rest of system)

**Design**: design patterns and WHY each fits its context, type system usage (inheritance, composition, generics), configuration surface (env vars, config, feature flags, effects), error model (representation, propagation, handling across boundaries)

**Code Organization**: naming conventions and what names communicate, grouping logic (co-location vs separation), abstraction quality (single responsibility, stable interface vs leaky)

**Observations**: structural strengths (clean separations, consistent patterns), structural debt (tangled deps, god classes, unclear responsibilities), missing structure (where abstractions would clarify)

## Output
Write to .mz/task/<task_name>/research_structure.md with sections: Module Catalog (per-module purpose, API, deps, layer), Dependency Graph (nodes, edges, hubs, cycles), Design Patterns (each with WHY and file:line), Configuration Map, Error Model, Observations (all with file:line), Diagram Suggestions (component/class diagram nodes, edges, subgraphs).
```

______________________________________________________________________

#### Execution Flow Analyst

Used for large scopes (> 10 files). Handles runtime behavior tracing. Spawn a `pipeline-researcher` agent (model: **sonnet**):

```
You are the EXECUTION FLOW analyst for a deep code explanation report.

Read .mz/task/<task_name>/scope.md for the file list and user's question. Do NOT analyze static structure or design patterns — another researcher handles that.

## Analysis Checklist

Read every file in scope. Trace how code RUNS:

**Entry Points**: catalog all entry points (HTTP handlers, CLI commands, event listeners, cron, main, signal handlers) — trigger, arguments/context, ultimate output/effect

**Call Chains**: happy-path traces step-by-step with file:line and args, error paths (which exceptions caught where, retries, propagation), branching points (guards vs genuine forks — document ALL branches), recursion/loops (termination conditions, iteration count drivers)

**Data Flow**: input shapes at each entry point (types, validation), transformations at each handoff (type → type with file:line), output shapes (serialization, formatting), intermediate state (accumulators, caches, context objects)

**Side Effects**: external interactions in execution order (DB read/write, HTTP, file I/O, queue, cache), state mutations (records created/updated/deleted, files written, caches invalidated), concurrency (async ops, parallel execution, lock lifecycle, race prevention)

**Timing**: initialization vs per-request vs lazy, cleanup (shutdown hooks, context managers, finalizers), ordering constraints (what breaks if reordered)

## Output
Write to .mz/task/<task_name>/research_flow.md with sections: Entry Point Catalog, Execution Traces (numbered steps with file:line, branching as sub-lists), Data Flow Maps (input → stages with types → output), Side Effect Timeline (per path), Concurrency Analysis, Lifecycle, Diagram Suggestions (sequence + flowchart actors/messages/decisions).
```

______________________________________________________________________

#### Domain Researcher

Dispatched when external dependencies are detected. Spawn a `pipeline-researcher` agent (model: **sonnet**):

```
You are the DOMAIN researcher for a deep code explanation report.

Read .mz/task/<task_name>/scope.md for the file list and user's question. Do NOT analyze internal code structure or trace execution — other researchers handle that. You provide external context that makes their findings make sense.

## External Dependencies Detected
<list of external libraries, protocols, and services identified during dispatch configuration>

## Research Checklist

**Library/Framework Context**: per dependency — what it solves, idiomatic usage, core abstractions; configuration rationale (why non-default values); API contracts (consistency, rate limits, error codes, pagination, versioning)

**Protocol/Standard Knowledge**: wire protocols (HTTP/2, WebSocket, gRPC, MQTT) — protocol details explaining code structure; standards compliance (OAuth, JWT, CORS, CSP) — required vs actual; data formats (protobuf, JSON-LD, msgpack) and their properties

**Domain Patterns**: architectural patterns in use (event sourcing, CQRS, saga, circuit breaker) — what failure mode each addresses; best practices comparison vs recommended usage; known pitfalls for these technologies and whether code avoids them

**Backing Decisions**: technology choice rationale (why X over alternatives, trade-offs represented); version-specific behavior or workarounds

Use WebSearch and WebFetch to verify technical claims. Cite sources. Focus on details explaining THIS code's structure, not general tutorials.

## Output
Write to .mz/task/<task_name>/research_domain.md with sections: Dependency Profiles (purpose, abstractions, config rationale per dep), Protocol/Standard Context, Domain Patterns (name, problem solved, quality), Technology Trade-offs, Pitfall Check, Diagram Suggestions (service architecture, API flows, handshakes).
```

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
- Keep to ≤ 20 nodes — group small files into their directory if needed

**2. Primary Execution Flow Diagram** (mandatory) — mermaid `sequenceDiagram` or `flowchart`:

- The main entry point through processing to output/side-effect
- All major branching points as `alt`/`opt` blocks (sequence) or diamond nodes (flowchart)
- Error paths as distinct flows (not just a single "error" box)
- External call-outs (DB queries, API calls) as interactions with named external participants
- Keep to ≤ 30 steps — summarize repetitive sections

**Additional diagrams** — include ALL that apply to the scope:

| #   | Type       | Mermaid syntax    | When to include                                        | Key elements                                                                                                           |
| --- | ---------- | ----------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| 3   | Data Flow  | `flowchart LR`    | Data undergoes significant transformations             | Input shape → transformation nodes with type annotations → output shape; validation as diamonds                        |
| 4   | Sequence   | `sequenceDiagram` | Multi-component interactions (API chains, event flows) | One participant per module/service; request/response pairs; `alt` blocks for errors; `activate`/`deactivate` for async |
| 5   | Class/Type | `classDiagram`    | Meaningful type hierarchies or composition             | Interfaces at top, implementations below with key methods; composition as aggregation arrows                           |
| 6   | ER         | `erDiagram`       | Code manages structured data with relationships        | Entities with key fields, relationships with cardinality; only entities the scope interacts with                       |
| 7   | State      | `stateDiagram-v2` | Code manages explicit state transitions                | All states as nodes, transitions labeled with triggers, guard conditions, start/end states                             |

### 3.3 Report template

Write the report to the resolved output path:

```markdown
# Code Explanation: <scope summary>

> <User's question, if one was asked. Omit this block if no question.>

## Overview

<2-3 paragraph executive summary. What this code does. Its role in the larger system. The key insight a reader should take away. If the user asked a question, lead with a direct answer. Written for someone who has never seen this code.>

## Architecture

### High-Level Diagram

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

<Additional mermaid diagrams as applicable — sequence, class, ER, state. Each with a short intro explaining what it shows and why it matters.>

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

1. **Reference integrity**: verify every `file:line` reference actually exists — read the file and confirm the line contains what you claim
1. **Diagram validity**: ensure mermaid diagrams use correct syntax — balanced quotes, valid node IDs (no spaces without quotes), proper arrow syntax, no dangling references
1. **Mandatory diagrams present**: architecture diagram + execution flow diagram must both exist
1. **Question answered**: if the user asked a specific question, verify the Overview section directly answers it
1. **No fabrication**: every claim about code behavior must be traceable to a specific file and line — do not describe behavior you inferred but didn't verify by reading the code

Write the report to the output path. Update state to `completed`. Report to the user: one-paragraph summary of what the report covers, plus the path to the full report.
