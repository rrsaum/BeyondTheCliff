#!/usr/bin/env python3
"""Import IRS Form 990 filings into data/financials.csv and data/financial_line_items.csv.

Form 990 is the annual return every private nonprofit college must file publicly. It is the
only financial record that exists for every one of them, on the same form, year after year,
which makes it the one place a school's decline (or recovery) is measurable from the outside.
It is a U.S. government record, so it is public domain.

Usage:

    python3 scripts/import_990.py <dir-or-file> [...]     # import, then rebuild with build_db.py
    python3 scripts/import_990.py <dir> --dry-run         # parse and print, write nothing
    python3 scripts/import_990.py <dir> --check           # also run the prior-year cross-check

Filings are keyed on EIN and this database is keyed on OPEID, so the join is the hand-curated
crosswalk in data/institution_eins.csv. An unknown EIN is reported and skipped: guessing which
school a filing belongs to is exactly the kind of error this project cannot make. Add the
pairing to that CSV first, sourced.

Two things this parser must get right, both learned from real filings:

  * The financial tags were renamed wholesale after tax year 2012. TY2012 says
    TotalRevenueCurrentYear, TY2013+ says CYTotalRevenueAmt, and the abbreviations are not
    predictable (GrantsAndSimilarAmntsCY vs CYGrantsAndSimilarPaidAmt). Hence FIELDS below
    carries both spellings per field, verified against filings rather than recalled.
  * The first EIN and the first business name in the XML belong to the PREPARER, not the
    school. Montreat's TY2012 filing opens with Dixon Hughes Goodman LLP. Identity is read
    from the Filer element only, never by first match.

Reruns are idempotent: a filing replaces its own (institution_id, tax_year) rows and leaves
every other school's rows untouched, so importing one college never disturbs another.
Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FINANCIALS = DATA / "financials.csv"
LINE_ITEMS = DATA / "financial_line_items.csv"
EINS = DATA / "institution_eins.csv"

SOURCE = "IRS Form 990"
# Every filing here is a public record retrievable by EIN from the IRS index.
SOURCE_URL = "https://www.irs.gov/charities-non-profits/form-990-series-downloads"

# field -> (tag in TY2013+ filings, tag in TY2012-and-earlier filings).
# Both spellings verified present across the filings in hand; do not add a row from memory.
FIELDS: dict[str, tuple[str, str]] = {
    "tax_year": ("TaxYr", "TaxYear"),
    "period_begin": ("TaxPeriodBeginDt", "TaxPeriodBeginDate"),
    "period_end": ("TaxPeriodEndDt", "TaxPeriodEndDate"),
    "return_type": ("ReturnTypeCd", "ReturnType"),
    "total_revenue": ("CYTotalRevenueAmt", "TotalRevenueCurrentYear"),
    "contributions": ("CYContributionsGrantsAmt", "ContributionsGrantsCurrentYear"),
    # The split inside contributions. Part VIII lines, so they sum to roughly (not exactly)
    # the Part I contributions total: keep all three and let the page show the difference.
    "government_grants": ("GovernmentGrantsAmt", "GovernmentGrants"),
    "other_contributions": ("AllOtherContributionsAmt", "AllOtherContributions"),
    "noncash_contributions": ("NoncashContributionsAmt", "NoncashContributions"),
    "program_svc_revenue": ("CYProgramServiceRevenueAmt", "ProgramServiceRevenueCY"),
    "investment_income": ("CYInvestmentIncomeAmt", "InvestmentIncomeCurrentYear"),
    "other_revenue": ("CYOtherRevenueAmt", "OtherRevenueCurrentYear"),
    "total_expenses": ("CYTotalExpensesAmt", "TotalExpensesCurrentYear"),
    "program_svc_expenses": ("TotalProgramServiceExpensesAmt", "TotalProgramServiceExpense"),
    "fundraising_expenses": ("CYTotalFundraisingExpenseAmt", "TotalFundrsngExpCurrentYear"),
    "salaries": ("CYSalariesCompEmpBnftPaidAmt", "SalariesEtcCurrentYear"),
    "grants_paid": ("CYGrantsAndSimilarPaidAmt", "GrantsAndSimilarAmntsCY"),
    "net_income": ("CYRevenuesLessExpensesAmt", "RevenuesLessExpensesCY"),
    "total_assets": ("TotalAssetsEOYAmt", "TotalAssetsEOY"),
    "total_liabilities": ("TotalLiabilitiesEOYAmt", "TotalLiabilitiesEOY"),
    "net_assets": ("NetAssetsOrFundBalancesEOYAmt", "NetAssetsOrFundBalancesEOY"),
    "employees": ("TotalEmployeeCnt", "TotalNbrEmployees"),
}

# Prior-year restatements. Each filing repeats last year's figures, so filing N's PY value
# should equal filing N-1's CY value: a free consistency check on both the source and this
# parser. Keyed by the CY field name above.
PRIOR_YEAR: dict[str, tuple[str, str]] = {
    "total_revenue": ("PYTotalRevenueAmt", "TotalRevenuePriorYear"),
    "total_expenses": ("PYTotalExpensesAmt", "TotalExpensesPriorYear"),
    "contributions": ("PYContributionsGrantsAmt", "ContributionsGrantsPriorYear"),
    "grants_paid": ("PYGrantsAndSimilarPaidAmt", "GrantsAndSimilarAmntsPriorYear"),
    "salaries": ("PYSalariesCompEmpBnftPaidAmt", "SalariesEtcPriorYear"),
}

# Part VIII program service revenue lines. The school writes its own labels here, so these
# are stored verbatim rather than mapped to columns. Element name differs by schema era.
PROG_SVC_ELEMENTS = ("ProgramServiceRevenueGrp", "ProgramServiceRevenue")
LINE_DESC = ("Desc", "Description")
LINE_AMOUNT = ("TotalRevenueColumnAmt", "TotalRevenueColumn")

CSV_COLUMNS = [
    "institution_id",
    "tax_year",
    "period_begin",
    "period_end",
    "return_type",
    "ein",
    "total_revenue",
    "contributions",
    "government_grants",
    "other_contributions",
    "noncash_contributions",
    "program_svc_revenue",
    "investment_income",
    "other_revenue",
    "total_expenses",
    "program_svc_expenses",
    "fundraising_expenses",
    "salaries",
    "grants_paid",
    "net_income",
    "total_assets",
    "total_liabilities",
    "net_assets",
    "employees",
    "source",
    "source_url",
    "source_file",
]
LINE_COLUMNS = ["institution_id", "tax_year", "part", "description", "amount", "source_file"]


def local(tag: str) -> str:
    """Strip the {http://www.irs.gov/efile} namespace the filings are wrapped in."""
    return tag.split("}")[-1]


def index_tags(root: ET.Element) -> dict[str, str]:
    """Flatten the filing to first-value-wins by local tag name.

    Safe for the financial totals (each appears once, in ReturnData) but NOT for identity:
    EIN and business name appear first under the preparer. Those come from filer_identity().
    """
    seen: dict[str, str] = {}
    for el in root.iter():
        name, text = local(el.tag), (el.text or "").strip()
        if text and name not in seen:
            seen[name] = text
    return seen


def filer_identity(root: ET.Element) -> tuple[str | None, str | None]:
    """(EIN, name) read from the Filer element only.

    The ReturnHeader lists the paid preparer's firm before the filer, so a document-order
    match on EIN or BusinessNameLine1 returns the accounting firm. This scopes to Filer.
    """
    for el in root.iter():
        if local(el.tag) != "Filer":
            continue
        ein = name = None
        for child in el.iter():
            tag, text = local(child.tag), (child.text or "").strip()
            if not text:
                continue
            if tag == "EIN" and ein is None:
                ein = text
            elif tag in ("BusinessNameLine1Txt", "BusinessNameLine1") and name is None:
                name = text
        return ein, name
    return None, None


def pick(tags: dict[str, str], pair: tuple[str, str]) -> str | None:
    """Value for a field, trying the modern tag then the pre-2013 one."""
    new, old = pair
    return tags.get(new, tags.get(old))


def as_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_filing(path: Path) -> tuple[dict, list[dict]]:
    """Parse one 990 XML into a financials row plus its verbatim line items."""
    root = ET.parse(path).getroot()
    tags = index_tags(root)
    ein, name = filer_identity(root)

    row: dict = {"ein": ein, "_filer_name": name, "source_file": path.name}
    for field, pair in FIELDS.items():
        raw = pick(tags, pair)
        row[field] = raw if field in ("period_begin", "period_end", "return_type") else as_int(raw)
    row["_prior"] = {f: as_int(pick(tags, p)) for f, p in PRIOR_YEAR.items()}

    lines = []
    for el in root.iter():
        if local(el.tag) not in PROG_SVC_ELEMENTS:
            continue
        vals = {local(c.tag): (c.text or "").strip() for c in el.iter()}
        desc = next((vals[k] for k in LINE_DESC if vals.get(k)), None)
        amount = next((vals[k] for k in LINE_AMOUNT if vals.get(k)), None)
        if desc or amount:
            lines.append(
                {
                    "tax_year": row["tax_year"],
                    "part": "program_service_revenue",
                    "description": desc,  # verbatim, typos and all
                    "amount": as_int(amount),
                    "source_file": path.name,
                }
            )
    return row, lines


def _institution_names() -> dict[str, str]:
    """institution_id -> name, from whichever CSVs feed the institution table."""
    names: dict[str, str] = {}
    for csv_path in sorted(DATA.glob("*.csv")):
        try:
            with csv_path.open(encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                if not reader.fieldnames or {"id", "name"} - set(reader.fieldnames):
                    continue
                for r in reader:
                    if r.get("id") and r.get("name") and r["id"] not in names:
                        names[r["id"]] = r["name"]
        except (OSError, csv.Error):
            continue
    return names


def ein_to_institution() -> dict[str, tuple[str, str]]:
    """EIN -> (institution_id, name), from data/institution_eins.csv.

    Read from the crosswalk alone, never from a column on an institution CSV. IPEDS does not
    publish EINs, and data/institutions_open.csv is regenerated whole from IPEDS by
    scripts/import_ipeds_roster.py, so an EIN parked there is erased the next time that runs.
    """
    if not EINS.exists():
        return {}
    names = _institution_names()
    mapping: dict[str, tuple[str, str]] = {}
    with EINS.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            ein = (r.get("ein") or "").strip()
            inst_id = (r.get("institution_id") or "").strip()
            if ein and inst_id:
                mapping[ein] = (inst_id, names.get(inst_id, inst_id))
    return mapping


def read_existing(path: Path, columns: list[str]) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return [{c: r.get(c, "") for c in columns} for r in csv.DictReader(fh)]


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({c: ("" if r.get(c) is None else r[c]) for c in columns})


def cross_check(rows: list[dict]) -> list[str]:
    """Each filing restates the prior year. Compare filing N's PY figures to filing N-1's CY.

    A mismatch means either the school amended a return or this parser mapped a tag wrong.
    Either way it is worth seeing rather than trusting silently. Consecutive years only.
    """
    problems = []
    by_year = {r["tax_year"]: r for r in rows if r.get("tax_year")}
    for year, row in sorted(by_year.items()):
        previous = by_year.get(year - 1)
        if not previous:
            continue
        for field, stated in (row.get("_prior") or {}).items():
            actual = previous.get(field)
            if stated is not None and actual is not None and stated != actual:
                problems.append(
                    f"TY{year} restates {field} for TY{year - 1} as {stated:,}, "
                    f"but the TY{year - 1} filing reported {actual:,}"
                )
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description="Import IRS Form 990 filings.")
    ap.add_argument("paths", nargs="+", help="990 XML files, or directories of them")
    ap.add_argument("--dry-run", action="store_true", help="parse and print, write nothing")
    ap.add_argument("--check", action="store_true", help="run the prior-year cross-check")
    args = ap.parse_args()

    files: list[Path] = []
    for p in args.paths:
        path = Path(p).expanduser()
        if path.is_dir():
            files.extend(sorted(path.glob("*.xml")))
        elif path.is_file():
            files.append(path)
        else:
            raise SystemExit(f"no such file or directory: {path}")
    if not files:
        raise SystemExit("no .xml filings found")

    mapping = ein_to_institution()
    parsed, lines, unmatched = [], [], {}
    for f in files:
        try:
            row, item_rows = parse_filing(f)
        except ET.ParseError as exc:
            print(f"  {f.name}: not parseable as XML ({exc}); skipped", file=sys.stderr)
            continue
        if not row.get("tax_year"):
            print(f"  {f.name}: no tax year found; skipped", file=sys.stderr)
            continue
        ein = row.get("ein")
        if ein not in mapping:
            unmatched.setdefault(ein, (row.get("_filer_name"), []))[1].append(f.name)
            continue
        inst_id, inst_name = mapping[ein]
        row["institution_id"] = inst_id
        row["source"], row["source_url"] = SOURCE, SOURCE_URL
        row["_name"] = inst_name
        for item in item_rows:
            item["institution_id"] = inst_id
        parsed.append(row)
        lines.extend(item_rows)

    for ein, (filer_name, filenames) in unmatched.items():
        print(
            f"  unknown ein={ein} ({filer_name or 'unknown filer'}): skipped "
            f"{len(filenames)} filing(s). Add the OPEID/EIN pairing to "
            f"{EINS.relative_to(ROOT)}, with a source, then rerun.",
            file=sys.stderr,
        )

    if not parsed:
        raise SystemExit("nothing imported")

    for name in sorted({r["_name"] for r in parsed}):
        subset = sorted(r["tax_year"] for r in parsed if r["_name"] == name)
        gaps = [y for y in range(min(subset), max(subset) + 1) if y not in subset]
        print(f"  {name}: {len(subset)} filing(s), TY{min(subset)}-TY{max(subset)}")
        if gaps:
            # Say the gap out loud. A missing year is invisible in a chart otherwise.
            print(f"    no filing for: {', '.join(f'TY{y}' for y in gaps)}")

    if args.check:
        problems = cross_check(parsed)
        if problems:
            print("  prior-year cross-check found mismatches:", file=sys.stderr)
            for p in problems:
                print(f"    {p}", file=sys.stderr)
        else:
            print("  prior-year cross-check: every restated figure agrees")

    if args.dry_run:
        print("  dry run: nothing written")
        return

    touched = {(r["institution_id"], str(r["tax_year"])) for r in parsed}
    kept = [
        r
        for r in read_existing(FINANCIALS, CSV_COLUMNS)
        if (r["institution_id"], r["tax_year"]) not in touched
    ]
    kept_lines = [
        r
        for r in read_existing(LINE_ITEMS, LINE_COLUMNS)
        if (r["institution_id"], r["tax_year"]) not in touched
    ]
    out = sorted(kept + parsed, key=lambda r: (r["institution_id"], int(r["tax_year"])))
    out_lines = sorted(kept_lines + lines, key=lambda r: (r["institution_id"], int(r["tax_year"])))
    write_csv(FINANCIALS, CSV_COLUMNS, out)
    write_csv(LINE_ITEMS, LINE_COLUMNS, out_lines)
    print(f"  wrote {FINANCIALS.relative_to(ROOT)}: {len(out)} row(s)")
    print(f"  wrote {LINE_ITEMS.relative_to(ROOT)}: {len(out_lines)} row(s)")
    print("  now run: python3 scripts/build_db.py")


if __name__ == "__main__":
    main()
