#!/usr/bin/env bash
# The done-gate: turn "it works / it's clean" into a verifiable command, not a
# claim. Runs the deterministic checks (style guide + ruff) over changed files and
# exits non-zero if any fail. Pass --tests to also run pytest if a suite exists.
#
# Usage:
#   scripts/verify.sh            # style guide + ruff on changed files
#   scripts/verify.sh --tests    # also run the pytest suite (if present)
#
# Exit 0 = clean. Exit non-zero = a claim of "done" is not yet backed by evidence.
set -uo pipefail

root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || echo .)}"
cd "$root" || exit 1

run_tests=0
[ "${1:-}" = "--tests" ] && run_tests=1

# Changed files: tracked edits (staged + unstaged, excluding deletions) plus
# untracked-but-not-ignored files. This is the surface a "done" claim covers.
# Kept bash 3.2 safe (macOS default shell): no mapfile, guard empty-array expansion.
all_files=()
py_files=()
while IFS= read -r f; do
  [ -n "$f" ] || continue
  [ -f "$f" ] || continue
  all_files+=("$f")
  case "$f" in
    *.py) py_files+=("$f") ;;
  esac
done < <(
  {
    git diff --name-only --diff-filter=d HEAD 2>/dev/null
    git ls-files --others --exclude-standard 2>/dev/null
  } | sort -u
)

fail=0

# Style guide (copy, templates, docs, code comments: the em-dash rule applies
# everywhere). style_lint.py takes file paths and degrades on non-text input.
if [ "${#all_files[@]}" -gt 0 ]; then
  echo "== style_lint =="
  python3 scripts/style_lint.py "${all_files[@]}" || fail=1
fi

# Ruff (Python only). Prefer ruff on PATH, else a project venv binary.
if [ "${#py_files[@]}" -gt 0 ]; then
  ruff_bin=$(command -v ruff || true)
  [ -n "$ruff_bin" ] || ruff_bin="$root/.venv/bin/ruff"
  [ -x "$ruff_bin" ] || ruff_bin="$root/venv/bin/ruff"
  if [ -x "$ruff_bin" ] || command -v "$ruff_bin" >/dev/null 2>&1; then
    echo "== ruff check =="
    "$ruff_bin" check "${py_files[@]}" || fail=1
    echo "== ruff format --check =="
    "$ruff_bin" format --check "${py_files[@]}" || fail=1
  else
    echo "ruff not found on PATH or in venv; skipping"
  fi
fi

# Tests (opt-in): the evidence behind a behavioral claim. Runs only if a suite exists.
if [ "$run_tests" -eq 1 ]; then
  if [ -d tests ] || ls test_*.py *_test.py >/dev/null 2>&1; then
    echo "== pytest =="
    if [ -x .venv/bin/python ]; then
      .venv/bin/python -m pytest || fail=1
    elif [ -x venv/bin/python ]; then
      venv/bin/python -m pytest || fail=1
    else
      pytest || fail=1
    fi
  else
    echo "no test suite found; skipping pytest"
  fi
fi

if [ "$fail" -ne 0 ]; then
  echo "VERIFY: FAILED. Resolve the above before claiming this work is done."
  exit 1
fi

if [ "${#all_files[@]}" -eq 0 ]; then
  echo "VERIFY: no changed files to check."
else
  echo "VERIFY: clean (${#all_files[@]} changed file(s) checked)."
fi
exit 0
