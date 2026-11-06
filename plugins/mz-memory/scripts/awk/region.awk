$0 == start { capture = 1; next }
$0 == end { capture = 0 }
capture { print }
