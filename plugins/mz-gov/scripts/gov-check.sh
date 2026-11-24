#!/usr/bin/env bash
# Mechanical facts about governance records for /gov-review: type, status, provenance fence,
# sections, options, supersede links and numbering. Judgment axes stay with the reviewer.
set -euo pipefail

usage() {
  echo "usage: gov-check.sh <record.md>..." >&2
  exit 2
}
[ $# -ge 1 ] || usage

# One pass over a record: front matter, fence fields, the Status section, headings,
# options under the type's options heading, supersede references and relative .md links.
EXTRACT=$(
  cat <<'AWK'
function trim(s) { sub(/^[ \t"']+/, "", s); sub(/[ \t"']+$/, "", s); return s }
function ref(kind, text,   n) {
  if (match(text, /[0-9]+/)) { n = substr(text, RSTART, RLENGTH) + 0; print "ref\t" kind "\t" n }
}
NR == 1 && /^---[ \t]*$/ { fm = 1; next }
fm && /^---[ \t]*$/ { fm = 0; next }
fm {
  if (match($0, /^status:/)) print "fm_status\t" trim(substr($0, RLENGTH + 1))
  if (match($0, /^state:/)) print "fm_state\t" trim(substr($0, RLENGTH + 1))
}
/<!-- mz-gov:agdr start -->/ { fence = 1; print "fence_start"; next }
/<!-- mz-gov:agdr end -->/ { fence = 0; print "fence_end"; next }
fence && match($0, /^[a-z_]+:/) { print "field\t" substr($0, 1, RLENGTH - 1) "\t" trim(substr($0, RLENGTH + 1)); next }
/^## / {
  h = tolower(trim(substr($0, 4)))
  sub(/[ \t]*<!--.*$/, "", h)
  print "heading\t" h
  in_status = (h == "status")
  in_opts = (want != "" && index(h, want) == 1)
  next
}
/^# / { in_status = 0; in_opts = 0 }
in_status && !status_done && $0 !~ /^[ \t]*$/ { print "status_section\t" trim($0); status_done = 1 }
in_opts && /^### / { sub_opts++ }
in_opts && /^[-*] / { list_opts++ }
{
  line = tolower($0)
  while (match(line, /superseded by (adr|rfd|design doc)?[- ]?[0-9]+/)) {
    ref("superseded_by", substr(line, RSTART, RLENGTH)); line = substr(line, RSTART + RLENGTH)
  }
  line = tolower($0)
  while (match(line, /supersedes:? (adr|rfd|design doc)?[- ]?[0-9]+/)) {
    ref("supersedes", substr(line, RSTART, RLENGTH)); line = substr(line, RSTART + RLENGTH)
  }
  line = $0
  while (match(line, /\]\([^)#: ]+\.md[)#]/)) {
    print "link\t" substr(line, RSTART + 2, RLENGTH - 3); line = substr(line, RSTART + RLENGTH)
  }
}
END { print "options\t" (sub_opts > 0 ? sub_opts : list_opts + 0) }
AWK
)

record_type() {
  case "$(basename "$(dirname "$1")")" in
  decisions) grep -qi '^## considered options' "$1" && echo adr-madr || echo adr-nygard ;;
  rfcs) echo rfd ;;
  design) echo design ;;
  *)
    if grep -q '^state:' "$1"; then
      echo rfd
    elif grep -qi '^## considered options' "$1"; then
      echo adr-madr
    elif grep -qi '^## goals and non-goals' "$1"; then
      echo design
    elif grep -qi '^## decision' "$1"; then
      echo adr-nygard
    else
      echo unknown
    fi
    ;;
  esac
}

options_heading() {
  case $1 in
  adr-madr) echo "considered options" ;;
  rfd) echo "proposal" ;;
  design) echo "alternatives considered" ;;
  *) echo "" ;;
  esac
}

required_sections() {
  case $1 in
  adr-nygard) printf '%s\n' "status" "context" "decision" "consequences" ;;
  adr-madr) printf '%s\n' "context and problem statement" "considered options" "decision outcome" ;;
  rfd) printf '%s\n' "summary" "problem statement" "proposal" "open questions" ;;
  design) printf '%s\n' "context and scope" "goals and non-goals" "the actual design" "alternatives considered" "cross-cutting concerns" ;;
  esac
}

facts_of() {
  awk -v want="$(options_heading "$(record_type "$1")")" "$EXTRACT" "$1"
}

value_of() {
  awk -F '\t' -v k="$1" '$1 == k { print $2; exit }'
}

# The status a record declares: RFD front matter `state`, then MADR front matter, then the Status section, then the fence.
# Only the leading phrase counts, so "Accepted. Supersedes ADR-0001." reads as accepted.
status_from() {
  local facts=$1 type=$2 s=""
  [ "$type" = rfd ] && s=$(value_of fm_state <<<"$facts")
  [ -n "$s" ] || s=$(value_of fm_status <<<"$facts")
  [ -n "$s" ] || s=$(value_of status_section <<<"$facts")
  [ -n "$s" ] || s=$(awk -F '\t' '$1 == "field" && $2 == "status" { print $3; exit }' <<<"$facts")
  printf '%s' "$s" | tr '[:upper:]' '[:lower:]' | sed -E 's/[.;,(].*$//; s/[[:space:]]+[-—–][[:space:]].*$//; s/[[:space:]]+$//'
}

# default | custom | invalid | missing, against status-vocabularies.md.
status_class() {
  local type=$1 s=$2
  [ -n "$s" ] || { echo missing; return; }
  case $type in
  rfd)
    case $s in prediscussion | ideation | discussion | published | committed | abandoned) echo default ;; *) echo invalid ;; esac
    ;;
  adr-*)
    case $s in proposed | accepted | rejected | deprecated | "superseded by "*) echo default ;; *) echo custom ;; esac
    ;;
  design)
    case $s in draft | reviewed | accepted | "superseded"*) echo default ;; *) echo custom ;; esac
    ;;
  *) echo custom ;;
  esac
}

decided() {
  case "$1:$2" in
  adr-*:accepted | adr-*:rejected | adr-*:deprecated | adr-*:superseded* | rfd:published | rfd:committed | design:accepted | design:superseded*) return 0 ;;
  *) return 1 ;;
  esac
}

number_of() {
  local base
  base=$(basename "$1")
  [[ $base =~ ^([0-9]{4})- ]] && echo "${BASH_REMATCH[1]}" || echo "-"
}

# File names in dir that start with the given four-digit pattern.
numbered_in() {
  local f
  # $2 is itself a glob such as [0-9][0-9][0-9][0-9], so it stays unquoted.
  # shellcheck disable=SC2231
  for f in "$1"/$2-*.md; do
    [ -e "$f" ] && basename "$f"
  done
  return 0
}

# The first record numbered n in dir.
record_numbered() {
  local dir=$1 n
  n=$(printf '%04d' "$2")
  local first
  first=$(numbered_in "$dir" "$n" | head -1 || true)
  [ -z "$first" ] || echo "$dir/$first"
}

REQUIRED_FIELDS="agdr_id timestamp agent model trigger status human_signoff"
repo_findings=()
dirs=""

for rec in "$@"; do
  [ -f "$rec" ] || {
    echo "gov-check.sh: no such file: $rec" >&2
    exit 1
  }
  dir=$(dirname "$rec")
  dirs+="$dir"$'\n'
  type=$(record_type "$rec")
  facts=$(facts_of "$rec")
  status=$(status_from "$facts" "$type")
  class=$(status_class "$type" "$status")
  findings=()

  if grep -q '^fence_start' <<<"$facts" && grep -q '^fence_end' <<<"$facts"; then
    fence=present
    missing_fields=""
    for f in $REQUIRED_FIELDS; do
      awk -F '\t' -v f="$f" '$1 == "field" && $2 == f { found = 1 } END { exit !found }' <<<"$facts" || missing_fields+="$f "
    done
    signoff=$(awk -F '\t' '$1 == "field" && $2 == "human_signoff" { print $3; exit }' <<<"$facts")
    model=$(awk -F '\t' '$1 == "field" && $2 == "model" { print $3; exit }' <<<"$facts")
  else
    fence=missing missing_fields="" signoff="" model=""
  fi

  # The fence's own lifecycle (proposed, accepted, executed, superseded) also says when a decision was made.
  fence_status=$(awk -F '\t' '$1 == "field" && $2 == "status" { print tolower($3); exit }' <<<"$facts")
  case $fence_status in accepted | executed | superseded*) fence_decided=yes ;; *) fence_decided=no ;; esac
  if decided "$type" "$status" || [ $fence_decided = yes ]; then is_decided=yes; else is_decided=no; fi
  case $signoff in
  "") signoff_state=absent ;;
  pending) signoff_state=pending ;;
  *@[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T*) signoff_state=signed ;;
  *) signoff_state=malformed ;;
  esac

  case $class in
  missing) findings+=("Critical: no status found (front matter, provenance fence or Status section).") ;;
  invalid) findings+=("Critical: status \`$status\` is not an RFD state (prediscussion, ideation, discussion, published, committed, abandoned).") ;;
  custom) findings+=("FYI: status \`$status\` is outside the default set; valid only if the project declares it.") ;;
  esac
  if [ "$type" != rfd ] && [ "$status" = superseded ]; then
    findings+=("Nit: status \`superseded\` names no replacement; write \`superseded by <id>\`.")
  fi
  if [ $fence = missing ]; then
    if [ $is_decided = yes ]; then
      findings+=("Critical: no AI-provenance fence on a record whose status \`$status\` presents it as decided.")
    else
      findings+=("Nit: no AI-provenance fence yet; it needs one with a sign-off before it is decided.")
    fi
  else
    [ -z "$missing_fields" ] || findings+=("Nit: provenance fence lacks: ${missing_fields% }.")
    case $signoff_state in
    pending | absent)
      if [ $is_decided = yes ]; then
        findings+=("Critical: human_signoff is ${signoff_state} on a record presented as decided (status \`$status\`${fence_status:+, fence status \`$fence_status\`}).")
      else
        findings+=("FYI: human_signoff is ${signoff_state}, expected while the status is \`${status:-unset}\`.")
      fi
      ;;
    malformed) findings+=("Nit: human_signoff \`$signoff\` is not \`<approver>@<ISO-8601>\`.") ;;
    esac
    case $model in
    opus | sonnet | haiku | fable | claude | gpt*) findings+=("Nit: model \`$model\` is a family name, not an exact model id.") ;;
    esac
  fi

  missing_sections=""
  while read -r section; do
    [ -n "$section" ] || continue
    awk -F '\t' -v s="$section" '$1 == "heading" && index($2, s) == 1 { found = 1 } END { exit !found }' <<<"$facts" ||
      missing_sections+="${section}; "
  done < <(required_sections "$type")

  links=""
  while IFS=$'\t' read -r kind rel n; do
    case $kind in
    ref)
      target=$(record_numbered "$dir" "$n")
      label="$rel $(printf '%04d' "$n")"
      if [ -z "$target" ]; then
        findings+=("Critical: \`$label\` points to a record that doesn't exist in $dir.")
        links+="$label (missing); "
        continue
      fi
      links+="$label (ok); "
      if [ "$rel" = supersedes ]; then
        t_type=$(record_type "$target")
        t_status=$(status_from "$(facts_of "$target")" "$t_type")
        case $t_status in
        superseded*) ;;
        *) repo_findings+=("Critical: $rec supersedes $(basename "$target"), which still reads \`${t_status:-no status}\`, not superseded.") ;;
        esac
      fi
      ;;
    link)
      [ -e "$dir/$rel" ] || findings+=("Nit: link to \`$rel\` points to a file that doesn't exist.")
      ;;
    esac
  done < <(grep -E '^(ref|link)'$'\t' <<<"$facts" || true)

  options=$(value_of options <<<"$facts")
  echo "## $rec"
  echo
  echo "- type: $type"
  echo "- number: $(number_of "$rec")"
  echo "- status: ${status:-none} ($class)"
  echo "- decided: $is_decided"
  echo "- provenance fence: $fence"
  [ $fence = missing ] || echo "- human_signoff: $signoff_state${signoff:+ (\`$signoff\`)}"
  missing_sections=${missing_sections%; }
  links=${links%; }
  echo "- sections missing: ${missing_sections:-none}"
  [ -z "$(options_heading "$type")" ] || echo "- options listed: $options"
  echo "- supersede links: ${links:-none}"
  if [ ${#findings[@]} -eq 0 ]; then
    echo "- findings: none"
  else
    echo "- findings:"
    printf '  - %s\n' "${findings[@]}"
  fi
  echo
done

# Numbering across each directory a record came from, including records not under review.
while read -r dir; do
  [ -n "$dir" ] || continue
  nums=$(numbered_in "$dir" '[0-9][0-9][0-9][0-9]' | cut -c1-4 | sort)
  [ -n "$nums" ] || continue
  while read -r n; do
    files=$(numbered_in "$dir" "$n" | sort | paste -sd, - | sed 's/,/, /g')
    repo_findings+=("Critical: $dir has more than one record numbered $n: $files.")
  done < <(uniq -d <<<"$nums")
  first=$((10#$(head -1 <<<"$nums")))
  last=$((10#$(tail -1 <<<"$nums")))
  gaps=""
  for ((i = first; i <= last; i++)); do
    grep -qx "$(printf '%04d' $i)" <<<"$nums" || gaps+="$(printf '%04d' $i) "
  done
  [ -z "$gaps" ] || repo_findings+=("FYI: $dir numbering skips ${gaps% }.")
done < <(sort -u <<<"$dirs")

echo "## Repository"
echo
if [ ${#repo_findings[@]} -eq 0 ]; then
  echo "- findings: none"
else
  printf -- '- %s\n' "${repo_findings[@]}"
fi
