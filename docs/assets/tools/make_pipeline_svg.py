"""
Generate docs/assets/pipeline.svg -- the six-stage pipeline in the README.

WHAT THIS IS
------------
Six stages, left to right, each a card carrying its own name, what it does and
what it produces. Straight connectors between them, and one small dot per
connector that travels once when that hand-off happens.

WHY IT LOOKS LIKE THIS NOW
--------------------------
The previous version drew each stage as five concentric layers -- atmospheric
glow, an outer hairline, two counter-rotating arcs, an illuminated inner ring
and a seated disc -- with technical ticks around the rim, particles in every
gap and a run of chevrons lighting in sequence. Twenty-four rotate transforms
and seventy-nine animations.

It was well made and it was the wrong thing. A README diagram's job is to be
read, and rings that spin regardless of what the data is doing compete with
the labels for attention while telling you nothing. The standard this now
follows is explicit: simple boxes, simple arrows, motion only where it
communicates flow, and no decorative rotation, particles or glow.

WHAT WAS KEPT, EXACTLY
----------------------
Every stage name, both description lines, every badge, every accent colour and
all six icon glyphs are unchanged -- they are the content. Only the drawing of
a node changed. STAGES and icon() below were spliced from the previous file
rather than retyped, so none of it could drift in the rewrite.

WHAT THE MOTION DOES NOW
------------------------
One dot per connector, travelling once per cycle in stage order, and the
receiving card's border brightening as it lands. That is the hand-off, and it
is the only thing moving. Nothing loops for decoration.

A NOTE ON REDUCED MOTION
------------------------
SMIL cannot be gated by prefers-reduced-motion: CSS loses to SMIL in the
cascade, and this loads through an <img>. So the answer is to keep the motion
quiet enough that gating is not needed -- one small dot, no rotation, no
pulsing -- rather than to claim a switch that does not exist.

SMIL NOTES, LEARNED THE HARD WAY (kept from the previous version)
------------------------------------------------------------------
* Two <animate> on the SAME attribute of the SAME element: the later silently
  wins from t=0. One animation per attribute, always.
* An animated attribute must ALSO be set, or it renders at its default before
  its begin time arrives.
* GitHub proxies this image: SMIL survives, CSS animation and script do not.
"""
import pathlib
import sys

W = 1280
PAD = 26
GAP = 24
COLS = 6
CARD_W = (W - 2 * PAD - GAP * (COLS - 1)) // COLS
CARD_H = 156
CARD_Y = 34
H = CARD_Y + CARD_H + 34

FONT = ("ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "Roboto,Helvetica,Arial,sans-serif")
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

INK = "#eaf3ff"
DIM = "#8ba1bc"

# One hand-off per stage, in order. Long enough that the eye can follow a
# single dot rather than watch six things at once.
STEP = 1.15
CYCLE = COLS * STEP


STAGES = [
    # title, desc line 1, desc line 2, badge, accent, icon key
    ("Market Data",   "Raw bars from your",  "chosen source",     "Schwab · Rithmic · CSV", "#22d3ee", "stream"),
    ("Resample",      "Normalise & align",   "across timeframes", "One aggregator",         "#2dd4bf", "aggregate"),
    ("Analysis",      "Extract structure &", "market context",    "Waves · VWAP",           "#3b82f6", "analyse"),
    ("Strategy",      "Apply rules &",       "generate signals",  "Signal",                 "#a855f7", "strategy"),
    ("Paper Broker",  "Simulate fills,",     "slippage & costs",  "Fills · Costs",          "#f97316", "order"),
    ("Scored Result", "Objective metrics",   "you can check",     "Sharpe · Drawdown",      "#22c55e", "score"),
]


def icon(key: str, ink: str) -> list[str]:
    """
    Icons on a 24x24 grid, outlined rather than solid.

    Outlined on purpose: a filled silhouette inside a ring of thin strokes reads
    as a blob pasted on top, where an outline of the same weight as the rings
    looks like part of the module.
    """
    # `base` carries NO stroke-width, deliberately. It used to, and every path
    # that wanted a different weight then emitted the attribute twice -- which is
    # a fatal XML error, not a warning: the browser stopped parsing the document
    # at that line and rendered ten of the twenty-four text nodes.
    base = f'fill="none" stroke="{ink}" stroke-linecap="round"'
    w = 'stroke-width="1.7"'
    g = {
        # a data stream falling into a tray
        "stream": [
            f'<path d="M12 4v9.4" {base} {w}/>',
            f'<path d="M8.2 10.2 12 14l3.8-3.8" {base} {w} stroke-linejoin="round"/>',
            f'<path d="M4.6 15.6v2.8a1.8 1.8 0 0 0 1.8 1.8h11.2a1.8 1.8 0 0 0 1.8-1.8v-2.8" {base} {w}/>',
            f'<path d="M7.4 6.4h1.8M14.8 6.4h1.8" {base} {w} stroke-opacity=".55"/>',
        ],
        # a database with a tick: many bars in, one aggregator out
        "aggregate": [
            f'<ellipse cx="11.4" cy="6" rx="6.6" ry="2.6" {base} {w}/>',
            f'<path d="M4.8 6v9.6c0 1.4 3 2.6 6.6 2.6" {base} {w}/>',
            f'<path d="M18 6v4.4" {base} {w}/>',
            f'<path d="M4.8 10.8c0 1.4 3 2.6 6.6 2.6" {base} {w} stroke-opacity=".7"/>',
            f'<circle cx="17.2" cy="16.4" r="4.4" {base} {w}/>',
            f'<path d="M15.4 16.5 17 18l2.2-2.8" {base} {w} stroke-linejoin="round"/>',
        ],
        # a waveform under a lens
        "analyse": [
            f'<circle cx="10.6" cy="10.6" r="6.8" {base} {w}/>',
            f'<path d="M15.6 15.6 20.4 20.4" {base} {w}/>',
            f'<path d="M7 11.2c1.1-1.6 1.9-1.6 2.7 0 .9 1.7 1.7 1.7 2.5 0" {base} '
            f'stroke-width="1.5"/>',
        ],
        # a target with the two rules that aim it
        "strategy": [
            f'<circle cx="12" cy="12" r="7.6" {base} {w}/>',
            f'<circle cx="12" cy="12" r="3.4" {base} {w}/>',
            f'<circle cx="12" cy="12" r="1" fill="{ink}" stroke="none"/>',
            f'<path d="M12 1.6v2.8M12 19.6v2.8M1.6 12h2.8M19.6 12h2.8" {base} {w} '
            f'stroke-opacity=".7"/>',
        ],
        # a filled order: a slip with a total on it
        "order": [
            f'<path d="M6 3.6h12v16.2l-2.2-1.5-2 1.5-2-1.5-2 1.5L6 19.8z" {base} {w} '
            f'stroke-linejoin="round"/>',
            f'<path d="M9.2 8.2h5.6M9.2 11.4h5.6" {base} stroke-width="1.5"/>',
            f'<path d="M9.2 14.8h2.8" {base} stroke-width="1.5" stroke-opacity=".7"/>',
        ],
        # bars with the trend line over them
        "score": [
            f'<path d="M4.6 19.6V14M9.8 19.6v-8.4M15 19.6v-4.2M20.2 19.6V8" {base} '
            f'stroke-width="2.4"/>',
            f'<path d="M4.6 9.6 9.8 6l4 3.2L20.2 3.4" {base} stroke-width="1.5" '
            f'stroke-opacity=".8" stroke-linejoin="round"/>',
        ],
    }
    return g[key]


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def card_x(i: int) -> int:
    return PAD + i * (CARD_W + GAP)


def build() -> str:
    o: list[str] = []
    label = ("AutoTrader pipeline: market data is resampled, analysed, traded by "
             "the strategy, filled by the paper broker and scored")
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" role="img" aria-label="{label}">')

    o.append('<defs>'
             '<linearGradient id="pbg" x1="0" y1="0" x2="0" y2="1">'
             '<stop offset="0%" stop-color="#0d1424"/>'
             '<stop offset="100%" stop-color="#0a0f1c"/></linearGradient>'
             f'<marker id="pah" markerWidth="8" markerHeight="8" refX="6.4" refY="4" '
             f'orient="auto"><path d="M0 1 L7 4 L0 7 z" fill="{DIM}"/></marker>'
             '</defs>')
    o.append(f'<rect width="{W}" height="{H}" rx="16" fill="url(#pbg)"/>')
    o.append(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="16" '
             f'fill="none" stroke="#1e2a44"/>')

    mid = CARD_Y + 62          # the line the connectors run along

    # ── connectors, drawn under the cards ─────────────────────────────────
    for i in range(COLS - 1):
        x1 = card_x(i) + CARD_W
        x2 = card_x(i + 1)
        o.append(f'<line x1="{x1+3}" y1="{mid}" x2="{x2-5}" y2="{mid}" '
                 f'stroke="{DIM}" stroke-opacity="0.32" stroke-width="1.6" '
                 f'marker-end="url(#pah)"/>')
        o.append(f'<circle cx="{x1+3}" cy="{mid}" r="2.4" fill="{DIM}" '
                 f'fill-opacity="0.45"/>')
        # the hand-off: one dot, once, in stage order
        begin = i * STEP
        o.append(f'<circle cx="{x1+3}" cy="{mid}" r="3.2" '
                 f'fill="{STAGES[i][4]}" opacity="0">'
                 f'<animate attributeName="cx" values="{x1+3};{x2-6}" '
                 f'begin="{begin:.2f}s" dur="0.72s" calcMode="linear" '
                 f'repeatCount="indefinite" />'
                 f'<animate attributeName="opacity" values="0;1;1;0" '
                 f'keyTimes="0;0.12;0.8;1" begin="{begin:.2f}s" dur="0.72s" '
                 f'repeatCount="indefinite"/></circle>')

    # ── the six stages ────────────────────────────────────────────────────
    for i, (title, d1, d2, badge, accent, key) in enumerate(STAGES):
        x = card_x(i)
        cx = x + CARD_W / 2
        arrive = max(0.0, i * STEP - 0.12)

        o.append(f'<rect x="{x}" y="{CARD_Y}" width="{CARD_W}" height="{CARD_H}" '
                 f'rx="12" fill="#101a2c" stroke="{accent}" stroke-opacity="0.26"/>')
        # brightens as its dot lands -- the only state change on a card
        o.append(f'<rect x="{x}" y="{CARD_Y}" width="{CARD_W}" height="{CARD_H}" '
                 f'rx="12" fill="none" stroke="{accent}" stroke-width="1.6" '
                 f'stroke-opacity="0">'
                 f'<animate attributeName="stroke-opacity" '
                 f'values="0;0;0.85;0.28;0.28" '
                 f'keyTimes="0;{arrive/CYCLE:.4f};{(arrive+0.22)/CYCLE:.4f};'
                 f'{(arrive+0.9)/CYCLE:.4f};1" begin="0s" dur="{CYCLE}s" '
                 f'repeatCount="indefinite"/></rect>')

        # The step index. It was above each node in the previous version and is
        # kept, because six stages in a row only read as a SEQUENCE if they are
        # numbered -- the arrows say direction, the numbers say position.
        o.append(f'<text x="{x+12}" y="{CARD_Y+21}" font-family="{MONO}" '
                 f'font-size="10" font-weight="700" letter-spacing="0.5" '
                 f'fill="{accent}" fill-opacity="0.75">{i+1:02d}</text>')

        # a flat seat for the glyph -- no rings, no ticks
        o.append(f'<rect x="{cx-19:.1f}" y="{CARD_Y+16}" width="38" height="38" '
                 f'rx="10" fill="{accent}" fill-opacity="0.11"/>')
        o.append(f'<g transform="translate({cx-12:.1f},{CARD_Y+23}) scale(1)">'
                 + "".join(icon(key, accent)) + '</g>')

        o.append(f'<text x="{cx:.1f}" y="{CARD_Y+76}" text-anchor="middle" '
                 f'font-family="{FONT}" font-size="13" font-weight="700" '
                 f'fill="{INK}">{esc(title)}</text>')
        o.append(f'<text x="{cx:.1f}" y="{CARD_Y+94}" text-anchor="middle" '
                 f'font-family="{FONT}" font-size="10.5" fill="{DIM}">{esc(d1)}</text>')
        o.append(f'<text x="{cx:.1f}" y="{CARD_Y+108}" text-anchor="middle" '
                 f'font-family="{FONT}" font-size="10.5" fill="{DIM}">{esc(d2)}</text>')

        bw = CARD_W - 26
        o.append(f'<rect x="{x+13}" y="{CARD_Y+120}" width="{bw}" height="21" rx="6" '
                 f'fill="{accent}" fill-opacity="0.10"/>')
        o.append(f'<text x="{cx:.1f}" y="{CARD_Y+134.5}" text-anchor="middle" '
                 f'font-family="{MONO}" font-size="9" letter-spacing="0.2" '
                 f'fill="{accent}">{esc(badge)}</text>')

    o.append("</svg>")
    return "".join(o)


if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parents[1] / "pipeline.svg"
    svg = build()
    out.write_text(svg, encoding="utf-8")
    assert "animateTransform" not in svg, "no rotation in an architecture diagram"
    assert "feGaussianBlur" not in svg, "no glow in an architecture diagram"
    print(f"wrote {out}  ({len(svg):,} bytes, {svg.count('<animate')} animations, "
          f"{CYCLE:.1f}s loop)", file=sys.stderr)
