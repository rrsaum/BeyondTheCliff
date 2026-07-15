#!/usr/bin/env python3
"""Import Heightened Cash Monitoring (HCM) history from the U.S. Dept. of Education snapshots.

HCM is the payment method ED places distressed institutions on for extra oversight (HCM1 =
additional oversight; HCM2 = reimbursement only, the most severe). Appearing on HCM is a
documented leading signal of financial distress, so "was this school on HCM before it
closed?" is core to the resilience thesis.

Source: the quarterly HCM spreadsheets in uploads/data/ (studentaid.gov/data-center/school/hcm),
a mix of old .xls and .xlsx. Each is a point-in-time snapshot: OPE ID, name, level, and an
"as of" date in the title row. This reads every snapshot, keeps the rows whose OPE ID is one
of ours, and writes data/hcm.csv (one row per institution per snapshot it appears in).

Run AFTER import_sheeo.py (needs our OPE IDs), BEFORE build_db.py.
Reads .xls via xlrd; .xlsx via the standard library.
"""
from __future__ import annotations

import csv
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import xlrd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SRC_DIR = DATA.parent / "uploads" / "data"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
MONTHS = {m.lower(): i for i, m in enumerate(
    ["", "January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"])}


def rows_xls(path: Path) -> list[list[str]]:
    book = xlrd.open_workbook(path)
    s = book.sheet_by_index(0)
    return [[str(s.cell_value(r, c)) for c in range(s.ncols)] for r in range(s.nrows)]


def rows_xlsx(path: Path) -> list[list[str]]:
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


def read_rows(path: Path) -> list[list[str]]:
    return rows_xls(path) if path.suffix.lower() == ".xls" else rows_xlsx(path)


def snapshot_date(rows: list[list[str]], fname: str) -> str | None:
    """ISO date of the snapshot, from the 'as of M-D-YYYY' title, else the filename."""
    head = " ".join(c for r in rows[:3] for c in r)
    m = re.search(r"as of\s*(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})", head, re.I)
    if m:
        mo, day, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        yr += 2000 if yr < 100 else 0
        return f"{yr:04d}-{mo:02d}-{day:02d}"
    # Filename fallbacks: month-name + year, or a MMDDYYYY / MMDDYY digit run.
    fm = re.search(r"(" + "|".join(list(MONTHS)[1:]) + r")[^0-9]*?(\d{4})", fname, re.I)
    if fm:
        return f"{int(fm.group(2)):04d}-{MONTHS[fm.group(1).lower()]:02d}-01"
    dm = re.search(r"(\d{2})(\d{2})(\d{4})", fname) or re.search(r"(\d{2})(\d{2})(\d{2})\b", fname)
    if dm:
        mo, day, yr = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
        yr += 2000 if yr < 100 else 0
        if 1 <= mo <= 12:
            return f"{yr:04d}-{mo:02d}-{day:02d}"
    return None


def col_index(rows: list[list[str]]) -> tuple[int, int, int] | None:
    """Locate the header row and return (ope_id_col, type_col, method_col)."""
    for r in rows[:8]:
        upper = [c.strip().upper() for c in r]
        if "OPE ID" in upper:
            ope = upper.index("OPE ID")
            method = next((i for i, c in enumerate(upper) if "MONITOR METHOD" in c or "STOP PAY" in c), -1)
            return ope, -1, method
    return None


def norm_opeid(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)          # xls may give "100700.0"
    return digits.zfill(8) if digits else ""


def hcm_level(method: str) -> str:
    m = re.search(r"([12])", method or "")
    return m.group(1) if m else ""


def main() -> None:
    ours = set()
    for name in ("institutions.csv", "manual_closures.csv"):  # include hand-curated rows with an OPEID
        p = DATA / name
        if p.exists():
            with p.open(encoding="utf-8", newline="") as fh:
                ours |= {r["opeid"].strip() for r in csv.DictReader(fh) if r.get("opeid", "").strip()}
    files = sorted(p for p in SRC_DIR.glob("*") if re.search(r"hcm", p.name, re.I)
                   and p.suffix.lower() in (".xls", ".xlsx"))

    out, seen = [], set()
    skipped, snapshots = [], 0
    for path in files:
        try:
            rows = read_rows(path)
        except Exception as exc:  # noqa: BLE001 - a bad file must not kill the batch
            skipped.append(f"{path.name}: unreadable ({exc})")
            continue
        date = snapshot_date(rows, path.name)
        cols = col_index(rows)
        if not date or not cols:
            skipped.append(f"{path.name}: no date or no OPE ID header")
            continue
        snapshots += 1
        ope_c, _, meth_c = cols
        for r in rows:
            if ope_c >= len(r):
                continue
            opeid = norm_opeid(r[ope_c])
            if opeid not in ours:
                continue
            level = hcm_level(r[meth_c] if 0 <= meth_c < len(r) else "")
            key = (opeid, date)
            if key in seen:
                continue
            seen.add(key)
            out.append({"institution_id": opeid, "as_of_date": date, "level": level,
                        "source_file": path.name})

    out.sort(key=lambda d: (d["institution_id"], d["as_of_date"]))
    with (DATA / "hcm.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["institution_id", "as_of_date", "level", "source_file"])
        w.writeheader()
        w.writerows(out)

    distinct = len({d["institution_id"] for d in out})
    print(f"HCM snapshots read: {snapshots}/{len(files)} files; "
          f"our-institution HCM records: {len(out)} across {distinct} institutions")
    for s in skipped:
        print(f"  skipped {s}")
    print("Next: python3 scripts/build_db.py")


if __name__ == "__main__":
    main()
