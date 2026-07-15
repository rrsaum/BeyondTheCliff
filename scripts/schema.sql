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
  status_year           INTEGER,                -- year of the terminal (or announced/flag) event
  closure_type          TEXT CHECK (closure_type IN ('institutional','campus','program')),  -- for closed/announced rows
  parent_name           TEXT,                   -- for a campus/program closure: the surviving parent institution
  cause                 TEXT CHECK (cause IN (   -- primary sourced cause of failure; NULL = not coded
                          'financial','enrollment','accreditation','sponsor','misconduct',
                          'disaster','restructuring','external','benefactor')),
  notes                 TEXT,
  source_url            TEXT
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

-- The lifecycle: closures, mergers, renames, reopenings. abrupt = 1 when the closure was
-- precipitous (doors shut with little warning), 0 orderly, NULL unknown. counterpart is
-- the other institution in a merger/acquisition, when known.
CREATE TABLE event (
  institution_id             TEXT NOT NULL REFERENCES institution(id),
  event_type                 TEXT NOT NULL CHECK (event_type IN
                               ('founded','renamed','merged_into','absorbed','consolidated',
                                'campus_closed','closed','teachout','reopened')),
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
  curroper        INTEGER    -- currently operating flag (1/0)
);
CREATE INDEX idx_sc ON scorecard(institution_id, year);

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
