match($0, /^- \[I-[0-9]+\]/) { if (substr($0, 6, RLENGTH - 6) + 0 > last) n++ } END { print n + 0 }
