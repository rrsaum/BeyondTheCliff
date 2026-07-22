#!/usr/bin/env python3
"""Descriptive analysis of the full closure record, 1746 to 2027 (NOT a predictive model).

This is deliberately separate from the predictive work in health_validate / health_era /
health_survival / health_interactions. Those are bounded by the federal-data era (closures 2004+,
features 2009+); this looks at the whole documented record, using only what the historical rows
actually carry: closure year, sector (control), and a recorded cause where one exists. It produces no
AUC and predicts nothing. It answers a different question: what does the century-long closure record
look like. Source is the closure record itself (SHEEO, IPEDS directory, and Wikipedia/Wikidata for the
historical rows); a recorded cause is Wikipedia-sourced and present for only some rows.

Read-only over the DB. Standard library, deterministic.

    .venv/bin/python scripts/closure_history.py
"""

import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "beyondthecliff.db"
ERAS = [
    (0, 1950, "pre-1950"),
    (1950, 2000, "1950-1999"),
    (2000, 2012, "2000-2011"),
    (2012, 2100, "2012-2027"),
]
CONTROL = {"public": "public", "private_nonprofit": "nonprofit", "private_forprofit": "for-profit"}


def _era(y):
    for lo, hi, lab in ERAS:
        if lo <= y < hi:
            return lab
    return None


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT status_year AS y, control, cause FROM institution "
        "WHERE status != 'open' AND status_year IS NOT NULL"
    ).fetchall()
    print(
        f"documented closures with a year: {len(rows)} (years {min(r['y'] for r in rows)} "
        f"to {max(r['y'] for r in rows)})\n"
    )

    print("== closures per decade ==")
    dec = Counter((r["y"] // 10) * 10 for r in rows)
    for d in sorted(dec):
        bar = "#" * round(dec[d] / 8)
        print(f"  {d}s: {dec[d]:4}  {bar}")

    print("\n== sector mix of closures by era (control), row % within era ==")
    by_era = defaultdict(list)
    for r in rows:
        e = _era(r["y"])
        if e:
            by_era[e].append(r)
    print(
        f"  {'era':12}{'n':>6}  {'public':>10}{'nonprofit':>11}{'for-profit':>12}{'(unknown)':>11}"
    )
    for _, _, lab in ERAS:
        er = by_era.get(lab, [])
        if not er:
            continue
        cc = Counter(CONTROL.get(r["control"], "(unknown)") for r in er)
        n = len(er)

        def pct(k, cc=cc, n=n):
            return f"{100 * cc.get(k, 0) / n:.0f}%"

        print(
            f"  {lab:12}{n:>6}  {pct('public'):>10}{pct('nonprofit'):>11}"
            f"{pct('for-profit'):>12}{pct('(unknown)'):>11}"
        )

    print("\n== recorded cause by era (among closures WITH a recorded cause) ==")
    for _, _, lab in ERAS:
        er = by_era.get(lab, [])
        withc = [r for r in er if r["cause"]]
        if not er:
            continue
        cov = f"{len(withc)}/{len(er)} = {100 * len(withc) / len(er):.0f}% have a cause"
        top = Counter(r["cause"] for r in withc).most_common(3)
        top_s = ", ".join(f"{k} {100 * v / len(withc):.0f}%" for k, v in top) if withc else "none"
        print(f"  {lab:12} ({cov}): {top_s}")

    print("\n== lifespan (closure year - founding year): NOT AVAILABLE ==")
    nf = con.execute(
        "SELECT COUNT(*) FROM institution WHERE status != 'open' AND status_year IS NOT NULL "
        "AND founding_year IS NOT NULL"
    ).fetchone()[0]
    print(f"  only {nf} of {len(rows)} closures carry a founding year (nearly all modern), too")
    print("  sparse for an honest lifespan distribution. Marked NOT AVAILABLE, not estimated.")


if __name__ == "__main__":
    main()
