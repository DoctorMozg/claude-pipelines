BEGIN { pattern = "\\[" prefix "-[0-9]+\\]" }
{
  line = $0
  while (match(line, pattern)) {
    number = substr(line, RSTART + length(prefix) + 2, RLENGTH - length(prefix) - 3) + 0
    if (number > max) max = number
    line = substr(line, RSTART + RLENGTH)
  }
}
END { print max + 1 }
