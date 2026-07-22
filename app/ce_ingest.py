"""The College Evaluator closure ingestion engine behind the browser admin page.

Given a list of collegeevaluator.com "closing information" URLs, this fetches each page (into a
local cache), parses it deterministically (the pages are static HTML, no JavaScript), resolves
the institution to a federal OPE ID via app/ipeds_index.py, dedups it against the committed
CSVs, classifies it campus-vs-institutional, and drafts the rows that WOULD be written to
data/manual_closures.csv / campuses.csv / names.csv.

Nothing here writes anything until commit() is called. build_batch() is a pure preview: the
admin page shows the drafted rows and the honesty flags, the human clicks Approve, and commit()
re-derives the same rows from the cached HTML and appends them. Standard library only.

Two page shapes, both confirmed against live markup:
  - Multi-campus: <title> "<Name> N Campuses Closing Information"; a table of
    [campus name, "STREET, CITY, ST ZIP", MM/DD/YYYY] rows, one per closed location.
  - Single: <title> "<Name> Closing Information"; a vertical key/value table
    (School Name / Address / City / State / ZIP / Closed Data).

Honesty rules encoded as flags (see FLAG_* below): we never record an open school as closed,
never invent a control/level/year we do not have, and never fabricate campuses a page did not
list. Uncertain cases are HELD (not written) and surfaced for human review.
"""
from __future__ import annotations

import csv
import html
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .ipeds_index import get_index, normalize

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CE_CACHE = DATA / "ce_cache"
UA = {"User-Agent": "BeyondTheCliff-research/1.0 (higher-ed closure research)"}

MANUAL = DATA / "manual_closures.csv"
CAMPUSES = DATA / "campuses.csv"
NAMES = DATA / "names.csv"
INSTITUTIONS = DATA / "institutions.csv"

MANUAL_FIELDS = ["id", "opeid", "name", "control", "level", "city", "state", "status",
                 "status_year", "closure_type", "parent_name", "cause", "notes", "source_url"]
CAMPUS_FIELDS = ["institution_id", "name", "city", "state", "opened_year", "closed_year",
                 "is_main", "source_url"]
NAME_FIELDS = ["institution_id", "name", "start_year", "end_year", "source_url"]

# Actions a drafted institution can take.
ADD = "add"    # write it
SKIP = "skip"  # already tracked; do not write (may still add a former-name alias)
HOLD = "hold"  # uncertain; do not write, surface for human review

# Honesty flags.
FLAG_OPERATING = "possibly still operating (IPEDS lists this OPEID as open); held for review"
FLAG_SCHOOL = "name looks like a K-12 school, not a college; held for review"
FLAG_NO_YEAR = "no closure year on the page; year left blank"
FLAG_NOT_ENUMERATED = "page claims more locations than it lists; institution added, missing campuses not invented"
FLAG_INFERRED = "no OPEID match, so control/level/enrollment profile are unknown"

_TITLE_MULTI = re.compile(r"<title>\s*(.*?)\s+(\d+)\s+Campuses Closing Information\s*</title>",
                          re.I | re.S)
_TITLE_SINGLE = re.compile(r"<title>\s*(.*?)\s+Closing Information\s*</title>", re.I | re.S)
_TABLE = re.compile(r"<table.*?</table>", re.I | re.S)
_TR = re.compile(r"<tr.*?</tr>", re.I | re.S)
_TD = re.compile(r"<t[dh].*?</t[dh]>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_DATE = re.compile(r"\b([0-1]?\d)/([0-3]?\d)/((?:19|20)\d{2})\b")
_ACTIVE = re.compile(r"There are\s+\d+\s+campuses[^.<]*still active", re.I)
_SCHOOL_HINT = re.compile(r"\b(HIGH SCHOOL|ELEMENTARY|MIDDLE SCHOOL|K-?12|ACADEMY OF)\b")


def _text(fragment: str) -> str:
    return html.unescape(_TAG.sub("", fragment)).strip()


def slug_for(url: str) -> str:
    m = re.search(r"/institute/([^/]+)/?", url.strip())
    return (m.group(1) if m else re.sub(r"[^a-z0-9]+", "-", url.lower())).strip("-")


def fetch_html(url: str) -> str:
    """Return the page HTML, caching it under data/ce_cache/ so re-previews and the commit
    re-parse do not re-hit the site."""
    CE_CACHE.mkdir(parents=True, exist_ok=True)
    cache = CE_CACHE / f"{slug_for(url)}.html"
    if cache.exists():
        return cache.read_text(encoding="utf-8", errors="replace")
    text = _download(url)
    cache.write_text(text, encoding="utf-8")
    return text


def _download(url: str) -> str:
    """Fetch a URL as text. Prefer the standard library; fall back to curl (always present on
    macOS) for environments where Python's own TLS egress is restricted."""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        try:
            out = subprocess.run(
                ["curl", "-sS", "-A", UA["User-Agent"], "--max-time", "60", url],
                capture_output=True, text=True, timeout=90, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            raise exc from None
        if out.returncode == 0 and out.stdout:
            return out.stdout
        raise exc from None


def parse_address(addr: str) -> tuple[str, str]:
    """'1457 MANHEIM PIKE, LANCASTER, PA 17601' -> ('Lancaster', 'PA'). The city is the
    second-to-last comma field; the state is the first token of the last field."""
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    if len(parts) < 2:
        return "", ""
    city = parts[-2].title()
    state = parts[-1].split()[0].upper() if parts[-1].split() else ""
    state = state if re.fullmatch(r"[A-Z]{2}", state) else ""
    return city, state


@dataclass
class Campus:
    name: str
    city: str
    state: str
    year: int | None


@dataclass
class Page:
    url: str
    institution: str
    shape: str  # 'multi' or 'single'
    claimed_count: int | None
    parent_active: bool          # a multi page whose parent still operates some campuses
    parent_institute: str        # set on a single page that is one closed campus of a parent
    campuses: list[Campus]


def _titlecase(s: str) -> str:
    """IPEDS/CollegeEvaluator sometimes gives ALL-CAPS names; title-case only those, leaving
    already-mixed-case names alone."""
    s = (s or "").strip()
    return s.title() if s and s.isupper() else s


def parse_page(url: str, doc: str) -> Page:
    active = bool(_ACTIVE.search(doc))
    m = _TITLE_MULTI.search(doc)
    if m:
        name = _text(m.group(1))
        return Page(url, name, "multi", int(m.group(2)), active, "", _parse_multi_rows(name, doc))
    m = _TITLE_SINGLE.search(doc)
    name = _text(m.group(1)) if m else slug_for(url).replace("-", " ").title()
    campuses, parent = _parse_single(name, doc)
    return Page(url, name, "single", None, active, parent, campuses)


def _parse_multi_rows(institution: str, doc: str) -> list[Campus]:
    tab = _TABLE.search(doc)
    if not tab:
        return []
    out: list[Campus] = []
    for tr in _TR.findall(tab.group(0)):
        cells = [_text(c) for c in _TD.findall(tr)]
        if len(cells) < 3:
            continue
        addr, date = cells[1], cells[2]
        city, state = parse_address(addr)
        dm = _DATE.search(date)
        year = int(dm.group(3)) if dm else None
        label = f"{institution} - {city}" if city else _text(cells[0])
        out.append(Campus(label, city, state, year))
    return out


def _parse_single(institution: str, doc: str) -> tuple[list[Campus], str]:
    """A single page uses a vertical key/value table. Two variants: a whole-institution
    closure, or one closed campus of a still-named parent (a 'School Name(Parent Institute)'
    row). Returns (campuses, parent_institute); parent_institute is '' for the whole-institution
    case."""
    kv: dict[str, str] = {}
    tab = _TABLE.search(doc)
    if tab:
        for tr in _TR.findall(tab.group(0)):
            cells = [_text(c) for c in _TD.findall(tr)]
            if len(cells) >= 2 and cells[0]:
                kv[cells[0].lower()] = cells[1]
    city = (kv.get("city") or "").title()
    state = (kv.get("state") or "").upper()[:2]
    dm = _DATE.search(kv.get("closed data", "") or kv.get("closed date", ""))
    year = int(dm.group(3)) if dm else None
    parent = ""
    for k, v in kv.items():
        if "parent institute" in k:
            parent = _titlecase(v)
            break
    label = institution
    if parent and kv.get("campus location"):
        label = _titlecase(kv["campus location"])
    return [Campus(label, city, state, year)], parent


# ---- existing-data snapshot (for dedup) --------------------------------------------------

def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


@dataclass
class Existing:
    opeids: set[str]
    ids: set[str]
    name_state: dict[tuple[str, str], str]  # (nkey, state) -> existing display name
    name_aliases: set[tuple[str, str]]      # (institution_id, name)
    next_man: int
    seen_campus: set[tuple[str, str, int | None]] = field(default_factory=set)  # intra-batch

    @classmethod
    def load(cls) -> "Existing":
        opeids: set[str] = set()
        ids: set[str] = set()
        name_state: dict[tuple[str, str], str] = {}
        max_man = 0
        for path in (INSTITUTIONS, MANUAL):
            for r in _read(path):
                rid = (r.get("id") or "").strip()
                if rid:
                    ids.add(rid)
                    mm = re.fullmatch(r"MAN-(\d+)", rid)
                    if mm:
                        max_man = max(max_man, int(mm.group(1)))
                op = (r.get("opeid") or "").strip()
                if op:
                    opeids.add(op)
                nm, st = (r.get("name") or "").strip(), (r.get("state") or "").strip().upper()
                if nm:
                    name_state.setdefault((normalize(nm), st), nm)
        aliases = {((r.get("institution_id") or "").strip(), (r.get("name") or "").strip())
                   for r in _read(NAMES)}
        return cls(opeids, ids, name_state, aliases, max_man)


# ---- proposal building -------------------------------------------------------------------

@dataclass
class Proposal:
    """One source page. A page can yield several institution-table rows (a surviving parent's
    closed campuses), campus-table rows (a dead parent's locations), and former-name aliases,
    plus lists of records that were held or skipped and why."""
    url: str
    institution: str
    action: str = ADD
    reason: str = ""
    matched: list[str] = field(default_factory=list)   # OPEID matches, for display
    inst_rows: list[dict] = field(default_factory=list)
    campus_rows: list[dict] = field(default_factory=list)
    name_rows: list[dict] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    held: list[str] = field(default_factory=list)      # records not written, needing review
    skipped: list[str] = field(default_factory=list)   # records already tracked
    error: str = ""

    def finalize(self) -> "Proposal":
        if self.error:
            self.action = HOLD
        elif self.inst_rows:
            self.action = ADD
        elif self.held:
            self.action = HOLD
        else:
            self.action = SKIP
        return self


@dataclass
class Batch:
    proposals: list[Proposal]

    def counts(self) -> dict:
        return {
            "institutions": sum(len(p.inst_rows) for p in self.proposals),
            "campuses": sum(len(p.campus_rows) for p in self.proposals),
            "aliases": sum(len(p.name_rows) for p in self.proposals),
            "held": sum(len(p.held) for p in self.proposals),
            "skipped": sum(len(p.skipped) for p in self.proposals),
            "errors": sum(1 for p in self.proposals if p.error),
        }


def _inst_row(inst_id, opeid, name, control, level, city, state, year,
              closure_type, parent_name, note, url, status="closed", cause="") -> dict:
    return {
        "id": inst_id, "opeid": opeid, "name": name, "control": control, "level": level,
        "city": city, "state": state, "status": status,
        "status_year": str(year) if year else "", "closure_type": closure_type,
        "parent_name": parent_name, "cause": cause, "notes": note, "source_url": url,
    }


def _register(ex: Existing, name: str, state: str, opeid: str) -> None:
    """Record a just-drafted row in the dedup snapshot so later rows in the SAME batch do not
    duplicate it."""
    ex.name_state.setdefault((normalize(name), (state or "").upper()), name)
    if opeid:
        ex.opeids.add(opeid)


def _dedup_campuses(campuses: list[Campus]) -> list[Campus]:
    """Collapse locations that share a city and closure year (the source lists several street
    addresses for the same city/year); drop entries with no parseable city."""
    seen: set[tuple[str, int | None]] = set()
    out: list[Campus] = []
    for c in campuses:
        if not c.city:
            continue
        key = (c.city.upper(), c.year)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def _resolve_opeid(page: Page, idx) -> tuple[dict | None, str]:
    """Try each campus location against IPEDS, returning the first confident record."""
    seen: set[tuple[str, str]] = set()
    last = "no IPEDS name match (school likely closed before 2004, IPEDS HD's start)"
    for c in page.campuses:
        key = (c.state, c.city)
        if key in seen:
            continue
        seen.add(key)
        rec, note = idx.resolve(page.institution, c.state, c.city)
        if rec:
            return rec, note
        last = note
    return None, last


def _add_campus_unit(p: Proposal, ex: Existing, idx, parent: str, c: Campus,
                     url: str, new_man) -> None:
    """Draft one closed-campus row for a surviving (or named) parent, applying the same
    dedup / operating-school gates as a whole institution."""
    label = c.name
    state = (c.state or "").upper()
    # Already in the committed data (also makes a re-run of the same batch a no-op).
    if (normalize(label), state) in ex.name_state:
        p.skipped.append(f"{label} ({c.state}): already tracked")
        return
    rec, _ = idx.resolve(parent, c.state, c.city)
    if rec and rec["opeid"] in ex.opeids:
        p.skipped.append(f"{label}: already tracked federally")
        return
    if rec and rec["opeid"] in idx.open_opeids:
        p.held.append(f"{label}: {FLAG_OPERATING}")
        if FLAG_OPERATING not in p.flags:
            p.flags.append(FLAG_OPERATING)
        return
    # Same city + same year is one closure listed at several addresses; a different year in the
    # same city is a genuinely distinct closure event, so keep both.
    if (normalize(label), state, c.year) in ex.seen_campus:
        return
    ex.seen_campus.add((normalize(label), state, c.year))
    if rec:
        inst_id = opeid = rec["opeid"]
        control, level = rec["control"], rec["level"]
        p.matched.append(f"{label}: OPEID {rec['opeid']}")
    else:
        inst_id, opeid, control, level = new_man(), "", "", ""
    if c.year is None and FLAG_NO_YEAR not in p.flags:
        p.flags.append(FLAG_NO_YEAR)
    note = f"Campus closure of {parent}; recorded on collegeevaluator.com."
    p.inst_rows.append(_inst_row(inst_id, opeid, label, control, level, c.city, c.state,
                                 c.year, "campus", parent, note, url))


def _build_one(page: Page, ex: Existing, man_counter: list[int]) -> Proposal:
    idx = get_index()
    p = Proposal(url=page.url, institution=page.institution)

    def new_man() -> str:
        man_counter[0] += 1
        return f"MAN-{man_counter[0]:04d}"

    def flag_not_enumerated() -> None:
        listed = len([c for c in page.campuses if c.city])
        if page.claimed_count and listed < page.claimed_count:
            p.flags.append(FLAG_NOT_ENUMERATED)

    # --- campus modes: a surviving parent (multi + "still active") or a named-parent single --
    if (page.shape == "multi" and page.parent_active) or page.parent_institute:
        parent = page.institution if page.parent_active else page.parent_institute
        p.reason = (f"campus closures of {parent}; parent survives"
                    if page.parent_active else f"campus closure of {parent}")
        for c in _dedup_campuses(page.campuses):
            _add_campus_unit(p, ex, idx, parent, c, page.url, new_man)
        flag_not_enumerated()
        return p.finalize()

    # --- institution modes ---------------------------------------------------------------
    rec, note = _resolve_opeid(page, idx)
    year = max((c.year for c in page.campuses if c.year), default=None)
    hq = page.campuses[0]
    inst_city = _titlecase(rec["city"]) if rec else hq.city
    inst_state = rec["state"] if rec else hq.state

    if rec and rec["opeid"] in ex.opeids:
        fed = idx.name_by_opeid.get(rec["opeid"], rec["name"])
        p.skipped.append(f"already tracked federally as \"{fed}\"")
        p.matched.append(f"OPEID {rec['opeid']} ({fed})")
        if normalize(fed) != normalize(page.institution) and (rec["opeid"], page.institution) not in ex.name_aliases:
            p.name_rows.append({"institution_id": rec["opeid"], "name": page.institution,
                                "start_year": "", "end_year": "", "source_url": page.url})
        return p.finalize()

    if (normalize(page.institution), (inst_state or "").upper()) in ex.name_state:
        existing = ex.name_state[(normalize(page.institution), (inst_state or "").upper())]
        p.skipped.append(f"already tracked as \"{existing}\" ({inst_state})")
        return p.finalize()

    if rec and rec["opeid"] in idx.open_opeids:
        p.held.append(f"{page.institution}: {FLAG_OPERATING}")
        p.flags.append(FLAG_OPERATING)
        p.matched.append(f"OPEID {rec['opeid']} (open)")
        return p.finalize()

    if _SCHOOL_HINT.search((page.institution or "").upper()):
        p.held.append(f"{page.institution}: {FLAG_SCHOOL}")
        p.flags.append(FLAG_SCHOOL)
        return p.finalize()

    if rec:
        inst_id = opeid = rec["opeid"]
        control, level = rec["control"], rec["level"]
        p.matched.append(f"OPEID {rec['opeid']} ({rec['name']})")
    else:
        inst_id, opeid, control, level = new_man(), "", "", ""
        p.flags.append(FLAG_INFERRED)
    if year is None:
        p.flags.append(FLAG_NO_YEAR)
    flag_not_enumerated()

    note_bits = [f"Closure recorded on collegeevaluator.com; {note}."]
    if not rec:
        note_bits.append("No federal OPEID (absent from IPEDS/SHEEO/PEPS).")
    p.inst_rows.append(_inst_row(inst_id, opeid, page.institution, control, level, inst_city,
                                 inst_state, year, "institutional", "", " ".join(note_bits), page.url))
    _register(ex, page.institution, inst_state, opeid)

    if page.shape == "multi":  # dead parent: enumerate its locations as campus rows
        for i, c in enumerate(_dedup_campuses(page.campuses)):
            p.campus_rows.append({
                "institution_id": inst_id, "name": c.name, "city": c.city, "state": c.state,
                "opened_year": "", "closed_year": str(c.year) if c.year else "",
                "is_main": "1" if i == 0 else "0", "source_url": page.url,
            })
    return p.finalize()


def build_batch(urls: list[str]) -> Batch:
    ex = Existing.load()
    man_counter = [ex.next_man]
    proposals: list[Proposal] = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        if not re.match(r"https?://(www\.)?collegeevaluator\.com/", url, re.I):
            proposals.append(Proposal(url=url, institution=slug_for(url),
                                      error="not a College Evaluator URL (expected "
                                      "https://www.collegeevaluator.com/institute/...); nothing parsed. "
                                      "This form reads College Evaluator closure pages only, not "
                                      "Wikipedia or other sites, and a stray comma can split one line "
                                      "into two.").finalize())
            continue
        try:
            page = parse_page(url, fetch_html(url))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError,
                ValueError) as exc:
            proposals.append(Proposal(url=url, institution=slug_for(url),
                                      error=f"could not fetch: {exc}").finalize())
            continue
        if not page.campuses:
            proposals.append(Proposal(url=url, institution=page.institution,
                                      error="no closure rows found on the page").finalize())
            continue
        proposals.append(_build_one(page, ex, man_counter))
    return Batch(proposals)


# ---- commit ------------------------------------------------------------------------------

def _existing_header(path: Path) -> list[str]:
    """The column names already on disk, or [] for a missing/empty file. Other tools widen these
    CSVs after ingest (enrich_ipeds adds parent_survives; the autopsy pass adds motto/logo_url), so
    the live header, not this module's field list, is the source of truth for what to write."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return next(csv.reader(fh), [])


def _append(path: Path, fields: list[str], rows: list[dict]) -> None:
    """Append rows, preserving every column the file already carries. Keyed off the on-disk header
    (widened with any field the new rows introduce), never a fixed list, so an enrichment column is
    never dropped and an unknown column never raises. Writes to a temp file then renames, so a
    failure can never truncate the source CSV (a fixed-list DictWriter once wiped 1860 rows)."""
    if not rows:
        return
    existing = _read(path)
    header = _existing_header(path) or list(fields)
    seen = set(header)
    for source in (fields, *(r.keys() for r in rows)):
        for key in source:
            if key not in seen:
                header.append(key)
                seen.add(key)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in header} for r in (existing + list(rows)))
    tmp.replace(path)


def commit(urls: list[str]) -> tuple[Batch, dict]:
    """Re-derive the batch deterministically from the cached HTML and append the drafted rows.
    Returns (batch, counts). Does NOT rebuild the DB; the caller does that."""
    batch = build_batch(urls)
    inst_rows = [r for p in batch.proposals for r in p.inst_rows]
    campus_rows = [r for p in batch.proposals for r in p.campus_rows]
    name_rows = [r for p in batch.proposals for r in p.name_rows]
    _append(MANUAL, MANUAL_FIELDS, inst_rows)
    _append(CAMPUSES, CAMPUS_FIELDS, campus_rows)
    _append(NAMES, NAME_FIELDS, name_rows)
    return batch, batch.counts()
