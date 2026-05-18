# Phase 3: Synthesis & Answer

Compile the research findings into a direct answer, write a report, and present the answer in chat. This phase produces no code changes.

## 3.1 Synthesize

Read `.mz/task/<task_name>/codebase_findings.md` and, if Phase 2 ran, `.mz/task/<task_name>/web_findings.md`. Then construct the answer:

- **Answer the question asked** — lead with a direct response, not a preamble. If the question was comparative ("why X over Y"), the answer states the reason; if a capability question ("does the repo support Z"), it states yes/no/partially first.
- **Ground every claim** — codebase claims cite `file:line`; external claims cite the official source. A claim with no citation does not belong in the answer.
- **Surface conflicts and gaps honestly** — if researchers disagreed, or a `CONFLICT DETECTED` / `UNVERIFIED` token appeared, present both sides and label confidence. If a phase was skipped or a researcher returned partial findings, say what is not covered.
- **Match depth to the question** — a narrow factual question gets a few sentences; a broad architectural question gets a structured answer. Do not pad.

## 3.2 Write the report

Write the report to `.mz/reports/<YYYY_MM_DD>_ask_<slug>.md` (append `_v2`, `_v3` on same-day collision). Use this template:

```markdown
# Answer: <question, verbatim>

## Question type
<codebase | external | hybrid>

## Answer
<the direct, complete answer — the load-bearing section>

## Evidence
### From the codebase
<bulleted findings, each with file:line>

### From external sources
<bulleted findings, each with a cited source — omit this section if Phase 2 did not run>

## Confidence & Gaps
<confidence level, any conflicts surfaced, anything the research could not settle>

## Sources
<list of files inspected and external URLs cited>
```

Omit the external-sources section entirely when `Question type: codebase`.

## 3.3 Present in chat

Present the answer directly in chat — the user should not need to open the report file to get their answer. Lead with the direct answer, include the key evidence, then point to the report path for the full detail.

## 3.4 Verification block

Output a visible verification block, then stop:

```
ask complete
- Question type: <codebase | external | hybrid>
- Codebase researchers: <N> | Web researchers: <M>
- Sources cited: <count>
- Report: <absolute path>
```

Update `state.md`: `Status: complete`, `Phase: 3`, `phase_complete: true`, `what_remains: []`, append the report path to `FilesWritten`.
