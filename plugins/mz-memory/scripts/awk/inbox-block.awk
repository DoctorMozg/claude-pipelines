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
