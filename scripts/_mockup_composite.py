#!/usr/bin/env python3
"""Generate three composite-score chart mockups for review in the browser."""
from pathlib import Path

DATA = [
    (2007, 1.6), (2008, 1.1), (2009, 1.1), (2010, 1.2), (2011, 2.2), (2012, 1.7),
    (2013, 1.2), (2014, 1.9), (2015, 2.1), (2016, 1.7), (2017, 1.7), (2018, 0.7),
    (2019, 1.1), (2020, 0.8), (2021, 2.3), (2022, 3.0), (2023, 2.2),
]
BREAK = 2020.5  # ED rewrote the ratios effective 1 July 2020
OLD = [d for d in DATA if d[0] < BREAK]
NEW = [d for d in DATA if d[0] > BREAK]

W, H = 940, 300
PADL, PADR, PADT, PADB = 52, 116, 18, 44


def zone(s):
    if s >= 1.5:
        return "pass"
    if s >= 1.0:
        return "zone"
    return "fail"


ZONE_LABEL = {"pass": "Financially responsible", "zone": "Added federal oversight",
              "fail": "Letter of credit required"}


def make(ymin, ymax):
    def sx(x):
        return PADL + (x - 2007) / (2023 - 2007) * (W - PADL - PADR)

    def sy(v):
        return H - PADB - (v - ymin) / (ymax - ymin) * (H - PADT - PADB)
    return sx, sy


def yaxis(sy, ymin, ymax, step=0.5):
    out = []
    v = ymin
    while v <= ymax + 1e-9:
        y = sy(v)
        out.append(f'<line x1="{PADL}" y1="{y:.1f}" x2="{W-PADR}" y2="{y:.1f}" class="grid"/>'
                   f'<text x="{PADL-8}" y="{y+3.5:.1f}" class="ylab" text-anchor="end">{v:.1f}</text>')
        v += step
    return "".join(out)


def xaxis(sx):
    out = []
    for yr, _ in DATA:
        x = sx(yr)
        out.append(f'<text x="{x:.1f}" y="{H-PADB+16:.1f}" class="xlab" text-anchor="middle">'
                   f'{str(yr)[2:]}</text>')
    out.append(f'<text x="{sx(2007):.1f}" y="{H-PADB+32:.1f}" class="xlab-full" text-anchor="middle">2007</text>')
    out.append(f'<text x="{sx(2023):.1f}" y="{H-PADB+32:.1f}" class="xlab-full" text-anchor="middle">2023</text>')
    return "".join(out)


def breakline(sx):
    x = sx(BREAK)
    return (f'<line x1="{x:.1f}" y1="{PADT}" x2="{x:.1f}" y2="{H-PADB}" class="brk"/>'
            f'<text x="{x-5:.1f}" y="{PADT+10}" class="brk-lab" text-anchor="end">'
            f'old formula</text>'
            f'<text x="{x+5:.1f}" y="{PADT+10}" class="brk-lab" text-anchor="start">'
            f'new formula</text>')


def thresholds(sy, ymin):
    """Threshold lines labelled in the right margin, never over the plot."""
    out = []
    for v, lab in ((1.5, "1.5 pass"), (1.0, "1.0 oversight")):
        if v < ymin:
            continue
        y = sy(v)
        out.append(f'<line x1="{PADL}" y1="{y:.1f}" x2="{W-PADR}" y2="{y:.1f}" class="thr thr-{lab.split()[1]}"/>'
                   f'<text x="{W-PADR+8}" y="{y+3.5:.1f}" class="thr-lab">{lab}</text>')
    return "".join(out)


# ---------- A: line + zone bands ----------
def mockup_a():
    ymin, ymax = 0.5, 3.0
    sx, sy = make(ymin, ymax)
    bands = ""
    for lo, hi, cls in ((ymin, 1.0, "fail"), (1.0, 1.5, "zone"), (1.5, ymax, "pass")):
        y1, y2 = sy(hi), sy(lo)
        bands += (f'<rect x="{PADL}" y="{y1:.1f}" width="{W-PADL-PADR}" height="{y2-y1:.1f}" '
                  f'class="band band-{cls}"/>')
    body = ""
    for seg in (OLD, NEW):
        pts = " ".join(f"{sx(y):.1f},{sy(v):.1f}" for y, v in seg)
        body += f'<polyline points="{pts}" class="ln"/>'
        for y, v in seg:
            body += (f'<circle cx="{sx(y):.1f}" cy="{sy(v):.1f}" r="4" class="dot dot-{zone(v)}">'
                     f'<title>{y}: {v:.1f} ({ZONE_LABEL[zone(v)]})</title></circle>')
    last = NEW[-1]
    body += (f'<text x="{sx(last[0]):.1f}" y="{sy(last[1])-12:.1f}" class="direct" '
             f'text-anchor="end">{last[1]:.1f}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" class="cv" role="img" '
            f'aria-label="Composite score 2007 to 2023, line with zone bands">'
            f'{bands}{yaxis(sy, ymin, ymax)}{breakline(sx)}{body}{xaxis(sx)}'
            f'<text x="{W-PADR+8}" y="{sy(2.25):.1f}" class="zn zn-pass">pass</text>'
            f'<text x="{W-PADR+8}" y="{sy(1.25):.1f}" class="zn zn-zone">oversight</text>'
            f'<text x="{W-PADR+8}" y="{sy(0.75):.1f}" class="zn zn-fail">letter of credit</text>'
            f'</svg>')


# ---------- B: columns coloured by zone ----------
def mockup_b():
    ymin, ymax = 0.0, 3.0
    sx, sy = make(ymin, ymax)
    bw = 30
    body = ""
    for y, v in DATA:
        x = sx(y) - bw / 2
        top = sy(v)
        body += (f'<rect x="{x:.1f}" y="{top:.1f}" width="{bw}" height="{sy(ymin)-top:.1f}" '
                 f'rx="3" class="bar bar-{zone(v)}">'
                 f'<title>{y}: {v:.1f} ({ZONE_LABEL[zone(v)]})</title></rect>'
                 f'<text x="{sx(y):.1f}" y="{top-6:.1f}" class="barlab" text-anchor="middle">{v:.1f}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" class="cv" role="img" '
            f'aria-label="Composite score by award year, columns coloured by federal zone">'
            f'{yaxis(sy, ymin, ymax)}{body}{thresholds(sy, ymin)}{breakline(sx)}{xaxis(sx)}</svg>')


# ---------- C: dot plot + zone strip ----------
def mockup_c():
    ymin, ymax = 0.5, 3.0
    sx, sy = make(ymin, ymax)
    body = ""
    for seg in (OLD, NEW):
        pts = " ".join(f"{sx(y):.1f},{sy(v):.1f}" for y, v in seg)
        body += f'<polyline points="{pts}" class="ln ln-faint"/>'
    for y, v in DATA:
        body += (f'<line x1="{sx(y):.1f}" y1="{sy(ymin):.1f}" x2="{sx(y):.1f}" y2="{sy(v):.1f}" '
                 f'class="stem stem-{zone(v)}"/>'
                 f'<circle cx="{sx(y):.1f}" cy="{sy(v):.1f}" r="5.5" class="dot dot-{zone(v)}">'
                 f'<title>{y}: {v:.1f} ({ZONE_LABEL[zone(v)]})</title></circle>')
    strip_y = H - PADB + 22
    strip = ""
    for y, v in DATA:
        strip += (f'<rect x="{sx(y)-13:.1f}" y="{strip_y}" width="26" height="6" rx="2" '
                  f'class="chip chip-{zone(v)}"><title>{y}: {ZONE_LABEL[zone(v)]}</title></rect>')
    return (f'<svg viewBox="0 0 {W} {H+18}" class="cv" role="img" '
            f'aria-label="Composite score by award year, dot plot with a status strip">'
            f'{yaxis(sy, ymin, ymax)}{thresholds(sy, ymin)}{breakline(sx)}{body}'
            f'{xaxis(sx)}{strip}</svg>')


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Composite score: three mockups</title>
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
.lead {{ color:var(--ink-soft); max-width:70ch; margin:0 0 1.5rem; }}
.card {{ background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);
  padding:1.1rem 1.2rem; margin:0 0 1.5rem; }}
h2 {{ font-size:1.05rem; margin:0 0 .2rem; }}
.tag {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.05em; color:var(--accent);
  font-weight:700; }}
.why {{ font-size:.85rem; color:var(--ink-soft); margin:.35rem 0 .9rem; max-width:78ch; }}
.tradeoff {{ font-size:.8rem; color:var(--ink-soft); margin:.7rem 0 0; padding-top:.6rem;
  border-top:1px solid var(--line); }}
.tradeoff b {{ color:var(--ink); }}
.cv {{ width:100%; height:auto; display:block; }}
.grid {{ stroke:var(--line); stroke-width:1; }}
.ylab,.xlab {{ fill:var(--ink-soft); font-size:11px; }}
.xlab-full {{ fill:var(--ink-soft); font-size:11px; font-weight:600; }}
.ln {{ fill:none; stroke:var(--accent); stroke-width:2; }}
.ln-faint {{ stroke:var(--line); stroke-width:1.5; }}
.dot {{ stroke:var(--surface); stroke-width:1.5; }}
.dot-pass {{ fill:var(--good); }} .dot-zone {{ fill:var(--warn); }} .dot-fail {{ fill:var(--closed); }}
.stem {{ stroke-width:1.5; }}
.stem-pass {{ stroke:var(--good); opacity:.35; }}
.stem-zone {{ stroke:var(--warn); opacity:.35; }}
.stem-fail {{ stroke:var(--closed); opacity:.35; }}
.bar-pass {{ fill:var(--good); }} .bar-zone {{ fill:var(--warn); }} .bar-fail {{ fill:var(--closed); }}
.barlab {{ fill:var(--ink-soft); font-size:10px; font-variant-numeric:tabular-nums; }}
.band-pass {{ fill:var(--good); opacity:.07; }}
.band-zone {{ fill:var(--warn); opacity:.10; }}
.band-fail {{ fill:var(--closed); opacity:.10; }}
.thr {{ stroke-dasharray:4 3; stroke-width:1.2; }}
.thr-pass {{ stroke:var(--good); }} .thr-oversight {{ stroke:var(--warn); }}
.thr-lab {{ fill:var(--ink-soft); font-size:10px; }}
.zn {{ font-size:10px; font-weight:600; }}
.zn-pass {{ fill:var(--good); }} .zn-zone {{ fill:var(--warn); }} .zn-fail {{ fill:var(--closed); }}
.brk {{ stroke:var(--ink-soft); stroke-width:1; stroke-dasharray:3 3; }}
.brk-lab {{ fill:var(--ink-soft); font-size:9.5px; font-style:italic; }}
.direct {{ fill:var(--ink); font-size:12px; font-weight:700; }}
.chip {{ }} .chip-pass {{ fill:var(--good); }} .chip-zone {{ fill:var(--warn); }}
.chip-fail {{ fill:var(--closed); }}
.note {{ font-size:.76rem; color:var(--ink-soft); margin:.6rem 0 0; }}
.legend {{ display:flex; gap:1rem; flex-wrap:wrap; font-size:.78rem; color:var(--ink-soft);
  margin:0 0 .6rem; }}
.key {{ display:inline-flex; align-items:center; gap:.35rem; }}
.sw {{ width:.7rem; height:.7rem; border-radius:2px; display:inline-block; }}
.sw-pass {{ background:var(--good); }} .sw-zone {{ background:var(--warn); }}
.sw-fail {{ background:var(--closed); }}
.decide {{ background:var(--accent-soft); border-left:3px solid var(--accent);
  border-radius:var(--radius); padding:.9rem 1rem; margin:0 0 1.5rem; }}
.decide h2 {{ color:var(--accent); }}
.decide ol {{ margin:.4rem 0 0; padding-left:1.2rem; font-size:.88rem; }}
.decide li {{ margin:.3rem 0; }}
</style>
<div class="wrap">
<h1>Composite score chart: three mockups</h1>
<p class="lead">Same data every time: Montreat College, Financial Responsibility Composite Score,
award years 2006-07 to 2022-23 (U.S. Dept. of Education, eZ-Audit). Pick one, or tell me what to
take from each.</p>

<div class="decide">
  <h2>What I need you to decide</h2>
  <ol>
    <li><b>Which form.</b> A reads the trend, B reads each year's verdict, C is a compromise.</li>
    <li><b>The y axis.</b> All three cut it at 0.5 or 0. ED publishes the scale as -1.0 to 3.0.
      The old chart showed the full scale, which left 40% of the plot empty and squashed the
      data. Cutting it reads better but stops this school's chart being directly comparable to
      one that scored below zero. My recommendation: cut it, and let the shared thresholds do the
      comparison work.</li>
    <li><b>Colour by zone, or one colour?</b> A, B and C all colour by federal zone (green /
      amber / red). It is legible but it makes a bad year look like a verdict. One accent colour
      throughout is more sober and more on-brand.</li>
  </ol>
</div>

<div class="card">
  <p class="tag">Mockup A</p>
  <h2>Line with zone bands</h2>
  <p class="why">The trend is the subject: the line carries it, and the shaded bands say what
    territory it was in without you reading numbers. Threshold names sit in the right margin
    instead of on top of the data, which is what made the old one unreadable.</p>
  <div class="legend">
    <span class="key"><i class="sw sw-pass"></i>1.5 and above: responsible</span>
    <span class="key"><i class="sw sw-zone"></i>1.0 to 1.4: added oversight</span>
    <span class="key"><i class="sw sw-fail"></i>Below 1.0: letter of credit</span>
  </div>
  {a}
  <p class="tradeoff"><b>Strength:</b> the shape of the story is instant, and the 2018 and 2020
    dips read as events. <b>Cost:</b> a line implies continuity between what are actually
    discrete annual audits.</p>
</div>

<div class="card">
  <p class="tag">Mockup B</p>
  <h2>One column per award year</h2>
  <p class="why">Treats each year as what it is: a separate audit with a separate verdict. No line
    implies anything between them. Every value is labelled, so the table underneath becomes
    optional.</p>
  <div class="legend">
    <span class="key"><i class="sw sw-pass"></i>Responsible</span>
    <span class="key"><i class="sw sw-zone"></i>Added oversight</span>
    <span class="key"><i class="sw sw-fail"></i>Letter of credit</span>
  </div>
  {b}
  <p class="tradeoff"><b>Strength:</b> the most honest about the data's grain, and the easiest to
    read a single year off. <b>Cost:</b> 17 bars is a lot of ink, and the trend is harder to see
    than in A.</p>
</div>

<div class="card">
  <p class="tag">Mockup C</p>
  <h2>Dot plot with a status strip</h2>
  <p class="why">Least ink. Dots are the annual audits, the faint line is there only to guide the
    eye and never claims to be data, and the strip along the bottom answers "which years was this
    school in trouble" at a glance without reading the plot at all.</p>
  <div class="legend">
    <span class="key"><i class="sw sw-pass"></i>Responsible</span>
    <span class="key"><i class="sw sw-zone"></i>Added oversight</span>
    <span class="key"><i class="sw sw-fail"></i>Letter of credit</span>
  </div>
  {c}
  <p class="tradeoff"><b>Strength:</b> carries trend and per-year verdict together, and the strip
    is scannable. <b>Cost:</b> the faint line is a judgement call; some readers will still read it
    as interpolation.</p>
</div>

<p class="note">All three: hover any mark for the year, score, and what it meant. The formula
break is drawn and never joined across, since ED rewrote the ratios effective 1 July 2020 and the
two sides are not the same measurement. Source: Financial Responsibility Composite Score, U.S.
Dept. of Education (eZ-Audit).</p>
</div>
"""

out = Path("app/static/mockups-composite.html")
out.write_text(PAGE.format(a=mockup_a(), b=mockup_b(), c=mockup_c()), encoding="utf-8")
print(f"wrote {out}")
