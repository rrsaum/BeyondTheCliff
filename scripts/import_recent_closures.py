#!/usr/bin/env python3
"""Extend closure coverage past SHEEO's 2020 cutoff with IPEDS HD CLOSEDAT (2021 to 2024).

SHEEO's dataset ends in 2020. IPEDS HD directory files carry a CLOSEDAT field with the
authoritative closure date for each institution, so recent closures come from federal data,
not from scraping article prose (which would risk fabricated names, states, and years).

Reads HD2021 to HD2024, finds institutions whose CLOSEDAT year is 2021 or later and whose
OPE ID is not already in our set, and APPENDS them to data/institutions.csv (as closed) and
a matching row to data/events.csv. The later enrichers (IPEDS enrollment, Wikidata, HCM)
then run over these new rows too.

Run AFTER import_sheeo.py, BEFORE enrich_ipeds.py. Standard library only (plus the shared
IPEDS fetch in enrich_ipeds). 2025 to 2026 closures are not in IPEDS yet; those are a
separate, news-sourced manual step.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from enrich_ipeds import fetch_csv, upper_reader  # shared IPEDS fetch + BOM-safe reader

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
YEARS = range(2004, 2025)
CONTROL = {"1": "public", "2": "private_nonprofit", "3": "private_forprofit"}
LEVEL = {"1": "4yr", "2": "2yr", "3": "lt2yr"}
SOURCE = "https://nces.ed.gov/ipeds/datacenter/data/HD{}.zip"


def parse_closedat(value: str) -> tuple[str | None, int | None]:
    """CLOSEDAT is '-2' when open, else MM/DD/YYYY. Return (iso_date, year) or (None, None)."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", (value or "").strip())
    if not m or m.group(3) == "0000":
        return None, None
    mo, day, yr = m.groups()
    return f"{yr}-{mo}-{day}", int(yr)


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8", newline="") as fh:
        r = csv.DictReader(fh)
        return list(r.fieldnames or []), list(r)


def append_csv(path: Path, fields: list[str], new_rows: list[dict]) -> None:
    _, existing = read_csv(path)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(existing + new_rows)


def main() -> None:
    inst_fields, institutions = read_csv(DATA / "institutions.csv")
    ev_fields, _ = read_csv(DATA / "events.csv")
    # Dedup against BOTH the SHEEO federal rows and the hand-curated manual layer, so a
    # backfilled IPEDS closure never collides with a school we already have.
    existing = {r["opeid"].strip() for r in institutions if r.get("opeid", "").strip()}
    manual_path = DATA / "manual_closures.csv"
    if manual_path.exists():
        _, manual = read_csv(manual_path)
        existing |= {r["opeid"].strip() for r in manual if r.get("opeid", "").strip()}

    recent: dict[str, dict] = {}
    years_seen = []
    for year in YEARS:
        lines = fetch_csv("HD", year)
        if not lines:
            continue
        years_seen.append(year)
        for row in upper_reader(lines):
            opeid = (row.get("OPEID") or "").strip()
            iso, yr = parse_closedat(row.get("CLOSEDAT") or "")
            if not opeid or not yr or yr < 2004 or opeid in existing:
                continue
            recent[opeid] = {  # later year wins (most complete record)
                "name": (row.get("INSTNM") or "").strip(),
                "city": (row.get("CITY") or "").strip(),
                "state": (row.get("STABBR") or "").strip(),
                "control": CONTROL.get((row.get("CONTROL") or "").strip(), ""),
                "level": LEVEL.get((row.get("ICLEVEL") or "").strip(), ""),
                "iso": iso, "year": yr,
            }

    inst_rows, event_rows = [], []
    for opeid, r in sorted(recent.items()):
        base = {f: "" for f in inst_fields}
        base.update({
            "id": opeid, "opeid": opeid, "name": r["name"], "control": r["control"],
            "level": r["level"], "city": r["city"], "state": r["state"],
            "status": "closed", "status_year": str(r["year"]),
            "notes": "Closure recorded in IPEDS HD (CLOSEDAT).",
            "source_url": SOURCE.format(2024),
        })
        inst_rows.append(base)
        ev = {f: "" for f in ev_fields}
        ev.update({
            "institution_id": opeid, "event_type": "closed", "event_year": str(r["year"]),
            "event_date": r["iso"], "description": "Closed (IPEDS CLOSEDAT).",
            "source_url": SOURCE.format(2024),
        })
        event_rows.append(ev)

    append_csv(DATA / "institutions.csv", inst_fields, inst_rows)
    append_csv(DATA / "events.csv", ev_fields, event_rows)
    hi = f"{min(years_seen)}-{max(years_seen)}" if years_seen else "none"
    print(f"HD years read: {hi}. IPEDS closures (2004+) not already in SHEEO/manual, added: "
          f"{len(inst_rows)} (now {len(institutions) + len(inst_rows)} institutions total).")
    print("Next: enrich_ipeds.py -> enrich_wikidata.py -> import_hcm.py -> build_db.py")


if __name__ == "__main__":
    main()
