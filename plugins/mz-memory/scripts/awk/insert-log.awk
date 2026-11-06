BEGIN { in_log = 0; new = ENVIRON["MZ_NEW_BLOCK"]; count = split(new, new_lines, "\n") }
$0 == start {
  print
  for (i = 1; i <= count && i <= max; i++) print new_lines[i]
  in_log = 1
  next
}
$0 == end { in_log = 0; print; next }
in_log {
  count++
  if (count > max) next
}
{ print }
