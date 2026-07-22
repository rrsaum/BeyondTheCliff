# Data model and pipeline

The closure tracker's data. Source-of-truth is a set of CSVs in `data/`, version-controlled
so every change is a dated, reviewable git commit. A build step turns them into a SQLite
database the app queries. You never hand-edit the database: you edit a CSV and rebuild.

```
uploads/SHEEO_Closed_College_Context.xlsx     (authoritative source, kept local)
        |  scripts/import_sheeo.py  (clean + normalize, one-time / on refresh)
        v
data/*.csv                                     (SOURCE OF TRUTH, committed to git)
        |  scripts/build_db.py      (validate + load)
        v
data/beyondthecliff.db                         (build artifact, git-ignored)
```

## Commands

Run the enrichers in this order (each reads and rewrites data/institutions.csv, so order
matters), then build:

```
python3 scripts/import_sheeo.py            # (re)generate core CSVs from the SHEEO source (2004-2020)
python3 scripts/import_recent_closures.py  # append 2021-2024 closures from IPEDS HD CLOSEDAT
python3 scripts/enrich_ipeds.py            # UnitID crosswalk + enrollment + HBCU/religious + degrees
python3 scripts/enrich_wikidata.py         # founding year + background + history (Wikidata/Wikipedia)
python3 scripts/import_hcm.py              # Heightened Cash Monitoring history (data/hcm.csv)
python3 scripts/import_hs_graduates.py     # NCES high-school-graduate counts (data/hs_graduates.csv)
python3 scripts/import_scorecard.py        # College Scorecard slice for our institutions (data/scorecard.csv)
python3 scripts/import_990.py <dir>        # IRS Form 990 financial history (data/financials.csv)
python3 scripts/build_db.py                # rebuild data/beyondthecliff.db from all data/*.csv
```

`import_scorecard.py` STREAMS the ~2.5 GB College Scorecard raw data (30 yearly MERGED files,
public domain, in `uploads/data/College_Scorecard_Raw_Data_.../`) line by line, keeping only
our institutions and ~13 closure-risk/profile columns into `data/scorecard.csv` (~0.7 MB, the
committed slice). Peak memory ~27 MB, ~30 s: safe on the memory-limited host. **The raw
Scorecard files can be deleted after this runs** (the slice is what the app uses); to
re-import with different columns, re-download the "All Data Files" ZIP from
https://collegescorecard.ed.gov/data/ back into `uploads/data/`.

`import_hs_graduates.py` is independent of the institution pipeline: it parses NCES Digest
tables 219.10 (national) and 219.20 (by state) into the `hs_graduates` table, the demographic
context behind the cliff. It powers the `/cliff` page. All sources here are public-domain
federal data (NCES/IPEDS/ED) or CC0 (Wikidata); Wikipedia extracts (the `history` column) are
CC BY-SA and shown with attribution.

`import_sheeo.py` OVERWRITES institutions/events/characteristics from the source, so the
enrichers must run after it. Each enricher fills its own columns and is safe to rerun.
Downloaded/raw source files (IPEDS, Wikidata, HCM spreadsheets) are cached or read from
`uploads/`, both git-ignored.

`import_sheeo.py` OVERWRITES `institutions.csv`, `events.csv`, and `characteristics.csv`
from the source spreadsheet, so run it only to (re)seed from SHEEO. Day-to-day corrections
and enrichment are hand-edits to the CSVs followed by `build_db.py`. `names.csv`,
`campuses.csv`, and `enrollment.csv` are hand-curated and never overwritten by the importer.

## Source

The spine is the **SHEEO Closed College Context dataset** (State Higher Education Executive
Officers), built from the U.S. Dept. of Education Postsecondary Education Participants System
(PEPS), the National Student Clearinghouse, and FOIA closure reports. 748 institution
closures, 2004 to 2020. Every institution row keeps its `source_url` and `notes` from the
dataset. Attribute SHEEO wherever this data is shown.

The importer cleans the real-world mess: Excel serial-number dates and `M/D/YYYY` strings
both become ISO dates; inconsistent sector strings normalize to `control` + `level` (the
original is preserved in `sector_raw`); 264 blank/partial source rows are dropped; the first
source URL is extracted. Numbers are never originated: absent facts stay NULL.

## Tables

| Table | Grain | Holds |
|---|---|---|
| `institution` | one per OPEID | name, control, level, city, state, status, close year, source |
| `institution_name` | one per past/current name | rename history (find a school by any former name) |
| `campus` | one per campus | multi-campus institutions and campus-level closures |
| `enrollment` | one per (institution, year, source) | headcount time series, best-effort, always sourced |
| `event` | one per lifecycle event | closed / merged / renamed / reopened, with `abrupt` flag and counterpart |
| `characteristic` | one per (institution, tag) | audience/mission + closure tags (e.g. `abrupt_closure`, `merger_involved`, `hbcu`, `religious`) |
| `hcm` | one per (institution, ED snapshot) | Heightened Cash Monitoring history; `level` 1 or 2; the leading distress signal |
| `hs_graduates` | one per (jurisdiction, measure, year) | NCES high-school-graduate counts: the demographic pool behind the cliff. Not linked to institutions |
| `scorecard` | one per (institution, year) | College Scorecard slice: enrolment, admit rate, Pell share, net tuition |
| `composite_score` | one per (institution, award year) | ED Financial Responsibility Composite Score, -1.0 to 3.0 |
| `sector_size` | one per (year, control) | how many institutions are still operating: the denominator |
| `national_series` | one per (series, year) | the US long run: `institutions` and `enrollment` back to 1869 (NCES Digest) and `real_gdp` from 1929 (BEA real GDP, chained 2017 dollars, via FRED `GDPCA`, public domain); `basis` records the counting definition per row. Drives the interactive `/cliff` timeline overlay (`charts.national_timeline` + `static/cliff-timeline.js`, the app's one client-JS chart, progressive-enhancement) |
| `timeline_marker` | one per (series, year) | key policy dates for a national chart (a simpler, currently-unrendered predecessor to `national_turn`) |
| `national_turn` | one per inflection | the "what drove the turns" reading under each national chart: sourced likely cause, category, and an `is_inference` flag |
| `institution_ein` | one per (institution, EIN) | the OPEID -> EIN crosswalk, hand-curated, the join to IRS filings |
| `financial_filing` | one per (institution, tax year, source) | Form 990 revenue, expenses, balance sheet; raw filing facts only |
| `financial_line_item` | one per breakout line | the filing's free-text revenue lines, stored verbatim |
| `closure_metric` | one per (institution, figure) | the closure autopsy's headline numbers (cash, obligations, debt, rescue, headcounts), hand-sourced; drives the "Anatomy of the closure" panel |
| `institution_search` | FTS5 | full-text name search over current + historical names |

The `institution` row also carries enriched columns: `unitid` + `unitid_match` (IPEDS
crosswalk, exact or prefix), `degrees` (highest award, IPEDS), `founding_year` +
`background` + `history` (Wikidata/Wikipedia).

Key is **OPEID** (the federal Office of Postsecondary Education ID, what PEPS/SHEEO use),
stored as text `id` to preserve leading zeros; institutions with no OPEID get a synthetic
`NOID-####`. `unitid` (IPEDS) is a nullable column for a later crosswalk join. Full column
definitions and the CHECK constraints are in `scripts/schema.sql`.

## Financial history (IRS Form 990)

Every private nonprofit college files a Form 990 publicly every year. It is the only financial
record that exists for all of them, on the same form, and it is a U.S. government record, so it
is public domain. `scripts/import_990.py <dir>` reads a folder of filings and writes
`data/financials.csv` and `data/financial_line_items.csv`. `--dry-run` parses without writing;
`--check` runs the cross-check below. Reruns are idempotent per (institution, tax year).

Currently loaded: **Montreat College** (OPEID `00294800`, 13 filings, TY2012 to TY2024, no gaps)
and **Embry-Riddle Aeronautical University** (OPEID `00147900`, EIN `590936101`, 13 filings, TY2012
to TY2024). The Embry-Riddle EIN is the consolidated corporation (all three campuses); the crosswalk
note records that it is mapped to the Daytona Beach roster row, so its figures are the whole
university, not that campus alone.

**Getting the raw XML (no manual clicking).** ProPublica's Nonprofit Explorer hosts the e-file XML,
but its `download-xml?object_id=...` endpoint sits behind a Cloudflare challenge: `curl`/`fetch`
get a 403 "Security Check" page, and the older IRS S3 bucket is gone (404). A real browser
navigation clears the challenge and the endpoint 302-redirects to a 30-minute presigned S3 URL on
`pp-990-xml.s3.amazonaws.com`, which is NOT behind Cloudflare. So the flow is: enumerate a filer's
`object_id`s from its org page, browser-navigate each `download-xml` URL to mint the presigned URL,
then `curl` that URL to disk. The ProPublica API (`/api/v2/organizations/{ein}.json`) returns
aggregate financials directly but not the raw XML or the line items the money chart needs.

Six things here were learned by getting them wrong. Do not undo any of them without a reason:

- **The filing joins through `data/institution_eins.csv`, never a column on an institution CSV.**
  IPEDS publishes no EIN, and `data/institutions_open.csv` is rewritten whole from IPEDS by
  `import_ipeds_roster.py`, so an EIN parked there is erased on the next roster run. That is not
  hypothetical: it happened, and the only symptom was the importer silently matching nothing.
- **An unknown EIN is reported and skipped, never guessed.** Attaching a school's finances to the
  wrong entity is invisible once it is in.
- **A filing is XML whatever it is called.** The IRS ships some as `.txt`; the importer globs both
  and steps over anything that will not parse (the same folders hold audit PDFs). Globbing `*.xml`
  alone silently skipped a real return.
- **Identity comes from the `Filer` element only.** The first EIN and the first business name in
  the document belong to the paid preparer. Montreat's TY2012 filing opens with its accountants.
- **The tags were renamed wholesale after TY2012**, unpredictably (`GrantsAndSimilarAmntsCY` vs
  `CYGrantsAndSimilarPaidAmt`), so `FIELDS` carries both spellings per field. Each filing restates
  its prior year, so `--check` compares filing N's prior-year figures to filing N-1's current-year
  ones. That check validates the mapping ACROSS the rename, and it passes on every field for all
  13 Montreat filings.
- **Line-item labels are stored verbatim, typos included.** Montreat filed "TUITITION AND FEES" in
  TY2012 and TY2013. Matching the correct spelling would have silently dropped its two worst years,
  so the label is matched at query time (`app/queries.py:_LINE_BUCKETS`) and never rewritten.

### Ratios are computed, never stored

`financial_filing` holds only what the filing says. Tuition dependency, operating margin, the
discount rate and the rest are computed in `app/queries.py:financial_series()`, so a definition can
be revised without a reimport and every number on the page traces to one line of one filing.

The four chart bands (`tuition`, `aux_and_other`, `private_giving`, `government_grants`) sum to
`total_revenue` exactly in every filed year, which is the only thing that entitles the page to draw
a stack. Two definitions are deliberate:

- `private_giving` = contributions MINUS government grants, not the filing's "all other
  contributions" line. That line omits federated campaigns, membership dues and fundraising events,
  and using it left up to $539k a year unexplained inside the stack.
- `aux_and_other` absorbs investment income, which goes negative in a bad market year and would
  otherwise invert a band.
- **The earned band handles two filing styles.** A school that itemizes program-service revenue
  (Montreat: separate "TUITION AND FEES" and "AUXILIARY SERVICES" lines) gets the first band from
  the matched tuition line item, labelled "Tuition and fees". A school that reports one combined
  program-service line (Embry-Riddle files a single "HIGHER EDUCATION" line, ~87% of revenue) has
  no line item matching the tuition bucket, so `financial_series` falls back to the aggregate
  `program_svc_revenue` and labels the band "Tuition and program revenue" (`earned_label`). Without
  this, the combined line matched nothing and the whole earned side collapsed to zero, so the chart
  read "$0 tuition, 79% government grants" and the stack no longer summed to total revenue. The
  fallback never asserts a tuition figure the filing did not state: the tuition discount rate
  (`aid_to_tuition`) stays keyed to the itemized tuition line and is correctly blank for a combined
  filer.

### Two traps when reading a 990 against an audited statement

Both were confirmed against Montreat's FY2025 Single Audit, and both will recur for any school:

- **A 990 is one filer; an audit is usually a group.** Montreat's audit consolidates the College,
  the Montreat College Foundation and the Carolina Cyber Center. The 990 is the College alone.
  FY2025 net assets: $64.8M on the return, $68.7M audited. This database understates any school
  running a separate foundation, which is most of them. The fix is to load the foundation's own 990
  under its own EIN, which is why `institution_ein` is not unique on `institution_id`.
- **The 990 reports tuition GROSS with institutional aid as an expense; GAAP reports it net.**
  Montreat FY2025: $42.9M total revenue on the return, $31.0M audited, both correct. Do not compare
  them line by line. The bottom line is the useful check and it agrees (-$0.87M against -$0.77M).
  This is also what makes `aid_to_tuition` a real discount rate: the audit's gross tuition
  ($26,749,295) matches the 990's TUITION AND FEES ($26,285,908) within $463k, and the rates agree
  at 53.2% computed against 53.6% audited. Verified on one school in one year.

### Public institutions: the IPEDS Finance record (`finance_year`)

Public universities do not file a Form 990 (they are governmental instrumentalities), so their
financial record comes from the IPEDS Finance survey (GASB), loaded by
`scripts/import_ipeds_finance.py` into `finance_year` (dollars, ~1,830 public schools, 2003 to
2023). `queries.ipeds_finance_series()` builds the same revenue-against-spending view a 990 gets:
bands are tuition, state and local appropriations, federal, private gifts, and `other` (the
residual to total revenue). The institution page shows it (via `charts.stacked_money(..., gutter=
False)`, education sources in full colour with `other` a receded neutral) only when a school has
NO 990, so private nonprofits keep their 990 record and publics get this one.

Two limits to know. First, **`other` is a single residual**: `finance_year` stores only the named
categories, so `other` lumps auxiliaries, any hospital or health system, sales and services, IP or
patent licensing, publishing, independent operations, and investment return. It varies enormously
by school (Penn State's is mostly its health system; Stanford's FY2021 was $13.5B of endowment
gains) and is labelled a residual, never a specific source. Itemizing it means importing the extra
IPEDS revenue columns, a schema and importer expansion not yet done. Second, **investment return
sits inside `other` and can run negative** for an endowment-rich school (MIT FY2022 was about
-$1.6B), which a stacked area cannot draw cleanly; the current gate to public institutions avoids
the worst of it, but breaking investment out as its own signed band is part of the same expansion.

## Maintenance playbook

- **Correct a fact:** edit the cell in the relevant `data/*.csv`, run `build_db.py`. The
  git diff is the audit trail; write a real commit message.
- **Add a closure by hand:** add a row to `institutions.csv` (set `status` = `closed`,
  `status_year`) and a matching `closed` row in `events.csv`. Use the real OPEID as `id`.
- **Record a merger:** on the closing school set `status` = `merged`; add an `event` of type
  `merged_into` with `counterpart_institution_id` = the survivor's `id` (add the survivor as
  an `open` institution if it is not already present).
- **Record a name change:** add both names to `names.csv` with year ranges, and a `renamed`
  event. FTS search will then find the school under either name after a rebuild.
- **Record a campus closure:** add the campus to `campuses.csv` with a `closed_year`; the
  institution stays `open`.
- **Add enrollment:** append rows to `enrollment.csv` with the `source` and `source_url`.
  Never enter a number you cannot cite. For pre-1985 schools the productive sources are the
  federal "Education Directory, Colleges and Universities" and the HEGIS "Fall Enrollment"
  institutional volumes, both digitized on archive.org (a directory dated N/N+1 reports fall
  N-1). Record the exact measurement in `source` (fall headcount vs FTE vs cumulative), and
  DISAMBIGUATE by FICE/OPEID: multiple colleges can share a city (Yankton College is FICE
  003476; Mount Marty in the same city is 003465).
- **Add closure-autopsy figures:** append rows to `data/closure_metrics.csv`, one per figure
  (`cash_on_hand`, `near_term_obligations`, `debt_prior_year`, `projected_deficit`,
  `rescue_needed`, `rescue_raised`, `endowment`, `employees`, `students_displaced`,
  `closure_warning_days`), each with its `unit`, `as_of_year`, and `source_url`; a figure with
  no number carries a sourced word in `qualitative` (e.g. `depleted`). Then `build_db.py`. These
  drive the "Anatomy of the closure" panel; see the closure-autopsy note below.

## The closure autopsy (`closure_metric`, and the two panels)

Each closed institution's page leads with two server-rendered panels, both templates driven by
data, not by a one-off per school:

- **"The evolution"** (`charts.enrollment_evolution`): enrollment as one line, solid across
  consecutive sourced years and dashed where it interpolates across a gap, with dots at every
  measured year, the peak marked, and the closing point in the closed colour. Fed by the
  `enrollment` table, so it renders for any school; lifecycle events stay in the timeline, so each
  fact appears once.
- **"Anatomy of the closure"** (`charts.anatomy` from `queries.closure_anatomy`): three
  diagnostic layers (liquidity, solvency, rescue gap) plus a human-toll strip, from the
  `closure_metric` figures. Like the financial layer, only raw sourced figures are stored; the
  readings (the runway ratio, the rescue gap) are COMPUTED in `queries.py`. The sign-and-colour
  convention is financial and deliberate: money OWED or LOST is a negative shown in red (payroll
  owed, debt, the projected loss); money HELD or the rescue target is positive and neutral; red is
  otherwise reserved for the fatal readings and the verdicts. For a Form-990 school these figures
  can instead derive from `financial_filing`.

`data/closure_metrics.csv` is hand-curated and, like `data/institution_eins.csv`, is deliberately
its own file (never a column on a generated roster), so a re-generated IPEDS file can never erase it.

## Browser ingestion console (`/admin`)

The everyday way to add College Evaluator closures, with no terminal or file editing. Paste
"closing information" URLs at `/admin`, review the parsed preview, and click Approve; the app
appends the rows to the CSVs and rebuilds the database in-process.

- `app/ce_ingest.py` fetches each page (cached in `data/ce_cache/`, git-ignored; `urllib` with
  a `curl` fallback), parses the two page shapes (a horizontal campus table, or a vertical
  key/value block), and drafts rows. `app/ipeds_index.py` resolves name + state (+ city) to a
  federal OPEID from the cached IPEDS HD files, so recent closures inherit a Scorecard profile.
- Classification mirrors the rest of the pipeline: a surviving parent ("N campuses still
  active", or a "Parent Institute" single page) yields one `campus` row per closed location; a
  dead parent yields one `institutional` row plus `campuses.csv` locations. Same city + same
  year is collapsed; a different year in the same city is kept as a distinct closure.
- Honesty gates never write a guess: a name that resolves to an OPEID IPEDS still lists as
  **open** is held for review (not added); a school with no OPEID match gets a blank
  control/level rather than an invented one; a missing date leaves `status_year` blank. Held
  and already-tracked rows are reported but not written.
- Dedup keys (OPEID, and name + state) make re-running a batch a no-op. The git diff of the
  CSVs is the audit trail, exactly as with a hand edit.
- The form reads **College Evaluator URLs only** (`collegeevaluator.com/...`): a non-CE link
  (a Wikipedia page, or a comma-split fragment) is flagged and never fetched or parsed, since the
  parser only understands the two CE page shapes. The append is keyed off the CSV's live header,
  not a fixed field list (other tools widen these files with `parent_survives` / `motto` /
  `logo_url`), and writes through a temp file then renames, so it preserves every existing column
  and can never truncate the source on error.

The same page also has a **news / announced closure form** (`app/news_ingest.py`) for closures
federal data has not captured: an announced (upcoming) closure, or a program closure. A news
article is prose, so the human supplies the facts (name, state, year, type) and the article URL
as the citation; the app only enriches from IPEDS (OPEID, city, sector), dedups, and writes. It
never originates a school fact.

- `status` gains a fourth value, `announced` (the closure is planned but has not happened; the
  school is still operating). `closure_type` gains a third value, `program` (a program ended
  while the institution stays open, a leading indicator of decline). Both are enum-checked in
  `scripts/schema.sql`.
- A campus keys to its own federal OPEID (resolved by matching the parent name plus the branch
  name in IPEDS, e.g. "Pennsylvania State University" + "DuBois"). A program has no OPEID of its
  own, so it takes a MAN id and borrows its parent's location for context; `parent_name` holds
  the surviving institution.
- The completed-closure charts filter `status = 'closed'`, so announced schools never inflate
  "closures by year." The map legend and the per-institution banners distinguish announced,
  campus, and program from a full institutional closure.

`status` also has a fifth value, `at_risk`: a financially distressed but still-operating school
(a watchlist entry, not a closure), carried with no `closure_type` and a sourced note. These are
excluded from the closure charts and shown with their own pill and banner.

The news form also records **mergers** (`status = merged`): the disappearing school is the row,
and the acquiring / surviving institution goes in `parent_name` (the form's "acquiring institution"
field). The detail page shows "merged into or was absorbed by <parent>", linked to the parent
filter. This gives the survivor a consistent home; earlier merged rows left it blank or buried it
in `notes`.

**Editing existing records** (`app/edit_record.py`, `/admin/edit?id=<id>`, plus an Edit link on
every institution page): change a row's status, year, closure type, cause, or any descriptive
field in the browser, most often to reclassify an `announced` closure to `closed` once its date
passes, or to code a cause. The row is located by id in whichever source CSV holds it, the edit
is validated against the schema enums, the file is rewritten, and the DB rebuilt. The git diff is
the audit trail.

**Closure-autopsy queue** (`app/autopsy_queue.py`, `/admin/autopsy`, `data/autopsy_queue.csv`):
a browser-managed worklist of closed schools to profile, mostly historical colleges with a
Wikipedia article. Paste one school per line; a bare URL derives its name from the last path
segment (`/wiki/William_%26_Vashti_College` becomes "William & Vashti College"), or prefix a line
with `Name https://url` to set the name explicitly. Duplicate names are skipped with feedback. The
queue only **collects** pointers: the profiling itself (reading each source, verifying every fact)
is done by hand into `data/manual_closures.csv` as `MAN-####` rows, deduped by name + state, so no
founding year, closure year, or cause is ever machine-guessed out of prose. `autopsy_queue.csv` is
git-ignored (a local worklist); the resulting closure rows in `manual_closures.csv` are the
committed, sourced output. Wikipedia is cited as the source and attributed CC BY-SA.

**Cause of failure** (`cause`, enum-checked, nullable): the tracker is a post-mortem, so each
closure carries a primary sourced cause from a fixed taxonomy: financial, enrollment,
accreditation, sponsor, misconduct, disaster, restructuring, external, benefactor. NULL means
"not yet coded", never "no cause" - we do not originate a cause. `scripts/backfill_cause.py`
codes causes conservatively from a row's own sourced `notes` (phrase matches), leaving blank
where the note does not say why; most rows stay blank because bare federal records (IPEDS/PEPS/
Hechinger) state no cause. New closures pick a cause in the browser form, and any row can be
coded in the edit panel. The index shows a "closures by cause" chart and a cause filter.

`scripts/enrich_cause_wikipedia.py` codes causes from each closure's Wikipedia article, tuned
hard for precision over recall: it reads only the sentences that discuss the closure, and codes a
cause only from an explicit causal clause ("closed due to / citing X") or an unambiguous distress
phrase, restricted to the three causes Wikipedia states cleanly (financial, enrollment,
accreditation). The rarer causes (war, fire, fraud, a religious order, a state consolidation)
appear too often as founding or historical background to code safely, so they are left for hand
coding. It attributes each coded cause to Wikipedia (CC BY-SA) in the row's notes and writes a
review file first. Real ceiling: most tracked closures are small for-profit or branch schools
with no Wikipedia article, so this covers only the notable degree-granting closures. The dominant
coded causes are financial, then enrollment, then accreditation.

## Historical closures and the cliff-chart floor

The tracker is a cross-era failure post-mortem, so it also carries older closures federal data
never captured, from authoritative state sources: `scripts/import_state_lists.py` adds the New
Jersey and Michigan state closed-college lists (reaching back to the 1930s), each sourced. These
predate IPEDS, so they are MAN-#### rows with no OPEID, control, level, or cause (blank, not
guessed). To keep them from distorting the modern cliff view, the index's "closures by year /
control / state" charts apply a `min_year` floor of 2004 (see `_filters`); historical rows stay
in the searchable table and totals but out of the modern charts.

`scripts/import_lostcolleges.py` adds the Lost Colleges archive (lostcolleges.com) historical
defunct colleges we do not already track (388 rows), from the rendered by-state HTML saved at
`uploads/data/lostcolleges.html` (git-ignored). The page is a Wix app whose per-college pages are
JavaScript-rendered, so curl gets only the shell; but the by-state INDEX, once rendered, has
UPPERCASE bold state headers and clean college links, which the importer segments by walking the
document. Each row is a MAN-#### id, status=closed, with blank year / cause / control / level
(deep-linked to its per-college page); blank year keeps them below the 2004 chart floor. Causes
for the historical layer are not in the index; `scripts/enrich_cause_wikipedia.py` now includes
historical rows in its target set, so an overnight run codes causes for those with a Wikipedia
article.

## IPEDS enrichment (scripts/enrich_ipeds.py)

Pulls NCES IPEDS files (cached in `data/ipeds_cache/`, git-ignored) and adds:

- **OPEID -> UnitID crosswalk**, unioned across HD directory files 2004 to 2020. Matches
  **522 of 748 (69%)** of our institutions. A single year covers only ~48%, because a school
  closed far from that year is not in the snapshot; the union lifts it. The unmatched ~31%
  are mostly branch OPEIDs and pre-2004 records; matching on the 6-digit OPEID prefix could
  raise it but risks wrong branch matches, so it is deferred.
- **Enrollment** from EFFY (12-month headcount): total / undergraduate / graduate per
  institution per year. **3,823 rows across 490 institutions**, each sourced to its EFFY file.
  Closed schools show real pre-closure decline (a validation signal, not an artifact).
- **HBCU** (from HD) and **religious yes/no** (from IC, field RELAFFIL) as characteristic tags.
- **Closure type** (`closure_type`): every closed institution is classified `institutional`
  or `campus`. The rule uses the OPEID's 6+2 structure (6-digit institution + 2-digit
  location): if the parent OPEID (`prefix + "00"`) is still open in IPEDS, this is a campus
  closure and the institution lives on (`parent_name` records the survivor); otherwise it is
  an institutional closure. Of the closures, 559 are institutional and 327 are campus, so
  ~37% of raw "closures" are branch closures, not schools dying. The distinction drives the
  index breakdown, the closure-type filter, the table badge, and the detail-page banner.

## Wikidata / Wikipedia and HCM enrichment

- **Founding year, background, history** come from Wikidata (inception, description) and
  Wikipedia (intro extract), matched conservatively by normalized name + state. Coverage is
  partial by design (~43 founding years of 748): our set is dominated by defunct for-profit
  branches that are not in Wikidata. A missing value is honest; a wrong one is not, so
  unmatched rows stay NULL.
- **Heightened Cash Monitoring** (`scripts/import_hcm.py`) reads the quarterly ED snapshots
  (2015 to 2026, `.xls` via xlrd and `.xlsx`) and records every snapshot our institutions
  appear in. 111 of our closures were ever on HCM; **110 were on HCM at or before their
  closure year**, the clearest leading distress signal in the data.

## Known gaps and next enrichment

- **Founding year coverage is limited by Wikidata** (defunct for-profit branches are absent).
  Manual entry or a fuzzier match could raise it. Denomination names for religious schools
  still need the IPEDS value-label dictionary.
- **Religious denomination names.** We record religious yes/no; mapping the IPEDS RELAFFIL
  code to a denomination name needs the IPEDS value-label dictionary and is deferred (a code
  guessed from memory would be a fabricated fact).
- **Branch-level rows.** SHEEO is OPEID/branch-level, so chains (e.g. Corinthian/Altierus)
  appear as many rows. Grouping under a parent uses the OPEID's leading 6 digits; deferred.
- **Coverage is 2004 to 2024** (SHEEO 2004-2020 + IPEDS HD 2021-2024). Pre-2004 and 2025+
  closures are not in the federal feeds yet.
- **Campus closures without a separate OPEID are invisible to federal data.** A multi-campus
  institution (e.g. American National University) can close a physical location that was an
  "additional location" under an existing OPEID; IPEDS/SHEEO/PEPS never record it as its own
  closure. These, plus 2025-2026 closures not yet in IPEDS, go in `data/manual_closures.csv`:
  hand-curated, news-sourced institution rows (same columns as `institutions.csv`, loaded
  into the `institution` table by `build_db.py`) with a synthetic `MAN-####` id, no OPEID, a
  `closure_type` and `parent_name`, and a `source_url`. This is the only place a fact is
  entered by hand, and each carries its citation.
- **State closure-policy data.** `uploads/CC_State_authorization_longitudinal_dataset.xlsx`
  (teach-out laws, record retention, surety bonds by state/year) is a separate future table
  (`state_policy`) for the resilience/policy analysis, not part of the institution core.
