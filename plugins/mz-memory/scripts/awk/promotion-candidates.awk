BEGIN { while ((getline line < declined) > 0) { split(line, field, " "); held[field[1]] = field[2] + 0 } }
{
  id = substr($4, 2, length($4) - 2)
  if ($1 >= min && !(id in held && $1 <= held[id])) print id
}
