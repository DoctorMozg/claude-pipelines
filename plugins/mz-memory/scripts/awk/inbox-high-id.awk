match($0, /^- \[I-[0-9]+\]/) { n = substr($0, 6, RLENGTH - 6) + 0; if (n > max) max = n } END { print max + 0 }
