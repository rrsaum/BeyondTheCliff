"""The closure-autopsy work queue: a browser-managed worklist of schools to profile.

This is deliberately a COLLECTOR, not an extractor. The form drops a school name plus its
Wikipedia and other source URLs into data/autopsy_queue.csv; nothing is parsed or written to the
tracker here. The actual profiling (reading each source, verifying every fact, writing the sourced
rows) is done by hand against the sources, because pulling founding years, enrollment, and
financials out of prose is exactly where a fabricated number would slip in, and this project never
originates a number. So the queue holds the pointers and the human-in-the-loop does the honest read.

The queue file is not one of the tables build_db.py loads, so it never touches the database; it is
just a durable, diffable worklist that the /admin page manages so no one has to remember a path.
"""

from __future__ import annotations

import csv
import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

QUEUE = Path(__file__).resolve().parent.parent / "data" / "autopsy_queue.csv"
FIELDS = ["added", "school", "urls", "status", "notes"]
STATUSES = ("pending", "in_progress", "done")


def load() -> list[dict]:
    if not QUEUE.exists():
        return []
    with QUEUE.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _write(rows: list[dict]) -> None:
    with QUEUE.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({k: r.get(k, "") for k in FIELDS} for r in rows)


def _name_from_url(url: str) -> str:
    """Derive a school name from a URL's last path segment, so a bare link queues cleanly. A
    Wikipedia article path is the title: '/wiki/William_%26_Vashti_College' -> 'William & Vashti
    College'. Returns '' when there is no usable segment (the caller then drops the line)."""
    seg = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    return unquote(seg).replace("_", " ").strip()


def parse_bulk(text: str) -> list[tuple[str, str]]:
    """Each non-empty line is one school. Everything before the first http(s) URL is the school
    name; from there on, whitespace-separated URLs. When a line is a bare URL (no name before it),
    the name is derived from the first URL's last path segment. A line with no URL is queued
    name-only."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        i = line.lower().find("http")
        if i >= 0:
            school = line[:i].strip(" -|,\t")
            urls = " ".join(line[i:].split())
            if not school and urls:
                school = _name_from_url(urls.split()[0])
        else:
            school, urls = line.strip(" -|,\t"), ""
        if school:
            out.append((school, urls))
    return out


def add(text: str) -> tuple[list[str], list[str]]:
    """Append parsed entries as 'pending', skipping any school already in the queue (case-
    insensitive by name). Returns (added_names, skipped_already_present)."""
    rows = load()
    have = {r["school"].strip().lower() for r in rows}
    today = datetime.date.today().isoformat()
    added, skipped = [], []
    for school, urls in parse_bulk(text):
        if school.lower() in have:
            skipped.append(school)
            continue
        have.add(school.lower())
        rows.append(
            {"added": today, "school": school, "urls": urls, "status": "pending", "notes": ""}
        )
        added.append(school)
    _write(rows)
    return added, skipped


def set_status(school: str, status: str, note: str = "") -> None:
    """Mark a queued school's status (used when a profile has been built). No-op if not found."""
    if status not in STATUSES:
        return
    rows = load()
    for r in rows:
        if r["school"].strip().lower() == school.strip().lower():
            r["status"] = status
            if note:
                r["notes"] = note
    _write(rows)
