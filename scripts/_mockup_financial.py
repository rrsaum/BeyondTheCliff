#!/usr/bin/env python3
"""Three mockups for the Form 990 financial section, in mockup A's visual language."""
from pathlib import Path

# (fiscal_year, total_revenue, contributions, government_grants, private_giving, total_expenses)
RAW = [
    (2013, 18872597, 1812433, 191240, 1472293, 21485088),
    (2014, 21411095, 4203667, 197862, 3466986, 21368773),
    (2015, 24520267, 7679022, 204244, 7383578, 23002253),
    (2016, 24489825, 5809165, 214284, 5594881, 23977746),
    (2017, 25614896, 5910813, 179420, 5531193, 24685779),
    (2018, 26025705, 5194277, 2138324, 2967553, 25177177),
    (2019, 26871797, 5172826, 150236, 4926890, 27047774),
    (2022, 59160491, 28763176, 18622812, 10054414, 40102921),
    (2023, 54006517, 22573699, 17660340, 4913359, 41975471),
    (2024, 50474167, 18296438, 8953918, 9342520, 40105166),
    (2025, 42925388, 7709897, 1982924, 5726973, 43796854),
]
YEARS = [r[0] for r in RAW]
EARNED = {r[0]: r[1] - r[2] for r in RAW}
EXPENSES = {r[0]: r[5] for r in RAW}
GOVT = {r[0]: r[3] for r in RAW}
PRIVATE = {r[0]: r[4] for r in RAW}
COVER = {y: EARNED[y] / EXPENSES[y] for y in YEARS}

W, H = 940, 300
PADL, PADT, PADB = 62, 20, 46


def runs(years):
    """Split into consecutive-year runs, so the FY2020-21 hole is drawn as a hole."""
    out, cur = [], [years[0]]
    for a, b in zip(years, years[1:]):
        if b - a == 1:
            cur.append(b)
        else:
            out.append(cur)
            cur = [b]
    out.append(cur)
    return out


RUNS = runs(YEARS)


def axes(padr, ymin, ymax):
    def sx(x):
        return PADL + (x - YEARS[0]) / (YEARS[-1] - YEARS[0]) * (W - PADL - padr)

    def sy(v):
        return H - PADB - (v - ymin) / (ymax - ymin) * (H - PADT - PADB)
    return sx, sy


def grid(sx, sy, padr, steps, fmt):
    out = ""
    for v in steps:
        y = sy(v)
        out += (f'<line x1="{PADL}" y1="{y:.1f}" x2="{W-padr}" y2="{y:.1f}" class="grid"/>'
                f'<text x="{PADL-8}" y="{y+3.5:.1f}" class="ylab" text-anchor="end">{fmt(v)}</text>')
    return out


def xlabels(sx):
    out = ""
    for y in YEARS:
        out += (f'<text x="{sx(y):.1f}" y="{H-PADB+16:.1f}" class="xlab" text-anchor="middle">'
                f'{str(y)[2:]}</text>')
    for y in (YEARS[0], YEARS[-1]):
        out += (f'<text x="{sx(y):.1f}" y="{H-PADB+32:.1f}" class="xlab-full" text-anchor="middle">'
                f'{y}</text>')
    return out


def gaphole(sx, label="no filing FY2020-FY2021"):
    x1, x2 = sx(2019), sx(2022)
    return (f'<rect x="{x1:.1f}" y="{PADT}" width="{x2-x1:.1f}" height="{H-PADB-PADT:.1f}" '
            f'class="hole"/>'
            f'<text x="{(x1+x2)/2:.1f}" y="{PADT+11}" class="hole-lab" text-anchor="middle">'
            f'{label}</text>')


def money(v):
    return f"${v/1e6:.0f}M"


# ---------- 1: the gap ----------
def m1():
    padr = 128
    ymin, ymax = 0, 48e6
    sx, sy = axes(padr, ymin, ymax)
    out = grid(sx, sy, padr, [0, 12e6, 24e6, 36e6, 48e6], money) + gaphole(sx)
    for r in RUNS:
        poly = (" ".join(f"{sx(y):.1f},{sy(EARNED[y]):.1f}" for y in r) + " "
                + " ".join(f"{sx(y):.1f},{sy(EXPENSES[y]):.1f}" for y in reversed(r)))
        out += f'<polygon points="{poly}" class="gapfill"/>'
    for key, cls in ((EXPENSES, "expense"), (EARNED, "earned")):
        for r in RUNS:
            pts = " ".join(f"{sx(y):.1f},{sy(key[y]):.1f}" for y in r)
            out += f'<polyline points="{pts}" class="ln ln-{cls}"/>'
        for y in YEARS:
            out += (f'<circle cx="{sx(y):.1f}" cy="{sy(key[y]):.1f}" r="3.4" class="dot dot-{cls}">'
                    f'<title>FY{y}: {money(key[y])}</title></circle>')
    ly = YEARS[-1]
    out += (f'<text x="{W-padr+8}" y="{sy(EXPENSES[ly])+4:.1f}" class="gut gut-expense">'
            f'Expenses {money(EXPENSES[ly])}</text>'
            f'<text x="{W-padr+8}" y="{sy(EARNED[ly])+4:.1f}" class="gut gut-earned">'
            f'Earned {money(EARNED[ly])}</text>'
            f'<text x="{W-padr+8}" y="{(sy(EXPENSES[ly])+sy(EARNED[ly]))/2+4:.1f}" '
            f'class="gut gut-gap">gap {money(EXPENSES[ly]-EARNED[ly])}</text>')
    return f'<svg viewBox="0 0 {W} {H}" class="cv" role="img" aria-label="Earned revenue against expenses">{out}{xlabels(sx)}</svg>'


# ---------- 2: coverage ratio ----------
def m2():
    padr = 132
    ymin, ymax = 0.5, 1.1
    sx, sy = axes(padr, ymin, ymax)
    out = ""
    y1, y0 = sy(1.1), sy(1.0)
    out += f'<rect x="{PADL}" y="{y1:.1f}" width="{W-PADL-padr}" height="{y0-y1:.1f}" class="band band-pass"/>'
    y1, y0 = sy(1.0), sy(ymin)
    out += f'<rect x="{PADL}" y="{y1:.1f}" width="{W-PADL-padr}" height="{y0-y1:.1f}" class="band band-zone"/>'
    out += grid(sx, sy, padr, [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1], lambda v: f"{v*100:.0f}%")
    out += gaphole(sx)
    out += (f'<line x1="{PADL}" y1="{sy(1.0):.1f}" x2="{W-padr}" y2="{sy(1.0):.1f}" class="thr"/>')
    for r in RUNS:
        pts = " ".join(f"{sx(y):.1f},{sy(COVER[y]):.1f}" for y in r)
        out += f'<polyline points="{pts}" class="ln ln-earned"/>'
    for y in YEARS:
        out += (f'<circle cx="{sx(y):.1f}" cy="{sy(COVER[y]):.1f}" r="4" class="dot dot-zone">'
                f'<title>FY{y}: earned revenue covered {COVER[y]*100:.0f}% of expenses</title></circle>')
    ly = YEARS[-1]
    out += (f'<text x="{sx(ly):.1f}" y="{sy(COVER[ly])-11:.1f}" class="direct" text-anchor="end">'
            f'{COVER[ly]*100:.0f}%</text>')
    out += (f'<text x="{W-padr+8}" y="{sy(1.05):.1f}" class="gut gut-pass">pays for itself</text>'
            f'<text x="{W-padr+8}" y="{sy(0.75):.1f}" class="gut gut-zone">the part gifts</text>'
            f'<text x="{W-padr+8}" y="{sy(0.75)+13:.1f}" class="gut gut-zone">must cover</text>')
    return f'<svg viewBox="0 0 {W} {H}" class="cv" role="img" aria-label="Share of expenses covered by earned revenue">{out}{xlabels(sx)}</svg>'


# ---------- 3: stacked composition ----------
def m3():
    padr = 128
    ymin, ymax = 0, 64e6
    sx, sy = axes(padr, ymin, ymax)
    out = grid(sx, sy, padr, [0, 16e6, 32e6, 48e6, 64e6], money) + gaphole(sx)
    layers = [("earned", EARNED), ("private", PRIVATE), ("govt", GOVT)]
    base = {y: 0 for y in YEARS}
    for name, vals in layers:
        for r in RUNS:
            top = [(y, base[y] + vals[y]) for y in r]
            bot = [(y, base[y]) for y in reversed(r)]
            poly = " ".join(f"{sx(y):.1f},{sy(v):.1f}" for y, v in top + bot)
            out += f'<polygon points="{poly}" class="area area-{name}"/>'
        for y in YEARS:
            base[y] += vals[y]
    for r in RUNS:
        pts = " ".join(f"{sx(y):.1f},{sy(EXPENSES[y]):.1f}" for y in r)
        out += f'<polyline points="{pts}" class="ln ln-expense"/>'
    for y in YEARS:
        out += (f'<circle cx="{sx(y):.1f}" cy="{sy(EXPENSES[y]):.1f}" r="3.4" class="dot dot-expense">'
                f'<title>FY{y}: expenses {money(EXPENSES[y])}</title></circle>')
    ly = YEARS[-1]
    out += (f'<text x="{W-padr+8}" y="{sy(EXPENSES[ly])+4:.1f}" class="gut gut-expense">'
            f'Expenses</text>'
            f'<text x="{W-padr+8}" y="{sy(EARNED[ly]/2):.1f}" class="gut gut-earned">Earned</text>'
            f'<text x="{W-padr+8}" y="{sy(EARNED[ly]+PRIVATE[ly]/2):.1f}" class="gut gut-private">Private gifts</text>'
            f'<text x="{W-padr+8}" y="{sy(EARNED[ly]+PRIVATE[ly]+GOVT[ly]/2)-4:.1f}" class="gut gut-govt">Government</text>')
    return f'<svg viewBox="0 0 {W} {H}" class="cv" role="img" aria-label="Revenue composition against expenses">{out}{xlabels(sx)}</svg>'


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>The financial record: three mockups</title>
<style>
:root {{
  --ink:#1b2733; --ink-soft:#4a5866; --paper:#fbfaf7; --surface:#ffffff; --line:#e3e0d8;
  --accent:#1f5c7a; --accent-soft:#dcebf1; --warn:#9a5b1d; --closed:#b23a48; --merged:#4a5866;
  --good:#2f6f4f; --radius:8px;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}}
body {{ margin:0; background:var(--paper); color:var(--ink); line-height:1.5; }}
.wrap {{ max-width:1040px; margin:0 auto; padding:1.5rem 1.25rem 4rem; }}
h1 {{ font-size:1.5rem; margin:0 0 .3rem; }}
.lead {{ color:var(--ink-soft); max-width:72ch; margin:0 0 1.5rem; }}
.card {{ background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);
  padding:1.1rem 1.2rem; margin:0 0 1.5rem; }}
h2 {{ font-size:1.05rem; margin:0 0 .2rem; }}
.tag {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.05em; color:var(--accent);
  font-weight:700; margin:0; }}
.why {{ font-size:.85rem; color:var(--ink-soft); margin:.35rem 0 .9rem; max-width:80ch; }}
.tradeoff {{ font-size:.8rem; color:var(--ink-soft); margin:.7rem 0 0; padding-top:.6rem;
  border-top:1px solid var(--line); }}
.tradeoff b {{ color:var(--ink); }}
.cv {{ width:100%; height:auto; display:block; }}
.grid {{ stroke:var(--line); stroke-width:1; }}
.ylab,.xlab {{ fill:var(--ink-soft); font-size:11px; }}
.xlab-full {{ fill:var(--ink-soft); font-size:11px; font-weight:600; }}
.ln {{ fill:none; stroke-width:2.2; }}
.ln-earned {{ stroke:var(--accent); }}
.ln-expense {{ stroke:var(--closed); }}
.dot {{ stroke:var(--surface); stroke-width:1.5; }}
.dot-earned {{ fill:var(--accent); }} .dot-expense {{ fill:var(--closed); }}
.dot-zone {{ fill:var(--warn); }}
.gapfill {{ fill:var(--warn); opacity:.13; }}
.area-earned {{ fill:var(--accent); opacity:.85; }}
.area-private {{ fill:var(--accent); opacity:.42; }}
.area-govt {{ fill:var(--warn); opacity:.72; }}
.band-pass {{ fill:var(--good); opacity:.09; }}
.band-zone {{ fill:var(--warn); opacity:.09; }}
.thr {{ stroke:var(--good); stroke-width:1.4; stroke-dasharray:4 3; }}
.hole {{ fill:var(--paper); opacity:.75; }}
.hole-lab {{ fill:var(--ink-soft); font-size:9.5px; font-style:italic; }}
.gut {{ font-size:10.5px; font-weight:600; }}
.gut-earned {{ fill:var(--accent); }} .gut-expense {{ fill:var(--closed); }}
.gut-gap {{ fill:var(--warn); }} .gut-govt {{ fill:var(--warn); }}
.gut-private {{ fill:var(--accent); }} .gut-pass {{ fill:var(--good); }}
.gut-zone {{ fill:var(--warn); }}
.direct {{ fill:var(--ink); font-size:12px; font-weight:700; }}
.note {{ font-size:.76rem; color:var(--ink-soft); margin:.6rem 0 0; }}
.decide {{ background:var(--accent-soft); border-left:3px solid var(--accent);
  border-radius:var(--radius); padding:.9rem 1rem; margin:0 0 1.5rem; }}
.decide h2 {{ color:var(--accent); }}
.decide ol {{ margin:.4rem 0 0; padding-left:1.2rem; font-size:.88rem; }}
.decide li {{ margin:.3rem 0; }}
</style>
<div class="wrap">
<h1>The financial record: three mockups</h1>
<p class="lead">Same data every time: Montreat College, IRS Form 990, FY2013 to FY2025. Same
visual language as the composite chart you picked. Each replaces BOTH charts in the current
section. Pick one, or tell me what to take from each.</p>

<div class="decide">
  <h2>What changed in all three, and what I need you to decide</h2>
  <ol>
    <li><b>"Total revenue" is gone.</b> It was the third line on the old chart and it is just
      earned plus gifts, so it added a line without adding a fact. Say if you want it back.</li>
    <li><b>Which form.</b> 1 shows the gap in dollars, 2 shows it as one ratio, 3 shows the whole
      composition. My recommendation is 2, because the finding is that the ratio barely moved in
      thirteen years, and only 2 shows that.</li>
    <li><b>Whether the FY2022-24 spike should dominate.</b> Money charts (1 and 3) are ruled by
      it: government grants tripled the scale, so the first seven years get squashed. The ratio
      (2) is immune. That is a real trade, not a detail.</li>
  </ol>
</div>

<div class="card">
  <p class="tag">Mockup 1</p>
  <h2>The gap, in dollars</h2>
  <p class="why">Two lines and the shaded distance between them. That distance is the subject:
    the part of every year that gifts and grants had to cover. The old chart drew this and never
    named it.</p>
  {m1}
  <p class="tradeoff"><b>Strength:</b> concrete, in dollars, and the gap is impossible to miss.
    <b>Cost:</b> the FY2022 jump compresses FY2013-19 into the bottom third, which is exactly
    where the school was in the most trouble.</p>
</div>

<div class="card">
  <p class="tag">Mockup 2</p>
  <h2>Share of expenses the school covered itself</h2>
  <p class="why">One line: earned revenue divided by expenses. The green line at 100% is the year
    paying for itself. Everything below it is the gap, expressed as the number a CFO would use.
    This is the only version where the actual finding is visible: the line is flat.</p>
  {m2}
  <p class="tradeoff"><b>Strength:</b> immune to the scale jump, and it says the thing worth
    saying, that thirteen years of change left this ratio where it started. It also matches the
    composite chart's grammar exactly: a line, a threshold, zones. <b>Cost:</b> a ratio is one
    step removed from the money, and it hides that the school doubled in size.</p>
</div>

<div class="card">
  <p class="tag">Mockup 3</p>
  <h2>Where every dollar came from, against what was spent</h2>
  <p class="why">Revenue stacked into what the school earned, what donors gave, and what
    government gave, with the expense line laid over it. One chart instead of two: the mix and
    the shortfall in the same frame.</p>
  {m3}
  <p class="tradeoff"><b>Strength:</b> the government-grant story tells itself, and it replaces
    both existing charts honestly. <b>Cost:</b> the densest of the three, stacked bands are hard
    to read a value off, and it inherits the same scale-jump problem as 1.</p>
</div>

<p class="note">All three: hover any mark for the year and value. No return was filed for FY2020
or FY2021, so every line breaks there rather than joining across a year nobody reported. Source:
IRS Form 990, FY2013 to FY2025, as filed.</p>
</div>
"""

out = Path("app/static/mockups-financial.html")
out.write_text(PAGE.format(m1=m1(), m2=m2(), m3=m3()), encoding="utf-8")
print(f"wrote {out}")
