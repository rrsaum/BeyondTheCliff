"""All SQL for the tracker. Filters are parameterized; sort columns are whitelisted, so a
query string can never inject SQL. Every list/chart query shares the same _filters() clause,
so the charts always reflect the same subset the table shows.
"""

from __future__ import annotations

import bisect

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
        "undergrads": int(val("ugds")) if val("ugds") is not None else None,
        "undergrads_year": latest.get("ugds", (None, None))[1],
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

    # Some universities report tuition, fees, and auxiliaries as one program-service line (e.g.
    # Embry-Riddle's "HIGHER EDUCATION"), so no line item matches the tuition bucket. When a school
    # never itemizes, the earned-from-students band falls back to the aggregate program service
    # revenue and is labelled generically. That keeps the stack reconciling to total revenue
    # instead of dropping the money, and never asserts a tuition figure the filing did not state.
    itemizes = any(buckets.get(r["tax_year"], {}).get("tuition") is not None for r in rows)
    earned_label = "Tuition and fees" if itemizes else "Tuition and program revenue"

    series = []
    for r in rows:
        line = buckets.get(r["tax_year"], {})
        tuition = line.get("tuition")
        earned_band = tuition if tuition is not None else r["program_svc_revenue"]
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
                # The earned-from-students band: itemized tuition where the filing splits it out,
                # otherwise the aggregate program service revenue (see earned_label above).
                "earned_band": earned_band,
                "grants_paid": r["grants_paid"],
                # The four bands of the revenue chart. They sum to total_revenue exactly, which
                # is the only reason a stacked chart is allowed to exist: a stack whose parts do
                # not reconcile is a picture of a number nobody reported.
                #
                # private_giving is contributions MINUS government grants, not the filing's
                # "all other contributions" line. That line omits federated campaigns,
                # membership dues and fundraising events, and using it left up to $539k a year
                # unexplained inside the stack. This definition is exact by construction: it is
                # every dollar given that did not come from a government.
                "private_giving": (
                    None
                    if None in (r["contributions"], r["government_grants"])
                    else r["contributions"] - r["government_grants"]
                ),
                # Everything earned that is not tuition: auxiliaries, room, investment income,
                # other. Folded into one band because "other earned" alone is about 3% of
                # revenue, and a band that thin fails the palette's lightness and contrast
                # checks: nobody can see it or name it, so it is not more honest split out.
                # Also absorbs investment income when it goes negative, which it does in a bad
                # market year, and which would otherwise invert a band.
                "aux_and_other": (
                    None
                    if None in (r["total_revenue"], r["contributions"]) or earned_band is None
                    else r["total_revenue"] - r["contributions"] - earned_band
                ),
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
                # Institutional aid against tuition: the tuition discount rate.
                #
                # This was deliberately unlabelled, because the 990 never states whether its
                # tuition line is gross or net of aid. Settled against Montreat's audited FY2025
                # statement, which reports tuition "net of discounts and scholarships of
                # $14,332,372" as $12,416,923. Gross is therefore $26,749,295 and the 990's
                # TUITION AND FEES is $26,285,908: the 990 line is gross, within $463k, and
                # nowhere near the $12.4M net figure. The rates agree too, 53.2% here against
                # 53.6% audited.
                #
                # Verified on one school in one year, so this is not yet a claim about every
                # filer. A school reporting tuition net would make this ratio meaningless rather
                # than merely wrong, and nothing in the filing would say so.
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
        "earned_label": earned_label,
        "itemizes_tuition": itemizes,
    }


def ipeds_finance_series(inst_id: str) -> dict | None:
    """A public institution's IPEDS Finance record (finance_year): the GASB counterpart to the
    Form 990. Public universities do not file a 990, so this is their revenue-by-source history.

    Bands: tuition, state and local appropriations, federal, private gifts, and 'other', where
    'other' is the residual to total revenue. finance_year stores only the named categories, so
    the residual is not itemized: it varies by institution (auxiliaries, a hospital or health
    system, sales and services, IP and patent licensing, publishing, investment return) and is
    labelled as a residual, never a specific source. Investment return sits inside it and can run
    negative for an endowment-rich school; itemizing these is a later import expansion.
    """
    conn = connect()
    rows = conn.execute(
        "SELECT fiscal_year, total_revenue, tuition_revenue, state_local_revenue, "
        "federal_revenue, private_gifts_grants, total_expenses, source, source_url "
        "FROM finance_year WHERE institution_id = ? AND total_revenue IS NOT NULL "
        "ORDER BY fiscal_year",
        (inst_id,),
    ).fetchall()
    conn.close()
    if len(rows) < 2:
        return None
    series = []
    audited_years = []  # years supplied from the school's own audited statements, not IPEDS
    for r in rows:
        tui = r["tuition_revenue"] or 0
        st = r["state_local_revenue"] or 0
        fed = r["federal_revenue"] or 0
        priv = r["private_gifts_grants"] or 0
        tot = r["total_revenue"] or 0
        if "audited" in (r["source"] or "").lower():
            audited_years.append(r["fiscal_year"])
        series.append(
            {
                "fiscal_year": r["fiscal_year"],
                "tuition": tui,
                "state_local": st,
                "federal": fed,
                "private": priv,
                "other": tot - tui - st - fed - priv,
                "total_revenue": tot,
                "total_expenses": r["total_expenses"],
            }
        )
    first, last = series[0], series[-1]
    fyears = [r["fiscal_year"] for r in series]
    gaps = [y for y in range(fyears[0], fyears[-1] + 1) if y not in fyears]
    return {
        "series": series,
        "first": first,
        "latest": last,
        "gap_years": gaps,
        "audited_years": audited_years,
        "leaderboard": {
            "tuition": last["tuition"],
            "tuition_growth": None
            if not first["tuition"]
            else last["tuition"] / first["tuition"] - 1,
            "state_local": last["state_local"],
            "state_growth": (
                None if not first["state_local"] else last["state_local"] / first["state_local"] - 1
            ),
            "tuition_per_state": _ratio(last["tuition"], last["state_local"]),
            "tuition_per_state_first": _ratio(first["tuition"], first["state_local"]),
        },
        "source": rows[0]["source"],
        "source_url": rows[0]["source_url"],
        "year_range": f"FY{first['fiscal_year']} to FY{last['fiscal_year']}",
    }


def national_series(series: str) -> list[tuple]:
    """The long-run national line for 'institutions' or 'enrollment', 1869 to latest (NCES)."""
    conn = connect()
    rows = conn.execute(
        "SELECT year, value FROM national_series WHERE series = ? ORDER BY year", (series,)
    ).fetchall()
    conn.close()
    return [(r[0], r[1]) for r in rows]


def national_closures_by_control() -> list[dict]:
    """Institutional closures per year, split by control, from our own records. Same filter the
    closure map uses (status='closed', closure_type='institutional'), so a year here matches the
    map. Rows whose control we could not source fall to 'unknown' rather than being guessed into a
    sector. Returns {year, private_nonprofit, private_forprofit, public, unknown, total}."""
    conn = connect()
    rows = conn.execute(
        "SELECT status_year AS y, "
        "SUM(CASE WHEN control = 'private_nonprofit' THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN control = 'private_forprofit' THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN control = 'public' THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN control IS NULL OR control NOT IN "
        "('private_nonprofit', 'private_forprofit', 'public') THEN 1 ELSE 0 END) "
        "FROM institution "
        "WHERE status = 'closed' AND closure_type = 'institutional' AND status_year IS NOT NULL "
        "GROUP BY status_year ORDER BY status_year"
    ).fetchall()
    conn.close()
    return [
        {
            "year": r[0],
            "private_nonprofit": r[1],
            "private_forprofit": r[2],
            "public": r[3],
            "unknown": r[4],
            "total": r[1] + r[2] + r[3] + r[4],
        }
        for r in rows
    ]


def timeline_markers(series: str) -> list[dict]:
    """Key dates under a national chart: (year, label, detail) likely causes of an inflection."""
    conn = connect()
    rows = conn.execute(
        "SELECT year, label, detail, source_url FROM timeline_marker WHERE series = ? ORDER BY year",
        (series,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def national_turns(series: str) -> list[dict]:
    """The 'what drove the turns' rows for a national chart, in CSV (rowid) order: each is an era
    with what the data shows, the sourced likely cause, a category, and whether the cause is our
    inference. Analysis, so the copy and the is_inference flag both say so."""
    conn = connect()
    rows = conn.execute(
        "SELECT era, shows, cause, category, is_inference, source_url "
        "FROM national_turn WHERE series = ? ORDER BY rowid",
        (series,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def national_growth(series: str, eras: list[tuple[int, int, str]]) -> list[dict]:
    """Compound annual growth rate for named spans of a national series, computed live from the
    stored values so a quoted rate can never drift from the data. eras: (start_year, end_year,
    label). Returns {label, start, end, v0, v1, cagr} for each span both endpoints exist for."""
    pts = dict(national_series(series))
    out = []
    for y0, y1, label in eras:
        if y0 in pts and y1 in pts and pts[y0] > 0 and y1 > y0:
            cagr = ((pts[y1] / pts[y0]) ** (1 / (y1 - y0)) - 1) * 100
            out.append(
                {"label": label, "start": y0, "end": y1, "v0": pts[y0], "v1": pts[y1], "cagr": cagr}
            )
    return out


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
    # Overlay the hand-curated descriptive facts (founding year, affiliation, sourced bio). The
    # institution row's own founding_year/religious_affiliation win when present (closures carry
    # them); the curated CSV fills them for survivors the generated roster left blank.
    inst = dict(inst)
    prof = conn.execute(
        "SELECT founded, affiliation, bio, source_url FROM institution_profile "
        "WHERE institution_id = ?",
        (inst_id,),
    ).fetchone()
    if prof:
        inst["founding_year"] = inst.get("founding_year") or prof["founded"]
        inst["religious_affiliation"] = inst.get("religious_affiliation") or prof["affiliation"]
        inst["bio"] = prof["bio"]
        inst["profile_source"] = prof["source_url"]
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
    closure_metrics = {
        r["metric"]: r
        for r in conn.execute("SELECT * FROM closure_metric WHERE institution_id = ?", (inst_id,))
    }
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
        "closure_metrics": closure_metrics,
    }


def _usd(v) -> str:
    """A closure figure as a compact dollar string: $37k, $2.3M, $0. Sign is added by the caller."""
    if v is None:
        return ""
    a = abs(v)
    if a >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if a >= 1_000:
        return f"${v / 1_000:.0f}k"
    return f"${v:,.0f}"


def closure_anatomy(m: dict) -> dict | None:
    """The three-question closure diagnostic, built from raw closure_metric rows.

    Every reading is COMPUTED, never stored, so a definition can change without re-entering data.
    The sign-and-colour convention is deliberate and financial: money the school OWED or LOST is a
    negative shown in red (payroll owed, debt, the projected loss); money it HAD or the rescue
    target is positive and neutral (cash, the amount needed, what was raised). Per-layer bar widths
    are relative to that layer's own largest figure, because $37k and $2.3M on one axis makes the
    small bar vanish. Returns None when a school has no autopsy figures, so the panel just does not
    render."""
    if not m:
        return None

    def amt(k):
        r = m.get(k)
        return r["amount"] if r and r["amount"] is not None else None

    def bar(label, key, top, *, negative=False):
        v = amt(key)
        if v is None:
            return None
        return {
            "label": label,
            "display": ("-" if negative and v else "") + _usd(v),
            "pct": round(100 * abs(v) / top, 1) if top else 0.0,
            "tone": "crit" if negative else "base",
            "amt_crit": bool(negative and v) or v == 0,
        }

    layers = []
    cash, payroll = amt("cash_on_hand"), amt("near_term_obligations")
    if cash is not None and payroll is not None:
        top = max(abs(cash), abs(payroll)) or 1
        ratio = cash / payroll if payroll else None
        layers.append(
            {
                "title": "Liquidity",
                "question": "Could it make payroll?",
                "bars": [
                    bar("Cash in bank", "cash_on_hand", top),
                    bar("Payroll owed", "near_term_obligations", top, negative=True),
                ],
                "verdict": f"{ratio:.1f} payrolls of cash on hand." if ratio is not None else "",
            }
        )

    debt, loss = amt("debt_prior_year"), amt("projected_deficit")
    endow = m.get("endowment")
    endow_amt = endow["amount"] if endow and endow["amount"] is not None else None
    depleted = bool(endow is not None and endow["qualitative"])
    if debt is not None or loss is not None or endow is not None:
        top = max([abs(x) for x in (debt, loss, endow_amt) if x is not None] or [1])
        bars = []
        if debt is not None:
            bars.append(bar("Debt carried", "debt_prior_year", top, negative=True))
        if loss is not None:
            dy = m["projected_deficit"]["as_of_year"]
            loss_label = f"{dy}-{str(dy + 1)[-2:]} loss" if dy else "Projected loss"
            bars.append(bar(loss_label, "projected_deficit", top, negative=True))
        if endow is not None and depleted:
            bars.append(
                {
                    "label": "Endowment",
                    "display": f"{endow['qualitative']} (no reserve reported)",
                    "pct": 0.0,
                    "tone": "na",
                    "amt_crit": True,
                }
            )
        elif endow_amt is not None:
            # The reserve it still held: a neutral resource shown alongside what it owed.
            bars.append(
                {
                    "label": "Endowment",
                    "display": _usd(endow_amt),
                    "pct": round(100 * abs(endow_amt) / top, 1) if top else 0.0,
                    "tone": "base",
                    "amt_crit": False,
                }
            )
        if depleted and (debt is not None or loss is not None):
            verdict = "Debt and coming shortfall, no reserve behind it."
        elif debt is not None or loss is not None:
            verdict = "More owed than it could cover."
        else:
            verdict = ""  # endowment only: show the reserve, make no unsourced claim
        layers.append(
            {
                "title": "Solvency",
                "question": "Did it owe more than it held?",
                "bars": bars,
                "verdict": verdict,
            }
        )

    needed, raised = amt("rescue_needed"), amt("rescue_raised")
    if needed is not None:
        top = needed or 1
        bars = [bar("Needed to survive", "rescue_needed", top)]
        if raised is not None:
            b = bar("Raised or lent", "rescue_raised", top)
            b["pct"] = max(b["pct"], 1.0)
            bars.append(b)
        layers.append(
            {
                "title": "Rescue gap",
                "question": "Could it be saved?",
                "bars": bars,
                "verdict": "No donors, no loans came." if raised == 0 else "The rescue fell short.",
            }
        )

    for i, layer in enumerate(layers, 1):  # renumber to what actually rendered (1..k)
        layer["n"] = i

    toll_labels = {
        "employees": "employees on the payroll",
        "students_displaced": "students displaced",
        "closure_warning_days": "days from announcement to close",
    }
    toll = []
    for k, lab in toll_labels.items():
        v = amt(k)
        if v is not None:
            value = f"{v:,} days" if m[k]["unit"] == "days" else f"{v:,}"
            toll.append({"value": value, "label": lab})

    return {"layers": layers, "toll": toll} if layers else None


_FOURYR = ("Bachelor's", "Master's", "Doctor's")


def _peer_label(control: str | None, fouryr: bool) -> str:
    """A plain description of the comparison group, e.g. '4-year private nonprofits'."""
    base = {
        "public": "public",
        "private_nonprofit": "private nonprofit",
        "private_forprofit": "for-profit",
    }.get(control, "college")
    return f"{'4-year' if fouryr else '2-year'} {base}s"


def _peer_percentile(
    conn, field: str, value, year: int, control: str, fouryr: bool
) -> float | None:
    """This school's percentile on `field` among COMPARABLE peers (same control and level) in `year`.

    Comparable peers, not all institutions: 762 undergraduates is median-sized among 4-year private
    nonprofits, but 'top 46%' against a universe stuffed with tiny certificate programs. field is
    whitelisted below, so it is never user input in the SQL."""
    if value is None or field not in ("ugds", "tuitfte", "pct_pell"):
        return None
    level = (
        "i.degrees IN ('Bachelor''s','Master''s','Doctor''s')"
        if fouryr
        else "(i.degrees NOT IN ('Bachelor''s','Master''s','Doctor''s') OR i.degrees IS NULL)"
    )
    rows = sorted(
        r[0]
        for r in conn.execute(
            f"SELECT s.{field} FROM scorecard s JOIN institution i ON i.id = s.institution_id "
            f"WHERE s.year = ? AND s.{field} IS NOT NULL AND i.control = ? AND {level}",
            (year, control),
        )
    )
    return bisect.bisect_left(rows, value) / len(rows) if rows else None


def resilience_profile(inst_id: str) -> dict | None:
    """This institution's Resilience score, shaped for the redesigned school-page panel.

    The band and overall percentile come from the FROZEN model (all-institution). The per-driver
    bars show the school's percentile among COMPARABLE peers (same control and level), because that
    is the comparison a reader can act on. Net tuition is shown neutrally: against all colleges it
    looks high, but for a private nonprofit it is often below the peer middle, so it is not colored
    as a fault. Pell is always context. The one clear concern (a falling enrollment line) is flagged.
    """
    conn = connect()
    row = conn.execute(
        "SELECT rs.*, i.control, i.status, i.degrees FROM resilience_score rs "
        "JOIN institution i ON i.id = rs.institution_id WHERE rs.institution_id = ?",
        (inst_id,),
    ).fetchone()
    n_open = conn.execute(
        "SELECT COUNT(*) FROM resilience_score rs JOIN institution i ON i.id = rs.institution_id "
        "WHERE i.status = 'open'"
    ).fetchone()[0]
    if row is None:
        conn.close()
        return None
    control = row["control"]
    fouryr = (row["degrees"] or "") in _FOURYR
    peers = _peer_label(control, fouryr)
    sc = conn.execute(
        "SELECT year, ugds, tuitfte, pct_pell FROM scorecard "
        "WHERE institution_id = ? AND ugds IS NOT NULL ORDER BY year DESC LIMIT 1",
        (inst_id,),
    ).fetchone()
    # Enrollment direction from the last five reported years (a fact: is the line falling?).
    ug = [
        r["ugds"]
        for r in conn.execute(
            "SELECT ugds FROM scorecard WHERE institution_id = ? AND ugds IS NOT NULL "
            "ORDER BY year DESC LIMIT 5",
            (inst_id,),
        )
    ]
    falling = len(ug) >= 2 and ug[0] < ug[-1]
    growing = len(ug) >= 2 and ug[0] > ug[-1]

    def pp(field):
        return (
            _peer_percentile(conn, field, sc[field] if sc else None, sc["year"], control, fouryr)
            if sc
            else None
        )

    def band_note(p, low, mid, high):
        if p is None:
            return mid
        return low if p < 0.4 else (high if p > 0.6 else mid)

    drivers = []
    # Enrollment trend: the one lever with an unambiguous direction, so it can be flagged.
    p_trend = row["p_trend"]
    drivers.append(
        {
            "feat": "trend",
            "label": "Enrollment trend",
            "pct": round((p_trend if p_trend is not None else 0.5) * 100),
            "kind": "concern" if falling else ("good" if growing else "neutral"),
            "note": "enrollment is falling"
            if falling
            else ("enrollment is growing" if growing else "enrollment is steady"),
        }
    )
    # Enrollment size, comparable peers.
    p_size = pp("ugds")
    drivers.append(
        {
            "feat": "size",
            "label": "Enrollment size",
            "pct": round((p_size if p_size is not None else row["p_size"] or 0.5) * 100),
            "kind": "concern" if (p_size is not None and p_size <= 0.25) else "neutral",
            "note": band_note(
                p_size, f"small for {peers}", f"about average for {peers}", f"large for {peers}"
            ),
        }
    )
    # Net tuition, comparable peers, shown NEUTRALLY (direction is genuinely ambiguous for health).
    p_tui = pp("tuitfte")
    drivers.append(
        {
            "feat": "tuition",
            "label": "Net tuition/student",
            "pct": round((p_tui if p_tui is not None else row["p_tuition"] or 0.5) * 100),
            "kind": "neutral",
            "note": band_note(
                p_tui,
                f"below the middle for {peers}",
                f"about typical for {peers}",
                f"above most {peers}",
            ),
        }
    )
    # Pell reliance: context, never a fault.
    p_pell = pp("pct_pell")
    drivers.append(
        {
            "feat": "pell",
            "label": "Pell share",
            "pct": round((p_pell if p_pell is not None else row["p_pell"] or 0.5) * 100),
            "kind": "context",
            "note": band_note(
                p_pell,
                f"low Pell share for {peers}",
                f"typical Pell share for {peers}",
                f"high Pell share for {peers}",
            )
            + " &middot; context, not fault",
        }
    )
    conn.close()
    pctile = row["pctile"]
    n = min(99, max(1, round(pctile * 100)))
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return {
        "band": row["band"],
        "pctile": pctile,
        "marker_pct": round(100 * pctile, 1),
        "pct_ordinal": f"{n}{suffix}",
        "rank_phrase": f"More resilient than {min(99, round(pctile * 100))}% of the {n_open:,} operating colleges we score",
        "is_public": control == "public",
        "closed": row["status"] != "open",
        "n_open": n_open,
        "peers": peers,
        "drivers": drivers,
    }


RESILIENCE_SORTS = {
    "risk": "rs.pctile ASC, i.name ASC",  # least resilient first (the schools to watch)
    "health": "rs.pctile DESC, i.name ASC",
    "name": "i.name ASC",
}
_RESILIENCE_DRAGS = {
    "enrollment trend": "c_trend",
    "net tuition": "c_tuition",
    "small size": "c_size",
}


def resilience_ranking(
    control: str, state: str, sort: str, page: int, per_page: int
) -> tuple[list, int, list]:
    """The living roster ranked by Resilience, for the Sector Resilience page.

    Returns (page rows, total matching, band distribution). Only living institutions carry a
    forward-looking band, so the page is survivors only. The distribution reflects the active
    filter so the bar moves with the control/state selection."""
    where = ["i.status = 'open'"]
    params: list = []
    if control:
        where.append("i.control = ?")
        params.append(control)
    if state:
        where.append("i.state = ?")
        params.append(state)
    clause = " AND ".join(where)
    order = RESILIENCE_SORTS.get(sort, RESILIENCE_SORTS["risk"])
    conn = connect()
    total = conn.execute(
        f"SELECT COUNT(*) FROM resilience_score rs JOIN institution i ON i.id = rs.institution_id "
        f"WHERE {clause}",
        params,
    ).fetchone()[0]
    dist = {
        r["band"]: r["n"]
        for r in conn.execute(
            f"SELECT rs.band, COUNT(*) n FROM resilience_score rs "
            f"JOIN institution i ON i.id = rs.institution_id WHERE {clause} GROUP BY rs.band",
            params,
        )
    }
    rows = conn.execute(
        f"SELECT i.id, i.name, i.control, i.state, rs.band, rs.pctile, "
        f"rs.c_size, rs.c_trend, rs.c_tuition FROM resilience_score rs "
        f"JOIN institution i ON i.id = rs.institution_id WHERE {clause} "
        f"ORDER BY {order} LIMIT ? OFFSET ?",
        [*params, per_page, (page - 1) * per_page],
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        drags = {label: r[col] for label, col in _RESILIENCE_DRAGS.items()}
        chief, val = max(drags.items(), key=lambda kv: kv[1] if kv[1] is not None else -9)
        out.append(
            {
                "id": r["id"],
                "name": r["name"],
                "control": r["control"],
                "state": r["state"],
                "band": r["band"],
                "pctile": round(r["pctile"] * 100),
                "chief_drag": chief if (val is not None and val > 0) else "",
            }
        )
    # Best-first ordered distribution for the stacked bar (only bands that occur).
    dist_ordered = [
        (name, dist[name])
        for name in ("Strained", "Watch", "Stable", "Resilient")
        if dist.get(name)
    ]
    return out, total, dist_ordered


def financial_summary(inst_id: str) -> dict | None:
    """Latest and earliest 990 balance-sheet snapshot, for the above-fold vitals and the
    two-question financial callout: the operating result (income statement) and the reserve
    (balance sheet) are different questions and are surfaced as such."""
    conn = connect()
    rows = conn.execute(
        "SELECT tax_year, period_end, total_revenue, total_expenses, net_income, net_assets "
        "FROM financial_filing WHERE institution_id = ? AND net_assets IS NOT NULL ORDER BY tax_year",
        (inst_id,),
    ).fetchall()
    conn.close()
    if not rows:
        return None
    last, first = rows[-1], rows[0]

    def fy(r):
        return int(r["period_end"][:4]) if r["period_end"] else r["tax_year"] + 1

    exp = last["total_expenses"]
    return {
        "fiscal_year": fy(last),
        "first_fy": fy(first),
        "net_assets": last["net_assets"],
        "first_net_assets": first["net_assets"],
        "net_income": last["net_income"],
        "total_revenue": last["total_revenue"],
        "total_expenses": exp,
        "reserve_ratio": (last["net_assets"] / exp) if exp else None,
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


def sector_series() -> dict[str, list[tuple]]:
    """How many colleges were operating each year, per control (IPEDS HD). control -> [(year,
    count)]. The denominator: a closure record alone says how many schools closed, never what
    share of the sector that was.

    Counted by scripts/import_ipeds_roster.py under the same is_college() rule the closure
    record uses, so each college is counted once and branch campuses and system offices are out.
    Raw counts only: the change-since-first-year the chart draws is arithmetic on top, done at
    the point of display, so the stored number stays the number NCES published."""
    conn = connect()
    rows = conn.execute("SELECT year, control, active FROM sector_size ORDER BY year").fetchall()
    conn.close()
    out: dict[str, list[tuple]] = {}
    for r in rows:
        out.setdefault(r["control"], []).append((r["year"], r["active"]))
    return out


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
