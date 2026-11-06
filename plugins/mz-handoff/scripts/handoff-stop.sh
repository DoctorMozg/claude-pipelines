#!/usr/bin/env bash
set -euo pipefail

# Stop: once the main conversation has been compacted MZ_HANDOFF_AFTER times, blocks the stop once
# so Claude writes a handoff, then reminds the user after each later compaction. Advisory: exits 0.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/handoff.sh
source "${SCRIPT_DIR}/lib/handoff.sh"
command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat)
field() { jq -r --arg key "$1" '.[$key] // empty | tostring' <<<"$INPUT" 2>/dev/null || echo ""; }

# Subagents and teammates never hand off, and a stop that is already continuing is left alone.
[[ -z "$(field agent_id)" ]] || exit 0
[[ "$(field stop_hook_active)" != "true" ]] || exit 0

SESSION_ID=$(field session_id)
TRANSCRIPT=$(field transcript_path)
[[ "$SESSION_ID" =~ ^[A-Za-z0-9_-]+$ ]] || exit 0

THRESHOLD=$(handoff_threshold)
[[ "$THRESHOLD" -gt 0 ]] || exit 0

HANDOFF_DIR="$(find_project_root)/.mz/handoff"
DUE_FILE="${HANDOFF_DIR}/.due/${SESSION_ID}"
# handoff-session.sh sets this flag on every compaction, so most turns end at this test.
[[ -e "$DUE_FILE" ]] || exit 0
rm -f "$DUE_FILE"

if [[ ! -f "$TRANSCRIPT" ]]; then
  echo "mz-handoff: transcript ${TRANSCRIPT} not found, can't count compactions" >&2
  exit 0
fi
COUNT=$(compaction_count "$TRANSCRIPT")
if [[ "$COUNT" -eq 0 ]]; then
  # A subagent compaction also sets the flag; only an unexplained zero means the format changed.
  if ! grep -rqF -- "$MZ_HANDOFF_BOUNDARY" "${TRANSCRIPT%.jsonl}/subagents" 2>/dev/null; then
    echo "mz-handoff: a compaction was reported but ${TRANSCRIPT} has no compact_boundary line; the transcript format may have changed" >&2
  fi
  exit 0
fi
[[ "$COUNT" -ge "$THRESHOLD" ]] || exit 0

SEEN_FILE="${HANDOFF_DIR}/.nudged/${SESSION_ID}"
SEEN=$(cat "$SEEN_FILE" 2>/dev/null || echo "")
[[ "$SEEN" =~ ^[0-9]+$ ]] || SEEN=""
if ! mkdir -p "${HANDOFF_DIR}/.nudged" || ! printf '%s\n' "$COUNT" >"$SEEN_FILE"; then
  echo "mz-handoff: can't write ${SEEN_FILE}, skipping the handoff nudge" >&2
  exit 0
fi

if [[ -z "$SEEN" ]]; then
  reason="This session has been compacted ${COUNT} times; the handoff threshold (MZ_HANDOFF_AFTER) is ${THRESHOLD}. Each further compaction summarizes a summary and loses detail. The /mz-handoff:handoff skill writes a handoff file under .mz/handoff/ from this session's transcript (${TRANSCRIPT}) and git state. Once it exists, the user can type /clear, and the next session in this terminal loads it."
  jq -n --arg reason "$reason" '{decision: "block", reason: $reason}'
elif [[ "$COUNT" -gt "$SEEN" ]]; then
  HANDOFF=$(handoff_for_session "$HANDOFF_DIR" "$SESSION_ID")
  if [[ -n "$HANDOFF" ]]; then
    where="The handoff is at ${HANDOFF#"$(find_project_root)"/}; /clear starts a fresh session that loads it."
  else
    where="No handoff written yet; run /mz-handoff:handoff, then /clear."
  fi
  jq -n --arg msg "mz-handoff: this session has been compacted ${COUNT} times. ${where}" '{systemMessage: $msg}'
fi
exit 0
