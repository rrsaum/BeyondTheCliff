#!/usr/bin/env python3
"""Code a primary cause of failure for tracked closures from their Wikipedia article.

The tracker is a post-mortem, but most rows are bare federal records that state no reason. Many
degree-granting closures do have a Wikipedia article that explains why they closed. This reads
those articles and codes a cause into the `cause` field, conservatively:

  - Only rows that plausibly have an article are tried (nonprofit/public, or 2yr/4yr); the tiny
    for-profit sub-2yr tail is skipped.
  - The article is fetched by exact title (following redirects). We keep only the sentences that
    actually discuss the closure ("closed", "ceased", "merged", "defunct", ...) and classify a
    cause from THOSE sentences, so a college merely "founded during the Depression" is never
    coded to an external shock.
  - We accept the match only if the article discusses a closure AND corroborates the school
    (its state name or the closure year appears). Otherwise we skip and leave the cause blank.
  - The cause is attributed to Wikipedia (CC BY-SA) in the row's notes. We never originate a
    cause; if the article does not state one, the row stays blank.

Wikipedia asks for a descriptive User-Agent; we fetch via curl (works where Python's own TLS is
restricted). Dry run by default: writes scripts/_cause_wiki_review.csv for eyeballing. Pass
--commit to write causes into the CSVs, then run build_db.py.

Usage:
    python3 scripts/enrich_cause_wikipedia.py [--limit N] [--commit]
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
FILES = [DATA / "institutions.csv", DATA / "manual_closures.csv"]
REVIEW = Path(__file__).resolve().parent / "_cause_wiki_review.csv"
UA = "BeyondTheCliff-research/1.0 (higher-ed closure research; contact apps@boundlessliving.org)"
ATTRIB = "Primary cause per Wikipedia (CC BY-SA)."

STATE_FULL = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}
CLOSURE_MARK = re.compile(r"clos|ceas|shut|defunct|dissolv|bankrupt|insolven|discontinu|merg|shutter")

# A cause is coded only from EXPLICIT distress phrasing, not any keyword that happens to sit near
# the word "closed". Each cause is an ordered list of regexes; the first cause with a hit wins,
# and the order puts specific causes ahead of the generic financial/enrollment ones. Founding or
# background mentions ("accredited by NECHE", "founded by the Sisters of Mercy") do not match,
# because the patterns require the failure phrasing itself (lost accreditation, order withdrew).
CAUSE_PATTERNS = [
    ("misconduct", [r"\bfraud\b", r"embezzl", r"\bscandal\b", r"financial (misconduct|irregular)",
                    r"mismanagement", r"criminal (charge|investigation)", r"indict"]),
    ("accreditation", [r"lost (its )?accreditation", r"loss of (its )?accreditation",
                       r"accreditation (was )?(withdrawn|revoked|lost|denied|terminated)",
                       r"stripped of[^.]{0,20}accreditation", r"withdraw[^.]{0,20}accreditation",
                       r"denied accreditation", r"placed on probation by[^.]{0,30}accredit"]),
    ("disaster", [r"destroyed by (a )?fire", r"burned down", r"\bhurricane\b", r"flood[^.]{0,20}destroy",
                  r"\bearthquake\b", r"\btornado\b", r"damaged by[^.]{0,20}(fire|storm|flood)"]),
    ("external", [r"during the (covid|coronavirus)", r"covid-19 pandemic", r"the pandemic",
                  r"great depression", r"world war"]),
    ("sponsor", [r"(order|diocese|archdiocese|church|synod|congregation)[^.]{0,40}"
                 r"(withdr|could no longer|ended its support|discontinued|ceased to support)",
                 r"loss of (church|denominational|religious) (support|sponsor)",
                 r"sponsoring (order|body|church)[^.]{0,30}withdr"]),
    ("restructuring", [r"as part of a[^.]{0,40}(consolidation|restructuring|reorganization|merger of)",
                       r"state (university |college )?system[^.]{0,40}(consolidat|merg|restructur)",
                       r"legislat[^.]{0,40}(consolidat|merg|clos)"]),
    ("enrollment", [r"declin\w* enrollment", r"enrollment declin", r"dwindling enrollment",
                    r"falling enrollment", r"low enrollment", r"drop in enrollment",
                    r"shrinking (student body|enrollment)", r"enrollment (challeng|problem|crisis)",
                    r"decreasing enrollment", r"loss of students"]),
    ("financial", [r"financial (trouble|difficult|problem|challeng|distress|crisis|strain|woe|"
                   r"pressure|hardship|instab|struggl|shortfall)", r"struggl\w* financially",
                   r"mounting debt", r"\binsolven", r"\bbankrupt", r"budget (deficit|shortfall)",
                   r"could not[^.]{0,30}(sustain|afford|financ)", r"unable to[^.]{0,30}financ",
                   r"economic (difficult|hardship)", r"lack of funding", r"funding (shortfall|cuts)"]),
]
# Explicit causal connectors: text right after these is the stated reason for the closure.
CAUSAL = re.compile(
    r"(?:due to|because of|citing|cited|as a result of|amid|attributed to|blamed on|"
    r"in the face of|faced with|owing to|as a consequence of|brought on by|driven by|"
    r"result of)\s+(.{0,140})", re.I)


def _match(text: str) -> str:
    low = text.lower()
    for cause, pats in CAUSE_PATTERNS:
        if any(re.search(p, low) for p in pats):
            return cause
    return ""


# Only these read cleanly as distress even outside a causal clause ("struggled financially",
# "declining enrollment", "lost its accreditation"). The rest (war, fire, a religious order, a
# state consolidation) are too often historical or founding background to trust without an
# explicit "due to / citing" connector, so they are coded ONLY from a causal clause.
_DISTRESS = {"financial", "enrollment", "accreditation"}


def classify_wiki(scoped: str) -> str:
    """Auto-code only the three causes Wikipedia states unambiguously (financial / enrollment /
    accreditation); these cover the large majority of modern closures. The rarer causes (war,
    fire, fraud, a religious order, a state consolidation) appear too often as historical or
    founding background to code safely from prose, so they are left blank for hand-coding from a
    verified source. Prefer a causal clause, then an explicit distress phrase; else return ''."""
    for m in CAUSAL.finditer(scoped):
        c = _match(m.group(1))
        if c in _DISTRESS:
            return c
    low = scoped.lower()
    for cause, pats in CAUSE_PATTERNS:
        if cause in _DISTRESS and any(re.search(p, low) for p in pats):
            return cause
    return ""


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        r = csv.DictReader(fh)
        return list(r.fieldnames or []), list(r)


def fetch_extract(title: str) -> str | None:
    params = {"action": "query", "format": "json", "redirects": "1", "prop": "extracts",
              "explaintext": "1", "titles": title}
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    try:
        out = subprocess.run(["curl", "-sS", "--max-time", "30", "-A", UA, url],
                             capture_output=True, text=True, timeout=45, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout:
        return None
    try:
        pages = json.loads(out.stdout)["query"]["pages"]
    except (ValueError, KeyError):
        return None
    page = next(iter(pages.values()))
    return None if "missing" in page else page.get("extract", "")


def closure_sentences(text: str) -> str:
    return " ".join(s for s in re.split(r"(?<=[.!?])\s+", text) if CLOSURE_MARK.search(s.lower()))


_STOP = {"OF", "THE", "AND", "A", "AT", "SCHOOL", "SCHOOLS", "COLLEGE", "COLLEGES", "INSTITUTE",
         "INSTITUTES", "ACADEMY", "UNIVERSITY", "SEMINARY", "INC"}


def _dtok(s: str) -> set:
    return {t for t in re.sub(r"[^A-Za-z0-9 ]", " ", s).upper().split() if t not in _STOP}


def search_titles(name: str, limit: int = 3) -> list[str]:
    """Wikipedia search for candidate article titles (for names whose exact title has no page,
    e.g. a disambiguated 'Concordia College (Selma, Alabama)')."""
    params = {"action": "query", "format": "json", "list": "search",
              "srsearch": f"{name} college closed", "srlimit": str(limit)}
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    try:
        out = subprocess.run(["curl", "-sS", "--max-time", "30", "-A", UA, url],
                             capture_output=True, text=True, timeout=45, check=False)
        hits = json.loads(out.stdout)["query"]["search"]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        return []
    return [h["title"] for h in hits]


def code(text: str, state: str, year: str, strict: bool = False) -> tuple[str, str, str]:
    """Return (cause, evidence, reason). cause='' with a reason when we decline to code. `strict`
    (used for search-sourced matches, which are riskier) requires the state name in the article,
    not merely the year."""
    scoped = closure_sentences(text)
    if not scoped:
        return "", "", "article does not discuss a closure"
    st_name = STATE_FULL.get(state, "")
    state_in = bool(st_name and st_name.lower() in text.lower())
    corroborated = state_in if strict else (state_in or (year and year in text))
    if not corroborated:
        return "", "", "article not corroborated by state (possible wrong school)"
    cause = classify_wiki(scoped)
    if not cause:
        return "", scoped[:160], "closure discussed but no cause phrase found"
    return cause, scoped[:200], ""


def main() -> None:
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    commit = "--commit" in sys.argv

    # Collect targets across both files: closures lacking a cause that plausibly have an article.
    targets = []
    data = {}
    for path in FILES:
        fields, rows = read_csv(path)
        data[path] = (fields, rows)
        for i, r in enumerate(rows):
            if (r.get("cause") or "").strip():
                continue
            if (r.get("status") or "") not in ("closed", "merged", "announced"):
                continue
            control, level = (r.get("control") or ""), (r.get("level") or "")
            src = r.get("source_url") or ""
            historical = any(h in src for h in ("lostcolleges", "nj.gov", "macrao"))
            if control in ("private_nonprofit", "public") or level in ("4yr", "2yr") or historical:
                targets.append((path, i, r))

    # Try the most article-likely schools first (degree-granting nonprofits/publics), so a
    # --limit sample is representative and the full run front-loads the hits.
    def rank(t):
        r = t[2]
        c, lv = (r.get("control") or ""), (r.get("level") or "")
        return (0 if (c in ("private_nonprofit", "public") and lv == "4yr") else
                1 if lv == "4yr" else 2 if c in ("private_nonprofit", "public") else 3)
    targets.sort(key=rank)
    if limit:
        targets = targets[:limit]

    coded = []
    dist, skipped = {}, {"no_article": 0, "no_closure": 0, "not_corroborated": 0, "no_cause": 0}
    for n, (path, i, r) in enumerate(targets, 1):
        name = (r.get("name") or "").strip()
        state = (r.get("state") or "").strip().upper()
        year = (r.get("status_year") or "").strip()
        text = fetch_extract(name)
        cause, evidence, reason = ("", "", "")
        if text is not None:
            cause, evidence, reason = code(text, state, year)
        elif (r.get("level") or "") == "4yr":
            # No exact-title page: for 4-year schools (the ones likely to have a disambiguated
            # article), search and accept a candidate only if its title shares our distinctive
            # name tokens AND the article corroborates the state. The 2yr/for-profit tail has no
            # article to find, so we do not spend search calls on it.
            want = _dtok(name)
            for title in search_titles(name):
                if want and not want.issubset(_dtok(title)):
                    continue
                cand = fetch_extract(title)
                if not cand:
                    continue
                cause, evidence, reason = code(cand, state, year, strict=True)
                if cause:
                    break
            if not cause and not evidence and not reason:
                skipped["no_article"] += 1
                continue
        else:
            skipped["no_article"] += 1
            continue
        if cause:
            coded.append({"path": path, "i": i, "id": r.get("id"), "name": name,
                          "state": r.get("state"), "year": r.get("status_year"),
                          "cause": cause, "evidence": evidence})
            dist[cause] = dist.get(cause, 0) + 1
        elif "does not discuss" in reason:
            skipped["no_closure"] += 1
        elif "not corroborated" in reason:
            skipped["not_corroborated"] += 1
        else:
            skipped["no_cause"] += 1
        if n % 50 == 0:
            print(f"  ...{n}/{len(targets)} processed, {len(coded)} coded", file=sys.stderr)

    with REVIEW.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "name", "state", "year", "cause", "evidence"])
        w.writeheader()
        w.writerows({k: c[k] for k in ("id", "name", "state", "year", "cause", "evidence")} for c in coded)

    print(f"Targets tried: {len(targets)}")
    print(f"  coded: {len(coded)}")
    for c, k in sorted(dist.items(), key=lambda kv: -kv[1]):
        print(f"    {c:14} {k}")
    print(f"  skipped: no article {skipped['no_article']}, no closure text {skipped['no_closure']}, "
          f"not corroborated {skipped['not_corroborated']}, no cause stated {skipped['no_cause']}")
    print(f"Review file: {REVIEW.relative_to(Path(__file__).resolve().parent.parent)}")

    if commit and coded:
        by_path: dict = {}
        for c in coded:
            by_path.setdefault(c["path"], []).append(c)
        for path, items in by_path.items():
            fields, rows = data[path]
            for c in items:
                row = rows[c["i"]]
                row["cause"] = c["cause"]
                note = (row.get("notes") or "").strip()
                if ATTRIB not in note:
                    row["notes"] = (note + " " + ATTRIB).strip()
            with path.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=fields)
                w.writeheader()
                w.writerows(rows)
            print(f"  wrote {len(items)} causes into {path.name}")
        print("Next: python3 scripts/build_db.py")
    elif not commit:
        print("DRY RUN (no --commit): nothing written.")


if __name__ == "__main__":
    main()
