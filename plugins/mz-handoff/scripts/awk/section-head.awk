$0 == heading { inside = 1; next }
inside && /^## / { exit }
inside && NF { print; exit }
