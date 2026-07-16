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
    out = [
        f'<figure class="chart"><figcaption>{escape(title)}</figcaption>',
        '<div class="bars" role="img" aria-label="' + escape(title) + '">',
    ]
    for label, value in rows:
        pct = round(100 * value / top, 1)
        out.append(
            '<div class="bar-row">'
            f'<span class="bar-label" style="min-width:{label_width}">{escape(str(label))}</span>'
            '<span class="bar-track">'
            f'<span class="bar-fill" style="width:{pct}%"></span></span>'
            f'<span class="bar-value">{value}</span>'
            "</div>"
        )
    out.append("</div></figure>")
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
        return (
            f'<figure class="chart cliff-chart"><figcaption>{escape(title)}</figcaption>'
            '<p class="muted">No data.</p></figure>'
        )
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
        grid.append(
            f'<line x1="{padl}" y1="{gy:.1f}" x2="{w - padr}" y2="{gy:.1f}" class="cl-grid"/>'
            f'<text x="{padl - 6}" y="{gy + 3:.1f}" class="cl-ylab" text-anchor="end">{_fmt(gv)}</text>'
        )
    # x labels: first, peak, last
    xlabs = []
    for xv in sorted({xmin, peak_x, xmax}):
        xlabs.append(
            f'<text x="{sx(xv):.1f}" y="{h - 10}" class="cl-xlab" text-anchor="middle">{xv}</text>'
        )
    label = escape(title)
    sub = f'<p class="chart-sub">{escape(subtitle)}</p>' if subtitle else ""
    footnote = f'<figcaption class="chart-note">{escape(note)}</figcaption>' if note else ""
    return (
        f'<figure class="chart cliff-chart"><figcaption>{label}</figcaption>{sub}'
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{label}" class="cl-svg">'
        f"{''.join(grid)}"
        f'<polygon points="{area}" class="cl-area"/>'
        f'<polyline points="{line_pts}" class="cl-line" fill="none"/>'
        f'<circle cx="{sx(peak_x):.1f}" cy="{sy(peak_y):.1f}" r="4" class="cl-peak"/>'
        f'<text x="{sx(peak_x):.1f}" y="{sy(peak_y) - 8:.1f}" class="cl-peaklab" text-anchor="middle">peak {_fmt(peak_y)} ({peak_x})</text>'
        f"{''.join(xlabs)}"
        f"</svg>{footnote}</figure>"
    )


def _money_axis(v: float) -> str:
    return f"{'-' if v < 0 else ''}${_fmt(abs(v))}"


def _money_point(year: int, v: float) -> str:
    return f"FY{year}: ${v:,.0f}"


def _band_of(v: float, bands) -> str | None:
    """The css suffix of the band a value falls in, or 'pass' when it clears every band.

    Bands are the regions a value is in TROUBLE in (for composite scores: below 1.5). Anything
    above them all is the healthy case, which has no band drawn and so needs a name here.
    """
    for lo, hi, suffix, _ in bands or []:
        if lo <= v < hi:
            return suffix
    return "pass" if bands else None


def _band_label(v: float, bands) -> str:
    for lo, hi, _, label in bands or []:
        if lo <= v < hi:
            return label
    return "above every threshold"


def money_lines(title: str, series: list[tuple[str, str, list[tuple]]], **kw) -> str:
    """Compare money series over fiscal years. See series_lines: this is that chart with the
    dollar formatting Form 990 data wants."""
    return series_lines(title, series, **kw)


def series_lines(
    title: str,
    series: list[tuple[str, str, list[tuple]]],
    *,
    subtitle: str = "",
    note: str = "",
    fmt_axis=_money_axis,
    fmt_point=_money_point,
    ymin_fixed: float | None = None,
    ymax_fixed: float | None = None,
    bands: list[tuple[float, float, str, str]] | None = None,
    break_at: tuple[float, str] | None = None,
    empty_msg: str = "Not enough filings to chart.",
    css: str = "fin-chart",
    label_gutter: int = 0,
    x_all_years: bool = False,
    color_by_band: bool = False,
    direct_last: bool = False,
    y_step: float | None = None,
) -> str:
    """Compare value series over years. series: (label, css_suffix, [(year, value)]).

    Two things this does that trend() and line() deliberately do not, both required by Form 990
    data and equally by composite scores:

      * It breaks the line across a missing year instead of joining over it. A school that did
        not file leaves a hole in the record, and a line drawn straight across that hole asserts
        a trend nobody reported. The gap is drawn as a gap and labelled.
      * It scales from a real minimum rather than assuming zero, so a negative value (an
        operating loss, or a composite score below zero, which is the whole point of either
        chart) has somewhere to go. A zero line is drawn whenever the range crosses it, so the
        baseline stays honest.

    ymin_fixed/ymax_fixed pin the y axis to a published domain (composite scores run -1.0 to
    3.0) so one school's chart is comparable to another's rather than being auto-scaled to its
    own data. bands shade named regions: (lo, hi, css_suffix, label).

    The last four arguments all default to off, so a caller that does not ask keeps the plain
    chart. They exist because band labels drawn inside the plot print straight across the data:

      label_gutter   reserve N px of right margin and put the band labels in it, outside the
                     plot, instead of on top of the line.
      x_all_years    label every year, not just the first and last. Two labels on a 17-year
                     axis means no reader can tell which year a point is.
      color_by_band  colour each marker by the band its value falls in, so a reader sees which
                     side of a threshold a year landed on without tracing it to the axis.
      direct_last    print the latest value next to its marker: the one number most readers
                     came for, rather than making them read it off the grid.
    """
    clean = [
        (label, suffix, sorted((int(y), float(v)) for y, v in pts if v is not None))
        for label, suffix, pts in series
    ]
    clean = [s for s in clean if len(s[2]) >= 2]
    if not clean:
        return (
            f'<figure class="chart {css}"><figcaption>{escape(title)}</figcaption>'
            f'<p class="muted">{escape(empty_msg)}</p></figure>'
        )

    w, h, padl, padr, padt, padb = 720, 330, 64, 16 + label_gutter, 16, 46
    all_years = sorted({y for _, _, pts in clean for y, _ in pts})
    all_vals = [v for _, _, pts in clean for _, v in pts]
    xmin, xmax = min(all_years), max(all_years)
    ymax = max(all_vals + [0]) * 1.08 if ymax_fixed is None else ymax_fixed
    if ymin_fixed is not None:
        ymin = ymin_fixed
    else:
        ymin = min(all_vals + [0]) * 1.15 if min(all_vals) < 0 else 0
    yspan = (ymax - ymin) or 1

    def sx(x):
        return padl + (x - xmin) / ((xmax - xmin) or 1) * (w - padl - padr)

    def sy(v):
        return h - padb - ((v - ymin) / yspan) * (h - padt - padb)

    grid = []
    for lo, hi, suffix, blabel in bands or []:
        y_hi, y_lo = sy(min(hi, ymax)), sy(max(lo, ymin))
        if y_lo <= y_hi:
            continue
        grid.append(
            f'<rect x="{padl}" y="{y_hi:.1f}" width="{w - padl - padr}" '
            f'height="{y_lo - y_hi:.1f}" class="band band-{suffix}"><title>{escape(blabel)}</title></rect>'
        )
        if label_gutter:
            # In the gutter, vertically centred on the band, reading left to right off the plot.
            grid.append(
                f'<text x="{w - padr + 8}" y="{(y_hi + y_lo) / 2 + 3.5:.1f}" '
                f'class="band-lab band-lab-{suffix}">{escape(blabel)}</text>'
            )
        else:
            grid.append(
                f'<text x="{w - padr - 4}" y="{y_hi + 12:.1f}" class="band-lab" text-anchor="end">'
                f"{escape(blabel)}</text>"
            )
    # Gridlines. Quartered by default, which is fine for money. y_step puts them on round
    # numbers instead, which matters when a threshold IS the subject: gridlines at 1.1 and 1.8
    # on a chart about clearing 1.0 and 1.5 make the reader do arithmetic to find the only two
    # lines that mean anything.
    if y_step:
        steps, gv = [], ymin
        while gv <= ymax + 1e-9:
            steps.append(gv)
            gv += y_step
    else:
        steps = [ymin + yspan * k / 4 for k in range(5)]
    for gv in steps:
        gy = sy(gv)
        grid.append(
            f'<line x1="{padl}" y1="{gy:.1f}" x2="{w - padr}" y2="{gy:.1f}" class="cl-grid"/>'
            f'<text x="{padl - 6}" y="{gy + 3:.1f}" class="cl-ylab" text-anchor="end">'
            f"{escape(fmt_axis(gv))}</text>"
        )
    if ymin < 0 < ymax:
        grid.append(
            f'<line x1="{padl}" y1="{sy(0):.1f}" x2="{w - padr}" y2="{sy(0):.1f}" class="fin-zero"/>'
        )

    body, legend = [], []
    for label, suffix, pts in clean:
        # Split into runs of consecutive filed years. Each run is its own polyline, so a
        # missing year leaves a visible break rather than an invented straight line. A
        # methodology break splits the line for the same reason: the values either side are
        # not the same measurement, so joining them would draw a trend that does not exist.
        runs, run = [], [pts[0]]
        for prev, cur in zip(pts, pts[1:]):
            crosses_break = break_at is not None and prev[0] < break_at[0] < cur[0]
            if cur[0] - prev[0] == 1 and not crosses_break:
                run.append(cur)
            else:
                runs.append(run)
                run = [cur]
        runs.append(run)
        for r in runs:
            if len(r) >= 2:
                poly = " ".join(f"{sx(y):.1f},{sy(v):.1f}" for y, v in r)
                body.append(
                    f'<polyline points="{poly}" class="fin-line fin-{suffix}" fill="none"/>'
                )
        for y, v in pts:
            zone = _band_of(v, bands) if color_by_band else None
            cls = f"dot-{zone}" if zone else f"fin-{suffix}"
            tip = escape(fmt_point(y, v))
            if zone:
                tip += f" ({escape(_band_label(v, bands))})"
            body.append(
                f'<circle cx="{sx(y):.1f}" cy="{sy(v):.1f}" '
                f'r="{4.0 if color_by_band else 2.6}" class="fin-dot {cls}">'
                f"<title>{tip}</title></circle>"
            )
        if direct_last and pts:
            ly, lv = pts[-1]
            body.append(
                f'<text x="{sx(ly):.1f}" y="{sy(lv) - 11:.1f}" class="direct-lab" '
                f'text-anchor="end">{escape(fmt_axis(lv))}</text>'
            )
        legend.append(
            f'<span class="fin-key"><i class="fin-swatch fin-{suffix}"></i>{escape(label)}</span>'
        )

    if x_all_years:
        # Two-digit ticks for every year, with the full year spelled out at each end so the
        # century is never in doubt. Ticks thin out if the range would crowd them.
        step = 1 if (xmax - xmin) <= 20 else 2
        ticks = [y for y in all_years if (y - xmin) % step == 0]
        xlabs = "".join(
            f'<text x="{sx(y):.1f}" y="{h - 26}" class="cl-xlab" text-anchor="middle">'
            f"{str(y)[2:]}</text>"
            for y in ticks
        )
        xlabs += "".join(
            f'<text x="{sx(y):.1f}" y="{h - 12}" class="cl-xlab-full" text-anchor="middle">'
            f"{y}</text>"
            for y in (xmin, xmax)
        )
    else:
        xlabs = "".join(
            f'<text x="{sx(y):.1f}" y="{h - 26}" class="cl-xlab" text-anchor="middle">{y}</text>'
            for y in (xmin, xmax)
        )
    if break_at is not None and xmin < break_at[0] < xmax:
        bx = sx(break_at[0])
        body.append(
            f'<line x1="{bx:.1f}" y1="{padt}" x2="{bx:.1f}" y2="{h - padb}" class="chart-break"/>'
            f'<text x="{bx:.1f}" y="{h - padb + 13:.1f}" class="chart-breaklab" '
            f'text-anchor="middle">{escape(break_at[1])}</text>'
        )
    gaps = [y for y in range(xmin, xmax + 1) if y not in all_years]
    # Name each hole in the record: an unexplained break reads as a rendering bug. Group the
    # missing years into contiguous runs and label each run separately, because labelling
    # first-to-last across scattered gaps would assert a hole that is not there.
    runs: list[list[int]] = []
    for g in gaps:
        if runs and g - runs[-1][-1] == 1:
            runs[-1].append(g)
        else:
            runs.append([g])
    gap_note = ""
    for run in runs:
        span = f"{run[0]}" if len(run) == 1 else f"{run[0]}-{run[-1]}"
        gap_note += (
            f'<text x="{(sx(run[0] - 1) + sx(run[-1] + 1)) / 2:.1f}" y="{padt + 10}" '
            f'class="fin-gaplab" text-anchor="middle">no data {span}</text>'
        )
        for g in run:
            body.append(
                f'<line x1="{sx(g):.1f}" y1="{padt}" x2="{sx(g):.1f}" y2="{h - padb}" class="fin-gap"/>'
            )

    label_txt = escape(title)
    sub = f'<p class="chart-sub">{escape(subtitle)}</p>' if subtitle else ""
    footnote = f'<figcaption class="chart-note">{escape(note)}</figcaption>' if note else ""
    return (
        f'<figure class="chart {css}"><figcaption>{label_txt}</figcaption>{sub}'
        f'<div class="fin-legend">{"".join(legend)}</div>'
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{label_txt}" class="cl-svg">'
        f"{''.join(grid)}{''.join(body)}{gap_note}{xlabs}"
        f"</svg>{footnote}</figure>"
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
        f"{y}: {v:,}</title></circle>"
        for y, v in pts
    )
    label = escape(title)
    return (
        f'<figure class="chart trend"><figcaption>{label}</figcaption>'
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{label}" class="trend-svg">'
        f'<polyline points="{poly}" class="tr-line" fill="none"/>{dots}'
        f'<text x="{pad}" y="{h - 8}" class="tr-ax">{xmin}</text>'
        f'<text x="{w - pad}" y="{h - 8}" class="tr-ax" text-anchor="end">{xmax}</text>'
        f'<text x="{pad}" y="{pad - 12}" class="tr-ax">peak {ymax:,}</text>'
        f"</svg></figure>"
    )
