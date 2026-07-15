#!/usr/bin/env python3
"""Import the SHEEO Closed College Context dataset into the data/ CSVs.

Source: uploads/SHEEO_Closed_College_Context.xlsx, sheet "Closed College Context".
This is the State Higher Education Executive Officers closed-college dataset (drawn from
PEPS / National Student Clearinghouse / FOIA closure reports). It is the authoritative,
sourced spine of the tracker.

The importer cleans the real-world mess so the CSVs are trustworthy:
  - Excel serial-number close dates AND "M/D/YYYY" strings -> ISO dates + year.
  - inconsistent Sector strings ("Proprietary", "Private, nonprofit", "Private for-profit
    2yr") -> normalized control + level, with the original preserved in sector_raw.
  - blank / partial rows (no school name) skipped and counted.
  - duplicate OPEIDs de-collided with a "-2" suffix so the primary key holds.
  - the first http(s) URL in the closure Source(s) cell -> source_url; full text -> notes.

Output CSVs (institutions, events, characteristics) are OVERWRITTEN from the source;
names/campuses/enrollment are left alone (hand-curated / enriched elsewhere). After running
this, run scripts/build_db.py. Standard library only.

Usage: python3 scripts/import_sheeo.py
"""
from __future__ import annotations

import csv
import datetime as dt
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
# The source may sit at uploads/ or uploads/data/ depending on how uploads is organized.
_CANDIDATES = [
    ROOT / "uploads" / "data" / "SHEEO_Closed_College_Context.xlsx",
    ROOT / "uploads" / "SHEEO_Closed_College_Context.xlsx",
]
SRC = next((p for p in _CANDIDATES if p.exists()), _CANDIDATES[0])
DATA = ROOT / "data"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
EXCEL_EPOCH = dt.date(1899, 12, 30)  # Excel's day-0 (accounts for the 1900 leap bug)
URL_RE = re.compile(r"https?://[^\s]+")


def read_sheet(path: Path, sheet_file: str = "xl/worksheets/sheet1.xml"):
    """Yield rows (lists of cell strings) from one worksheet, resolving shared strings."""
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))

    def val(c):
        t = c.get("t")
        v = c.find(f"{NS}v")
        if v is None:
            isv = c.find(f"{NS}is")
            return "".join(x.text or "" for x in isv.iter(f"{NS}t")) if isv is not None else ""
        return shared[int(v.text)] if t == "s" else (v.text or "")

    ws = ET.fromstring(z.read(sheet_file))
    for row in ws.iter(f"{NS}row"):
        yield [val(c) for c in row.findall(f"{NS}c")]


def parse_date(raw: str):
    """Return (iso_date_or_None, year_or_None) from an Excel serial int or M/D/YYYY."""
    s = (raw or "").strip()
    if not s:
        return None, None
    if s.isdigit():
        try:
            d = EXCEL_EPOCH + dt.timedelta(days=int(s))
            return d.isoformat(), d.year
        except (ValueError, OverflowError):
            return None, None
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            d = dt.datetime.strptime(s, fmt).date()
            return d.isoformat(), d.year
        except ValueError:
            continue
    m = re.search(r"(19|20)\d{2}", s)  # last resort: a bare year in free text
    return (None, int(m.group(0))) if m else (None, None)


def parse_sector(raw: str):
    """SHEEO sector string -> (control, level). Original kept separately in sector_raw."""
    s = (raw or "").strip().lower()
    if not s:
        return None, None
    if "public" in s:
        control = "public"
    elif "for-profit" in s or "for profit" in s or "proprietary" in s:
        control = "private_forprofit"
    elif "nonprofit" in s or "non-profit" in s:
        control = "private_nonprofit"
    else:
        control = None
    if "4yr" in s or "4 yr" in s or "4-year" in s or "4 year" in s:
        level = "4yr"
    elif "2yr" in s or "2 yr" in s or "2-year" in s or "2 year" in s:
        level = "2yr"
    else:
        level = None
    return control, level


def first_url(text: str):
    m = URL_RE.search(text or "")
    return m.group(0).rstrip(").,;") if m else ""


def clean(text: str) -> str:
    """Collapse the whitespace/newlines the source uses heavily, for a tidy CSV cell."""
    return re.sub(r"\s+", " ", (text or "").strip())


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing source: {SRC}")
    rows = list(read_sheet(SRC))
    header = [h.strip() for h in rows[0]]
    idx = {name: i for i, name in enumerate(header)}

    def cell(row, name):
        i = idx.get(name)
        return row[i] if i is not None and i < len(row) else ""

    institutions, events, characteristics = [], [], []
    seen_ids: set[str] = set()
    kept = skipped_blank = noid = deduped = 0

    for row in rows[1:]:
        name = clean(cell(row, "School Name"))
        if not name:
            skipped_blank += 1
            continue
        kept += 1

        opeid = clean(cell(row, "OPEID"))
        if not opeid or not re.match(r"^\d+$", opeid):
            noid += 1
            inst_id = f"NOID-{noid:04d}"
            opeid = ""
        else:
            inst_id = opeid
        if inst_id in seen_ids:  # de-collide duplicate OPEIDs
            deduped += 1
            suffix = 2
            while f"{inst_id}-{suffix}" in seen_ids:
                suffix += 1
            inst_id = f"{inst_id}-{suffix}"
        seen_ids.add(inst_id)

        control, level = parse_sector(cell(row, "Sector"))
        sector_raw = clean(cell(row, "Sector"))
        _, close_year = parse_date(cell(row, "Date Closed"))
        close_iso, _ = parse_date(cell(row, "Date Closed"))
        merged_peps = clean(cell(row, "Merged/Consolidated (in PEPS)"))
        abrupt_raw = clean(cell(row, "Abrupt (1) vs Orderly (0)"))
        abrupt = abrupt_raw if abrupt_raw in ("0", "1") else ""

        merged = bool(merged_peps) and merged_peps.lower() not in ("0", "no", "n")
        status = "merged" if merged else "closed"
        event_type = "merged_into" if merged else "closed"

        source_cells = " ".join(
            cell(row, c) for c in ("Source(s)",) if idx.get("Source(s)") is not None
        )
        # "Source(s)" appears multiple times in the header; scan every occurrence.
        all_sources = " ".join(
            row[i] for i, h in enumerate(header) if h == "Source(s)" and i < len(row)
        )
        source_url = first_url(all_sources) or first_url(source_cells)
        notes = clean(cell(row, "Notes"))

        institutions.append({
            "id": inst_id, "opeid": opeid, "unitid": "", "unitid_match": "", "name": name,
            "control": control or "", "level": level or "", "sector_raw": sector_raw,
            "religious_affiliation": "", "founding_year": "",
            "degrees": "", "background": "", "history": "",
            "city": clean(cell(row, "City")), "state": clean(cell(row, "State")),
            "status": status, "status_year": close_year or "",
            "closure_type": "", "parent_name": "",
            "notes": notes[:500], "source_url": source_url,
        })
        events.append({
            "institution_id": inst_id, "event_type": event_type,
            "event_year": close_year or "", "event_date": close_iso or "",
            "abrupt": abrupt, "counterpart_institution_id": "",
            "description": ("Merged/consolidated per PEPS. " if merged else "") + notes[:300],
            "source_url": source_url,
        })
        if abrupt == "1":
            characteristics.append({"institution_id": inst_id, "tag": "abrupt_closure"})
        if clean(cell(row, "Attempted or Executed Merger")):
            characteristics.append({"institution_id": inst_id, "tag": "merger_involved"})

    write_csv(DATA / "institutions.csv", institutions,
              ["id", "opeid", "unitid", "unitid_match", "name", "control", "level",
               "sector_raw", "religious_affiliation", "founding_year", "degrees",
               "background", "history", "city", "state", "status", "status_year",
               "closure_type", "parent_name", "notes", "source_url"])
    write_csv(DATA / "events.csv", events,
              ["institution_id", "event_type", "event_year", "event_date", "abrupt",
               "counterpart_institution_id", "description", "source_url"])
    write_csv(DATA / "characteristics.csv", characteristics,
              ["institution_id", "tag"])

    print(f"Source rows (excl. header): {len(rows) - 1}")
    print(f"  kept (had a school name): {kept}")
    print(f"  skipped (blank name):     {skipped_blank}")
    print(f"  no OPEID (synthetic id):  {noid}")
    print(f"  duplicate OPEID suffixed: {deduped}")
    print(f"Wrote institutions.csv ({len(institutions)}), events.csv ({len(events)}), "
          f"characteristics.csv ({len(characteristics)})")
    print("Next: python3 scripts/build_db.py")


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
