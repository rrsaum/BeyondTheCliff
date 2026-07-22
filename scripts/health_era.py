#!/usr/bin/env python3
"""Era-forward validation (hardening step 1): train on earlier closures, test on later ones.

The cross-sectional split in health_validate.py holds out schools; this holds out TIME. It trains a
model on closures through the cutoff year and tests it on the closures after, which is the harder
question a cross-sectional split cannot answer: does a model fit to the past rank the closures that
came after, or was it riding one era (the 2016 for-profit wave is 22 percent of dated closures)?

Design and pass bars are preregistered in docs/strategy/INSTITUTIONAL_HEALTH_METRICS.md and were
committed before this was run. Reuses health_validate.py's feature builder, logistic fit, and AUC
rather than rewriting them. Read-only over the DB. Standard library, deterministic.

    .venv/bin/python scripts/health_era.py
"""

import hashlib
import sqlite3
import statistics as st

from health_validate import DB, auc, build_rows, logit_fit, predict

CUTOFF = 2016  # EARLY = closures with status_year <= 2016; LATE = 2017 and after. Preregistered.


def _survivor_era(iid):
    """Partition survivors (no closure year) so none is in both eras, base rate kept realistic."""
    return "early" if int(hashlib.md5(str(iid).encode()).hexdigest(), 16) % 2 == 0 else "late"


def run(train, test, feats, name):
    """Standardize on TRAIN only, fit, score TEST, report held-out AUC and the fitted weights."""
    tr = [r for r in train if all(r[f] is not None for f in feats)]
    te = [r for r in test if all(r[f] is not None for f in feats)]
    if len(tr) < 30 or len(te) < 30:
        print(f"{name:34} n too small (train {len(tr)}, test {len(te)})")
        return None
    mean = {f: st.mean([r[f] for r in tr]) for f in feats}
    sd = {f: (st.pstdev([r[f] for r in tr]) or 1.0) for f in feats}

    def vec(r):
        return [(r[f] - mean[f]) / sd[f] for f in feats]

    w, b = logit_fit([vec(r) for r in tr], [r["y"] for r in tr])
    scores = [predict(w, b, vec(r)) for r in te]
    a = auc(scores, [r["y"] for r in te])
    base = sum(r["y"] for r in te) / len(te)
    wtxt = "  ".join(f"{f}={w[j]:+.2f}" for j, f in enumerate(feats))
    print(f"{name:34} AUC {a:.3f}  (train {len(tr)}, test {len(te)}, test closed {base:.0%})")
    print(f"      weights: {wtxt}")
    return a


UNIVERSAL = [
    (["ugds_pctile"], "enrollment level only"),
    (["ugds_pctile", "ugds_slope5"], "enrollment level + trend"),
    (["ugds_pctile", "ugds_slope5", "pell_pctile"], "+ Pell reliance"),
    (["ugds_pctile", "ugds_slope5", "pell_pctile", "tuit_pctile"], "+ net tuition (workhorse)"),
]
COMPOSITE = [
    (["comp_pctile"], "federal composite ALONE (baseline)"),
    (["comp_pctile", "comp_slope"], "composite level + trend"),
    (["comp_pctile", "ugds_pctile", "ugds_slope5"], "composite + enrollment"),
    (
        ["comp_pctile", "comp_slope", "ugds_pctile", "ugds_slope5", "pell_pctile"],
        "composite + our full set",
    ),
]


def _split(rows, syear):
    early, late = [], []
    for r in rows:
        if r["y"] == 1:  # closure: era by its closure year
            yr = syear.get(r["id"])
            if yr is None:
                continue
            (early if yr <= CUTOFF else late).append(r)
        else:  # survivor: hashed partition
            (early if _survivor_era(r["id"]) == "early" else late).append(r)
    return early, late


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = build_rows(con)
    syear = {
        r["id"]: r["status_year"]
        for r in con.execute("SELECT id, status_year FROM institution WHERE status != 'open'")
    }
    early, late = _split(rows, syear)
    nc_e = sum(r["y"] for r in early)
    nc_l = sum(r["y"] for r in late)
    print(f"EARLY (<= {CUTOFF}): {len(early)} schools, {nc_e} closures ({nc_e / len(early):.0%})")
    print(
        f"LATE  (>= {CUTOFF + 1}): {len(late)} schools, {nc_l} closures ({nc_l / len(late):.0%})\n"
    )

    for title, train, test in [
        ("PRIMARY: train EARLY, test LATE (forward)", early, late),
        ("ROBUSTNESS: train LATE, test EARLY (reverse)", late, early),
    ]:
        print(f"== {title} ==")
        print("-- universal (whole roster) --")
        for feats, name in UNIVERSAL:
            run(train, test, feats, name)
        print("-- composite subset --")
        csub_tr = [r for r in train if r["comp_pctile"] is not None]
        csub_te = [r for r in test if r["comp_pctile"] is not None]
        for feats, name in COMPOSITE:
            run(csub_tr, csub_te, feats, name)
        print()


if __name__ == "__main__":
    main()
