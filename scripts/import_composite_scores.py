#!/usr/bin/env python3
"""Import a U.S. Dept. of Education Financial Responsibility Composite Score spreadsheet.

Source: https://studentaid.gov/data-center/school/composite-scores (a federal government work,
public domain). ED publishes one spreadsheet per award year, cut from eZ-Audit, the system
schools file their audited financial statements into. The score is ED's own verdict on whether
a school is financially responsible enough to keep handling Title IV money, which makes it the
closest thing to an official, annual, sector-wide distress signal that exists.

    python3 scripts/import_composite_scores.py <file.xls> [more.xls ...]   # preview only
    python3 scripts/import_composite_scores.py --commit <file.xls> [...]   # write the CSV

Then rebuild: python3 scripts/build_db.py. The browser console at /admin/composite wraps this
same code, so a file loaded there and a file loaded here produce identical rows.

This importer only ever ATTACHES scores to institutions we already track. It never creates an
institution, because it cannot honestly do so:

  - ED scores only PRIVATE NON-PROFIT and PROPRIETARY institutions. Public institutions are
    absent from every one of these files, so this roster is not the sector. The roster of who
    is open comes from IPEDS (scripts/import_ipeds_roster.py); the closure record comes from
    SHEEO and hand curation. Any rate computed from composite scores alone must say so.

  - A school in the 2006-07 file that appears in no later file did not necessarily close. It
    may have merged, been renamed, changed OPEID, or simply left Title IV. Nothing here can
    tell those apart, so an unmatched row goes to scripts/_composite_review.csv for a human to
    adjudicate rather than being invented into a status.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "composite_cache"
SCORES_CSV = DATA / "composite_scores.csv"
REVIEW_CSV = Path(__file__).resolve().parent / "_composite_review.csv"

SOURCE_URL = "https://studentaid.gov/data-center/school/composite-scores"

# studentaid.gov drops a connection that does not present a browser User-Agent (curl's default
# gets no response at all, not a 403), so the fetch below sends one. Verified July 2026.
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
}

# One file per award year. ED has renamed these four times over the years and there is no
# derivable pattern, so the URLs are enumerated rather than constructed. Each was verified to
# return 200 and a real .xls in July 2026. The data-center page itself is an Angular app with
# no server-rendered links, so it cannot be scraped for these; data.ed.gov's CKAN API
# (package_show?id=financial-responsibility-composite-scores) is the machine-readable index and
# is where the 2014-15 file lives, the one year missing from studentaid.gov.
_SAG = "https://studentaid.gov/sites/default/files"
_CKAN = "https://data.ed.gov/dataset/ff51fef3-9d22-49a7-b34b-54329a290307/resource"
SOURCES = {
    "2006-07": f"{_SAG}/0607CompositeScores.xls",
    "2007-08": f"{_SAG}/0708CompositeScores.xls",
    "2008-09": f"{_SAG}/0809CompositeScores.xls",
    "2009-10": f"{_SAG}/0910CompositeScores.xls",
    "2010-11": f"{_SAG}/1011CompositeScores.xls",
    "2011-12": f"{_SAG}/1112CompositeScores.xls",
    "2012-13": f"{_SAG}/1213CompositeScores.xls",
    "2013-14": f"{_SAG}/20132014CompositeScores.xls",
    "2014-15": f"{_CKAN}/c04c1fea-f4ad-4881-b8d1-c76ac1f45793/download/20142015compositescores.xls",
    "2015-16": f"{_SAG}/20152016CompositeScores.xls",
    "2016-17": f"{_SAG}/ay16-17-composite-scores.xls",
    "2017-18": f"{_SAG}/ay17-18-composite-scores.xls",
    "2018-19": f"{_SAG}/ay-18-19-composite-scores.xls",
    "2019-20": f"{_SAG}/ay-19-20-composite-scores.xls",
    "2020-21": f"{_SAG}/ay-20-21-composite-scores.xls",
    "2021-22": f"{_SAG}/ay-21-22-composite-scores.xls",
    "2022-23": f"{_SAG}/ay-22-23-composite-scores.xls",
}
# AY 2023-24 and later are deliberately absent: every plausible filename 404s as of July 2026.
# Do not add one without fetching it first; a guessed URL is not a source.


def fetch(award_year: str) -> Path:
    """Download an award year's spreadsheet into the git-ignored cache and return its path.
    Cached, so re-imports and the admin console never re-download."""
    url = SOURCES.get(award_year)
    if not url:
        raise SystemExit(
            f"no known source for award year {award_year!r}. Known: {', '.join(sorted(SOURCES))}"
        )
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{award_year}.xls"
    if path.exists() and path.stat().st_size > 0:
        return path
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as resp:
            body = resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"could not download {award_year} from {url}: {exc}")
    if not body.startswith(b"\xd0\xcf\x11\xe0"):  # OLE2 magic: an .xls, not an error page
        raise SystemExit(
            f"{url} did not return an .xls (got {len(body)} bytes). ED may have renamed the file."
        )
    path.write_bytes(body)
    return path


SCORE_FIELDS = [
    "institution_id",
    "award_year",
    "year",
    "score",
    "fy_end",
    "institution_type",
    "as_of",
    "source_url",
    "source_file",
]
REVIEW_FIELDS = [
    "opeid",
    "name",
    "city",
    "state",
    "award_year",
    "score",
    "institution_type",
    "reason",
    "source_file",
]


# ---- parsing -----------------------------------------------------------------------------


@dataclass
class Meta:
    """What the spreadsheet says about itself, read from its title block."""

    award_year: str = ""  # '2022-23'
    year: int | None = None  # ending calendar year, for sorting/plotting
    as_of: str = ""  # the eZ-Audit snapshot date printed in the title
    title: str = ""
    source_file: str = ""


@dataclass
class Record:
    opeid: str
    name: str
    city: str
    state: str
    fy_end: str
    inst_type: str
    score: float | None
    raw_score: str = ""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


# Header labels drift year to year, so columns are matched by substring, never by position.
# Order matters: the most specific pattern wins, because 'Institution Fiscal Year End' and
# 'Institution Type' both contain 'institution'.
HEADER_PATTERNS = [
    ("score", ("composite score", "composite")),
    # 'School Fiscal Year End Date' (2008-11), 'Institution Fiscal Year End' (2012 on), and bare
    # 'Institution Fiscal Year' (2013-15). The score column is claimed first, so the loose
    # 'fiscal year' pattern cannot steal "Composite Score for ... Fiscal Year Ending Between".
    ("fy_end", ("fiscal year end", "fiscal year", "fye")),
    ("inst_type", ("institution type", "school type", "type")),
    ("opeid", ("opeid", "ope id")),
    ("name", ("institution name", "school name", "name")),
    ("city", ("city",)),
    ("state", ("state",)),
    ("zip", ("zip",)),
]


def _is_opeid_header(value: str) -> bool:
    """'OPEID' in the newer files, 'OPE ID' in the older ones."""
    return re.sub(r"[^a-z]", "", str(value or "").lower()) == "opeid"


def _map_headers(cells: list[str]) -> dict[str, int]:
    """Map our field names to column indexes for this file's header row."""
    taken: set[int] = set()
    out: dict[str, int] = {}
    for fieldname, patterns in HEADER_PATTERNS:
        for pat in patterns:
            hit = next((i for i, c in enumerate(cells) if i not in taken and pat in _norm(c)), None)
            if hit is not None:
                out[fieldname] = hit
                taken.add(hit)
                break
    return out


def _parse_meta(title: str, path: Path) -> Meta:
    """Read the award year out of the title block, which states the fiscal-year window, e.g.
    '... with Fiscal Years Ending Between 7/1/2022 and 6/30/2023'. Falls back to the filename
    (ay-22-23-composite-scores.xls) only if the title does not state it."""
    m = Meta(title=re.sub(r"\s+", " ", title).strip(), source_file=path.name)
    win = re.search(
        r"between\s+\d{1,2}/\d{1,2}/(\d{4})\s+and\s+\d{1,2}/\d{1,2}/(\d{4})", _norm(title)
    )
    if win:
        start, end = int(win.group(1)), int(win.group(2))
        m.award_year, m.year = f"{start}-{str(end)[2:]}", end
    else:
        fn = re.search(r"ay-?(\d{2})-(\d{2})", path.name.lower())
        if fn:
            start = 2000 + int(fn.group(1))
            m.award_year, m.year = f"{start}-{fn.group(2)}", start + 1
    # Newer files print 'Data Source: eZ-Audit as of December 17, 2024'; the 2006-11 files print
    # 'Processed through June 30, 2010'. Both state when ED cut the file, which matters because
    # ED revises scores after publication.
    as_of = re.search(r"(?:as of|processed through)\s+([a-z]+ \d{1,2},? \d{4})", _norm(title))
    if as_of:
        m.as_of = as_of.group(1).title()
    return m


def _xls_date(cell, book) -> str:
    """ED writes the fiscal year end as an Excel date serial. Return an ISO date."""
    import xlrd

    if cell.ctype == xlrd.XL_CELL_DATE:
        y, mo, d, *_ = xlrd.xldate.xldate_as_tuple(cell.value, book.datemode)
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return str(cell.value or "").strip()


def parse(path: Path) -> tuple[Meta, list[Record], list[str]]:
    """Parse one ED spreadsheet into (meta, records, warnings)."""
    import xlrd

    warnings: list[str] = []
    if path.suffix.lower() == ".xlsx":
        raise SystemExit(
            f"{path.name}: .xlsx is not supported (xlrd 2.x reads only .xls). "
            "Download the .xls version, or add openpyxl and extend parse()."
        )
    if path.suffix.lower() != ".xls":
        raise SystemExit(f"{path.name}: expected an ED .xls composite-score spreadsheet.")
    book = xlrd.open_workbook(str(path))
    sheet = book.sheet_by_index(0)
    rows = [sheet.row(r) for r in range(sheet.nrows)]
    if not rows:
        raise SystemExit(f"{path.name}: empty workbook.")

    # Find the header row (the one naming OPEID); everything above it is the title block.
    hdr_i = next(
        (i for i, r in enumerate(rows[:20]) if any(_is_opeid_header(c.value) for c in r)), None
    )
    if hdr_i is None:
        raise SystemExit(
            f"{path.name}: no header row naming 'OPEID' in the first 20 rows. "
            "Is this an ED composite-score file?"
        )
    cols = _map_headers([c.value for c in rows[hdr_i]])
    for required in ("opeid", "name", "score"):
        if required not in cols:
            raise SystemExit(
                f"{path.name}: header row has no '{required}' column: "
                f"{[c.value for c in rows[hdr_i]]}"
            )

    title = " ".join(str(c.value) for r in rows[:hdr_i] for c in r if str(c.value).strip())
    meta = _parse_meta(title, path)
    if not meta.award_year:
        raise SystemExit(
            f"{path.name}: could not read the award year from the title or the "
            f"filename. Title was: {meta.title[:160]!r}"
        )

    def cell(row, key: str) -> str:
        i = cols.get(key)
        return str(row[i].value).strip() if i is not None and i < len(row) else ""

    seen: dict[str, Record] = {}
    for r in rows[hdr_i + 1 :]:
        opeid, name = cell(r, "opeid"), cell(r, "name")
        if not opeid or not name:
            continue
        # OPEIDs are 8 digits with leading zeros; a numeric cell loses them.
        if re.fullmatch(r"\d+(\.0)?", opeid):
            opeid = opeid.split(".")[0].zfill(8)
        raw = cell(r, "score")
        try:
            score = float(raw)
        except ValueError:
            score = None
            if raw:
                warnings.append(f"{name} ({opeid}): non-numeric score {raw!r}, stored as blank")
        if opeid in seen:
            warnings.append(f"{name} ({opeid}): OPEID appears twice in this file; kept the first")
            continue
        seen[opeid] = Record(
            opeid=opeid,
            name=name,
            city=cell(r, "city"),
            state=cell(r, "state").upper()[:2],
            fy_end=_xls_date(r[cols["fy_end"]], book) if "fy_end" in cols else "",
            inst_type=cell(r, "inst_type"),
            score=score,
            raw_score=raw,
        )
    return meta, list(seen.values()), warnings


# ---- existing-data snapshot --------------------------------------------------------------


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


@dataclass
class Existing:
    """Who we already track, read from the CSVs (the source of truth), not the built DB."""

    known: dict[str, dict] = field(default_factory=dict)  # opeid -> row, any status
    scores: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls) -> Existing:
        ex = cls()
        for name in ("institutions.csv", "manual_closures.csv", "institutions_open.csv"):
            for row in _read(DATA / name):
                if row.get("id"):
                    ex.known[row["id"]] = row
        ex.scores = _read(SCORES_CSV)
        return ex


# ---- batch -------------------------------------------------------------------------------


@dataclass
class Batch:
    meta: Meta
    score_rows: list[dict] = field(default_factory=list)
    review: list[dict] = field(default_factory=list)  # OPEID we do not track; needs a human
    flags: list[str] = field(default_factory=list)  # contradictions worth a look
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict:
        return {
            "award_year": self.meta.award_year,
            "scores": len(self.score_rows),
            "review": len(self.review),
            "flags": len(self.flags),
        }


def build_batch(path: Path, ex: Existing | None = None) -> Batch:
    """Draft every row this file would write. Writes nothing."""
    ex = ex or Existing.load()
    meta, records, warnings = parse(path)
    b = Batch(meta=meta, warnings=warnings)

    for rec in records:
        known = ex.known.get(rec.opeid)
        if not known:
            b.review.append(
                {
                    "opeid": rec.opeid,
                    "name": rec.name,
                    "city": rec.city,
                    "state": rec.state,
                    "award_year": meta.award_year,
                    "score": "" if rec.score is None else rec.score,
                    "institution_type": rec.inst_type,
                    "source_file": meta.source_file,
                    "reason": f"filed a {meta.award_year} audit but is not in the IPEDS open roster "
                    "and is not tracked as a closure: fate unknown (closed, merged, "
                    "renamed, changed OPEID, or left Title IV)",
                }
            )
            continue

        # A school we record as having closed BEFORE it filed this audit is a contradiction in
        # our own data. Say so; never silently rewrite either side.
        sy = (known.get("status_year") or "").strip()
        if (
            known.get("status") in ("closed", "merged")
            and sy.isdigit()
            and int(sy) < (meta.year or 0) - 1
        ):
            b.flags.append(
                f"{rec.name} ({rec.opeid}): we record {known.get('status')} in {sy}, but it "
                f"filed an audited {meta.award_year} return. Check the closure year, or an "
                "OPEID reused by a different school."
            )

        b.score_rows.append(
            {
                "institution_id": rec.opeid,
                "award_year": meta.award_year,
                "year": meta.year or "",
                "score": "" if rec.score is None else rec.score,
                "fy_end": rec.fy_end,
                "institution_type": rec.inst_type,
                "as_of": meta.as_of,
                "source_url": SOURCE_URL,
                "source_file": meta.source_file,
            }
        )
    return b


# ---- commit ------------------------------------------------------------------------------


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows([{k: r.get(k, "") for k in fields} for r in rows])


def commit(path: Path) -> Batch:
    """Apply a batch to the CSVs. Idempotent: re-importing the same file replaces that award
    year's rows rather than duplicating them. Does NOT rebuild the DB; the caller does."""
    ex = Existing.load()
    b = build_batch(path, ex)

    kept = [r for r in ex.scores if r.get("award_year") != b.meta.award_year]
    _write(
        SCORES_CSV,
        SCORE_FIELDS,
        sorted(kept + b.score_rows, key=lambda r: (str(r["institution_id"]), str(r["award_year"]))),
    )

    prior = [r for r in _read(REVIEW_CSV) if r.get("award_year") != b.meta.award_year]
    if prior or b.review:
        _write(
            REVIEW_CSV,
            REVIEW_FIELDS,
            sorted(prior + b.review, key=lambda r: (str(r["award_year"]), str(r["opeid"]))),
        )
    return b


def _report(b: Batch, committed: bool) -> None:
    c = b.counts()
    print(f"\n{b.meta.source_file}  award year {c['award_year']}")
    if b.meta.as_of:
        print(f"  eZ-Audit snapshot: {b.meta.as_of}")
    print(f"  scores attached  : {c['scores']}")
    print(
        f"  sent to review   : {c['review']}"
        + (f"  -> {REVIEW_CSV.relative_to(ROOT)}" if b.review else "")
    )
    for w in b.warnings[:10]:
        print(f"  warning: {w}")
    if len(b.warnings) > 10:
        print(f"  ... and {len(b.warnings) - 10} more warnings")
    for f in b.flags[:10]:
        print(f"  FLAG: {f}")
    if len(b.flags) > 10:
        print(f"  ... and {len(b.flags) - 10} more flags")
    if committed:
        print(f"  wrote {SCORES_CSV.relative_to(ROOT)}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "files", nargs="*", type=Path, help="ED composite-score .xls file(s) already on disk"
    )
    ap.add_argument(
        "--year",
        action="append",
        default=[],
        metavar="AY",
        help=f"download and import an award year ({min(SOURCES)} to {max(SOURCES)})",
    )
    ap.add_argument(
        "--all", action="store_true", help="download and import every award year ED publishes"
    )
    ap.add_argument(
        "--commit",
        action="store_true",
        help="write the CSV (default is a preview that writes nothing)",
    )
    args = ap.parse_args(argv)

    paths = list(args.files)
    # Oldest first, so a re-run's output reads chronologically. Order does not affect the rows:
    # each award year replaces its own, and none of them create institutions.
    for ay in sorted(SOURCES) if args.all else sorted(args.year):
        paths.append(fetch(ay))
    if not paths:
        ap.error("give a file, --year, or --all")
    for path in paths:
        _report(commit(path) if args.commit else build_batch(path), args.commit)
    if not args.commit:
        print("\nPreview only. Re-run with --commit to write, then: python3 scripts/build_db.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
