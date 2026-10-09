# Beyond the Cliff

Beyond the Cliff tracks the contraction of American higher education (the enrollment cliff,
closures, consolidations) and maps the way through it. This repository holds its first
feature, a closure and consolidation tracker. It is a FastAPI + Jinja app over a SQLite
database built from committed CSVs.

The tracker records closures and survivors side by side, every figure traced to a primary
source: IPEDS, the SHEEO Closed College Context dataset, ED composite scores and Heightened Cash
Monitoring lists, IRS Form 990 filings, NCES Digest tables, and dated news reports.

## Quick start

### Docker

```
docker compose up        # builds the DB from data/*.csv, serves on http://localhost:8002
docker compose down      # stop it
```

The repo is bind-mounted into the container, so `/admin` edits to `data/*.csv` land in the working
tree and `uvicorn --reload` picks up code changes. Set `TRACKER_PORT` in `.env` to change the host
port (default 8002).

### Local

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
python3 scripts/build_db.py                          # build data/beyondthecliff.db from data/*.csv
.venv/bin/python -m uvicorn app.main:app --reload    # serve the tracker
```

The Docker image uses Python 3.14 (`Dockerfile`).

### From a prebuilt snapshot (no build step)

A deployment can restore a packaged database and skip the CSV-to-SQL pipeline entirely:

```
python3 scripts/build_db.py      # (maintainer) make sure the DB is current
python3 scripts/backup_db.py     # (maintainer) writes dist/beyondthecliff.db.gz + manifest
scripts/install.sh               # (target) verify checksum, restore into data/, check row counts
```

`dist/` is git-ignored. Ship the snapshot as a release asset, not through git.

## What it serves

| Route | Page |
|---|---|
| `/` | The closure map: a filterable, sortable table of closures with aggregate charts and sector-size context |
| `/cliff` | The demographic picture: national colleges, enrollment, high-school graduates, and real GDP back to 1869, plus state graduate trends |
| `/resilience` | Institutions ranked by resilience, filterable by control and state |
| `/institution/{id}` | One institution: enrollment history, closure anatomy, composite scores, and financial history where filed |
| `/admin` | The local ingestion console: preview-then-commit for closure records (College Evaluator URLs or news reports), composite-score years and the IPEDS roster (`/admin/composite`), closure-autopsy figures (`/admin/autopsy`), and record edits (`/admin/edit`) |

Charts are server-rendered. The one client-side script (`app/static/cliff-timeline.js`) is a
progressive enhancement over a no-JS fallback.

## Data

```
primary sources --(scripts/import_*.py)--> data/*.csv --(scripts/build_db.py)--> data/beyondthecliff.db
```

- **`data/*.csv` is the source of truth**, committed to git so every data change is a dated,
  reviewable commit.
- **`data/beyondthecliff.db` is a build artifact.** It is git-ignored and rebuilt from the CSVs
  in about half a second. Never edit it by hand.
- **Importers run only when there is new source data**, never as a routine rebuild. They preview by
  default and write nothing without `--commit`:

  ```
  python3 scripts/import_ipeds_roster.py --commit              # who is open + sector size (IPEDS)
  python3 scripts/import_composite_scores.py --all --commit    # ED financial responsibility scores
  python3 scripts/import_990.py <dir>                          # IRS Form 990 history for a school
  ```

- **`scripts/import_sheeo.py` is a one-time bootstrap, not a rebuild.** It refuses to overwrite
  an enriched `institutions.csv` unless given `--reseed`.

Two rules keep the data intact:

1. **A generated file has one owner: its generator.** Do not hand-edit a CSV an importer rewrites
   whole (`institutions_open.csv`, `sector_size.csv`, `composite_scores.csv`, `financials.csv`,
   `financial_line_items.csv`). Added columns and rows will not survive the next import.
2. **A hand-curated fact gets its own hand-curated CSV**, for example `institution_eins.csv` (the
   OPEID/EIN crosswalk) and `closure_metrics.csv` (the closure-autopsy figures).

Some limits are structural and the app states them where it shows the data:

- Open schools come from the newest IPEDS collection year. "Open" means confirmed open through
  that year, not open today. Closure counts and lists exclude open schools unless asked for.
- ED does not score public institutions, so composite scores cover private nonprofit and
  proprietary schools only. ED rewrote the ratios effective 1 July 2020, so scores on either
  side of that date are never joined into one line.
- Form 990 financial history currently covers two schools: Montreat College and Embry-Riddle
  Aeronautical University.

Tables, sources, and the import traps are documented in
[`docs/technical/DATA_MODEL.md`](docs/technical/DATA_MODEL.md).

## Layout

```
app/          FastAPI app: routes (main.py), admin console (admin.py), queries, server-rendered charts,
              Jinja templates, static assets
scripts/      build_db.py, the importers and enrichers, backup/install, style_lint.py, verify.sh
data/         CSV source of truth (and the git-ignored built DB)
docs/         technical/ (data model, parallel sessions) and standards/ (copy, design, conduct)
```

## Contributing

Before calling work done, run the verification gate over changed files:

```
scripts/verify.sh            # style lint + ruff check + ruff format --check
scripts/verify.sh --tests    # also run pytest, if a suite exists
```

Once per clone, run `scripts/install-hooks.sh` to enable the pre-commit hook in `.githooks/`,
which runs the same checks on staged files and blocks a commit that fails them.

- **Style:** `scripts/style_lint.py` enforces the house style, including no typographic em-dashes
  anywhere. Python is linted and formatted with ruff.
- **Copy:** reader-facing text follows `docs/standards/MARKETING_STYLE_GUIDE.md`. Grim facts are
  reported soberly and sourced, never as a death-watch on the schools.
- **Interface changes:** any new chart, page, or layout change gets three in-browser mockups
  first, and one is chosen before anything is built.
- **Parallel work:** never run two writing sessions in one checkout. Use a git worktree with its
  own `TRACKER_PORT`; see [`docs/technical/PARALLEL_SESSIONS.md`](docs/technical/PARALLEL_SESSIONS.md).

[`CLAUDE.md`](CLAUDE.md) holds the full working agreement.

## License

MIT. See [`LICENSE`](LICENSE).
