#!/usr/bin/env python3
"""Import a focused slice of the U.S. Dept. of Education College Scorecard for our institutions.

Scorecard is public-domain federal data, ~3,300 columns per institution per year across ~30
yearly MERGED files (~2.5 GB total). Loading it whole would be wasteful, so this STREAMS each
MERGED{start}_{end}_PP.csv line by line, keeps only the rows whose OPEID is one of ours, and
extracts ~13 columns that speak to closure risk and student profile:

  enrollment   UGDS
  selectivity  ADM_RATE
  finances     TUITFTE (net tuition/FTE), TUITIONFEE_IN, COSTT4_A, PCTPELL
  demographics PPTUG_EF (part-time share), UGDS_WHITE/BLACK/HISP, FIRST_GEN
  status       CURROPER

Because the MERGED files go back to 1996, a school that closed in 2012 still has its
pre-closure Scorecard years here. Writes data/scorecard.csv (one row per institution per
year with any data). Run before build_db.py. Standard library only.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SC_DIR = DATA.parent / "uploads" / "data" / "College_Scorecard_Raw_Data_06032026"
if not SC_DIR.exists():
    SC_DIR = ROOT / "uploads" / "data" / "College_Scorecard_Raw_Data_06032026"

# Scorecard column name -> our output column.
COLS = {
    "UGDS": "ugds", "ADM_RATE": "adm_rate", "PCTPELL": "pct_pell",
    "TUITFTE": "tuitfte", "TUITIONFEE_IN": "tuitionfee_in", "COSTT4_A": "costt4_a",
    "PPTUG_EF": "pptug_ef", "UGDS_WHITE": "ugds_white", "UGDS_BLACK": "ugds_black",
    "UGDS_HISP": "ugds_hisp", "FIRST_GEN": "first_gen", "CURROPER": "curroper",
}
OUT_FIELDS = ["institution_id", "year", *COLS.values()]
NULLS = {"", "NA", "NULL", "PS", "PrivacySuppressed"}


def clean(v: str) -> str:
    return "" if v is None or v.strip() in NULLS else v.strip()


def main() -> None:
    if not SC_DIR.exists():
        raise SystemExit(f"Scorecard directory not found: {SC_DIR}")
    ours = set()
    for name in ("institutions.csv", "manual_closures.csv"):  # include hand-curated rows with an OPEID
        p = DATA / name
        if p.exists():
            with p.open(encoding="utf-8", newline="") as fh:
                ours |= {r["opeid"].strip() for r in csv.DictReader(fh) if r.get("opeid", "").strip()}

    files = sorted(SC_DIR.glob("MERGED*_PP.csv"))
    out, kept_years = [], []
    for path in files:
        m = re.match(r"MERGED(\d{4})_(\d{2})_PP\.csv", path.name)
        if not m:
            continue
        year = int(m.group(1)) + 1  # academic year end, e.g. MERGED2013_14 -> 2014
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            idx = {h: i for i, h in enumerate(header)}
            if "OPEID" not in idx or not all(c in idx for c in COLS):
                continue
            ope_i = idx["OPEID"]
            col_i = {sc: idx[sc] for sc in COLS}
            n = 0
            for row in reader:
                if ope_i >= len(row):
                    continue
                opeid = row[ope_i].strip()
                if opeid not in ours:
                    continue
                rec = {"institution_id": opeid, "year": year}
                for sc, out_col in COLS.items():
                    rec[out_col] = clean(row[col_i[sc]] if col_i[sc] < len(row) else "")
                if any(rec[c] for c in COLS.values()):  # skip rows that are all-null
                    out.append(rec)
                    n += 1
        kept_years.append((year, n))

    # One row per (institution, year): keep the last file's value if a year repeats.
    dedup = {}
    for rec in out:
        dedup[(rec["institution_id"], rec["year"])] = rec
    rows = sorted(dedup.values(), key=lambda r: (r["institution_id"], r["year"]))

    with (DATA / "scorecard.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(rows)

    insts = len({r["institution_id"] for r in rows})
    print(f"Scorecard files read: {len(kept_years)}; rows for our institutions: {len(rows)} "
          f"across {insts} institutions, years {kept_years[0][0]} to {kept_years[-1][0]}")
    print("Next: python3 scripts/build_db.py")


if __name__ == "__main__":
    main()
