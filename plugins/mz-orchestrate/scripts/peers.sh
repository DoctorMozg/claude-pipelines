#!/usr/bin/env bash
# The $names inside single-quoted jq programs are jq variables, not shell ones.
# shellcheck disable=SC2016
# Owns every write to the orchestrator's peer registry (.mz/orchestrate/peers.json).
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: peers.sh <registry> init <self-name> <self-ref>
       peers.sh <registry> add <name> <ref> <role-json>
       peers.sh <registry> role <name> <role-json>
       peers.sh <registry> hello <name> <address> <hello-json>
       peers.sh <registry> status <name> <pending|attached|refused|detaching|detached>
       peers.sh <registry> unit <name> <task>/<unit>|none
       peers.sh <registry> remove <name>
       peers.sh <registry> list
EOF
  exit 2
}

[ $# -ge 2 ] || usage
registry=$1
cmd=$2
shift 2

command -v jq >/dev/null || {
  echo "peers.sh: jq is required" >&2
  exit 1
}

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

require_json() {
  printf '%s' "$1" | jq -e 'type == "object"' >/dev/null 2>&1 || {
    echo "peers.sh: $2 must be a JSON object, got: $1" >&2
    exit 2
  }
}

require_peer() {
  jq -e --arg n "$1" '.peers | any(.name == $n)' "$registry" >/dev/null || {
    echo "peers.sh: no peer named '$1' in $registry" >&2
    exit 1
  }
}

# Writes through a temp file in the same directory so a crash never leaves half a registry.
update() {
  local tmp
  tmp=$(mktemp "${registry}.XXXXXX")
  jq "$@" "$registry" >"$tmp"
  mv "$tmp" "$registry"
}

if [ "$cmd" != init ] && [ ! -f "$registry" ]; then
  echo "peers.sh: $registry does not exist; run init first" >&2
  exit 1
fi

case "$cmd" in
init)
  [ $# -eq 2 ] || usage
  mkdir -p "$(dirname "$registry")"
  [ -f "$registry" ] || printf '{"orchestrator":{},"peers":[]}\n' >"$registry"
  update --arg n "$1" --arg r "$2" --arg t "$(now)" '.orchestrator = {name: $n, ref: $r, since: $t}'
  ;;
add)
  [ $# -eq 3 ] || usage
  require_json "$3" role-json
  update --arg n "$1" --arg r "$2" --argjson role "$3" --arg t "$(now)" '
    .peers |= (map(select(.name != $n)) + [{name: $n, ref: $r, address: null, status: "pending",
      role: $role, hello: null, current_unit: null, updated: $t}])'
  ;;
role)
  [ $# -eq 2 ] || usage
  require_json "$2" role-json
  require_peer "$1"
  update --arg n "$1" --argjson role "$2" --arg t "$(now)" '
    .peers |= map(if .name == $n then .role = $role | .updated = $t else . end)'
  ;;
hello)
  [ $# -eq 3 ] || usage
  require_json "$3" hello-json
  require_peer "$1"
  update --arg n "$1" --arg a "$2" --argjson h "$3" --arg t "$(now)" '
    .peers |= map(if .name == $n then .address = $a | .hello = $h | .status = "attached" | .updated = $t else . end)'
  ;;
status)
  [ $# -eq 2 ] || usage
  case "$2" in pending | attached | refused | detaching | detached) ;; *) usage ;; esac
  require_peer "$1"
  update --arg n "$1" --arg s "$2" --arg t "$(now)" '
    .peers |= map(if .name == $n then .status = $s | .updated = $t else . end)'
  ;;
unit)
  [ $# -eq 2 ] || usage
  require_peer "$1"
  update --arg n "$1" --arg u "$2" --arg t "$(now)" '
    .peers |= map(if .name == $n then .current_unit = (if $u == "none" then null else $u end) | .updated = $t else . end)'
  ;;
remove)
  [ $# -eq 1 ] || usage
  require_peer "$1"
  update --arg n "$1" '.peers |= map(select(.name != $n))'
  ;;
list)
  [ $# -eq 0 ] || usage
  jq -r '.peers[] | [.name, .ref, .status, (.role.note // ""), (.current_unit // "-")] | @tsv' "$registry"
  ;;
*)
  usage
  ;;
esac
