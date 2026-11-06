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
}
