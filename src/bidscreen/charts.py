"""Charts as plain SVG strings. No plotting library, no JavaScript needed.

Colours are CSS custom properties (``var(--viz-...)``), so one chart serves two
purposes. Inlined in the HTML report it follows the page's light or dark
theme. Written to a file with ``standalone`` the variables are replaced by the
literal colours of one theme, for use as an image in a README.

Marks that respond to hover carry ``data-v`` (the value) and ``data-l`` (what
it is). The report page turns those into a tooltip. Every chart also has a
table next to it, so nothing can only be read by hovering.
"""

from __future__ import annotations

import html
import math
import re
from collections.abc import Sequence

FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

# Palette from a validated default set: slots 1 and 2 pass the colour-vision
# separation and contrast checks on both surfaces.
THEMES = {
    "light": {
        "surface": "#fcfcfb",
        "ink": "#0b0b0b",
        "ink-2": "#52514e",
        "muted": "#6b6a65",
        "grid": "#e1e0d9",
        "axis": "#c3c2b7",
        "series-1": "#2a78d6",
        "series-2": "#eb6834",
        "context": "#a3a29a",
    },
    "dark": {
        "surface": "#1a1a19",
        "ink": "#f0efec",
        "ink-2": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "axis": "#383835",
        "series-1": "#3987e5",
        "series-2": "#d95926",
        "context": "#6f6e69",
    },
}

# Class rules shared by the report page and by standalone files.
VIZ_CSS = f"""
.viz text {{ font-family: {FONT}; }}
.viz-title {{ fill: var(--viz-ink); font-size: 14px; font-weight: 600; }}
.viz-label {{ fill: var(--viz-ink-2); font-size: 12px; }}
.viz-value {{ fill: var(--viz-ink); font-size: 12px; font-weight: 600; }}
.viz-tick {{ fill: var(--viz-muted); font-size: 11px; font-variant-numeric: tabular-nums; }}
.viz-note {{ fill: var(--viz-ink-2); font-size: 11px; }}
.viz-grid {{ stroke: var(--viz-grid); stroke-width: 1; }}
.viz-axis {{ stroke: var(--viz-axis); stroke-width: 1; }}
.viz-ref {{ stroke: var(--viz-muted); stroke-width: 1; }}
.viz-s1 {{ fill: var(--viz-series-1); }}
.viz-s1-line {{ stroke: var(--viz-series-1); stroke-width: 2; stroke-linecap: round; fill: none; }}
.viz-context {{ fill: var(--viz-context); }}
.viz-context-line {{ stroke: var(--viz-context); stroke-width: 1; fill: none; }}
.viz-whisker {{ stroke: var(--viz-context); stroke-width: 2; stroke-linecap: round; }}
.viz-ring {{ stroke: var(--viz-surface); stroke-width: 2; }}
.viz-hit {{ fill: transparent; stroke: none; cursor: default; outline: none; }}
.viz-hit:hover + .viz-mark, .viz-hit:focus-visible + .viz-mark {{ filter: brightness(1.18); }}
"""


def _esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def _fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def _svg(width: int, height: int, body: str, title: str, desc: str) -> str:
    return (
        f'<svg class="viz" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="group" aria-label="{_esc(title)}">'
        f"<desc>{_esc(desc)}</desc>{body}</svg>"
    )


def _hit(shape: str, value: str, label: str, focusable: bool = False) -> str:
    """A transparent target that carries the tooltip text for the next mark."""
    tab = ' tabindex="0"' if focusable else ""
    name = _esc(f"{label}: {value}")
    return (
        f'<{shape} class="viz-hit" role="img" aria-label="{name}" '
        f'data-v="{_esc(value)}" data-l="{_esc(label)}"{tab}/>'
    )


def standalone(svg: str, theme: str = "light") -> str:
    """Resolve the colour variables for one theme and paint a background, so
    the chart can be saved as a self-contained image file."""
    colours = THEMES[theme]
    size = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
    width, height = size.group(1), size.group(2)
    css = re.sub(r"var\(--viz-([a-z0-9-]+)\)", lambda m: colours[m.group(1)], VIZ_CSS)
    background = f'<rect width="{width}" height="{height}" rx="8" fill="{colours["surface"]}"/>'
    head, rest = svg.split("</desc>", 1)
    return f"{head}</desc><style>{css}</style>{background}{rest}\n"


def _nice_step(span: float, target: int = 5) -> float:
    if span <= 0:
        return 1.0
    raw = span / target
    power = 10 ** math.floor(math.log10(raw))
    for multiple in (1, 2, 2.5, 5, 10):
        if raw <= multiple * power:
            return multiple * power
    return 10 * power


# --------------------------------------------------------------------------
# Dot and whisker: one value with an interval per row, against a reference
# --------------------------------------------------------------------------


def dot_whisker(
    rows: Sequence[dict],
    *,
    title: str,
    desc: str,
    x_min: float = 0.3,
    x_max: float = 1.0,
    reference: float | None = 0.5,
    reference_label: str = "coin toss",
    x_label: str = "",
    width: int = 940,
) -> str:
    """Rows are dicts with ``label``, ``value``, ``low``, ``high`` and an
    optional ``note`` shown under the label."""
    left, right, top, row_h = 278, 56, 34, 40
    plot_w = width - left - right
    height = top + row_h * len(rows) + 46

    def x(value: float) -> float:
        clamped = min(max(value, x_min), x_max)
        return left + (clamped - x_min) / (x_max - x_min) * plot_w

    parts = []
    bottom = top + row_h * len(rows)
    tick = x_min
    while tick <= x_max + 1e-9:
        parts.append(
            f'<line class="viz-grid" x1="{x(tick):.1f}" y1="{top}" x2="{x(tick):.1f}" y2="{bottom}"/>'
            f'<text class="viz-tick" x="{x(tick):.1f}" y="{bottom + 16}" text-anchor="middle">'
            f"{_fmt(tick, 1)}</text>"
        )
        tick += 0.1
    if reference is not None:
        parts.append(
            f'<line class="viz-ref" x1="{x(reference):.1f}" y1="{top - 6}" '
            f'x2="{x(reference):.1f}" y2="{bottom}"/>'
            f'<text class="viz-note" x="{x(reference):.1f}" y="{top - 12}" text-anchor="middle">'
            f"{_esc(reference_label)}</text>"
        )
    if x_label:
        parts.append(
            f'<text class="viz-label" x="{left + plot_w / 2:.1f}" y="{bottom + 36}" '
            f'text-anchor="middle">{_esc(x_label)}</text>'
        )

    for i, row in enumerate(rows):
        cy = top + row_h * i + row_h / 2
        label_y = cy + 4 if not row.get("note") else cy - 2
        parts.append(
            f'<text class="viz-label" x="{left - 14}" y="{label_y:.1f}" text-anchor="end">'
            f"{_esc(row['label'])}</text>"
        )
        if row.get("note"):
            parts.append(
                f'<text class="viz-tick" x="{left - 14}" y="{cy + 12:.1f}" text-anchor="end">'
                f"{_esc(row['note'])}</text>"
            )
        value, low, high = row["value"], row["low"], row["high"]
        if not math.isfinite(value):
            continue
        if math.isfinite(low) and math.isfinite(high):
            parts.append(
                f'<line class="viz-whisker" x1="{x(low):.1f}" y1="{cy}" x2="{x(high):.1f}" y2="{cy}"/>'
            )
        tip = f"{_fmt(value)} (95% interval {_fmt(low)} to {_fmt(high)})"
        parts.append(
            _hit(
                f'rect x="{left}" y="{cy - row_h / 2:.1f}" width="{plot_w}" height="{row_h}"',
                tip,
                row["label"],
                focusable=True,
            )
            + f'<circle class="viz-mark viz-s1 viz-ring" cx="{x(value):.1f}" cy="{cy}" r="6"/>'
        )
        end = x(high) if math.isfinite(high) else x(value)
        parts.append(
            f'<text class="viz-value" x="{end + 10:.1f}" y="{cy + 4:.1f}">{_fmt(value)}</text>'
        )
    return _svg(width, height, "".join(parts), title, desc)


# --------------------------------------------------------------------------
# Histogram
# --------------------------------------------------------------------------


def histogram(
    edges: Sequence[float],
    counts: Sequence[int],
    *,
    title: str,
    desc: str,
    x_label: str,
    y_label: str,
    annotations: Sequence[dict] = (),
    unit: str = "awards",
    x_tick_step: float = 0.1,
    width: int = 940,
    height: int = 340,
) -> str:
    """``annotations`` are dicts with ``x`` (a data value), ``text`` and
    ``anchor`` ("start" or "end"): a short note tied to one bar."""
    left, right, top, bottom = 56, 20, 58, 50
    plot_w, plot_h = width - left - right, height - top - bottom
    x_min, x_max = edges[0], edges[-1]
    y_max = max(max(counts), 1)
    step = _nice_step(y_max)
    y_top = math.ceil(y_max / step) * step

    def x(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_w

    def y(value: float) -> float:
        return top + plot_h - value / y_top * plot_h

    parts = []
    tick = 0.0
    while tick <= y_top + 1e-9:
        parts.append(
            f'<line class="viz-grid" x1="{left}" y1="{y(tick):.1f}" x2="{left + plot_w}" '
            f'y2="{y(tick):.1f}"/>'
            f'<text class="viz-tick" x="{left - 8}" y="{y(tick) + 4:.1f}" text-anchor="end">'
            f"{int(tick):,}</text>"
        )
        tick += step

    for lo, hi, count in zip(edges[:-1], edges[1:], counts, strict=True):
        if count <= 0:
            continue
        slot = x(hi) - x(lo)
        bar_w = max(min(slot - 2, 24), 1)
        bx = x(lo) + (slot - bar_w) / 2
        by, bh = y(count), y(0) - y(count)
        r = min(4, bar_w / 2, bh)
        path = (
            f"M{bx:.1f},{by + bh:.1f} L{bx:.1f},{by + r:.1f} Q{bx:.1f},{by:.1f} {bx + r:.1f},{by:.1f} "
            f"L{bx + bar_w - r:.1f},{by:.1f} Q{bx + bar_w:.1f},{by:.1f} {bx + bar_w:.1f},{by + r:.1f} "
            f"L{bx + bar_w:.1f},{by + bh:.1f} Z"
        )
        parts.append(
            _hit(
                f'rect x="{x(lo):.1f}" y="{top}" width="{slot:.1f}" height="{plot_h}"',
                f"{count:,} {unit}",
                f"{_fmt(lo, 3)} to {_fmt(hi, 3)}",
            )
            + f'<path class="viz-mark viz-s1" d="{path}"/>'
        )

    parts.append(
        f'<line class="viz-axis" x1="{left}" y1="{y(0):.1f}" x2="{left + plot_w}" y2="{y(0):.1f}"/>'
    )
    tick = math.ceil(x_min / x_tick_step - 1e-9) * x_tick_step
    while tick <= x_max + 1e-9:
        parts.append(
            f'<text class="viz-tick" x="{x(tick):.1f}" y="{y(0) + 16:.1f}" text-anchor="middle">'
            f"{_fmt(tick)}</text>"
        )
        tick += x_tick_step
    parts.append(
        f'<text class="viz-label" x="{left + plot_w / 2:.1f}" y="{height - 10}" '
        f'text-anchor="middle">{_esc(x_label)}</text>'
        f'<text class="viz-label" x="{left - 44}" y="{top - 14}">{_esc(y_label)}</text>'
    )

    for i, note in enumerate(annotations):
        index = max(0, min(len(counts) - 1, _bin_index(edges, note["x"])))
        cx = (x(edges[index]) + x(edges[index + 1])) / 2
        tip_y = y(counts[index]) - 4
        text_y = top - 30 + 16 * (i % 2)
        anchor = note.get("anchor", "start")
        text_x = cx + (6 if anchor == "start" else -6)
        parts.append(
            f'<line class="viz-ref" x1="{cx:.1f}" y1="{text_y + 4:.1f}" x2="{cx:.1f}" y2="{tip_y:.1f}"/>'
            f'<text class="viz-note" x="{text_x:.1f}" y="{text_y:.1f}" text-anchor="{anchor}">'
            f"{_esc(note['text'])}</text>"
        )
    return _svg(width, height, "".join(parts), title, desc)


def _bin_index(edges: Sequence[float], value: float) -> int:
    for i in range(len(edges) - 1):
        if edges[i] <= value < edges[i + 1]:
            return i
    return len(edges) - 2


# --------------------------------------------------------------------------
# Scatter with one group picked out
# --------------------------------------------------------------------------


def scatter(
    points: Sequence[dict],
    *,
    title: str,
    desc: str,
    x_label: str,
    y_label: str,
    highlight_label: str,
    context_label: str,
    threshold: float | None = None,
    threshold_label: str = "",
    y_ticks: Sequence[float] = (3, 10, 30, 100, 300, 1000),
    width: int = 940,
    height: int = 400,
) -> str:
    """Points are dicts with ``x`` (0 to 1), ``y`` (positive, log scale),
    ``highlight`` (bool), ``value`` and ``label`` for the tooltip."""
    left, right, top, bottom = 56, 24, 56, 50
    plot_w, plot_h = width - left - right, height - top - bottom
    ys = [p["y"] for p in points if p["y"] > 0] or [1]
    y_lo = min(min(ys), y_ticks[0])
    y_hi = max(max(ys), y_ticks[0] * 2)
    ticks = [t for t in y_ticks if y_lo <= t <= y_hi * 1.0001]
    log_lo, log_hi = math.log10(y_lo * 0.85), math.log10(y_hi * 1.2)

    def x(value: float) -> float:
        return left + min(max(value, 0.0), 1.0) * plot_w

    def y(value: float) -> float:
        return top + plot_h - (math.log10(max(value, y_lo)) - log_lo) / (log_hi - log_lo) * plot_h

    parts = []
    for t in ticks:
        parts.append(
            f'<line class="viz-grid" x1="{left}" y1="{y(t):.1f}" x2="{left + plot_w}" y2="{y(t):.1f}"/>'
            f'<text class="viz-tick" x="{left - 8}" y="{y(t) + 4:.1f}" text-anchor="end">'
            f"{int(t):,}</text>"
        )
    for i in range(0, 11, 2):
        t = i / 10
        parts.append(
            f'<text class="viz-tick" x="{x(t):.1f}" y="{top + plot_h + 16}" text-anchor="middle">'
            f"{_fmt(t, 1)}</text>"
        )
    parts.append(
        f'<line class="viz-axis" x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" '
        f'y2="{top + plot_h}"/>'
        f'<text class="viz-label" x="{left + plot_w / 2:.1f}" y="{height - 10}" '
        f'text-anchor="middle">{_esc(x_label)}</text>'
        f'<text class="viz-label" x="{left - 44}" y="{top - 34}">{_esc(y_label)}</text>'
    )
    if threshold is not None:
        parts.append(
            f'<line class="viz-ref" x1="{x(threshold):.1f}" y1="{top}" x2="{x(threshold):.1f}" '
            f'y2="{top + plot_h}"/>'
            f'<text class="viz-note" x="{x(threshold) + 6:.1f}" y="{top + 12}">'
            f"{_esc(threshold_label)}</text>"
        )

    # Legend: always present with two series.
    lx = left + plot_w - 300
    parts.append(
        f'<circle class="viz-s1" cx="{lx}" cy="{top - 38}" r="5"/>'
        f'<text class="viz-label" x="{lx + 10}" y="{top - 34}">{_esc(highlight_label)}</text>'
        f'<circle class="viz-context" cx="{lx + 170}" cy="{top - 38}" r="5"/>'
        f'<text class="viz-label" x="{lx + 180}" y="{top - 34}">{_esc(context_label)}</text>'
    )

    ordered = sorted(points, key=lambda p: bool(p.get("highlight")))
    for p in ordered:
        cx, cy = x(p["x"]), y(p["y"])
        lead = bool(p.get("highlight"))
        css = "viz-s1" if lead else "viz-context"
        parts.append(
            _hit(f'circle cx="{cx:.1f}" cy="{cy:.1f}" r="12"', p["value"], p["label"], lead)
            + f'<circle class="viz-mark {css} viz-ring" cx="{cx:.1f}" cy="{cy:.1f}" '
            f'r="{5.5 if lead else 4.5}"/>'
        )
    return _svg(width, height, "".join(parts), title, desc)


# --------------------------------------------------------------------------
# Bipartite picture of one group: firms on the left, tenders on the right
# --------------------------------------------------------------------------


def bipartite(
    firms: Sequence[dict],
    tenders: Sequence[dict],
    edges: Sequence[tuple],
    *,
    title: str,
    desc: str,
    footnote: str = "",
    width: int = 940,
) -> str:
    """``firms`` are dicts with ``id``, ``label`` and ``member``; ``tenders``
    are dicts with ``id`` and ``label``; ``edges`` are (firm id, tender id,
    won) triples. Tenders run top to bottom in time order."""
    top, legend_h = 64, 0
    firm_x, tender_x = 190, width - 150
    n_rows = max(len(firms), len(tenders), 1)
    spacing = 16 if len(tenders) > 24 else 22
    plot_h = max(spacing * (len(tenders) - 1), 60, 34 * (len(firms) - 1))
    height = top + plot_h + (54 if footnote else 34) + legend_h
    del n_rows

    def spread(count: int, index: int) -> float:
        if count == 1:
            return top + plot_h / 2
        return top + plot_h * index / (count - 1)

    firm_y = {f["id"]: spread(len(firms), i) for i, f in enumerate(firms)}
    tender_y = {t["id"]: spread(len(tenders), i) for i, t in enumerate(tenders)}
    members = {f["id"] for f in firms if f.get("member")}

    parts = [
        f'<text class="viz-note" x="{firm_x}" y="{top - 22}" text-anchor="end">Bidders</text>'
        f'<text class="viz-note" x="{tender_x}" y="{top - 22}">Tenders, oldest first</text>'
    ]
    # Legend, top right of the title row.
    lx, ly = firm_x + 40, 20
    parts.append(
        f'<circle class="viz-s1" cx="{lx}" cy="{ly}" r="5"/>'
        f'<text class="viz-label" x="{lx + 10}" y="{ly + 4}">Group member</text>'
        f'<circle class="viz-context" cx="{lx + 118}" cy="{ly}" r="5"/>'
        f'<text class="viz-label" x="{lx + 128}" y="{ly + 4}">Other bidders</text>'
        f'<line class="viz-s1-line" x1="{lx + 232}" y1="{ly}" x2="{lx + 254}" y2="{ly}"/>'
        f'<text class="viz-label" x="{lx + 260}" y="{ly + 4}">Winning bid</text>'
        f'<line class="viz-context-line" x1="{lx + 348}" y1="{ly}" x2="{lx + 370}" y2="{ly}"/>'
        f'<text class="viz-label" x="{lx + 376}" y="{ly + 4}">Losing bid</text>'
    )

    for won_pass in (False, True):  # winning bids are drawn last, on top
        for firm, tender, won in edges:
            if bool(won) != won_pass or firm not in firm_y or tender not in tender_y:
                continue
            css = "viz-s1-line" if won else "viz-context-line"
            parts.append(
                f'<line class="{css}" x1="{firm_x + 7}" y1="{firm_y[firm]:.1f}" '
                f'x2="{tender_x - 6}" y2="{tender_y[tender]:.1f}"/>'
            )

    for f in firms:
        cy = firm_y[f["id"]]
        css = "viz-s1" if f["id"] in members else "viz-context"
        parts.append(
            f'<circle class="{css} viz-ring" cx="{firm_x}" cy="{cy:.1f}" r="7"/>'
            f'<text class="viz-label" x="{firm_x - 14}" y="{cy + 4:.1f}" text-anchor="end">'
            f"{_esc(f['label'])}</text>"
        )
    previous_label = None
    for t in tenders:
        cy = tender_y[t["id"]]
        parts.append(
            _hit(f'circle cx="{tender_x}" cy="{cy:.1f}" r="{spacing / 2:.1f}"', t["tip"], t["id"])
            + f'<circle class="viz-mark viz-context viz-ring" cx="{tender_x}" cy="{cy:.1f}" r="4.5"/>'
        )
        if t["label"] != previous_label:
            parts.append(
                f'<text class="viz-tick" x="{tender_x + 12}" y="{cy + 4:.1f}">{_esc(t["label"])}</text>'
            )
            previous_label = t["label"]
    if footnote:
        parts.append(
            f'<text class="viz-note" x="{firm_x}" y="{height - 12}">{_esc(footnote)}</text>'
        )
    return _svg(width, height, "".join(parts), title, desc)
