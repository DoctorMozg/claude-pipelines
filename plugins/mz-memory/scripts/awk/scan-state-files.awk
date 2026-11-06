function start(   parts, count, a) {
  count = split(FILENAME, parts, "/")
  task = parts[count - 1]
  status = ""; has_status = 0; phase = ""; has_phase = 0
  decisions = 0; extras = 0; lessons = 0; harvested = 0
  for (a = 1; a <= agents; a++) mentioned[a] = 0
}
function finish(   i, a, entry) {
  if (task == "") return
  # Lessons are read whatever the status: failed and blocked runs are where most of them come from.
  for (i = 1; i <= harvested; i++) print task fs (status == "" ? "unknown" : status) fs lesson[i] > (out "/lessons")
  # Writers use `complete`; `completed` is still read because older skills wrote it.
  if (status != "complete" && status != "completed") return
  # Without a marker we cannot tell what the old date-keyed dedup already logged.
  if (first_run && (task in logged)) return
  entry = "- [" today "] " task
  if (phase != "") entry = entry " (phase=" phase ")"
  if (branch != "" && sha != "") entry = entry " [" branch "@" sha "]"
  print entry > (out "/log")
  for (i = 1; i <= extras; i++) print extra[i] > (out "/log")
  for (a = 1; a <= agents; a++) if (mentioned[a]) print agent[a] "\t" entry > (out "/agents")
}
BEGIN {
  count = split(ENVIRON["MZ_AGENTS"], names, "\n")
  for (i = 1; i <= count; i++) if (names[i] != "") { agent[++agents] = names[i]; tag[agents] = "[" tolower(names[i]) "]" }
  if (first_run) {
    while ((getline line < ENVIRON["MZ_MEMORY_FILE"]) > 0) {
      split(line, field, " ")
      if (field[1] == "-") logged[field[3]] = 1
    }
  }
}
FNR == 1 { finish(); start() }
{
  if (!has_status && match($0, /Status[*]*: [a-z_]*/)) {
    has_status = 1; status = substr($0, RSTART, RLENGTH); sub(/.*: /, "", status)
  }
  if (!has_phase && match($0, /Phase[*]*: [A-Za-z0-9_.-]*/)) {
    has_phase = 1; phase = substr($0, RSTART, RLENGTH); sub(/.*: /, "", phase)
  }
  heading = ($0 ~ /^##[[:space:]]/)

  # The first non-blank lines of Decisions and Notes, counted together in file order. Lessons go
  # to lessons.md instead, so they do not age out with the log.
  if ($0 ~ /^##[[:space:]]+(Decisions|Notes)[[:space:]]*$/) decisions = 1
  else if (heading) decisions = 0
  else if (decisions && NF && extras < max_extra) extra[++extras] = "  " $0

  # Bullets under the first "## Lessons" only, which a repeated heading right after it extends;
  # prose lines are skipped.
  if (lessons != 2 && $0 ~ /^##[[:space:]]+Lessons[[:space:]]*$/) lessons = 1
  else if (lessons == 1 && heading) lessons = 2
  else if (lessons == 1 && harvested < max_lessons && $0 ~ /^[[:space:]]*([-*]|[0-9]+\.)[[:space:]]+[^[:space:]]/) {
    text = $0
    sub(/^[[:space:]]*([-*]|[0-9]+\.)[[:space:]]+/, "", text)
    lesson[++harvested] = text
  }

  # The agent bridge: an entry whose state file mentions [agent-name] is copied to that agent.
  if (agents) {
    low = tolower($0)
    for (a = 1; a <= agents; a++) if (!mentioned[a] && index(low, tag[a])) mentioned[a] = 1
  }
}
END { finish() }
