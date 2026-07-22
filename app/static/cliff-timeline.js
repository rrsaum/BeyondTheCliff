/* Interactive upgrade for the /cliff timeline overlay.
 *
 * Progressive enhancement: the server renders a static SVG of the default window plus this data as
 * JSON. If this script runs, it reveals the controls and re-renders the chart interactively
 * (duration buttons, one dual-handle range, pointer/touch scrub). If it does not run, the static
 * SVG stays. No framework, no external dependency. Colours live in app.css (class per series), so
 * this file sets no hex.
 */
(function () {
  "use strict";
  var fig = document.getElementById("cliff-timeline");
  if (!fig) return;
  var dataEl = fig.querySelector(".tl-data");
  var data;
  try {
    data = JSON.parse(dataEl.textContent);
  } catch (e) {
    return; // leave the static fallback in place
  }

  var ORDER = data.order,
    SER = data.series,
    YMIN = data.yearMin,
    YMAX = data.yearMax,
    GDPFROM = data.gdpFrom,
    closures = data.closures;

  var FMT = {
    count: function (v) {
      return Math.round(v).toLocaleString();
    },
    people: function (v) {
      return (v / 1e6).toFixed(v >= 1e7 ? 1 : 2) + "M";
    },
    gdp: function (v) {
      return "$" + (v / 1000).toFixed(1) + "T";
    },
  };
  function unit(k, v) {
    return FMT[SER[k].unit](v);
  }
  function interp(pts, yr) {
    if (!pts.length || yr < pts[0][0] || yr > pts[pts.length - 1][0]) return null;
    for (var i = 1; i < pts.length; i++) {
      if (pts[i][0] === yr) return pts[i][1];
      if (pts[i][0] > yr) {
        var x0 = pts[i - 1][0],
          y0 = pts[i - 1][1],
          x1 = pts[i][0],
          y1 = pts[i][1];
        return y0 + ((y1 - y0) * (yr - x0)) / (x1 - x0);
      }
    }
    return pts[0][1];
  }
  function at(pts, yr) {
    for (var i = 0; i < pts.length; i++) if (pts[i][0] === yr) return pts[i][1];
    return null;
  }

  var NS = "http://www.w3.org/2000/svg";
  function EL(n, a) {
    var e = document.createElementNS(NS, n);
    for (var k in a) e.setAttribute(k, a[k]);
    return e;
  }
  function TX(x, y, s, cls, anc) {
    var t = EL("text", { x: x, y: y, class: cls || "" });
    if (anc) t.setAttribute("text-anchor", anc);
    t.textContent = s;
    return t;
  }

  var controls = fig.querySelector(".tl-controls");
  var plot = fig.querySelector(".tl-plot");
  var readout = fig.querySelector(".tl-readout");
  var winlab = fig.querySelector(".tl-winlab");
  var gdpflag = fig.querySelector(".tl-gdpflag");
  var startEl = fig.querySelector(".tl-start");
  var endEl = fig.querySelector(".tl-end");
  var rfill = fig.querySelector(".tl-rfill");

  var OFF = data.defaultOff || [];
  var on = {};
  ORDER.forEach(function (k) {
    on[k] = OFF.indexOf(k) < 0;
  });
  on.cl = true;

  // Max should start where the last of the long NCES series begins (HS graduates, 1870), so no
  // series silently vanishes for lack of a base year. GDP is excluded here: it starts in 1929.
  var MAXSTART = Math.max.apply(
    null,
    ORDER.filter(function (k) {
      return k !== "gdp";
    }).map(function (k) {
      return SER[k].points[0][0];
    }),
  );

  function syncFill() {
    var a = +startEl.value,
      b = +endEl.value;
    rfill.style.left = ((a - YMIN) / (YMAX - YMIN)) * 100 + "%";
    rfill.style.width = ((b - a) / (YMAX - YMIN)) * 100 + "%";
    // when both handles sit in the recent era, keep the start handle grabbable on top
    startEl.style.zIndex = a > (YMIN + YMAX) / 2 ? 5 : 3;
    endEl.style.zIndex = 4;
  }

  function draw() {
    var a = +startEl.value,
      b = +endEl.value;
    if (a > b - 5) {
      a = b - 5;
      startEl.value = a;
    }
    if (winlab) winlab.textContent = a + " to " + b + " (" + (b - a) + " yrs)";
    var gdpOK = a >= GDPFROM;
    if (gdpflag) gdpflag.hidden = !(on.gdp && !gdpOK);

    var active = ORDER.filter(function (k) {
      return on[k] && (k !== "gdp" || gdpOK);
    });
    var W = 960,
      H = 440,
      padL = 46,
      padR = 96,
      padT = 20,
      padB = 34,
      iw = W - padL - padR,
      ih = H - padT - padB;
    var X = function (y) {
      return padL + ((y - a) / (b - a)) * iw;
    };
    var base = {},
      lines = {},
      vlo = 95,
      vhi = 105;
    active.forEach(function (k) {
      var pts = SER[k].points,
        bs = interp(pts, a);
      if (!bs) return;
      base[k] = bs;
      var seq = [[a, 100]];
      pts.forEach(function (d) {
        if (d[0] > a && d[0] < b) seq.push([d[0], (100 * d[1]) / bs]);
      });
      var be = interp(pts, b);
      if (be != null) seq.push([b, (100 * be) / bs]);
      lines[k] = seq;
      seq.forEach(function (p) {
        vlo = Math.min(vlo, p[1]);
        vhi = Math.max(vhi, p[1]);
      });
    });
    var dlo = Math.min(vlo, 100),
      dhi = Math.max(vhi, 100),
      L = Math.log10;
    var loL = L(dlo),
      hiL = L(dhi),
      lpad = Math.max((hiL - loL) * 0.05, 0.03),
      y0L = loL - lpad,
      y1L = hiL + lpad;
    var Y = function (v) {
      return padT + ih - ((L(v) - y0L) / (y1L - y0L)) * ih;
    };

    var svg = EL("svg", {
      viewBox: "0 0 " + W + " " + H,
      class: "cl-svg tl-svg",
      role: "img",
      "aria-label": "Metrics indexed to " + a + ", ratio scale, " + a + " to " + b,
    });
    var cand = [];
    for (var p = 0; p <= 5; p++)
      [1, 1.5, 2, 3, 5, 7].forEach(function (m) {
        cand.push(m * Math.pow(10, p));
      });
    var ticks = cand.filter(function (v) {
      return v >= dlo * 0.985 && v <= dhi * 1.015;
    });
    while (ticks.length > 8)
      ticks = ticks.filter(function (_, i) {
        return i % 2 === 0;
      });
    ticks.forEach(function (v) {
      svg.append(EL("line", { x1: padL, y1: Y(v), x2: padL + iw, y2: Y(v), class: "cl-grid" }));
      svg.append(TX(padL - 6, Y(v) + 3, v >= 1000 ? v / 1000 + "k" : String(v), "cl-ylab", "end"));
    });
    svg.append(EL("line", { x1: padL, y1: Y(100), x2: padL + iw, y2: Y(100), class: "tl-ref" }));
    svg.append(TX(padL - 6, padT - 6, "index, ratio scale (" + a + "=100)", "cl-ylab", "start"));

    var span = b - a,
      tstep = span > 120 ? 25 : span > 60 ? 20 : span > 30 ? 10 : 5,
      t0 = Math.ceil(a / tstep) * tstep;
    for (var y = t0; y <= b; y += tstep)
      svg.append(TX(X(y), H - padB + 16, y, "cl-xlab", "middle"));

    if (on.cl) {
      var inwin = closures.filter(function (r) {
        return r[0] >= a && r[0] <= b;
      });
      if (inwin.length) {
        var cmax = Math.max.apply(
            null,
            inwin.map(function (r) {
              return r[1];
            }),
          ) || 1,
          bh = ih * 0.26,
          bw = Math.max((iw / (b - a)) * 0.7, 1.5);
        inwin.forEach(function (r) {
          var hh = (r[1] / cmax) * bh;
          svg.append(
            EL("rect", { x: X(r[0]) - bw / 2, y: padT + ih - hh, width: bw, height: hh, class: "tl-clbar" }),
          );
        });
        svg.append(TX(padL + 2, padT + ih - 4, "closures/yr (context, own scale)", "tl-cllab", "start"));
      }
    }

    var labelYs = [];
    active.forEach(function (k) {
      var seq = lines[k];
      if (!seq) return;
      var d = "";
      seq.forEach(function (pt, i) {
        d += (i ? "L" : "M") + X(pt[0]).toFixed(1) + " " + Y(pt[1]).toFixed(1);
      });
      svg.append(EL("path", { d: d, fill: "none", class: "tl-halo" }));
      svg.append(EL("path", { d: d, fill: "none", class: "tl-line tl-" + k }));
      var last = seq[seq.length - 1];
      var ly = Y(last[1]) + 3;
      while (
        labelYs.some(function (p) {
          return Math.abs(ly - p) < 12;
        })
      )
        ly += 12; // nudge colliding end-labels apart
      labelYs.push(ly);
      svg.append(TX(padL + iw + 5, ly, SER[k].short || SER[k].label, "tl-lab tl-" + k, "start"));
    });

    (data.annotations || []).forEach(function (anno) {
      var ak = anno.series;
      if (active.indexOf(ak) < 0 || anno.year < a || anno.year > b) return;
      var bs = base[ak];
      if (!bs) return;
      var av = interp(SER[ak].points, anno.year);
      if (av == null) return;
      var ax = X(anno.year),
        ay = Y((100 * av) / bs);
      svg.append(EL("circle", { cx: ax, cy: ay, r: 3.5, class: "tl-anno-dot" }));
      svg.append(TX(ax, ay + 16, anno.label, "tl-anno", "middle"));
    });

    var hl = EL("line", { y1: padT, y2: padT + ih, class: "tl-cross", opacity: 0 });
    svg.append(hl);
    var hit = EL("rect", { x: padL, y: padT, width: iw, height: ih, fill: "transparent", class: "tl-hit" });
    svg.append(hit);
    function move(e) {
      var r = svg.getBoundingClientRect();
      var yr = Math.round(a + (((e.clientX - r.left) / r.width) * W - padL) / iw * (b - a));
      if (yr < a) yr = a;
      if (yr > b) yr = b;
      hl.setAttribute("x1", X(yr));
      hl.setAttribute("x2", X(yr));
      hl.setAttribute("opacity", 1);
      var parts = active
        .map(function (k) {
          var v = interp(SER[k].points, yr);
          if (v == null) return null;
          var ix = Math.round((100 * v) / base[k]);
          return (
            '<span class="tl-fg tl-' + k + '">' + SER[k].label + "</span> " + unit(k, v) +
            ' <span class="tl-mut">(' + ix + ")</span>"
          );
        })
        .filter(Boolean);
      if (on.cl) {
        var c = at(closures, yr);
        if (c != null) parts.push('<span class="tl-fg tl-cl">closures</span> ' + c);
      }
      readout.innerHTML = "<b>" + yr + "</b> " + parts.join(' <span class="tl-mut">&middot;</span> ');
    }
    hit.addEventListener("pointermove", move);
    hit.addEventListener("pointerdown", move);
    hit.addEventListener("pointerleave", function () {
      hl.setAttribute("opacity", 0);
      hint();
    });

    plot.innerHTML = "";
    plot.append(svg);
  }

  function hint() {
    readout.innerHTML =
      '<span class="tl-mut">Hover or tap the chart to read a year’s values.</span>';
  }
  function clearDur() {
    fig.querySelectorAll(".tl-dur").forEach(function (x) {
      x.setAttribute("aria-pressed", "false");
    });
  }

  fig.querySelector(".tl-chips").addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b) return;
    on[b.dataset.k] = !on[b.dataset.k];
    b.setAttribute("aria-pressed", on[b.dataset.k]);
    draw();
  });
  fig.querySelectorAll(".tl-dur").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var n = btn.dataset.n;
      if (n === "max") {
        startEl.value = MAXSTART;
        endEl.value = YMAX;
      } else {
        endEl.value = YMAX;
        startEl.value = YMAX - +n;
      }
      fig.querySelectorAll(".tl-dur").forEach(function (x) {
        x.setAttribute("aria-pressed", x === btn ? "true" : "false");
      });
      syncFill();
      draw();
    });
  });
  startEl.addEventListener("input", function () {
    if (+startEl.value > +endEl.value - 5) startEl.value = +endEl.value - 5;
    clearDur();
    syncFill();
    draw();
  });
  endEl.addEventListener("input", function () {
    if (+endEl.value < +startEl.value + 5) endEl.value = +startEl.value + 5;
    clearDur();
    syncFill();
    draw();
  });

  controls.hidden = false; // reveal the controls now that the upgrade is running
  syncFill();
  draw();
  hint();
})();
