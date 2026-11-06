function flush() {
  if (text != "") printf "- [D-%04d] n=1 last=%s trig=migrated src=mz-compressed tags=%s :: %s\n", next_id++, today, tag, text
  text = ""
}
/^#+[[:space:]]/ {
  flush()
  tag = tolower($0)
  sub(/^#+[[:space:]]+/, "", tag); gsub(/[^a-z0-9]+/, "-", tag); sub(/^-+/, "", tag); sub(/-+$/, "", tag)
  next
}
/^[[:space:]]*[-*][[:space:]]/ { flush(); text = $0; sub(/^[[:space:]]*[-*][[:space:]]+/, "", text); next }
NF { line = $0; sub(/^[[:space:]]+/, "", line); text = (text == "" ? line : text " " line) }
END { flush() }
