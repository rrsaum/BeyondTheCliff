"""Server-rendered charts. Dependency-free: each chart is a small block of accessible HTML
(a labelled bar list) generated from a query result, so charts regenerate on every request
and reflect the active filters. No JavaScript, no external chart library, prints cleanly.

Richer interactive/SVG visualization is a later design pass (see the dataviz skill); the
markup here is intentionally simple and styleable via static/app.css.
"""
from __future__ import annotations

from html import escape


def bars(title: str, rows: list[tuple], *, label_width: str = "6ch") -> str:
    """rows: list of (label, value). Returns a <figure> of proportional bars."""
    if not rows:
        return (
            f'<figure class="chart"><figcaption>{escape(title)}</figcaption>'
            '<p class="muted">No data for this selection.</p></figure>'
        )
    top = max(v for _, v in rows) or 1
    out = [f'<figure class="chart"><figcaption>{escape(title)}</figcaption>',
           '<div class="bars" role="img" aria-label="' + escape(title) + '">']
    for label, value in rows:
        pct = round(100 * value / top, 1)
        out.append(
            '<div class="bar-row">'
            f'<span class="bar-label" style="min-width:{label_width}">{escape(str(label))}</span>'
            '<span class="bar-track">'
            f'<span class="bar-fill" style="width:{pct}%"></span></span>'
            f'<span class="bar-value">{value}</span>'
            '</div>'
        )
    out.append('</div></figure>')
    return "".join(out)


def _fmt(v: float) -> str:
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.0f}K"
    return str(int(v))


def line(title: str, points: list[tuple], *, subtitle: str = "", note: str = "") -> str:
    """Filled area + line chart of a value over years, with a y axis, x-year labels, and a
    peak marker. points: (year, value). Baseline at zero so the scale is honest."""
    pts = sorted((int(y), int(v)) for y, v in points if str(v).strip() not in ("", "None"))
    if len(pts) < 2:
        return f'<figure class="chart cliff-chart"><figcaption>{escape(title)}</figcaption>' \
               '<p class="muted">No data.</p></figure>'
    w, h, padl, padr, padt, padb = 720, 340, 60, 18, 34, 30
    years = [p[0] for p in pts]
    vals = [p[1] for p in pts]
    xmin, xmax, ymax = min(years), max(years), max(vals) * 1.06
    peak_x, peak_y = max(pts, key=lambda p: p[1])

    def sx(x):
        return padl + (x - xmin) / ((xmax - xmin) or 1) * (w - padl - padr)

    def sy(v):
        return h - padb - (v / ymax) * (h - padt - padb)

    line_pts = " ".join(f"{sx(y):.1f},{sy(v):.1f}" for y, v in pts)
    area = f"{padl},{h - padb} {line_pts} {sx(xmax):.1f},{h - padb}"
    # y gridlines at ~4 steps
    grid = []
    for k in range(1, 5):
        gv = ymax * k / 4
        gy = sy(gv)
        grid.append(f'<line x1="{padl}" y1="{gy:.1f}" x2="{w - padr}" y2="{gy:.1f}" class="cl-grid"/>'
                    f'<text x="{padl - 6}" y="{gy + 3:.1f}" class="cl-ylab" text-anchor="end">{_fmt(gv)}</text>')
    # x labels: first, peak, last
    xlabs = []
    for xv in sorted({xmin, peak_x, xmax}):
        xlabs.append(f'<text x="{sx(xv):.1f}" y="{h - 10}" class="cl-xlab" text-anchor="middle">{xv}</text>')
    label = escape(title)
    sub = f'<p class="chart-sub">{escape(subtitle)}</p>' if subtitle else ""
    footnote = f'<figcaption class="chart-note">{escape(note)}</figcaption>' if note else ""
    return (
        f'<figure class="chart cliff-chart"><figcaption>{label}</figcaption>{sub}'
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{label}" class="cl-svg">'
        f'{"".join(grid)}'
        f'<polygon points="{area}" class="cl-area"/>'
        f'<polyline points="{line_pts}" class="cl-line" fill="none"/>'
        f'<circle cx="{sx(peak_x):.1f}" cy="{sy(peak_y):.1f}" r="4" class="cl-peak"/>'
        f'<text x="{sx(peak_x):.1f}" y="{sy(peak_y) - 8:.1f}" class="cl-peaklab" text-anchor="middle">peak {_fmt(peak_y)} ({peak_x})</text>'
        f'{"".join(xlabs)}'
        f'</svg>{footnote}</figure>'
    )


def trend(title: str, points: list[tuple]) -> str:
    """Inline SVG line chart of a value over years (e.g. enrollment). points: (year, value);
    None/blank values are dropped. Returns '' if there are fewer than two usable points."""
    pts = [(int(y), int(v)) for y, v in points if str(v).strip() not in ("", "None")]
    pts.sort()
    if len(pts) < 2:
        return ""
    w, h, pad = 520, 150, 30
    years = [p[0] for p in pts]
    vals = [p[1] for p in pts]
    xmin, xmax = min(years), max(years)
    ymax = max(vals)
    span_x = (xmax - xmin) or 1

    def sx(x):
        return pad + (x - xmin) / span_x * (w - 2 * pad)

    def sy(v):
        return h - pad - (v / (ymax or 1)) * (h - 2 * pad)

    poly = " ".join(f"{sx(y):.1f},{sy(v):.1f}" for y, v in pts)
    dots = "".join(
        f'<circle cx="{sx(y):.1f}" cy="{sy(v):.1f}" r="2.5" class="tr-dot"><title>'
        f'{y}: {v:,}</title></circle>' for y, v in pts
    )
    label = escape(title)
    return (
        f'<figure class="chart trend"><figcaption>{label}</figcaption>'
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{label}" class="trend-svg">'
        f'<polyline points="{poly}" class="tr-line" fill="none"/>{dots}'
        f'<text x="{pad}" y="{h - 8}" class="tr-ax">{xmin}</text>'
        f'<text x="{w - pad}" y="{h - 8}" class="tr-ax" text-anchor="end">{xmax}</text>'
        f'<text x="{pad}" y="{pad - 12}" class="tr-ax">peak {ymax:,}</text>'
        f'</svg></figure>'
    )
