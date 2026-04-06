# Phases 2-3: Research and Report Generation

Full detail for the research and report phases of the dev-explain-code skill. Covers adaptive researcher dispatch, role-specific analysis prompts, and the comprehensive report template with mandatory mermaid diagrams.

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

## Scope
Read .mz/task/<task_name>/scope.md for the file list and the user's question/focus.

## User's Question
"<question or 'general explanation'>"

## Analysis Checklist

Read every file in scope thoroughly — line by line, not skimming. For each file, analyze:

### Structure
1. **Purpose**: what this file/module does and its role in the larger system
2. **Public API**: exported functions, classes, endpoints — what other code calls into
3. **Internal organization**: how the file is structured, major sections
4. **Dependencies**: what it imports (internal and external), what imports it
5. **Configuration**: environment variables, config files, feature flags it reads

### Execution Flow
6. **Entry points**: where execution begins — request handlers, main functions, event listeners, CLI commands
7. **Call chains**: trace the primary execution paths step by step — what calls what, in what order, with what arguments
8. **Branching logic**: conditional paths, error branches, early returns — map ALL paths, not just the happy path
9. **Data transformations**: how data changes shape as it flows — input format to intermediate to output, with types at each stage
10. **Side effects**: database writes, file I/O, network calls, cache mutations, logging — anything that affects state beyond the function
11. **Concurrency**: async/await patterns, thread spawning, locks, queues, parallelism — where ordering matters

### Design Rationale
12. **Pattern choices**: identify design patterns used (repository, factory, observer, middleware chain, etc.) and explain WHY they fit this context
13. **Trade-offs**: what was gained and lost by current design choices — performance vs. readability, flexibility vs. simplicity
14. **Defensive coding**: where and why input validation, error handling, retries, timeouts exist
15. **Historical context**: check git blame on files with surprising patterns — recent rewrites, TODO comments, or workarounds often explain unusual code

### Observations (document, don't fix)
16. **Potential issues**: bugs, race conditions, missing error handling, unguarded edge cases — things that COULD go wrong
17. **Design debt**: overly complex sections, duplicated logic, leaky abstractions, unclear naming
18. **Missing pieces**: error paths without handling, unhappy paths not covered, validation gaps
19. **Strengths**: well-designed sections, clean abstractions, good test coverage — call out what works well too

## Output

Write to .mz/task/<task_name>/research_comprehensive.md with sections: Per-File Analysis (purpose, API, key functions with file:line, dependencies), Execution Flow Traces (per-entry-point numbered steps with file:line, branching as sub-lists), Data Flow Map (input type → stages → output type with file:line), Design Decisions (choice, rationale, trade-off, alternatives), Observations (strengths, issues, debt, gaps — all with file:line), Diagram Suggestions (type, content, key nodes/edges — no mermaid syntax, just descriptions).

Be thorough. Do not skip complexity — explain it.
```

______________________________________________________________________

#### Code Structure Analyst

Used for large scopes (> 10 files). Handles static structure and design. Spawn a `pipeline-researcher` agent (model: **sonnet**):

```
You are the STRUCTURE analyst for a deep code explanation report.

## Scope
Read .mz/task/<task_name>/scope.md for the file list and user's question.

## Your Focus
Analyze the static structure and design of the code. Do NOT trace runtime execution — another researcher handles that.

## Analysis Checklist

Read every file in scope. Analyze:

### Architecture
1. **Module purposes**: what each file/module does, its responsibility boundary
2. **Public APIs**: exported functions, classes, types, constants — the contract each module offers to its callers
3. **Dependency graph**: what imports what within scope — note circular dependencies, hub modules, leaf modules
4. **Layering**: identify architectural layers (controller/service/repository, handler/middleware/model, etc.) and whether the code respects layer boundaries
5. **Boundaries**: where this scope interfaces with the rest of the system — the seam files, the external-facing APIs

### Design
6. **Patterns**: identify design patterns (factory, observer, middleware, repository, strategy, decorator, etc.) and explain WHY each was chosen for its context — what problem it solves here specifically
7. **Type system**: how types, interfaces, protocols, or abstract bases structure the code — inheritance hierarchies, composition patterns, generic usage
8. **Configuration surface**: env vars, config files, feature flags, constants — the tunable parameters and their effects
9. **Error model**: how errors are represented (exception types, result types, error codes), propagated (thrown, returned, logged), and handled across module boundaries

### Code Organization
10. **Naming conventions**: patterns in function/variable/file naming — what naming communicates about purpose, visibility, or lifecycle
11. **Grouping logic**: how related functionality is co-located or separated across files and directories
12. **Abstraction quality**: where abstractions are clean (single responsibility, stable interface) vs. leaky (caller needs to know internals, mixed concerns)

### Observations
13. **Structural strengths**: clean separations, consistent patterns, well-defined boundaries
14. **Structural debt**: tangled dependencies, god classes/files, unclear responsibilities, naming that misleads
15. **Missing structure**: places where an abstraction would clarify intent, or where tight coupling will cause pain later

## Output
Write to .mz/task/<task_name>/research_structure.md with sections: Module Catalog (per-module purpose, API, deps, layer), Dependency Graph (nodes, directed edges, hub nodes, cycles), Design Patterns (each with WHY and file:line), Configuration Map (all config points and effects), Error Model (error flow across scope), Observations (strengths, debt, gaps — all with file:line), Diagram Suggestions (component/class diagram content — nodes, edges, subgraphs).
```

______________________________________________________________________

#### Execution Flow Analyst

Used for large scopes (> 10 files). Handles runtime behavior tracing. Spawn a `pipeline-researcher` agent (model: **sonnet**):

```
You are the EXECUTION FLOW analyst for a deep code explanation report.

## Scope
Read .mz/task/<task_name>/scope.md for the file list and user's question.

## Your Focus
Trace how code RUNS — entry points, call chains, data transformations, side effects, timing. Do NOT analyze static structure or design patterns — another researcher handles that.

## Analysis Checklist

Read every file in scope. Trace:

### Entry Points
1. **Catalog all entry points**: HTTP handlers, CLI commands, event listeners, cron jobs, main functions, signal handlers, callback registrations — every way execution enters this code
2. **Per entry point**: what triggers it, what arguments or context it receives, what it ultimately produces or effects

### Call Chains
3. **Happy-path traces**: for each entry point, trace the primary call chain step by step — function A at file:line calls B at file:line with args X, B validates then calls C, C queries the database, etc. Every step must have file:line.
4. **Error paths**: trace what happens when things fail — which exceptions are caught where, what gets retried, what propagates to the caller, what gets swallowed
5. **Branching points**: every significant conditional that changes the execution path — document ALL branches, not just the common case. Note which branches are guards (early returns) vs. genuine forks.
6. **Recursion and loops**: any recursive calls or iteration patterns that process collections — note termination conditions and what determines iteration count

### Data Flow
7. **Input shapes**: what data enters at each entry point — request bodies, CLI args, event payloads, environment reads. Include types and validation steps.
8. **Transformations**: how data changes shape at each handoff — function A receives `RawRequest`, extracts fields, constructs `ValidatedInput`, passes to B which produces `DomainModel`. Map the type at every boundary.
9. **Output shapes**: what comes out — response bodies, return values, written records, emitted events. Include serialization steps.
10. **Intermediate state**: accumulators, caches, buffers, context objects that carry state across call boundaries

### Side Effects
11. **External interactions**: database queries (read vs. write), HTTP requests, file I/O, message queue operations, cache reads/writes — every interaction with systems outside the code, in execution order
12. **State mutations**: what persistent state changes — database records created/updated/deleted, files written, caches invalidated, sessions modified
13. **Concurrency patterns**: async operations, parallel execution, lock acquisition/release, shared state access — where race conditions are possible and how they're prevented (or not)

### Timing and Lifecycle
14. **Initialization**: what happens at startup vs. per-request vs. lazily — module-level code, singleton initialization, connection pool setup
15. **Cleanup**: shutdown hooks, context managers, deferred calls, finalizers — resource release paths
16. **Ordering constraints**: operations that MUST happen in sequence and what breaks if reordered

## Output
Write to .mz/task/<task_name>/research_flow.md with sections: Entry Point Catalog (trigger, inputs, outputs per entry point), Execution Traces (numbered steps with file:line, branching as sub-lists), Data Flow Maps (input type → stages with types → output), Side Effect Timeline (ordered external interactions per path), Concurrency Analysis (shared state, synchronization, races), Lifecycle (init order, cleanup, ordering constraints), Diagram Suggestions (sequence + flowchart content — actors, messages, decision nodes, not mermaid syntax).
```

______________________________________________________________________

#### Domain Researcher

Dispatched when external dependencies are detected. Spawn a `pipeline-researcher` agent (model: **sonnet**):

```
You are the DOMAIN researcher for a deep code explanation report.

## Scope
Read .mz/task/<task_name>/scope.md for the file list and user's question.

## External Dependencies Detected
<list of external libraries, protocols, and services identified during dispatch configuration>

## Your Focus
Research the external knowledge needed to understand WHY this code is written the way it is. Do NOT analyze internal code structure or trace execution — other researchers handle that. You provide the domain context that makes their findings make sense.

## Research Checklist

### Library and Framework Context
1. **Per dependency**: what problem does it solve, what's the idiomatic usage pattern, what are its core abstractions (e.g., for SQLAlchemy: Session, Engine, declarative base; for Express: middleware chain, Router, error handler)
2. **Configuration rationale**: if the code configures a library in a specific way (pool sizes, timeout values, retry policies, serialization options), research WHY that configuration — what behavior does it produce, what are the defaults, what problems does the non-default value solve
3. **API contracts**: what guarantees do external APIs provide — consistency models, rate limits, error codes, pagination behavior, versioning strategy, deprecation notices

### Protocol and Standard Knowledge
4. **Wire protocols**: if the code implements or consumes a protocol (HTTP/2 streams, WebSocket frames, gRPC service definitions, MQTT QoS levels), document the protocol-level details that explain why the code is structured the way it is
5. **Standards compliance**: OAuth 2.0 flows, JWT validation requirements, CORS preflight rules, Content-Security-Policy — what the standard REQUIRES vs. what the code actually does, and whether gaps are intentional or oversights
6. **Data formats**: serialization choices (protobuf schema design, JSON-LD context, msgpack vs. JSON) and what properties they provide (schema evolution, compact encoding, human readability)

### Domain Patterns
7. **Architectural patterns**: if the code follows recognized patterns for its domain (event sourcing, CQRS, saga orchestration, circuit breaker, bulkhead), explain what the pattern is, what failure mode it addresses, and how this code implements it
8. **Best practices comparison**: how does the code's approach compare to the library/framework's recommended practices — following guides, or diverging for a reason
9. **Known pitfalls**: common mistakes with these technologies — N+1 queries with ORMs, connection leaks with pools, message ordering with async queues — and whether this code avoids or falls into them

### Backing Decisions
10. **Technology choice rationale**: WHY these libraries or services were likely chosen over alternatives — what constraints or trade-offs do they represent (e.g., chose Redis over Memcached for pub/sub support; chose gRPC over REST for streaming)
11. **Version-specific behavior**: if the code uses version-specific features or works around version-specific bugs, document the version context

## Rules
- Use WebSearch and WebFetch to verify technical claims. Do NOT guess about library behavior, protocol requirements, or API contracts.
- Cite sources where possible — link to official docs, RFCs, or authoritative blog posts.
- Focus on details that explain THIS code's structure, not general tutorials.

## Output
Write to .mz/task/<task_name>/research_domain.md with sections: Dependency Profiles (purpose, abstractions, idiomatic patterns, config rationale per dep), Protocol/Standard Context (relevant details only, not full specs), Domain Patterns (name, problem solved, implementation quality), Technology Trade-offs (what was gained/lost per choice vs. alternatives), Pitfall Check (which apply, how code handles them), Diagram Suggestions (service architecture, API flows, protocol handshakes).
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
