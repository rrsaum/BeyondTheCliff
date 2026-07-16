"""All SQL for the tracker. Filters are parameterized; sort columns are whitelisted, so a
query string can never inject SQL. Every list/chart query shares the same _filters() clause,
so the charts always reflect the same subset the table shows.
"""

from __future__ import annotations

from .db import connect

# Whitelist: request sort key -> real column. Anything else falls back to close year.
SORT_COLUMNS = {
    "name": "i.name",
    "city": "i.city",
    "state": "i.state",
    "control": "i.control",
    "year": "i.status_year",
    "status": "i.status",
}

CONTROL_LABELS = {
    "public": "Public",
    "private_nonprofit": "Private nonprofit",
    "private_forprofit": "Private for-profit",
}
STATUS_LABELS = {
    "closed": "Closed",
    "merged": "Merged/consolidated",
    "announced": "Announced (upcoming)",
    "at_risk": "At-risk (open)",
    "open": "Operating",
}
CLOSURE_TYPE_LABELS = {
    "institutional": "Institutional closure",
    "campus": "Campus closure",
    "program": "Program closure",
}

# ED's own reading of the Financial Responsibility Composite Score, kept here rather than in the
# composite_score table: the score is the published fact, these thresholds are the interpretation
# ED applies to it, and separating them means a rule change never requires a reimport.
#
#   >= 1.5    financially responsible. 34 CFR 668.171(b)(1): the Department considers an
#             institution financially responsible if its ratios "yield a composite score of at
#             least 1.5".
#   1.0 - 1.4 the "zone": still financially responsible, but ED imposes added oversight, and an
#             institution may use the zone alternative "for no more than three consecutive
#             years" (34 CFR 668.175(d)(1)).
#   < 1.0     not financially responsible. To keep participating the school must post a letter
#             of credit worth "not less than one-half of the title IV, HEA program funds" it
#             received last fiscal year (34 CFR 668.175(c)).
#
# Scored on a scale of -1.0 to 3.0 (84 FR 49919, appendix A: strength factor scores are capped
# at 3 and floored at -1). Only the trouble bands are shaded: passing is the unmarked default.
# The published scale is -1.0 to 3.0 and COMPOSITE_MIN records that, because it is a fact about
# ED's measure and belongs in the copy. COMPOSITE_PLOT_MIN is what the chart floors at, and it is
# a separate number on purpose: plotting the full scale left about 40% of the panel empty and
# compressed every real score into the top half. Scores below 0.5 are rare and would clip, so
# raise this floor only after checking the school actually charts (see charts.series_lines).
COMPOSITE_MIN, COMPOSITE_MAX = -1.0, 3.0
COMPOSITE_PLOT_MIN = 0.5
COMPOSITE_BANDS = [
    (-1.0, 1.0, "fail", "Below 1.0: letter of credit"),
    (1.0, 1.5, "zone", "1.0 to 1.4: added oversight"),
    (1.5, 3.0, "pass", "1.5 and above: responsible"),
]

# ED rewrote the ratio definitions in 84 FR 49788, effective 1 July 2020: leases moved onto the
# balance sheet (FASB Topic 842), intangibles and unsecured related-party receivables came out.
# Scores either side of that are computed from different formulas on the same -1.0 to 3.0 scale,
# so a level shift across it is not necessarily a change in a school's finances. The award-year
# files are fiscal-year windows, so the boundary falls between AY 2019-20 (fiscal years ending
# by 30 June 2020, old formula) and AY 2020-21 (new). Drawn as a break, never joined across.
# Inference, flagged as such: ED states the effective date, not the file-year mapping.
COMPOSITE_BREAK = (2020.5, "ED changed the formula")

COMPOSITE_SOURCE = "Financial Responsibility Composite Score, U.S. Dept. of Education (eZ-Audit)"


def composite_reading(score: float | None) -> tuple[str, str]:
    """ED's reading of a score: (css suffix, plain-language label). Interpretation, not data."""
    if score is None:
        return "", "Not reported"
    if score >= 1.5:
        return "pass", "Financially responsible"
    if score >= 1.0:
        return "zone", "Responsible, with added federal oversight"
    return "fail", "Not financially responsible without a letter of credit"


CAUSE_LABELS = {
    "financial": "Financial insolvency",
    "enrollment": "Enrollment / demographic decline",
    "accreditation": "Loss of accreditation",
    "sponsor": "Sponsor withdrawal",
    "misconduct": "Fraud / mismanagement",
    "disaster": "Disaster / fire",
    "restructuring": "State restructuring",
    "external": "External shock (war / pandemic)",
    "benefactor": "Benefactor collapse",
}


def _filters(args: dict) -> tuple[str, list]:
    where, params = [], []
    if args.get("q"):
        # Match every word of the query independently, against the current name OR any former
        # name (institution_name). So "laurel" finds John Wesley University, and
        # "everest greenspoint" finds the record named "Altierus ... Greenspoint" whose former
        # name is "Everest Institute-Greenspoint" (words split across current and former name).
        for word in args["q"].split()[:6]:  # cap to keep the query bounded
            where.append(
                "(i.name LIKE ? OR EXISTS (SELECT 1 FROM institution_name n "
                "WHERE n.institution_id = i.id AND n.name LIKE ?))"
            )
            params.append(f"%{word}%")
            params.append(f"%{word}%")
    if args.get("state"):
        where.append("i.state = ?")
        params.append(args["state"])
    if args.get("min_year"):
        # Floor for the modern cliff charts, so historical closures (e.g. authoritative state
        # lists reaching back to the 1930s) do not distort "closures by year / by state".
        where.append("i.status_year >= ?")
        params.append(int(args["min_year"]))
    if args.get("control"):
        where.append("i.control = ?")
        params.append(args["control"])
    if args.get("status"):
        where.append("i.status = ?")
        params.append(args["status"])
    if args.get("closure_type"):
        where.append("i.closure_type = ?")
        params.append(args["closure_type"])
    if args.get("cause"):
        where.append("i.cause = ?")
        params.append(args["cause"])
    if args.get("parent"):
        where.append("i.parent_name = ?")
        params.append(args["parent"])
    if args.get("has_profile"):
        where.append("EXISTS (SELECT 1 FROM scorecard s WHERE s.institution_id = i.id)")
    if args.get("abrupt"):
        where.append(
            "EXISTS (SELECT 1 FROM event e WHERE e.institution_id = i.id AND e.abrupt = 1)"
        )
    # A still-operating school is in this dataset for its financial record, as a survivor case
    # (data/institutions_open.csv), and is NOT a closure. Excluded from every list row, chart
    # bar, and count here, because listing a healthy school on a closure map misrepresents it.
    # Only an explicit status=open filter surfaces one.
    if args.get("status") != "open":
        where.append("i.status <> 'open'")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    return clause, params


def search(args: dict, sort: str, order: str, page: int, per_page: int) -> tuple[list, int]:
    clause, params = _filters(args)
    col = SORT_COLUMNS.get(sort, "i.status_year")
    direction = "ASC" if order == "asc" else "DESC"
    offset = (page - 1) * per_page
    conn = connect()
    total = conn.execute(f"SELECT count(*) FROM institution i{clause}", params).fetchone()[0]
    # ({col} IS NULL) sorts NULLs last portably (no NULLS LAST, which older SQLite lacks).
    rows = conn.execute(
        f"""SELECT i.id, i.name, i.city, i.state, i.control, i.level, i.status, i.status_year,
                   i.closure_type, i.cause,
                   (SELECT max(e.abrupt) FROM event e WHERE e.institution_id = i.id) AS abrupt,
                   EXISTS (SELECT 1 FROM scorecard s WHERE s.institution_id = i.id) AS has_profile
            FROM institution i{clause}
            ORDER BY ({col} IS NULL), {col} {direction}, i.name ASC
            LIMIT ? OFFSET ?""",
        params + [per_page, offset],
    ).fetchall()
    conn.close()
    return rows, total


def search_open(args: dict, limit: int = 6) -> tuple[list, int]:
    """(rows, total) for operating schools matching a name search, SEPARATE from the closures.

    _filters() keeps operating schools out of every list, chart, and count, which is right when
    someone is browsing a closure map and wrong when they type a school's name into it. A search
    for "montreat" that returns two closed Montreat campuses and not Montreat College is not
    protecting anyone: the school is in the database, and hiding it reads as an empty result, not
    as a careful distinction.

    So this runs only when there is an actual query, and the caller renders the rows in their own
    band. They are never merged into the closure table or added to its count, because the count
    is a claim about how many schools closed.

    Skipped when the reader has already picked a status: they asked for one thing, so answer it.

    Returns a total alongside a capped list because the open roster is the whole IPEDS
    directory, thousands of schools. A precise search ("montreat") matches one and the list is
    the answer. A loose one ("university") matches hundreds, where listing an arbitrary handful
    is noise pretending to be a result: the caller shows the count and a link instead.
    """
    if not args.get("q") or args.get("status"):
        return [], 0
    open_args = {k: args[k] for k in ("q", "state", "control") if args.get(k)}
    open_args["status"] = "open"
    clause, params = _filters(open_args)
    conn = connect()
    total = conn.execute(f"SELECT count(*) FROM institution i{clause}", params).fetchone()[0]
    rows = conn.execute(
        f"""SELECT i.id, i.name, i.city, i.state, i.control, i.level,
                   EXISTS (SELECT 1 FROM financial_filing f WHERE f.institution_id = i.id)
                       AS has_financials
            FROM institution i{clause}
            ORDER BY i.name ASC
            LIMIT ?""",
        params + [limit],
    ).fetchall()
    conn.close()
    return rows, total


def _group_count(args: dict, col_sql: str, *, by_label: bool, limit: int | None) -> list[tuple]:
    clause, params = _filters(args)
    # Exclude rows where the grouped column is NULL/blank, whether or not filters exist.
    joiner = " AND " if clause else " WHERE "
    clause = f"{clause}{joiner}{col_sql} IS NOT NULL AND {col_sql} <> ''"
    order = "ORDER BY 1" if by_label else "ORDER BY 2 DESC, 1"
    lim = f" LIMIT {int(limit)}" if limit else ""
    conn = connect()
    rows = conn.execute(
        f"SELECT {col_sql} AS k, count(*) AS c FROM institution i{clause} GROUP BY 1 {order}{lim}",
        params,
    ).fetchall()
    conn.close()
    return [(r[0], r[1]) for r in rows]


def by_year(args: dict) -> list[tuple]:
    return _group_count(args, "i.status_year", by_label=True, limit=None)


def by_control(args: dict) -> list[tuple]:
    rows = _group_count(args, "i.control", by_label=False, limit=None)
    return [(CONTROL_LABELS.get(k, k), c) for k, c in rows]


def by_state(args: dict, limit: int = 12) -> list[tuple]:
    return _group_count(args, "i.state", by_label=False, limit=limit)


def facets() -> dict:
    conn = connect()
    states = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT state FROM institution WHERE state <> '' ORDER BY state"
        )
    ]
    conn.close()
    return {
        "states": states,
        "controls": CONTROL_LABELS,
        "statuses": STATUS_LABELS,
        "closure_types": CLOSURE_TYPE_LABELS,
        "causes": CAUSE_LABELS,
    }


def by_cause(args: dict) -> list[tuple]:
    rows = _group_count(args, "i.cause", by_label=False, limit=None)
    return [(CAUSE_LABELS.get(k, k), c) for k, c in rows]


def total_count() -> int:
    """How many closures/consolidations the tracker holds. Excludes surviving institutions,
    which are here for their financials only: counting one as a closure would overstate the
    record by exactly the schools the brand exists to help."""
    conn = connect()
    n = conn.execute("SELECT count(*) FROM institution WHERE status <> 'open'").fetchone()[0]
    conn.close()
    return n


def closure_summary() -> dict:
    """Counts of COMPLETED closures by type (institutional = the institution closed; campus =
    a branch closed while the parent survives; program = a program ended while the school
    stays open), plus merged and the count of announced-but-not-yet-closed schools. The
    distinctions are load-bearing: a campus or program closure is not a school dying, and an
    announced closure has not happened yet."""
    conn = connect()
    rows = dict(
        conn.execute(
            "SELECT closure_type, count(*) FROM institution "
            "WHERE status = 'closed' AND closure_type IS NOT NULL GROUP BY closure_type"
        ).fetchall()
    )
    merged = conn.execute("SELECT count(*) FROM institution WHERE status = 'merged'").fetchone()[0]
    announced = conn.execute(
        "SELECT count(*) FROM institution WHERE status = 'announced'"
    ).fetchone()[0]
    at_risk = conn.execute("SELECT count(*) FROM institution WHERE status = 'at_risk'").fetchone()[
        0
    ]
    conn.close()
    return {
        "institutional": rows.get("institutional", 0),
        "campus": rows.get("campus", 0),
        "program": rows.get("program", 0),
        "merged": merged,
        "announced": announced,
        "at_risk": at_risk,
    }


def scorecard_profile(inst_id: str) -> dict | None:
    """Latest available Scorecard value per metric (fields report in different years, so we
    take the most recent non-null for each), plus interpretive closure-risk flags. Source:
    U.S. Dept. of Education College Scorecard."""
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM scorecard WHERE institution_id = ? ORDER BY year", (inst_id,)
    ).fetchall()
    conn.close()
    if not rows:
        return None

    # Coerce to float and skip anything non-numeric (e.g. a stray Scorecard suppression
    # marker like 'PS'), so a bad cell can never crash the page.
    latest: dict[str, tuple] = {}
    for r in rows:
        for k in (
            "ugds",
            "adm_rate",
            "pct_pell",
            "tuitfte",
            "tuitionfee_in",
            "costt4_a",
            "pptug_ef",
            "ugds_white",
            "ugds_black",
            "ugds_hisp",
            "first_gen",
        ):
            if r[k] is not None:
                try:
                    latest[k] = (float(r[k]), r["year"])
                except (TypeError, ValueError):
                    pass

    def val(k):
        return latest[k][0] if k in latest else None

    def pct(x):
        return f"{round(x * 100)}%" if x is not None else None

    def dollars(x):
        return f"${int(x):,}" if x is not None else None

    metrics = [
        (
            "Undergraduates",
            f"{int(val('ugds')):,}" if val("ugds") is not None else None,
            latest.get("ugds", (None, None))[1],
        ),
        ("Admission rate", pct(val("adm_rate")), latest.get("adm_rate", (None, None))[1]),
        ("On Pell grants", pct(val("pct_pell")), latest.get("pct_pell", (None, None))[1]),
        ("Net tuition / student", dollars(val("tuitfte")), latest.get("tuitfte", (None, None))[1]),
        (
            "In-state tuition + fees",
            dollars(val("tuitionfee_in")),
            latest.get("tuitionfee_in", (None, None))[1],
        ),
        (
            "Avg cost of attendance",
            dollars(val("costt4_a")),
            latest.get("costt4_a", (None, None))[1],
        ),
        ("Part-time undergrads", pct(val("pptug_ef")), latest.get("pptug_ef", (None, None))[1]),
        ("First-generation", pct(val("first_gen")), latest.get("first_gen", (None, None))[1]),
    ]
    metrics = [m for m in metrics if m[1] is not None]

    demo = None
    if any(val(k) is not None for k in ("ugds_white", "ugds_black", "ugds_hisp")):
        demo = f"White {pct(val('ugds_white')) or '?'}, Black {pct(val('ugds_black')) or '?'}, Hispanic {pct(val('ugds_hisp')) or '?'}"

    flags = []
    if val("adm_rate") is not None and val("adm_rate") >= 0.75:
        flags.append(f"Non-selective: admitted {pct(val('adm_rate'))} of applicants")
    if val("pct_pell") is not None and val("pct_pell") >= 0.40:
        flags.append(f"High low-income reliance: {pct(val('pct_pell'))} on Pell grants")
    if val("ugds") is not None and val("ugds") < 1000:
        flags.append(f"Small: {int(val('ugds')):,} undergraduates")

    years = [r["year"] for r in rows]
    return {
        "metrics": metrics,
        "demographics": demo,
        "flags": flags,
        "year_range": f"{min(years)} to {max(years)}",
    }


# Substrings that fold a filing's free-text revenue labels into buckets. Substrings, not exact
# matches, because each school writes its own labels and they drift year to year.
_LINE_BUCKETS: dict[str, tuple[str, ...]] = {
    # Both spellings are real: Montreat's TY2012 and TY2013 filings say "TUITITION AND FEES".
    # This is why financial_line_item stores the label verbatim and matches here instead.
    "tuition": ("TUIT",),
    "auxiliary": ("AUXILIAR", "ROOM", "BOARD", "HOUSING", "DINING"),
}


def _line_totals(conn, inst_id: str) -> dict[int, dict[str, int]]:
    """Program service revenue line items folded into buckets, per tax year.

    The 990 lets each school write its own labels, so this matches on a substring of the
    verbatim description. Anything unmatched is deliberately left out of the buckets rather
    than forced into one.
    """
    out: dict[int, dict[str, int]] = {}
    rows = conn.execute(
        "SELECT tax_year, description, amount FROM financial_line_item "
        "WHERE institution_id = ? AND amount IS NOT NULL",
        (inst_id,),
    ).fetchall()
    for r in rows:
        desc = (r["description"] or "").upper()
        for bucket, needles in _LINE_BUCKETS.items():
            if any(n in desc for n in needles):
                year = out.setdefault(r["tax_year"], {})
                year[bucket] = year.get(bucket, 0) + r["amount"]
                break
    return out


def _ratio(numerator, denominator):
    """Guarded division: None unless both sides are real numbers and the denominator is > 0."""
    if numerator is None or not denominator:
        return None
    return numerator / denominator


def financial_series(inst_id: str) -> dict | None:
    """A school's Form 990 history plus the ratios computed from it.

    Ratios are computed here, never stored (see scripts/schema.sql): the filing rows hold only
    what the IRS record says, so a definition can change without a reimport and every number on
    the page traces back to one line of one filing.

    Each row carries its own tax year and fiscal period end. Missing years are reported rather
    than interpolated: a gap in the filings is a fact about the record, and a chart that joins
    across it would invent a trend that was never filed.
    """
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM financial_filing WHERE institution_id = ? ORDER BY tax_year", (inst_id,)
    ).fetchall()
    if not rows:
        conn.close()
        return None
    buckets = _line_totals(conn, inst_id)
    conn.close()

    series = []
    for r in rows:
        line = buckets.get(r["tax_year"], {})
        tuition = line.get("tuition")
        series.append(
            {
                "tax_year": r["tax_year"],
                # Label from the fiscal year end, not the tax year: a TaxYr 2024 filing covers the
                # year ending 30 June 2025, and "FY2025" is what the school's own CFO would call it.
                "fiscal_year": int(r["period_end"][:4]) if r["period_end"] else r["tax_year"] + 1,
                "period_end": r["period_end"],
                "total_revenue": r["total_revenue"],
                "contributions": r["contributions"],
                "government_grants": r["government_grants"],
                "other_contributions": r["other_contributions"],
                "program_svc_revenue": r["program_svc_revenue"],
                "total_expenses": r["total_expenses"],
                "net_income": r["net_income"],
                "total_assets": r["total_assets"],
                "total_liabilities": r["total_liabilities"],
                "net_assets": r["net_assets"],
                "employees": r["employees"] or None,  # a filed 0 means "not reported", not "none"
                "tuition": tuition,
                "grants_paid": r["grants_paid"],
                # Share of all revenue earned from students (tuition, fees, auxiliaries). The higher
                # this runs, the more a demographic dip lands straight on the operating budget.
                "program_dependency": _ratio(r["program_svc_revenue"], r["total_revenue"]),
                "contribution_share": _ratio(r["contributions"], r["total_revenue"]),
                "operating_margin": _ratio(r["net_income"], r["total_revenue"]),
                # How much of the year's expenses the school covered from what it earned itself,
                # setting contributions aside. This is NOT a pass/fail line: a private nonprofit
                # college is built to run on gifts and endowment, so a value under 1 is ordinary
                # rather than fatal. It answers a narrower question, and the useful one for a
                # reader running a school: how much of this operation depends on money that has to
                # be raised again next year.
                "self_funded_ratio": _ratio(
                    None
                    if None in (r["total_revenue"], r["contributions"])
                    else r["total_revenue"] - r["contributions"],
                    r["total_expenses"],
                ),
                # Of the money given to the school, how much came from government rather than
                # donors. The distinction has a schedule attached: relief programs end on a date,
                # donors can be asked again.
                "govt_share_of_contributions": _ratio(r["government_grants"], r["contributions"]),
                # Institutional aid measured against tuition revenue. NOT labelled a discount rate:
                # that requires knowing whether the filing reports tuition gross or net of aid, and
                # the 990 does not say. Stated as the ratio it is, on the basis it has.
                "aid_to_tuition": _ratio(r["grants_paid"], tuition),
                "debt_to_assets": _ratio(r["total_liabilities"], r["total_assets"]),
            }
        )

    years = [s["tax_year"] for s in series]
    gaps = [y for y in range(min(years), max(years) + 1) if y not in years]
    return {
        "series": series,
        "latest": series[-1],
        "first": series[0],
        "gap_years": gaps,
        "source": rows[0]["source"],
        "source_url": rows[0]["source_url"],
        "year_range": f"FY{series[0]['fiscal_year']} to FY{series[-1]['fiscal_year']}",
    }


def hs_series(jurisdiction: str, measure: str = "total") -> list[tuple]:
    conn = connect()
    rows = conn.execute(
        "SELECT year, graduates FROM hs_graduates WHERE jurisdiction = ? AND measure = ? "
        "ORDER BY year",
        (jurisdiction, measure),
    ).fetchall()
    conn.close()
    return [(r[0], r[1]) for r in rows]


def hs_states() -> list[str]:
    conn = connect()
    rows = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT jurisdiction FROM hs_graduates WHERE jurisdiction_type = 'state' "
            "ORDER BY jurisdiction"
        )
    ]
    conn.close()
    return rows


def hs_recent_change(since: int = 2013) -> list[tuple]:
    """Per-state % change in public HS graduates from `since` to the latest year. Negative =
    the demographic pool is already shrinking there, a leading indicator of closure pressure."""
    conn = connect()
    latest = conn.execute("SELECT max(year) FROM hs_graduates WHERE measure = 'public'").fetchone()[
        0
    ]
    rows = conn.execute(
        "SELECT a.jurisdiction, b.graduates AS old, a.graduates AS new "
        "FROM hs_graduates a JOIN hs_graduates b "
        "  ON a.jurisdiction = b.jurisdiction AND a.measure = b.measure "
        "WHERE a.jurisdiction_type = 'state' AND a.measure = 'public' "
        "  AND a.year = ? AND b.year = ?",
        (latest, since),
    ).fetchall()
    conn.close()
    out = [(j, round(100 * (new - old) / old, 1)) for j, old, new in rows if old]
    return sorted(out, key=lambda t: t[1])


def get_institution(inst_id: str) -> dict | None:
    conn = connect()
    inst = conn.execute("SELECT * FROM institution WHERE id = ?", (inst_id,)).fetchone()
    if inst is None:
        conn.close()
        return None
    events = conn.execute(
        "SELECT * FROM event WHERE institution_id = ? ORDER BY (event_year IS NULL), event_year",
        (inst_id,),
    ).fetchall()
    names = conn.execute(
        "SELECT * FROM institution_name WHERE institution_id = ? ORDER BY start_year", (inst_id,)
    ).fetchall()
    tags = [
        r[0]
        for r in conn.execute(
            "SELECT tag FROM characteristic WHERE institution_id = ? ORDER BY tag", (inst_id,)
        )
    ]
    enrollment = conn.execute(
        "SELECT * FROM enrollment WHERE institution_id = ? ORDER BY year", (inst_id,)
    ).fetchall()
    hcm = conn.execute(
        "SELECT * FROM hcm WHERE institution_id = ? ORDER BY as_of_date", (inst_id,)
    ).fetchall()
    campuses = conn.execute(
        "SELECT * FROM campus WHERE institution_id = ? ORDER BY (closed_year IS NULL), closed_year, name",
        (inst_id,),
    ).fetchall()
    # Sibling campuses: other closures sharing this one's surviving parent institution.
    siblings = []
    if inst["parent_name"]:
        siblings = conn.execute(
            "SELECT id, name, city, state, status_year FROM institution "
            "WHERE parent_name = ? AND id <> ? ORDER BY status_year, name",
            (inst["parent_name"], inst_id),
        ).fetchall()
    conn.close()
    return {
        "inst": inst,
        "events": events,
        "names": names,
        "tags": tags,
        "enrollment": enrollment,
        "hcm": hcm,
        "siblings": siblings,
        "campuses": campuses,
    }


def composite_series(inst_id: str) -> dict | None:
    """This institution's Financial Responsibility Composite Score history, as published by
    ED. Returns the raw published scores and nothing derived: the pass/zone/fail reading is
    ED's interpretation of the number and is applied in the template layer via COMPOSITE_BANDS,
    so a threshold can be corrected without touching stored data."""
    conn = connect()
    rows = conn.execute(
        "SELECT award_year, year, score, fy_end, institution_type, as_of, source_url "
        "FROM composite_score WHERE institution_id = ? AND score IS NOT NULL "
        "ORDER BY year",
        (inst_id,),
    ).fetchall()
    conn.close()
    if not rows:
        return None
    last = rows[-1]
    return {
        "points": [(r["year"], r["score"]) for r in rows],
        "rows": [dict(r) for r in rows],
        "latest": last["score"],
        "latest_award_year": last["award_year"],
        "as_of": last["as_of"],
        "source_url": last["source_url"],
        "span": (rows[0]["award_year"], last["award_year"]),
        "count": len(rows),
    }


def composite_years() -> dict[str, int]:
    """award_year -> how many scores we hold for it. Drives the admin console's loaded/not
    state, so the console reports what is actually in the database rather than what it tried
    to load."""
    conn = connect()
    rows = conn.execute(
        "SELECT award_year, count(*) n FROM composite_score GROUP BY award_year"
    ).fetchall()
    conn.close()
    return {r["award_year"]: r["n"] for r in rows}


def sector_series() -> dict:
    """How many institutions were actually operating, per year, per control (IPEDS HD). This is
    the denominator: the closure record alone can say how many schools closed, never what share
    of the sector that was.

    Control is kept broken out because the aggregate is misleading on its own. Most of the
    decline since the 2012 peak is for-profit; a single total line would tell a tuition-dependent
    private nonprofit that its own sector collapsed by a fifth, which is not what IPEDS says."""
    conn = connect()
    rows = conn.execute("SELECT year, control, active FROM sector_size ORDER BY year").fetchall()
    conn.close()
    if not rows:
        return {}
    by_control: dict[str, list[tuple]] = {}
    totals: dict[int, int] = {}
    for r in rows:
        by_control.setdefault(r["control"], []).append((r["year"], r["active"]))
        totals[r["year"]] = totals.get(r["year"], 0) + r["active"]
    years = sorted(totals)
    peak_year = max(years, key=lambda y: totals[y])
    return {
        "by_control": by_control,
        "total": sorted(totals.items()),
        "peak_year": peak_year,
        "peak": totals[peak_year],
        "latest_year": years[-1],
        "latest": totals[years[-1]],
        "first_year": years[0],
    }


def hcm_summary() -> dict:
    """Headline signal: how many INSTITUTIONAL closures were on Heightened Cash Monitoring
    before they closed. Scoped to institutional closures (a campus closing is not a school
    dying) and to closures from 2015 on, since HCM snapshots start in 2015."""
    conn = connect()
    before = conn.execute(
        "SELECT count(DISTINCT h.institution_id) FROM hcm h JOIN institution i ON i.id = h.institution_id "
        "WHERE i.closure_type = 'institutional' AND i.status_year IS NOT NULL "
        "AND CAST(substr(h.as_of_date, 1, 4) AS INT) <= i.status_year"
    ).fetchone()[0]
    eligible = conn.execute(
        "SELECT count(*) FROM institution WHERE closure_type = 'institutional' AND status_year >= 2015"
    ).fetchone()[0]
    conn.close()
    return {"before_closure": before, "eligible": eligible}
