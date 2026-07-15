#!/usr/bin/env python3
"""Best-effort founding year, background, and history from Wikidata + Wikipedia.

Founding year is NOT in IPEDS, and neither is a narrative background. This fills three
columns in data/institutions.csv where our institution matches a Wikidata record by
normalized name AND state:
  - founding_year  <- Wikidata inception (P571)
  - background     <- Wikidata one-line description
  - history        <- Wikipedia intro extract (fetched by the matched title)

The match is deliberately conservative (exact normalized name, disambiguated by state), so
we never guess. Coverage is partial by design: well-known nonprofits and publics match,
defunct for-profit branches mostly will not. A missing value is honest; a wrong one is not.

Run AFTER import_sheeo.py and enrich_ipeds.py, BEFORE build_db.py. Responses are cached in
data/ipeds_cache/ for fast reruns. Standard library only.
"""
from __future__ import annotations

import csv
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE_DIR = DATA / "ipeds_cache"
WD_CACHE = CACHE_DIR / "wikidata_founding.json"
WP_CACHE = CACHE_DIR / "wikipedia_extracts.json"
UA = "BeyondTheCliff-research/1.0 (higher-ed closure research)"

QUERY = """
SELECT ?item ?itemLabel ?itemDescription ?inception ?stLabel WHERE {
  ?item wdt:P31/wdt:P279* wd:Q38723 ; wdt:P17 wd:Q30 ; wdt:P571 ?inception .
  OPTIONAL { ?item wdt:P131* ?st . ?st wdt:P31 wd:Q35657 . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""

STATE_ABBR = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND",
    "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN",
    "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}


def normalize(name: str) -> str:
    s = name.lower().replace("&", " and ").replace(".", " ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^the ", "", s)
    # Expand the common abbreviations that differ between SHEEO (all-caps, abbreviated) and
    # Wikidata (spelled out), so "College of St Joseph" aligns with "College of Saint Joseph".
    s = re.sub(r"\bst\b", "saint", s)
    s = re.sub(r"\bmt\b", "mount", s)
    return s


def http_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def fetch_wikidata() -> list[dict]:
    if WD_CACHE.exists():
        return json.loads(WD_CACHE.read_text())
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode(
        {"query": QUERY, "format": "json"})
    data = http_json(url)
    rows = []
    for b in data["results"]["bindings"]:
        label = b.get("itemLabel", {}).get("value", "")
        desc = b.get("itemDescription", {}).get("value", "")
        state = b.get("stLabel", {}).get("value", "")
        item = b.get("item", {}).get("value", "")
        m = re.match(r"(-?\d{3,4})-", b.get("inception", {}).get("value", ""))
        year = int(m.group(1)) if m and int(m.group(1)) > 0 else None
        if label and year:
            rows.append({"name": label, "year": year, "desc": desc,
                         "state": STATE_ABBR.get(state.lower(), ""), "item": item})
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    WD_CACHE.write_text(json.dumps(rows))
    return rows


def wikipedia_extract(title: str, cache: dict) -> str:
    """Intro extract for a Wikipedia title, cached. Returns '' if there is no page."""
    if title in cache:
        return cache[title]
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title, safe="")
    extract = ""
    try:
        data = http_json(url)
        if data.get("type") == "standard":
            extract = (data.get("extract") or "").strip()[:800]
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        extract = ""
    cache[title] = extract
    return extract


def main() -> None:
    wd = fetch_wikidata()
    # normalized name -> {state -> record}, earliest inception kept per (name, state).
    index: dict[str, dict[str, dict]] = {}
    for r in wd:
        by_state = index.setdefault(normalize(r["name"]), {})
        if r["state"] not in by_state or r["year"] < by_state[r["state"]]["year"]:
            by_state[r["state"]] = r
    print(f"Wikidata US higher-ed with inception: {len(wd)} ({len(index)} distinct names)")

    with (DATA / "institutions.csv").open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames or []
        institutions = list(reader)
    for col in ("founding_year", "background", "history"):
        if col not in fields:
            fields.append(col)

    wp_cache = json.loads(WP_CACHE.read_text()) if WP_CACHE.exists() else {}
    filled_year = filled_bg = filled_hist = 0
    for inst in institutions:
        by_state = index.get(normalize(inst["name"]))
        if not by_state:
            continue
        state = inst.get("state", "")
        rec = by_state.get(state)
        if rec is None and len(by_state) == 1 and "" in by_state:
            rec = by_state[""]           # single stateless candidate: accept
        if rec is None:
            continue                     # name matches but state does not: skip
        if not inst.get("founding_year"):
            inst["founding_year"] = str(rec["year"])
            filled_year += 1
        if not inst.get("background") and rec["desc"]:
            inst["background"] = rec["desc"]
            filled_bg += 1
        if not inst.get("history"):
            extract = wikipedia_extract(rec["name"], wp_cache)
            if extract:
                inst["history"] = extract
                filled_hist += 1

    WP_CACHE.write_text(json.dumps(wp_cache))
    with (DATA / "institutions.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(institutions)

    n = len(institutions)
    print(f"founding_year: {filled_year}/{n} | background: {filled_bg} | history: {filled_hist}")
    print("Next: python3 scripts/build_db.py")


if __name__ == "__main__":
    main()
