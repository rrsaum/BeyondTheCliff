#!/usr/bin/env python3
"""Re-validation of the retention/graduation import (step 4, H7): do they beat the workhorse?

Zemsky's third variable is retention. This adds the newly imported Scorecard retention and
graduation (coalesced level-appropriate, as within-year percentiles by build_rows) to the workhorse
and asks whether they clear their preregistered bar out of sample. All models run on the SAME usable
set (schools with every feature present) so the AUC lift is attributable. Reuses health_validate's
panel builder, split, fit, and AUC. Read-only. Standard library, deterministic.

    .venv/bin/python scripts/health_retention.py
"""

import statistics as st

from health_validate import DB, _in_train, auc, build_rows, logit_fit, predict

WORKHORSE = ["ugds_pctile", "ugds_slope5", "pell_pctile", "tuit_pctile"]


def run(rows, feats, name):
    tr = [r for r in rows if _in_train(r["id"])]
    ho = [r for r in rows if not _in_train(r["id"])]
    mean = {f: st.mean([r[f] for r in tr]) for f in feats}
    sd = {f: (st.pstdev([r[f] for r in tr]) or 1.0) for f in feats}

    def vec(r):
        return [(r[f] - mean[f]) / sd[f] for f in feats]

    w, b = logit_fit([vec(r) for r in tr], [r["y"] for r in tr])
    a = auc([predict(w, b, vec(r)) for r in ho], [r["y"] for r in ho])
    print(
        f"{name:28} AUC {a:.3f}   weights: "
        + "  ".join(f"{f}={w[j]:+.2f}" for j, f in enumerate(feats))
    )
    return a


def main():
    import sqlite3

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    need = [*WORKHORSE, "ret_pctile", "grad_pctile"]
    rows = [r for r in build_rows(con) if all(r[f] is not None for f in need)]
    closed = sum(r["y"] for r in rows)
    ho_n = len([r for r in rows if not _in_train(r["id"])])
    print(
        f"common usable set: {len(rows)} schools ({closed} closed, {closed / len(rows):.0%}), "
        f"holdout {ho_n}\n"
    )
    base = run(rows, WORKHORSE, "workhorse (baseline)")
    run(rows, [*WORKHORSE, "ret_pctile"], "+ retention")
    run(rows, [*WORKHORSE, "grad_pctile"], "+ graduation")
    both = run(rows, [*WORKHORSE, "ret_pctile", "grad_pctile"], "+ retention + graduation")
    print(
        f"\nH7  retention+graduation lift over workhorse: {both - base:+.3f}  (pass bar >= +0.010)"
    )


if __name__ == "__main__":
    main()
