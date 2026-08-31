"""
Generate docs/assets/divergence.svg -- the RSI divergence setup in the README.

WHAT THIS IS TRYING TO BE
-------------------------
The Strategy Engine table gives rsi_divergence one line: "Price makes a new
extreme, RSI does not." That is the observation, not the rule. The rule is two
steps separated by several bars -- the divergence ARMS a setup, and a later
close above the divergence bar's high is what actually enters -- and the README
says so only in a callout about why each timeframe needs its own instance.

Two steps separated in time is a thing to draw, not describe. The diagram plays
the sequence: the first low, the second lower low with RSI refusing to follow,
the two divergence lines opening against each other, the setup arming, and the
entry firing when price finally takes the trigger level.

THIS IS A SCHEMATIC, NOT A BACKTEST
-----------------------------------
The series are authored to show the pattern cleanly. They are not sampled from
a run and the drawing never presents a P&L, a date or a symbol -- the moment it
did, it would be claiming a result it did not compute.

SMIL NOTES (same three make_pipeline_svg.py learned the hard way)
----------------------------------------------------------------
* One <animate> per attribute per element.
* An animated attribute must ALSO be set statically.
* GitHub proxies this image: SMIL survives, CSS animation and script do not.
"""

import pathlib
import sys

W = 1280
H = 456   # +26 for the second caption line; see the footnote below
PAD = 34
PLOT_X = PAD + 8
PLOT_W = W - PLOT_X - PAD - 210      # room for the right-hand rule list
                                     # 150 clipped "not an entry" and "the trigger";
                                     # measured against the longest string, not guessed

PRICE_Y, PRICE_H = 62, 210
RSI_Y, RSI_H = 300, 92

# ── the two series ────────────────────────────────────────────────────────
# Authored, and the shape is the whole argument: price prints a LOWER low at
# bar 26 while RSI prints a HIGHER low at the same bar. Anything else and the
# picture is of some other pattern.
PRICE = [
    72, 70, 67, 63, 58, 52, 45, 38, 30, 34, 41, 49, 56, 62, 66, 69, 71, 70,
    66, 60, 52, 44, 36, 28, 22, 18, 16, 24, 33, 43, 53, 63, 72, 79, 84, 88,
]
RSI = [
    58, 52, 44, 36, 28, 21, 15, 10, 7, 18, 30, 44, 57, 66, 71, 74, 72, 66,
    58, 50, 43, 37, 32, 28, 25, 23, 22, 34, 47, 59, 70, 79, 86, 90, 92, 93,
]
N = len(PRICE)

LOW_1 = 8        # first swing low
LOW_2 = 26       # second: lower on price, higher on RSI -- the divergence
ENTRY = 31       # the close that takes the trigger level

FONT = ("ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "Roboto,Helvetica,Arial,sans-serif")
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

INK, DIM, GRID = "#eaf3ff", "#8ba1bc", "#1c2740"
UP, DOWN, ARM, TRIG = "#22c55e", "#ef4444", "#a855f7", "#f59e0b"

CYCLE = 11.0
T_LOW1, T_LOW2, T_DIV, T_ARM, T_ENTRY = 1.6, 3.6, 4.6, 5.6, 7.0

STEP = PLOT_W / (N - 1)


def px(i: float) -> float:
    return PLOT_X + i * STEP


def py(v: float) -> float:
    return PRICE_Y + PRICE_H - (v / 100) * PRICE_H


def ry(v: float) -> float:
    return RSI_Y + RSI_H - (v / 100) * RSI_H


def fade(begin: float, to: float = 1.0, dur: float = 0.5) -> str:
    """Appear once at `begin` and stay for the rest of the loop."""
    return (
        f'<animate attributeName="opacity" values="0;0;{to};{to}" '
        f'keyTimes="0;{begin/CYCLE:.4f};{(begin+dur)/CYCLE:.4f};1" '
        f'begin="0s" dur="{CYCLE}s" repeatCount="indefinite"/>'
    )


def build() -> str:
    o: list[str] = []
    o.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" aria-label="RSI divergence: price '
        f'prints a lower low while RSI prints a higher low, which arms the setup; '
        f'a later close above the divergence bar’s high is the entry">'
    )

    o.append(
        '<defs>'
        '<linearGradient id="dbg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#0d1424"/>'
        '<stop offset="100%" stop-color="#0a0f1c"/></linearGradient>'
        '</defs>'
    )
    o.append(f'<rect width="{W}" height="{H}" rx="16" fill="url(#dbg)"/>')
    o.append(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="16" '
             f'fill="none" stroke="#1e2a44"/>')

    # ── titles ────────────────────────────────────────────────────────────
    o.append(f'<text x="{PAD}" y="34" font-family="{FONT}" font-size="20.6" '
             f'font-weight="700" letter-spacing="1.6" fill="{INK}">'
             f'RSI DIVERGENCE — THE SETUP</text>')
    o.append(f'<text x="{W-PAD}" y="34" text-anchor="end" font-family="{MONO}" '
             f'font-size="20.6" letter-spacing="1.1" fill="{DIM}">SCHEMATIC</text>')

    # ── panel frames ──────────────────────────────────────────────────────
    for y, h, label in ((PRICE_Y, PRICE_H, "PRICE"), (RSI_Y, RSI_H, "RSI(2)")):
        o.append(f'<rect x="{PLOT_X-8}" y="{y-8}" width="{PLOT_W+16}" '
                 f'height="{h+16}" rx="10" fill="#0f1729" stroke="{GRID}"/>')
        o.append(f'<text x="{PLOT_X-2}" y="{y+12}" font-family="{MONO}" '
                 f'font-size="17.8" letter-spacing="1" fill="{DIM}">{label}</text>')

    # RSI oversold guide -- the level the second low does NOT reach
    o.append(f'<line x1="{PLOT_X}" y1="{ry(20):.1f}" x2="{PLOT_X+PLOT_W}" '
             f'y2="{ry(20):.1f}" stroke="{UP}" stroke-opacity="0.30" '
             f'stroke-dasharray="4 4"/>')

    # ── the series ────────────────────────────────────────────────────────
    for series, ymap, colour in ((PRICE, py, "#7dd3fc"), (RSI, ry, "#c084fc")):
        pts = " ".join(f"{px(i):.1f},{ymap(v):.1f}" for i, v in enumerate(series))
        o.append(f'<polyline points="{pts}" fill="none" stroke="{colour}" '
                 f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')

    # ── step 1 · the two lows ─────────────────────────────────────────────
    for idx, (bar, t) in enumerate(((LOW_1, T_LOW1), (LOW_2, T_LOW2))):
        for series, ymap in ((PRICE, py), (RSI, ry)):
            cx, cy = px(bar), ymap(series[bar])
            o.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6.5" fill="none" '
                     f'stroke="{DOWN if series is PRICE else ARM}" '
                     f'stroke-width="2.2" opacity="0">{fade(t)}</circle>')
        o.append(f'<text x="{px(bar):.1f}" y="{py(PRICE[bar])+26:.1f}" '
                 f'text-anchor="middle" font-family="{MONO}" font-size="17.8" '
                 f'fill="{DIM}" opacity="0">low {idx+1}{fade(t)}</text>')

    # ── step 2 · the divergence, two lines opening against each other ─────
    o.append(f'<line x1="{px(LOW_1):.1f}" y1="{py(PRICE[LOW_1]):.1f}" '
             f'x2="{px(LOW_2):.1f}" y2="{py(PRICE[LOW_2]):.1f}" stroke="{DOWN}" '
             f'stroke-width="2" stroke-dasharray="6 5" opacity="0">{fade(T_DIV)}</line>')
    o.append(f'<line x1="{px(LOW_1):.1f}" y1="{ry(RSI[LOW_1]):.1f}" '
             f'x2="{px(LOW_2):.1f}" y2="{ry(RSI[LOW_2]):.1f}" stroke="{UP}" '
             f'stroke-width="2" stroke-dasharray="6 5" opacity="0">{fade(T_DIV)}</line>')
    # Sat ON their own dashed lines when placed at an endpoint. Both now hang
    # off the MIDPOINT of the line they describe -- price below it, RSI above
    # it, which is the side the series curve is not on in each panel.
    mid = (LOW_1 + LOW_2) / 2
    p_mid = (py(PRICE[LOW_1]) + py(PRICE[LOW_2])) / 2
    r_mid = (ry(RSI[LOW_1]) + ry(RSI[LOW_2])) / 2
    o.append(f'<text x="{px(mid):.1f}" y="{p_mid+15:.1f}" '
             f'text-anchor="middle" font-family="{FONT}" font-size="20.6" '
             f'font-weight="600" fill="{DOWN}" opacity="0">'
             f'price: lower low{fade(T_DIV)}</text>')
    o.append(f'<text x="{px(mid):.1f}" y="{r_mid-9:.1f}" '
             f'text-anchor="middle" font-family="{FONT}" font-size="20.6" '
             f'font-weight="600" fill="{UP}" opacity="0">'
             f'RSI: higher low{fade(T_DIV)}</text>')

    # ── step 3 · armed, and the trigger level it arms ─────────────────────
    trig_y = py(max(PRICE[LOW_2 - 1:LOW_2 + 2]) + 12)
    o.append(f'<line x1="{px(LOW_2):.1f}" y1="{PRICE_Y}" x2="{px(LOW_2):.1f}" '
             f'y2="{RSI_Y+RSI_H:.1f}" stroke="{ARM}" stroke-width="1.4" '
             f'stroke-dasharray="3 4" opacity="0">{fade(T_ARM)}</line>')
    o.append(f'<rect x="{px(LOW_2)-30:.1f}" y="{PRICE_Y-22}" width="60" height="17" '
             f'rx="5" fill="{ARM}" fill-opacity="0.16" stroke="{ARM}" '
             f'stroke-opacity="0.5" opacity="0">{fade(T_ARM)}</rect>')
    o.append(f'<text x="{px(LOW_2):.1f}" y="{PRICE_Y-10}" text-anchor="middle" '
             f'font-family="{MONO}" font-size="17" font-weight="700" fill="{ARM}" '
             f'opacity="0">ARMED{fade(T_ARM)}</text>')

    o.append(f'<line x1="{px(LOW_2):.1f}" y1="{trig_y:.1f}" '
             f'x2="{px(N-1):.1f}" y2="{trig_y:.1f}" stroke="{TRIG}" '
             f'stroke-width="1.6" stroke-dasharray="5 4" opacity="0">{fade(T_ARM)}</line>')
    # Anchored at the LEFT end of the line and inside the panel; anchored right
    # it ran past the plot edge and into the rule list.
    o.append(f'<text x="{px(LOW_2)+8:.1f}" y="{trig_y-7:.1f}" '
             f'font-family="{MONO}" font-size="17" fill="{TRIG}" opacity="0">'
             f'trigger — high of the divergence bar{fade(T_ARM)}</text>')

    # ── step 4 · the entry ────────────────────────────────────────────────
    ex, ey = px(ENTRY), py(PRICE[ENTRY])
    o.append(f'<path d="M {ex:.1f} {ey+22:.1f} l -7 12 l 14 0 Z" fill="{UP}" '
             f'opacity="0">{fade(T_ENTRY)}</path>')
    o.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="7" fill="none" stroke="{UP}" '
             f'stroke-width="2.4" opacity="0">{fade(T_ENTRY)}</circle>')
    o.append(f'<text x="{ex:.1f}" y="{ey-14:.1f}" text-anchor="middle" '
             f'font-family="{MONO}" font-size="20.6" font-weight="700" fill="{UP}" '
             f'opacity="0">BUY{fade(T_ENTRY)}</text>')

    # ── the rule, in order, down the right edge ───────────────────────────
    lx = PLOT_X + PLOT_W + 26
    steps = [
        ("1", "Price prints a lower low", DOWN, T_LOW2),
        ("2", "RSI prints a higher low", UP, T_DIV),
        ("3", "Setup arms, not an entry", ARM, T_ARM),
        ("4", "Close takes the trigger", UP, T_ENTRY),
    ]
    for i, (num, text, colour, t) in enumerate(steps):
        y = PRICE_Y + 26 + i * 46
        o.append(f'<g opacity="0">{fade(t)}'
                 f'<circle cx="{lx+9}" cy="{y-4}" r="9" fill="{colour}" '
                 f'fill-opacity="0.16" stroke="{colour}" stroke-opacity="0.55"/>'
                 f'<text x="{lx+9}" y="{y}" text-anchor="middle" font-family="{MONO}" '
                 f'font-size="17" font-weight="700" fill="{colour}">{num}</text>'
                 f'<text x="{lx+26}" y="{y}" font-family="{FONT}" font-size="20.6" '
                 f'fill="{INK}">{text}</text></g>')

    # Two lines. SVG <text> does not wrap, so a caption longer than the canvas
    # is not shrunk or reflowed -- it is silently cut off at the edge, which is
    # exactly what the single-line version did once the type went up.
    for i, line in enumerate((
        'The divergence only ARMS the setup. Several bars can pass before the',
        'trigger is taken — which is why every timeframe needs its own strategy instance.',
    )):
        o.append(f'<text x="{PAD}" y="{H-40+i*24}" font-family="{FONT}" '
                 f'font-size="18.4" fill="{DIM}">{line}</text>')

    o.append("</svg>")
    return "".join(o)


if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parents[1] / "divergence.svg"
    svg = build()
    out.write_text(svg, encoding="utf-8")
    assert PRICE[LOW_2] < PRICE[LOW_1], "price must print the LOWER low"
    assert RSI[LOW_2] > RSI[LOW_1], "RSI must print the HIGHER low"
    print(f"wrote {out}  ({len(svg):,} bytes, {CYCLE}s loop)", file=sys.stderr)
