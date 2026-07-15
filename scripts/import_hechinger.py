#!/usr/bin/env python3
"""Reconcile the Hechinger Report college-closure list against our data, and add the closures
we are missing.

Source: https://hechingerreport.org/tracking-college-closures/ (exported as a CSV with columns
School Name, State, Program Length, School Type, Year of Closure). Hechinger is a nonprofit
newsroom; we cite it as the source for each added closure's existence and year. Where a row also
resolves to a unique, already-CLOSED IPEDS institution, we attach that federal OPE ID (and take
its city / control / level from IPEDS); otherwise the row is a hand-curated MAN-#### entry whose
control and level come from Hechinger's own columns. We never attach an OPEID that IPEDS lists as
still open (that would almost always be a different, living school) so a wrong OPEID can never
pull the wrong Scorecard profile.

Matching is deliberately conservative to avoid both false duplicates and false additions:
  present if  (a) exact normalized name + state already in our data (current or former names), or
              (b) a same-state record shares a non-empty set of DISTINCTIVE tokens (stop words
                  like "school", "college", "academy" removed) that subsets either way, or
              (c) one normalized full name contains the other (length-guarded), same state.
Rows whose name is entirely generic (no distinctive token) only count as present on an exact
name+state hit, and are flagged for review.

Usage:
    python3 scripts/import_hechinger.py "<path to Hechinger CSV>"            # dry run + review file
    python3 scripts/import_hechinger.py "<path to Hechinger CSV>" --commit   # also append rows
Standard library only (plus the shared IPEDS index).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.ipeds_index import get_index, normalize  # noqa: E402

DATA = ROOT / "data"
MANUAL = DATA / "manual_closures.csv"
REVIEW = ROOT / "scripts" / "_hechinger_review.csv"
SOURCE_URL = "https://hechingerreport.org/tracking-college-closures/"

STATE = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Washington D.C.": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY",
    "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
    "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
    "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    "Puerto Rico": "PR",
}
CONTROL = {"Private,for profit": "private_forprofit", "Private,nonprofit": "private_nonprofit",
           "Public": "public"}
LEVEL = {
    "Bachelor's degree": "4yr", "Doctor's Degree": "4yr", "Master's Degree": "4yr",
    "Master's Degree or Doctor's Degree": "4yr", "First professional degree": "4yr",
    "Graduate/Professional": "4yr", "Associate degree": "2yr", "Non-degree": "lt2yr",
    "Non-degree, 1 year": "lt2yr", "Non-degree, 2 years": "lt2yr",
    "Non-degree, 3-plus years": "lt2yr", "Short term": "lt2yr",
}
STOP = {"OF", "THE", "AND", "A", "AT", "SCHOOL", "SCHOOLS", "COLLEGE", "COLLEGES", "INSTITUTE",
        "INSTITUTES", "ACADEMY", "ACADEMIES", "CAREER", "CAREERS", "CENTER", "CENTERS", "INC",
        "CAMPUS", "UNIVERSITY", "TRAINING", "EDUCATION"}
MANUAL_FIELDS = ["id", "opeid", "name", "control", "level", "city", "state", "status",
                 "status_year", "closure_type", "parent_name", "notes", "source_url"]


def distinctive(name: str) -> set:
    return {t for t in normalize(name).split() if t not in STOP}


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        r = csv.DictReader(fh)
        return list(r.fieldnames or []), list(r)


def build_dedup():
    """Indexes of what we already track, keyed for the three match tiers. Includes former names
    (institution_name) carried at their owning institution's state."""
    _, insts = read_csv(DATA / "institutions.csv")
    _, manual = read_csv(MANUAL)
    _, names = read_csv(DATA / "names.csv")
    rows = insts + manual
    id2state = {(r.get("id") or "").strip(): (r.get("state") or "").strip().upper() for r in rows}

    exact, dis8, full, opeids = set(), {}, {}, set()
    max_man = 0

    def add(name, state):
        nn = normalize(name)
        exact.add((nn, state))
        d = distinctive(name)
        if d:
            dis8.setdefault(state, []).append(d)
        full.setdefault(state, []).append(nn)

    for r in rows:
        st = (r.get("state") or "").strip().upper()
        add(r.get("name") or "", st)
        op = (r.get("opeid") or "").strip()
        if op:
            opeids.add(op)
        rid = (r.get("id") or "").strip()
        if rid.startswith("MAN-") and rid[4:].isdigit():
            max_man = max(max_man, int(rid[4:]))
    for n in names:
        add(n.get("name") or "", id2state.get((n.get("institution_id") or "").strip(), ""))
    return exact, dis8, full, opeids, max_man


def is_present(name, state, exact, dis8, full) -> bool:
    nn = normalize(name)
    if (nn, state) in exact:
        return True
    d = distinctive(name)
    if d:
        for dd in dis8.get(state, []):
            if d <= dd or dd <= d:
                return True
    if len(nn) >= 8:
        for fn in full.get(state, []):
            if len(fn) >= 8 and (nn in fn or fn in nn):
                return True
    return False


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: import_hechinger.py <hechinger.csv> [--commit]")
    src = Path(sys.argv[1])
    commit = "--commit" in sys.argv[2:]
    _, grid = read_csv(src)
    if not grid:
        raise SystemExit(f"no rows read from {src}")

    exact, dis8, full, opeids, max_man = build_dedup()
    idx = get_index()

    present = 0
    proposals: list[dict] = []
    seen: set = set()
    man = max_man
    counts = {"opeid": 0, "man": 0, "generic": 0, "ipeds_no_closedate": 0, "dup_in_grid": 0}

    for r in grid:
        name = (r.get("School Name") or "").strip()
        st = STATE.get((r.get("State") or "").strip(), "")
        year = (r.get("Year of Closure") or "").strip()
        if not name or not st:
            continue
        if is_present(name, st, exact, dis8, full):
            present += 1
            continue
        key = (normalize(name), st, year)
        if key in seen:
            counts["dup_in_grid"] += 1
            continue
        seen.add(key)

        flags = []
        if not distinctive(name):
            flags.append("generic-name")
            counts["generic"] += 1

        # resolve() only returns on a UNIQUE, EXACT normalized-name + state match, so a hit is
        # the same institution (coincidental collisions were verified to be zero). IPEDS's
        # "open" flag is unreliable for schools that simply vanished from later directories
        # without a CLOSEDAT, so we do NOT withhold the OPEID on that basis; Hechinger is the
        # authority for the closure and its year, IPEDS for the identity.
        rec, _ = idx.resolve(name, st, "")
        if rec and rec["opeid"] in opeids:
            present += 1  # already tracked under this OPEID (another name)
            continue

        if rec:
            inst_id = opeid = rec["opeid"]
            city, control, level = rec["city"].title(), rec["control"], rec["level"]
            parent = rec["opeid"][:6] + "00"
            ctype = "campus" if (parent in idx.open_opeids and parent != rec["opeid"]) else "institutional"
            src_note = "OPEID, city, and sector from IPEDS."
            if rec["is_open"]:
                src_note += " IPEDS has not recorded a closure date for this OPEID; closure and year per Hechinger."
                counts["ipeds_no_closedate"] += 1
            counts["opeid"] += 1
        else:
            man += 1
            inst_id, opeid, city = f"MAN-{man:04d}", "", ""
            control = CONTROL.get((r.get("School Type") or "").strip(), "")
            level = LEVEL.get((r.get("Program Length") or "").strip(), "")
            ctype = "institutional"
            src_note = "No federal OPEID match; control/level from the Hechinger dataset."
            counts["man"] += 1

        note = f"Closure from the Hechinger Report college-closure tracker (year {year}). {src_note}"
        if flags:
            note += f" [{', '.join(flags)}]"
        proposals.append({
            "id": inst_id, "opeid": opeid, "name": name, "control": control, "level": level,
            "city": city, "state": st, "status": "closed", "status_year": year,
            "closure_type": ctype, "parent_name": "", "notes": note, "source_url": SOURCE_URL,
        })

    with REVIEW.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MANUAL_FIELDS)
        w.writeheader()
        w.writerows(proposals)

    print(f"Hechinger rows read: {len(grid)}")
    print(f"  already present: {present}")
    print(f"  to add:          {len(proposals)}  "
          f"(OPEID-matched {counts['opeid']}, MAN {counts['man']})")
    print(f"  skipped dup within source: {counts['dup_in_grid']}; "
          f"generic-name flagged: {counts['generic']}; OPEID attached despite no IPEDS close-date: {counts['ipeds_no_closedate']}")
    print(f"Review file: {REVIEW.relative_to(ROOT)}")

    if commit and proposals:
        fields, existing = read_csv(MANUAL)
        with MANUAL.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(existing + [{k: p.get(k, "") for k in fields} for p in proposals])
        print(f"APPENDED {len(proposals)} rows to {MANUAL.relative_to(ROOT)}. "
              f"Next: python3 scripts/build_db.py")
    elif not commit:
        print("DRY RUN (no --commit): nothing written to manual_closures.csv yet.")


if __name__ == "__main__":
    main()
