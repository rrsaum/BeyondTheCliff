#!/usr/bin/env bash
# UserPromptSubmit hook: re-assert the factual-honesty standard on every turn, so
# it survives context compaction (CLAUDE.md can be summarized out of context; this
# is re-injected each prompt). It does NOT verify facts; it sets the standing rule.
# The verifiable gate is scripts/verify.sh, wired into the Stop hook.
set -uo pipefail
cat >/dev/null 2>&1 || true  # drain the hook JSON on stdin (unused)

read -r -d '' ctx <<'EOF' || true
Factual-honesty standard (binding, Beyond the Cliff):
- State only what you verified this session. Cite the source of each claim: file:line, command output, or URL.
- Separate verified fact from inference, and label inference as inference.
- If you did not read it or run it, say so instead of guessing. Prefer "I do not know" or "let me check" over a confident unverified answer.
- Never present a guess, a recalled API or library detail, or an assumed file, function, route, column, or flag as established fact without confirming it exists.
- Every data point about a school, closure, enrollment figure, or trend must be sourced (IPEDS, filing, news report, primary document). Never originate a number. No estimated figure presented as data.
- "Done" means verified by a command, not asserted. Run scripts/verify.sh before claiming work is complete.
EOF

jq -n --arg c "$ctx" '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$c}}'
