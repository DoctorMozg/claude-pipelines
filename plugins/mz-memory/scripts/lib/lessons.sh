#!/usr/bin/env bash
# Helpers for the lessons store (.mz/memory/lessons.md). Source after lib/common.sh,
# which provides atomic_write. Like common.sh, every function must stay exit-code-clean.

MZ_LESSONS_START="<!-- mz-lessons-start -->"
MZ_LESSONS_END="<!-- mz-lessons-end -->"
MZ_INBOX_START="<!-- mz-inbox-start -->"
MZ_INBOX_END="<!-- mz-inbox-end -->"
MZ_LESSONS_PER_TASK=10
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

# extract_state_lessons <state_file> <task> <status> — print one record per bullet under
# "## Lessons": task, status and text joined by MZ_LESSON_FS. Prose lines are skipped.
extract_state_lessons() {
  local state_file="$1" task="$2" status="$3"
  awk -v task="$task" -v status="$status" -v fs="$MZ_LESSON_FS" -v max="$MZ_LESSONS_PER_TASK" '
    /^##[[:space:]]+Lessons[[:space:]]*$/ { capture = 1; next }
    /^##[[:space:]]/ && capture { exit }
    capture && /^[[:space:]]*([-*]|[0-9]+\.)[[:space:]]+[^[:space:]]/ {
      sub(/^[[:space:]]*([-*]|[0-9]+\.)[[:space:]]+/, "")
      print task fs status fs $0
      if (++count >= max) exit
    }
  ' "$state_file" 2>/dev/null || true
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

# add_lessons_to_inbox <lessons_file> <date> <sha> — read records from stdin and prepend the
# new ones to the Inbox, newest first. A task's lesson is skipped once seen, so re-reading an
# edited state file adds only its new lines, while the same lesson from another task still
# counts as a recurrence.
add_lessons_to_inbox() {
  local lessons_file="$1" today="$2" sha="$3"
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
      -v max_chars="$MZ_LESSON_MAX_CHARS" -v keys_path="$keys_file" '
      { seen[$0] = 1 }
      END {
        total = split(ENVIRON["MZ_RECORDS"], records, "\n")
        for (i = 1; i <= total; i++) {
          if (split(records[i], field, fs) < 3) continue
          task = field[1]; status = field[2]; text = field[3]
          trig = "other"
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

    if [[ -n "$block" ]]; then
      MZ_NEW_BLOCK="$block" awk -v start="$MZ_INBOX_START" '
        $0 == start { print; print ENVIRON["MZ_NEW_BLOCK"]; next }
        { print }
      ' "$lessons_file" | atomic_write "$lessons_file"
    fi
    # Mark lines as seen only after the Inbox write, so a failed write retries them next time.
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
