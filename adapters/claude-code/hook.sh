#!/usr/bin/env bash
# adapters/claude-code/hook.sh — PostToolUse hook glue for Claude Code.
#
# Redacts PII in tool output in place, same posture as secret-guard
# (exact character spans from Presidio make this as safe as
# secret-guard's precise-span secret redaction — unlike injection-guard,
# which can only flag, not redact, since its judgment covers a whole
# chunk rather than a precise span).
#
# No AUTH_TOKEN concept — pii-guard has no hosted tier (see README "Why
# no hosted tier"), so there's nothing to authenticate against. Talks to
# pii-guard-daemon over HTTP, default localhost:8731.
#
# Fail-open: if the daemon isn't reachable, this passes tool output
# through unchanged and logs a warning — same posture as both siblings.

set -uo pipefail

ENDPOINT="${PII_GUARD_ENDPOINT:-http://127.0.0.1:8731}"

RAW="$(cat)"

TEXT="$(printf '%s' "$RAW" | jq -r '
  .tool_response as $r
  | if $r == null then ""
    elif ($r | type) == "string" then $r
    elif $r.stdout != null then $r.stdout
    elif $r.output != null then $r.output
    elif $r.content != null then ($r.content | if type == "string" then . else tojson end)
    else ($r | tojson)
    end
' 2>/dev/null)"

if [ -z "$TEXT" ]; then
  exit 0
fi

RESPONSE="$(jq -n --arg text "$TEXT" '{text: $text}' \
  | curl -sS -m 10 -X POST "${ENDPOINT}/analyze" \
      -H "Content-Type: application/json" \
      -d @- 2>/dev/null)"

if [ -z "$RESPONSE" ]; then
  echo "pii-guard: daemon unreachable at ${ENDPOINT}, passing through unredacted (fail-open)" >&2
  exit 0
fi

FOUND="$(echo "$RESPONSE" | jq -r '.found // false' 2>/dev/null)"

if [ "$FOUND" != "true" ]; then
  exit 0
fi

REDACTED="$(echo "$RESPONSE" | jq -r '.redacted_text')"

jq -n --arg out "$REDACTED" \
  '{hookSpecificOutput: {hookEventName: "PostToolUse", updatedToolOutput: $out}}'
