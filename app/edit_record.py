"""Edit an existing institution record from the browser: reclassify its status (for example
announced -> closed once a closure date passes), fix a field, or correct a mislabel.

The row lives in one of the two source-of-truth CSVs (data/institutions.csv for federal/SHEEO
rows, data/manual_closures.csv for hand-curated ones). This locates it by id, updates only the
editable fields, rewrites that file, and lets the caller rebuild the DB. Enum fields are
validated against the schema so a bad edit cannot produce a row build_db would reject.

Standard library only.
"""
from __future__ import annotations

import csv
from pathlib import Path

from . import ce_ingest as ce

FILES = [ce.INSTITUTIONS, ce.MANUAL]

# Fields a human may edit here. Others (opeid, unitid, enrichment) are left to the importers.
EDITABLE = ["name", "control", "level", "city", "state", "status", "status_year",
            "closure_type", "parent_name", "cause", "notes", "source_url"]

STATUSES = ["open", "closed", "merged", "announced", "at_risk"]
CLOSURE_TYPES = ["", "institutional", "campus", "program"]
CAUSES = ["", "financial", "enrollment", "accreditation", "sponsor", "misconduct",
          "disaster", "restructuring", "external", "benefactor"]
CONTROLS = ["", "public", "private_nonprofit", "private_forprofit"]
LEVELS = ["", "4yr", "2yr", "lt2yr"]


def _read(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        r = csv.DictReader(fh)
        return list(r.fieldnames or []), list(r)


def _locate(inst_id: str) -> tuple[Path, list[str], list[dict], int] | None:
    for path in FILES:
        fields, rows = _read(path)
        for i, row in enumerate(rows):
            if (row.get("id") or "").strip() == inst_id:
                return path, fields, rows, i
    return None


def load(inst_id: str) -> dict | None:
    """Return the current row (all columns) for prefilling the edit form, or None."""
    found = _locate(inst_id)
    if not found:
        return None
    _, _fields, rows, i = found
    return rows[i]


def validate(updates: dict) -> str:
    """Return '' if the proposed values are legal, else an error message."""
    if updates.get("status") and updates["status"] not in STATUSES:
        return f"status must be one of {', '.join(STATUSES)}"
    ct = updates.get("closure_type", "")
    if ct and ct not in CLOSURE_TYPES:
        return f"closure type must be blank or one of {', '.join(c for c in CLOSURE_TYPES if c)}"
    cz = updates.get("cause", "")
    if cz and cz not in CAUSES:
        return f"cause must be blank or one of {', '.join(c for c in CAUSES if c)}"
    yr = (updates.get("status_year") or "").strip()
    if yr and not yr.isdigit():
        return f"year must be a number or blank, got {yr!r}"
    return ""


def update(inst_id: str, updates: dict) -> str:
    """Apply updates (only EDITABLE keys present in the file) to the row and rewrite the file.
    Returns '' on success or an error message."""
    found = _locate(inst_id)
    if not found:
        return f"no record found with id {inst_id!r}"
    err = validate(updates)
    if err:
        return err
    path, fields, rows, i = found
    for key in EDITABLE:
        if key in fields and key in updates:
            rows[i][key] = updates[key].strip()
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return ""
