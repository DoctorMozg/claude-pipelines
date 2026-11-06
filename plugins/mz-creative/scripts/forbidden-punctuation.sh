#!/usr/bin/env bash
set -euo pipefail

# forbidden-punctuation.sh [--preserve <term>] [--allow <name>]... <file>... prints `file:line: <name>` per banned character in prose.
# --allow lifts the ban on em-dash, en-dash, semicolon, ellipsis or arrow. Exit 0 when clean, 1 on any hit, 2 on a usage error.
# Code, URLs, blockquotes, quoted text, frontmatter and preserved terms are skipped: they reproduce something verbatim.

usage() {
  echo "usage: forbidden-punctuation.sh [--preserve <term>]... [--allow em-dash|en-dash|semicolon|ellipsis|arrow]... <file>..." >&2
  exit 2
}

preserve=()
allowed=()
while [[ $# -gt 0 && ($1 == --preserve || $1 == --allow) ]]; do
  [[ $# -ge 2 && -n $2 ]] || usage
  if [[ $1 == --allow ]]; then
    case $2 in
      em-dash | en-dash | semicolon | ellipsis | arrow) allowed+=("${2//-/ }") ;;
      *)
        echo "forbidden-punctuation.sh: unknown --allow name $2" >&2
        usage
        ;;
    esac
  else
    preserve+=("$2")
  fi
  shift 2
done
[[ $# -gt 0 ]] || usage
for file in "$@"; do
  if [[ ! -f "$file" || ! -r "$file" ]]; then
    echo "forbidden-punctuation.sh: cannot read $file" >&2
    exit 2
  fi
done

# Terms travel through the environment, one per line, because awk -v would rewrite their backslashes.
PRESERVE_TERMS="$(printf '%s\n' ${preserve[@]+"${preserve[@]}"})"
export PRESERVE_TERMS
ALLOWED_NAMES="$(printf '%s\n' ${allowed[@]+"${allowed[@]}"})"
export ALLOWED_NAMES

# Byte semantics make the multibyte literals below match the same way in gawk and mawk.
LC_ALL=C awk '
  function strip_between(s, opener, closer,    i, j, out) {
    out = ""
    while ((i = index(s, opener)) > 0) {
      j = index(substr(s, i + length(opener)), closer)
      if (j == 0) break
      out = out substr(s, 1, i - 1)
      s = substr(s, i + length(opener) + j - 1 + length(closer))
    }
    return out s
  }

  function strip_literal(s, term,    i) {
    while ((i = index(s, term)) > 0) s = substr(s, 1, i - 1) substr(s, i + length(term))
    return s
  }

  BEGIN {
    terms = split(ENVIRON["PRESERVE_TERMS"], preserved, "\n")
    n = split(ENVIRON["ALLOWED_NAMES"], names, "\n")
    for (a = 1; a <= n; a++) allowed[names[a]] = 1
    count = split("— – ; … → ← ⇒", banned, " ")
    label["—"] = "em dash"
    label["–"] = "en dash"
    label[";"] = "semicolon"
    label["…"] = "ellipsis"
    label["→"] = "arrow"
    label["←"] = "arrow"
    label["⇒"] = "arrow"
  }

  FNR == 1 {
    fence = ""
    front = ($0 ~ /^---[ \t]*$/)
    if (front) next
  }
  front {
    if ($0 ~ /^---[ \t]*$/) front = 0
    next
  }
  fence != "" {
    if ($0 ~ ("^[ \t]*" fence "[" substr(fence, 1, 1) "]*[ \t]*$")) fence = ""
    next
  }
  match($0, /^[ \t]*(````*|~~~~*)/) {
    fence = substr($0, RSTART, RLENGTH)
    sub(/^[ \t]*/, "", fence)
    next
  }
  /^[ \t]*>/ { next }

  {
    line = $0
    for (t = 1; t <= terms; t++) line = strip_literal(line, preserved[t])
    gsub(/`[^`]*`/, "", line)
    gsub(/https?:\/\/[^ \t)>]*/, "", line)
    gsub(/&#?[A-Za-z0-9]+;/, "", line)
    gsub(/"[^"]*"/, "", line)
    line = strip_between(line, "“", "”")
    gsub(/[0-9]–[0-9]/, "", line)
    for (k = 1; k <= count; k++) {
      name = label[banned[k]]
      if (name in allowed) continue
      if (index(line, banned[k]) && !((FILENAME, FNR, name) in seen)) {
        seen[FILENAME, FNR, name] = 1
        printf "%s:%d: %s %s\n", FILENAME, FNR, name, banned[k]
        hits++
      }
    }
  }

  END { exit hits > 0 ? 1 : 0 }
' "$@"
