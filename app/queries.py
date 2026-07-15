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
STATUS_LABELS = {"closed": "Closed", "merged": "Merged/consolidated",
                 "announced": "Announced (upcoming)", "at_risk": "At-risk (open)"}
CLOSURE_TYPE_LABELS = {"institutional": "Institutional closure", "campus": "Campus closure",
                       "program": "Program closure"}
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
        where.append("EXISTS (SELECT 1 FROM event e WHERE e.institution_id = i.id AND e.abrupt = 1)")
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
    states = [r[0] for r in conn.execute(
        "SELECT DISTINCT state FROM institution WHERE state <> '' ORDER BY state"
    )]
    conn.close()
    return {"states": states, "controls": CONTROL_LABELS, "statuses": STATUS_LABELS,
            "closure_types": CLOSURE_TYPE_LABELS, "causes": CAUSE_LABELS}


def by_cause(args: dict) -> list[tuple]:
    rows = _group_count(args, "i.cause", by_label=False, limit=None)
    return [(CAUSE_LABELS.get(k, k), c) for k, c in rows]


def total_count() -> int:
    conn = connect()
    n = conn.execute("SELECT count(*) FROM institution").fetchone()[0]
    conn.close()
    return n


def closure_summary() -> dict:
    """Counts of COMPLETED closures by type (institutional = the institution closed; campus =
    a branch closed while the parent survives; program = a program ended while the school
    stays open), plus merged and the count of announced-but-not-yet-closed schools. The
    distinctions are load-bearing: a campus or program closure is not a school dying, and an
    announced closure has not happened yet."""
    conn = connect()
    rows = dict(conn.execute(
        "SELECT closure_type, count(*) FROM institution "
        "WHERE status = 'closed' AND closure_type IS NOT NULL GROUP BY closure_type"
    ).fetchall())
    merged = conn.execute("SELECT count(*) FROM institution WHERE status = 'merged'").fetchone()[0]
    announced = conn.execute(
        "SELECT count(*) FROM institution WHERE status = 'announced'").fetchone()[0]
    at_risk = conn.execute(
        "SELECT count(*) FROM institution WHERE status = 'at_risk'").fetchone()[0]
    conn.close()
    return {"institutional": rows.get("institutional", 0), "campus": rows.get("campus", 0),
            "program": rows.get("program", 0), "merged": merged, "announced": announced,
            "at_risk": at_risk}


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
        for k in ("ugds", "adm_rate", "pct_pell", "tuitfte", "tuitionfee_in", "costt4_a",
                  "pptug_ef", "ugds_white", "ugds_black", "ugds_hisp", "first_gen"):
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
        ("Undergraduates", f"{int(val('ugds')):,}" if val("ugds") is not None else None, latest.get("ugds", (None, None))[1]),
        ("Admission rate", pct(val("adm_rate")), latest.get("adm_rate", (None, None))[1]),
        ("On Pell grants", pct(val("pct_pell")), latest.get("pct_pell", (None, None))[1]),
        ("Net tuition / student", dollars(val("tuitfte")), latest.get("tuitfte", (None, None))[1]),
        ("In-state tuition + fees", dollars(val("tuitionfee_in")), latest.get("tuitionfee_in", (None, None))[1]),
        ("Avg cost of attendance", dollars(val("costt4_a")), latest.get("costt4_a", (None, None))[1]),
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
    return {"metrics": metrics, "demographics": demo, "flags": flags,
            "year_range": f"{min(years)} to {max(years)}"}


def hs_series(jurisdiction: str, measure: str = "total") -> list[tuple]:
    conn = connect()
    rows = conn.execute(
        "SELECT year, graduates FROM hs_graduates WHERE jurisdiction = ? AND measure = ? "
        "ORDER BY year", (jurisdiction, measure),
    ).fetchall()
    conn.close()
    return [(r[0], r[1]) for r in rows]


def hs_states() -> list[str]:
    conn = connect()
    rows = [r[0] for r in conn.execute(
        "SELECT DISTINCT jurisdiction FROM hs_graduates WHERE jurisdiction_type = 'state' "
        "ORDER BY jurisdiction"
    )]
    conn.close()
    return rows


def hs_recent_change(since: int = 2013) -> list[tuple]:
    """Per-state % change in public HS graduates from `since` to the latest year. Negative =
    the demographic pool is already shrinking there, a leading indicator of closure pressure."""
    conn = connect()
    latest = conn.execute("SELECT max(year) FROM hs_graduates WHERE measure = 'public'").fetchone()[0]
    rows = conn.execute(
        "SELECT a.jurisdiction, b.graduates AS old, a.graduates AS new "
        "FROM hs_graduates a JOIN hs_graduates b "
        "  ON a.jurisdiction = b.jurisdiction AND a.measure = b.measure "
        "WHERE a.jurisdiction_type = 'state' AND a.measure = 'public' "
        "  AND a.year = ? AND b.year = ?", (latest, since),
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
    tags = [r[0] for r in conn.execute(
        "SELECT tag FROM characteristic WHERE institution_id = ? ORDER BY tag", (inst_id,)
    )]
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
    return {"inst": inst, "events": events, "names": names, "tags": tags,
            "enrollment": enrollment, "hcm": hcm, "siblings": siblings, "campuses": campuses}


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
