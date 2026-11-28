#!/usr/bin/env bash
# Runs one unit as a fresh session in its own worktree: a `claude --bg` session that messages its
# result back when the repository is trusted, otherwise a headless `claude -p` run.
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: session.sh bg <repo> <name> <skill|direct> <envelope-file>
       session.sh run <repo> <name> <skill|direct> <envelope-file> <out-json>
       session.sh result <out-json>
       session.sh state <session-id>
       session.sh stop <session-id>
       session.sh progress <worktree> <base-commit>
       session.sh forget <worktree>
EOF
  exit 2
}

fail() {
  echo "session.sh: $*" >&2
  exit 1
}

# Exit 3 tells the orchestrator to fall back from a --bg session to `run`.
fallback() {
  echo "session.sh: $*" >&2
  exit 3
}

check_unit() {
  local repo=$1 name=$2 envelope=$3
  git -C "$repo" rev-parse --git-dir >/dev/null 2>&1 || fail "$repo is not a git repository"
  [ -f "$envelope" ] || fail "no envelope file $envelope"
  [[ $name =~ ^[A-Za-z0-9._-]+$ ]] || fail "worktree name '$name' may hold only letters, digits, '.', '_' and '-'"
  command -v "$claude" >/dev/null || fail "the claude CLI '$claude' is not on PATH"
}

# The harness addresses a session by the socket named after its process id.
address_of() {
  local sock
  sock="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/cc-socks/$1.sock"
  [ -S "$sock" ] || return 1
  echo "uds:$sock"
}

session_field() {
  "$claude" agents --json 2>/dev/null | jq -r --arg k "$1" --arg v "$2" --arg f "$3" \
    'first(.[] | select(.[$k] == $v) | .[$f]) // empty'
}

# Seconds since a file changed; GNU stat takes -c, BSD stat takes -f (and GNU -f means something else).
age_of() {
  local mtime
  mtime=$(stat -c %Y "$1" 2>/dev/null || stat -f %m "$1")
  echo $(($(date +%s) - mtime))
}

# The unit's skill state is the newest state.md with a worker_unit line; the worker's own has none.
unit_state() {
  local file
  while IFS= read -r file; do
    if grep -q '^worker_unit:' "$file"; then
      echo "$file"
      return 0
    fi
  done < <(ls -t "$1"/.mz/task/*/state.md 2>/dev/null)
  return 1
}

# A YAML list under or after the key, flattened to one line.
what_remains_of() {
  local line items=() inside=0
  while IFS= read -r line; do
    if [ $inside -eq 0 ]; then
      [[ $line == what_remains:* ]] || continue
      inside=1
      line=${line#what_remains:}
      line=${line# }
      [ -z "$line" ] || [ "$line" = "[]" ] || items+=("$line")
    elif [[ $line =~ ^[[:space:]]*-[[:space:]]+(.*)$ ]]; then
      items+=("${BASH_REMATCH[1]}")
    else
      break
    fi
  done <"$1"
  [ ${#items[@]} -gt 0 ] || items=(none)
  local joined=${items[0]} item
  for item in "${items[@]:1}"; do joined+="; $item"; done
  echo "$joined"
}

# A wrapper that sets its account's env itself, such as gnai-claude, can stand in for claude.
claude=${MZ_ORCHESTRATE_CLAUDE:-claude}

[ $# -ge 1 ] || usage
cmd=$1
shift

case "$cmd" in
bg)
  [ $# -eq 4 ] || usage
  repo=$1 name=$2 skill=$3 envelope=$4
  check_unit "$repo" "$name" "$envelope"
  self_pid=$(session_field sessionId "${CLAUDE_CODE_SESSION_ID:-}" pid)
  [ -n "$self_pid" ] || fallback "this session isn't listed by claude agents, so a --bg worker couldn't reply"
  reply_to=$(address_of "$self_pid") || fallback "no socket for this session (pid $self_pid)"
  allowed=("Skill(mz-orchestrate:orchestrate-worker)")
  [ "$skill" = direct ] || allowed+=("Skill($skill)")
  read -ra extra <<<"${MZ_ORCHESTRATE_WORKER_ARGS:-}"
  # The worker sends its ORCH-RESULT to reply-to; the field goes right under the envelope's first line.
  prompt=$(sed "1a\\
reply-to: $reply_to" "$envelope")
  # --allowedTools takes every word after it, so the prompt goes after --.
  out=$(cd "$repo" && "$claude" --bg --name "$name" --worktree "$name" --permission-mode auto \
    --permission-prompts none --settings '{"crossSessionInbound":"accept"}' \
    --allowedTools "${allowed[@]}" "${extra[@]}" -- "$prompt" 2>&1) || {
    case $out in *"not trusted"*) fallback "$repo is not a trusted workspace" ;; esac
    fail "claude --bg failed: $out"
  }
  id=$(sed -n 's/^backgrounded · \([^ ]*\) · .*/\1/p' <<<"$out")
  [ -n "$id" ] || fail "claude --bg printed no session id: $out"
  pid=
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    pid=$(session_field id "$id" pid)
    [ -z "$pid" ] || break
    sleep 1
  done
  [ -n "$pid" ] || fail "session $id never appeared in claude agents"
  address=$(address_of "$pid") || fail "no socket for session $id (pid $pid)"
  printf 'id=%s\naddress=%s\nreply_to=%s\nworktree=%s\nworktree_branch=%s\n' \
    "$id" "$address" "$reply_to" "$(cd "$repo" && pwd)/.claude/worktrees/$name" "worktree-$name"
  ;;
state)
  [ $# -eq 1 ] || usage
  status=$(session_field id "$1" status)
  echo "${status:-gone}"
  ;;
stop)
  [ $# -eq 1 ] || usage
  # Stopping a session that already ended fails harmlessly; one still busy is a real failure.
  if ! err=$("$claude" stop "$1" 2>&1) && [ "$(session_field id "$1" status)" = busy ]; then
    fail "could not stop session $1: $err"
  fi
  echo "stopped $1"
  ;;
run)
  [ $# -eq 5 ] || usage
  repo=$1 name=$2 skill=$3 envelope=$4 out=$5
  check_unit "$repo" "$name" "$envelope"
  # Nobody answers a prompt in -p, so the skills the unit runs are approved up front.
  allowed=("Skill(mz-orchestrate:orchestrate-worker)")
  [ "$skill" = direct ] || allowed+=("Skill($skill)")
  # Extra CLI arguments for development runs, such as --plugin-dir for unpublished plugins.
  read -ra extra <<<"${MZ_ORCHESTRATE_WORKER_ARGS:-}"
  status=0
  (cd "$repo" &&
    CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=${CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS:-3600000} \
      "$claude" -p -w "$name" --output-format json --permission-mode auto --permission-prompts none \
      --allowedTools "${allowed[@]}" "${extra[@]}" <"$envelope" >"$out") || status=$?
  printf 'worktree=%s\nworktree_branch=%s\nexit=%s\n' \
    "$(cd "$repo" && pwd)/.claude/worktrees/$name" "worktree-$name" "$status"
  ;;
result)
  [ $# -eq 1 ] || usage
  [ -s "$1" ] || fail "no session output in $1"
  jq -e 'type == "object"' "$1" >/dev/null 2>&1 || fail "$1 is not the JSON a -p session prints"
  if ! jq -e '(.is_error | not) and (.result | type == "string")' "$1" >/dev/null; then
    fail "the session ended without a result: $(jq -r '"\(.subtype // "unknown"): \(.result // .error // "no text")"' "$1")"
  fi
  jq -r '.result' "$1"
  ;;
progress)
  [ $# -eq 2 ] || usage
  worktree=$1 base=$2
  [ -d "$worktree" ] || fail "no worktree at $worktree"
  if state=$(unit_state "$worktree"); then
    phase=$(sed -n '/^Phase: */{s///p;q}' "$state")
    phase_name=$(sed -n '/^PhaseName: */{s///p;q}' "$state")
    echo "state: $state"
    echo "phase: ${phase:-unknown}${phase_name:+ $phase_name}"
    echo "what_remains: $(what_remains_of "$state")"
    echo "state_age: $(age_of "$state")"
  else
    echo "state: none"
  fi
  echo "changed: $(git -C "$worktree" status --porcelain | wc -l | tr -d ' ')"
  head=$(git -C "$worktree" rev-parse HEAD) || fail "$worktree is not a git worktree"
  if [ "$head" = "$(git -C "$worktree" rev-parse "$base^{commit}")" ]; then
    echo "last_commit: none"
  else
    echo "last_commit: $(git -C "$worktree" log -1 --format='%h %s')"
  fi
  ;;
forget)
  [ $# -eq 1 ] || usage
  worktree=${1%/}
  # purge deletes every transcript of the path it gets, so only a worker's own worktree may be named.
  [[ ${worktree%/*} == */.claude/worktrees && ${worktree##*/} =~ ^orch-[A-Za-z0-9._-]+$ ]] ||
    fail "'$1' is not a worker worktree (<repo>/.claude/worktrees/orch-...)"
  # Each worktree is a project of its own to Claude Code, so its transcript would stay in /resume.
  if out=$("$claude" purge -y "$worktree" </dev/null 2>&1); then
    echo "forgot $worktree"
  elif [[ $out == *"No Claude Code project data found"* ]]; then
    echo "nothing to forget for $worktree"
  else
    fail "could not purge the sessions of $worktree: $out"
  fi
  ;;
*)
  usage
  ;;
esac
