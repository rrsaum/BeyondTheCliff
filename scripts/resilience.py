#!/usr/bin/env python3
"""Resilience score: the shared scoring library for the institutional-health band.

ONE home for the scoring logic, imported by build_db.py (to populate the resilience_score table
at build time). Its `--fit` mode FITS the model and prints fresh coefficients; health_validate.py
splits and validates it out of sample. The score is the universal, out-of-sample-validated model
documented in docs/strategy/INSTITUTIONAL_HEALTH_METRICS.md: enrollment level, five-year
enrollment trend, Pell reliance, and net tuition per student.

The deployed coefficients are FROZEN below, not refit on every build: the model was validated
once, and a published, cited score has to be stable, so a school's band cannot move because some
other school's data shifted the fit. To refresh the model deliberately (new data or a new method),
run `python3 scripts/resilience.py --fit`, which prints an updated FROZEN block to paste here, and
re-validate with health_validate.py before adopting it. Peer PERCENTILES are still computed live
each build (they are a ranking of whoever is in the roster now); only the model weights are frozen.

Pure standard library. Read-only over the DB except write_scores(), which populates its own table.
"""

from __future__ import annotations

import bisect
import math
import statistics as st
from collections import defaultdict

# The four validated signals. Order matters: it is the order of FROZEN["weights"].
FEATS = ["size", "trend", "pell", "tuition"]
FEAT_LABEL = {
    "size": "enrollment size",
    "trend": "enrollment trend",
    "pell": "Pell reliance",
    "tuition": "net tuition/student",
}
# Pell is a validated risk signal but a MARKER of an under-resourced, vulnerable-student-serving
# school, not a fault of the school. It is shown as neutral context on the reader-facing panel,
# never as a blameworthy driver. Everything else is an actionable trajectory lever.
CONTEXT_FEATS = {"pell"}

# Band cut-points on the peer percentile (health rank among living institutions), best-first.
BANDS = [(0.60, "Resilient"), (0.35, "Stable"), (0.15, "Watch"), (0.0, "Strained")]

# Frozen production model: standardized logistic-regression weights + standardization moments +
# intercept, fit on the full panel by `--fit`. Refresh only that way (see module docstring).
FROZEN = {
    "mean": {"size": 0.456089, "trend": 15.180505, "pell": 0.539800, "tuition": 0.506701},
    "sd": {"size": 0.280249, "trend": 414.185876, "pell": 0.278638, "tuition": 0.263959},
    "weights": {"size": -0.653249, "trend": -1.081853, "pell": 0.949288, "tuition": 0.785136},
    "intercept": -1.553686,
}


def _pct_fn(vals_by_year):
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


def build_features(con):
    """One row per scored institution: the four model features over its window, plus id/status.

    A closure is summarized over its pre-closure years; a survivor over all its years. Features
    are median within-year percentiles (so a school is compared to its peers that year), except
    the enrollment trend, which is the raw five-year slope (standardized in the model).
    """
    inst = {
        r["id"]: dict(closed=(r["status"] != "open"), cyr=r["status_year"])
        for r in con.execute("SELECT id,status,status_year FROM institution")
    }
    sc = defaultdict(dict)
    for r in con.execute(
        "SELECT institution_id,year,ugds,tuitfte,pct_pell FROM scorecard WHERE year IS NOT NULL"
    ):
        sc[r["institution_id"]][r["year"]] = r

    def collect(field):
        d = defaultdict(list)
        for ys in sc.values():
            for r in ys.values():
                if r[field] is not None:
                    d[r["year"]].append(r[field])
        return _pct_fn(d)

    pf = {m: collect(m) for m in ("ugds", "tuitfte", "pct_pell")}
    rows = []
    for i, ys in sc.items():
        o = inst.get(i)
        if not o:
            continue
        win = [y for y in sorted(ys) if (not o["closed"] or not o["cyr"] or y < o["cyr"])]
        if len(win) < 3:
            continue
        feat = dict(
            size=_med([pf["ugds"](y, ys[y]["ugds"]) for y in win]),
            trend=_slope([(y, ys[y]["ugds"]) for y in win[-5:]]),
            tuition=_med([pf["tuitfte"](y, ys[y]["tuitfte"]) for y in win]),
            pell=_med([pf["pct_pell"](y, ys[y]["pct_pell"]) for y in win]),
        )
        if any(feat[f] is None for f in FEATS):
            continue
        rows.append(dict(id=i, closed=o["closed"], **feat))
    return rows


def logit_fit(X, y, l2=1.0, lr=0.1, iters=4000):
    """Plain L2-regularized logistic regression by gradient descent. Standard library only."""
    n, d = len(X), len(X[0])
    w = [0.0] * d
    b = 0.0
    for _ in range(iters):
        gw = [0.0] * d
        gb = 0.0
        for xi, yi in zip(X, y):
            z = b + sum(w[j] * xi[j] for j in range(d))
            p = 1.0 / (1.0 + math.exp(-max(-30, min(30, z))))
            e = p - yi
            for j in range(d):
                gw[j] += e * xi[j]
            gb += e
        for j in range(d):
            w[j] -= lr * (gw[j] / n + l2 * w[j] / n)
        b -= lr * gb / n
    return w, b


def fit_model(rows):
    """Fit the model on a set of feature rows; return a FROZEN-shaped dict."""
    mean = {f: st.mean([r[f] for r in rows]) for f in FEATS}
    sd = {f: (st.pstdev([r[f] for r in rows]) or 1.0) for f in FEATS}
    X = [[(r[f] - mean[f]) / sd[f] for f in FEATS] for r in rows]
    w, b = logit_fit(X, [1 if r["closed"] else 0 for r in rows])
    return {
        "mean": mean,
        "sd": sd,
        "weights": {f: w[j] for j, f in enumerate(FEATS)},
        "intercept": b,
    }


def _band(pctile):
    for cut, name in BANDS:
        if pctile >= cut:
            return name
    return BANDS[-1][1]


def score_all(con, model=None):
    """Apply the model to every institution and return display-ready score dicts.

    Each row carries the band, the peer percentile (health rank among LIVING institutions), and,
    per feature, its display percentile and signed contribution (positive pushes toward risk).
    """
    model = model or FROZEN
    rows = build_features(con)
    w, b = model["weights"], model["intercept"]
    mean, sd = model["mean"], model["sd"]
    # Live percentile of the raw trend slope, for a readable "enrollment trend: 8th percentile".
    live_trend = sorted(r["trend"] for r in rows if not r["closed"])
    for r in rows:
        contrib = {f: w[f] * (r[f] - mean[f]) / sd[f] for f in FEATS}
        z = b + sum(contrib.values())
        r["risk"] = 1.0 / (1.0 + math.exp(-max(-30, min(30, z))))
        r["health"] = 1.0 - r["risk"]
        r["contrib"] = contrib
        r["disp"] = {
            "size": r["size"],
            "tuition": r["tuition"],
            "pell": r["pell"],
            "trend": bisect.bisect_left(live_trend, r["trend"]) / max(len(live_trend) - 1, 1),
        }
    live_health = sorted(r["health"] for r in rows if not r["closed"])
    for r in rows:
        r["pctile"] = bisect.bisect_left(live_health, r["health"]) / max(len(live_health) - 1, 1)
        r["band"] = _band(r["pctile"])
    return rows


def write_scores(con):
    """Populate the resilience_score table (defined in schema.sql) from the current DB.

    Called by build_db.py after the data loads, mirroring build_search_index. Read-only over the
    source tables; the only table it writes is its own.
    """
    con.execute("DELETE FROM resilience_score")
    scored = score_all(con)
    con.executemany(
        "INSERT INTO resilience_score (institution_id,band,pctile,health,"
        "p_size,p_trend,p_pell,p_tuition,c_size,c_trend,c_pell,c_tuition) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                r["id"],
                r["band"],
                round(r["pctile"], 4),
                round(r["health"], 4),
                round(r["disp"]["size"], 4),
                round(r["disp"]["trend"], 4),
                round(r["disp"]["pell"], 4),
                round(r["disp"]["tuition"], 4),
                round(r["contrib"]["size"], 4),
                round(r["contrib"]["trend"], 4),
                round(r["contrib"]["pell"], 4),
                round(r["contrib"]["tuition"], 4),
            )
            for r in scored
        ],
    )
    return len(scored)


if __name__ == "__main__":
    import sqlite3
    import sys
    from pathlib import Path

    con = sqlite3.connect(Path(__file__).resolve().parent.parent / "data" / "beyondthecliff.db")
    con.row_factory = sqlite3.Row
    if "--fit" in sys.argv:
        m = fit_model(build_features(con))
        print("FROZEN = {")
        for k in ("mean", "sd", "weights"):
            print(f'    "{k}": {{' + ", ".join(f'"{f}": {m[k][f]:.6f}' for f in FEATS) + "},")
        print(f'    "intercept": {m["intercept"]:.6f},')
        print("}")
    else:
        rows = score_all(con)
        live = [r for r in rows if not r["closed"]]
        print(f"scored {len(rows)} institutions ({len(live)} living)")
        for _, name in BANDS:
            n = sum(1 for r in live if r["band"] == name)
            print(f"  {name:10} {n:5}  ({n / len(live):.0%})")
