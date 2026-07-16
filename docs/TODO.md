# TODO and open items

Deferred, optional, or follow-up items as of the tracker build. Nothing here blocks the app;
these are enrichment, data-quality, and coverage items plus a few operational notes. Verify state
with `scripts/verify.sh` before marking anything done.

## Cause enrichment (surfacing why each institution failed)

- **Run the Wikipedia cause pass to completion.** `scripts/enrich_cause_wikipedia.py` is built and
  validated but only partially run (it is a slow, roughly 2-hour sequential-fetch job, best run
  overnight on the host). Its target set now includes the historical rows (~2,069 targets). A full
  run would raise coverage above the current ~130 coded causes. It writes a review file first and
  only codes financial / enrollment / accreditation from explicit causal phrasing.
- **Per-college Lost Colleges causes.** lostcolleges.com per-college pages state causes the
  by-state index does not, but they are JavaScript-rendered (Wix), so curl gets only the shell.
  To code those precisely, paste a per-college page (as the index was pasted) or find a
  machine-readable export. The site also has a "Causes for Closure" taxonomy page worth comparing
  against our cause enum.
- **Cause coverage is ~130 of ~3,378 (roughly 4 percent).** Most historical and tiny for-profit
  closures have no usable Wikipedia article, so coverage is capped by source availability, not
  effort. The coded set skews to notable degree-granting closures; the cross-era pattern is
  financial > enrollment > accreditation.

## Data quality and corrections

- **Reclassify announced records to closed as their dates pass.** Example: Hampshire College is
  `announced` (closes after fall 2026); flip to `closed` once that term ends. Use the edit panel
  (`/admin/edit?id=...`).
- **Antioch College** is recorded as closed (its 2008 closure) but it reopened in 2011 and is
  operating. Its `status` likely needs review/correction.
- **Historical closure_type defaults.** Lost Colleges rows default to `closure_type=institutional`,
  but some are really program/department closures (for example "Northwestern University Dental
  School", "Medical Department, University of Oregon", "New York College of Dentistry"). Reclassify
  as `program` where appropriate.
- **Acronym casing from sources.** A few names come through title-cased from their source (for
  example "Cbm Education Center" should read "CBM"). Cosmetic; fix via the edit panel.
- **Missing OPEIDs on ambiguous matches.** Some records got a MAN id instead of an OPEID because
  the name matched more than one IPEDS entity (for example Evangel University, which has a separate
  online-college entity). These have no Scorecard profile; attach the correct OPEID by hand if
  wanted.
- **Possible dedup false-positives.** The tiered name matcher can over-match on a single shared
  token (for example historical "Birmingham College" against modern "Birmingham-Southern"), which
  can slightly understate genuinely-missing historical colleges. Spot-check when adding sources.

## Coverage (which institutions failed)

- **More authoritative state closed-college lists** are the feasible path to historical coverage
  (they render as static HTML, unlike Lost Colleges' JS pages). NJ and MI are in; others exist.
- **Sources that could not be mined this round:** New Hampshire (HTTP 403), Higher Ed Dive
  (interactive tracker, no static list), College History Garden (per-state blog pages). Revisit if
  a machine-readable form is available.
- **Program closures** as a leading indicator: keep adding these (a program ends while the school
  survives) via the news form; only one is in so far (U of Illinois Institute of Aviation).
- **At-risk watchlist** (8 institutions) can grow from new financial-distress sources. Remaining
  SFSTL / St. Louis Fed file candidates were mostly Forbes-only (copyrighted, not citable) or
  large stable publics; each new candidate needs a public-source verification before adding, and
  Forbes scores must not be stored.

## Features and UI (optional)

- **A dedicated historical view/filter.** Historical rows are kept out of the modern charts by the
  2004 `min_year` floor and remain in the table/search, but there is no explicit "historical" era
  filter or badge yet.
- **A distress-signal layer** (like the existing HCM layer) sourced to the public DOE Financial
  Responsibility Score dataset could formalize at-risk detection beyond hand-entry.
- **Brand and marketing pages** named in CLAUDE.md are not built (the tracker ships as the feature;
  the umbrella brand pages, positioning, funnel entry points are TBD).

## Financial layer (IRS Form 990)

`scripts/import_990.py` ingests a folder of 990 XML filings into `data/financials.csv` and
`data/financial_line_items.csv`; the tables are `financial_filing` and `financial_line_item`.
Ratios are computed in `app/queries.py:financial_series()` and never stored. Currently loaded:
Montreat College only (OPEID 00294800, TY2012-TY2024, 11 filings).

- **A browser ingestion console for 990s is not built.** Filings are imported from the terminal
  today, which does not match the browser-only workflow the `/admin` console exists to serve.
  The `ce_ingest` drop-preview-approve pattern is the model to follow.
- **A filing joins through `data/institution_eins.csv`, and only Montreat is in it.** Adding a
  school means adding its OPEID/EIN pairing there first, with a source; the importer refuses to
  guess which school an unmatched EIN belongs to and reports it instead. Backfilling EINs across
  the closed institutions is the unlock for comparing the schools that closed against the ones
  that did not.
- **Do not put an EIN on an institution CSV.** It was on `institutions_open.csv` briefly and was
  destroyed within the hour: `scripts/import_ipeds_roster.py` rewrites that file whole from
  IPEDS, and IPEDS does not publish EINs, so anything hand-added there is erased on the next
  roster run. The crosswalk is a separate table (`institution_ein`) for exactly that reason.
- **What the government grants actually were is unverified.** Montreat's filings report government
  grants of $18.6M / $17.7M / $9.0M in TY2021-TY2023 against roughly $200k in typical prior years.
  The size and timing are consistent with federal pandemic relief, but the 990 says only
  "government grants" and no primary source has been read. Do not name a programme in copy until
  one is. Schedule A or the audited statements would settle it.
- **The tuition figure's basis is unknown.** `aid_to_tuition` divides institutional aid by the
  reported tuition line, but the 990 does not state whether that tuition is gross or net of aid,
  so it is not a published discount rate and is not labelled as one. Confirm against an audited
  statement before ever calling it one.
- **Line-item labels are matched on substrings** (`app/queries.py:_LINE_BUCKETS`) because schools
  write their own. Montreat filed "TUITITION AND FEES" in TY2012 and TY2013 and "TUITION AND FEES"
  from TY2014, which is why the description is stored verbatim and matched at query time. Expect
  new spellings with every new school, and widen the bucket rather than editing the stored text.
- **No filings for TY2019 or TY2020** (fiscal years ending June 2020 and June 2021), the COVID
  window. Charts break across the gap rather than joining over it. Worth chasing: those are the
  two years the sector's story turns on.

## Data quality: flagged, not yet fixed

- **`Montreat College - North Carolina Wesleyan College` conflates two schools.** Rows `00294818`
  (Rocky Mount) and `00294819` (Durham) in `data/institutions.csv` carry that name with
  `unitid=199032`, which is Montreat's UnitID, and `unitid_match=prefix`. North Carolina Wesleyan
  is a separate institution that is still open (OPEID `00295100`, UnitID `199209`, per
  `data/ipeds_cache/_name_index.json`). These are Montreat's own branch campuses, closed 2017. The
  name string's provenance is unknown, so it was left alone rather than rewritten.
- **`style_lint.py` does not catch `&mdash;`.** The em-dash rule is total, but the linter matches
  the literal U+2014 character, not the HTML entity, which renders identically to a reader.
  `app/templates/institution.html:28` has one. Either widen the linter or fix the template.
- **The repo has no ruff config.** With no `pyproject.toml`, `ruff format` defaults to an 88
  character line and would reformat essentially every file away from the ~100 character style the
  code actually uses. `ruff check` passes clean. Pin `line-length` before anyone runs
  `ruff format`, or the first person to run it produces a repo-wide diff.

## Operations and repository

- **Merge `tracker-build` into `main`** (or keep on the branch for review), and set up a remote /
  push if one is wanted.
- **Server persistence.** The dev server does not stay up on its own between sessions. A macOS
  LaunchAgent auto-start was offered and deferred until production; set it up when deploying.
- **Scorecard raw data** (`uploads/data/College_Scorecard_Raw_Data_...`, ~3.7 GB, git-ignored) is
  only needed to re-run `scripts/import_scorecard.py`. It can be deleted to reclaim space if a
  re-run is not planned; `data/scorecard.csv` (the derived, committed output) is what the app uses.
- **IPEDS enrichment gaps** noted in CLAUDE.md: founding year and enrollment enrichment, and
  coverage beyond the current window, remain partial.
