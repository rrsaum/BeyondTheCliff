#!/usr/bin/env python3
"""Build the Beyond the Cliff SQLite database from the CSV source-of-truth in data/.

The CSVs in data/ are the source of truth: version-controlled, reviewable, and diffable,
so every data change is a dated git commit with a reason. This script rebuilds
data/beyondthecliff.db from them, from scratch, on every run. Never hand-edit the .db;
edit a CSV and rerun:

    python3 scripts/build_db.py

It validates as it loads (enum CHECKs, foreign keys, unique keys) and fails loudly with a
file:line, so a bad data edit cannot silently ship. Prints a row-count summary on success.
Standard library only (sqlite3, csv): no dependencies to maintain.
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCHEMA = Path(__file__).resolve().parent / "schema.sql"
DB = DATA / "beyondthecliff.db"

# (csv filename, table, integer-typed columns) in foreign-key-safe load order:
# institution first, then everything that references it. Note the id/opeid keys are TEXT
# (OPEID with leading zeros), so they are NOT in the integer-column sets.
TABLES = [
    (
        "institutions.csv",
        "institution",
        {"unitid", "founding_year", "status_year", "parent_survives"},
    ),
    (
        "manual_closures.csv",
        "institution",
        {"unitid", "founding_year", "status_year", "parent_survives"},
    ),
    # Surviving institutions, kept separate from the closure imports above: this dataset is a
    # closure record, and a school that is still operating enters it only deliberately.
    ("institutions_open.csv", "institution", {"unitid", "founding_year", "status_year"}),
    # Hand-curated, and deliberately not part of any generated file: IPEDS has no EIN, and
    # institutions_open.csv is rewritten whole by scripts/import_ipeds_roster.py.
    ("institution_eins.csv", "institution_ein", set()),
    ("names.csv", "institution_name", {"start_year", "end_year"}),
    ("campuses.csv", "campus", {"opened_year", "closed_year", "is_main"}),
    ("enrollment.csv", "enrollment", {"year", "total_headcount", "undergrad", "graduate", "fte"}),
    ("events.csv", "event", {"event_year", "abrupt"}),
    ("characteristics.csv", "characteristic", set()),
    # Hand-curated, one sourced row per closure-autopsy figure. Not part of any generated file.
    ("closure_metrics.csv", "closure_metric", {"amount", "as_of_year"}),
    ("hcm.csv", "hcm", set()),
    ("hs_graduates.csv", "hs_graduates", {"year", "graduates"}),
    ("national_series.csv", "national_series", {"year", "value"}),
    ("timeline_markers.csv", "timeline_marker", {"year"}),
    ("national_turns.csv", "national_turn", {"is_inference"}),
    (
        "scorecard.csv",
        "scorecard",
        {"year", "ugds", "tuitfte", "tuitionfee_in", "costt4_a", "curroper"},
    ),
    (
        "finance_year.csv",
        "finance_year",
        {
            "fiscal_year",
            "total_revenue",
            "tuition_revenue",
            "federal_revenue",
            "state_local_revenue",
            "private_gifts_grants",
            "investment_return",
            "total_expenses",
            "instruction_expense",
            "endowment_eoy",
        },
    ),
    ("program_year.csv", "program_year", {"year", "n_programs", "n_added", "n_dropped"}),
    (
        "financials.csv",
        "financial_filing",
        {
            "tax_year",
            "total_revenue",
            "contributions",
            "government_grants",
            "other_contributions",
            "noncash_contributions",
            "program_svc_revenue",
            "investment_income",
            "other_revenue",
            "total_expenses",
            "program_svc_expenses",
            "fundraising_expenses",
            "salaries",
            "grants_paid",
            "net_income",
            "total_assets",
            "total_liabilities",
            "net_assets",
            "employees",
        },
    ),
    ("financial_line_items.csv", "financial_line_item", {"tax_year", "amount"}),
    ("composite_scores.csv", "composite_score", {"year"}),
    ("sector_size.csv", "sector_size", {"year", "active"}),
]


def coerce(value: str | None, is_int: bool):
    """Empty cell -> NULL; integer columns parsed as int (with a clear error)."""
    v = (value or "").strip()
    if v == "":
        return None
    if is_int:
        try:
            return int(v)
        except ValueError as exc:
            raise ValueError(f"expected an integer, got {value!r}") from exc
    return v


def load_csv(conn: sqlite3.Connection, path: Path, table: str, int_cols: set[str]) -> int:
    if not path.exists():
        print(f"  {table}: no {path.name}, skipping")
        return 0
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        cols = reader.fieldnames or []
        rows = []
        for lineno, row in enumerate(reader, start=2):  # line 1 is the header
            try:
                rows.append([coerce(row.get(c), c in int_cols) for c in cols])
            except ValueError as exc:
                raise SystemExit(f"{path.name}:{lineno}: {exc}")
        if not rows:
            return 0
        placeholders = ",".join("?" for _ in cols)
        collist = ",".join(cols)
        try:
            conn.executemany(f"INSERT INTO {table} ({collist}) VALUES ({placeholders})", rows)
        except sqlite3.IntegrityError as exc:
            raise SystemExit(f"{path.name}: integrity error loading {table}: {exc}")
    return len(rows)


def build_search_index(conn: sqlite3.Connection) -> None:
    """Populate the FTS5 name index from current and historical names."""
    conn.execute("DELETE FROM institution_search")
    conn.execute(
        "INSERT INTO institution_search (institution_id, name) SELECT id, name FROM institution"
    )
    conn.execute(
        "INSERT INTO institution_search (institution_id, name) "
        "SELECT institution_id, name FROM institution_name WHERE name IS NOT NULL"
    )


def main() -> None:
    if not SCHEMA.exists():
        raise SystemExit(f"missing schema: {SCHEMA}")
    DB.unlink(missing_ok=True)
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.execute("PRAGMA foreign_keys = ON")  # enforce during the loads below

    print(f"Building {DB.relative_to(ROOT)}")
    for fname, table, int_cols in TABLES:
        n = load_csv(conn, DATA / fname, table, int_cols)
        print(f"  {table}: {n} row(s)")

    build_search_index(conn)

    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        for v in violations:
            print(f"  foreign-key violation: {v}", file=sys.stderr)
        raise SystemExit("foreign-key violations; fix the CSVs and rebuild")

    conn.commit()
    conn.close()
    print("OK")


if __name__ == "__main__":
    main()
