$0 == "## Next" { inside = 1; next } inside && /^## / { exit } inside && NF { print }
