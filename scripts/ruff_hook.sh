#!/usr/bin/env bash
# PostToolUse hook (warn, non-blocking): run ruff on the .py file just written or
# edited so lint/format findings get fixed in the same turn. Reads the hook JSON
# on stdin. Degrades to a no-op if the file is not Python or ruff is unavailable,
# so it never blocks a turn. CI is the actual gate (see .github/workflows/ruff.yml).
set -uo pipefail
payload=$(cat)
f=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')
[ -n "$f" ] || exit 0
case "$f" in
  *.py) ;;
  *) exit 0 ;;
esac
root="${CLAUDE_PROJECT_DIR:-.}"
# Prefer ruff on PATH, else the project venv binary.
ruff_bin=$(command -v ruff || true)
[ -n "$ruff_bin" ] || ruff_bin="$root/venv/bin/ruff"
[ -x "$ruff_bin" ] || command -v "$ruff_bin" >/dev/null 2>&1 || exit 0
# Only surface output when ruff actually finds something (non-zero exit). ruff
# prints success messages ("All checks passed!", "N files already formatted") on
# clean runs, so gate on exit codes, not on whether there was any output.
check_out=$("$ruff_bin" check "$f" 2>&1); check_rc=$?
fmt_out=$("$ruff_bin" format --check "$f" 2>&1); fmt_rc=$?
[ "$check_rc" -eq 0 ] && [ "$fmt_rc" -eq 0 ] && exit 0
out=""
[ "$check_rc" -ne 0 ] && out="$check_out"
if [ "$fmt_rc" -ne 0 ]; then
  if [ -n "$out" ]; then
    out="$out
$fmt_out"
  else
    out="$fmt_out"
  fi
fi
jq -n --arg c "$out" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:("ruff findings in the file just edited (run `ruff check --fix` then `ruff format`):\n"+$c)}}'
