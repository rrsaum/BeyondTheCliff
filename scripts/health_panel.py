#!/usr/bin/env python3
"""Survivorship-free institutional-health panel and a first descriptive pass.

Builds school-year rows for closures AND survivors from the Scorecard and composite-score
history, normalizes every metric to a within-year percentile (so a school is compared to its
peers THAT year, not to today's), and compares the two groups over each school's window (the
pre-closure years for closures, all years for survivors). This is DESCRIPTIVE exploratory
analysis, not a validated predictor: the preregistered, out-of-sample, combination test
described in docs/strategy/INSTITUTIONAL_HEALTH_METRICS.md is the next step. Read-only; no writes.

    .venv/bin/python scripts/health_panel.py
"""

import bisect
import sqlite3
import statistics as st
from collections import defaultdict
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "beyondthecliff.db"


def _pct(vals_by_year):
    tbl = {y: sorted(v) for y, v in vals_by_year.items()}
    return lambda y, v: (
        bisect.bisect_left(tbl[y], v) / max(len(tbl[y]) - 1, 1)
        if (v is not None and tbl.get(y))
        else None
    )


def _slope(pairs):
    p = [(y, v) for y, v in pairs if v is not None]
    if len(p) < 3:
        return None
    mx = sum(y for y, _ in p) / len(p)
    my = sum(v for _, v in p) / len(p)
    d = sum((y - mx) ** 2 for y, _ in p)
    return None if d == 0 else sum((y - mx) * (v - my) for y, v in p) / d


def _med(xs):
    xs = [v for v in xs if v is not None]
    return st.median(xs) if xs else None


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    inst = {
        r["id"]: dict(cyr=r["status_year"], closed=(r["status"] != "open"))
        for r in con.execute("SELECT id,status,status_year FROM institution")
    }
    sc = defaultdict(dict)
    for r in con.execute(
        "SELECT institution_id,year,ugds,adm_rate,tuitfte,pct_pell FROM scorecard WHERE year IS NOT NULL"
    ):
        sc[r["institution_id"]][r["year"]] = r
    comp = defaultdict(dict)
    for r in con.execute(
        "SELECT institution_id,year,score FROM composite_score WHERE score IS NOT NULL"
    ):
        comp[r["institution_id"]][r["year"]] = r["score"]

    def collect(field):
        d = defaultdict(list)
        for ys in sc.values():
            for y, r in ys.items():
                if r[field] is not None:
                    d[y].append(r[field])
        return _pct(d)

    pf = {m: collect(m) for m in ("ugds", "tuitfte", "adm_rate", "pct_pell")}
    cby = defaultdict(list)
    for ys in comp.values():
        for y, s in ys.items():
            cby[y].append(s)
    pc = _pct(cby)

    rows = []
    for i, ys in sc.items():
        o = inst.get(i)
        if not o:
            continue
        win = [y for y in sorted(ys) if (not o["closed"] or not o["cyr"] or y < o["cyr"])]
        if len(win) < 3:
            continue
        rows.append(
            dict(
                closed=o["closed"],
                comp_pctile=_med([pc(y, comp[i][y]) for y in win if y in comp.get(i, {})]),
                comp_last=next((comp[i][y] for y in reversed(win) if y in comp.get(i, {})), None),
                ugds_pctile=_med([pf["ugds"](y, ys[y]["ugds"]) for y in win]),
                tuit_pctile=_med([pf["tuitfte"](y, ys[y]["tuitfte"]) for y in win]),
                adm_pctile=_med([pf["adm_rate"](y, ys[y]["adm_rate"]) for y in win]),
                pell_pctile=_med([pf["pct_pell"](y, ys[y]["pct_pell"]) for y in win]),
                ugds_slope5=_slope([(y, ys[y]["ugds"]) for y in win[-5:]]),
            )
        )
    closed = [r for r in rows if r["closed"]]
    surv = [r for r in rows if not r["closed"]]
    print(f"PANEL (>=3 usable years): {len(closed)} closed, {len(surv)} survivors\n")
    print(f"{'metric':32}{'closed':>9}{'survivor':>10}{'sep':>9}{'nC':>7}{'nS':>7}")
    labels = [
        ("comp_pctile", "composite %ile (peers)"),
        ("comp_last", "composite score (raw, last)"),
        ("ugds_pctile", "enrollment %ile"),
        ("ugds_slope5", "enrollment slope/yr (last 5)"),
        ("tuit_pctile", "net tuition/student %ile"),
        ("adm_pctile", "admit %ile (high=less selective)"),
        ("pell_pctile", "Pell %ile"),
    ]
    for k, lab in labels:
        c = [r[k] for r in closed if r[k] is not None]
        s = [r[k] for r in surv if r[k] is not None]
        mc, ms = (st.median(c) if c else None), (st.median(s) if s else None)
        sep = f"{mc - ms:+.3f}" if (mc is not None and ms is not None) else "    -"

        def fm(x):
            return "    -" if x is None else f"{x:8.3f}"

        print(f"{lab:32}{fm(mc):>9}{fm(ms):>10}{sep:>9}{len(c):>7}{len(s):>7}")


if __name__ == "__main__":
    main()
