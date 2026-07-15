"""Beyond the Cliff: the closure tracker web app.

FastAPI + Jinja over the read-only SQLite database. Server-rendered pages (no client
framework): a filterable, sortable table of closures with live aggregate charts, plus a
per-institution detail page. Run:

    uvicorn app.main:app --reload
"""
from __future__ import annotations

from math import ceil
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import admin, charts, queries

BASE = Path(__file__).resolve().parent
PER_PAGE = 50
SORTABLE = ["name", "city", "state", "control", "year", "status"]

app = FastAPI(title="Beyond the Cliff")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))
app.include_router(admin.router)  # browser closure-ingestion console at /admin


def _qs(**overrides) -> str:
    """Build a query string, dropping empties. Used for sort links and pagination so the
    active filters carry across."""
    merged = {k: v for k, v in overrides.items() if v not in ("", None)}
    return "?" + urlencode(merged) if merged else ""


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    q: str = "",
    state: str = "",
    control: str = "",
    status: str = "",
    closure_type: str = "",
    cause: str = "",
    parent: str = "",
    abrupt: str = "",
    has_profile: str = "",
    sort: str = "year",
    order: str = "desc",
    page: int = 1,
):
    if sort not in SORTABLE:
        sort = "year"
    order = "asc" if order == "asc" else "desc"
    page = max(1, page)
    args = {"q": q.strip(), "state": state, "control": control, "status": status,
            "closure_type": closure_type, "cause": cause, "parent": parent, "abrupt": abrupt,
            "has_profile": has_profile}

    rows, total = queries.search(args, sort=sort, order=order, page=page, per_page=PER_PAGE)
    pages = max(1, ceil(total / PER_PAGE))

    base = {k: v for k, v in {**args, "sort": sort, "order": order}.items() if v}
    # For each sortable column: the link toggles asc/desc if it is the active sort.
    sort_links = {}
    for col in SORTABLE:
        nxt = "asc" if (sort == col and order == "desc") else "desc"
        sort_links[col] = _qs(**{**{k: v for k, v in args.items() if v}, "sort": col, "order": nxt})

    # Charts focus on COMPLETED institutional closures (the real school-death signal),
    # combined with the other active filters. status='closed' keeps announced-but-not-yet
    # closed schools and mergers out of the "closures by year" counts. The table below still
    # shows whatever the user filtered to.
    chart_args = {**args, "closure_type": "institutional", "status": "closed", "min_year": 2004}
    chart_html = (
        charts.bars("Institutional closures by year", queries.by_year(chart_args))
        + charts.bars("Institutional closures by control", queries.by_control(chart_args), label_width="15ch")
        + charts.bars("Institutional closures: top states", queries.by_state(chart_args), label_width="4ch")
    )
    # Primary cause of failure, where a sourced cause has been recorded. Uses all closures
    # matching the active filters (any closure type), since cause is not type-specific.
    cause_data = queries.by_cause({**args, "status": "closed"})
    if cause_data:
        chart_html += charts.bars("Closures by primary cause (where recorded)", cause_data,
                                  label_width="22ch")

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "rows": rows,
            "total": total,
            "grand_total": queries.total_count(),
            "page": page,
            "pages": pages,
            "sort": sort,
            "order": order,
            "sort_links": sort_links,
            "charts_html": chart_html,
            "facets": queries.facets(),
            "hcm_summary": queries.hcm_summary(),
            "closure_summary": queries.closure_summary(),
            "args": args,
            "control_labels": queries.CONTROL_LABELS,
            "status_labels": queries.STATUS_LABELS,
            "prev_qs": _qs(**{**base, "page": page - 1}) if page > 1 else "",
            "next_qs": _qs(**{**base, "page": page + 1}) if page < pages else "",
        },
    )


@app.get("/cliff", response_class=HTMLResponse)
def cliff(request: Request, state: str = ""):
    national = charts.line(
        "U.S. high school graduates, 1990 to 2024",
        [(y, v) for y, v in queries.hs_series("United States", "total") if y >= 1990],
        subtitle="Total graduates (public and private). Actuals only: the projected decline (the cliff) begins after 2025.",
        note="Source: NCES Digest of Education Statistics, Table 219.10.",
    )
    states = queries.hs_states()
    if state not in states:
        state = "California"
    state_chart = charts.line(
        f"{state}: public high school graduates",
        queries.hs_series(state, "public"),
        subtitle="Public high school graduates by school year.",
        note="Source: NCES Digest of Education Statistics, Table 219.20.",
    )
    changes = queries.hs_recent_change(since=2013)
    decliners = charts.bars(
        "Steepest declines in public graduates, 2013 to 2024 (%)",
        [(j, abs(pct)) for j, pct in changes if pct < 0][:12], label_width="16ch",
    )
    return templates.TemplateResponse(
        request, "cliff.html",
        {"national_chart": national, "state_chart": state_chart, "decliners": decliners,
         "states": states, "state": state,
         "growth": [(j, pct) for j, pct in reversed(changes)][:5],
         "decline": [(j, pct) for j, pct in changes][:5]},
    )


@app.get("/institution/{inst_id}", response_class=HTMLResponse)
def institution(request: Request, inst_id: str):
    data = queries.get_institution(inst_id)
    if data is None:
        return HTMLResponse("<h1>Not found</h1>", status_code=404)
    trend_html = charts.trend(
        "Enrollment (12-month headcount)",
        [(r["year"], r["total_headcount"]) for r in data["enrollment"]],
    )
    # HCM banner: when did the distress signal first appear relative to closure?
    hcm_first = data["hcm"][0]["as_of_date"] if data["hcm"] else None
    hcm_lead_years = None
    if hcm_first and data["inst"]["status_year"]:
        hcm_lead_years = data["inst"]["status_year"] - int(hcm_first[:4])
    return templates.TemplateResponse(
        request,
        "institution.html",
        {
            "control_labels": queries.CONTROL_LABELS,
            "status_labels": queries.STATUS_LABELS,
            "cause_labels": queries.CAUSE_LABELS,
            "trend_html": trend_html,
            "hcm_first": hcm_first,
            "hcm_lead_years": hcm_lead_years,
            "hcm_has_severe": any(r["level"] == "2" for r in data["hcm"]),
            "scorecard": queries.scorecard_profile(inst_id),
            **data,
        },
    )
