#!/usr/bin/env python3
"""Add historical defunct colleges from the Lost Colleges archive (lostcolleges.com) that we do
not already track, as a labeled historical layer.

The tracker is a cross-era failure post-mortem, so it carries the long tail of colleges that
closed long before federal data existed. Lost Colleges is a curated archive of defunct U.S.
colleges; we cite it, and deep-link each row to its per-college page. These predate IPEDS, so
they take a MAN-#### id with no OPEID or financial profile; founding/closure year, control,
level, and cause are left blank (not guessed). Because their year is blank they fall below the
2004 floor on the modern cliff charts (see app/queries.py _filters), so they enrich the record
and totals without distorting the modern view.

Input is the rendered by-state HTML (uploads/data/lostcolleges.html, git-ignored). States are
UPPERCASE bold headers; each college is a link. We walk the document, track the current state,
and assign each college to it. Dedup uses the shared tiered matcher, so a college already tracked
(under any name) is skipped and a re-run is a no-op. Dry run by default; --commit appends to
data/manual_closures.csv. Standard library only.
"""
from __future__ import annotations

import csv
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from import_hechinger import build_dedup, is_present  # noqa: E402

SRC = ROOT / "uploads" / "data" / "lostcolleges.html"
MANUAL = ROOT / "data" / "manual_closures.csv"
STATES = ["ALABAMA", "ALASKA", "ARIZONA", "ARKANSAS", "CALIFORNIA", "COLORADO", "CONNECTICUT",
          "DELAWARE", "DISTRICT OF COLUMBIA", "FLORIDA", "GEORGIA", "HAWAII", "IDAHO", "ILLINOIS",
          "INDIANA", "IOWA", "KANSAS", "KENTUCKY", "LOUISIANA", "MAINE", "MARYLAND",
          "MASSACHUSETTS", "MICHIGAN", "MINNESOTA", "MISSISSIPPI", "MISSOURI", "MONTANA",
          "NEBRASKA", "NEVADA", "NEW HAMPSHIRE", "NEW JERSEY", "NEW MEXICO", "NEW YORK",
          "NORTH CAROLINA", "NORTH DAKOTA", "OHIO", "OKLAHOMA", "OREGON", "PENNSYLVANIA",
          "RHODE ISLAND", "SOUTH CAROLINA", "SOUTH DAKOTA", "TENNESSEE", "TEXAS", "UTAH",
          "VERMONT", "VIRGINIA", "WASHINGTON", "WEST VIRGINIA", "WISCONSIN", "WYOMING"]
ABBR = {s: a for s, a in zip(STATES, [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
    "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
    "VT", "VA", "WA", "WV", "WI", "WY"])}
MANUAL_FIELDS = ["id", "opeid", "name", "control", "level", "city", "state", "status",
                 "status_year", "closure_type", "parent_name", "cause", "notes", "source_url"]


def parse(text: str) -> list[tuple]:
    """Return (name, state, url) in document order, each college assigned to the preceding state
    header."""
    events = []
    for s in STATES:
        for m in re.finditer(r"font-weight:bold[^>]*>(?:\s|&nbsp;|<[^>]+>)*" + re.escape(s)
                             + r"(?![A-Z])", text):
            events.append((m.start(), "STATE", s))
    for m in re.finditer(r'<a[^>]*href="(https://www\.lostcolleges\.com/[^"]*)"[^>]*>(.*?)</a>',
                         text, re.S):
        nm = html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        if len(nm) >= 3 and re.search(r"[A-Za-z]{3}", nm):
            events.append((m.start(), "COLL", (nm, m.group(1))))
    events.sort(key=lambda e: e[0])
    cur, out, seen = None, [], set()
    for _, typ, val in events:
        if typ == "STATE":
            cur = ABBR[val]
        elif cur:
            nm, url = val
            key = (nm.lower(), cur)
            if key not in seen:
                seen.add(key)
                out.append((nm, cur, url))
    return out


def read(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        r = csv.DictReader(fh)
        return list(r.fieldnames or []), list(r)


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing input {SRC}")
    commit = "--commit" in sys.argv
    colleges = parse(SRC.read_text(encoding="utf-8", errors="replace"))
    exact, dis8, full, opeids, max_man = build_dedup()
    man = max_man
    proposals = []
    present = 0
    for name, state, url in colleges:
        if is_present(name, state, exact, dis8, full):
            present += 1
            continue
        man += 1
        proposals.append({
            "id": f"MAN-{man:04d}", "opeid": "", "name": name, "control": "", "level": "",
            "city": "", "state": state, "status": "closed", "status_year": "",
            "closure_type": "institutional", "parent_name": "", "cause": "",
            "notes": "Historical defunct college from the Lost Colleges archive; founding/closure "
                     "year and cause not yet coded.",
            "source_url": url,
        })

    print(f"Lost Colleges parsed: {len(colleges)} | already tracked: {present} | to add: {len(proposals)}")
    for p in proposals[:6]:
        print(f"  {p['id']} | {p['name']} | {p['state']}")
    if commit and proposals:
        fields, existing = read(MANUAL)
        with MANUAL.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(existing + [{k: p.get(k, "") for k in fields} for p in proposals])
        print(f"APPENDED {len(proposals)} rows to {MANUAL.name}. Next: build_db.py")
    else:
        print("DRY RUN (no --commit).")


if __name__ == "__main__":
    main()
