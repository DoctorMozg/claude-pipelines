/^# Project Memory[[:space:]]*$/ { skip = 1; next }
/^<!-- Auto-managed by mz-memory/ { next }
/^<!-- Entries below are auto-managed/ { next }
/^<!-- mz-memory:/ { next }
skip && /^[[:space:]]*$/ { skip = 0; next }
{ skip = 0; print }
