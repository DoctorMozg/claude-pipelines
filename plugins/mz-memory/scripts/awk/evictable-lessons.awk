$2 ~ /^\[L-[0-9]+\]$/ && $3 ~ /^n=[0-9]+$/ && $4 ~ /^last=/ {
  n = substr($3, 3) + 0
  if (n < keep) printf "0\t%06d\t%s\t%s\t%s\n", n, substr($4, 6), $2, $0
}
