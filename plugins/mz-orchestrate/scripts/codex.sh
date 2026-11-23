#!/usr/bin/env bash
# Runs one unit on Codex: builds the unit's worktree and brief, runs its skill with `codex exec`,
# then runs verify, commits the owned paths and prints the ORCH-RESULT itself.
set -euo pipefail

usage() {
  echo "usage: codex.sh <repo> <name> <envelope-file> <out-dir>" >&2
  exit 2
}

fail() {
  echo "codex.sh: $*" >&2
  exit 1
}

[ $# -eq 4 ] || usage
repo=$1 name=$2 envelope=$3 out=$4
git -C "$repo" rev-parse --git-dir >/dev/null 2>&1 || fail "$repo is not a git repository"
[ -f "$envelope" ] || fail "no envelope file $envelope"
[[ $name =~ ^[A-Za-z0-9._-]+$ ]] || fail "worktree name '$name' may hold only letters, digits, '.', '_' and '-'"
command -v codex >/dev/null || fail "the codex CLI is not on PATH"

field() { sed -n "/^$1: /{s///p;q;}" "$envelope"; }
task=$(field task) unit=$(field unit) title=$(field title) kind=$(field kind) skill=$(field skill)
base=$(field base-commit) branch=$(field branch) owns=$(field owns) verify=$(field verify)
spec=$(sed -n '/^--- spec ---$/,/^END ORCH-UNIT$/{/^--- spec ---$/d;/^END ORCH-UNIT$/d;p;}' "$envelope")
for key in task unit kind skill base branch; do
  [ -n "${!key}" ] || fail "the envelope in $envelope has no ${key/base/base-commit} line"
done

repo=$(cd "$repo" && git rev-parse --show-toplevel)
wt=$repo/.claude/worktrees/$name
mkdir -p "$out"

report_path=none report_text=none

# status verify head-commit files notes; the worktree is reported only once it exists.
result() {
  local where=none
  [ -d "$wt" ] && where=$wt
  {
    printf 'ORCH-RESULT v1 (handle with mz-orchestrate:orchestrate)\n'
    printf 'task: %s\nunit: %s\nstatus: %s\nrepo: %s\nworktree: %s\nbranch: %s\n' \
      "$task" "$unit" "$1" "$repo" "$where" "$branch"
    printf 'head-commit: %s\nverify: %s\nfiles: %s\nreport: %s\n' "$3" "$2" "$4" "$report_path"
    printf -- '--- notes ---\n%s\n--- report ---\n%s\nEND ORCH-RESULT\n' "${5:-none}" "$report_text"
  } | tee "$out/result.txt"
  exit 0
}

if [ "$skill" != direct ]; then
  plugin=${skill%%:*}
  codex plugin list 2>/dev/null | grep -Eq "^${plugin}@[^ ]+ +installed, enabled" ||
    result REFUSED not-run none "" "skill not installed: $plugin is not installed and enabled in Codex"
fi

if ! git -C "$repo" worktree add -q --detach "$wt" "$base" >"$out/git.log" 2>&1 ||
  ! git -C "$wt" checkout -q -B "$branch" >>"$out/git.log" 2>&1; then
  result FAILED not-run none "" "worktree: $(cat "$out/git.log")"
fi

mkdir -p "$wt/.mz/orchestrate"
printf '# Unit %s: %s\n\n- task: %s\n- kind: %s\n- skill: %s\n- owns: %s\n- verify: %s\n\n## Spec\n\n%s\n' \
  "$unit" "$title" "$task" "$kind" "$skill" "$owns" "$verify" "$spec" >"$wt/.mz/orchestrate/unit.md"

if [ "$skill" = direct ]; then
  prompt="Carry out the unit in .mz/orchestrate/unit.md yourself. Edit only files matching its owns globs, run its verify command, and don't commit, ask questions or create worktrees. End with a short summary of what changed, any concern under ## Concerns or blocker under ## Blocker, and, as the very last line, STATUS: DONE, STATUS: DONE_WITH_CONCERNS or STATUS: BLOCKED."
else
  prompt="Use the $skill skill with the argument unit:.mz/orchestrate/unit.md. Worker mode decides every gate, so never ask a question. Edit only files matching the unit's owns globs and don't commit. End with the skill's final message, whose very last line is its STATUS line."
fi

# Extra CLI arguments, such as -m <model>, from the environment.
read -ra extra <<<"${MZ_ORCHESTRATE_CODEX_ARGS:-}"
# --ephemeral is left out on purpose: Codex subagents load their context from the session file.
code=0
codex exec -C "$wt" -s workspace-write --json -o "$out/last.txt" "${extra[@]}" "$prompt" \
  </dev/null >"$out/events.jsonl" 2>"$out/stderr.log" || code=$?

final=$(cat "$out/last.txt" 2>/dev/null || true)
status=$(grep -o '^STATUS: [A-Z_]*' <<<"$final" | tail -n 1 | cut -d' ' -f2 || true)
notes=$(grep -v '^STATUS: ' <<<"$final" || true)
case $status in
DONE | DONE_WITH_CONCERNS | BLOCKED) ;;
*) result FAILED not-run none "" "codex exited $code without a STATUS line: $(tail -n 5 "$out/stderr.log")" ;;
esac

if [ "$kind" != change ]; then
  # A review or context skill names its report under `## Report`; the text goes back whole,
  # because a context unit's dependents read it after this worktree is gone.
  path=$(sed -n '/^## Report$/,${/^## Report$/d;/^[[:space:]]*$/d;p;q;}' <<<"$final" | tr -d '`')
  [ -z "$path" ] || [[ $path == /* ]] || path=$wt/$path
  if [ -n "$path" ] && [ -f "$path" ]; then
    report_path=$path
    report_text=$(cat "$path")
  fi
  result "$status" not-run none "" "$notes"
fi

verified=not-run
if [ -n "$verify" ]; then
  verified=fail
  (cd "$wt" && bash -c "$verify") >"$out/verify.log" 2>&1 && verified=pass
fi

IFS=, read -ra globs <<<"$owns"
for glob in "${globs[@]}"; do
  glob=${glob#"${glob%%[![:space:]]*}"}
  glob=${glob%"${glob##*[![:space:]]}"}
  # A glob with no file behind it is normal for a unit that left it alone, and git add rejects it.
  git -C "$wt" add -A -- ":(glob)$glob" 2>/dev/null || true
done
if git -C "$wt" diff --cached --quiet; then
  [ "$status" = DONE ] && status=DONE_WITH_CONCERNS
  notes=$(printf 'no changes\n%s' "$notes")
elif ! git -C "$wt" commit -q -m "orch $unit: $title" >"$out/commit.log" 2>&1; then
  result FAILED "$verified" none "" "commit: $(cat "$out/commit.log")"
fi

result "$status" "$verified" "$(git -C "$wt" rev-parse HEAD)" \
  "$(git -C "$wt" diff --name-only "$base"..HEAD | paste -sd, -)" "$notes"
