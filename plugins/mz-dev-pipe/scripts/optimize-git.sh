#!/usr/bin/env bash
# The git steps of /optimize's candidate loop, run from the repository being optimized.
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: optimize-git.sh snapshot <ref> <message>
       optimize-git.sh promote <base-sha> <candidate-sha> <patch-path>
       optimize-git.sh sweep <task_name> [<branch> <worktree> ...]
EOF
  exit 2
}

fail() {
  echo "optimize-git.sh: $*" >&2
  exit 1
}

[ $# -ge 1 ] || usage
cmd=$1
shift
cd "$(git rev-parse --show-toplevel)"

case $cmd in
snapshot)
  [ $# -eq 2 ] || usage
  ref=$1 message=$2
  # A private index, so the user's index, branch and HEAD stay as they are.
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  export GIT_INDEX_FILE=$tmp/index
  # read-tree keeps tracked files that match an ignore rule; add -A then records edits and untracked files.
  git read-tree HEAD
  git add -A -- . ':(exclude).claude/worktrees'
  tree=$(git write-tree)
  unset GIT_INDEX_FILE
  base=$(git -c user.name=mz-optimize -c user.email=mz-optimize@localhost commit-tree "$tree" -p HEAD -m "$message")
  # The ref keeps the commit safe from git gc until the sweep deletes it.
  git update-ref "$ref" "$base"
  echo "BASE_SHA=$base"
  ;;
promote)
  [ $# -eq 3 ] || usage
  base=$1 candidate=$2 patch=$3
  mkdir -p "$(dirname "$patch")"
  git diff --binary "$base" "$candidate" >"$patch"
  git apply --check "$patch" || fail "the patch in $patch no longer applies to the working tree"
  git apply "$patch"
  echo "patch=$patch"
  ;;
sweep)
  # The task name, then branch and worktree pairs.
  [ $(($# % 2)) -eq 1 ] || usage
  task=$1
  shift
  while [ $# -gt 0 ]; do
    branch=$1 worktree=$2
    shift 2
    if git worktree list --porcelain | grep -qxF "worktree $worktree"; then
      git worktree unlock "$worktree" 2>/dev/null || true
      git worktree remove --force "$worktree"
    fi
    git branch -q -D "$branch" 2>/dev/null || true
  done
  git for-each-ref --format='%(refname)' "refs/mz/optimize/$task/" | while read -r ref; do
    git update-ref -d "$ref"
  done
  git worktree prune
  echo "remaining=$(git for-each-ref "refs/mz/optimize/$task/" | wc -l | tr -d ' ')"
  ;;
*)
  usage
  ;;
esac
