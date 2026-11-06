NR >= from && $0 == ENVIRON["OLD_FIRST"] { found = 1; exit }
{ print }
END { exit !found }
