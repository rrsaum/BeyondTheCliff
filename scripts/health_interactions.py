#!/usr/bin/env python3
"""Value-trap interaction search (step 3): is a high discount that fails to grow revenue predictive?

The doc grades the discount rate alone as weak and confounded. The value-trap thesis is sharper: a
high discount that FAILS to grow net tuition or fill the class is the distress signal, the give-away
that no longer works. This tests that specific interaction (not a scan of all pairs, to avoid
multiple-comparison luck): discount interacted with net-tuition growth and with enrollment trend.

Every model runs on the SAME usable set (schools with all six features present) so the holdout AUC
lifts are attributable, not artifacts of a shifting sample. Design and pass bars are preregistered in
docs/strategy/INSTITUTIONAL_HEALTH_METRICS.md and committed before this ran. Reuses health_validate's
percentile, slope, split, fit, and AUC. Read-only. Standard library, deterministic.

    .venv/bin/python scripts/health_interactions.py
"""

import statistics as st
from collections import defaultdict

from health_validate import DB, _in_train, _med, _pct_fn, _slope, auc, logit_fit, predict

BASE = ["size", "trend", "pell", "tuition"]  # the workhorse


def build(con):
    inst = {
        r["id"]: dict(closed=(r["status"] != "open"), s=r["status_year"])
        for r in con.execute("SELECT id, status, status_year FROM institution")
    }
    sc = defaultdict(dict)
    for r in con.execute(
        "SELECT institution_id, year, ugds, pct_pell, tuitfte, tuitionfee_in "
        "FROM scorecard WHERE year IS NOT NULL"
    ):
        sc[r["institution_id"]][r["year"]] = r

    def disc(r):
        t, s = r["tuitfte"], r["tuitionfee_in"]
        return 1 - t / s if (t is not None and s is not None and s > 0) else None

    by = {f: defaultdict(list) for f in ("ugds", "pct_pell", "tuitfte", "disc")}
    for ys in sc.values():
        for y, r in ys.items():
            for f, v in (
                ("ugds", r["ugds"]),
                ("pct_pell", r["pct_pell"]),
                ("tuitfte", r["tuitfte"]),
                ("disc", disc(r)),
            ):
                if v is not None:
                    by[f][y].append(v)
    pf = {f: _pct_fn(by[f]) for f in by}

    rows = []
    for i, ys in sc.items():
        o = inst.get(i)
        if not o:
            continue
        win = [y for y in sorted(ys) if (not o["closed"] or o["s"] is None or y < o["s"])]
        if len(win) < 3:
            continue
        rows.append(
            dict(
                id=i,
                y=1 if o["closed"] else 0,
                size=_med([pf["ugds"](y, ys[y]["ugds"]) for y in win]),
                trend=_slope([(y, ys[y]["ugds"]) for y in win[-5:]]),
                pell=_med([pf["pct_pell"](y, ys[y]["pct_pell"]) for y in win]),
                tuition=_med([pf["tuitfte"](y, ys[y]["tuitfte"]) for y in win]),
                discount=_med([pf["disc"](y, disc(ys[y])) for y in win]),
                nt_growth=_slope([(y, ys[y]["tuitfte"]) for y in win[-5:]]),
            )
        )
    return rows


def _design(r, feats, inters, mean, sd):
    z = {f: (r[f] - mean[f]) / sd[f] for f in feats}
    return [z[f] for f in feats] + [z[a] * z[b] for a, b in inters]


def run(rows, feats, inters, name):
    """All callers pass the SAME rows (common usable set) so AUC lifts are attributable."""
    tr = [r for r in rows if _in_train(r["id"])]
    ho = [r for r in rows if not _in_train(r["id"])]
    mean = {f: st.mean([r[f] for r in tr]) for f in feats}
    sd = {f: (st.pstdev([r[f] for r in tr]) or 1.0) for f in feats}
    w, b = logit_fit([_design(r, feats, inters, mean, sd) for r in tr], [r["y"] for r in tr])
    scores = [predict(w, b, _design(r, feats, inters, mean, sd)) for r in ho]
    a = auc(scores, [r["y"] for r in ho])
    labels = feats + [f"{x}*{y}" for x, y in inters]
    print(f"{name:34} AUC {a:.3f}")
    print("      weights: " + "  ".join(f"{lab}={w[j]:+.2f}" for j, lab in enumerate(labels)))
    return a


def main():
    import sqlite3

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    allrows = build(con)
    need = [*BASE, "discount", "nt_growth"]
    rows = [r for r in allrows if all(r[f] is not None for f in need)]
    ho_n = len([r for r in rows if not _in_train(r["id"])])
    closed = sum(r["y"] for r in rows)
    print(
        f"common usable set: {len(rows)} schools ({closed} closed, {closed / len(rows):.0%}), "
        f"holdout {ho_n}\n"
    )

    a_work = run(rows, BASE, [], "workhorse (baseline)")
    a_disc = run(rows, [*BASE, "discount"], [], "+ discount main effect (H5)")
    a_add = run(rows, [*BASE, "discount", "nt_growth"], [], "additive (+ discount + nt_growth)")
    a_int = run(
        rows,
        [*BASE, "discount", "nt_growth"],
        [("discount", "nt_growth"), ("discount", "trend")],
        "additive + value-trap interactions (H6)",
    )
    print()
    print(
        f"H5  discount main-effect lift over workhorse: {a_disc - a_work:+.3f}  (predicted < +0.010)"
    )
    print(
        f"H6  interaction lift over additive:           {a_int - a_add:+.3f}  (pass bar >= +0.005)"
    )


if __name__ == "__main__":
    main()
