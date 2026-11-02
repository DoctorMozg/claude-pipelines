#!/usr/bin/env bash
# Helpers for the lessons store (.mz/memory/lessons.md). Source after lib/common.sh,
# which provides atomic_write. Like common.sh, every function must stay exit-code-clean.

MZ_LESSONS_START="<!-- mz-lessons-start -->"
MZ_LESSONS_END="<!-- mz-lessons-end -->"
MZ_INBOX_START="<!-- mz-inbox-start -->"
MZ_INBOX_END="<!-- mz-inbox-end -->"
MZ_LESSON_MAX_CHARS=400
# The seen list only has to outlive re-reads of recently edited state files.
MZ_LESSONS_SEEN_MAX=2000
# Unit separator between task, status and text: it survives strip_private's whitespace collapse.
MZ_LESSON_FS=$'\037'

# Create lessons.md if missing. A file that lost a marker is rebuilt around its ID'd lines,
# with the original kept as lessons.md.bak.
ensure_lessons_file() {
  local lessons_file="$1"
  mkdir -p "$(dirname "$lessons_file")"
  if [[ ! -f "$lessons_file" ]]; then
    _emit_lessons_file "" "" | atomic_write "$lessons_file"
    return 0
  fi

  local marker
  for marker in "$MZ_LESSONS_START" "$MZ_LESSONS_END" "$MZ_INBOX_START" "$MZ_INBOX_END"; do
    if ! grep -qxF "$marker" "$lessons_file"; then
      _rebuild_lessons_file "$lessons_file"
      return 0
    fi
  done
}

_rebuild_lessons_file() {
  local lessons_file="$1"
  local curated inbox
  cp -f "$lessons_file" "${lessons_file}.bak"
  curated=$(grep -E '^- \[L-[0-9]+\]' "$lessons_file" || true)
  inbox=$(grep -E '^- \[I-[0-9]+\]' "$lessons_file" || true)
  _emit_lessons_file "$curated" "$inbox" | atomic_write "$lessons_file"
}

_emit_lessons_file() {
  local curated="$1" inbox="$2"
  printf '# Project Lessons\n\n'
  printf '<!-- Auto-managed by mz-memory. Curated lessons first; new lessons wait in the Inbox. -->\n\n'
  printf '## Lessons\n\n%s\n' "$MZ_LESSONS_START"
  [[ -n "$curated" ]] && printf '%s\n' "$curated"
  printf '%s\n\n## Inbox\n\n%s\n' "$MZ_LESSONS_END" "$MZ_INBOX_START"
  [[ -n "$inbox" ]] && printf '%s\n' "$inbox"
  printf '%s\n' "$MZ_INBOX_END"
}

# next_lesson_number <prefix> <file>... — one past the highest <prefix>-NNNN id in the files
# that exist. The archive is passed too, so an id is never reused after its line moves there.
next_lesson_number() {
  local prefix="$1"
  shift
  { cat -- "$@" 2>/dev/null || true; } | awk -v prefix="$prefix" '
    BEGIN { pattern = "\\[" prefix "-[0-9]+\\]" }
    {
      line = $0
      while (match(line, pattern)) {
        number = substr(line, RSTART + length(prefix) + 2, RLENGTH - length(prefix) - 3) + 0
        if (number > max) max = number
        line = substr(line, RSTART + RLENGTH)
      }
    }
    END { print max + 1 }
  '
}

# add_lessons_to_inbox <file> <date> <sha> [trig] — prepend stdin's records to the Inbox; print the lines written.
# Untagged records get [trig] (default other). A lesson seen from the same task is skipped; from another, it recurs.
add_lessons_to_inbox() {
  local lessons_file="$1" today="$2" sha="$3" default_trig="${4:-other}"
  local records
  records=$(cat)
  [[ -n "$records" ]] || return 0

  local memory_dir seen_file keys_file
  memory_dir=$(dirname "$lessons_file")
  seen_file="${memory_dir}/.lessons-seen"
  mkdir -p "$memory_dir"
  {
    flock 9 2>/dev/null || true
    ensure_lessons_file "$lessons_file"
    touch "$seen_file"
    keys_file=$(mktemp "${memory_dir}/.mz-lessons-keys.XXXXXX")
    local first_id block
    first_id=$(next_lesson_number I "$lessons_file" "${memory_dir}/lessons.archive.md")
    # shellcheck disable=SC1112 # the curly quotes sit inside the awk program on purpose
    block=$(MZ_RECORDS="$records" awk \
      -v today="$today" -v sha="$sha" -v next_id="$first_id" -v fs="$MZ_LESSON_FS" \
      -v max_chars="$MZ_LESSON_MAX_CHARS" -v keys_path="$keys_file" -v default_trig="$default_trig" '
      { seen[$0] = 1 }
      END {
        total = split(ENVIRON["MZ_RECORDS"], records, "\n")
        for (i = 1; i <= total; i++) {
          if (split(records[i], field, fs) < 3) continue
          task = field[1]; status = field[2]; text = field[3]
          trig = default_trig
          if (match(text, /^\([a-z]+\)/)) {
            tag = substr(text, 2, RLENGTH - 2)
            if (tag ~ /^(review|failure|correction|change)$/) {
              trig = tag
              text = substr(text, RLENGTH + 1)
            }
          }
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", text)
          if (text == "") continue

          # Case and punctuation edits are not a new lesson; non-ASCII letters stay in the key.
          # [:punct:] is ASCII-only in mawk, so the arrows, dashes and quotes LLMs swap in are listed.
          key = tolower(text)
          gsub(/→|—|–|…|“|”|‘|’/, " ", key)
          gsub(/[[:punct:][:space:]]+/, " ", key)
          gsub(/^ +| +$/, "", key)
          key = task "\t" key
          if (key in seen) continue
          seen[key] = 1
          print key > keys_path

          # Cut at a word boundary so a multi-byte character is never split.
          if (length(text) > max_chars) {
            text = substr(text, 1, max_chars)
            sub(/[[:space:]]+[^[:space:]]*$/, "", text)
            text = text "..."
          }
          src = (sha != "") ? task "@" sha : task
          lines[++count] = sprintf("- [I-%04d] %s trig=%s src=%s status=%s :: %s", next_id++, today, trig, src, status, text)
        }
        for (i = count; i >= 1; i--) print lines[i]
      }
    ' "$seen_file")

    # Lines are marked seen only after the Inbox write, so a failed write retries them next time.
    # The check is explicit: a caller's $(...) may run with errexit off.
    if [[ -n "$block" ]]; then
      if ! MZ_NEW_BLOCK="$block" awk -v start="$MZ_INBOX_START" '
        $0 == start { print; print ENVIRON["MZ_NEW_BLOCK"]; next }
        { print }
      ' "$lessons_file" | atomic_write "$lessons_file"; then
        rm -f "$keys_file"
        return 1
      fi
      printf '%s\n' "$block"
    fi
    cat "$keys_file" >>"$seen_file"
    rm -f "$keys_file"
    _trim_seen "$seen_file"
  } 9>>"${lessons_file}.lock"
}

_trim_seen() {
  local seen_file="$1"
  local lines
  lines=$(wc -l <"$seen_file")
  if [[ "$lines" -gt "$MZ_LESSONS_SEEN_MAX" ]]; then
    tail -n "$MZ_LESSONS_SEEN_MAX" "$seen_file" | atomic_write "$seen_file"
  fi
}

# compact_items — drop the metadata from lesson, inbox and Digest item lines, keeping "- [ID] text".
compact_items() {
  sed -E 's/^- \[([A-Z]-[0-9]+)\] [^:]* :: /- [\1] /'
}

# fit_chars <max_chars> — print stdin's lines in order until the next one would pass the budget.
# It reads all of stdin, so the writer never gets SIGPIPE.
fit_chars() {
  awk -v max="$1" '!full { used += length($0) + 1; if (used > max) full = 1; else print }'
}

# Curated lessons as "<n> TAB <last> TAB <line>", for ranking by count, then recency.
_ranked_curated() {
  _memory_region "$1" "$MZ_LESSONS_START" "$MZ_LESSONS_END" 2>/dev/null \
    | awk '$2 ~ /^\[L-[0-9]+\]$/ && $3 ~ /^n=[0-9]+$/ && $4 ~ /^last=/ {
        printf "%d\t%s\t%s\n", substr($3, 3), substr($4, 6), $0
      }' \
    | sort -t "$(printf '\t')" -k1,1nr -k2,2r || true
}

# session_lessons <lessons_file> <top> <newest> — the <top> curated lessons seen most often, then
# most recently, followed by the <newest> inbox items.
session_lessons() {
  local lessons_file="$1" top="$2" newest="$3"
  [[ -f "$lessons_file" ]] || return 0
  _ranked_curated "$lessons_file" | cut -f3- | head -n "$top" || true
  _memory_region "$lessons_file" "$MZ_INBOX_START" "$MZ_INBOX_END" 2>/dev/null \
    | grep -E '^- \[I-[0-9]+\] ' | head -n "$newest" || true
}

# promotion_candidates <lessons_file> <min_n> — ids of curated lessons seen at least <min_n> times.
promotion_candidates() {
  local lessons_file="$1" min_n="$2"
  [[ -f "$lessons_file" ]] || return 0
  _ranked_curated "$lessons_file" | awk -v min="$min_n" '$1 >= min { print substr($4, 2, length($4) - 2) }'
}

# match_lessons <lessons_file> <keywords> <max> — the <max> lessons whose text or tags hold the
# most distinct keywords (lowercase, one per line). Ties go to the higher count, then file order.
match_lessons() {
  local lessons_file="$1" keywords="$2" max="$3"
  [[ -f "$lessons_file" && -n "$keywords" ]] || return 0
  {
    _memory_region "$lessons_file" "$MZ_LESSONS_START" "$MZ_LESSONS_END"
    _memory_region "$lessons_file" "$MZ_INBOX_START" "$MZ_INBOX_END"
  } 2>/dev/null | MZ_KEYWORDS="$keywords" awk '
    BEGIN { words = split(ENVIRON["MZ_KEYWORDS"], word, "\n") }
    /^- \[[LI]-[0-9]+\] / && (cut = index($0, " :: ")) {
      n = ($3 ~ /^n=[0-9]+$/) ? substr($3, 3) + 0 : 0
      tags = ""
      for (i = 3; i <= NF && $i != "::"; i++) if ($i ~ /^tags=/) tags = substr($i, 6)
      # Metadata stays out of the match, so a task name in src= never pulls a lesson in.
      text = tolower(substr($0, cut + 4) " " tags)
      hits = 0
      for (w = 1; w <= words; w++) if (word[w] != "" && index(text, word[w])) hits++
      if (hits) printf "%d\t%d\t%d\t%s\n", hits, n, NR, $0
    }' \
    | sort -t "$(printf '\t')" -k1,1nr -k2,2nr -k3,3n | cut -f4- | head -n "$max" || true
}
