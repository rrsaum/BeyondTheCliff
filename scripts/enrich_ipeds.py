#!/usr/bin/env python3
"""Enrich the tracker with IPEDS data from NCES: the OPEID -> UnitID crosswalk, 12-month
enrollment, and the HBCU / religious-affiliation flags IPEDS carries.

Why NCES directly: the Urban Institute API host does not resolve from here, but NCES does.
Files are pulled from the IPEDS Data Center (one zip per survey per year) into a local,
git-ignored cache (data/ipeds_cache/), so re-runs are fast and offline.

What it does, honestly scoped:
  - Unions HD (directory) files across YEARS into an OPEID -> UnitID crosswalk. One year
    only covers ~half our closures (schools closed far from that year are not in the
    snapshot), so the union across 2004 to 2020 lifts the match rate.
  - Fills the `unitid` column in data/institutions.csv for matched institutions, and adds
    `hbcu` / `religious` characteristic tags where IPEDS flags them.
  - Reads EFFY (12-month enrollment) files across YEARS and writes total / undergrad /
    graduate headcount per institution per year into data/enrollment.csv, sourced to IPEDS.

NOTE: founding year is NOT in IPEDS (verified: the only year fields are open-to-public and
closure date). This script does not invent one. Founding year is a separate, best-effort
enrichment from Wikidata or manual entry.

Run:  python3 scripts/enrich_ipeds.py   (then: python3 scripts/build_db.py)
Standard library only.
"""
from __future__ import annotations

import csv
import re
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

_DATE_RE = re.compile(r"\d{2}/\d{2}/\d{4}")  # IPEDS CLOSEDAT is MM/DD/YYYY when closed

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "ipeds_cache"
YEARS = range(2004, 2025)  # SHEEO covers 2004-2020; HD/EFFY through 2024 cover recent closures
BASE_URL = "https://nces.ed.gov/ipeds/datacenter/data"
UA = {"User-Agent": "BeyondTheCliff-research/1.0 (higher-ed closure research)"}

# IPEDS HD HLOFFER: highest level of offering -> readable "highest award offered".
HLOFFER_LABEL = {
    "1": "Certificate (under 1 year)", "2": "Certificate (1 to 2 years)",
    "3": "Associate's", "4": "Award (2 to 4 years)", "5": "Bachelor's",
    "6": "Postbaccalaureate certificate", "7": "Master's",
    "8": "Post-master's certificate", "9": "Doctorate",
}


def fetch_csv(kind: str, year: int) -> list[str] | None:
    """Download {kind}{year}.zip (cached) and return its CSV lines, or None if unavailable."""
    fname = f"{kind}{year}"
    zpath = CACHE / f"{fname}.zip"
    if not zpath.exists():
        url = f"{BASE_URL}/{fname}.zip"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as resp:
                zpath.write_bytes(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            return None
    try:
        z = zipfile.ZipFile(zpath)
    except zipfile.BadZipFile:
        return None
    name = next((n for n in z.namelist() if n.lower().endswith(".csv")), None)
    if not name:
        return None
    raw = z.read(name)
    try:
        text = raw.decode("utf-8-sig")  # strips the BOM recent HD files carry
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")
    return text.splitlines()


def upper_reader(lines: list[str]):
    """DictReader whose keys are upper-cased (IPEDS varies case across years)."""
    reader = csv.reader(lines)
    header = [h.strip().upper() for h in next(reader)]
    for row in reader:
        yield dict(zip(header, row))


def build_crosswalk() -> tuple[dict, dict, set]:
    """From HD directory files: an exact 8-digit OPEID -> UnitID map, a 6-digit-prefix ->
    {UnitIDs} map (for a fallback when the exact branch OPEID is not in IPEDS), and the set
    of HBCU UnitIDs. Later years win on the exact map."""
    crosswalk, prefix, hbcu, hloffer = {}, {}, set(), {}
    closedat, opeid_name = {}, {}  # latest-year status + name per OPEID, for closure typing
    years_seen = []
    for year in YEARS:
        lines = fetch_csv("HD", year)
        if not lines:
            continue
        years_seen.append(year)
        for row in upper_reader(lines):
            opeid = (row.get("OPEID") or "").strip()
            unitid = (row.get("UNITID") or "").strip()
            if opeid:
                closedat[opeid] = (row.get("CLOSEDAT") or "").strip()  # later year wins
                nm = (row.get("INSTNM") or "").strip()
                if nm:
                    opeid_name[opeid] = nm
            if opeid and unitid:
                crosswalk[opeid] = unitid
                if len(opeid) >= 6:
                    prefix.setdefault(opeid[:6], set()).add(unitid)
                if (row.get("HBCU") or "").strip() == "1":
                    hbcu.add(unitid)
                hl = (row.get("HLOFFER") or "").strip()
                if hl in HLOFFER_LABEL:  # later year wins (keeps the most recent offering)
                    hloffer[unitid] = hl
    open_opeids = {op for op, cd in closedat.items() if not _DATE_RE.match(cd)}
    print(f"HD years fetched: {years_seen[0]}-{years_seen[-1]} ({len(years_seen)} files), "
          f"crosswalk OPEIDs: {len(crosswalk)}")
    return crosswalk, prefix, hbcu, hloffer, open_opeids, opeid_name


def resolve_unitid(opeid: str, crosswalk: dict, prefix: dict) -> tuple[str | None, str | None]:
    """Return (unitid, confidence). Exact 8-digit match preferred. Otherwise fall back to
    the 6-digit institution prefix, but ONLY when it is unambiguous (the prefix maps to
    exactly one UnitID) or a clear parent branch (xxxxxx00) exists, so we never silently
    attach the wrong branch's enrollment. Ambiguous prefixes are left unmatched."""
    if opeid in crosswalk:
        return crosswalk[opeid], "exact"
    if len(opeid) >= 6:
        parent = opeid[:6] + "00"
        if parent in crosswalk:
            return crosswalk[parent], "prefix"
        candidates = prefix.get(opeid[:6], set())
        if len(candidates) == 1:
            return next(iter(candidates)), "prefix"
    return None, None


def build_religious() -> set:
    """UnitIDs with a positive RELAFFIL (religiously affiliated) from IC files. This is a
    yes/no flag: the RELAFFIL denomination code -> name map lives in the IPEDS value-label
    dictionary and is a later enrichment, so we do not guess a denomination here."""
    religious = set()
    for year in YEARS:
        lines = fetch_csv("IC", year)
        if not lines:
            continue
        for row in upper_reader(lines):
            unitid = (row.get("UNITID") or "").strip()
            relaff = (row.get("RELAFFIL") or "").strip()
            if unitid and relaff.lstrip("-").isdigit() and int(relaff) > 0:
                religious.add(unitid)
    return religious


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8", newline="") as fh:
        r = csv.DictReader(fh)
        return list(r.fieldnames or []), list(r)


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    crosswalk, prefix, hbcu, hloffer, open_opeids, opeid_name = build_crosswalk()
    religious = build_religious()

    # 1) Fill unitid on the institutions, keyed by OPEID (exact, then unambiguous prefix).
    fields, institutions = read_csv(DATA / "institutions.csv")
    if not institutions:
        raise SystemExit(
            "institutions.csv has no rows. Run scripts/import_sheeo.py first (it builds it "
            "from the SHEEO source); do not run enrich against an empty file."
        )
    # Defensive: make sure the columns we write exist in the header, so a schema drift can
    # never make DictWriter raise mid-write and truncate the file.
    for col in ("unitid", "unitid_match", "closure_type", "parent_name"):
        if col not in fields:
            fields.append(col)
    # unit2inst maps a UnitID to OUR institution id, but ONLY for exact matches. A prefix
    # match resolves a branch to its parent UnitID, so pulling that UnitID's enrollment would
    # attribute the parent's system-wide headcount to one branch. We keep the prefix link for
    # reference (the unitid column) but never source enrollment or flags through it.
    unit2inst: dict[str, str] = {}
    exact = prefixed = campus = institutional = 0
    for inst in institutions:
        opeid = (inst.get("opeid") or "").strip()
        uid, conf = resolve_unitid(opeid, crosswalk, prefix)
        if uid:
            inst["unitid"] = uid
            inst["unitid_match"] = conf
            if conf == "exact":
                unit2inst[uid] = inst["id"]
                if uid in hloffer:
                    inst["degrees"] = HLOFFER_LABEL[hloffer[uid]]
                exact += 1
            else:
                prefixed += 1
        # Campus vs institutional closure: an OPEID whose parent (prefix + "00") is still
        # open in IPEDS is a campus/branch closure; the institution itself lives on.
        if inst.get("status") == "closed" and opeid:
            parent = opeid[:6] + "00"
            if parent in open_opeids and parent != opeid:
                inst["closure_type"] = "campus"
                inst["parent_name"] = opeid_name.get(parent, "")
                campus += 1
            else:
                inst["closure_type"] = "institutional"
                institutional += 1
    write_csv(DATA / "institutions.csv", fields, institutions)
    print(f"institutions linked to a UnitID: {exact + prefixed}/{len(institutions)} "
          f"[exact {exact}, prefix {prefixed}]. Enrollment/flags attributed to exact only.")
    print(f"closure type: {institutional} institutional, {campus} campus (parent survives)")

    # 2) HBCU / religious tags for matched institutions (merge, do not duplicate).
    cfields, chars = read_csv(DATA / "characteristics.csv")
    existing = {(c["institution_id"], c["tag"]) for c in chars}
    added = 0
    for uid, inst_id in unit2inst.items():
        for flag, tag in ((hbcu, "hbcu"), (religious, "religious")):
            if uid in flag and (inst_id, tag) not in existing:
                chars.append({"institution_id": inst_id, "tag": tag})
                existing.add((inst_id, tag))
                added += 1
    write_csv(DATA / "characteristics.csv", cfields, chars)
    print(f"IPEDS characteristic tags added (hbcu/religious): {added}")

    # 3) Enrollment: EFFY 12-month headcount per institution per year.
    # EFFYLEV 1 = all students, 2 = undergraduate, 4 = graduate. EFYTOTLT = grand total.
    per: dict[tuple[str, int], dict] = {}
    enroll_years = []
    for year in YEARS:
        lines = fetch_csv("EFFY", year)
        if not lines:
            continue
        enroll_years.append(year)
        for row in upper_reader(lines):
            uid = (row.get("UNITID") or "").strip()
            inst_id = unit2inst.get(uid)
            if not inst_id:
                continue
            lev = (row.get("EFFYLEV") or "").strip()
            total = (row.get("EFYTOTLT") or "").strip()
            if not total.lstrip("-").isdigit():
                continue
            rec = per.setdefault((inst_id, year), {"total": "", "undergrad": "", "graduate": ""})
            if lev == "1":
                rec["total"] = total
            elif lev == "2":
                rec["undergrad"] = total
            elif lev == "4":
                rec["graduate"] = total

    enroll_rows = []
    for (inst_id, year), rec in sorted(per.items()):
        if not any(rec.values()):
            continue
        enroll_rows.append({
            "institution_id": inst_id, "year": year,
            "total_headcount": rec["total"], "undergrad": rec["undergrad"],
            "graduate": rec["graduate"], "fte": "",
            "source": "IPEDS EFFY", "source_url": f"{BASE_URL}/EFFY{year}.zip",
        })
    write_csv(DATA / "enrollment.csv",
              ["institution_id", "year", "total_headcount", "undergrad", "graduate", "fte",
               "source", "source_url"],
              enroll_rows)
    distinct = len({r["institution_id"] for r in enroll_rows})
    print(f"EFFY years fetched: {len(enroll_years)}; enrollment rows: {len(enroll_rows)} "
          f"across {distinct} institutions")
    print("Next: python3 scripts/build_db.py")


if __name__ == "__main__":
    main()
