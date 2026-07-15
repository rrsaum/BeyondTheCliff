"""An in-memory IPEDS lookup for the admin ingestion page: resolve an institution's
name + city + state to its federal OPE ID, control, level, and open/closed status.

Why this exists: the browser ingestion flow (app/admin.py) needs to attach a federal OPEID
to a pasted closure so it inherits a College Scorecard profile and the campus-vs-institutional
classification. The authoritative source is the IPEDS HD directory files, already cached under
data/ipeds_cache/ by scripts/enrich_ipeds.py. We stream those cached zips once, build a
name -> records index, and keep it in a module global so the web process pays the cost a single
time. A JSON snapshot (data/ipeds_cache/_name_index.json) makes restarts instant.

We reuse fetch_csv / upper_reader / the closure-date regex from scripts/enrich_ipeds.py rather
than re-implement the (BOM-safe, cache-backed) download logic. Standard library only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
CACHE = ROOT / "data" / "ipeds_cache"
SNAPSHOT = CACHE / "_name_index.json"

# scripts/ is not a package; put it on the path so we can reuse the IPEDS fetch helpers.
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from enrich_ipeds import YEARS, fetch_csv, upper_reader  # noqa: E402  (path set above)

_DATE_RE = re.compile(r"\d{2}/\d{2}/\d{4}")  # IPEDS CLOSEDAT is MM/DD/YYYY when closed
_CONTROL = {"1": "public", "2": "private_nonprofit", "3": "private_forprofit"}
_LEVEL = {"1": "4yr", "2": "2yr", "3": "lt2yr"}
_STOP_SUFFIX = re.compile(r"\b(INC|LLC|LTD|THE)\b")


def normalize(name: str) -> str:
    """Fold a school name to a match key: uppercase, drop punctuation and filler words,
    collapse whitespace. Conservative on purpose, so two genuinely different schools do not
    collide into one key."""
    up = (name or "").upper()
    up = up.replace("&", " AND ")
    up = re.sub(r"[^A-Z0-9 ]", " ", up)
    up = _STOP_SUFFIX.sub(" ", up)
    return re.sub(r"\s+", " ", up).strip()


class Index:
    """name -> IPEDS records, plus the set of OPEIDs currently open. One record per OPEID
    (latest HD year wins)."""

    def __init__(self, records: list[dict], open_opeids: set[str]):
        self.records = records
        self.open_opeids = open_opeids
        self.by_name: dict[str, list[dict]] = {}
        self.name_by_opeid: dict[str, str] = {}
        for r in records:
            self.by_name.setdefault(r["nkey"], []).append(r)
            self.name_by_opeid[r["opeid"]] = r["name"]

    def resolve(self, name: str, state: str, city: str) -> tuple[dict | None, str]:
        """Return (record, note). A match requires the normalized name AND the state to agree,
        with city as the tie-breaker when a name+state pair is not unique. Anything short of that
        returns (None, reason) so the caller can leave the OPEID blank rather than guess wrong."""
        cands = self.by_name.get(normalize(name), [])
        if not cands:
            return None, "no IPEDS name match (school likely closed before 2004, IPEDS HD's start)"
        st = (state or "").strip().upper()
        in_state = [r for r in cands if r["state"] == st] if st else cands
        if not in_state:
            other = ", ".join(sorted({r["state"] for r in cands}))
            return None, f"name matches IPEDS but in a different state ({other}); left unmatched for review"
        if len(in_state) == 1:
            return in_state[0], "matched on name + state"
        cty = (city or "").strip().upper()
        in_city = [r for r in in_state if r["city"] == cty]
        if len(in_city) == 1:
            return in_city[0], "matched on name + state + city"
        return None, f"{len(in_state)} IPEDS branches share this name in {st}; ambiguous, left unmatched"

    def resolve_child(self, parent: str, child: str, state: str) -> tuple[dict | None, str]:
        """Resolve one branch of a parent by requiring the IPEDS name to contain every word of
        BOTH the parent and the child (e.g. parent 'Pennsylvania State University' + child
        'DuBois' -> 'Pennsylvania State University-Penn State DuBois'), within the given state.
        Used for campus/program entries where the human names the parent and the branch."""
        ptoks = set(normalize(parent).split())
        ctoks = set(normalize(child).split())
        st = (state or "").strip().upper()
        if not ptoks or not ctoks:
            return None, "need both a parent and a campus/program name"
        cands = [
            r for r in self.records
            if (not st or r["state"] == st)
            and ptoks <= set(r["nkey"].split())
            and ctoks <= set(r["nkey"].split())
        ]
        if len(cands) == 1:
            return cands[0], "matched parent + branch + state"
        if not cands:
            return None, "no IPEDS match for this branch (it may have no federal OPEID)"
        return None, f"{len(cands)} IPEDS branches match; ambiguous, left unmatched"


_INDEX: Index | None = None


def _scan_hd() -> tuple[list[dict], list[str]]:
    """Single streaming pass over the cached HD directory files. Later years overwrite earlier
    ones, so each OPEID ends on its most recent name / status."""
    by_opeid: dict[str, dict] = {}
    for year in YEARS:
        lines = fetch_csv("HD", year)
        if not lines:
            continue
        for row in upper_reader(lines):
            opeid = (row.get("OPEID") or "").strip()
            name = (row.get("INSTNM") or "").strip()
            if not opeid or not name:
                continue
            closedat = (row.get("CLOSEDAT") or "").strip()
            by_opeid[opeid] = {
                "opeid": opeid,
                "unitid": (row.get("UNITID") or "").strip(),
                "name": name,
                "nkey": normalize(name),
                "city": (row.get("CITY") or "").strip().upper(),
                "state": (row.get("STABBR") or "").strip().upper(),
                "control": _CONTROL.get((row.get("CONTROL") or "").strip(), ""),
                "level": _LEVEL.get((row.get("ICLEVEL") or "").strip(), ""),
                "is_open": not _DATE_RE.match(closedat),
            }
    records = list(by_opeid.values())
    open_opeids = [r["opeid"] for r in records if r["is_open"]]
    return records, open_opeids


def _load_snapshot() -> Index | None:
    if not SNAPSHOT.exists():
        return None
    try:
        blob = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        return Index(blob["records"], set(blob["open_opeids"]))
    except (ValueError, KeyError, OSError):
        return None


def get_index(refresh: bool = False) -> Index:
    """Lazily build (or load) the index and cache it in the process. First build streams ~21
    cached HD zips and can take a few seconds; a JSON snapshot makes every later start instant.
    Pass refresh=True to rebuild from the zips (e.g. after refreshing the IPEDS cache)."""
    global _INDEX
    if _INDEX is not None and not refresh:
        return _INDEX
    if not refresh:
        snap = _load_snapshot()
        if snap is not None:
            _INDEX = snap
            return _INDEX
    records, open_opeids = _scan_hd()
    _INDEX = Index(records, set(open_opeids))
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(
            json.dumps({"records": records, "open_opeids": open_opeids}), encoding="utf-8"
        )
    except OSError:
        pass  # a read-only cache dir just means we rebuild next start; not fatal
    return _INDEX
