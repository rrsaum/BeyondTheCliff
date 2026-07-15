#!/usr/bin/env bash
# Stop hook (asyncRewake): at the done boundary, re-run the deterministic verify
# gate over changed files. Exit 0 when clean (silent); exit 2 to wake the model
# with the failures, so "done" cannot mean "unverified". Tests are NOT run here
# (slow, need the DB): run scripts/verify.sh --tests for behavioral claims.
#
# To soften this from a re-waking gate to an advisory note, drop "asyncRewake" from
# the Stop hook in .claude/settings.json, or remove the hook via /hooks.
set -uo pipefail
cat >/dev/null 2>&1 || true  # drain the Stop hook JSON on stdin (unused)

root="${CLAUDE_PROJECT_DIR:-.}"
out=$(bash "$root/scripts/verify.sh" 2>&1)
rc=$?

[ "$rc" -eq 0 ] && exit 0

printf '%s\n' "Done-gate failed. Resolve before finishing this turn:" "$out"
exit 2
