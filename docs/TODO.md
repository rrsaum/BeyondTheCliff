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
