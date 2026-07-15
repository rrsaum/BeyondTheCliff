#!/usr/bin/env bash
# Activate the committed git hooks for this clone. Run once after cloning:
#   scripts/install-hooks.sh
# Git does not auto-run committed hooks (security), so this points core.hooksPath
# at the version-controlled .githooks/ directory.
set -euo pipefail
root=$(git rev-parse --show-toplevel)
git -C "$root" config core.hooksPath .githooks
chmod +x "$root/.githooks/"* 2>/dev/null || true
echo "Hooks installed: core.hooksPath -> .githooks"
echo "Pre-commit now runs style_lint.py + ruff on staged files. Bypass with --no-verify."
