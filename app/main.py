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
    args = {
        "q": q.strip(),
        "state": state,
        "control": control,
        "status": status,
        "closure_type": closure_type,
        "cause": cause,
        "parent": parent,
        "abrupt": abrupt,
        "has_profile": has_profile,
    }

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
        + charts.bars(
            "Institutional closures by control", queries.by_control(chart_args), label_width="15ch"
        )
        + charts.bars(
            "Institutional closures: top states", queries.by_state(chart_args), label_width="4ch"
        )
    )
    # Primary cause of failure, where a sourced cause has been recorded. Uses all closures
    # matching the active filters (any closure type), since cause is not type-specific.
    cause_data = queries.by_cause({**args, "status": "closed"})
    if cause_data:
        chart_html += charts.bars(
            "Closures by primary cause (where recorded)", cause_data, label_width="22ch"
        )

    # The sector's actual size over time, from IPEDS. Deliberately NOT filtered with the rest of
    # the page: it is the fixed denominator the closure counts are read against, so it stays put
    # while the reader filters the map. Broken out by control because the aggregate misleads.
    sector = queries.sector_series()
    sector_chart = ""
    if sector:
        by = sector["by_control"]
        sector_chart = charts.series_lines(
            "How many colleges are left",
            [
                (queries.CONTROL_LABELS[k], suffix, by.get(k, []))
                for k, suffix in (
                    ("private_nonprofit", "nonprofit"),
                    ("public", "public"),
                    ("private_forprofit", "forprofit"),
                )
            ],
            subtitle=(
                "Institutions still operating each year, counted from the federal directory. "
                "The three lines move for different reasons, which is why they are drawn "
                "separately: the steep fall is the for-profit sector contracting, and reading it "
                "as the whole sector's decline would overstate what happened to everyone else."
            ),
            fmt_axis=lambda v: f"{v:,.0f}",
            fmt_point=lambda y, v: f"{y}: {v:,.0f} operating",
            note=(
                f"Source: IPEDS HD directory files {sector['first_year']} to "
                f"{sector['latest_year']} (NCES), institutions marked currently active. "
                "A count per collection year, not a lifecycle: an institution leaving the "
                "count has not necessarily closed."
            ),
            css="sector-chart",
        )

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "rows": rows,
            "total": total,
            "sector": sector,
            "sector_chart": sector_chart,
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
        [(j, abs(pct)) for j, pct in changes if pct < 0][:12],
        label_width="16ch",
    )
    return templates.TemplateResponse(
        request,
        "cliff.html",
        {
            "national_chart": national,
            "state_chart": state_chart,
            "decliners": decliners,
            "states": states,
            "state": state,
            "growth": [(j, pct) for j, pct in reversed(changes)][:5],
            "decline": [(j, pct) for j, pct in changes][:5],
        },
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
    # ED's Financial Responsibility Composite Score history. One score is a number; the series
    # is the story, so the chart appears as soon as there are two award years to draw.
    composite = queries.composite_series(inst_id)
    composite_chart = ""
    if composite and composite["count"] >= 2:
        composite_chart = charts.series_lines(
            "What the federal government scored this school",
            [("Composite score", "score", composite["points"])],
            subtitle=(
                "The score the U.S. Dept. of Education gives a school each year, from its "
                "audited accounts, to decide whether it is financially sound enough to keep "
                "handling federal student aid. Anything under 1.5 puts the school under extra "
                "federal oversight."
            ),
            fmt_axis=lambda v: f"{v:.1f}",
            fmt_point=lambda y, v: f"{y}: {v:.1f}",
            ymin_fixed=queries.COMPOSITE_MIN,
            ymax_fixed=queries.COMPOSITE_MAX,
            bands=queries.COMPOSITE_BANDS,
            break_at=queries.COMPOSITE_BREAK,
            note=(
                f"Source: {queries.COMPOSITE_SOURCE}, {composite['span'][0]} to "
                f"{composite['span'][1]}. Scored -1.0 to 3.0. The Department rewrote the "
                "ratios behind the score effective 1 July 2020, so the two segments are not "
                "the same measurement and are not joined."
            ),
            css="score-chart",
        )

    financials = queries.financial_series(inst_id)
    finance_charts = []
    if financials:
        s = financials["series"]
        finance_charts.append(
            charts.money_lines(
                "What the school earned, and what it spent",
                [
                    ("Total revenue", "total", [(r["fiscal_year"], r["total_revenue"]) for r in s]),
                    (
                        "Earned revenue (tuition, fees, auxiliaries, investments)",
                        "earned",
                        [
                            (
                                r["fiscal_year"],
                                None
                                if None in (r["total_revenue"], r["contributions"])
                                else r["total_revenue"] - r["contributions"],
                            )
                            for r in s
                        ],
                    ),
                    (
                        "Total expenses",
                        "expense",
                        [(r["fiscal_year"], r["total_expenses"]) for r in s],
                    ),
                ],
                subtitle=(
                    "The distance between earned revenue and expenses is the part of the year that "
                    "gifts and grants have to cover. Where the two lines sit relative to each other, "
                    "and whether that distance is closing, is the question this page exists to answer."
                ),
                note=f"Source: {financials['source']}, {financials['year_range']}. Fiscal years end 30 June.",
            )
        )
        if any(r["government_grants"] is not None for r in s):
            finance_charts.append(
                charts.money_lines(
                    "Who the money came from",
                    [
                        (
                            "Government grants",
                            "govt",
                            [(r["fiscal_year"], r["government_grants"]) for r in s],
                        ),
                        (
                            "Private giving",
                            "earned",
                            [(r["fiscal_year"], r["other_contributions"]) for r in s],
                        ),
                    ],
                    subtitle=(
                        "Gifts and government grants land in the same line on the summary page, but "
                        "they behave differently: a relief programme ends on a date somebody else set, "
                        "while a donor can be asked again."
                    ),
                    note=f"Source: {financials['source']}, Part VIII lines 1e and 1f.",
                )
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
            "composite": composite,
            "composite_chart": composite_chart,
            "composite_reading": queries.composite_reading,
            "financials": financials,
            "finance_charts": finance_charts,
            **data,
        },
    )
