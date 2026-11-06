function flush() {
  if (body != "") printf "- [E-%04d] %s trig=log src=%s status=log :: %s\n", ++count, day, src, body
  body = ""
}
BEGIN { day = today; src = "note" }
/^- / {
  flush()
  body = substr($0, 3); day = today; src = "note"
  if (body ~ /^\[[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]\] /) { day = substr(body, 2, 10); body = substr(body, 14) }
  if (body ~ /^[0-9][0-9][0-9][0-9]_[0-9][0-9]_[0-9][0-9]_/) { src = body; sub(/[^A-Za-z0-9_.-].*$/, "", src) }
  next
}
NF { line = $0; sub(/^[[:space:]]+/, "", line); body = (body == "" ? line : body " | " line) }
END { flush() }
