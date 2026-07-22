#!/usr/bin/env python3
"""Preregistered, out-of-sample test: does combining our signals beat the federal score alone?

The discipline is the one carried over from Quantsage: single factors are traps, combinations
have to be validated, and validation means HELD-OUT institutions the model never saw, not the
rows it was fit on. Deaths stay in the sample (a closure is the outcome, not a dropped row).

Design, fixed before looking at any holdout number:
  * Unit: one row per institution, features summarized over its window (pre-closure years for a
    closure; all years for a survivor). Label y = 1 if the institution is closed.
  * Split: by institution id hash (md5 mod 100), 70 train / 30 holdout. No school in both, so a
    school-level pattern cannot leak across the split.
  * Model: plain L2-regularized logistic regression, fit by gradient descent, standardized on the
    TRAIN moments only. Reported metric: AUC on the holdout (probability a random closure scores
    less healthy than a random survivor).
  * Prespecified comparison: composite score ALONE vs composite + our added signals, on the subset
    where composite exists (private-nonprofit / proprietary). The added signals earn their place
    only if holdout AUC rises. A universal model (no composite) is reported for the full roster.

Read-only. Pure standard library. Deterministic (fixed seed in the split hash), so it reproduces.

    .venv/bin/python scripts/health_validate.py
"""

import bisect
import hashlib
import math
import sqlite3
import statistics as st
from collections import defaultdict
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "beyondthecliff.db"


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


def build_rows(con):
    inst = {
        r["id"]: dict(cyr=r["status_year"], closed=(r["status"] != "open"))
        for r in con.execute("SELECT id,status,status_year FROM institution")
    }
    sc = defaultdict(dict)
    for r in con.execute(
        "SELECT institution_id,year,ugds,adm_rate,tuitfte,pct_pell, "
        "COALESCE(ret_ft4,ret_ftl4) AS retention, COALESCE(c150_4,c150_l4) AS grad "
        "FROM scorecard WHERE year IS NOT NULL"
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
            for r in ys.values():
                if r[field] is not None:
                    d[r["year"]].append(r[field])
        return _pct_fn(d)

    pf = {m: collect(m) for m in ("ugds", "tuitfte", "adm_rate", "pct_pell", "retention", "grad")}
    cby = defaultdict(list)
    for i, ys in comp.items():
        for y, s in ys.items():
            cby[y].append(s)
    pc = _pct_fn(cby)

    rows = []
    for i, ys in sc.items():
        o = inst.get(i)
        if not o:
            continue
        win = [y for y in sorted(ys) if (not o["closed"] or not o["cyr"] or y < o["cyr"])]
        if len(win) < 3:
            continue
        cvals = [(y, comp[i][y]) for y in win if y in comp.get(i, {})]
        rows.append(
            dict(
                id=i,
                y=1 if o["closed"] else 0,
                comp_pctile=_med([pc(y, v) for y, v in cvals]),
                comp_slope=_slope(cvals),
                ugds_pctile=_med([pf["ugds"](y, ys[y]["ugds"]) for y in win]),
                ugds_slope5=_slope([(y, ys[y]["ugds"]) for y in win[-5:]]),
                tuit_pctile=_med([pf["tuitfte"](y, ys[y]["tuitfte"]) for y in win]),
                adm_pctile=_med([pf["adm_rate"](y, ys[y]["adm_rate"]) for y in win]),
                pell_pctile=_med([pf["pct_pell"](y, ys[y]["pct_pell"]) for y in win]),
                ret_pctile=_med([pf["retention"](y, ys[y]["retention"]) for y in win]),
                grad_pctile=_med([pf["grad"](y, ys[y]["grad"]) for y in win]),
            )
        )
    return rows


def _in_train(iid):
    h = int(hashlib.md5(str(iid).encode()).hexdigest(), 16)
    return (h % 100) < 70


def logit_fit(X, y, l2=1.0, lr=0.1, iters=4000):
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


def predict(w, b, x):
    z = b + sum(w[j] * x[j] for j in range(len(w)))
    return 1.0 / (1.0 + math.exp(-max(-30, min(30, z))))


def auc(scores, labels):
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return None
    order = sorted(range(len(scores)), key=lambda k: scores[k])
    ranks = [0.0] * len(scores)
    k = 0
    while k < len(order):
        j = k
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[k]]:
            j += 1
        avg = (k + j) / 2.0 + 1.0
        for m in range(k, j + 1):
            ranks[order[m]] = avg
        k = j + 1
    rsum = sum(ranks[i] for i in range(len(scores)) if labels[i] == 1)
    return (rsum - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))


def run_model(rows, feats, name):
    usable = [r for r in rows if all(r[f] is not None for f in feats)]
    tr = [r for r in usable if _in_train(r["id"])]
    ho = [r for r in usable if not _in_train(r["id"])]
    if len(tr) < 30 or len(ho) < 30:
        print(f"{name:36} n too small (train {len(tr)}, holdout {len(ho)})")
        return
    mean = {f: st.mean([r[f] for r in tr]) for f in feats}
    sd = {f: (st.pstdev([r[f] for r in tr]) or 1.0) for f in feats}

    def vec(r):
        return [(r[f] - mean[f]) / sd[f] for f in feats]

    Xtr = [vec(r) for r in tr]
    ytr = [r["y"] for r in tr]
    w, b = logit_fit(Xtr, ytr)
    sho = [predict(w, b, vec(r)) for r in ho]
    a = auc(sho, [r["y"] for r in ho])
    base = sum(r["y"] for r in ho) / len(ho)
    print(f"{name:36} holdout AUC {a:.3f}  (train {len(tr)}, holdout {len(ho)}, closed {base:.0%})")
    print("      weights: " + "  ".join(f"{f}={w[j]:+.2f}" for j, f in enumerate(feats)))
    return a


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = build_rows(con)
    print(f"panel: {len(rows)} institutions ({sum(r['y'] for r in rows)} closed)\n")

    print("== UNIVERSAL (whole roster: Scorecard signals, no federal composite) ==")
    run_model(rows, ["ugds_pctile"], "enrollment level only")
    run_model(rows, ["ugds_pctile", "ugds_slope5"], "enrollment level + trend")
    run_model(rows, ["ugds_pctile", "ugds_slope5", "pell_pctile"], "+ Pell reliance")
    run_model(
        rows,
        ["ugds_pctile", "ugds_slope5", "pell_pctile", "tuit_pctile", "adm_pctile"],
        "all universal signals",
    )
    print(
        "\n== COMPOSITE SUBSET (private-nonprofit / proprietary: does adding our signals beat it?) =="
    )
    csub = [r for r in rows if r["comp_pctile"] is not None]
    print(f"   subset with a federal composite score: {len(csub)} institutions\n")
    run_model(rows, ["comp_pctile"], "federal composite ALONE (baseline)")
    run_model(rows, ["comp_pctile", "comp_slope"], "composite level + trend")
    run_model(rows, ["comp_pctile", "ugds_pctile", "ugds_slope5"], "composite + enrollment")
    run_model(
        rows,
        ["comp_pctile", "comp_slope", "ugds_pctile", "ugds_slope5", "pell_pctile"],
        "composite + our full set",
    )


if __name__ == "__main__":
    main()
