function dump(path,   line) { while ((getline line < path) > 0) print line; close(path) }
$0 == ds { print; dump(digest_file); in_digest = 1; next }
in_digest && $0 == de { in_digest = 0; print; next }
in_digest { next }
# A file without a Digest gets one just above the Activity Log heading, or its marker.
!has_digest && want_digest && !inserted && ($0 == "## Activity Log" || $0 == ls) {
  printf "## Digest\n\n%s\n", ds
  dump(digest_file)
  printf "%s\n\n", de
  inserted = 1
}
$0 == ls { print; dump(log_file); in_log = 1; next }
in_log && $0 == le { in_log = 0; print; next }
in_log { next }
{ print }
