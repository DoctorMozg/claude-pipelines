#!/usr/bin/env bash
set -euo pipefail

# forbidden-punctuation.sh <file>... prints `file:line: <name>` for each banned character in prose.
# Exit 0 when clean, 1 on any hit, 2 on a usage error or an unreadable file.
# Code, URLs, blockquotes, quoted text and frontmatter are skipped: they reproduce something verbatim.

if [[ $# -eq 0 ]]; then
  echo "usage: forbidden-punctuation.sh <file>..." >&2
  exit 2
fi
for file in "$@"; do
  if [[ ! -f "$file" || ! -r "$file" ]]; then
    echo "forbidden-punctuation.sh: cannot read $file" >&2
    exit 2
  fi
done

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

  BEGIN {
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
    gsub(/`[^`]*`/, "", line)
    gsub(/https?:\/\/[^ \t)>]*/, "", line)
    gsub(/&#?[A-Za-z0-9]+;/, "", line)
    gsub(/"[^"]*"/, "", line)
    line = strip_between(line, "“", "”")
    gsub(/[0-9]–[0-9]/, "", line)
    for (k = 1; k <= count; k++) {
      name = label[banned[k]]
      if (index(line, banned[k]) && !((FILENAME, FNR, name) in seen)) {
        seen[FILENAME, FNR, name] = 1
        printf "%s:%d: %s %s\n", FILENAME, FNR, name, banned[k]
        hits++
      }
    }
  }

  END { exit hits > 0 ? 1 : 0 }
' "$@"
