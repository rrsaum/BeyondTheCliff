"""The browser ingestion console: paste College Evaluator closure URLs, review a parsed
preview with honesty flags, and approve to write the rows and rebuild the tracker database.

This is the whole ingestion workflow moved into the browser: no terminal, no file editing.
GET /admin shows the form; POST /admin/preview drafts the rows (writing nothing); POST
/admin/commit appends the approved rows to the CSV source-of-truth and rebuilds the SQLite DB
in-process. Form bodies are parsed with parse_qs so no extra dependency is needed.

The rebuild recreates data/beyondthecliff.db from the CSVs (scripts/build_db.py). The app reads
the DB read-only and opens a fresh connection per request, so a rebuild between requests is safe
for this single-user local tool.
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from . import ce_ingest, edit_record, news_ingest, queries

BASE = Path(__file__).resolve().parent
SCRIPTS = BASE.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE / "templates"))


async def _urls_from_body(request: Request) -> tuple[str, list[str]]:
    raw = (await request.body()).decode("utf-8", errors="replace")
    fields = parse_qs(raw, keep_blank_values=True)
    text = (fields.get("urls", [""])[0]).strip()
    urls = [u.strip() for u in text.replace(",", "\n").splitlines() if u.strip()]
    return text, urls


async def _news_fields(request: Request) -> dict:
    raw = (await request.body()).decode("utf-8", errors="replace")
    g = parse_qs(raw, keep_blank_values=True)

    def one(key: str) -> str:
        return (g.get(key, [""])[0]).strip()

    status = one("status") if one("status") in news_ingest.STATUSES else "announced"
    ctype = one("closure_type") if one("closure_type") in news_ingest.TYPES else "institutional"
    cause = one("cause") if one("cause") in queries.CAUSE_LABELS else ""
    return {
        "source_url": one("source_url"), "name": one("name"),
        "state": one("state").upper(), "status": status, "closure_type": ctype,
        "year": one("year"), "items": one("items"), "note": one("note"),
        "acquirer": one("acquirer"), "cause": cause,
    }


def rebuild_db() -> str:
    """Rebuild the SQLite DB from the CSVs. Returns '' on success or an error message."""
    import importlib

    import build_db  # from scripts/, on sys.path above
    importlib.reload(build_db)  # pick up any CSV path changes cleanly
    try:
        build_db.main()
        return ""
    except SystemExit as exc:  # build_db raises SystemExit(message) on a bad row
        return str(exc)
    except Exception as exc:  # noqa: BLE001  surface anything else to the browser
        return f"{type(exc).__name__}: {exc}"


@router.get("/admin", response_class=HTMLResponse)
def admin_form(request: Request):
    return templates.TemplateResponse(request, "admin.html", {})


@router.post("/admin/preview", response_class=HTMLResponse)
async def admin_preview(request: Request):
    text, urls = await _urls_from_body(request)
    if not urls:
        return templates.TemplateResponse(request, "admin.html",
                                          {"error": "Paste at least one College Evaluator URL."})
    batch = ce_ingest.build_batch(urls)
    return templates.TemplateResponse(
        request, "admin_preview.html",
        {"batch": batch, "counts": batch.counts(), "urls_text": text,
         "ADD": ce_ingest.ADD, "SKIP": ce_ingest.SKIP, "HOLD": ce_ingest.HOLD},
    )


@router.post("/admin/commit", response_class=HTMLResponse)
async def admin_commit(request: Request):
    _text, urls = await _urls_from_body(request)
    if not urls:
        return templates.TemplateResponse(request, "admin.html",
                                          {"error": "No URLs to commit."})
    batch, counts = ce_ingest.commit(urls)
    db_error = rebuild_db()
    added = [r for p in batch.proposals for r in p.inst_rows]
    return templates.TemplateResponse(
        request, "admin_result.html",
        {"counts": counts, "added": added, "db_error": db_error},
    )


@router.post("/admin/news/preview", response_class=HTMLResponse)
async def news_preview(request: Request):
    f = await _news_fields(request)
    if not f["source_url"] or not f["name"]:
        return templates.TemplateResponse(request, "admin.html",
                                          {"error": "A source URL and an institution name are required."})
    batch = news_ingest.build_batch(f)
    return templates.TemplateResponse(
        request, "admin_news_preview.html",
        {"batch": batch, "counts": batch.counts(), "f": f},
    )


@router.post("/admin/news/commit", response_class=HTMLResponse)
async def news_commit(request: Request):
    f = await _news_fields(request)
    if not f["source_url"] or not f["name"]:
        return templates.TemplateResponse(request, "admin.html",
                                          {"error": "A source URL and an institution name are required."})
    batch, counts = news_ingest.commit(f)
    db_error = rebuild_db()
    added = [r for p in batch.proposals for r in p.inst_rows]
    return templates.TemplateResponse(
        request, "admin_result.html",
        {"counts": counts, "added": added, "db_error": db_error},
    )


@router.get("/admin/edit", response_class=HTMLResponse)
def edit_form(request: Request, id: str = ""):
    record = edit_record.load(id.strip()) if id.strip() else None
    return templates.TemplateResponse(
        request, "admin_edit.html",
        {"id": id.strip(), "record": record,
         "not_found": bool(id.strip()) and record is None,
         "statuses": edit_record.STATUSES, "closure_types": edit_record.CLOSURE_TYPES,
         "controls": edit_record.CONTROLS, "levels": edit_record.LEVELS,
         "causes": edit_record.CAUSES, "cause_labels": queries.CAUSE_LABELS,
         "status_labels": queries.STATUS_LABELS},
    )


@router.post("/admin/edit/commit", response_class=HTMLResponse)
async def edit_commit(request: Request):
    raw = (await request.body()).decode("utf-8", errors="replace")
    g = parse_qs(raw, keep_blank_values=True)
    inst_id = (g.get("id", [""])[0]).strip()
    updates = {k: (g.get(k, [""])[0]) for k in edit_record.EDITABLE}
    err = edit_record.update(inst_id, updates)
    if err:
        record = edit_record.load(inst_id)
        return templates.TemplateResponse(
            request, "admin_edit.html",
            {"id": inst_id, "record": record, "error": err, "not_found": record is None,
             "statuses": edit_record.STATUSES, "closure_types": edit_record.CLOSURE_TYPES,
             "controls": edit_record.CONTROLS, "levels": edit_record.LEVELS,
             "causes": edit_record.CAUSES, "cause_labels": queries.CAUSE_LABELS,
             "status_labels": queries.STATUS_LABELS},
        )
    db_error = rebuild_db()
    return templates.TemplateResponse(
        request, "admin_edit_result.html",
        {"id": inst_id, "record": edit_record.load(inst_id), "db_error": db_error},
    )
