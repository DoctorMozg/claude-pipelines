#!/usr/bin/env bash
# The git side of an orchestration run: the integration worktree, unit merges, the scope check, checkpoint probes and cleanup.
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: integrate.sh init <repo> <task> <worktree>
       integrate.sh merge <worktree> <unit-branch> <message>
       integrate.sh conclude <worktree>
       integrate.sh land <checkout> <start-branch> <integration-branch>
       integrate.sh abort <worktree>
       integrate.sh scope <repo> <base> <unit-branch> <glob> [<glob> ...]
       integrate.sh cleanup <repo> <unit-worktree|none> <unit-branch> <integration-branch>
       integrate.sh merges <worktree> <since-commit>
       integrate.sh probe <repo> <path> <commit>
       integrate.sh unprobe <repo> <path>
EOF
  exit 2
}

[ $# -ge 1 ] || usage
cmd=$1
shift

fail() {
  echo "integrate.sh: $*" >&2
  exit 1
}

require_repo() {
  git -C "$1" rev-parse --git-dir >/dev/null 2>&1 || fail "$1 is not a git repository"
}

merging() {
  git -C "$1" rev-parse -q --verify MERGE_HEAD >/dev/null
}

# Prints "<checkout> <branch-or-commit>" for the checkout a Claude session worktree was made from.
# A --bg session isolates into <checkout>/.claude/worktrees/<name>, locked "claude session ...";
# any other worktree prints nothing. Reads only this worktree's view, never git -C <checkout>.
session_origin() {
  local top origin path="" head="" ref="" lock="" is_session=no start=""
  top=$(git -C "$1" rev-parse --show-toplevel)
  case $top in */.claude/worktrees/*) ;; *) return 0 ;; esac
  origin=${top%/.claude/worktrees/*}
  while IFS= read -r line || [ -n "$path" ]; do
    case $line in
    "worktree "*) path=${line#worktree } ;;
    "HEAD "*) head=${line#HEAD } ;;
    "branch refs/heads/"*) ref=${line#branch refs/heads/} ;;
    "locked "*) lock=${line#locked } ;;
    "")
      if [ "$path" = "$top" ] && [[ $lock == "claude session "* ]]; then is_session=yes; fi
      if [ "$path" = "$origin" ]; then start=${ref:-$head}; fi
      path="" head="" ref="" lock=""
      ;;
    esac
  done < <(git -C "$1" worktree list --porcelain)
  if [ "$is_session" = yes ] && [ -n "$start" ]; then
    printf '%s %s\n' "$origin" "$start"
  fi
}

case "$cmd" in
init)
  [ $# -eq 3 ] || usage
  repo=$1 task=$2 worktree=$3
  require_repo "$repo"
  branch="orchestrate/$task"
  origin=$(session_origin "$repo")
  if [ -n "$origin" ]; then
    # A --bg session may not look into the checkout it left, so its edits there are unknown.
    checkout=${origin% *} start=${origin##* } dirty=unknown
  else
    checkout=$(git -C "$repo" rev-parse --show-toplevel)
    start=$(git -C "$repo" symbolic-ref -q --short HEAD || git -C "$repo" rev-parse HEAD)
    # The integration branch starts from committed work only; uncommitted edits stay in the user's checkout.
    dirty=no
    [ -z "$(git -C "$repo" status --porcelain --untracked-files=no)" ] || dirty=yes
  fi
  if [ -d "$worktree" ]; then
    [ "$(git -C "$worktree" symbolic-ref -q --short HEAD)" = "$branch" ] ||
      fail "$worktree exists but is not on $branch"
  elif git -C "$repo" show-ref -q --verify "refs/heads/$branch"; then
    git -C "$repo" worktree add -q "$worktree" "$branch"
  else
    git -C "$repo" worktree add -q -b "$branch" "$worktree" "$start"
  fi
  printf 'start_branch=%s\nstart_checkout=%s\nintegration_branch=%s\nworktree=%s\ntip=%s\ndirty=%s\n' \
    "$start" "$checkout" "$branch" "$(cd "$worktree" && pwd)" "$(git -C "$worktree" rev-parse HEAD)" "$dirty"
  ;;
merge)
  [ $# -eq 3 ] || usage
  worktree=$1 branch=$2 message=$3
  require_repo "$worktree"
  merging "$worktree" && fail "a merge is already in progress in $worktree; conclude or abort it first"
  git -C "$worktree" rev-parse -q --verify "$branch^{commit}" >/dev/null || fail "no branch $branch"
  if git -C "$worktree" merge-base --is-ancestor "$branch" HEAD; then
    printf 'state=up-to-date\ntip=%s\n' "$(git -C "$worktree" rev-parse HEAD)"
    exit 0
  fi
  # The merge is staged, not committed, so verify runs on the merged tree before conclude commits it.
  if out=$(git -C "$worktree" merge -q --no-ff --no-commit "$branch" 2>&1); then
    git -C "$worktree" rev-parse -q --verify MERGE_HEAD >/dev/null || fail "merge of $branch left no merge state"
    printf '%s\n' "$message" >"$(git -C "$worktree" rev-parse --path-format=absolute --git-path MERGE_MSG)"
    echo "state=staged"
    exit 0
  fi
  conflicted=$(git -C "$worktree" diff --name-only --diff-filter=U)
  if [ -z "$conflicted" ]; then
    merging "$worktree" && git -C "$worktree" merge --abort
    fail "merge of $branch failed without conflicts: $out"
  fi
  printf '%s\n' "$message" >"$(git -C "$worktree" rev-parse --path-format=absolute --git-path MERGE_MSG)"
  # Exit 3 leaves the merge in progress for the resolver.
  while IFS= read -r file; do echo "conflicted=$file"; done <<<"$conflicted"
  exit 3
  ;;
conclude)
  [ $# -eq 1 ] || usage
  worktree=$1
  merging "$worktree" || fail "no merge in progress in $worktree"
  unmerged=$(git -C "$worktree" diff --name-only --diff-filter=U)
  [ -z "$unmerged" ] || fail "still unmerged: $(echo "$unmerged" | tr '\n' ' ')"
  if markers=$(git -C "$worktree" diff --cached --name-only -G '^(<<<<<<<|>>>>>>>) ' HEAD) && [ -n "$markers" ]; then
    fail "conflict markers left in: $(echo "$markers" | tr '\n' ' ')"
  fi
  git -C "$worktree" commit -q --no-edit
  echo "tip=$(git -C "$worktree" rev-parse HEAD)"
  ;;
land)
  [ $# -eq 3 ] || usage
  checkout=$1 start=$2 branch=$3
  require_repo "$checkout"
  top=$(git -C "$checkout" rev-parse --show-toplevel)
  # Running this script must not get a --bg session past the guard that keeps it out of the user's checkout.
  if git rev-parse --git-dir >/dev/null 2>&1; then
    origin=$(session_origin .)
    [ "${origin% *}" != "$top" ] ||
      fail "this session is isolated from $top; the user runs: git -C $top merge --ff-only $branch"
  fi
  current=$(git -C "$checkout" symbolic-ref -q --short HEAD || echo detached)
  [ "$current" = "$start" ] || fail "$top is on $current, not $start"
  git -C "$checkout" merge-base --is-ancestor "$start" "$branch" ||
    fail "$start has commits $branch lacks; merge $start into $branch first"
  git -C "$checkout" merge -q --ff-only "$branch" || fail "fast-forward of $start in $top failed"
  echo "tip=$(git -C "$checkout" rev-parse HEAD)"
  ;;
abort)
  [ $# -eq 1 ] || usage
  merging "$1" || fail "no merge in progress in $1"
  git -C "$1" merge --abort
  echo "aborted"
  ;;
scope)
  [ $# -ge 4 ] || usage
  repo=$1 base=$2 branch=$3
  shift 3
  require_repo "$repo"
  # Prints the files the unit changed outside its owns globs; * matches across directories here.
  git -C "$repo" diff --name-only "$base" "$branch" | while IFS= read -r file; do
    inside=no
    for glob in "$@"; do
      # shellcheck disable=SC2053
      if [[ $file == $glob ]]; then
        inside=yes
        break
      fi
    done
    [ "$inside" = yes ] || echo "$file"
  done
  ;;
cleanup)
  [ $# -eq 4 ] || usage
  repo=$1 worktree=$2 branch=$3 into=$4
  require_repo "$repo"
  # Only merged work is thrown away; a failed or skipped unit keeps its branch for the user.
  if git -C "$repo" show-ref -q --verify "refs/heads/$branch" &&
    ! git -C "$repo" merge-base --is-ancestor "$branch" "$into"; then
    fail "$branch is not merged into $into; keeping it"
  fi
  if [ "$worktree" != none ] && [ -d "$worktree" ]; then
    # A worktree made by claude -p -w or claude --bg --worktree is left locked.
    git -C "$repo" worktree unlock "$worktree" 2>/dev/null || true
    git -C "$repo" worktree remove --force "$worktree"
  fi
  git -C "$repo" worktree prune
  if git -C "$repo" show-ref -q --verify "refs/heads/$branch"; then
    git -C "$repo" branch -q -D "$branch"
  fi
  echo "removed $branch"
  ;;
merges)
  [ $# -eq 2 ] || usage
  require_repo "$1"
  # One line per merge on the integration branch, oldest first: the steps a checkpoint bisects.
  git -C "$1" log --first-parent --reverse --format='%H %s' "$2..HEAD"
  ;;
probe)
  [ $# -eq 3 ] || usage
  repo=$1 path=$2 commit=$3
  require_repo "$repo"
  sha=$(git -C "$repo" rev-parse -q --verify "$commit^{commit}") || fail "no commit $commit"
  # A detached worktree, so the suite runs on a fixed commit while merges go on in the integration worktree.
  if [ -d "$path" ] && git -C "$path" rev-parse --git-dir >/dev/null 2>&1; then
    git -C "$path" checkout -q --force --detach "$sha"
  else
    git -C "$repo" worktree add -q --detach "$path" "$sha"
  fi
  printf 'probe=%s\ncommit=%s\n' "$(cd "$path" && pwd)" "$sha"
  ;;
unprobe)
  [ $# -eq 2 ] || usage
  require_repo "$1"
  [ ! -d "$2" ] || git -C "$1" worktree remove --force "$2"
  git -C "$1" worktree prune
  echo "removed $2"
  ;;
*)
  usage
  ;;
esac
