# Evidence-Tier Rules

Used by Phase 3 (Consolidate) to cap finding severity based on the quality of evidence a researcher provides. Findings are never silently discarded — they are capped and annotated.

## Evidence Tier Definitions

| Evidence Tier | Label     | Definition                                                                                                             | Max Allowed Severity     |
| ------------- | --------- | ---------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| T0            | Proven    | Reproducing failing test OR exploit PoC OR measured delta (profiler before/after, mutation kill score)                 | Critical                 |
| T1            | Confirmed | SAST CWE match with specific code location + reachability traced OR STRIDE boundary crossing with stated attacker path | High                     |
| T2            | Detected  | Deterministic pattern match with cited rule + code reference (file:line)                                               | Medium                   |
| T3            | Advisory  | Heuristic, "may", "could", "suspicious pattern", similarity to known issue, unsupported assertion                      | Low (labeled "Advisory") |

## Capping Rule

When a researcher asserts a severity that exceeds what their evidence supports, the finding is **capped** — not discarded.

In `findings.md`, the capped finding shows:

- `severity_original`: what the researcher asserted
- `severity_capped`: the evidence-adjusted severity
- `evidence_tier`: T0/T1/T2/T3
- `cap_reason`: one sentence explaining why the original severity was not supported

### Examples

| Researcher asserts | Evidence provided                                           | Evidence tier | Capped to         |
| ------------------ | ----------------------------------------------------------- | ------------- | ----------------- |
| Critical           | Reproducing test that triggers the bug                      | T0            | Critical (no cap) |
| Critical           | "This pattern is similar to CVE-2023-XXXX"                  | T3            | Low (Advisory)    |
| High               | SAST CWE-89 match at `db.py:47` with traced user-input path | T1            | High (no cap)     |
| High               | "This looks like it could allow injection"                  | T3            | Low (Advisory)    |
| Medium             | Pattern `yaml.load(` without `Loader=` at `config.py:12`    | T2            | Medium (no cap)   |
| Critical           | Pattern match only, no reachability trace                   | T2            | Medium (capped)   |

## Applying Evidence Tiers in Practice

Researchers must include an `evidence_tier` field with every finding. If omitted, the consolidation agent assigns T3 (Advisory) by default.

For Critical findings, a T0-quality reproducer (failing test or PoC) must be attached or the finding is automatically capped to High (T1 max).

STRIDE-delta findings with a stated attacker path qualify as T1 by default. STRIDE-delta findings without an attacker path qualify as T2.

Blinded-inversion findings (Wave B) are not severity-ranked by the researcher; the consolidation agent assigns an initial evidence tier of T2 if the finding cites a specific code location, T3 otherwise.
