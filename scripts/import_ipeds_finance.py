#!/usr/bin/env python3
"""Import the IPEDS Finance (F) survey time series into data/finance_year.csv.

IPEDS Finance is a U.S. Dept. of Education public record covering every Title IV institution
every fiscal year, in THREE reporting forms that carve up revenue differently, so each maps onto
our columns separately (form and codes verified against the official FY2022-23 dictionary,
F2223_{F1A,F2,F3}_Dict):

  F1A  public institutions, GASB 34/35
  F2   private not-for-profit (and FASB-reporting publics)
  F3   private for-profit

Keyed on UNITID, so we map UNITID -> our institution id (OPEID) via the unitid column on the
IPEDS-derived rows. Raw sourced dollars ONLY; ratios stay computed in queries.py.

Loads the six cleanly cross-comparable measures (total/tuition revenue, investment return,
total/instruction expense, end-of-year endowment) AND revenue by source (federal, state+local,
private). GASB and FASB split government money on different schedules, so each source is the SUM
of every line at that government level (operating + nonoperating + appropriations; capital grants
excluded) -- a defined convention that makes "federal dependence" comparable across the forms.

Reads the per-year form files from uploads/data/ipeds_finance/ (gitignored raw data, like the
Scorecard importer). For each file it extracts only the columns actually present in that year's
header, so variable-name drift across 20 years never fabricates a value. Standard library only.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FIN_DIR = ROOT / "uploads" / "data" / "ipeds_finance"

# our output column -> the source variable(s) in each form (verified from the FY2223 dictionary).
# Each per-form entry is a LIST of variable codes that are SUMMED (one element for the directly
# comparable measures; several for revenue-by-source, where GASB and FASB split government money on
# different schedules and the comparable convention is to sum every line at that government level
# -- operating + nonoperating + appropriations, capital grants excluded). Empty list = not reported
# by that form (e.g. for-profit F3 has no endowment).
MAP = {
    #                       F1A (GASB public)                    F2 (FASB nonprofit)  F3 (for-profit)
    "total_revenue": (["F1D01"], ["F2B01"], ["F3D09"]),
    "tuition_revenue": (["F1B01"], ["F2D01"], ["F3D01"]),
    "federal_revenue": (["F1B02", "F1B10", "F1B13"], ["F2D02", "F2D05"], ["F3D02"]),
    "state_local_revenue": (
        ["F1B03", "F1B04A", "F1B11", "F1B12", "F1B14", "F1B15"],
        ["F2D03", "F2D04"],
        ["F3D03"],
    ),
    "private_gifts_grants": (["F1B04B", "F1B16"], ["F2D08"], ["F3D04"]),
    "investment_return": (["F1B17"], ["F2D10"], ["F3D05"]),
    "total_expenses": (["F1C191"], ["F2E131"], ["F3E071"]),
    "instruction_expense": (["F1C011"], ["F2E011"], ["F3E011"]),
    "endowment_eoy": (["F1H02"], ["F2H02"], []),
}
FORM_IDX = {"f1a": 0, "f2": 1, "f3": 2}
OUT_FIELDS = [
    "institution_id",
    "fiscal_year",
    "total_revenue",
    "tuition_revenue",
    "federal_revenue",
    "state_local_revenue",
    "private_gifts_grants",
    "investment_return",
    "total_expenses",
    "instruction_expense",
    "endowment_eoy",
    "source",
    "source_url",
]
URL = "https://nces.ed.gov/ipeds/datacenter/data/{tag}.zip"


def unitid_to_id() -> dict[str, str]:
    m = {}
    for name in ("institutions.csv", "institutions_open.csv"):
        p = DATA / name
        if not p.exists():
            continue
        with p.open(encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                u = (r.get("unitid") or "").strip()
                if u and u not in m:
                    m[u] = r["id"].strip()
    return m


def clean_int(v: str) -> str:
    v = (v or "").strip()
    if v in {"", ".", "NA", "NULL"}:
        return ""
    try:
        return str(int(float(v)))
    except ValueError:
        return ""


def main() -> None:
    if not FIN_DIR.exists():
        raise SystemExit(f"Finance data dir not found: {FIN_DIR}")
    u2id = unitid_to_id()
    files = sorted(FIN_DIR.glob("f*_f*.csv"))
    out, kept = {}, []
    for path in files:
        m = re.match(r"f(\d{2})(\d{2})_(f1a|f2|f3)\.csv", path.name)
        if not m:
            continue
        fiscal_year = 2000 + int(m.group(2))  # f2223 -> FY2023
        form = m.group(3)
        fi = FORM_IDX[form]
        tag = f"F{m.group(1)}{m.group(2)}_{ {'f1a': 'F1A', 'f2': 'F2', 'f3': 'F3'}[form] }"
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            idx = {h.strip().upper(): i for i, h in enumerate(header)}
            if "UNITID" not in idx:
                continue
            ui = idx["UNITID"]
            # resolve, per this year's header, the header indices that feed each field (summed)
            col = {}
            for out_col, srcs in MAP.items():
                present = [idx[cc.upper()] for cc in srcs[fi] if cc.upper() in idx]
                if present:
                    col[out_col] = present
            n = 0
            for row in reader:
                if ui >= len(row):
                    continue
                unit = row[ui].strip()
                iid = u2id.get(unit)
                if not iid:
                    continue
                rec = {
                    "institution_id": iid,
                    "fiscal_year": fiscal_year,
                    "source": tag,
                    "source_url": URL.format(tag=tag),
                }
                for out_col, cis in col.items():
                    vals = [clean_int(row[ci]) for ci in cis if ci < len(row)]
                    nums = [int(v) for v in vals if v != ""]
                    rec[out_col] = str(sum(nums)) if nums else ""
                if any(rec.get(c) for c in MAP):  # skip all-null rows
                    out[(iid, fiscal_year)] = rec  # last form/year wins on any collision
                    n += 1
        kept.append((path.name, n))

    rows = sorted(out.values(), key=lambda r: (r["institution_id"], r["fiscal_year"]))
    with (DATA / "finance_year.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in OUT_FIELDS})

    insts = len({r["institution_id"] for r in rows})
    yrs = sorted({r["fiscal_year"] for r in rows})
    print(
        f"Finance files read: {len(kept)}; rows: {len(rows)} across {insts} institutions, "
        f"fiscal years {yrs[0] if yrs else '-'} to {yrs[-1] if yrs else '-'}"
    )
    print("Next: python3 scripts/build_db.py")


if __name__ == "__main__":
    main()
