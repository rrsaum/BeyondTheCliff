#!/usr/bin/env python3
"""Build the roster of currently-operating U.S. institutions from IPEDS HD directory files.

This is the denominator. The tracker is a closure record, so on its own it can only ever say
how many schools closed, never what share of the sector that is. IPEDS HD (the NCES
institutional directory, a federal government work, public domain) is the authoritative list
of who is still standing: every Title IV institution, all sectors, with the CYACTIVE flag NCES
uses to mark an institution as currently active.

    python3 scripts/import_ipeds_roster.py            # preview, writes nothing
    python3 scripts/import_ipeds_roster.py --commit    # write data/institutions_open.csv
    python3 scripts/build_db.py                        # then rebuild

Reuses the cached, BOM-safe fetch helpers in scripts/enrich_ipeds.py, so the HD zips already
under data/ipeds_cache/ are read straight off disk and no network call is made.

Scope, stated honestly:
  - "Open" here means IPEDS marked the institution active in its latest HD collection year.
    It is evidence of operating through that year, not proof of operating today, so the row
    carries status_year = that HD year and the profile reads it as "confirmed open through".
  - An OPEID we already track as closed/merged is NEVER overwritten from here. IPEDS listing
    it as active is a contradiction between two sources, so it goes to the review file instead
    of being silently resolved in either direction.
  - Institutions with no OPEID are not Title IV participants and cannot be keyed in this
    schema. They are written to the review file rather than dropped in silence.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from enrich_ipeds import BASE_URL, HLOFFER_LABEL, YEARS, fetch_csv, upper_reader  # noqa: E402

OPEN_CSV = DATA / "institutions_open.csv"
SIZE_CSV = DATA / "sector_size.csv"
REVIEW_CSV = SCRIPTS / "_roster_review.csv"

OPEN_FIELDS = [
    "id",
    "opeid",
    "unitid",
    "unitid_match",
    "name",
    "control",
    "level",
    "sector_raw",
    "degrees",
    "city",
    "state",
    "status",
    "status_year",
    "source_url",
]
SIZE_FIELDS = ["year", "control", "active", "source", "source_url"]
REVIEW_FIELDS = ["opeid", "unitid", "name", "city", "state", "hd_year", "reason"]

# IPEDS HD codebook values.
CONTROL = {"1": "public", "2": "private_nonprofit", "3": "private_forprofit"}
ICLEVEL = {"1": "4yr", "2": "2yr", "3": "lt2yr"}
SECTOR_LABEL = {
    "0": "Administrative unit",
    "1": "Public 4yr or above",
    "2": "Private nonprofit 4yr or above",
    "3": "Private for-profit 4yr or above",
    "4": "Public 2yr",
    "5": "Private nonprofit 2yr",
    "6": "Private for-profit 2yr",
    "7": "Public <2yr",
    "8": "Private nonprofit <2yr",
    "9": "Private for-profit <2yr",
}


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def latest_hd_year() -> int:
    """The newest HD collection year we can actually read (cache first, no network needed)."""
    for year in sorted(YEARS, reverse=True):
        if (DATA / "ipeds_cache" / f"HD{year}.zip").exists():
            return year
    raise SystemExit("no HD zip in data/ipeds_cache/; run scripts/enrich_ipeds.py first")


@dataclass
class Batch:
    hd_year: int
    rows: list[dict] = field(default_factory=list)  # the open roster to write
    conflicts: list[dict] = field(default_factory=list)  # IPEDS says active, we say closed
    review: list[dict] = field(default_factory=list)  # no OPEID, or otherwise unkeyable
    sizes: list[dict] = field(default_factory=list)  # active count per year per control
    merged_branches: int = 0  # rows folded into a shared OPEID

    def counts(self) -> dict:
        return {
            "hd_year": self.hd_year,
            "open": len(self.rows),
            "conflicts": len(self.conflicts),
            "review": len(self.review),
            "merged_branches": self.merged_branches,
            "sizes": len(self.sizes),
        }


def build_batch(hd_year: int | None = None) -> Batch:
    """Draft the open roster from the latest HD file. Writes nothing."""
    hd_year = hd_year or latest_hd_year()
    lines = fetch_csv("HD", hd_year)
    if not lines:
        raise SystemExit(f"could not read HD{hd_year}")

    tracked: dict[str, dict] = {}
    for name in ("institutions.csv", "manual_closures.csv"):
        for row in _read(DATA / name):
            if row.get("id"):
                tracked[row["id"]] = row

    b = Batch(hd_year=hd_year)
    source_url = f"{BASE_URL}/HD{hd_year}.zip"
    by_opeid: dict[str, dict] = {}

    for r in upper_reader(lines):
        if r.get("CYACTIVE") != "1":  # NCES: not currently active
            continue
        opeid = (r.get("OPEID") or "").strip()
        unitid = (r.get("UNITID") or "").strip()
        name = (r.get("INSTNM") or "").strip()
        if not opeid or not opeid.isdigit():
            b.review.append(
                {
                    "opeid": opeid,
                    "unitid": unitid,
                    "name": name,
                    "city": (r.get("CITY") or "").strip(),
                    "state": (r.get("STABBR") or "").strip(),
                    "hd_year": hd_year,
                    "reason": "IPEDS lists no OPEID: not a Title IV participant, so it "
                    "cannot be keyed in this schema",
                }
            )
            continue
        opeid = opeid.zfill(8)

        if opeid in tracked:
            known = tracked[opeid]
            b.conflicts.append(
                {
                    "opeid": opeid,
                    "unitid": unitid,
                    "name": name,
                    "city": (r.get("CITY") or "").strip(),
                    "state": (r.get("STABBR") or "").strip(),
                    "hd_year": hd_year,
                    "reason": f"we record {known.get('status')} in "
                    f"{known.get('status_year') or 'an unknown year'} as "
                    f'"{known.get("name")}", but IPEDS HD{hd_year} marks this OPEID '
                    "currently active. Check our closure year, or an OPEID reused by a "
                    "different school.",
                }
            )
            continue

        row = {
            "id": opeid,
            "opeid": opeid,
            "unitid": int(unitid) if unitid.isdigit() else "",
            "unitid_match": "exact" if unitid.isdigit() else "",
            "name": name,
            "control": CONTROL.get((r.get("CONTROL") or "").strip(), ""),
            "level": ICLEVEL.get((r.get("ICLEVEL") or "").strip(), ""),
            "sector_raw": SECTOR_LABEL.get((r.get("SECTOR") or "").strip(), ""),
            "degrees": HLOFFER_LABEL.get((r.get("HLOFFER") or "").strip(), ""),
            "city": (r.get("CITY") or "").strip(),
            "state": (r.get("STABBR") or "").strip(),
            "status": "open",
            "status_year": hd_year,
            "source_url": source_url,
        }
        # Branch campuses can share an 8-digit OPEID, which is our primary key. Keep the
        # lowest UnitID (IPEDS assigns it to the parent) so the choice is deterministic, and
        # count the rest rather than let them vanish.
        if opeid in by_opeid:
            b.merged_branches += 1
            if str(row["unitid"] or "9" * 9) < str(by_opeid[opeid]["unitid"] or "9" * 9):
                by_opeid[opeid] = row
        else:
            by_opeid[opeid] = row

    b.rows = sorted(by_opeid.values(), key=lambda x: x["id"])
    return b


def sector_sizes() -> list[dict]:
    """Count active institutions per HD collection year per control: the sector's actual size
    over time, which is the denominator the closure record cannot supply. Every HD year we can
    read is counted, so the series extends itself as new files are cached."""
    rows = []
    for year in sorted(YEARS):
        lines = fetch_csv("HD", year)
        if not lines:
            continue
        counts: dict[str, int] = {}
        for r in upper_reader(lines):
            if r.get("CYACTIVE") != "1":
                continue
            control = CONTROL.get((r.get("CONTROL") or "").strip())
            if control:
                counts[control] = counts.get(control, 0) + 1
        for control, n in sorted(counts.items()):
            rows.append(
                {
                    "year": year,
                    "control": control,
                    "active": n,
                    "source": f"IPEDS HD{year} (NCES)",
                    "source_url": f"{BASE_URL}/HD{year}.zip",
                }
            )
    return rows


def _guard_generated(path: Path, fields: list[str]) -> None:
    """Refuse to overwrite a generated file that has grown a column we cannot regenerate.

    Every file this script writes is rewritten whole from IPEDS, so any column it does not
    produce is destroyed on the next run, silently, and the tracker keeps working afterwards:
    the row is still there and the foreign key still holds, so nothing visibly breaks. That is
    exactly how an EIN hand-added to institutions_open.csv was lost once already. IPEDS does
    not publish EINs, so that column could never survive here; the crosswalk belongs in its own
    hand-curated file (data/institution_eins.csv, table institution_ein) precisely because
    nothing regenerates it.

    Dropped ROWS are not guarded: a school leaving the IPEDS active roster is the signal this
    script exists to record. An unexpected COLUMN carrying data is the signature of curation by
    hand, and that is what must never be quietly thrown away."""
    if not path.exists():
        return
    existing = _read(path)
    if not existing:
        return
    extra = [c for c in existing[0] if c and c not in fields]
    carrying = [c for c in extra if any((row.get(c) or "").strip() for row in existing)]
    if carrying:
        raise SystemExit(
            f"{path.relative_to(ROOT)} carries column(s) this importer cannot regenerate: "
            f"{', '.join(carrying)}. This file is rewritten whole from IPEDS, so committing "
            "would destroy that data. Move it to its own table and hand-curated CSV (see "
            "data/institution_eins.csv for the pattern), then re-run."
        )


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    _guard_generated(path, fields)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows([{k: r.get(k, "") for k in fields} for r in rows])


def commit(hd_year: int | None = None) -> Batch:
    """Rewrite institutions_open.csv and sector_size.csv from IPEDS. Whole-file rewrites, not
    appends: IPEDS is the source of truth for who is open, so a rebuild reflects the latest HD
    exactly. Does NOT rebuild the DB; the caller does."""
    b = build_batch(hd_year)
    _write(OPEN_CSV, OPEN_FIELDS, b.rows)
    b.sizes = sector_sizes()
    _write(SIZE_CSV, SIZE_FIELDS, b.sizes)
    if b.conflicts or b.review:
        _write(REVIEW_CSV, REVIEW_FIELDS, b.conflicts + b.review)
    return b


def _report(b: Batch, committed: bool) -> None:
    c = b.counts()
    print(f"\nIPEDS HD{c['hd_year']} roster (CYACTIVE = currently active)")
    print(f"  open institutions   : {c['open']}")
    print(f"  branch rows folded  : {c['merged_branches']} (shared an 8-digit OPEID)")
    print(f"  source conflicts    : {c['conflicts']} (IPEDS says active, we record closed)")
    print(f"  unkeyable (no OPEID): {c['review']}")
    if b.conflicts or b.review:
        print(f"  review file         : {REVIEW_CSV.relative_to(ROOT)}")
    if committed:
        print(f"  sector-size rows    : {c['sizes']} (active per year per control)")
        print(f"  wrote {OPEN_CSV.relative_to(ROOT)} and {SIZE_CSV.relative_to(ROOT)}")
    else:
        print("\nPreview only. Re-run with --commit to write, then: python3 scripts/build_db.py")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--commit",
        action="store_true",
        help="write data/institutions_open.csv (default previews only)",
    )
    ap.add_argument(
        "--year", type=int, default=None, help="HD collection year to use (default: newest cached)"
    )
    args = ap.parse_args(argv)
    b = commit(args.year) if args.commit else build_batch(args.year)
    _report(b, args.commit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
