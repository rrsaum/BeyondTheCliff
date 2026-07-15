#!/usr/bin/env python3
"""Add the `cause` column to the institution CSVs and code a primary cause of failure from each
row's already-sourced `notes`, conservatively.

The tracker is a post-mortem on why institutions fail, so closures carry a primary cause drawn
from a fixed taxonomy. We do not originate causes: this only classifies what a row's own
(sourced) note already states, using explicit phrase matches, and leaves `cause` blank wherever
the note does not clearly say why. Blank means "not yet coded", not "no cause". New closures get
a hand-picked cause through the browser form; any row can be corrected in the edit panel.

Idempotent: adds the column if missing and only fills a blank cause. Run, then build_db.py.
Standard library only.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
FILES = [DATA / "institutions.csv", DATA / "manual_closures.csv"]

# Ordered rules: the FIRST cause whose any phrase appears in the lower-cased note wins. The
# distinctive causes are checked before the generic financial/enrollment ones, and enrollment
# is checked before financial so a note naming both is coded to the demographic root cause.
RULES = [
    ("misconduct", ["fraud", "scandal", "misled", "deceptive", "deceiv", "indict",
                     "criminal", "mismanagement", "embezzl", "corinthian", "falsified"]),
    ("accreditation", ["accreditation withdrawn", "lost its accreditation", "lost accreditation",
                       "withdrawal of accreditation", "loss of accreditation", "revoked accreditation",
                       "denied accreditation", "withdraw its accreditation", "lost accreditor",
                       "accreditation was withdrawn"]),
    ("disaster", ["hurricane", "wildfire", "flood", "earthquake", "tornado", " fire "]),
    ("external", ["pandemic", "covid", "world war", "great depression"]),
    ("sponsor", ["diocese", "archdiocese", "religious order", "sisters of", "society of jesus",
                 "synod", "sponsoring order", "the church withdrew"]),
    ("restructuring", ["restructur", "reorganiz", "passhe", "state university system",
                       "public system consolidation", "system realignment"]),
    ("enrollment", ["declining enrollment", "enrollment decline", "enrollment cliff", "demographic",
                    "dwindling enrollment", "falling enrollment", "low enrollment",
                    "drop in enrollment", "enrollment challenges"]),
    ("financial", ["financ", "insolven", "insufficient finan", "rescue fund", "budget deficit",
                   "mounting debt", " debt", "deficit", "fiscal", "bankrupt", "could no longer",
                   "money", "revenue shortfall", "endowment"]),
]


def classify(note: str) -> str:
    low = (note or "").lower()
    # Accreditation stated in any word order (e.g. "accreditation withdrawal", "withdrew its
    # accreditation", "lost accreditation") beats the generic financial/enrollment fallback.
    if "accreditation" in low and any(w in low for w in
                                      ("withdr", "lost", "revok", "lose", "denied", "loss")):
        return "accreditation"
    for cause, phrases in RULES:
        if any(p in low for p in phrases):
            return cause
    return ""


def main() -> None:
    total_coded = 0
    dist: dict[str, int] = {}
    for path in FILES:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
        if "cause" not in fields:
            fields.insert(fields.index("notes") if "notes" in fields else len(fields), "cause")
        coded = 0
        for r in rows:
            if not (r.get("cause") or "").strip() and (r.get("status") or "") in ("closed", "merged", "announced"):
                c = classify(r.get("notes", ""))
                if c:
                    r["cause"] = c
                    coded += 1
                    dist[c] = dist.get(c, 0) + 1
            r.setdefault("cause", "")
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print(f"{path.name}: coded {coded} of {len(rows)} rows")
        total_coded += coded

    print(f"\nTotal newly coded: {total_coded}")
    for c, n in sorted(dist.items(), key=lambda kv: -kv[1]):
        print(f"  {c:14} {n}")
    print("(rows without a cause phrase in their note stay blank = not yet coded)")
    print("Next: python3 scripts/build_db.py")


if __name__ == "__main__":
    main()
