"""The exported report's Volume Profile and oscillator rows, drawn from the live
chart's own settings (api/schemas/chart_settings.py).

Each function here mirrors, line for line, the web code that draws the same
thing on the dashboard:

    compute_volume_profile / _profiles   web/src/lib/volumeProfile.ts
    session_profile_shapes               web/src/lib/volumeProfileShapes.ts
    level_trace / bubble_annotation /    web/src/lib/vpPlotStyles.ts
      title_entries
    active_oscillator_rows /             web/src/lib/oscillatorStudies.ts
      oscillator_row_heights
    draw_volume_profile                  CandlestickChart.tsx -- the bars, the
                                         plot names, the input-names title

A change to one side that skips the other is the defect this module exists to
remove; tests/test_report_chart_settings.py pins the behaviour and the browser
check compares the two drawn figures directly.

WHY THE PROFILE IS PORTED RATHER THAN CALLING calc_volume_profile
-----------------------------------------------------------------
src/analysis/indicators.py's calc_volume_profile is described as the same
algorithm, and the report used it until 2026-09-15. It is not the same numbers:

* it files a bar into a bucket with floor division, (low - lo) // width, where
  the browser uses Math.floor((low - lo) / width). For float operands those
  differ when the quotient rounds up onto a whole number, which on 0.25-tick
  prices happens constantly -- 19 of 800 bar edges in one test series landed
  one bucket lower, enough to move the POC by a bucket;
* numpy sums pairwise and derives centres from linspace edges, where the browser
  sums left to right and computes each centre directly, so even agreeing
  buckets can differ in the last bit -- and a bubble rounds its price to the
  cent, where 5000.375 sits exactly on a half-cent.

So the report's levels could differ from the chart's. This port does the
arithmetic in the browser's order, and tests/fixtures/volume_profile_golden.json
-- computed by the browser code and checked by both test suites -- holds the
two to the same numbers exactly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd
import plotly.graph_objects as go

from api.schemas.chart_settings import (
    OSC_ORDER, ChartSettings, PlotStyle, PlotStyles, VolumeProfileSettings,
)

# ── Oscillator rows ──────────────────────────────────────────────────────────

#: CandlestickChart.tsx's PRICE_WEIGHT and ROW_SPACING.
PRICE_WEIGHT = 0.68
ROW_SPACING = 0.028

OSC_TITLE = {"rsi2": "RSI(2)", "stochrsi": "StochRSI", "rsi13": "RSI(13)", "mfi": "MFI"}

#: (overbought, oversold) -- oscillatorStudies.ts's OSC_STUDIES levels. RSI(2)
#: at 94/2 and RSI(13) at 70/30 are confirmed final; do not change them here.
OSC_LEVELS = {"rsi2": (94, 2), "stochrsi": (80, 20), "rsi13": (70, 30), "mfi": (80, 20)}


def active_oscillator_rows(settings: ChartSettings) -> list[str]:
    """The oscillator rows to draw, top to bottom."""
    return [k for k in OSC_ORDER if getattr(settings.oscillators, k)]


def oscillator_row_heights(rows: int) -> list[float]:
    """Price first, then an equal share per oscillator; price alone takes it all."""
    if rows <= 0:
        return [1.0]
    return [PRICE_WEIGHT, *[(1 - PRICE_WEIGHT) / rows] * rows]


# ── JavaScript number formatting ─────────────────────────────────────────────

def js_to_fixed(value: float, digits: int) -> str:
    """Number.prototype.toFixed: rounds the exact binary value, ties away from zero.

    Python's format() rounds ties to even, so f"{100.125:.2f}" is "100.12" where
    the chart prints "100.13".
    """
    if value == 0:
        # (-0).toFixed(2) is "0.00"; a small negative such as -0.001 stays "-0.00".
        value = 0.0
    q = Decimal(value).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return f"{q:.{digits}f}"


def js_number(value: float) -> str:
    """How a JavaScript template literal prints a number: 1 not 1.0, 0.00001 not 1e-05."""
    v = float(value)
    if v.is_integer() and abs(v) < 1e21:
        return str(int(v))
    text = repr(v)
    if "e" in text and abs(v) >= 1e-6:
        text = format(Decimal(text), "f")
    return text


# ── Profile computation (web/src/lib/volumeProfile.ts) ───────────────────────

@dataclass
class Profile:
    prices: list[float] = field(default_factory=list)
    volumes: list[float] = field(default_factory=list)
    poc: float | None = None
    val: float | None = None
    vah: float | None = None
    bin_size: float | None = None


@dataclass
class ProfileSlice:
    start: pd.Timestamp
    end: pd.Timestamp
    profile: Profile


def compute_volume_profile(highs: list[float], lows: list[float], vols: list[float],
                           bins: int = 48, value_area_pct: float = 0.7) -> Profile:
    """computeVolumeProfile(), in the same order of operations."""
    if not highs or bins < 1:
        return Profile()

    lo, hi, total_vol = math.inf, -math.inf, 0.0
    for h, l, v in zip(highs, lows, vols):
        if l < lo:
            lo = l
        if h > hi:
            hi = h
        total_vol += v
    if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo or total_vol <= 0:
        return Profile()

    width = (hi - lo) / bins
    centers = [lo + width * (i + 0.5) for i in range(bins)]
    bucket = [0.0] * bins
    for h, l, v in zip(highs, lows, vols):
        if v <= 0 or not math.isfinite(h) or not math.isfinite(l):
            continue
        first = min(max(math.floor((l - lo) / width), 0), bins - 1)
        last = min(max(math.floor((h - lo) / width), 0), bins - 1)
        share = v / (last - first + 1)
        for i in range(first, last + 1):
            bucket[i] += share

    total = 0.0
    for b in bucket:
        total += b
    if total <= 0:
        return Profile()

    poc_i = 0
    for i in range(1, bins):
        if bucket[i] > bucket[poc_i]:
            poc_i = i

    target = total * value_area_pct
    covered = bucket[poc_i]
    below = above = poc_i
    while covered < target and (below > 0 or above < bins - 1):
        take_below = bucket[below - 1] if below > 0 else -1.0
        take_above = bucket[above + 1] if above < bins - 1 else -1.0
        if take_above >= take_below:
            above += 1
            covered += take_above
        else:
            below -= 1
            covered += take_below

    return Profile(prices=centers, volumes=bucket, poc=centers[poc_i],
                   val=lo + width * below, vah=lo + width * (above + 1), bin_size=width)


def _period_key(ts: pd.Timestamp, time_per: str) -> str:
    # The bar's own calendar date, as written -- see periodKey() in volumeProfile.ts.
    if time_per == "CHART":
        return "all"
    day_index = (ts.date() - date(1970, 1, 1)).days
    if time_per == "WEEK":
        return f"w{day_index // 7}"
    return f"d{day_index}"


def compute_volume_profiles(df: pd.DataFrame, vp: VolumeProfileSettings) -> list[ProfileSlice]:
    """computeVolumeProfiles(): one profile per CHART / DAY / WEEK period."""
    n = len(df)
    if n == 0:
        return []
    highs = [float(x) for x in df["high"]]
    lows = [float(x) for x in df["low"]]
    if "volume" in df.columns:
        # The chart receives a missing volume as null and reads it as 0.
        vols = [0.0 if (x is None or x != x) else float(x) for x in df["volume"]]
    else:
        vols = [0.0] * n
    times = list(df.index)

    groups: dict[str, list[int]] = {}
    for i, ts in enumerate(times):
        groups.setdefault(_period_key(ts, vp.time_per), []).append(i)
    order = list(groups)

    step = max(1, math.floor(vp.multiplier))
    merged = [[i for k in order[j:j + step] for i in groups[k]] for j in range(0, len(order), step)]
    kept = merged[-max(1, vp.max_profiles):]

    out: list[ProfileSlice] = []
    for grp in kept:
        bin_count = vp.bins
        if vp.row_mode == "MANUAL" and vp.row_height > 0:
            lo = min(lows[i] for i in grp)
            hi = max(highs[i] for i in grp)
            if math.isfinite(lo) and math.isfinite(hi) and hi > lo:
                # Math.round, not Python's round(): ties go up, not to even.
                bin_count = max(1, min(2000, math.floor((hi - lo) / vp.row_height + 0.5)))
        profile = compute_volume_profile([highs[i] for i in grp], [lows[i] for i in grp],
                                         [vols[i] for i in grp], bin_count, vp.value_area / 100)
        if not profile.prices:
            continue
        out.append(ProfileSlice(start=times[grp[0]], end=times[grp[-1]], profile=profile))
    return out


# ── Plot styling (web/src/lib/vpPlotStyles.ts) ───────────────────────────────

#: Tab order, as the dialog lists the plots.
PLOT_ORDER = ("poc", "profile_high", "profile_low", "vah", "val")
PLOT_LABEL = {"poc": "POC", "profile_high": "ProfileHigh", "profile_low": "ProfileLow",
              "vah": "VAHigh", "val": "VALow"}
MAX_LEVEL_MARKERS = 60
_MARKER = {"points": "circle", "squares": "square", "triangles": "triangle-up"}
_LABEL_BG = "rgba(20,21,28,0.75)"


def line_width_px(width: int) -> float:
    """Width 1 is the 1.2px the levels have always been drawn at."""
    return 1.2 if width <= 1 else width


def level_trace(label: str, value: float, xs: list, style: PlotStyle) -> go.Scatter:
    common = dict(name=label, legendgroup="vp", xaxis="x", yaxis="y",
                  hovertemplate=f"<b>{label}</b>: %{{y:.2f}}<extra></extra>")
    if style.draw_as == "line":
        return go.Scatter(mode="lines", x=xs, y=[value] * len(xs),
                          line=dict(color=style.color, width=line_width_px(style.width), dash=style.style),
                          **common)
    step = max(1, math.ceil(len(xs) / MAX_LEVEL_MARKERS))
    sx = xs[::step]
    return go.Scatter(mode="markers", x=sx, y=[value] * len(sx),
                      marker=dict(symbol=_MARKER[style.draw_as], size=3 + 2 * style.width, color=style.color),
                      **common)


def bubble_annotation(value: float, style: PlotStyle, side: str) -> dict:
    left = side == "left"
    return dict(x=0 if left else 1, xref="paper", xanchor="right" if left else "left",
                y=value, yref="y", yanchor="middle", text=js_to_fixed(value, 2), showarrow=False,
                font=dict(size=10, color="#0b0c10"), bgcolor=style.color, borderpad=2)


def title_entries(plots: PlotStyles, values: dict[str, float | None]) -> str:
    return "  ·  ".join(
        f"{PLOT_LABEL[k]}: {js_to_fixed(values[k], 2)}"
        for k in PLOT_ORDER
        if getattr(plots, k).show and getattr(plots, k).title and values[k] is not None
    )


def _fill(opacity: float, in_value_area: bool) -> str:
    return f"rgba(56,189,248,{js_to_fixed(opacity * (0.68 if in_value_area else 0.26), 3)})"


# ── Session-anchored profiles (web/src/lib/volumeProfileShapes.ts) ───────────

def _chart_x(x0: pd.Timestamp, offset_ms: float) -> pd.Timestamp:
    """A boundary x0 + offset, serialised as volumeProfileShapes.ts serialises it.

    A Date truncates fractional milliseconds. formatterFor() then writes a
    naive timestamp -- which is what bars carry here -- with toNaiveString,
    which has no milliseconds at all, so a naive boundary lands on the whole
    second below. A zoned one keeps its milliseconds (toISOString).
    """
    x = x0 + pd.Timedelta(milliseconds=math.trunc(offset_ms))
    return x if x0.tzinfo is not None else x.floor("s")


def session_profile_shapes(slices: list[ProfileSlice], opacity_pct: float, plots: PlotStyles) -> list[dict]:
    out: list[dict] = []
    a = opacity_pct / 100
    for sl in slices:
        p = sl.profile
        x0 = pd.Timestamp(sl.start)
        # Milliseconds, as Date.parse gives them.
        span = max((pd.Timestamp(sl.end) - x0) / pd.Timedelta(milliseconds=1), 60_000)
        max_vol = max(max(p.volumes), 1)
        half = (p.bin_size or 0) / 2

        for price, vol in zip(p.prices, p.volumes):
            frac = vol / max_vol
            if frac <= 0:
                continue
            in_va = p.val is not None and p.vah is not None and p.val <= price <= p.vah
            out.append(dict(
                type="rect", xref="x", yref="y", layer="below",
                x0=x0, x1=_chart_x(x0, span * frac * 0.9),
                y0=price - half, y1=price + half,
                fillcolor=_fill(a, in_va), line=dict(width=0),
            ))

        levels = (
            ("poc", p.poc),
            ("vah", p.vah),
            ("val", p.val),
            ("profile_high", p.prices[-1] + half if p.prices else None),
            ("profile_low", p.prices[0] - half if p.prices else None),
        )
        for key, value in levels:
            st = getattr(plots, key)
            if not st.show or value is None:
                continue
            out.append(dict(
                type="line", xref="x", yref="y",
                x0=x0, x1=_chart_x(x0, span),
                y0=value, y1=value,
                line=dict(color=st.color, width=st.width if st.width > 1 else 1.1, dash=st.style),
            ))
    return out


# ── Everything the Volume Profile study puts on the price row ────────────────

@dataclass
class VolumeProfileDrawing:
    #: Appended to the chart title when Show input names is on.
    title_suffix: str = ""
    #: The reversed overlay axis the whole-chart histogram sits on, or None.
    overlay_axis: dict | None = None


def draw_volume_profile(fig: go.Figure, df: pd.DataFrame, vp: VolumeProfileSettings) -> VolumeProfileDrawing:
    """Draw the study on the price row exactly as CandlestickChart.tsx does."""
    drawing = VolumeProfileDrawing()
    slices = compute_volume_profiles(df, vp)
    # The right-hand overlay only makes sense for one whole-chart profile;
    # DAY / WEEK profiles are anchored in time inside their own sessions.
    single = vp.time_per == "CHART" and len(slices) == 1
    local = slices[-1].profile if slices else Profile()
    visible = vp.on and vp.show_study and single and vp.on_expansion and len(local.prices) > 0
    opacity = vp.opacity / 100

    if visible:
        in_va = [local.val is not None and local.vah is not None and local.val <= p <= local.vah
                 for p in local.prices]
        fig.add_trace(go.Bar(
            orientation="h", x=local.volumes, y=local.prices, width=local.bin_size,
            marker=dict(color=[_fill(opacity, f) for f in in_va]),
            name="Volume Profile",
            hovertemplate="<b>Volume Profile</b><br>%{y:.2f}: %{x:,.0f}<extra></extra>",
            # Axis 9, not 5: the price row and four oscillator rows use axes 1 to 5.
            xaxis="x9", yaxis="y", showlegend=True,
        ))
        drawing.overlay_axis = dict(
            overlaying="x", side="top", anchor="y",
            range=[max(max(local.volumes), 1) * 4, 0],     # reversed; bars use <= 1/4 width
            showgrid=False, zeroline=False, showticklabels=False, fixedrange=True,
        )

    if vp.on and vp.show_study and not single and slices:
        fig.update_layout(shapes=list(fig.layout.shapes or []) + session_profile_shapes(slices, vp.opacity, vp.plots))

    values: dict[str, float | None] = dict.fromkeys(PLOT_ORDER)
    levels: list[tuple[str, float, PlotStyle]] = []
    if visible:
        half = (local.bin_size or 0) / 2
        values.update(poc=local.poc, vah=local.vah, val=local.val,
                      profile_high=local.prices[-1] + half, profile_low=local.prices[0] - half)
        for key in ("poc", "vah", "val", "profile_high", "profile_low"):
            st = getattr(vp.plots, key)
            if st.show and values[key] is not None:
                levels.append((key, values[key], st))

    annotations: list[dict] = []
    if vp.show_plot_names:
        for key, value, st in levels:
            annotations.append(dict(x=1, xref="paper", xanchor="right", y=value, yref="y", yanchor="middle",
                                    text=PLOT_LABEL[key], showarrow=False,
                                    font=dict(size=9, color=st.color), bgcolor=_LABEL_BG, borderpad=2))
    for _, value, st in levels:
        if st.bubble:
            annotations.append(bubble_annotation(value, st, "left" if vp.left_axis else "right"))
    title_line = title_entries(vp.plots, values) if visible else ""
    if title_line:
        annotations.append(dict(x=0, xref="paper", xanchor="left", y=1, yref="y domain", yanchor="top",
                                text=title_line, showarrow=False,
                                font=dict(size=10, color="#7dd3fc"), bgcolor=_LABEL_BG, borderpad=2))
    for ann in annotations:
        fig.add_annotation(**ann)

    xs = list(df.index)
    for key, value, st in levels:
        fig.add_trace(level_trace(PLOT_LABEL[key], value, xs, st))

    if vp.on and vp.show_study and vp.show_input_names:
        yn = lambda b: "Yes" if b else "No"  # noqa: E731
        drawing.title_suffix = (
            '<br><span style="font-size:10px;color:#7dd3fc">'
            f"VolumeProfile({vp.row_mode}, {js_number(vp.row_height)}, {vp.time_per}, "
            f"{js_number(vp.multiplier)}, {yn(vp.on_expansion)}, {vp.max_profiles}, "
            f"{yn(vp.plots.poc.show)}, {yn(vp.plots.vah.show or vp.plots.val.show)}, "
            f"{js_number(vp.value_area)}, {js_number(vp.opacity)})</span>"
        )
    return drawing
