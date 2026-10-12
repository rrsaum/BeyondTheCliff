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
- **Backfill sourced closure years into nine blank-year rows (from the 2026-07-22 autopsy pass).**
  These already-tracked rows have a blank `status_year` that the Wikipedia read now sources; edit
  each via `/admin/edit?id=...` after re-confirming the source: `MAN-0545` Alabama Presbyterian
  (1923), `MAN-0657` Leander Clark (1919), `MAN-0655` Humboldt (1916), `MAN-0809` Scio (1911),
  `MAN-0795` Red River Valley (1905), `MAN-0835` Penn College of Dental Surgery (1909), `MAN-0904`
  Blair Business College (1933), `MAN-0851` American Temperance University (1908), `MAN-0804`
  Nelson Business College (1930).
- **Reconcile one closure-year discrepancy.** `MAN-1463` Lake Charles College records 1902, but
  its Wikipedia article says the school closed in 1899. One source is wrong; the existing row's
  provenance is unknown, so it was not overwritten. Check a primary source before editing.

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
Montreat College only (OPEID 00294800, TY2012-TY2024, 13 filings, no gaps). The reader-facing
chart is `charts.stacked_money()`, chosen from mockups. Full detail and the traps:
`docs/technical/DATA_MODEL.md`.

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
- **What the big government grants actually were is STILL unverified.** Montreat's filings report
  government grants of $5.4M / $18.6M / $17.7M / $9.0M in FY2021-FY2024 against roughly $200k in
  typical prior years, $56.0M across the 13 filed years. The size and timing are consistent with
  federal pandemic relief, but the 990 says only "government grants". The FY2025 Single Audit in
  the source folder does NOT settle it: it covers FY2025 and FY2024 only, and its Schedule of
  Expenditures of Federal Awards is a different measure again (see below). The FY2022 and FY2023
  Single Audits would settle it. Until one is read, do not name a programme in copy.
- **A Single Audit's federal total is not the 990's government grants, and must never be compared
  to it.** Montreat's FY2025 SEFA totals $10,880,495, but $10,512,168 of that is the Student
  Financial Assistance Cluster: $8.2M of Direct Loans and $2.2M of Pell, which are aid to students
  passing through the school, not revenue to it. The 990's government grants line for the same
  year is $1,982,924. Two different questions, two different numbers, both correct.
- **`aid_to_tuition` is the tuition discount rate, and this is now sourced.** Settled against
  Montreat's audited FY2025 statement, which reports tuition "net of discounts and scholarships of
  $14,332,372" as $12,416,923. Gross is therefore $26,749,295 against the 990's TUITION AND FEES of
  $26,285,908: the 990 line is gross, within $463k, and nowhere near the net figure. Rates agree,
  53.2% computed against 53.6% audited. Verified on ONE school in ONE year: a school that reports
  tuition net would make the ratio meaningless and nothing in its filing would say so.

## The 990 is one entity; the audited statements are three

Montreat's audited financials are CONSOLIDATED: Montreat College, Montreat College Foundation, and
Carolina Cyber Center. The 990 loaded here (EIN 560543261) is the College alone. For FY2025 the gap
is modest but real, and it is not a rounding difference:

| Figure, FY ending 30 June 2025 | 990 (College) | Audit (consolidated) |
|---|---|---|
| Net assets | $64,793,216 | $68,702,500 |
| Government grants | $1,982,924 | $1,982,924 (exact match) |
| Government grants, FY2024 | $8,953,918 | $11,498,680 |
| Result | -$871,466 | -$766,240 |

The FY2024 government-grant gap of $2.5M is the clue: the Cyber Center draws federal cybersecurity
grants (the FY2025 SEFA lists DoD awards under Assistance Listing 12.902 and 12.905) that never
touch the College's own return. So this database understates the institution wherever a school
runs a separate foundation or subsidiary, which most of them do. Two consequences:

- **Never call a 990 figure "the school's finances" without checking whether a foundation exists.**
  A tuition-dependent college with a large foundation will look far weaker on its 990 than it is.
- The fix, if this matters later, is to load the foundation's own 990 under its own EIN and sum
  them, which is exactly what `institution_ein` allows: it is deliberately not unique on
  institution_id.

Note also that the two bases are not comparable line by line. The 990 reports tuition gross with
institutional aid as an expense; GAAP reports tuition net of it. Montreat's FY2025 revenue is
$42.9M on the 990 and $31.0M audited, and both are right. The bottom line agrees (-$0.87M against
-$0.77M), which is the useful check.
- **Line-item labels are matched on substrings** (`app/queries.py:_LINE_BUCKETS`) because schools
  write their own. Montreat filed "TUITITION AND FEES" in TY2012 and TY2013 and "TUITION AND FEES"
  from TY2014, which is why the description is stored verbatim and matched at query time. Expect
  new spellings with every new school, and widen the bucket rather than editing the stored text.
- **Montreat's record is complete: 13 filings, TY2012 to TY2024, no gaps.** The TY2019 and TY2020
  returns (the COVID window) were added late and the prior-year cross-check now agrees end to end
  across the whole unbroken chain, which is a stronger validation than either side of a hole. The
  chart still breaks across a missing year by design; there just is not one any more.

## National context layer (NCES Digest)

Added October 2026 from a review of the author's `github.com/rrsaum/Data` HigherEd CSVs, re-pulled
from the current Digest editions: `national_closure` (Table 317.50), `national_series` by control
(303.10, 317.10), and `population_18_24` (101.10). The /cliff "private nonprofit picture" section
draws on the first two. See `docs/technical/DATA_MODEL.md`.

- **Look at the /cliff private nonprofit section on screen.** It was checked through its HTML and
  approved, but never screenshotted: no browser could run on the host (headless Chromium needs
  `libatk1.0-0`). In particular confirm the decade-bar end labels sit inside the frame; their room
  was sized from a character-width estimate, not a measurement.
- **Test the "sorting" reading before it becomes a claim.** The section's closing line is labelled
  as our reading, not an NCES finding: average private nonprofit enrollment per college rose from
  1,507 (1976) to 2,546 (2022), but averages cannot show whether students concentrated in fewer,
  larger schools. The per-school IPEDS enrollment in `data/enrollment.csv` can test it. If it
  holds, the line can drop its hedge; if not, rewrite it.
- **Chart the college-age population.** `population_18_24` (1970 to 2022, thousands) is stored but
  not drawn anywhere. Any chart goes through the three-mockup gate first.
- **Add US live births (1970 onward).** Digest Table 101.10, already parsed for the population
  series, also carries live births per year: the leading indicator of the cliff, 18 years ahead.
  Store as a `national_series` row set; exclude any row the table footnotes as a projection.
- **Explain the 1920s in "What drove the turns".** Colleges grew about 3.1%/yr from 1919 to 1929
  (1,041 to 1,409, Digest 301.20) and no `national_turns` row covers that decade. A row needs a
  sourced likely cause, flagged `is_inference` where it is one.
- **The 15 to 29 decennial population back to 1870 is not imported.** The author's
  `InstCollegePopGrowth.csv` has it, but it is not the conventional college-age band and its values
  were not verified against a primary Census table. Import only if that source is found.
- **Rejected from the key-events list (do not re-add without new evidence):** the Smith-Hughes Act
  of 1917 funds vocational teachers, not colleges (39 Stat. 929), and the college count shows no
  turn at 1917; the Great Depression and 9/11 coincide with continued growth in the stored series.
  The other six events were already `national_turns` rows.
- **The two new chart renderers repeat axis plumbing.** `charts.indexed_lines` and
  `charts.emphasis_bars` hand-roll their grid, axis labels, and scales, as `line`, `series_lines`,
  `small_multiples`, and `enrollment_evolution` each already do. A shared `_y_grid` / scale helper
  would let a fix land once instead of in six places. Not urgent; touches every SVG chart.
- **`/cliff` opens about 21 SQLite connections per request**, one per query helper, and reads the
  `institutions` and `enrollment` series three times each. Measured at about 1 ms of overhead in
  total, so not worth fixing at this data size; revisit if the page grows or slows.

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
- **Adopting `ruff format` repo-wide is still undecided.** `ruff.toml` records why: it would rewrite
  about 2,886 hand-aligned lines. Until it is decided, format only new code; never run it on a
  whole existing file.
