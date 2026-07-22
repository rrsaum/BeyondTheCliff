-- Beyond the Cliff: closure and consolidation database (SQLite, portable SQL).
-- Built from the CSVs in data/ by scripts/build_db.py. The CSVs are generated from the
-- SHEEO closed-college dataset by scripts/import_sheeo.py, then hand-curated. Never
-- hand-edit the .db; edit a CSV and rebuild.
--
-- "Closure" is not a single field: an institution has a lifecycle (founded, renamed,
-- merged, closed, reopened) and relationships to other institutions, so the terminal
-- facts live in the event table, not a column.
--
-- Keyed on OPEID (the U.S. Dept. of Education Office of Postsecondary Education ID), which
-- is what the authoritative closure data (PEPS / SHEEO / NSC) uses. IPEDS UnitID is a
-- later enrichment join (nullable unitid column). Portable to PostgreSQL apart from the
-- FTS5 search table at the bottom.

PRAGMA foreign_keys = ON;

-- One row per institution (per OPEID). id is the OPEID as text (preserves leading zeros);
-- institutions with no OPEID get a synthetic 'NOID-####' id so a key always exists.
CREATE TABLE institution (
  id                    TEXT PRIMARY KEY,       -- OPEID, or 'NOID-####'
  opeid                 TEXT,                   -- federal OPE ID (equals id when present)
  unitid                INTEGER,                -- IPEDS UnitID, from the crosswalk
  unitid_match          TEXT CHECK (unitid_match IN ('exact','prefix')),  -- crosswalk confidence
  name                  TEXT NOT NULL,
  control               TEXT CHECK (control IN ('public','private_nonprofit','private_forprofit')),
  level                 TEXT CHECK (level IN ('4yr','2yr','lt2yr')),
  sector_raw            TEXT,                   -- original SHEEO sector string, preserved as-is
  religious_affiliation TEXT,                   -- NULL if secular / unknown
  founding_year         INTEGER,                -- from Wikidata (not in IPEDS); NULL if unmatched
  degrees               TEXT,                   -- highest award offered, from IPEDS HD (HLOFFER)
  background            TEXT,                   -- one-line descriptor, from Wikidata
  history               TEXT,                   -- intro/history extract, from Wikipedia
  city                  TEXT,
  state                 TEXT,                   -- 2-letter USPS code
  status                TEXT NOT NULL CHECK (status IN ('open','closed','merged','announced','at_risk')),
  status_year           INTEGER,                -- year of the terminal (or announced/flag) event.
                                                -- For an 'open' row there is no such event, so it
                                                -- carries the last year we hold positive evidence
                                                -- the school was operating (e.g. it filed an audit
                                                -- for that composite-score award year). Read it as
                                                -- "confirmed open through", never as "open today".
  closure_type          TEXT CHECK (closure_type IN ('institutional','campus','program')),  -- for closed/announced rows
                                                -- 'campus' is decided by the OPEID: an 8-digit
                                                -- OPEID is campus-level, so any suffix other
                                                -- than '00' is a branch, never a college in its
                                                -- own right. Counting branches as institutional
                                                -- closures once put every ITT Tech location on
                                                -- the map as a separate school dying.
  parent_name           TEXT,                   -- for a campus/program closure: the parent institution
  parent_survives       INTEGER,                -- campus rows only: 1 = the parent institution is
                                                -- still open, 0 = it closed or merged too, NULL =
                                                -- not applicable/unknown. A campus closure is not
                                                -- proof the school survived: most of ours are
                                                -- branches of chains that died outright, so no
                                                -- page may claim "the parent remains open"
                                                -- without checking this.
  cause                 TEXT CHECK (cause IN (   -- primary sourced cause of failure; NULL = not coded
                          'financial','enrollment','accreditation','sponsor','misconduct',
                          'disaster','restructuring','external','benefactor')),
  notes                 TEXT,
  source_url            TEXT,
  motto                 TEXT,                   -- the school's motto, verbatim (with a translation
                                                -- in the same cell when it is Latin), sourced
  logo_url              TEXT                    -- URL of a logo/seal ONLY when it is verifiably
                                                -- public domain or CC (the open-license rule);
                                                -- trademarked logos are left NULL by design
);

-- Name history: schools rename, sometimes repeatedly. end_year NULL = current name.
CREATE TABLE institution_name (
  institution_id  TEXT NOT NULL REFERENCES institution(id),
  name            TEXT NOT NULL,
  start_year      INTEGER,
  end_year        INTEGER,
  source_url      TEXT
);

-- Campuses: an institution can have many, and a campus can close while the institution
-- lives on. closed_year NULL = still open. (SHEEO is OPEID/branch-level, so chain
-- grouping via the OPEID parent prefix is a later enrichment.)
CREATE TABLE campus (
  institution_id  TEXT NOT NULL REFERENCES institution(id),
  name            TEXT NOT NULL,
  city            TEXT,
  state           TEXT,
  opened_year     INTEGER,
  closed_year     INTEGER,
  is_main         INTEGER DEFAULT 0,
  source_url      TEXT
);

-- Enrollment time series, best-effort. Not in SHEEO; enriched from IPEDS/news later.
-- Every row carries its source, because coverage is uneven.
CREATE TABLE enrollment (
  institution_id   TEXT NOT NULL REFERENCES institution(id),
  year             INTEGER NOT NULL,
  total_headcount  INTEGER,
  undergrad        INTEGER,
  graduate         INTEGER,
  fte              INTEGER,
  source           TEXT,
  source_url       TEXT,
  UNIQUE (institution_id, year, source)
);

-- The lifecycle: closures, mergers, renames, reopenings, AND the build-side moves (a campus or
-- program opened, or a program cut). abrupt = 1 when the closure was precipitous (doors shut with
-- little warning), 0 orderly, NULL unknown. counterpart is the other institution in a
-- merger/acquisition, when known. The *_opened / program_closed types let the timeline record not
-- just retreats but reinvestment, so a "cut vs build" ratio is computable per institution over time
-- (a school that only ever closes things is spiralling; one that closes and opens is pivoting).
CREATE TABLE event (
  institution_id             TEXT NOT NULL REFERENCES institution(id),
  event_type                 TEXT NOT NULL CHECK (event_type IN
                               ('founded','renamed','merged_into','absorbed','consolidated',
                                'campus_closed','closed','teachout','reopened',
                                'campus_opened','program_opened','program_closed')),
  event_year                 INTEGER,
  event_date                 TEXT,             -- ISO date when known
  abrupt                     INTEGER,          -- 1 abrupt, 0 orderly, NULL unknown
  counterpart_institution_id TEXT REFERENCES institution(id),
  description                TEXT,
  source_url                 TEXT
);

-- "Audience served", mission, and closure attributes as flexible tags, so a new category
-- never needs a schema change. Examples: HBCU, tribal, womens, religious, catholic,
-- teach_out_plan, merger_attempted, accreditor:AACSB.
CREATE TABLE characteristic (
  institution_id  TEXT NOT NULL REFERENCES institution(id),
  tag             TEXT NOT NULL,
  UNIQUE (institution_id, tag)
);

-- The closure autopsy's headline figures: the small set of numbers that explain HOW a school
-- failed, one sourced row per figure. Storage template behind the "Anatomy of the closure" panel,
-- deliberately generic (a metric key + a value) so any closure's crisis can be recorded without a
-- schema change: cash_on_hand, near_term_obligations, debt_prior_year, projected_deficit,
-- rescue_needed, rescue_raised, endowment, employees, students_displaced, closure_warning_days.
--
-- Raw sourced facts ONLY, like financial_filing: the panel COMPUTES the readings (runway, the
-- rescue gap) in app/queries.py, so a definition can change without re-entering data and every
-- number traces to one sourced row. For a Form-990 school these can derive from financial_filing;
-- for a pre-federal school like Yankton they are hand-sourced here. amount is the number when
-- there is one; qualitative carries a sourced word ('depleted') when there is no figure. Its own
-- hand-curated CSV (data/closure_metrics.csv), never a column on a generated file.
CREATE TABLE closure_metric (
  institution_id  TEXT NOT NULL REFERENCES institution(id),
  metric          TEXT NOT NULL,   -- the figure's key (see list above)
  amount          INTEGER,         -- the value, when there is one; NULL for a qualitative-only fact
  unit            TEXT,            -- 'usd' | 'count' | 'days'
  qualitative     TEXT,            -- a sourced word when there is no number (e.g. 'depleted')
  as_of_year      INTEGER,         -- the year the figure describes
  note            TEXT,
  source_url      TEXT,
  UNIQUE (institution_id, metric)
);
CREATE INDEX idx_closure_metric_inst ON closure_metric(institution_id);

-- Heightened Cash Monitoring history: one row per institution per ED snapshot it appears
-- in. level '1' = HCM1 (added oversight), '2' = HCM2 (reimbursement, most severe). Appearing
-- on HCM before the closure year is a leading distress signal for the resilience model.
CREATE TABLE hcm (
  institution_id  TEXT NOT NULL REFERENCES institution(id),
  as_of_date      TEXT NOT NULL,          -- ISO date of the snapshot
  level           TEXT,                   -- '1' or '2'
  source_file     TEXT
);
CREATE INDEX idx_hcm_inst ON hcm(institution_id, as_of_date);

-- High school graduate counts (NCES Digest 219.10 national, 219.20 by state). The
-- demographic pool behind the enrollment cliff. Long format: one row per
-- (jurisdiction, measure, year). Not linked to institutions; contextual.
CREATE TABLE hs_graduates (
  source_table      TEXT,
  jurisdiction      TEXT NOT NULL,
  jurisdiction_type TEXT,                    -- national | region | state
  school_year       TEXT,                    -- e.g. '2013-14'
  year              INTEGER,                  -- ending calendar year, for sorting/plotting
  measure           TEXT,                     -- total | public | private
  graduates         INTEGER
);
CREATE INDEX idx_hsg ON hs_graduates(jurisdiction, measure, year);

-- The national long run: how many colleges the country has had, and how many students they have
-- enrolled, back to 1869. Context for the closure record: the tracker shows a sector contracting
-- from a peak, and this is the peak it contracted from. Sourced entirely from the NCES Digest of
-- Education Statistics (public domain); every row carries its source and the counting basis,
-- because the basis changes across the span. The institutions line splices decennial pre-1974
-- (branch campuses excluded) onto annual 1974+ (branches included); the enrollment line splices
-- decennial pre-1947 onto annual 1947+. Those are different definitions, so `basis` records which
-- each row is on and a reader-facing chart marks the seam. One row per (series, year).
CREATE TABLE national_series (
  series  TEXT NOT NULL,      -- 'institutions' | 'enrollment'
  year    INTEGER NOT NULL,
  value   INTEGER NOT NULL,
  basis   TEXT,               -- the counting definition this row is on (see note above)
  source  TEXT,               -- the exact NCES Digest table
  UNIQUE (series, year)
);
CREATE INDEX idx_natser ON national_series(series, year);

-- Key dates for the timeline under the national charts: the policy or demographic events that are
-- the LIKELY cause of an inflection in the line above. Editorial attributions, not data readings,
-- so each carries a primary source and the copy frames them as likely causes, never as proven.
-- One row per (series, year).
CREATE TABLE timeline_marker (
  series      TEXT NOT NULL,  -- which chart it annotates
  year        INTEGER NOT NULL,
  label       TEXT NOT NULL,  -- short bottom-axis label
  detail      TEXT,           -- the one-line likely cause
  source_url  TEXT,
  UNIQUE (series, year)
);

-- The richer "what drove the turns" reading under each national chart: one row per inflection a
-- reader can see (an era of fast growth, a plateau, a peak or valley), with the sourced likely
-- cause and a category (policy / demographic / economic / war / pandemic / artifact). This is
-- analysis, not a data reading, so is_inference marks the rows where the cause is our inference
-- from timing rather than a source that states it outright, and the copy is written to match. The
-- growth rates the chart quotes are NOT stored here: they are computed live from national_series
-- (app/queries.national_growth), so the numbers can never drift from the underlying data.
-- Display order within a series is the CSV row order, read back via rowid, so the file is the
-- single place the order is set.
CREATE TABLE national_turn (
  series        TEXT NOT NULL,  -- 'institutions' | 'enrollment'
  era           TEXT NOT NULL,  -- the span, e.g. '1869-1889' or '2010 onward'
  shows         TEXT,           -- what the data shows in that span
  cause         TEXT,           -- the sourced likely cause
  category      TEXT,           -- policy | demographic | economic | war | pandemic | artifact
  is_inference  INTEGER,        -- 1 = the cause is our inference from timing, not a stated source
  source_url    TEXT
);
CREATE INDEX idx_turn ON national_turn(series);

-- College Scorecard slice (U.S. Dept. of Education, public domain): a focused set of
-- closure-risk and student-profile fields per institution per year, filtered to our
-- institutions only (raw Scorecard stays in uploads/, never loaded whole).
CREATE TABLE scorecard (
  institution_id  TEXT NOT NULL REFERENCES institution(id),
  year            INTEGER,
  ugds            INTEGER,   -- undergraduate enrollment (headcount)
  adm_rate        REAL,      -- admission rate 0-1 (higher = less selective)
  pct_pell        REAL,      -- share of undergraduates on Pell (low-income reliance)
  tuitfte         INTEGER,   -- net tuition revenue per FTE student ($)
  tuitionfee_in   INTEGER,   -- in-state tuition and fees ($)
  costt4_a        INTEGER,   -- average annual cost of attendance ($)
  pptug_ef        REAL,      -- part-time undergraduate share 0-1
  ugds_white      REAL,
  ugds_black      REAL,
  ugds_hisp       REAL,
  first_gen       REAL,      -- first-generation share 0-1
  curroper        INTEGER,   -- currently operating flag (1/0)
  ret_ft4         REAL,      -- first-time full-time retention, 4-year (0-1)
  ret_ftl4        REAL,      -- first-time full-time retention, <4-year (0-1)
  c150_4          REAL,      -- completion within 150% of expected time, 4-year (0-1)
  c150_l4         REAL       -- completion within 150% of expected time, <4-year (0-1)
);
CREATE INDEX idx_sc ON scorecard(institution_id, year);

-- The financial time series, from the IPEDS Finance (F) survey: a U.S. Dept. of Education public
-- record covering EVERY Title IV institution every year (public, private nonprofit, and for-profit
-- alike), keyed on UNITID. This is the layer that makes tuition dependence, revenue diversification,
-- and reserve trends measurable across the whole sector, not just the one Form-990 school. Raw
-- sourced dollars ONLY, one row per institution per fiscal year: the ratios (tuition share of
-- revenue, federal-money dependence, months of reserves) are opinions about these numbers and are
-- computed in app/queries.py so a definition can change without a reimport. Populated by a dedicated
-- IPEDS-F importer (data/finance_year.csv); empty until that import is run. FASB (private) and GASB
-- (public) forms report on different line schedules, so the importer maps both onto these columns.
CREATE TABLE finance_year (
  institution_id       TEXT NOT NULL REFERENCES institution(id),
  fiscal_year          INTEGER,
  total_revenue        INTEGER,   -- total revenues and investment return ($)
  tuition_revenue      INTEGER,   -- tuition and fees, net of institutional discounts ($)
  federal_revenue      INTEGER,   -- federal appropriations, grants and contracts ($)
  state_local_revenue  INTEGER,   -- state + local appropriations, grants and contracts ($)
  private_gifts_grants INTEGER,   -- private gifts, grants and contracts ($)
  investment_return    INTEGER,   -- investment return / income ($)
  total_expenses       INTEGER,   -- total expenses ($)
  instruction_expense  INTEGER,   -- instruction expenses ($)
  endowment_eoy        INTEGER,   -- endowment assets, end of fiscal year ($) -- the reserve proxy
  tuition_allowances   INTEGER,   -- discounts/allowances applied to tuition ($); gross = net + this
  net_position         INTEGER,   -- total net position/net assets/equity ($); the reserve balance
  source               TEXT,      -- e.g. 'IPEDS F2223_F1A'
  source_url           TEXT
);
CREATE INDEX idx_fin ON finance_year(institution_id, fiscal_year);

-- Program breadth over time, from the IPEDS Completions (C) survey: the count of distinct academic
-- programs (4-digit CIP families that produced a graduate) an institution ran each year, plus how
-- many it ADDED and DROPPED versus the prior reported year. This is the quantitative half of the
-- "you must replace what you cut" thesis: a school whose n_dropped keeps exceeding n_added is
-- shrinking its offerings (a retreat), while one that adds as it cuts is pivoting. Together with the
-- curated program_opened / program_closed events, it lets a cut-vs-build ratio be computed per
-- institution over time. Populated by a dedicated IPEDS-C importer (data/program_year.csv).
-- Caveat carried in queries, not the data: CIP was recoded in 2011 and 2021, so added/dropped spike
-- artificially across those two boundaries; the count itself is robust.
CREATE TABLE program_year (
  institution_id  TEXT NOT NULL REFERENCES institution(id),
  year            INTEGER,
  n_programs      INTEGER,   -- distinct 4-digit CIP programs with >=1 graduate that year
  n_added         INTEGER,   -- programs present this year but not the prior reported year
  n_dropped       INTEGER,   -- programs present the prior reported year but not this year
  source          TEXT,
  source_url      TEXT
);
CREATE INDEX idx_progyr ON program_year(institution_id, year);

-- Financial history from IRS Form 990, the annual return every private nonprofit college files
-- publicly (a U.S. government record, public domain). This is where "where things fall apart"
-- becomes measurable: revenue, expenses, and balance sheet in the years before a closure, or in
-- the years a school pulled out of one. Filings are keyed on EIN, so institution_ein is the join.
--
-- Raw filing facts ONLY. Tuition dependency, operating margin, and months of cash are ratios, and
-- a ratio is an opinion about the numbers: those are computed in app/queries.py, so a definition
-- can be revised without a reimport and every stored number traces to one line of one filing.
--
-- One row per institution per tax year per source. Note tax_year is the IRS tax year, which for a
-- June fiscal-year-end school runs a year behind the fiscal year it closes: TaxYr 2024 ends
-- 2025-06-30. Label a reader-facing chart from period_end, not tax_year.
-- OPEID -> EIN crosswalk: the join between this database (keyed on OPEID) and IRS filings
-- (keyed on EIN). Its own table, and its own hand-curated CSV, for one hard reason: IPEDS does
-- not publish EINs, and data/institutions_open.csv is rewritten whole from IPEDS by
-- scripts/import_ipeds_roster.py. An EIN kept on the institution row would be silently erased
-- the next time that roster regenerates, which is exactly what happened once already.
--
-- One row per (institution, EIN). A school can legitimately have more than one over time
-- (it reincorporates, or a merger moves the filer), so this is not unique on institution_id;
-- source records where the number came from, because an unsourced EIN attaches a school's
-- finances to the wrong entity and that error is invisible once it is in.
CREATE TABLE institution_ein (
  institution_id  TEXT NOT NULL REFERENCES institution(id),
  ein             TEXT NOT NULL,
  source          TEXT,                   -- how this pairing was established
  source_url      TEXT,
  UNIQUE (institution_id, ein)
);
CREATE INDEX idx_inst_ein ON institution_ein(ein);

CREATE TABLE financial_filing (
  institution_id       TEXT NOT NULL REFERENCES institution(id),
  tax_year             INTEGER NOT NULL,
  period_begin         TEXT,                -- ISO date
  period_end           TEXT,                -- ISO date: the fiscal year end
  return_type          TEXT,                -- '990', '990EZ', '990PF'
  ein                  TEXT,
  -- Part I summary and Part VIII revenue
  total_revenue        INTEGER,
  contributions        INTEGER,             -- Part I total: government grants AND private giving
  -- The split inside contributions, and the reason it is stored rather than derived: a college
  -- rebuilding on government money and one rebuilding on donors look identical in the headline
  -- total, and only one of them keeps the money. Government relief arrives, then stops.
  government_grants    INTEGER,
  other_contributions  INTEGER,             -- private giving: everything that is not a govt grant
  noncash_contributions INTEGER,            -- gifts in kind (property, securities), not cash in the door
  program_svc_revenue  INTEGER,             -- tuition, fees, auxiliaries (broken out in financial_line_item)
  investment_income    INTEGER,
  other_revenue        INTEGER,
  -- Part I and Part IX expenses
  total_expenses       INTEGER,
  program_svc_expenses INTEGER,
  fundraising_expenses INTEGER,
  salaries             INTEGER,             -- salaries, other compensation, employee benefits
  grants_paid          INTEGER,             -- "grants and similar amounts paid": for a college this
                                            -- is mostly institutional aid, i.e. the tuition discount

  net_income           INTEGER,             -- revenue less expenses; negative is an operating loss
  -- Part X balance sheet, end of year
  total_assets         INTEGER,
  total_liabilities    INTEGER,
  net_assets           INTEGER,
  employees            INTEGER,             -- Part I headcount; a 0 can mean "not reported", not "none"
  source               TEXT,                -- e.g. 'IRS Form 990'
  source_url           TEXT,
  source_file          TEXT,                -- the filing XML this row was parsed from
  UNIQUE (institution_id, tax_year, source)
);
CREATE INDEX idx_fin_inst ON financial_filing(institution_id, tax_year);

-- The free-text breakout lines inside a filing (Part VIII program service revenue, for now).
-- These are not fixed fields: each school writes its own labels, so tuition arrives as
-- 'TUITION AND FEES' one year and the typo 'TUITITION AND FEES' another. Stored verbatim, typos
-- included, so the raw record stays faithful to the filing and a label matcher can be corrected
-- later without a reimport. Never clean up description to make it match.
CREATE TABLE financial_line_item (
  institution_id  TEXT NOT NULL REFERENCES institution(id),
  tax_year        INTEGER NOT NULL,
  part            TEXT,        -- which section the line came from, e.g. 'program_service_revenue'
  description     TEXT,        -- verbatim from the filing
  amount          INTEGER,
  source_file     TEXT
);
CREATE INDEX idx_finline_inst ON financial_line_item(institution_id, tax_year);

-- How many institutions were actually operating, per year, per sector: the denominator the
-- closure record cannot supply on its own. Counted straight from the IPEDS HD directory files
-- (NCES, public domain) by scripts/import_ipeds_roster.py, one row per (year, control), where
-- the count is of institutions NCES marked CYACTIVE = currently active in that collection year.
--
-- This exists so the tracker can say what share of the sector closed instead of only how many
-- did. Read it as a snapshot per collection year, not a lifecycle: an institution leaving the
-- count is not necessarily a closure (it may have merged, or left Title IV), which is exactly
-- why the closure record is curated separately and never derived from these counts.
--
-- Keep control broken out, and chart it broken out. The 2012 to 2024 decline is roughly 84%
-- for-profit; presenting a single total line would tell a tuition-dependent private nonprofit
-- that its sector collapsed by a fifth, which is not what this data says.
CREATE TABLE sector_size (
  year        INTEGER NOT NULL,   -- IPEDS HD collection year
  control     TEXT,               -- public | private_nonprofit | private_forprofit
  active      INTEGER,            -- institutions marked currently active
  source      TEXT,
  source_url  TEXT,
  UNIQUE (year, control)
);
CREATE INDEX idx_sector_size ON sector_size(year);

-- Financial Responsibility Composite Score (U.S. Dept. of Education, public domain), the
-- single number ED itself uses to decide whether a school is financially responsible enough
-- to keep handling Title IV money. Published per award year at
-- https://studentaid.gov/data-center/school/composite-scores and sourced from eZ-Audit, the
-- system schools file their audited financial statements into. This is the closest thing to
-- an official, comparable, annual distress signal that exists across the whole sector.
--
-- Coverage is NOT the whole sector, and a rate computed off it must say so: ED only scores
-- PRIVATE NON-PROFIT and PROPRIETARY institutions. Public institutions are absent, because
-- they are backed by a state and are not required to demonstrate financial responsibility
-- this way. Never present a denominator from this table as "all colleges".
--
-- One row per institution per award year. award_year is the label ED groups the file by
-- ('2022-23' = fiscal years ending between 7/1/2022 and 6/30/2023) and year is its ending
-- calendar year, for sorting and plotting: the same TEXT-label + INTEGER-year pattern
-- hs_graduates uses. fy_end is the institution's own fiscal year end within that window,
-- which varies school to school, so label a reader-facing chart from award_year, not fy_end.
--
-- score is stored exactly as ED published it and is never recomputed here: the pass/zone/fail
-- thresholds are ED's interpretation of the number and live in app/queries.py, so a
-- reading can be revised without a reimport. institution_type is verbatim ED text
-- ('Non Profit' / 'Proprietary') and is per-year on purpose: schools do convert between the
-- two, and this table records which they were in each year rather than flattening it.
-- as_of is the eZ-Audit snapshot date printed in the file, because ED revises scores.
CREATE TABLE composite_score (
  institution_id   TEXT NOT NULL REFERENCES institution(id),
  award_year       TEXT NOT NULL,        -- e.g. '2022-23'
  year             INTEGER,              -- ending calendar year, for sorting/plotting
  score            REAL,                 -- as published, -1.0 to 3.0
  fy_end           TEXT,                 -- ISO date: this institution's fiscal year end
  institution_type TEXT,                 -- verbatim ED text: 'Non Profit' | 'Proprietary'
  as_of            TEXT,                 -- eZ-Audit snapshot date the file was cut from
  source_url       TEXT,
  source_file      TEXT,                 -- the ED spreadsheet this row was parsed from
  UNIQUE (institution_id, award_year)
);
CREATE INDEX idx_cs_inst ON composite_score(institution_id, year);
CREATE INDEX idx_cs_year ON composite_score(year, score);

CREATE INDEX idx_inst_state    ON institution(state);
CREATE INDEX idx_inst_control  ON institution(control);
CREATE INDEX idx_inst_status   ON institution(status, status_year);
CREATE INDEX idx_enroll_inst   ON enrollment(institution_id, year);
CREATE INDEX idx_event_inst    ON event(institution_id);
CREATE INDEX idx_event_type    ON event(event_type, event_year);
CREATE INDEX idx_name_inst     ON institution_name(institution_id);
CREATE INDEX idx_char_tag      ON characteristic(tag);

-- Full-text search over current and historical names, so a search finds a school by any
-- name it ever carried. Rebuilt by build_db.py after the data loads.
CREATE VIRTUAL TABLE institution_search USING fts5(institution_id UNINDEXED, name);

-- Peer-relative Resilience score, a pure function of scorecard + composite + status already in
-- this DB. Populated by scripts/resilience.write_scores after the data loads (never from a CSV):
-- the model weights are frozen in resilience.py, the peer percentiles are recomputed each build.
-- band in ('Resilient','Stable','Watch','Strained'); pctile/health/p_*/c_* are 0..1 display and
-- signed-contribution values. See docs/strategy/INSTITUTIONAL_HEALTH_METRICS.md.
CREATE TABLE resilience_score (
  institution_id TEXT PRIMARY KEY REFERENCES institution(id),
  band     TEXT NOT NULL CHECK (band IN ('Resilient','Stable','Watch','Strained')),
  pctile   REAL NOT NULL,        -- health rank among LIVING institutions, 0..1
  health   REAL NOT NULL,        -- 1 - model risk
  p_size   REAL, p_trend REAL, p_pell REAL, p_tuition REAL,   -- per-driver display percentiles
  c_size   REAL, c_trend REAL, c_pell REAL, c_tuition REAL    -- signed contributions (>0 = risk)
);
CREATE INDEX idx_resilience_band ON resilience_score(band, pctile);
