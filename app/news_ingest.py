"""Engine for adding news-sourced closures through the browser: announced (upcoming) or
completed closures that federal data has not captured yet, at the institution, campus, or
program level.

Unlike the College Evaluator flow (app/ce_ingest.py), a news article is unstructured prose, so
the human supplies the facts (name, state, year, type) and the article URL as the citation; the
app only enriches (resolve OPEID / city / control / level from IPEDS), dedups, and writes. This
keeps the honesty standard intact: nothing here originates a school fact, it only records what a
human read in a cited source.

It reuses the row model and CSV writers from ce_ingest so a news entry and a College Evaluator
entry produce identical `institution`-table rows. Standard library only.
"""
from __future__ import annotations

from . import ce_ingest as ce
from .ipeds_index import get_index, normalize

STATUSES = ("announced", "closed", "at_risk", "merged")
TYPES = ("institutional", "campus", "program")


_LEADS = {
    "announced": "Announced closure recorded from a primary news source; not yet closed.",
    "at_risk": "Flagged financially at-risk (still operating), recorded from a primary source.",
    "closed": "Closure recorded from a primary news source.",
    "merged": "Merger/consolidation recorded from a primary source.",
}


def _note(user_note: str, status: str, extra: str = "") -> str:
    lead = _LEADS.get(status, _LEADS["closed"])
    return " ".join(p for p in (lead, extra, user_note.strip()) if p)


def _institutional(f: dict, ex: ce.Existing, idx, new_man) -> ce.Proposal:
    name, state = f["name"].strip(), f["state"].strip().upper()
    p = ce.Proposal(url=f["source_url"], institution=name)
    rec, note = idx.resolve(name, state, "")
    if rec and rec["opeid"] in ex.opeids:
        p.skipped.append(f"already tracked as \"{idx.name_by_opeid.get(rec['opeid'], rec['name'])}\"")
        return p.finalize()
    if (normalize(name), state) in ex.name_state:
        p.skipped.append(f"already tracked as \"{ex.name_state[(normalize(name), state)]}\" ({state})")
        return p.finalize()
    if rec:
        inst_id = opeid = rec["opeid"]
        city, control, level = ce._titlecase(rec["city"]), rec["control"], rec["level"]
        p.matched.append(f"OPEID {rec['opeid']} ({rec['name']})")
    else:
        inst_id, opeid, city, control, level = new_man(), "", "", "", ""
        p.flags.append(ce.FLAG_INFERRED)
    # Neither an at-risk school nor a merged one carries a closure_type (it did not close).
    # For a merger, parent_name holds the acquiring / surviving institution.
    ctype = "" if f["status"] in ("at_risk", "merged") else "institutional"
    acquirer = f.get("acquirer", "").strip() if f["status"] == "merged" else ""
    extra = f"Merged into / absorbed by {acquirer}." if acquirer else ""
    p.inst_rows.append(ce._inst_row(inst_id, opeid, name, control, level, city, state,
                                    f["year"], ctype, acquirer,
                                    _note(f["note"], f["status"], extra), f["source_url"],
                                    status=f["status"], cause=f.get("cause", "")))
    ce._register(ex, name, state, opeid)
    return p.finalize()


def _child(parent: str, child: str, f: dict, ex: ce.Existing, idx, new_man) -> ce.Proposal:
    """One campus or program of a surviving parent."""
    state = f["state"].strip().upper()
    ctype = f["closure_type"]
    label = f"{parent} - {child}"
    p = ce.Proposal(url=f["source_url"], institution=label)

    rec, _ = idx.resolve_child(parent, child, state)
    # A program has no federal OPEID of its own; only a campus does. So we only key a row to an
    # OPEID for a campus, never for a program (that OPEID belongs to the still-open institution).
    use_rec = rec if ctype == "campus" else None

    if use_rec and use_rec["opeid"] in ex.opeids:
        p.skipped.append(f"{label}: already tracked")
        return p.finalize()
    if (normalize(label), state) in ex.name_state:
        p.skipped.append(f"{label}: already tracked")
        return p.finalize()

    if use_rec:
        inst_id = opeid = use_rec["opeid"]
        city, control, level = ce._titlecase(use_rec["city"]), use_rec["control"], use_rec["level"]
        display = use_rec["name"]
        p.matched.append(f"OPEID {use_rec['opeid']} ({use_rec['name']})")
    else:
        inst_id, opeid, display = new_man(), "", label
        # For a program, borrow the parent institution's location/control for context only.
        prec, _ = idx.resolve(parent, state, "")
        city = ce._titlecase(prec["city"]) if prec else ""
        control = prec["control"] if (prec and ctype == "program") else ""
        level = prec["level"] if (prec and ctype == "program") else ""
        if ctype == "program" and not prec:
            p.flags.append(ce.FLAG_INFERRED)
    p.inst_rows.append(ce._inst_row(inst_id, opeid, display, control, level, city, state,
                                    f["year"], ctype, parent, _note(f["note"], f["status"]),
                                    f["source_url"], status=f["status"], cause=f.get("cause", "")))
    ce._register(ex, display, state, opeid)
    return p.finalize()


def build_batch(f: dict) -> ce.Batch:
    """f keys: source_url, name, state, status, closure_type, year (int|None), items (str), note."""
    ex = ce.Existing.load()
    idx = get_index()
    man = [ex.next_man]

    def new_man() -> str:
        man[0] += 1
        return f"MAN-{man[0]:04d}"

    # At-risk and merged are always institution-level; a campus/program is only meaningful for
    # a closure.
    if f["status"] in ("at_risk", "merged") or f["closure_type"] == "institutional":
        return ce.Batch([_institutional(f, ex, idx, new_man)])

    parent = f["name"].strip()
    children = [c.strip() for c in (f.get("items") or "").replace(",", "\n").splitlines() if c.strip()]
    return ce.Batch([_child(parent, c, f, ex, idx, new_man) for c in children])


def commit(f: dict) -> tuple[ce.Batch, dict]:
    batch = build_batch(f)
    ce._append(ce.MANUAL, ce.MANUAL_FIELDS, [r for p in batch.proposals for r in p.inst_rows])
    return batch, batch.counts()
