# vault-schema DSL v1 Syntax Reference

Lazy-loaded reference for the YAML schema DSL consumed by `vault-schema`. Grep this file for the specific construct you need — do not load the whole file into context.

## File location

The schema lives at `.mz/vault-schema.yml` under the vault root. The exact path is exposed as the `SCHEMA_PATH` constant in `SKILL.md`.

## Top-level shape

The file contains a single top-level `note_types:` map. Each key is a note type name (the value that appears as `type:` in note frontmatter). Each value declares the rules for that type.

```yaml
# .mz/vault-schema.yml
note_types:
  <type_name>:
    required: [...]
    optional: [...]
    allowed_values:
      <field>: [...]
```

Three rule keys are supported in v1:

- `required` — list of frontmatter keys that MUST be present for notes of this type. Missing a required key produces a `Critical:` finding.
- `optional` — list of frontmatter keys that MAY be present. Used only to distinguish declared-optional keys from unknown keys; a missing optional key never triggers a finding.
- `allowed_values` — map of `<field>: [v1, v2, ...]` declaring a closed enum for string fields. A note whose declared field carries a value outside the list produces a `Critical:` finding.

## v1 DSL template

Copy this template into `.mz/vault-schema.yml` when the schema does not yet exist. The three note_types (`permanent`, `fleeting`, `research`) match the vault conventions used across `process-notes`, `vault-ingest`, and `vault-research`.

```yaml
note_types:
  permanent:
    required: [status, created, tags]
    optional: [source, last_reviewed, epistemic_status, confidence]
    allowed_values:
      status: [draft, evergreen, archived]

  fleeting:
    required: [created, tags]
    optional: [source, review_after]

  research:
    required: [status, created, source_type]
    optional: [report_path, captured_at]
    allowed_values:
      status: [draft, evergreen]
      source_type: [research-report, voice, image, pdf, youtube, screenshot]
```

## Semantics

### Order does not matter

Key order inside `required`, `optional`, and `allowed_values` lists is irrelevant. The validator normalizes to sets before comparing.

### `allowed_values` applies to strings only

Enums constrain string-valued fields. If the frontmatter field carries a list (e.g., `tags: [a, b, c]`), the validator does not evaluate `allowed_values` against list elements in v1. Declare list fields in `required` or `optional` and leave enum enforcement for a future rule (`list_allowed_values:` is a v2 candidate).

### Missing schema entry = pass-through

If a note's `type:` is not a key in `note_types:`, the validator skips the note. No finding is recorded. This is intentional: unknown types should not block validation runs while the schema is under construction. Add the type to `note_types:` when you are ready to enforce rules for it.

### Missing `type:` frontmatter = skipped

If a note has no `type:` field in its frontmatter, the validator skips it. `type:` is the lookup key into `note_types:` — not a rule the validator enforces. Missing-`type:` notes are the concern of `vault-schema migrate`, which can propose a type assignment.

### Unknown keys become Nit findings

When a note's frontmatter contains a key that is NOT in `required`, NOT in `optional`, and NOT the literal `type:` key, the validator records a `Nit:` finding suggesting either the key be removed or added to the `optional` list. Nit findings never fail the verdict — they are advisory.

## Interaction with the migrator

`vault-schema migrate` reads the validator's `validation_report.md` as its source of truth:

- `Critical:` findings with `rule_violated: required_field_missing` become proposed frontmatter additions.
- `Critical:` findings with `rule_violated: allowed_values_violation` become proposed value changes — the migrator asks the user to pick from the declared enum before writing.
- `Nit:` findings are never auto-migrated in v1. They can be addressed by editing the schema (adding the key to `optional`) or by hand.

The migrator always writes `rollback.md` BEFORE any frontmatter patch. If the schema itself is under active revision, re-run `vault-schema validate` before migrating — the migrator trusts the report, not the live schema file.

## Common patterns

### Add a new note_type

Append under `note_types:`:

```yaml
  daily:
    required: [date, tags]
    optional: [mood, weather]
    allowed_values:
      mood: [calm, anxious, focused, tired]
```

### Tighten a constraint without breaking existing notes

When adding a new `required` field to an existing type, expect the next validation run to surface `Critical:` findings across all pre-existing notes of that type. Run `vault-schema migrate` with user approval to backfill the field rather than editing notes by hand.

### Relax a constraint

Remove the field from `required` and (if still allowed) add it to `optional`. No migration needed — the validator will drop any open `required_field_missing` findings on the next run.

### Introduce an enum

Add an entry under `allowed_values` for an existing string field. The next validation run will surface any out-of-enum values as `Critical:` findings.

## What v1 does NOT support

Document what is intentionally out-of-scope so future schema authors know where the edges are.

- **Cross-field constraints** (e.g., "if `status` is `evergreen` then `last_reviewed` is required"). v1 is per-field only.
- **Regex patterns** for string fields. v1 is exact-match via `allowed_values`.
- **Type coercion** (e.g., forcing `created` to ISO date format). The validator checks presence, not shape.
- **Inheritance between note_types**. Each type stands alone — copy the rules if two types share them.
- **List-element enumeration**. `tags` can be declared `required` but individual tag values are not constrained in v1.

v2 candidates (document, don't implement): `list_allowed_values`, `regex`, `conditional_required`, `inherits_from`.

## Bootstrap via AskUserQuestion

When `vault-schema validate` runs and `.mz/vault-schema.yml` is absent, the skill presents the v1 template above via AskUserQuestion and asks the user to accept, reject, or edit. On acceptance the skill writes the template to `SCHEMA_PATH` and continues validation. This is the ONE place the skill writes to `.mz/` on behalf of the user — everywhere else the schema file is read-only.
