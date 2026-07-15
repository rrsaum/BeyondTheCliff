#!/usr/bin/env python3
"""Import high-school-graduate counts from NCES Digest tables 219.10 and 219.20.

These are the demographic pool behind the enrollment cliff: the number of high school
graduates is the feedstock of traditional college enrollment, and its decline is what the
whole thesis is about.

  219.10  national HS graduates by year (total / public / private), 1869-70 to 2022-23.
  219.20  public HS graduates by region, state, and jurisdiction, 1980-81 to 2023-24.

Source: NCES Digest of Education Statistics (nces.ed.gov/programs/digest), files in
uploads/data/. These are actuals; NCES moved projections to a separate table. Writes
data/hs_graduates.csv (long format). Run before build_db.py. Standard library only.
"""
from __future__ import annotations

import csv
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SRC = DATA / "uploads" if (DATA / "uploads").exists() else ROOT / "uploads" / "data"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REGIONS = {"Northeast", "Midwest", "South", "West"}


def read_sheet(path: Path) -> list[list[str]]:
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(f"{NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))

    def val(c):
        t = c.get("t")
        v = c.find(f"{NS}v")
        if v is None:
            isv = c.find(f"{NS}is")
            return "".join(x.text or "" for x in isv.iter(f"{NS}t")) if isv is not None else ""
        return shared[int(v.text)] if t == "s" else (v.text or "")

    ws = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    return [[val(c) for c in row.findall(f"{NS}c")] for row in ws.iter(f"{NS}row")]


def clean_year(raw: str) -> str | None:
    """'2013-14\\1\\' -> '2013-14'. Return None if not a school-year label."""
    s = re.sub(r"\\[0-9]+\\", "", raw or "").strip()
    return s if re.match(r"^\d{4}-\d{2,4}$", s) else None


def end_year(school_year: str) -> int:
    start, end = school_year.split("-")
    return int(end) if len(end) == 4 else (int(start) // 100) * 100 + int(end)


def to_int(raw: str) -> int | None:
    s = re.sub(r"\\[0-9]+\\", "", raw or "").replace(",", "").strip()
    return int(s) if re.match(r"^\d+$", s) else None


def parse_219_20(rows: list[list[str]]) -> list[dict]:
    header = rows[1]
    year_cols = {i: clean_year(header[i]) for i in range(len(header)) if clean_year(header[i])}
    out = []
    for row in rows[3:]:
        name = re.sub(r"\\[0-9]+\\", "", (row[0] if row else "")).strip()
        if not name or name in ("State", "Region") or name.startswith(("NOTE", "SOURCE")):
            continue
        jtype = ("national" if name == "United States"
                 else "region" if name in REGIONS else "state")
        for i, sy in year_cols.items():
            g = to_int(row[i]) if i < len(row) else None
            if g is not None:
                out.append({"source_table": "219.20", "jurisdiction": name,
                            "jurisdiction_type": jtype, "school_year": sy,
                            "year": end_year(sy), "measure": "public", "graduates": g})
    return out


def parse_219_10(rows: list[list[str]]) -> list[dict]:
    # Data rows carry a school year in column 0; columns 1/4/10 are total/public/private.
    out = []
    for row in rows:
        sy = clean_year(row[0]) if row else None
        if not sy:
            continue
        for col, measure in ((1, "total"), (4, "public"), (10, "private")):
            g = to_int(row[col]) if col < len(row) else None
            if g is not None:
                out.append({"source_table": "219.10", "jurisdiction": "United States",
                            "jurisdiction_type": "national", "school_year": sy,
                            "year": end_year(sy), "measure": measure, "graduates": g})
    return out


def main() -> None:
    f10, f20 = SRC / "tabn219.10.xlsx", SRC / "tabn219.20.xlsx"
    if not f10.exists() or not f20.exists():
        raise SystemExit(f"missing source tables in {SRC}")
    records = parse_219_10(read_sheet(f10)) + parse_219_20(read_sheet(f20))
    with (DATA / "hs_graduates.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["source_table", "jurisdiction", "jurisdiction_type",
                                           "school_year", "year", "measure", "graduates"])
        w.writeheader()
        w.writerows(records)
    states = len({r["jurisdiction"] for r in records if r["jurisdiction_type"] == "state"})
    yrs = sorted({r["year"] for r in records})
    print(f"HS graduate records: {len(records)} ({states} states/jurisdictions, "
          f"years {yrs[0]} to {yrs[-1]})")
    print("Next: python3 scripts/build_db.py")


if __name__ == "__main__":
    main()
