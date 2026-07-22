#!/usr/bin/env python3
"""Discrete-time hazard model (hardening step 2): probability of closing within H years.

The window-summary models (health_validate, health_era) ask "does this profile look like the ones
that closed." A board asks "given how we look NOW, what is the chance we close in the next few
years." This is that model: one row per institution per Scorecard year, features computed AS OF that
year (point-in-time, so no future information leaks back), label = closes within H years. It also
removes the one honest weakness of steps 1 and 2, whose survivor features summarized a window
reaching into the future.

Design and pass bars are preregistered in docs/strategy/INSTITUTIONAL_HEALTH_METRICS.md and were
committed before this ran. Reuses health_validate's percentile, slope, split, fit, and AUC. Read-only
over the DB. Standard library, deterministic.

    .venv/bin/python scripts/health_survival.py
"""

import statistics as st
from collections import defaultdict

from health_validate import DB, _in_train, _pct_fn, _slope, auc, logit_fit, predict

HORIZONS = [3, 5]
WORKHORSE = ["size", "trend", "pell", "tuition"]


def load(con):
    inst = {
        r["id"]: dict(closed=(r["status"] != "open"), s=r["status_year"])
        for r in con.execute("SELECT id, status, status_year FROM institution")
    }
    sc = defaultdict(dict)
    for r in con.execute(
        "SELECT institution_id, year, ugds, pct_pell, tuitfte FROM scorecard WHERE year IS NOT NULL"
    ):
        sc[r["institution_id"]][r["year"]] = r
    comp = defaultdict(dict)
    for r in con.execute(
        "SELECT institution_id, year, score FROM composite_score "
        "WHERE score IS NOT NULL AND year IS NOT NULL"
    ):
        comp[r["institution_id"]][r["year"]] = r["score"]
    return inst, sc, comp


def pct_fns(sc):
    by = {f: defaultdict(list) for f in ("ugds", "pct_pell", "tuitfte")}
    for ys in sc.values():
        for y, r in ys.items():
            for f in by:
                if r[f] is not None:
                    by[f][y].append(r[f])
    return {f: _pct_fn(by[f]) for f in by}


def features_asof(sc_i, comp_i, t, pf):
    r = sc_i[t]
    pts = [
        (y, sc_i[y]["ugds"])
        for y in range(t - 4, t + 1)
        if y in sc_i and sc_i[y]["ugds"] is not None
    ]
    comp_years = [y for y in comp_i if y <= t]
    return dict(
        size=pf["ugds"](t, r["ugds"]),
        trend=_slope(pts),  # five-year ugds slope ending at t
        pell=pf["pct_pell"](t, r["pct_pell"]),
        tuition=pf["tuitfte"](t, r["tuitfte"]),
        comp=comp_i[max(comp_years)] if comp_years else None,
    )


def build_person_periods(inst, sc, comp, pf, horizon, max_year):
    rows = []
    for i, ys in sc.items():
        o = inst.get(i)
        if not o:
            continue
        for t in sorted(ys):
            if o["closed"]:
                if o["s"] is None or t >= o["s"]:
                    continue  # unknown or post-closure year: not labelable
                event = 1 if (o["s"] - t) <= horizon else 0
            else:
                if t + horizon > max_year:
                    continue  # survivor outcome window not yet observable: right-censored
                event = 0
            rows.append(dict(id=i, t=t, y=event, **features_asof(ys, comp.get(i, {}), t, pf)))
    return rows


def run(rows, feats, name):
    usable = [r for r in rows if all(r[f] is not None for f in feats)]
    tr = [r for r in usable if _in_train(r["id"])]
    ho = [r for r in usable if not _in_train(r["id"])]
    if len(tr) < 50 or len(ho) < 50:
        print(f"{name:32} n too small (train {len(tr)}, holdout {len(ho)})")
        return
    mean = {f: st.mean([r[f] for r in tr]) for f in feats}
    sd = {f: (st.pstdev([r[f] for r in tr]) or 1.0) for f in feats}

    def vec(r):
        return [(r[f] - mean[f]) / sd[f] for f in feats]

    w, b = logit_fit([vec(r) for r in tr], [r["y"] for r in tr])
    scores = [predict(w, b, vec(r)) for r in ho]
    a = auc(scores, [r["y"] for r in ho])
    base = sum(r["y"] for r in ho) / len(ho)
    insts = len({r["id"] for r in ho})
    print(f"{name:32} AUC {a:.3f}  (holdout {len(ho)} periods / {insts} schools, event {base:.0%})")
    print("      weights: " + "  ".join(f"{f}={w[j]:+.2f}" for j, f in enumerate(feats)))


def main():
    import sqlite3

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    inst, sc, comp = load(con)
    pf = pct_fns(sc)
    max_year = max(y for ys in sc.values() for y in ys)
    print(f"max Scorecard year (censoring horizon): {max_year}\n")
    for h in HORIZONS:
        rows = build_person_periods(inst, sc, comp, pf, h, max_year)
        events = sum(r["y"] for r in rows)
        print(f"== HORIZON: closes within {h} years ==")
        print(
            f"   {len(rows)} person-periods, {len({r['id'] for r in rows})} schools, "
            f"{events} events ({events / len(rows):.1%} base rate)"
        )
        run(rows, ["size"], "enrollment level only")
        run(rows, ["size", "trend"], "enrollment level + trend")
        run(rows, ["size", "trend", "pell"], "+ Pell reliance")
        run(rows, WORKHORSE, "+ net tuition (workhorse)")
        csub = [r for r in rows if r["comp"] is not None]
        run(csub, ["comp"], "composite ALONE (subset)")
        run(csub, ["comp", *WORKHORSE], "composite + workhorse (subset)")
        print()


if __name__ == "__main__":
    main()
