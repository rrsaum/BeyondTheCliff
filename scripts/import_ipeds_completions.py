#!/usr/bin/env python3
"""Import IPEDS Completions into a program-breadth time series (data/program_year.csv).

The IPEDS Completions (C) survey lists, per institution per year, every CIP program that produced
an award. This importer reduces each year to how many distinct 4-digit CIP programs an institution
graduated students in (n_programs), and how many it ADDED and DROPPED versus its prior reported
year (n_added, n_dropped) -- the quantitative half of the "you must replace what you cut" thesis.

Program identity is the 4-digit CIP family (e.g. "01.09"), which is more stable across the 2011 and
2021 CIP recodings than the 6-digit detail; the grand-total code 99 and second-major rows are
excluded, and only CIP codes with at least one award (CTOTALT > 0) count as "offered that year".

Keyed on UNITID -> our institution id (OPEID). Reads c<year>_a.csv from uploads/data/
ipeds_completions/ (gitignored raw data). We hold CIP sets only for OUR institutions, so memory
stays bounded. Standard library only.

Caveat (documented, not silently corrected): CIP was recoded in 2011 and 2021, so n_added/n_dropped
spike artificially across those boundaries. n_programs itself is robust. Analyses should skip the
2010->2011 and 2020->2021 transitions when reading added/dropped.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
C_DIR = ROOT / "uploads" / "data" / "ipeds_completions"
URL = "https://nces.ed.gov/ipeds/datacenter/data/C{year}_A.zip"
OUT_FIELDS = [
    "institution_id",
    "year",
    "n_programs",
    "n_added",
    "n_dropped",
    "source",
    "source_url",
]


def unitid_to_id() -> dict[str, str]:
    m = {}
    for name in ("institutions.csv", "institutions_open.csv"):
        p = DATA / name
        if not p.exists():
            continue
        with p.open(encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                u = (r.get("unitid") or "").strip()
                if u and u not in m:
                    m[u] = r["id"].strip()
    return m


def main() -> None:
    if not C_DIR.exists():
        raise SystemExit(f"Completions data dir not found: {C_DIR}")
    u2id = unitid_to_id()
    # sets[id][year] = {4-digit CIP families with a graduate}
    sets: dict[str, dict[int, set[str]]] = {}
    files = sorted(C_DIR.glob("c*_a.csv"))
    for path in files:
        m = re.match(r"c(\d{4})_a\.csv", path.name)
        if not m:
            continue
        year = int(m.group(1))
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            header = [h.strip().upper() for h in next(reader)]
            idx = {h: i for i, h in enumerate(header)}
            need = {"UNITID", "CIPCODE", "MAJORNUM", "CTOTALT"}
            if not need <= set(idx):
                continue
            ui, ci, mj, ct = idx["UNITID"], idx["CIPCODE"], idx["MAJORNUM"], idx["CTOTALT"]
            for row in reader:
                if ct >= len(row):
                    continue
                iid = u2id.get(row[ui].strip())
                if not iid:
                    continue
                if (row[mj].strip() or "1") != "1":  # first major only
                    continue
                cip = row[ci].strip().strip('"')
                if not cip or cip.startswith("99"):  # 99 = grand total / undesignated
                    continue
                try:
                    if int(float(row[ct] or 0)) <= 0:
                        continue
                except ValueError:
                    continue
                fam = cip[:5]  # 4-digit CIP family, e.g. "01.09"
                sets.setdefault(iid, {}).setdefault(year, set()).add(fam)

    out = []
    for iid, byyear in sets.items():
        prevset: set[str] | None = None
        for y in sorted(byyear):
            cur = byyear[y]
            if prevset is None:
                added: int | str = ""  # first observed year: no baseline
                dropped: int | str = ""
            else:
                added = len(cur - prevset)
                dropped = len(prevset - cur)
            out.append(
                {
                    "institution_id": iid,
                    "year": y,
                    "n_programs": len(cur),
                    "n_added": added,
                    "n_dropped": dropped,
                    "source": f"IPEDS C{y}_A",
                    "source_url": URL.format(year=y),
                }
            )
            prevset = cur

    out.sort(key=lambda r: (r["institution_id"], r["year"]))
    with (DATA / "program_year.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(out)

    yrs = sorted({r["year"] for r in out})
    print(
        f"Completions files read: {len(files)}; program-year rows: {len(out)} across "
        f"{len(sets)} institutions, years {yrs[0] if yrs else '-'} to {yrs[-1] if yrs else '-'}"
    )
    print("Next: python3 scripts/build_db.py")


if __name__ == "__main__":
    main()
