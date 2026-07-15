#!/usr/bin/env bash
# PostToolUse hook (warn, non-blocking): flag style-guide violations in the file
# just written/edited, so they get fixed in the same turn. Reads the hook JSON on
# stdin; if scripts/style_lint.py reports violations, emits additionalContext.
set -euo pipefail
payload=$(cat)
f=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')
[ -n "$f" ] || exit 0
root="${CLAUDE_PROJECT_DIR:-.}"
out=$(python3 "$root/scripts/style_lint.py" "$f" 2>/dev/null || true)
[ -n "$out" ] || exit 0
jq -n --arg c "$out" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:("Beyond the Cliff style-guide violations in the file just edited (fix before continuing):\n"+$c)}}'
