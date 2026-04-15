# Phases 1-2: Reproduce and Diagnose

## Phase 1: Reproduce

**Goal**: Confirm the bug exists and capture a reliable reproduction.

### 1.1 Detect tooling

Dispatch a `pipeline-tooling-detector` agent (model: **haiku**):

```
Detect project tooling and write the result to:
output_path: .mz/task/<task_name>/tooling.md
```

Read `.mz/task/<task_name>/tooling.md` when done.

If the **Test command** field is "none detected": ask the user via AskUserQuestion how to run tests. Do not proceed without a test command.

### 1.2 Choose reproduction strategy

Based on the input type classified in Phase 0:

| Input type      | Strategy                                                                                           |
| --------------- | -------------------------------------------------------------------------------------------------- |
| `failing_test`  | Run the test directly. If it fails, reproduction is done. If it passes, investigate why.           |
| `stack_trace`   | Extract file:line references, read code at those locations, identify the trigger condition.        |
| `error_message` | Grep for the error string across the codebase, trace to the origin function, identify the trigger. |
| `free_text`     | Dispatch researcher to locate relevant code and attempt reproduction.                              |
| `github_issue`  | Parse issue for steps/tests/error messages, then apply the matching strategy above.                |

### 1.3 Direct reproduction (failing_test, stack_trace, error_message)

For these input types, attempt reproduction directly:

1. **failing_test**: Run the specific test. Capture full output.
1. **stack_trace**: Read the code at each frame. Identify the failing condition. If a test exercises that path, run it. If not, check if you can write a minimal trigger command.
1. **error_message**: Grep for the exact string. Read the function that raises/throws it. Trace callers to find how to trigger it. Run any existing test that covers the path.

If direct reproduction succeeds, save results and skip to 1.5.

If direct reproduction fails or the path is unclear, fall through to 1.4.

### 1.4 Researcher-assisted reproduction (free_text, or fallback)

Dispatch a `pipeline-researcher` agent (model: **sonnet**):

```
Investigate a bug report and attempt to reproduce it.

## Bug Report
<original bug description / issue content>

## Input Type
<classified type>

## What We Know So Far
<any file:line references, error strings, or partial traces from 1.3 — omit if first attempt>

## Tooling
Read .mz/task/<task_name>/tooling.md for test/lint commands.

## Instructions
1. Search the codebase for code related to the bug description.
2. Trace the execution path that would trigger the reported behavior.
3. Identify the specific file:line where the bug manifests.
4. If an existing test covers this path, run it and report the result.
5. If no test exists, describe how to trigger the bug (input, API call, sequence of operations).
6. If you cannot find relevant code or a trigger path, report what you searched and what you found.

## Report
- Relevant files and their roles
- Execution path from entry point to bug manifestation
- Reproduction method (test name, command, or manual steps)
- Reproduction result: confirmed / static-only / unable
- Key observations about the surrounding code
```

### 1.5 Handle reproduction result

| Result                  | Action                                                                                                           |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **Reproduced**          | Save to `reproduction.md` with test/command output, proceed to Phase 2.                                          |
| **Static confirmation** | Code analysis confirms the bug but no runtime trigger found. Note it, proceed to Phase 2.                        |
| **Can't reproduce**     | Escalate via AskUserQuestion with what was tried and found. Ask for more context. Do NOT proceed with guesswork. |

Write `.mz/task/<task_name>/reproduction.md`:

```markdown
# Reproduction

## Method
<test name / command / static analysis>

## Result
<reproduced / static_confirmation / unable>

## Output
<test output or code analysis summary>

## Key Files
- <file:line> — <role in the bug>
```

Update state: `reproduced` field and phase to `reproduced`.

______________________________________________________________________

## Phase 2: Diagnose

**Goal**: Identify the root cause and propose a minimal fix. Conditionally research external dependencies.

### 2.1 Codebase investigation

Dispatch a `pipeline-researcher` agent (model: **sonnet**):

```
Diagnose the root cause of a confirmed bug.

## Bug
<original bug description>

## Reproduction
Read .mz/task/<task_name>/reproduction.md for how the bug was reproduced.

## Instructions
1. Read the reproduction files and trace backward from the failure point to the root cause.
2. Identify the exact file:line where the logic is wrong.
3. Explain WHY the current code is wrong (not just what it does).
4. Assess impact scope: what else could this bug affect?
5. Propose a minimal fix — fewest lines changed, no refactoring, no improvements.
6. Rate fix risk: low (isolated change) / medium (touches shared code) / high (architectural).
7. Note any external dependencies involved (APIs, libraries, protocols, specs).

## Report
- Root cause: file:line + explanation of why it's wrong
- Impact scope: what else is affected
- Proposed fix: minimal description
- Fix risk: low / medium / high
- External dependencies: list any, or "none"
- Similar patterns: other locations with the same bug pattern (don't require fixing)
```

### 2.2 Detect external dependency involvement

After the codebase researcher returns, scan the report for external dependencies. A bug involves external dependencies if:

- The root cause is incorrect usage of a third-party API or library
- The fix requires understanding protocol behavior (HTTP, WebSocket, gRPC, etc.)
- The bug is caused by version-specific library behavior or breaking changes
- The correct behavior depends on an external specification or standard

If **no external dependencies**: skip to 2.4.

If **external dependencies detected**: proceed to 2.3.

**Parallel dispatch optimization**: If external dependency involvement is obvious from the bug report itself (e.g., "WebSocket reconnection fails", "OAuth token refresh broken", "gRPC deadline exceeded"), dispatch both the codebase researcher (2.1) and domain researcher (2.3) in parallel. Otherwise, run them sequentially.

### 2.3 Domain research (conditional)

Dispatch a second `pipeline-researcher` agent (model: **sonnet**):

```
Research external domain context for a bug involving <dependency/protocol/API>.

## Bug Context
<root cause summary from 2.1, or bug description if running in parallel>

## External Dependency
<specific library, API, protocol, or spec involved>

## Questions to Answer
1. What is the correct behavior / usage pattern for this dependency?
2. Are there known issues, gotchas, or version-specific quirks?
3. What does the official documentation say about this specific scenario?
4. Are there common mistakes developers make with this dependency?
5. What is the recommended fix approach?

Use WebSearch and WebFetch to find:
- Official documentation for the dependency
- GitHub issues or discussions about similar problems
- Stack Overflow answers for the specific error pattern
- Changelog entries for relevant version changes

## Report
- Correct behavior per documentation
- Known issues or gotchas relevant to this bug
- Recommended fix approach based on official guidance
- Documentation links consulted
- Confidence level: high (docs are clear) / medium (inferred) / low (ambiguous)
```

### 2.4 Synthesize diagnosis

Merge codebase investigation + domain research (if any) into `.mz/task/<task_name>/diagnosis.md`:

```markdown
# Diagnosis

## Root Cause
<file:line — what's wrong and why>

## Impact Scope
<what else is affected by this bug>

## Proposed Fix
<minimal change description — what to modify and how>

## Fix Risk
<low / medium / high — with explanation>

## External Context
<domain research findings — omit section entirely if no external deps>
<correct behavior per docs, gotchas, recommended approach>

## Similar Patterns
<other locations with the same bug pattern — not fixing, just noting>
```

Update state phase to `diagnosed`.

**Proceed to Phase 2.5 (User Approval Gate) in SKILL.md.**
