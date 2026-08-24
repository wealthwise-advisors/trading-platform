"""
Generate docs/assets/one-clock.svg -- the shared market clock in the README.

WHAT THIS IS TRYING TO BE
-------------------------
The Backtesting section explains the platform's least obvious decision in
prose: stepping N engines once per tick does NOT give you a synchronised view,
because a bar is a different amount of time on every timeframe. After a hundred
ticks a 1m pane has moved a hundred minutes and a 1h pane a hundred hours.

That is a claim about TIME, and a paragraph is a poor place to make it. Here it
is a picture: one playhead crosses sixty minutes of market time, and each lane
lights only when its own bar has closed. The 1m lane fires sixty times, the 1h
lane fires once, at the end -- and you can see that they finish together.

The lane counts are the argument. They are computed from the periods, not
typed, so the drawing cannot claim a number the geometry does not produce.

WHY GENERATED
-------------
Four lanes, seventy-seven cells and their close times all keyed off one tick
duration. Typed by hand, the 15m lane ends up half a tick out from the 5m lane
under it and the whole point -- that they land together -- quietly stops being
true.

SMIL NOTES (the same ones make_pipeline_svg.py learned the hard way)
--------------------------------------------------------------------
* One <animate> per attribute per element. Two on the same attribute and the
  later one silently wins from t=0.
* An animated attribute must ALSO be set statically, or it renders at its
  default until its begin time arrives.
* GitHub proxies this image: SMIL survives, CSS animation and <script> do not.
"""

import pathlib
import sys

# ── canvas ────────────────────────────────────────────────────────────────
W = 1280
PAD = 34
LABEL_W = 116
TRACK_X = PAD + LABEL_W
COUNT_W = 52
TRACK_W = W - TRACK_X - PAD - COUNT_W

HEAD_Y = 52          # baseline of the header row
LANE_Y0 = 108        # top of the first lane
LANE_H = 46          # lane pitch
BAR_H = 30           # drawn height of a cell

# ── the run ───────────────────────────────────────────────────────────────
# Sixty minutes of market time. Chosen so the 1h lane closes exactly once --
# a shorter window would leave it dark for the whole loop, which reads as a
# broken lane rather than as the point being made.
TICKS = 60
TICK_DUR = 0.20                       # seconds of wall clock per market minute
CYCLE = TICKS * TICK_DUR              # 12.0s
STEP_X = TRACK_W / TICKS

# label, period in base bars, accent
LANES = [
    ("1m",  1,  "#22d3ee"),
    ("5m",  5,  "#3b82f6"),
    ("15m", 15, "#a855f7"),
    ("1h",  60, "#22c55e"),
]

FONT = ("ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "Roboto,Helvetica,Arial,sans-serif")
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

INK = "#eaf3ff"
DIM = "#8ba1bc"
GRID = "#1c2740"

H = LANE_Y0 + LANE_H * len(LANES) + 54

# Fast attack, slower decay, dark for the rest -- a bar CLOSING, not breathing.
# Same envelope the pipeline nodes use, so the two drawings agree about what an
# event looks like.
KT = "0;.06;.34;1"
KS = ".15 0 .1 1;.35 0 .45 1;0 0 1 1"


def _n(v) -> str:
    """Shortest exact spelling of a number for an SVG attribute.

    "0.14" -> ".14", "12.0" -> "12". SVG treats these as identical values, and
    at 154 animations the leading zeros alone are real bytes. Purely a spelling
    change: nothing here alters a timing or an opacity.
    """
    s = f"{float(v):g}"
    return s[1:] if s.startswith("0.") else ("-" + s[2:] if s.startswith("-0.") else s)


def close_anim(attr: str, lo, hi, begin: float) -> str:
    """One <animate> for one attribute, on the shared close envelope.

    Every field except `begin` is identical across all 154 of these, which is
    ~187 of the ~200 bytes. SMIL offers no way to share them: animation
    attributes are not inherited, <use> clones share one timeline rather than
    staggering, and the CSS @keyframes approach that WOULD collapse them is
    ruled out by the proxy note above. So the count is irreducible and only the
    spelling can be tightened.
    """
    return (
        f'<animate attributeName="{attr}" '
        f'values="{_n(lo)};{_n(hi)};{_n(lo)};{_n(lo)}" '
        f'keyTimes="{KT}" calcMode="spline" keySplines="{KS}" '
        f'begin="{_n(round(begin, 2))}s" dur="{_n(CYCLE)}s" repeatCount="indefinite"/>'
    )


def build() -> str:
    o: list[str] = []
    o.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" '
        f'aria-label="One market clock drives every timeframe: a playhead crosses '
        f'sixty minutes and each lane lights only when its own bar closes">'
    )

    # ── defs ──────────────────────────────────────────────────────────────
    o.append("<defs>")
    o.append(
        '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#0d1424"/>'
        '<stop offset="100%" stop-color="#0a0f1c"/></linearGradient>'
    )
    for _, _, c in LANES:
        key = c.lstrip("#")
        o.append(
            f'<linearGradient id="g{key}" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0%" stop-color="{c}" stop-opacity="0.85"/>'
            f'<stop offset="100%" stop-color="{c}" stop-opacity="0.35"/></linearGradient>'
        )
    o.append(
        '<linearGradient id="head" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#ffffff" stop-opacity="0.9"/>'
        '<stop offset="100%" stop-color="#7dd3fc" stop-opacity="0.5"/></linearGradient>'
    )
    o.append("</defs>")

    o.append(f'<rect width="{W}" height="{H}" rx="16" fill="url(#bg)"/>')
    o.append(
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="16" '
        f'fill="none" stroke="#1e2a44"/>'
    )

    # ── header ────────────────────────────────────────────────────────────
    o.append(
        f'<text x="{PAD}" y="{HEAD_Y-14}" font-family="{FONT}" font-size="13" '
        f'font-weight="700" letter-spacing="1.6" fill="{INK}">ONE MARKET CLOCK</text>'
    )
    o.append(
        f'<text x="{PAD}" y="{HEAD_Y+6}" font-family="{FONT}" font-size="12.5" '
        f'fill="{DIM}">One tick advances market time by a single base bar. '
        f'A pane steps only when its own bar has closed.</text>'
    )
    o.append(
        f'<text x="{W-PAD}" y="{HEAD_Y-14}" text-anchor="end" font-family="{MONO}" '
        f'font-size="12" letter-spacing="1.2" fill="{DIM}">60 MIN OF MARKET TIME</text>'
    )

    # ── lanes ─────────────────────────────────────────────────────────────
    for li, (label, period, colour) in enumerate(LANES):
        y = LANE_Y0 + li * LANE_H
        cy = y + BAR_H / 2
        key = colour.lstrip("#")
        closes = TICKS // period
        cell_w = STEP_X * period

        # label chip
        o.append(
            f'<rect x="{PAD}" y="{y+3}" width="{LABEL_W-22}" height="{BAR_H-6}" rx="7" '
            f'fill="{colour}" fill-opacity="0.10" stroke="{colour}" stroke-opacity="0.34"/>'
        )
        o.append(
            f'<text x="{PAD+14}" y="{cy+4.5}" font-family="{MONO}" font-size="13" '
            f'font-weight="700" fill="{colour}">{label}</text>'
        )

        # the empty track the cells sit in
        o.append(
            f'<rect x="{TRACK_X}" y="{y}" width="{TRACK_W}" height="{BAR_H}" rx="6" '
            f'fill="#0f1729" stroke="{GRID}"/>'
        )

        # one cell per closed bar
        for i in range(closes):
            x = TRACK_X + i * cell_w
            begin = (i + 1) * period * TICK_DUR
            inset = 1.4
            o.append(
                f'<rect x="{x+inset:.2f}" y="{y+inset}" '
                f'width="{cell_w-inset*2:.2f}" height="{BAR_H-inset*2}" rx="4" '
                f'fill="url(#g{key})" fill-opacity="0.14">'
                + close_anim("fill-opacity", 0.14, 0.95, begin) +
                "</rect>"
            )
            # the close itself -- a bright edge at the boundary the bar closed on
            xe = x + cell_w - inset
            o.append(
                f'<rect x="{xe-1.6:.2f}" y="{y+inset}" width="1.8" '
                f'height="{BAR_H-inset*2}" rx="1" fill="{colour}" fill-opacity="0">'
                + close_anim("fill-opacity", 0, 1, begin) +
                "</rect>"
            )

        # How many times this lane fired. This is the ARGUMENT of the whole
        # drawing -- sixty closes against one, over the same minute of market
        # time -- so it is on screen throughout rather than revealed at the
        # end. It brightens as the lane finishes, which is emphasis, not the
        # only chance to read it.
        o.append(
            f'<text x="{W-PAD}" y="{cy+4.5}" text-anchor="end" font-family="{MONO}" '
            f'font-size="12" font-weight="700" fill="{colour}" opacity="0.42">'
            f'{closes}×'
            f'<animate attributeName="opacity" values="0.42;0.42;1;0.42" '
            f'keyTimes="0;0.86;0.94;1" begin="0s" dur="{CYCLE}s" '
            f'repeatCount="indefinite"/></text>'
        )

    # ── the playhead ──────────────────────────────────────────────────────
    # Drawn last so it rides over every lane. Linear on purpose: market time
    # does not ease.
    top = LANE_Y0 - 12
    bot = LANE_Y0 + LANE_H * len(LANES) - (LANE_H - BAR_H) + 6
    o.append(
        f'<g><rect x="{TRACK_X}" y="{top}" width="2" height="{bot-top}" '
        f'fill="url(#head)">'
        f'<animate attributeName="x" values="{TRACK_X};{TRACK_X+TRACK_W}" '
        f'begin="0s" dur="{CYCLE}s" calcMode="linear" repeatCount="indefinite"/>'
        f'</rect>'
        f'<circle cx="{TRACK_X+1}" cy="{top}" r="3.4" fill="#ffffff">'
        f'<animate attributeName="cx" values="{TRACK_X+1};{TRACK_X+TRACK_W+1}" '
        f'begin="0s" dur="{CYCLE}s" calcMode="linear" repeatCount="indefinite"/>'
        f'</circle></g>'
    )

    # ── footnote ──────────────────────────────────────────────────────────
    o.append(
        f'<text x="{PAD}" y="{H-20}" font-family="{FONT}" font-size="12" fill="{DIM}">'
        f'Every lane reaches the right edge together — that is what "synchronised" '
        f'means here, and it is what stepping each engine once per tick does not give you.'
        f'</text>'
    )

    o.append("</svg>")
    return "".join(o)


if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parents[1] / "one-clock.svg"
    svg = build()
    out.write_text(svg, encoding="utf-8")
    total_cells = sum(TICKS // p for _, p, _ in LANES)
    print(f"wrote {out}  ({len(svg):,} bytes, {total_cells} cells, "
          f"{CYCLE:.1f}s loop)", file=sys.stderr)
