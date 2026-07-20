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


def line(
    title: str,
    points: list[tuple],
    *,
    subtitle: str = "",
    note: str = "",
    markers: list[dict] | None = None,
) -> str:
    """Filled area + line chart of a value over years, with a y axis, x-year labels, and a
    peak marker. points: (year, value). Baseline at zero so the scale is honest.

    markers, when given, are key dates drawn along the BOTTOM as a timeline: each is
    {'year', 'label', 'detail'?} and renders as a faint full-height guide plus a year-and-label
    tag under the axis. They are the likely cause of an inflection in the line, so the tag stays
    small and recessive: three of them read as a timeline, a dozen dashed lines read as noise.
    """
    pts = sorted((int(y), int(v)) for y, v in points if str(v).strip() not in ("", "None"))
    if len(pts) < 2:
        return (
            f'<figure class="chart cliff-chart"><figcaption>{escape(title)}</figcaption>'
            '<p class="muted">No data.</p></figure>'
        )
    marks = [m for m in (markers or []) if pts[0][0] <= int(m["year"]) <= pts[-1][0]]
    w, h, padl, padr, padt, padb = 720, 340, 60, 18, 34, (54 if marks else 30)
    years = [p[0] for p in pts]
    vals = [p[1] for p in pts]
    xmin, xmax, ymax = min(years), max(years), max(vals) * 1.06
    peak_x, peak_y = max(pts, key=lambda p: p[1])
    axis_y = h - padb

    def sx(x):
        return padl + (x - xmin) / ((xmax - xmin) or 1) * (w - padl - padr)

    def sy(v):
        return axis_y - (v / ymax) * (axis_y - padt)

    line_pts = " ".join(f"{sx(y):.1f},{sy(v):.1f}" for y, v in pts)
    area = f"{padl},{axis_y} {line_pts} {sx(xmax):.1f},{axis_y}"
    # y gridlines at ~4 steps
    grid = []
    for k in range(1, 5):
        gv = ymax * k / 4
        gy = sy(gv)
        grid.append(
            f'<line x1="{padl}" y1="{gy:.1f}" x2="{w - padr}" y2="{gy:.1f}" class="cl-grid"/>'
            f'<text x="{padl - 6}" y="{gy + 3:.1f}" class="cl-ylab" text-anchor="end">{_fmt(gv)}</text>'
        )
    # Timeline markers along the bottom: a faint guide up to the curve, and a small tag under
    # the axis (year over a short label) so a reader can tie the inflection to its likely cause.
    # Tags for dates close together (e.g. 1965 and 1972) would overprint, so the second of a
    # too-near pair drops one line lower instead of colliding.
    mark_svg = []
    prev_mx = None
    for m in sorted(marks, key=lambda d: int(d["year"])):
        mx = sx(int(m["year"]))
        drop = prev_mx is not None and (mx - prev_mx) < 62
        yr_y = axis_y + (28 if drop else 14)
        prev_mx = mx
        mark_svg.append(
            f'<line x1="{mx:.1f}" y1="{padt}" x2="{mx:.1f}" y2="{axis_y:.1f}" class="cl-mark"/>'
            f'<text x="{mx:.1f}" y="{yr_y:.1f}" class="cl-mark-yr" text-anchor="middle">{int(m["year"])}</text>'
            f'<text x="{mx:.1f}" y="{yr_y + 10:.1f}" class="cl-mark-lab" text-anchor="middle">{escape(m["label"])}</text>'
        )
    if marks:
        # With a bottom timeline, the markers carry the interior; just label the two endpoints.
        xlabs = [
            f'<text x="{sx(xmin):.1f}" y="{h - 4}" class="cl-xlab" text-anchor="start">{xmin}</text>',
            f'<text x="{sx(xmax):.1f}" y="{h - 4}" class="cl-xlab" text-anchor="end">{xmax}</text>',
        ]
    else:
        # Proportional decade axis: a tick every decade, a label every `step` years, so time reads
        # evenly across the span instead of only at the ends. A decade label within `step` years of
        # an endpoint is dropped so it cannot overprint the always-drawn endpoint label.
        step = 20 if (xmax - xmin) > 80 else 10
        parts = []
        for yr in range((xmin // 10 + 1) * 10, xmax, 10):
            tx = sx(yr)
            parts.append(
                f'<line x1="{tx:.1f}" y1="{h - padb:.1f}" x2="{tx:.1f}" '
                f'y2="{h - padb + 4:.1f}" class="cl-dtick"/>'
            )
            if yr % step == 0 and abs(yr - xmin) >= step / 2 and abs(yr - xmax) >= step / 2:
                parts.append(
                    f'<text x="{tx:.1f}" y="{h - 10}" class="cl-xlab" '
                    f'text-anchor="middle">{yr}</text>'
                )
        parts.append(
            f'<text x="{sx(xmin):.1f}" y="{h - 10}" class="cl-xlab" text-anchor="start">{xmin}</text>'
        )
        parts.append(
            f'<text x="{sx(xmax):.1f}" y="{h - 10}" class="cl-xlab" text-anchor="end">{xmax}</text>'
        )
        xlabs = parts
    label = escape(title)
    sub = f'<p class="chart-sub">{escape(subtitle)}</p>' if subtitle else ""
    footnote = f'<figcaption class="chart-note">{escape(note)}</figcaption>' if note else ""
    return (
        f'<figure class="chart cliff-chart"><figcaption>{label}</figcaption>{sub}'
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{label}" class="cl-svg">'
        f"{''.join(grid)}{''.join(mark_svg)}"
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


def _declutter(items: list[tuple[float, object]], gap: float, floor: float) -> list[tuple]:
    """Space labels so none overlap: sort, push down while closer than gap, push overflow up.

    gap is the HEIGHT OF A LABEL, not a gap between anchor points. Spacing the anchors by less
    than the label's own height still overlaps, because a two-line label occupies the space
    under its own anchor: measure the box, not the point.
    """
    out = sorted(items, key=lambda t: t[0])
    for i in range(1, len(out)):
        if out[i][0] - out[i - 1][0] < gap:
            out[i] = (out[i - 1][0] + gap, out[i][1])
    over = out[-1][0] - floor
    if over > 0:
        for i in range(len(out) - 1, -1, -1):
            out[i] = (out[i][0] - over, out[i][1])
            if i and out[i][0] - out[i - 1][0] >= gap:
                break
    return out


def stacked_money(
    title: str,
    bands: list[tuple[str, str, dict]],
    line: tuple[str, str, dict],
    *,
    years: list[int],
    subtitle: str = "",
    note: str = "",
    ymax: float | None = None,
) -> str:
    """Revenue by source (stacked bands) against a spending line, over fiscal years.

    bands: [(css_suffix, label, {year: value})] bottom-up. line: (css_suffix, label, {year: v}).

    Chosen from mockups over a plain two-line gap chart and a coverage ratio. Four decisions in
    here are load-bearing and were each made because the alternative failed a check:

      * Bands must sum to the line's own total for the stack to mean anything. The caller owns
        that; app/queries.py:financial_series builds bands that reconcile exactly.
      * A 2px surface-coloured separator between bands, or the eye reads two bands as one shape.
      * The line is drawn twice, a surface-coloured halo under the real stroke, because for most
        years it sits within a hair of the stack top and vanishes into that edge otherwise.
      * A result strip under the axis states surplus or deficit per year outright. It is the
        question the chart exists to answer, and it is exactly the question the line-against-
        stack-edge geometry answers worst.
    """
    if len(years) < 2:
        return (
            f'<figure class="chart fin-chart"><figcaption>{escape(title)}</figcaption>'
            '<p class="muted">Not enough filings to chart.</p></figure>'
        )
    w, h = 980, 360
    padl, padr, padt, padb = 64, 208, 24, 66
    top_total = {y: sum((b[2].get(y) or 0) for b in bands) for y in years}
    hi = ymax or max(list(top_total.values()) + [line[2].get(y) or 0 for y in years]) * 1.08

    def sx(x):
        return padl + (x - years[0]) / ((years[-1] - years[0]) or 1) * (w - padl - padr)

    def sy(v):
        return h - padb - (v / hi) * (h - padt - padb)

    # Runs of consecutive filed years: a year nobody filed is a hole, not a straight line.
    runs, run = [], [years[0]]
    for a, b in zip(years, years[1:]):
        if b - a == 1:
            run.append(b)
        else:
            runs.append(run)
            run = [b]
    runs.append(run)

    out = []
    for k in range(5):
        gv = hi * k / 4
        out.append(
            f'<line x1="{padl}" y1="{sy(gv):.1f}" x2="{w - padr}" y2="{sy(gv):.1f}" class="cl-grid"/>'
            f'<text x="{padl - 8}" y="{sy(gv) + 3.5:.1f}" class="cl-ylab" text-anchor="end">'
            f"${gv / 1e6:.0f}M</text>"
        )
    base = {y: 0.0 for y in years}
    for css, _lab, vals in bands:
        for r in runs:
            pts = [(y, base[y] + (vals.get(y) or 0)) for y in r] + [
                (y, base[y]) for y in reversed(r)
            ]
            out.append(
                f'<polygon points="{" ".join(f"{sx(y):.1f},{sy(v):.1f}" for y, v in pts)}" '
                f'class="area area-{css}"/>'
            )
        for y in years:
            base[y] += vals.get(y) or 0
    run_top = {y: 0.0 for y in years}
    for css, _lab, vals in bands[:-1]:
        for y in years:
            run_top[y] += vals.get(y) or 0
        for r in runs:
            out.append(
                f'<polyline points="{" ".join(f"{sx(y):.1f},{sy(run_top[y]):.1f}" for y in r)}" '
                f'class="area-sep"/>'
            )
    lcss, llab, lvals = line
    for r in runs:
        pts = " ".join(f"{sx(y):.1f},{sy(lvals.get(y) or 0):.1f}" for y in r)
        out.append(f'<polyline points="{pts}" class="ln-halo"/>')
        out.append(f'<polyline points="{pts}" class="fin-line fin-{lcss}"/>')
    for y in years:
        out.append(
            f'<circle cx="{sx(y):.1f}" cy="{sy(lvals.get(y) or 0):.1f}" r="3.4" '
            f'class="fin-dot fin-{lcss}"/>'
        )

    ly = years[-1]
    total = top_total[ly] or 1
    items = [(sy(lvals.get(ly) or 0), (lcss, llab, lvals.get(ly) or 0, None))]
    prev = 0.0
    for css, lab, vals in bands:
        v = vals.get(ly) or 0
        items.append((sy(prev + v / 2), (css, lab, v, v / total)))
        prev += v
    for (ypos, (css, lab, val, share)), (anchor, _) in zip(
        _declutter(items, 26.0, h - padb), sorted(items, key=lambda t: t[0])
    ):
        if abs(ypos - anchor) > 4:
            # A label pushed off its band points at the wrong band without a leader.
            out.append(
                f'<path d="M {w - padr + 1} {anchor:.1f} H {w - padr + 5} V {ypos - 3.5:.1f} '
                f'H {w - padr + 8}" class="leader leader-{css}"/>'
            )
        sub = f"${val / 1e6:.1f}M" + (
            f" · {share * 100:.0f}% of revenue" if share is not None else ""
        )
        out.append(
            f'<text x="{w - padr + 10}" y="{ypos:.1f}" class="gut gut-{css}">{escape(lab)}</text>'
            f'<text x="{w - padr + 10}" y="{ypos + 12:.1f}" class="gutsub">{escape(sub)}</text>'
        )

    sty = h - padb + 30
    out.append(
        f'<text x="{sx(years[0]) - 22:.1f}" y="{sty + 7.5:.1f}" class="striplab" '
        f'text-anchor="end">Result</text>'
    )
    for y in years:
        res = (top_total[y] or 0) - (lvals.get(y) or 0)
        word = "surplus" if res >= 0 else "deficit"
        out.append(
            f'<rect x="{sx(y) - 15:.1f}" y="{sty:.1f}" width="30" height="9" rx="2" '
            f'class="chip chip-{word}"><title>FY{y}: {word} ${abs(res) / 1e6:.1f}M</title></rect>'
        )
    for y in years:
        out.append(
            f'<text x="{sx(y):.1f}" y="{h - padb + 16:.1f}" class="cl-xlab" text-anchor="middle">'
            f"{str(y)[2:]}</text>"
        )
    for y in (years[0], years[-1]):
        out.append(
            f'<text x="{sx(y):.1f}" y="{h - padb + 58:.1f}" class="cl-xlab-full" '
            f'text-anchor="middle">FY{y}</text>'
        )
    wd = (w - padl - padr) / len(years) * 0.9
    for y in years:
        res = (top_total[y] or 0) - (lvals.get(y) or 0)
        rows = [f"FY{y}"] + [f"{lab} ${(v.get(y) or 0) / 1e6:.1f}M" for _c, lab, v in bands]
        rows += [
            f"Total revenue ${(top_total[y] or 0) / 1e6:.1f}M",
            f"{llab} ${(lvals.get(y) or 0) / 1e6:.1f}M",
            f"{'Surplus' if res >= 0 else 'Deficit'} ${abs(res) / 1e6:.1f}M",
        ]
        out.append(
            f'<rect x="{sx(y) - wd / 2:.1f}" y="{padt}" width="{wd:.1f}" height="{h - padb - padt:.1f}" '
            f'class="hit"><title>{escape(chr(10).join(rows))}</title></rect>'
        )

    legend = (
        "".join(
            f'<span class="fin-key"><i class="fin-swatch sw-{css}"></i>{escape(lab)}</span>'
            for css, lab, _v in bands
        )
        + f'<span class="fin-key"><i class="fin-swatch sw-line sw-{lcss}"></i>{escape(llab)}</span>'
    )
    sub_html = f'<p class="chart-sub">{escape(subtitle)}</p>' if subtitle else ""
    note_html = f'<figcaption class="chart-note">{escape(note)}</figcaption>' if note else ""
    return (
        f'<figure class="chart fin-chart"><figcaption>{escape(title)}</figcaption>{sub_html}'
        f'<div class="fin-legend">{legend}</div>'
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}" class="cl-svg">'
        f"{''.join(out)}</svg>{note_html}</figure>"
    )


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


def small_multiples(
    title: str,
    panels: list[tuple[str, str, list[tuple]]],
    *,
    subtitle: str = "",
    note: str = "",
    ylo: float,
    yhi: float,
    ticks: list[float],
    fmt_axis,
    fmt_value,
    css: str = "sm-chart",
) -> str:
    """One frame repeated per category, same scale, one hue. panels: (label, sublabel, points).

    Why this and not three coloured lines on one chart: the brand's three series colours fail
    the palette check outright (the two closest sit dE 5.1 apart on a floor of 15), and the rule
    for a hard normal-vision failure is to cut series or facet, not to lean on labels to rescue
    an unreadable palette. Faceting removes the problem rather than mitigating it: with one
    series per frame, hue carries no meaning at all and the panel label is the only identity.

    Every panel shares ylo/yhi so the frames are honestly comparable, which is the whole point
    of a small multiple: the eye compares shape against a fixed frame, not against a legend.
    """
    if not panels:
        return (
            f'<figure class="chart {css}"><figcaption>{escape(title)}</figcaption>'
            '<p class="muted">No data.</p></figure>'
        )
    w, h, padl, padr, padt, padb = 700, 132, 54, 92, 12, 24
    years = [y for _, _, pts in panels for y, _ in pts]
    xmin, xmax = min(years), max(years)

    def sx(x):
        return padl + (x - xmin) / ((xmax - xmin) or 1) * (w - padl - padr)

    def sy(v):
        return h - padb - ((v - ylo) / ((yhi - ylo) or 1)) * (h - padt - padb)

    out = [f'<figure class="chart {css}"><figcaption>{escape(title)}</figcaption>']
    if subtitle:
        out.append(f'<p class="chart-sub">{escape(subtitle)}</p>')
    for label, sub, pts in panels:
        pts = sorted(pts)
        grid = "".join(
            f'<line x1="{padl}" y1="{sy(t):.1f}" x2="{w - padr}" y2="{sy(t):.1f}" class="cl-grid"/>'
            f'<text x="{padl - 8}" y="{sy(t) + 3.5:.1f}" class="cl-ylab" text-anchor="end">'
            f"{escape(fmt_axis(t))}</text>"
            for t in ticks
        )
        poly = " ".join(f"{sx(y):.1f},{sy(v):.1f}" for y, v in pts)
        area = f"{sx(xmin):.1f},{sy(ylo):.1f} {poly} {sx(xmax):.1f},{sy(ylo):.1f}"
        # A dot per year, each its own hover/focus target. The callout is CSS only, so it works
        # in a server-rendered page with no script; the table under the chart is the
        # non-hover route to the same numbers, because a tooltip may enhance access, never gate it.
        marks = []
        for yr, v in pts:
            cx, cy = sx(yr), sy(v)
            tw, th, gap = 78, 34, 10
            tx = min(max(cx - tw / 2, 2), w - tw)
            # Flip the callout below the dot when it would clip the top of the frame. The peak
            # dot sits at padt, and a callout drawn above it lands at a negative y, outside the
            # card, which is the clipping in the screenshot. Below the dot, the same callout is
            # always inside. ty is the rect top; text baselines are offset from it either way.
            above = cy - th - gap >= padt
            ty = cy - th - gap if above else cy + gap
            marks.append(
                f'<g class="sm-pt" tabindex="0" role="img" '
                f'aria-label="{yr}: {escape(fmt_value(v))}">'
                f'<circle class="hit" cx="{cx:.1f}" cy="{cy:.1f}" r="11"/>'
                f'<circle class="sm-dot" cx="{cx:.1f}" cy="{cy:.1f}" r="3.2"/>'
                f'<g class="sm-tip"><rect x="{tx:.1f}" y="{ty:.1f}" width="{tw}" '
                f'height="{th}" rx="4"/>'
                f'<text x="{tx + tw / 2:.1f}" y="{ty + 15:.1f}" class="sm-tv" '
                f'text-anchor="middle">{escape(fmt_value(v))}</text>'
                f'<text x="{tx + tw / 2:.1f}" y="{ty + 27:.1f}" class="sm-tl" '
                f'text-anchor="middle">{yr}</text></g></g>'
            )
        out.append(
            f'<div class="sm-pan"><div class="sm-h"><span class="sm-name">{escape(label)}</span>'
            f'<span class="sm-d">{escape(sub)}</span></div>'
            f'<svg viewBox="0 0 {w} {h}" class="cl-svg" role="img" '
            f'aria-label="{escape(label)}: {escape(sub)}">{grid}'
            f'<polygon points="{area}" class="sm-area"/>'
            f'<polyline points="{poly}" class="sm-line" fill="none"/>'
            f'<text x="{sx(xmax) + 8:.1f}" y="{sy(pts[-1][1]) + 4:.1f}" class="sm-end">'
            f"{escape(fmt_value(pts[-1][1]))}</text>{''.join(marks)}"
            f'<text x="{padl}" y="{h - 6}" class="cl-xlab">{xmin}</text>'
            f'<text x="{sx(xmax):.1f}" y="{h - 6}" class="cl-xlab" text-anchor="middle">{xmax}</text>'
            f"</svg></div>"
        )
    if note:
        out.append(f'<figcaption class="chart-note">{escape(note)}</figcaption>')
    out.append("</figure>")
    return "".join(out)


def enrollment_evolution(
    title: str,
    points: list[tuple],
    *,
    terminal: bool = False,
    subtitle: str = "",
    note: str = "",
) -> str:
    """Enrollment as one readable trajectory: a solid line across consecutive sourced years and a
    dashed line interpolating across the gaps we have not sourced, dots at every measured year, the
    peak in the warn colour and (for a closed school) the final point in the closed colour. Trend
    over time wants a line; the dashed segments keep it honest about which years are interpolated.

    points: (year, headcount). terminal marks the last point as the closure. Lifecycle events are
    NOT drawn here: they live in the timeline, so each fact appears once."""
    pts = sorted((int(y), int(v)) for y, v in points if str(v).strip() not in ("", "None"))
    if len(pts) < 2:
        return ""
    w, h, padl, padr, padt, padb = 940, 300, 56, 20, 40, 44
    axis_y = h - padb
    years, vals = [p[0] for p in pts], [p[1] for p in pts]
    xmin = (min(years) // 10) * 10
    xmax = -(-max(years) // 10) * 10  # ceil to the next decade
    if xmax <= xmin:
        xmax = xmin + 10
    ymax = max(vals) * 1.08
    gstep = next(
        (c for c in (10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000) if ymax / c <= 5), 10000
    )

    def sx(x):
        return padl + (x - xmin) / (xmax - xmin) * (w - padl - padr)

    def sy(v):
        return axis_y - (v / ymax) * (axis_y - padt)

    out = [
        f'<text x="{padl}" y="{padt - 16}" class="ev-axtitle">Enrollment (sourced headcount)</text>'
    ]
    g = 0
    while g < ymax:
        gy = sy(g)
        out.append(
            f'<line x1="{padl}" y1="{gy:.1f}" x2="{w - padr}" y2="{gy:.1f}" class="cl-grid"/>'
            f'<text x="{padl - 6}" y="{gy + 3:.1f}" class="cl-ylab" text-anchor="end">{g}</text>'
        )
        g += gstep
    # Full dashed trajectory (interpolates across gaps), then solid over consecutive-year runs.
    out.append(
        f'<polyline points="{" ".join(f"{sx(y):.1f},{sy(v):.1f}" for y, v in pts)}" class="ev-gapline"/>'
    )
    runs, run = [], [pts[0]]
    for a, b in zip(pts, pts[1:]):
        if b[0] - a[0] == 1:
            run.append(b)
        else:
            runs.append(run)
            run = [b]
    runs.append(run)
    for r in runs:
        if len(r) >= 2:
            out.append(
                f'<polyline points="{" ".join(f"{sx(y):.1f},{sy(v):.1f}" for y, v in r)}" class="ev-line"/>'
            )
    peak, last = max(pts, key=lambda p: p[1]), pts[-1]
    for y, v in pts:
        if (y, v) == peak:
            cls, rad = "ev-peak", 5
        elif (y, v) == last and terminal:
            cls, rad = "ev-dot-last", 5
        else:
            cls, rad = "ev-dot", 3.6
        out.append(
            f'<circle cx="{sx(y):.1f}" cy="{sy(v):.1f}" r="{rad}" class="{cls}"><title>{y}: {v:,}</title></circle>'
        )
    out.append(
        f'<text x="{sx(pts[0][0]):.1f}" y="{sy(pts[0][1]) - 8:.1f}" class="ev-lab" text-anchor="middle">'
        f"{pts[0][1]:,} ({pts[0][0]})</text>"
    )
    out.append(
        f'<text x="{sx(peak[0]):.1f}" y="{sy(peak[1]) - 8:.1f}" class="ev-peaklab" text-anchor="middle">'
        f"peak {peak[1]:,} ({peak[0]})</text>"
    )
    lx = sx(last[0])
    lab = f"{last[1]:,} at close ({last[0]})" if terminal else f"{last[1]:,} ({last[0]})"
    out.append(
        f'<text x="{min(lx, w - padr - 4):.1f}" y="{sy(last[1]) - 8:.1f}" class="ev-lab" '
        f'text-anchor="{"end" if lx > w - 90 else "middle"}">{lab}</text>'
    )
    tickstep = 20 if (xmax - xmin) > 60 else 10
    t = xmin
    while t <= xmax:
        tx = sx(t)
        out.append(
            f'<line x1="{tx:.1f}" y1="{axis_y}" x2="{tx:.1f}" y2="{axis_y + 5}" class="ev-tick"/>'
            f'<text x="{tx:.1f}" y="{axis_y + 20}" class="cl-xlab" text-anchor="middle">{t}</text>'
        )
        t += tickstep
    label = escape(title)
    sub = f'<p class="chart-sub">{escape(subtitle)}</p>' if subtitle else ""
    foot = f'<figcaption class="chart-note">{escape(note)}</figcaption>' if note else ""
    return (
        f'<figure class="chart evolution"><figcaption>{label}</figcaption>{sub}'
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{label}" class="cl-svg">{"".join(out)}</svg>{foot}</figure>'
    )


def anatomy(struct: dict | None, *, note: str = "") -> str:
    """The 'Anatomy of the closure' panel from queries.closure_anatomy. Accessible HTML bars, no
    script; the readings and the sign/colour are computed in queries.py, this only lays them out."""
    if not struct:
        return ""
    layers = []
    for layer in struct["layers"]:
        rows = []
        for b in layer["bars"]:
            if b["tone"] == "na":
                rows.append(
                    f'<div class="an-row"><span class="an-lab">{escape(b["label"])}</span>'
                    f'<span class="an-na">{escape(b["display"])}</span></div>'
                )
            else:
                amt_cls = " an-amt-crit" if b.get("amt_crit") else ""
                rows.append(
                    f'<div class="an-row"><span class="an-lab">{escape(b["label"])}</span>'
                    f'<span class="an-track"><span class="an-bar an-{b["tone"]}" '
                    f'style="width:{b["pct"]}%"></span></span>'
                    f'<span class="an-amt{amt_cls}">{escape(b["display"])}</span></div>'
                )
        layers.append(
            f'<div class="an-layer"><h3>{layer["n"]} &middot; {escape(layer["title"])}</h3>'
            f'<p class="an-q">{escape(layer["question"])}</p>{"".join(rows)}'
            f'<p class="an-verdict">{escape(layer["verdict"])}</p></div>'
        )
    toll = "".join(
        f"<div><b>{escape(t['value'])}</b>{escape(t['label'])}</div>" for t in struct["toll"]
    )
    toll_html = f'<div class="an-toll">{toll}</div>' if toll else ""
    footnote = f'<figcaption class="chart-note">{escape(note)}</figcaption>' if note else ""
    return (
        '<figure class="chart anatomy">'
        '<p class="chart-sub">The three questions every closure answers: could it make payroll, '
        "did it owe more than it held, and could it be saved.</p>"
        f'<div class="an-diag">{"".join(layers)}</div>{toll_html}{footnote}</figure>'
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
