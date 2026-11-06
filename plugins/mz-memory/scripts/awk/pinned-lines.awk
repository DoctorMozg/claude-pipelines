/^# / { next }
/^<!--/ { next }
/^## / { next }
/^- / { next }
/^[[:space:]]*$/ { next }
{ print }
