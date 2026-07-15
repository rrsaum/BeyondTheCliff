# Enforcement: how code and content standards are kept

Standards are enforced in depth. Reminders alone get skipped, so the durable
guarantees are mechanical. From weakest (guidance) to strongest (unbypassable):

| Layer | Where | Runs for | Blocks? |
|---|---|---|---|
| CLAUDE.md standards | loaded each session | the agent | no (guidance) |
| design-system skill | `.claude/skills/design-system` | the agent, on UI work | no (guidance) |
| PreToolUse schema/route guard | `.claude/settings.json` to `scripts/schema_route_guard.sh` | the agent, on Write/Edit of DDL or routes | deny-once (re-issue allowed) |
| PostToolUse hooks | `.claude/settings.json` to `scripts/*_hook.sh` | the agent, on edit | no (warn) |
| **pre-commit gate** | `.githooks/pre-commit` | **any local commit** | **yes (local)** |
| **CI + branch protection** | `.github/workflows/*.yml` | **every push and PR** | **yes (server, unbypassable)** |

The engines that run in pre-commit and CI:
- `scripts/style_lint.py`: hard-blocks em-dash + member-facing jargon; inline style advisory.
- `ruff` (config in `pyproject.toml`): lint + format-check on Python.
- `scripts/schema_audit.py`: hard-blocks a duplicate column or re-created table; similar-name advisory.
- `scripts/route_audit.py`: hard-blocks a duplicate route method+path.
- `scripts/quality_audit.py`: advisory only (duplication, module length, complexity/simplify, dead code).
- `scripts/html_audit.py`: semantic-markup / accessibility audit on templates (heading
  hierarchy, img alt-text, native controls vs clickable divs, page metadata, JSON-LD,
  layout-shift proxies). Ships ADVISORY-FIRST: it always exits 0 (`BLOCK_HARD=False`),
  so it prints findings without gating. Flip `BLOCK_HARD` to True to graduate the hard
  rules (hierarchy/a11y-alt/a11y-ctrl/seo-head) and the pre-commit, CI, and verify.sh
  passes all start enforcing together. It checks only the STATICALLY decidable keys;
  Web3, static-site/framework choice, responsive design, and Core Web Vitals as a
  runtime metric are judgment calls owned by the `design-system` skill + CLAUDE.md.

All are scoped to CHANGED or STAGED files, so pre-existing findings do not block
unrelated work, but anything you touch must be clean.

### Full test suite (CI only)

`.github/workflows/test-suite.yml` runs the WHOLE `pytest` suite on every push and
PR, against a real PostgreSQL 16 service. The suite is DB-backed: `conftest.py`
builds the entire schema from `intelligence_api/migrations/*.sql` into an empty
database, so CI needs no seed step. This gate exists because the suite once
silently rotted (it was only ever run in subsets, never whole); running it whole
means a regression cannot land green. It installs `intelligence_api/requirements.txt`
on Python 3.12 (verified the suite passes against those exact pinned versions).
`tests/visual` is EXCLUDED there (its baseline PNGs are macOS-specific and will
not pixel-match a Linux CI browser); visual is a local pre-ship gate on macOS.

### Advisory to blocking (graduation)

`quality_audit.py` is advisory-first on purpose, the same way ruff was: a one-time
baseline sweep precedes any blocking. To graduate a rule group, sweep the active
tree, confirm clean on changed-files scope, then move the group into the ruff
`select` (drop `F841` from `ignore`), or flip `quality_audit.exit_code` to return
1 on the duplication/module-length tags. The advisory set and checklist live in
`pyproject.toml`.

## 1. Local gate: install the pre-commit hook (once per clone)

Git does not auto-run committed hooks (security), so each clone runs this once:

```
scripts/install-hooks.sh
```

This sets `core.hooksPath` to `.githooks/`. From then on, `git commit` runs
`style_lint.py` + `ruff` on staged files and blocks on hard violations.
Emergency bypass: `git commit --no-verify` (the server gate below still applies).

## 2. Server gate: branch protection (the unbypassable layer)

CI already runs on every push and PR, but a red check only PREVENTS a merge
once `main` requires it. Enable this once (repo admin):

GitHub UI: Settings to Branches to Add branch ruleset (or rule) for `main`:
- Require a pull request before merging.
- Require status checks to pass: add the `Style Lint` and `Ruff` checks.
- Require branches to be up to date before merging.
- Include administrators (so the rule applies to everyone, including admins).

Or via the CLI (after `gh auth login`). The status-check context names must match
exactly what appears in a PR's Checks tab (the job names); confirm them on a real
PR first, then:

```
gh api -X PUT repos/rrsaum/360Investor/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  --input - <<'JSON'
{
  "required_status_checks": { "strict": true, "contexts": ["style-lint", "ruff"] },
  "enforce_admins": true,
  "required_pull_request_reviews": { "required_approving_review_count": 0 },
  "restrictions": null
}
JSON
```

## Test database isolation (binding)

**A test must never leave a committed change in a live or shared database.** It runs
against the isolated test database, rolls back everything it writes, or mocks the
persistence layer. This is a rule, not a convention, and it is enforced mechanically,
not by reviewer vigilance.

How it is enforced (`intelligence_api/tests/conftest.py`):

- Tests run against a SEPARATE database, `intelligence_test`, never the live
  `intelligence` dev DB. `conftest.py` forces `POSTGRES_DB=intelligence_test` before
  any app module is imported, so the production code paths under test (which reach the
  DB through `config.settings` / `db.postgres`) connect to the test DB too. A test that
  exercises a real write path can no longer touch dev data.
- The test DB is auto-created from the migration ledger on first run (a fresh checkout
  or CI just works), so it is reproducible and disposable.
- A session guard (`_enforce_isolated_db`) aborts the whole run if the application is
  ever resolved to the live database name, and an import-time check refuses
  `TEST_POSTGRES_DB=intelligence`. Either path fails loudly rather than silently
  reading or writing production data.

Why this exists: the suite previously ran against the dev DB. A failure-path test
drove the real `record_fetch_subsystem` write path, which stamps every row in a
subsystem, leaving ~98 real rows reading `fetch_status='error'` ('boom') plus an
`error` job ledger. The state machine then painted a wall of false "fetch down" on the
live status page. Per-test snapshot/restore was tried and leaked again within the hour
(it missed `scheduler_job_status`): table-by-table restore is whack-a-mole. The
isolated test DB removes the entire class structurally.

## Honest limits

- Client-side layers (hooks, pre-commit) are best-effort: they can be skipped by
  not installing them, by `--no-verify`, or by editing on github.com. They catch
  mistakes early but do not guarantee anything.
- The only unbypassable layer is server-side required status checks. Until branch
  protection is enabled, CI is informational on direct pushes.

## Widening to the whole repo (optional follow-up)

Done so far (2026-06-01): the one-time `ruff check --fix && ruff format` baseline
sweep ran, so `ruff check .` is clean repo-wide; the `_emdash_exempt` deferral
path bug is fixed (deferred dirs are now correctly skipped); ruff is scoped to
changed files in CI and the hooks.

Still needed before widening enforcement from changed-files to the WHOLE tree:

1. Em-dash holdouts: non-deferred files still contain em-dashes (for example
   `intelligence_api/schema_migration*.sql`). Sweep those, and decide whether to
   keep or clear the em-dash deferral list in `style_lint.py`.
2. Then widen the CI globs (`ruff.yml`, `style-lint.yml`) and the pre-commit gate
   from changed-files to the whole tree.

`F841` (unused locals) is currently in the ruff ignore list as deferred noise;
a focused pass could re-enable it.
