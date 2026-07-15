#!/usr/bin/env python3
"""Add closures from authoritative state higher-education closed-college lists that we do not
already track: the New Jersey Office of the Secretary of Higher Education and the Michigan
Association of Collegiate Registrars and Admissions Officers (MACRAO).

These are mostly older, smaller New Jersey and Michigan closures and consolidations that federal
data (which our set is built from) never captured. We cite each to its state source. They predate
IPEDS, so they take a MAN-#### id with no OPEID or financial profile; control, level, and cause
are left blank rather than guessed, and the successor institution a state list notes (where a
records-location column names a college) is recorded in the note, not asserted as a merger. Each
is entered as status=closed, faithful to how the source categorizes it; reclassify in the edit
panel if a specific one was really a merger.

Dedup uses the shared tiered matcher, so re-running is a no-op. Dry run by default; --commit
appends to data/manual_closures.csv. Then run build_db.py. Standard library only.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from import_hechinger import build_dedup, is_present  # noqa: E402

MANUAL = ROOT / "data" / "manual_closures.csv"
MANUAL_FIELDS = ["id", "opeid", "name", "control", "level", "city", "state", "status",
                 "status_year", "closure_type", "parent_name", "cause", "notes", "source_url"]

NJ_URL = "https://www.nj.gov/highereducation/colleges/closed_renamed.shtml"
MI_URL = "https://www.macrao.org/closed-michigan-colleges"

# (name, year, successor-or-records-location) from the NJ "CLOSED" table (the "renamed" table is
# rebrands of operating schools and is deliberately excluded).
NJ = [
    ("Yeshiva Chayei Olam", "2018", ""), ("Bloomfield College", "2024", "Montclair State University"),
    ("Alma White College", "1978", "Pillar College"), ("Alphonsus College", "1974", "Seton Hall University"),
    ("Bayonne Junior College", "1951", ""), ("Bergen Junior College", "1954", "Fairleigh Dickinson University"),
    ("College of South Jersey", "1950", "Rowan"), ("Cumberland County College", "2019", "Rowan College of South Jersey"),
    ("Don Bosco College", "1990", ""), ("Englewood Cliffs College", "1974", "Saint Peter's University"),
    ("Essex Junior College", "1937", "Kean University"), ("Gibbs College", "2010", "Sanford-Brown Institute"),
    ("Immaculate Conception Seminary", "1986", "Felician College"), ("ITT Technical Institute", "2016", ""),
    ("Jersey City Junior College", "1959", ""), ("John Marshall College", "1950", "Seton Hall University"),
    ("Law School of South Jersey", "1949", "Rutgers University"), ("Luther College of Bible", "1978", ""),
    ("Maryknoll Junior College", "1954", ""), ("Mother Savior Seminary", "1961", ""),
    ("Mount Saint Mary College", "1970", "Georgian Court University"), ("Northeastern Bible College", "1990", "The King's College"),
    ("Panzer College of Physical Education", "1958", "Montclair State University"), ("Saint Gabriel's College", "1968", "Iona College"),
    ("Saint Joseph's College", "1970", ""), ("Saint Michael's Monastery", "1984", ""),
    ("Salesian College", "1973", ""), ("Shelton College", "1971", ""), ("Tombrock College", "1976", ""),
    ("Trenton Junior College", "1967", "Mercer County Community College"), ("Union College", "1982", "Union College of Union County"),
    ("University of Medicine & Dentistry of New Jersey", "2013", "Rutgers University"), ("University of Newark", "1947", "Rutgers University"),
    ("Upsala College", "1995", "Felician University"), ("Villa Walsh Junior College", "1971", ""),
    ("Westminster Choir College", "1992", "Rider University"),
]
MI = [
    ("Ava Maria College", ""), ("Ave Maria School of Law", ""), ("Chrysler Institute of Engineering", "1988"),
    ("Convent of the Sacred Heart", ""), ("Delima Junior College", "1970"), ("D'Etre University", "1992"),
    ("Detroit Bible College", "2004"), ("Detroit Engineering Institute", "1989"), ("Detroit Institute of Technology", "1982"),
    ("Duns Scotus College", ""), ("Grand Rapids School of Bible & Music", "1993"), ("Great Lakes College", ""),
    ("Highland Park Community College", "1996"), ("Institute of Merchandising and Design", ""),
    ("Jackson Business Institute", "1994"), ("John Wesley College", "1980"), ("Jordan College", "1995"),
    ("Jordan Seminary", "1955"), ("Lansing Business Institute", ""), ("Lewis College of Business", ""),
    ("Mackinac College", "1973"), ("Maryglade College", "1973"), ("Mercy Central School of Nursing", ""),
    ("Mercy College", ""), ("Merrill-Palmer Institute", ""), ("Michigan Lutheran College", "1983"),
    ("Muskegon Business College", ""), ("Nazareth College", "1992"), ("Owosso Bible College", ""),
    ("Pontiac Business Institute", "1990"), ("Saginaw Business Institute", ""), ("Shaw College at Detroit", "1983"),
    ("St. Johns Provincial Seminary", "1988"), ("St. Mary's College", "2002"), ("William Tyndale College", "2004"),
]


def read(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        r = csv.DictReader(fh)
        return list(r.fieldnames or []), list(r)


def main() -> None:
    commit = "--commit" in sys.argv
    exact, dis8, full, opeids, max_man = build_dedup()
    man = max_man
    proposals = []
    for state, items, url, src in (("NJ", NJ, NJ_URL, "NJ Office of the Secretary of Higher Education"),
                                   ("MI", MI, MI_URL, "Michigan MACRAO")):
        for it in items:
            name = it[0]
            year = it[1]
            successor = it[2] if len(it) > 2 else ""
            if is_present(name, state, exact, dis8, full):
                continue
            man += 1
            note = f"Closure per the {src} closed-college list."
            if successor:
                note += f" Records/successor: {successor}."
            proposals.append({
                "id": f"MAN-{man:04d}", "opeid": "", "name": name, "control": "", "level": "",
                "city": "", "state": state, "status": "closed",
                "status_year": year if re.fullmatch(r"\d{4}", year or "") else "",
                "closure_type": "institutional", "parent_name": "", "cause": "",
                "notes": note, "source_url": url,
            })

    print(f"NJ + MI missing to add: {len(proposals)}")
    for p in proposals[:8]:
        print(f"  {p['id']} | {p['name']} | {p['state']} | {p['status_year'] or '----'}")
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
