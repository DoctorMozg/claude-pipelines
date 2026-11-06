NR <= max { out = out (NR > 1 ? ", " : "") $0 }
END { if (NR > max) out = out " and " NR - max " more"; print out }
