# Phase 1: Install / Update / Uninstall

Detailed implementation for installing, replacing, and removing the governance policy block in `CLAUDE.md`. Entered from SKILL.md Phase 0 after the setup block is emitted. There is a single policy block, not a rule set — exactly one sentinel pair per file.

The policy uses its **own** sentinel namespace (`mz-gov:governance-policy`), distinct from `init-rules`' `mz-rule:` blocks, so both can coexist in the same `CLAUDE.md` without interfering.

## Step 1: Resolve target path

| Scope   | Target                |
| ------- | --------------------- |
| project | `./CLAUDE.md`         |
| global  | `~/.claude/CLAUDE.md` |

If the file is missing and this is not `--uninstall`, flag `will_create = true` for the approval gate. Record the resolved path in `state.md` (`Target:`).

## Step 2: Read the policy body and resolve version

1. **Body source**: `${CLAUDE_PLUGIN_ROOT}/skills/gov-init/policy/governance-policy.md`. If unset or unreadable, escalate via AskUserQuestion with the failing path — do not invent the body.
1. **Version**: read `${CLAUDE_PLUGIN_ROOT}/../plugin.json` → `version`. If the file is missing or unreadable, use the literal `unknown`.
1. **Prepare the injected body**:
   - Strip any YAML frontmatter (the leading `---` … `---` block) if present.
   - Demote any H1 heading (`# `) in the body to H2 (`## `) so `CLAUDE.md` stays single-rooted. The policy file's title `# Development Governance Policy` becomes `## Development Governance Policy`. H2 and below pass through verbatim.

## Step 3: Sentinel format

The policy block is wrapped exactly:

```
<!-- mz-gov:governance-policy v=<plugin-version> start -->
<!-- source: governance-policy.md -->
<body, frontmatter stripped, H1 demoted to H2>
<!-- mz-gov:governance-policy end -->
```

- `<plugin-version>` = the version resolved in Step 2 (or `unknown`).
- The `source` comment records the origin file for future upgrade diffing.
- Detection matches on the namespace `mz-gov:governance-policy`, not on the version — the version in the start sentinel is informational.

Detection regexes:

- Start sentinel: `<!-- mz-gov:governance-policy v=\S+ start -->`
- End sentinel: `<!-- mz-gov:governance-policy end -->`

Exactly one block per file. If duplicates exist (manual edit or prior bug), stop and surface an error — do not guess which to replace.

## Step 4: Branch on idempotency state

Grep the resolved `CLAUDE.md` for the start sentinel and branch.

### State matrix

| File / sentinel state                 | `--force`? | Action           | Record      |
| ------------------------------------- | ---------- | ---------------- | ----------- |
| File missing (install)                | n/a        | create + append  | `installed` |
| Start sentinel **absent**             | n/a        | append           | `installed` |
| Start sentinel **present**            | no         | skip             | `skipped`   |
| Start sentinel **present**            | yes        | replace in place | `replaced`  |
| **Two or more** start sentinels found | any        | stop + error     | —           |

The duplicate-sentinel case is a hard stop: report the conflicting line numbers and ask the user to resolve before re-running. Never pick one arbitrarily.

### 4a. Install / replace — no `--uninstall`

**Approval gate** (runs before any write — see Step 5). Proceed only on explicit approval.

After approval, apply the action from the state matrix:

1. **File missing** → create `CLAUDE.md` with a minimal header, then append the sentinel block (Step 6 build). Use this header for **project** scope:

   ```
   # Project Rules

   <!-- This file is partially managed by mz-gov gov-init. Sentinel-wrapped blocks below are maintained automatically; content outside them is user-authored. -->
   ```

   Use `# Global Rules` for **global** scope. **Never overwrite an existing header** — only create one when the file does not exist.

1. **Sentinel absent** → append a blank line, then the sentinel block, at end of file. Record `installed`.

1. **Sentinel present, no `--force`** → skip; the policy is already installed. Record `skipped`. (Re-running is safe and changes nothing.)

1. **Sentinel present, `--force`** → replace the content **only between** the matching start and end sentinels in place, preserving everything outside the block (header, user content, any `mz-rule:` blocks). Record `replaced`.

### 4b. Uninstall — `--uninstall`

1. **Approval gate** — list the `mz-gov:governance-policy` sentinel pair found (with line numbers); confirm before removing. See Step 5.
1. After approval, remove the block (start sentinel through end sentinel, inclusive) **plus one adjacent blank line** to avoid leaving an accumulating gap.
1. **Never delete `CLAUDE.md` itself**, even if it ends up containing only the managed header and the `init-rules` blocks. Record `removed`.
1. If no sentinel is present, report "nothing to remove" and stop — do not error.

## Step 5: Approval gate

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated. This gate uses the two-surface plan pattern: the change is shown as an ordinary markdown chat message, then a short AskUserQuestion selector.

**Pre-read / resolve**: capture the resolved facts in context — the target path, whether the file will be created or modified, the action (`install` / `replace` / `uninstall`), and the exact sentinel block that will be written (install/replace) or removed (uninstall). The policy body is fixed source from `governance-policy.md`; show it so the user sees exactly what enters their `CLAUDE.md`.

**Surface 1 — emit the plan message.** Output the change as an ordinary markdown chat message (not inside a tool call). Show the verbatim block — never substitute a path or summary:

```
## CLAUDE.md change ready for review — gov-init

<install | replace | uninstall> the mz-gov governance policy block in `<resolved path>` (<create-new | modify-existing>).

### Block to <write | remove>  ·  sentinel `mz-gov:governance-policy v=<version>`

<verbatim sentinel-wrapped governance-policy block — the exact bytes that will be written, or the existing block that will be removed>

---
**Approve** → apply the change, then verify the sentinel count  ·  **Reject** → mark aborted, touch nothing  ·  reply with feedback to adjust scope or flags
```

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the block, it lives in the plan message above:

- question: `The CLAUDE.md change above is ready to apply.`
- options: **Approve** — apply the write and verify the sentinel count · **Reject** — abort, write nothing to `CLAUDE.md`

Two named options only; feedback (e.g. "use global scope instead") rides the free-text reply field.

**Response handling:**

- **Approve** → perform the Step 4 write, update `state.md` (`Action:`, `phase_complete: true`), proceed to Step 7 verification.
- **Reject** → set `Status: aborted_by_user`, write nothing to `CLAUDE.md`, stop.
- **Any other reply (feedback)** → adjust the scope or flags per the user's input, re-resolve the target, re-build the block, return to Surface 1, and re-emit the entire plan message. This is a loop — repeat until the user explicitly approves. Never write to `CLAUDE.md` without explicit approval.

## Step 6: Build the block (reference)

The exact bytes written for an install/replace (with version `0.44.0` as an example):

```
<!-- mz-gov:governance-policy v=0.44.0 start -->
<!-- source: governance-policy.md -->
## Development Governance Policy

<...body with H1 demoted to H2, frontmatter stripped...>
<!-- mz-gov:governance-policy end -->
```

For `replace`, only the span from the start sentinel line through the end sentinel line is overwritten; all surrounding content is preserved byte-for-byte.

## Step 7: Verification

Print a short summary, then confirm the on-disk state.

**Install / replace summary:**

```
CLAUDE.md: <resolved path> (created|modified)
  <appended|replaced>: mz-gov governance policy (v=<version>)

Scope: <project|global>   Action: <installed|replaced|skipped>
```

**Uninstall summary:**

```
Removed from <resolved path>:
  - mz-gov governance policy block

Action: removed
```

**On-disk check** (visible output, not a silent check):

- After **install / replace**: grep `CLAUDE.md` for the `mz-gov:governance-policy` start sentinel — expect **exactly one** match. Print the match count.
- After **uninstall**: grep for the start sentinel — expect **zero** matches. Print the match count.
- A `skipped` run (already installed, no `--force`) still verifies exactly one sentinel.

If the count is anything other than expected, report it as a failure with the actual count — do not claim success.

## Red Flags

- You modified `CLAUDE.md` without the approval gate.
- You replaced content **outside** the sentinel boundaries (a `--force` replace must touch only the span between the two sentinels).
- You overwrote an existing top-level header instead of leaving it untouched.
- You omitted the version tag in the start sentinel.
- You used the `mz-rule:` namespace instead of `mz-gov:governance-policy`, or otherwise collided with `init-rules` blocks.
- (uninstall) You deleted `CLAUDE.md` itself, or removed a block you did not author.
- You injected the body with its H1 intact, leaving `CLAUDE.md` with two top-level headings.
