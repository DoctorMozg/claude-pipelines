# Phase 5: Enforce — Link the Artifact, Recommend the Next Step

Tie the durable artifact to where the work actually lands — the commit, the branch, the PR — and point the user at the next skill. This phase reads git state, appends a links section to the committed artifact, advances status where it makes sense, and **recommends** the follow-on skill without ever invoking it. The accepted decision is the input a human feeds to the next pipeline, not a trigger that auto-fires one.

## Inputs (from Phase 4)

- The durable artifact path under `docs/` (e.g. `docs/decisions/0001-use-redis.md`), its number, and status.
- `.mz/task/<task_name>/provenance.md` with the recorded `human_signoff`.

## Step 5.1 — Detect git context

Run read-only git probes (the working dir may not be a repo — handle that gracefully):

```bash
git rev-parse --is-inside-work-tree 2>/dev/null   # is this a repo at all?
git rev-parse HEAD 2>/dev/null                     # current commit
git rev-parse --abbrev-ref HEAD 2>/dev/null        # current branch
```

If the directory is not a git repo, skip straight to the "implementation pending" path in Step 5.3 — no commit, no branch, no PR to link.

## Step 5.2 — Detect an open PR (read-only, tiered fallback)

Look for an open PR on the current branch, read-only. Use the fallback chain — never block on the first failure:

1. `gh pr view --json number,url,title 2>/dev/null` — the GitHub CLI.
1. If `gh` is unavailable (not installed, not authenticated, rate-limited) and the session exposes GitHub MCP tools (`mcp__*github*`), use those to look up the PR for the branch.
1. If neither is available, try REST: `curl -fsSL -H "Authorization: Bearer $GITHUB_TOKEN" -H "Accept: application/vnd.github+json" "https://api.github.com/repos/{owner}/{repo}/pulls?head={owner}:{branch}&state=open"`.

If all three tiers fail, there is simply no PR link to add — that is not an error. Record "no open PR found" and continue. This step is strictly read-only — never open, edit, or comment on a PR.

## Step 5.3 — Append the Provenance / Links section

Append a `## Provenance / Links` section to the committed artifact (the `docs/` file from Phase 4). Use the Read tool to load the file, then append — do not rewrite the body, do not touch the AgDR fence.

When git context exists:

```markdown
## Provenance / Links

- **Commit**: <short SHA at sign-off time>
- **Branch**: <branch name>
- **PR**: <PR url, or "none open at record time">
- **Decision recorded**: <ISO timestamp>
- **Human sign-off**: <approver@ISO from provenance.md>
```

When there is no repo or no implementation yet:

```markdown
## Provenance / Links

- **Status**: implementation pending — no commit or PR linked yet.
- **Decision recorded**: <ISO timestamp>
- **Human sign-off**: <approver@ISO from provenance.md>
```

The sign-off line restates the human signature on the durable artifact itself, so the accountability record lives with the decision, not only in the scratch dir.

## Step 5.4 — Advance status where appropriate

Advance the artifact's status only when the git context warrants it and the vocabulary allows it:

- **RFD** — if the decision is now being implemented on a branch/PR, `discussion → published` (or `committed` once it is fully implemented). Stay within the fixed Oxide six states; never add a state.
- **ADR** / **design doc** — usually already at `accepted`/`reviewed` from the sign-off; advance a design doc to `accepted` if it is the design now being built. Only move status on real signal — do not inflate it because the phase exists.

Edit the status field in the committed artifact (and its frontmatter, for MADR/RFD) if you advance it. If nothing warrants advancing, leave it as recorded — that is the correct outcome.

## Step 5.5 — Recommend the next skill (never auto-invoke)

Recommend, do not run. Pick the recommendation from the artifact type:

- **ADR / design doc** (`accepted`) → the decision is ready to build. Recommend: `Recommended next: /build <the decision> — feed this accepted artifact as the plan.`
- **RFD** still in `discussion` → recommend circulating it for input before it graduates to an ADR or design doc; no build step yet.

State it as a recommendation the user chooses to act on. **Never invoke the next skill yourself** — the human decides when to start the build, and the accepted artifact is the input they hand it, not an automatic trigger.

## Step 5.6 — Final verification block and complete

Emit a visible final block:

```
Governance complete — <task_name>

Artifact:     <docs/...> (<artifact type>, status: <status>)
Sign-off:     <approver@ISO>
Provenance:   embedded (agdr fence + human_signoff)
Git links:    <commit / branch / PR, or "implementation pending">
Recommended:  <the /build … line, or the circulate-RFD line>
```

Then mark `state.md`: `Status: complete`, `Phase: 5`, `phase_complete: true`, `what_remains: []`, stamp `last_verified: <ISO>`, and confirm the `docs/` artifact path is in `FilesWritten`. `what_remains` MUST be `[]` at completion.

## Notes

- Read-only on everything git/GitHub — this phase observes and links, it never pushes, commits, or comments. The user owns those actions.
- The recommendation is the cross-pipeline seam: `govern` produces the accepted artifact; `/build` consumes it. Keeping it a recommendation (not an auto-invoke) preserves the human's control over when implementation starts.
- If the artifact has no implementation yet, "implementation pending" is the honest, complete link state — re-running `govern` is not needed to fill it later; a future `gov-review` or a manual edit can attach the commit/PR when the work lands.
