#!/usr/bin/env bash
# adapters/claude-code/hook.sh — PostToolUse hook glue for Claude Code.
#
# BASH-ONLY, STRUCTURED OUTPUT — found the hard way, while building
# gramatr/claude-plugin-guards: Claude Code's updatedToolOutput schema
# is PER TOOL, and only Bash's shape is confirmed from the docs — a
# structured object, not a bare string:
#   {"stdout": "...", "stderr": "...", "interrupted": false, "isImage": false}
# "A value that doesn't match the tool's output schema is ignored and
# the original output is used." This script used to return a bare
# string and matched Read|Grep|WebFetch too — it would have silently
# no-op'd on every tool if ever wired into a real settings.json. Fixed:
# Bash only, correct shape, exits 0 for anything else. See README
# "Known limitations."
#
# Also found at the same time: if multiple PostToolUse hooks are
# matched on the same tool call, Claude Code's docs say they run in
# parallel with an undefined resolution order for updatedToolOutput.
# If you're using this alongside secret-guard/injection-guard, prefer
# gramatr/claude-plugin-guards' combined-hook.sh (one deterministic
# result) over wiring all three independently on the same matcher.
#
# Redacts PII in tool output in place, same posture as secret-guard
# (exact character spans from Presidio make this as safe as
# secret-guard's precise-span secret redaction).
#
# No AUTH_TOKEN concept — pii-guard has no hosted tier (see README "Why
# no hosted tier"). Talks to pii-guard-daemon over HTTP, default
# localhost:8731.
#
# Fail-open: if the daemon isn't reachable, this passes tool output
# through unchanged and logs a warning.

set -uo pipefail

ENDPOINT="${PII_GUARD_ENDPOINT:-http://127.0.0.1:8731}"

RAW="$(cat)"

TOOL_NAME="$(printf '%s' "$RAW" | jq -r '.tool_name // ""' 2>/dev/null)"
if [ "$TOOL_NAME" != "Bash" ]; then
  exit 0
fi

STDOUT="$(printf '%s' "$RAW" | jq -r '.tool_response.stdout // ""' 2>/dev/null)"
STDERR="$(printf '%s' "$RAW" | jq -r '.tool_response.stderr // ""' 2>/dev/null)"
INTERRUPTED="$(printf '%s' "$RAW" | jq -r '.tool_response.interrupted // false' 2>/dev/null)"
IS_IMAGE="$(printf '%s' "$RAW" | jq -r '.tool_response.isImage // false' 2>/dev/null)"

if [ -z "$STDOUT" ]; then
  exit 0
fi

RESPONSE="$(jq -n --arg text "$STDOUT" '{text: $text}' \
  | curl -sS -m 10 -X POST "${ENDPOINT}/analyze" \
      -H "Content-Type: application/json" \
      -d @- 2>/dev/null)"

if [ -z "$RESPONSE" ]; then
  echo "pii-guard hook: daemon unreachable at ${ENDPOINT}, passing through unredacted (fail-open)" >&2
  exit 0
fi

FOUND="$(echo "$RESPONSE" | jq -r '.found // false' 2>/dev/null)"

if [ "$FOUND" != "true" ]; then
  exit 0
fi

REDACTED="$(echo "$RESPONSE" | jq -r '.redacted_text')"

jq -n \
  --arg stdout "$REDACTED" \
  --arg stderr "$STDERR" \
  --argjson interrupted "$INTERRUPTED" \
  --argjson isImage "$IS_IMAGE" \
  '{hookSpecificOutput: {hookEventName: "PostToolUse", updatedToolOutput: {stdout: $stdout, stderr: $stderr, interrupted: $interrupted, isImage: $isImage}}}'
