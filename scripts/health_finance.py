#!/usr/bin/env python3
"""Re-validation with the clean IPEDS discount and reserve (step 4, H6-clean and H8).

The rough scorecard discount proxy could not see the value trap (H6 null). This reruns that test with
the dictionary-verified IPEDS discount rate (allowances / gross tuition) and adds a primary-reserve
ratio (net position / total expenses), the first balance-sheet-strength signal that covers public
institutions. Workhorse features come from build_rows (Scorecard); discount, net-tuition growth, and
reserve are aggregated per institution from finance_year (IPEDS). All models run on the SAME usable
set so the lifts are attributable.

Design and pass bars preregistered in docs/strategy/INSTITUTIONAL_HEALTH_METRICS.md, committed before
this ran. Reuses health_validate's builder, split, fit, and AUC. Read-only. Standard library.

    .venv/bin/python scripts/health_finance.py
"""

import statistics as st
from collections import defaultdict

from health_validate import DB, _in_train, _med, _slope, auc, build_rows, logit_fit, predict

WORK = ["ugds_pctile", "ugds_slope5", "pell_pctile", "tuit_pctile"]


def finance_features(con):
    fy = defaultdict(list)
    for r in con.execute(
        "SELECT institution_id, fiscal_year, tuition_revenue, tuition_allowances, "
        "net_position, total_expenses FROM finance_year WHERE fiscal_year IS NOT NULL"
    ):
        fy[r["institution_id"]].append(r)
    out = {}
    for iid, rows in fy.items():
        disc, res, nt = [], [], []
        for r in rows:
            t, a = r["tuition_revenue"], r["tuition_allowances"]
            if t is not None and a is not None and (t + a) > 0:
                disc.append(a / (t + a))
            if r["net_position"] is not None and r["total_expenses"] and r["total_expenses"] > 0:
                res.append(r["net_position"] / r["total_expenses"])
            if r["tuition_revenue"] is not None:
                nt.append((r["fiscal_year"], r["tuition_revenue"]))
        out[iid] = dict(discount=_med(disc), reserve=_med(res), nt_growth=_slope(nt))
    return out


def _design(r, feats, inters, mean, sd):
    z = {f: (r[f] - mean[f]) / sd[f] for f in feats}
    return [z[f] for f in feats] + [z[a] * z[b] for a, b in inters]


def run(rows, feats, inters, name):
    tr = [r for r in rows if _in_train(r["id"])]
    ho = [r for r in rows if not _in_train(r["id"])]
    mean = {f: st.mean([r[f] for r in tr]) for f in feats}
    sd = {f: (st.pstdev([r[f] for r in tr]) or 1.0) for f in feats}
    w, b = logit_fit([_design(r, feats, inters, mean, sd) for r in tr], [r["y"] for r in tr])
    a = auc([predict(w, b, _design(r, feats, inters, mean, sd)) for r in ho], [r["y"] for r in ho])
    labels = feats + [f"{x}*{y}" for x, y in inters]
    print(f"{name:38} AUC {a:.3f}")
    print("      weights: " + "  ".join(f"{lab}={w[j]:+.2f}" for j, lab in enumerate(labels)))
    return a


def main():
    import sqlite3

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    ff = finance_features(con)
    rows = []
    for r in build_rows(con):
        f = ff.get(r["id"])
        if f:
            rows.append({**r, **f})
    need = [*WORK, "discount", "nt_growth", "reserve"]
    rows = [r for r in rows if all(r.get(f) is not None for f in need)]
    closed = sum(r["y"] for r in rows)
    ho_n = len([r for r in rows if not _in_train(r["id"])])
    print(
        f"common usable set: {len(rows)} schools ({closed} closed, {closed / len(rows):.0%}), "
        f"holdout {ho_n}\n"
    )

    a_work = run(rows, WORK, [], "workhorse (baseline)")
    a_disc = run(rows, [*WORK, "discount"], [], "+ clean discount main effect (H6a)")
    a_res = run(rows, [*WORK, "reserve"], [], "+ reserve ratio (H8)")
    a_add = run(rows, [*WORK, "discount", "nt_growth"], [], "additive (+ discount + nt_growth)")
    a_int = run(
        rows,
        [*WORK, "discount", "nt_growth"],
        [("discount", "nt_growth"), ("discount", "ugds_slope5")],
        "additive + value-trap interactions (H6b)",
    )
    print()
    print(
        f"H6a clean-discount main-effect lift over workhorse: {a_disc - a_work:+.3f}  (predict < +0.010)"
    )
    print(
        f"H6b value-trap interaction lift over additive:      {a_int - a_add:+.3f}  (pass bar >= +0.005)"
    )
    print(
        f"H8  reserve-ratio lift over workhorse:              {a_res - a_work:+.3f}  (pass bar >= +0.010)"
    )


if __name__ == "__main__":
    main()
