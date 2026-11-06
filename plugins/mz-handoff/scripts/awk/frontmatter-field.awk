NR == 1 { if ($0 != "---") exit; next }
$0 == "---" { exit }
index($0, key ": ") == 1 { print substr($0, length(key) + 3); exit }
