#!/usr/bin/env bash
# The $names inside single-quoted jq programs are jq variables, not shell ones.
# shellcheck disable=SC2016
# Every deterministic step on an orchestration DAG (dag.json), so the model never computes it by hand.
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: dag.sh <dag.json> lint [peers.json]
       dag.sh <dag.json> ready
       dag.sh <dag.json> list <status>
       dag.sh <dag.json> fits <unit> <peers.json>
       dag.sh <dag.json> add <unit.json> [peers.json]
       dag.sh <dag.json> mark <unit> <status> [key=value ...]
       dag.sh <dag.json> skip <unit>
       dag.sh <dag.json> requeue <unit>
       dag.sh <dag.json> render
EOF
  exit 2
}

[ $# -ge 2 ] || usage
dag=$1
cmd=$2
shift 2

command -v jq >/dev/null || {
  echo "dag.sh: jq is required" >&2
  exit 1
}
[ -f "$dag" ] || {
  echo "dag.sh: $dag does not exist" >&2
  exit 1
}
jq -e 'type == "object" and (.units | type == "array")' "$dag" >/dev/null 2>&1 || {
  echo "dag.sh: $dag is not a DAG (an object with a units array)" >&2
  exit 1
}

statuses='pending running done merged blocked failed skipped'
mark_keys='base_commit branch head_commit worktree worktree_branch backend_used deadline result note'

# Shared jq definitions. A glob's literal prefix is everything before its first wildcard; two
# globs may overlap when one prefix starts with the other, which errs toward reporting a clash.
lib='
def deps: reduce .units[] as $u ({}; .[$u.id] = ($u.depends_on // []));
def closure($d; $id):
  {front: ($d[$id] // []), seen: []}
  | until(.front | length == 0; .seen += .front | .front = (([.front[] | $d[.][]?] | unique) - .seen))
  | .seen;
def prefix: sub("[*?\\[{].*$"; "");
def overlaps($a; $b): ($a | prefix) as $p | ($b | prefix) as $q | ($p | startswith($q)) or ($q | startswith($p));
def under($g; $role): ($g | prefix) as $p | any($role[]; . as $r | $p | startswith($r | prefix));
def owns_list: if (.owns | type) == "array" then .owns else [] end;
def satisfied: (.status // "pending") as $s | $s == "merged" or ($s == "done" and .kind != "change");
def role_misses($r):
  . as $u
  | (if ($r.kinds // "any") == "any" or ($u.kind | IN($r.kinds[])) then empty
     else "kind \($u.kind) is outside the role" end),
    (if ($r.repos // "any") == "any" or ($u.repo | IN($r.repos[])) then empty
     else "repo \($u.repo) is outside the role" end),
    (if ($r.skills // "any") == "any" or ($u.skill | IN($r.skills[])) then empty
     else "skill \($u.skill) is outside the role" end),
    (if ($r.paths // "any") == "any" then empty
     else ($u | owns_list)[] | select(under(.; $r.paths) | not) | "owns \(.), outside the paths" end);
'

# Writes through a temp file in the same directory so a crash never leaves half a DAG.
update() {
  local tmp
  tmp=$(mktemp "${dag}.XXXXXX")
  jq "$@" "$dag" >"$tmp"
  mv "$tmp" "$dag"
}

require_unit() {
  jq -e --arg id "$1" 'any(.units[]; .id == $id)' "$dag" >/dev/null || {
    echo "dag.sh: no unit '$1' in $dag" >&2
    exit 1
  }
}

lint() {
  local peers=${1:-}
  local peers_json='{"peers":[]}'
  if [ -n "$peers" ]; then
    [ -f "$peers" ] || {
      echo "dag.sh: peer registry $peers does not exist" >&2
      exit 1
    }
    peers_json=$(cat "$peers")
  fi
  local errors
  errors=$(jq -r --argjson reg "$peers_json" "$lib"'
    deps as $d
    | .units as $root_units
    | [.units[].id] as $ids
    | (if (.task // "") == "" then "dag: missing task" else empty end),
      (if ((.project // "") | startswith("/")) then empty else "dag: project must be an absolute path" end),
      ($ids | group_by(.) | map(select(length > 1) | .[0]) | .[] | "\(.): duplicate id"),
      (.units[] | . as $u | .id as $id
        | ((["id", "title", "repo", "skill", "spec"][] | select(($u[.] // "") == "") | "\($id): missing \(.)"),
           (if ($u.kind | IN("change", "review", "context")) then empty else "\($id): kind must be change, review or context" end),
           (if (($u.repo // "") | startswith("/")) or ($u.repo // "") == "" then empty else "\($id): repo must be an absolute path" end),
           (if $u.kind == "change" and ($u | owns_list | length) == 0 then "\($id): a change unit needs owns globs" else empty end),
           (if $u.kind == "change" and ($u.verify // "") == "" then "\($id): a change unit needs a verify command" else empty end),
           (if $u.kind == "context" and ($u | owns_list | length) > 0 then "\($id): a context unit owns nothing" else empty end),
           (if $u.kind == "context" and ([$root_units[] | select(any(.depends_on[]?; . == $id))] | length) == 0
             then "\($id): no unit depends on this context unit, so nobody reads its report" else empty end),
           # A benchmark shares the machine with every unit running beside it.
           (if $u.skill == "mz-dev-pipe:optimize" and $u.exclusive != true
             then "\($id): an optimize unit needs exclusive: true" else empty end),
           (($u.depends_on // [])[] | select(IN($ids[]) | not) | "\($id): depends on unknown unit \(.)"),
           (($u.depends_on // [])[] | select(. == $id) | "\($id): depends on itself"),
           (($u.backend // "auto") as $b
             | if ($b | IN("auto", "subagent", "session", "codex")) or ($b | startswith("peer:")) then empty
               else "\($id): unknown backend \($b)" end),
           (if ($u.backend // "") == "subagent" and $u.repo != $root.project
             then "\($id): a subagent can only work in the project repo" else empty end))),
      ( # Kahn: peel units whose deps are all peeled; whatever is left sits on a cycle.
        def peel($left; $done):
          [$left[] | select(. as $i | all($d[$i][]; . as $x | ($x | IN($done[])) or ($d | has($x) | not)))] as $free
          | if ($free | length) == 0 then $left else peel($left - $free; $done + $free) end;
        peel($ids; []) | select(length > 0) | "cycle through: \(join(", "))"),
      ( [.units[] | select(.kind == "change")] as $c
        | range(0; $c | length) as $i | range($i + 1; $c | length) as $j
        | $c[$i] as $a | $c[$j] as $b
        | select($a.repo == $b.repo)
        | select((any(closure($d; $a.id)[]; . == $b.id) or any(closure($d; $b.id)[]; . == $a.id)) | not)
        | [($a | owns_list)[] as $g | ($b | owns_list)[] as $h | select(overlaps($g; $h)) | "\($g) ~ \($h)"]
        | select(length > 0)
        | "\($a.id), \($b.id): can run in parallel but both own \(join("; ")); add a depends_on or split the paths"),
      ( .units[] | . as $u | select(($u.backend // "") | startswith("peer:"))
        | ($u.backend | ltrimstr("peer:")) as $name
        | ($reg.peers | map(select(.name == $name)) | first) as $p
        | if $p == null then "\($u.id): backend names peer \($name), which is not attached"
          else $u | role_misses($p.role) | "\($u.id): \(.) of \($name)" end)
  ' --argjson root "$(jq '{project}' "$dag")" "$dag")
  if [ -n "$errors" ]; then
    printf 'dag.sh: lint: %s\n' "${errors//$'\n'/$'\n'dag.sh: lint: }" >&2
    exit 1
  fi
  echo "lint: ok ($(jq '.units | length' "$dag") units)"
}

case "$cmd" in
lint)
  [ $# -le 1 ] || usage
  lint "${1:-}"
  ;;
ready)
  [ $# -eq 0 ] || usage
  # An exclusive unit runs alone: once one is ready, the rest wait until it has run.
  jq -r "$lib"'
    (reduce .units[] as $u ({}; .[$u.id] = ($u | satisfied))) as $ok
    | [.units[] | select((.status // "pending") == "running")] as $running
    | [.units[] | select((.status // "pending") == "pending")
       | select(all((.depends_on // [])[]; $ok[.] == true))] as $ready
    | [$ready[] | select(.exclusive == true)] as $excl
    | if any($running[]; .exclusive == true) then empty
      elif ($excl | length) > 0 then (if ($running | length) == 0 then $excl[0].id else empty end)
      else $ready[].id end' "$dag"
  ;;
list)
  [ $# -eq 1 ] || usage
  case " $statuses " in *" $1 "*) ;; *)
    echo "dag.sh: unknown status '$1' (one of: $statuses)" >&2
    exit 2
    ;;
  esac
  jq -r --arg s "$1" '.units[] | select((.status // "pending") == $s) | .id' "$dag"
  ;;
fits)
  # Attached peers whose role covers the unit and that run no unit of this DAG now.
  [ $# -eq 2 ] || usage
  require_unit "$1"
  [ -f "$2" ] || {
    echo "dag.sh: peer registry $2 does not exist" >&2
    exit 1
  }
  jq -r --arg id "$1" --slurpfile reg "$2" "$lib"'
    ([.units[] | select((.status // "pending") == "running") | .backend_used // ""]) as $busy
    | (.units[] | select(.id == $id)) as $u
    | $reg[0].peers[]
    | select(.status == "attached" and ("peer:\(.name)" | IN($busy[]) | not))
    | select(.role as $r | [$u | role_misses($r)] | length == 0)
    | .name' "$dag"
  ;;
add)
  # The DAG with the new unit has to pass lint before it replaces the old one.
  case $# in 1 | 2) ;; *) usage ;; esac
  jq -e 'type == "object"' "$1" >/dev/null 2>&1 || {
    echo "dag.sh: $1 is not a unit (a JSON object)" >&2
    exit 1
  }
  final=$dag
  dag=$(mktemp "${final}.XXXXXX")
  trap 'rm -f "$dag"' EXIT
  jq --slurpfile u "$1" '.units += [$u[0] | .status = "pending" | .attempts = 0]' "$final" >"$dag"
  lint "${2:-}"
  mv "$dag" "$final"
  ;;
mark)
  [ $# -ge 2 ] || usage
  id=$1
  status=$2
  shift 2
  case " $statuses " in *" $status "*) ;; *)
    echo "dag.sh: unknown status '$status' (one of: $statuses)" >&2
    exit 2
    ;;
  esac
  require_unit "$id"
  fields='{}'
  for pair in "$@"; do
    key=${pair%%=*}
    [ "$key" != "$pair" ] || usage
    case " $mark_keys " in *" $key "*) ;; *)
      echo "dag.sh: mark cannot set '$key' (one of: $mark_keys)" >&2
      exit 2
      ;;
    esac
    fields=$(jq -c --arg k "$key" --arg v "${pair#*=}" '.[$k] = $v' <<<"$fields")
  done
  update --arg id "$id" --arg s "$status" --argjson f "$fields" '
    .units |= map(if .id == $id
      then (if $s == "running" and .status != "running" then .attempts = ((.attempts // 0) + 1) else . end) | . + $f | .status = $s
      else . end)'
  ;;
requeue)
  # An attempt cut short by a restart or a lost attachment doesn't count toward the retry limit.
  [ $# -eq 1 ] || usage
  require_unit "$1"
  update --arg id "$1" '.units |= map(if .id == $id
    then .status = "pending" | .attempts = ([(.attempts // 0) - 1, 0] | max) else . end)'
  ;;
skip)
  [ $# -eq 1 ] || usage
  require_unit "$1"
  update --arg id "$1" "$lib"'
    deps as $d
    | ([.units[].id | select(. as $u | any(closure($d; $u)[]; . == $id))] + [$id]) as $drop
    | .units |= map(if .id | IN($drop[]) then .status = "skipped" else . end)'
  jq -r --arg id "$1" '.units[] | select(.status == "skipped") | .id' "$dag"
  ;;
render)
  [ $# -eq 0 ] || usage
  jq -r '
    def node: gsub("[^A-Za-z0-9_]"; "_");
    def cell: tostring | gsub("\\|"; "\\|") | gsub("\n"; " ");
    "| Unit | Title | Kind | Skill | Repo | Backend | Depends on | Status |",
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
    (.units[] | "| \(.id) | \(.title | cell) | \(.kind) | \(.skill) | \(.repo | split("/") | last) | \(.backend // "auto") | \((.depends_on // []) | join(", ") | if . == "" then "-" else . end) | \(.status // "pending") |"),
    "",
    ([.units[] | .status // "pending"] | group_by(.) | map("\(.[0]): \(length)") | join(", ")),
    "",
    "```mermaid",
    "graph TD",
    (.units[] | "  \(.id | node)[\"\(.id): \(.title | gsub("\""; "'"'"'"))\"]"),
    (.units[] | .id as $id | (.depends_on // [])[] | "  \(node) --> \($id | node)"),
    "```"' "$dag"
  ;;
*)
  usage
  ;;
esac
