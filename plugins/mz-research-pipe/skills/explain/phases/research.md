# Phase 2: Research Dispatch

Full detail for the research dispatch phase of the explain skill. Covers adaptive researcher dispatch based on scope and external dependencies, role-specific analysis prompts, and per-researcher artifact format.

## Contents

- [Phase 2: Research Dispatch](#phase-2-research-dispatch)
  - 2.1 Detect dispatch configuration
  - 2.2 Researcher artifacts
  - 2.3 Researcher prompts

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

Each researcher is read-only and returns its findings **inline in its response**. The **orchestrator** (not a sub-agent) writes the returned markdown to `.mz/task/<task_name>/research_<role>.md` using the Write tool, one call per returned response:

- `research_comprehensive.md` — when a single analyst handles everything
- `research_structure.md` — static structure and design analysis
- `research_flow.md` — runtime execution and data flow tracing
- `research_domain.md` — external dependency and domain knowledge

If a researcher returns `BLOCKED` or `NEEDS_CONTEXT`, still write the response content (preserves the blocker rationale) and note the failure in the state file.

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

Return the report as markdown **in your response** — the orchestrator persists to `.mz/task/<task_name>/research_comprehensive.md`. Use these sections:
- Per-File Analysis (purpose, API, key functions with file:line, deps)
- Execution Flow Traces (per entry point, numbered steps with file:line, branching as sub-lists)
- Data Flow Map (input type → stages → output type, all with file:line)
- Design Decisions (choice, rationale, trade-off, alternatives)
- Observations (strengths, issues, debt, gaps — all with file:line)
- Diagram Suggestions (see format below)

### Diagram Suggestions format

Write one structured block per proposed diagram. Do NOT write mermaid syntax; the orchestrator synthesizes it at Phase 3. Each block:

### Diagram: <type>
- **Type**: one of `flowchart`, `sequenceDiagram`, `classDiagram`, `stateDiagram-v2`, `erDiagram`, `mindmap`
- **Nodes/Participants**: bullet list of `<id> — <one-line description>` (alphanumeric/underscore ids only)
- **Key edges**: bullet list of `<src> → <dst> : <label>` (label explains the relationship or message)
- **Rationale**: one sentence — what question this diagram answers for the reader

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
Return the report as markdown **in your response** — the orchestrator persists to `.mz/task/<task_name>/research_structure.md`. Use these sections: Module Catalog (per-module purpose, API, deps, layer), Dependency Graph (nodes, edges, hubs, cycles), Design Patterns (each with WHY and file:line), Configuration Map, Error Model, Observations (all with file:line), Diagram Suggestions — candidates: architecture flowchart, classDiagram for type relationships, mindmap for large module hierarchies (see format below).

### Diagram Suggestions format

Write one structured block per proposed diagram. Do NOT write mermaid syntax; the orchestrator synthesizes it at Phase 3. Each block:

### Diagram: <type>
- **Type**: one of `flowchart`, `classDiagram`, `mindmap`
- **Nodes/Participants**: bullet list of `<id> — <one-line description>` (alphanumeric/underscore ids only)
- **Key edges**: bullet list of `<src> → <dst> : <label>` (label explains the relationship or message)
- **Rationale**: one sentence — what question this diagram answers for the reader
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
Return the report as markdown **in your response** — the orchestrator persists to `.mz/task/<task_name>/research_flow.md`. Use these sections: Entry Point Catalog, Execution Traces (numbered steps with file:line, branching as sub-lists), Data Flow Maps (input → stages with types → output), Side Effect Timeline (per path), Concurrency Analysis, Lifecycle, Diagram Suggestions — candidates: sequenceDiagram for multi-component interactions, flowchart for branching execution, stateDiagram-v2 if explicit states exist (see format below).

### Diagram Suggestions format

Write one structured block per proposed diagram. Do NOT write mermaid syntax; the orchestrator synthesizes it at Phase 3. Each block:

### Diagram: <type>
- **Type**: one of `sequenceDiagram`, `flowchart`, `stateDiagram-v2`
- **Nodes/Participants**: bullet list of `<id> — <one-line description>` (alphanumeric/underscore ids only)
- **Key edges**: bullet list of `<src> → <dst> : <label>` (label explains the relationship or message)
- **Rationale**: one sentence — what question this diagram answers for the reader
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
Return the report as markdown **in your response** — the orchestrator persists to `.mz/task/<task_name>/research_domain.md`. Use these sections: Dependency Profiles (purpose, abstractions, config rationale per dep), Protocol/Standard Context, Domain Patterns (name, problem solved, quality), Technology Trade-offs, Pitfall Check, Diagram Suggestions — candidates: sequenceDiagram for handshakes/protocol flows, flowchart for service topology (see format below).

### Diagram Suggestions format

Write one structured block per proposed diagram. Do NOT write mermaid syntax; the orchestrator synthesizes it at Phase 3. Each block:

### Diagram: <type>
- **Type**: one of `sequenceDiagram`, `flowchart`, `erDiagram`
- **Nodes/Participants**: bullet list of `<id> — <one-line description>` (alphanumeric/underscore ids only)
- **Key edges**: bullet list of `<src> → <dst> : <label>` (label explains the relationship or message)
- **Rationale**: one sentence — what question this diagram answers for the reader
```
