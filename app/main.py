"""Beyond the Cliff: the closure tracker web app.

FastAPI + Jinja over the read-only SQLite database. Server-rendered pages (no client
framework): a filterable, sortable table of closures with live aggregate charts, plus a
per-institution detail page. Run:

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from math import ceil, floor
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


def asset_version(name: str) -> str:
    """Stamp a static file's modification time onto its URL so a browser cannot serve a stale
    copy of it.

    Without this the stylesheet is requested as a bare /static/app.css, StaticFiles sends no
    Cache-Control, and the browser is free to reuse whatever it already has. Change the CSS and
    the reader keeps the old file against the new markup, which does not fail: it renders. A
    chart whose classes are all missing draws as black polygons with every tooltip stuck open,
    and it looks like the chart is broken rather than the cache. Shipped exactly that once.
    """
    try:
        return str(int((BASE / "static" / name).stat().st_mtime))
    except OSError:
        return "0"


templates.env.globals["asset_version"] = asset_version
# The admin router builds its own Jinja2Templates instance, so it needs the same global or every
# /admin page 500s on base.html's asset_version() call. Register it here, at the composition root.
admin.templates.env.globals["asset_version"] = asset_version


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
    # Operating schools that match the same search. Kept out of `rows` and out of `total`, which
    # are a closure record and a count of closures, and shown in their own band instead.
    open_matches, open_total = queries.search_open(args)
    # Link to the full operating list when the band is only showing a slice of the matches.
    open_all_qs = _qs(**{**{k: v for k, v in args.items() if v}, "status": "open"})

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

    # The sector's own size over time, one frame per sector. Deliberately NOT filtered with the
    # rest of the page: it is the fixed denominator the closure counts are read against, so it
    # stays put while the reader filters the map.
    #
    # Plotted as change since the first year rather than as counts, so the three frames compare
    # directly and the biggest sector does not simply look like the worst one. Zero means "no
    # change", so the axis genuinely starts at zero and nothing is truncated to dramatise a move.
    sector = queries.sector_series()
    sector_chart = ""
    if sector:
        panels = []
        for key in ("private_nonprofit", "public", "private_forprofit"):
            pts = sector.get(key) or []
            if len(pts) < 2:
                continue
            first = pts[0][1]
            change = [(y, 100 * (v - first) / first) for y, v in pts]
            panels.append(
                (queries.CONTROL_LABELS[key], f"{change[-1][1]:+.1f}% since {pts[0][0]}", change)
            )
        if panels:
            first_year = min(y for _, _, pts in panels for y, _ in pts)
            last_year = max(y for _, _, pts in panels for y, _ in pts)
            # Derive the shared scale from the data, never hardcode it. A fixed -35 to +5 window
            # clipped the for-profit line straight off the top of its frame for a decade: that
            # sector grew 12% before it fell, and an axis written from the assumption that every
            # line only falls cannot draw it.
            vals = [v for _, _, pts in panels for _, v in pts]
            ylo = floor((min(vals) - 2) / 5) * 5
            yhi = ceil((max(vals) + 2) / 5) * 5
            ticks = [t for t in range(int(yhi), int(ylo) - 1, -10) if ylo <= t <= yhi]
            sector_chart = charts.small_multiples(
                "How each sector has changed since 2004",
                panels,
                subtitle=(
                    "Colleges still operating each year, against where that sector started. "
                    "Every frame shares one scale, so the three read against each other rather "
                    "than against their own size. For-profit grew by an eighth before it fell. "
                    "The other two only fell."
                ),
                ylo=ylo,
                yhi=yhi,
                ticks=ticks,
                fmt_axis=lambda t: f"{t:+.0f}%" if t else "0%",
                fmt_value=lambda v: f"{v:+.1f}%",
                note=(
                    f"Source: IPEDS HD directory files {first_year} to {last_year} (NCES). "
                    "Institutions NCES marks currently active, counting each college once: "
                    "branch campuses and system offices are excluded, the same rule the "
                    "closure record uses. A count per collection year, not a lifecycle: an "
                    "institution leaving the count has not necessarily closed."
                ),
            )

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "rows": rows,
            "total": total,
            "sector_chart": sector_chart,
            "open_matches": open_matches,
            "open_total": open_total,
            "open_all_qs": open_all_qs,
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
    # The long run first: how many colleges the country has had, and how many students, back to
    # 1869. The closure map shows a sector contracting from a peak; this is the peak. The x-axis is
    # a proportional decade scale; the causes of each turn live in the "what drove the turns" table
    # (queries.national_turns), and the growth rates are computed live (queries.national_growth).
    # The unified overlay: supply (colleges), demand (enrollment), the graduate pool, and real GDP
    # on one ratio-scaled index axis, with the closure flow as context. Interactive via progressive
    # enhancement (static/cliff-timeline.js); the same data dict renders the no-JS fallback. GDP is
    # BEA real GDP (national_series 'real_gdp', from 1929); it is absent, never extrapolated, before
    # then. Closures are our own institutional-closure records, per year.
    # Annual PUBLIC HS graduates, deduped by year (219.10 and 219.20 overlap on some years). This
    # is a separate line, never spliced into the total: its 1971-1985 gap years come from NCES
    # Digest 1995/2000 (rounded, some estimated), so it carries the annual 1970s-80s shape the
    # total line, collected only at intervals then, has to straight-line across.
    _pub_seen: set[int] = set()
    pub_points = []
    for _y, _v in queries.hs_series("United States", "public"):
        if _y not in _pub_seen:
            _pub_seen.add(_y)
            pub_points.append([_y, _v])
    timeline_data = {
        "yearMin": 1869,
        "yearMax": 2025,
        "gdpFrom": 1929,
        "defaultStart": 2000,
        "defaultEnd": 2025,
        "order": ["inst", "enr", "hs", "hspub", "gdp"],
        "defaultOff": ["hspub"],
        "series": {
            "inst": {
                "label": "Colleges (open)",
                "unit": "count",
                "source": "NCES",
                "points": queries.national_series("institutions"),
            },
            "enr": {
                "label": "Enrollment",
                "unit": "people",
                "source": "NCES",
                "points": queries.national_series("enrollment"),
            },
            "hs": {
                "label": "HS graduates",
                "unit": "people",
                "source": "NCES",
                "points": queries.hs_series("United States", "total"),
            },
            "hspub": {
                "label": "HS graduates (public)",
                "short": "public",
                "unit": "people",
                "source": "NCES",
                "points": pub_points,
            },
            "gdp": {
                "label": "Real GDP",
                "unit": "gdp",
                "source": "BEA",
                "points": queries.national_series("real_gdp"),
            },
        },
        "closures": [[c["year"], c["total"]] for c in queries.national_closures_by_control()],
        # The prior demographic contraction, anchored on the verified graduate trough (SY 1993-94,
        # NCES 219.10). Drawn only when the graduate line is shown and 1994 is in the window, so it
        # appears on the 50-year-and-wider views where that era is visible, not on the default.
        "annotations": [{"series": "hs", "year": 1994, "label": "prior graduate contraction"}],
    }
    timeline_chart = charts.national_timeline(
        timeline_data,
        title="A century of colleges, enrollment, graduates, and GDP",
        subtitle=(
            "Indexed to the start of the visible window (=100) on a ratio scale, so a sector that "
            "grew fourfold and one that grew twentyfold read as comparable slopes. Colleges and "
            "enrollment: NCES. High-school graduates: NCES. Real GDP: BEA (FRED GDPCA, chained 2017 "
            "dollars), from 1929. Closures: this tracker's institutional-closure records."
        ),
        note=(
            "Figures before 1974 (colleges) and 1986 (graduates) are collected about once a decade, "
            "so those early stretches are straight lines between sparse points. Real GDP begins in "
            "1929 and is shown only when the window includes it; it is never extrapolated earlier."
        ),
    )
    institutions_chart = charts.line(
        "The number of US colleges, 1869 to 2022",
        queries.national_series("institutions"),
        subtitle=(
            "Every degree-granting institution, counted each period. From 563 colleges after the "
            "Civil War to a peak of 4,726 in 2012, then the decline the closure map tracks. The "
            "1974 step is where branch campuses enter the count, a change in the counting, not a "
            "real surge."
        ),
        note=(
            "Source: NCES Digest of Education Statistics. 1869 to 1969 (decennial): 2022 Table "
            "301.20, branch campuses excluded. 1974 to 2022 (annual): 2023 Table 317.10, branches "
            "included."
        ),
    )
    enrollment_chart = charts.line(
        "US college enrollment, 1869 to 2023",
        queries.national_series("enrollment"),
        subtitle=(
            "Students, not colleges. This is where policy, war, and the economy show. The climb "
            "runs from 2.4 million in 1949 to a peak of 21 million in 2010, then a fall of 11.6 "
            "percent to 2022 and a tick up in 2023. The line stops at the last actual year and "
            "draws no projection."
        ),
        note=(
            "Source: NCES Digest of Education Statistics. 1869 to 1939 (decennial): 2022 Table "
            "301.20. 1947 to 2023 (annual): 2023/2024 Table 303.10; 2023 provisional. Total "
            "enrollment, all institutions, 50 states + DC."
        ),
    )
    # Growth rates computed live from national_series, so a quoted rate can never drift from the
    # data. The era boundaries are editorial; the numbers are not.
    inst_growth = queries.national_growth(
        "institutions",
        [
            (1869, 1889, "founding boom"),
            (1889, 1919, "the plateau"),
            (1919, 2012, "climb to the 2012 peak"),
        ],
    )
    enr_growth = queries.national_growth(
        "enrollment",
        [
            (1869, 2023, "whole period"),
            (1949, 1969, "fastest era"),
            (1969, 1979, "1970s"),
            (1979, 2010, "1979 to the peak"),
            (2010, 2022, "since the peak"),
        ],
    )
    inst_turns = queries.national_turns("institutions")
    enr_turns = queries.national_turns("enrollment")
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
            "timeline_chart": timeline_chart,
            "institutions_chart": institutions_chart,
            "enrollment_chart": enrollment_chart,
            "inst_growth": inst_growth,
            "enr_growth": enr_growth,
            "inst_turns": inst_turns,
            "enr_turns": enr_turns,
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
    inst = data["inst"]
    # Enrollment as one honest trajectory: a line across consecutive sourced years, dashed across
    # gaps, driven by the enrollment table so it renders for any school, dense or sparse.
    evolution_html = charts.enrollment_evolution(
        "The evolution",
        [(r["year"], r["total_headcount"]) for r in data["enrollment"]],
        terminal=inst["status"] in ("closed", "merged"),
        note=(
            "Dots mark the years with a sourced figure; a solid line joins consecutive years, a "
            "dashed line interpolates across the gaps between them. Historical counts can be "
            "whole-institution or cumulative and are not always comparable to a modern headcount: "
            "read the source column below."
        ),
    )
    # The anatomy panel: how the closure happened, from sourced closure_metric figures.
    anatomy_html = charts.anatomy(
        queries.closure_anatomy(data["closure_metrics"]),
        note="Each figure is one sourced record; the readings and signs are computed from them.",
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
            # Floor at COMPOSITE_PLOT_MIN, not the published COMPOSITE_MIN of -1.0. The full
            # scale left roughly 40% of the plot empty and squashed the line into the top half.
            # The thresholds are identical on every school's chart, so they carry the
            # cross-school comparison the fixed floor was there to provide. Chosen from mockups.
            ymin_fixed=queries.COMPOSITE_PLOT_MIN,
            ymax_fixed=queries.COMPOSITE_MAX,
            bands=queries.COMPOSITE_BANDS,
            break_at=queries.COMPOSITE_BREAK,
            label_gutter=118,
            x_all_years=True,
            color_by_band=True,
            direct_last=True,
            y_step=0.5,  # so gridlines land on 1.0 and 1.5, the two lines that decide anything
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
        years = [r["fiscal_year"] for r in s]
        by = {
            k: {r["fiscal_year"]: r[k] for r in s}
            for k in (
                "earned_band",
                "aux_and_other",
                "private_giving",
                "government_grants",
                "total_expenses",
            )
        }
        # Precise band descriptions for the note. When a school reports tuition and auxiliaries as
        # one program-service line, the earned band is that whole line and the second band is only
        # investment and other revenue; when it itemizes, the second band carries the auxiliaries.
        if financials["itemizes_tuition"]:
            aux_desc = (
                "Auxiliaries and other earned carries room, board, investment income and "
                "other revenue."
            )
        else:
            aux_desc = (
                "This school reports tuition, fees, and auxiliaries as one program-service line, "
                "so they appear together and cannot be split; the second band is investment and "
                "other revenue."
            )
        finance_charts.append(
            charts.stacked_money(
                "Where every dollar came from, against what was spent",
                # Bottom-up, ordered by how reliably the money comes back next year: tuition is
                # the base because it is the thing the school controls, government grants sit on
                # top because they are the thing that stops.
                [
                    ("tuition", financials["earned_label"], by["earned_band"]),
                    ("auxother", "Auxiliaries and other earned", by["aux_and_other"]),
                    ("private", "Private gifts", by["private_giving"]),
                    ("govt", "Government grants", by["government_grants"]),
                ],
                ("expense", "Expenses", by["total_expenses"]),
                years=years,
                subtitle=(
                    "Every band is money the school took in that year, and they stack to its total "
                    "revenue. The line is what it spent. Read the strip under the axis for the "
                    "answer to each year, and the bands for what produced it."
                ),
                note=(
                    f"Source: {financials['source']}, {financials['year_range']}, as filed. Fiscal "
                    "years end 30 June. Private gifts is all giving that was not a government "
                    f"grant. {aux_desc}"
                ),
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
            "evolution_html": evolution_html,
            "anatomy_html": anatomy_html,
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
