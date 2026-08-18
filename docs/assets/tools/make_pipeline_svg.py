"""
Generate docs/assets/pipeline.svg -- the six-stage pipeline in the README.

WHAT THIS IS TRYING TO BE
-------------------------
A live processing module per stage, not a circle with a picture in it. Each node
is five concentric layers -- atmospheric glow, an outer hairline, two
counter-rotating arcs, an illuminated inner ring and a seated disc -- with
technical ticks around the rim. The first version was one ring and one arc, and
it read as a flat infographic because that is what one ring is.

The connector matters as much as the nodes: a wide low-opacity bed for glow, a
bright core over it, a faint secondary rail below, illuminated pips at each end,
two particles per gap and a run of chevrons that light in sequence. The point is
that data should look like it is MOVING, which a static line between two dots
cannot do however well it is coloured.

WHY GENERATED
-------------
Six nodes, five links and ninety-odd animations whose begin times all have to
agree. Typed by hand that is how you get an arc spinning against its own pulse.
Everything derives from one block of constants, so the sequence is right by
construction and stays right when a column moves.

WHAT IS DELIBERATELY ABSENT
---------------------------
The hero title, the subtitle, the "6 STEPS" chip, the row of adjectives and the
closing slogan. Those were framing for a poster. This is a diagram in a README,
and it does not need to assert that its own results are trustworthy.

SMIL NOTES, LEARNED THE HARD WAY
--------------------------------
* Two <animate> on the SAME attribute of the SAME element: the later silently
  wins from t=0. One animation per attribute, always.
* An animated attribute must ALSO be set, or it renders at its default before
  its begin time arrives -- cx defaults to 0, which parks dots at the far edge.
* `pathLength` is not inherited, so it does nothing on a <g>. Dash maths is done
  here against the real circumference.
* GitHub proxies this image: SMIL survives, CSS animation and script do not.
"""
import math
import pathlib
import sys

W = 1280
H = 344

PAD = 34
COLS = 6
COL_W = (W - 2 * PAD) / COLS

# ── node geometry, outside in ─────────────────────────────────────────────
R_GLOW = 68          # atmospheric halo
R_TICK = 60          # the ring the technical ticks sit on
R_OUT = 52           # outer hairline + first arc
R_MID = 43           # second arc, counter-rotating
R_INNER = 34         # illuminated inner ring
R_DISC = 31          # the seat the icon sits on
ICON = 32

CY = 146             # node centre
Y_NUM = 42
Y_STEM = (52, 68)
Y_TITLE = 238
Y_DESC1 = 259
Y_DESC2 = 275
Y_BADGE = 288
BADGE_H = 26

# ── timing ───────────────────────────────────────────────────────────────
# One pass of the pulse from 01 to 06. Each stage lights STAGGER after the one
# before, and a link's particle takes LINK_DUR to cross, so the arrival and the
# activation coincide instead of drifting apart.
STAGGER = 0.62
LINK_DUR = 0.62
CYCLE = STAGGER * COLS          # 3.72s

FONT = ("ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "Helvetica,Arial,sans-serif")
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

INK = "#eaf3ff"
DIM = "#8ba1bc"

STAGES = [
    # title, desc line 1, desc line 2, badge, accent, icon key
    ("Market Data",   "Raw bars from your",  "chosen source",     "Schwab · Rithmic · CSV", "#22d3ee", "stream"),
    ("Resample",      "Normalise & align",   "across timeframes", "One aggregator",         "#2dd4bf", "aggregate"),
    ("Analysis",      "Extract structure &", "market context",    "Waves · VWAP",           "#3b82f6", "analyse"),
    ("Strategy",      "Apply rules &",       "generate signals",  "Signal",                 "#a855f7", "strategy"),
    ("Paper Broker",  "Simulate fills,",     "slippage & costs",  "Fills · Costs",          "#f97316", "order"),
    ("Scored Result", "Objective metrics",   "you can check",     "Sharpe · Drawdown",      "#22c55e", "score"),
]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def centre(i: int) -> float:
    return PAD + COL_W * (i + 0.5)


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


def build() -> str:
    out: list[str] = []
    a = out.append

    label = ("AutoTrader pipeline: market data is resampled, analysed, traded by "
             "the strategy, filled by the paper broker and scored")
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
      f'viewBox="0 0 {W} {H}" role="img" aria-label="{label}">')

    # ══ defs ══════════════════════════════════════════════════════════════
    a("  <defs>")
    a('    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">')
    a('      <stop offset="0%" stop-color="#070d18"/>')
    a('      <stop offset="55%" stop-color="#0a1424"/>')
    a('      <stop offset="100%" stop-color="#05090f"/>')
    a("    </linearGradient>")
    # Two grid scales: a fine mesh and a heavier one over it, which is what makes
    # a technical background read as depth rather than graph paper.
    a('    <pattern id="fine" width="16" height="16" patternUnits="userSpaceOnUse">')
    a('      <path d="M16 0H0v16" fill="none" stroke="#8ec5ff" stroke-opacity=".030" '
      'stroke-width=".6"/>')
    a("    </pattern>")
    a('    <pattern id="coarse" width="80" height="80" patternUnits="userSpaceOnUse">')
    a('      <path d="M80 0H0v80" fill="none" stroke="#8ec5ff" stroke-opacity=".045" '
      'stroke-width="1"/>')
    a("    </pattern>")
    # Atmosphere: a wash from above, and a vignette that darkens the corners so
    # the middle of the band sits forward.
    a('    <radialGradient id="sky" cx="50%" cy="-8%" r="88%">')
    a('      <stop offset="0%" stop-color="#38bdf8" stop-opacity=".13"/>')
    a('      <stop offset="60%" stop-color="#3b82f6" stop-opacity=".035"/>')
    a('      <stop offset="100%" stop-color="#3b82f6" stop-opacity="0"/>')
    a("    </radialGradient>")
    a('    <radialGradient id="vig" cx="50%" cy="50%" r="72%">')
    a('      <stop offset="55%" stop-color="#000000" stop-opacity="0"/>')
    a('      <stop offset="100%" stop-color="#000000" stop-opacity=".55"/>')
    a("    </radialGradient>")

    for i, s in enumerate(STAGES):
        accent = s[4]
        # The node's halo.
        a(f'    <radialGradient id="halo{i}" cx="50%" cy="50%" r="50%">')
        a(f'      <stop offset="0%" stop-color="{accent}" stop-opacity=".40"/>')
        a(f'      <stop offset="45%" stop-color="{accent}" stop-opacity=".13"/>')
        a(f'      <stop offset="100%" stop-color="{accent}" stop-opacity="0"/>')
        a("    </radialGradient>")
        # The disc under the icon: lit from the top, so the module looks solid.
        a(f'    <linearGradient id="disc{i}" x1="0" y1="0" x2="0" y2="1">')
        a(f'      <stop offset="0%" stop-color="{accent}" stop-opacity=".20"/>')
        a(f'      <stop offset="100%" stop-color="{accent}" stop-opacity=".045"/>')
        a("    </linearGradient>")

    # Each link fades from the stage it leaves to the stage it enters.
    for i in range(COLS - 1):
        x1 = centre(i) + R_OUT + 8
        x2 = centre(i + 1) - R_OUT - 8
        a(f'    <linearGradient id="rail{i}" gradientUnits="userSpaceOnUse" '
          f'x1="{x1:.1f}" y1="{CY}" x2="{x2:.1f}" y2="{CY}">')
        a(f'      <stop offset="0%" stop-color="{STAGES[i][4]}" stop-opacity=".85"/>')
        a(f'      <stop offset="100%" stop-color="{STAGES[i + 1][4]}" stop-opacity=".85"/>')
        a("    </linearGradient>")
    a("  </defs>")

    # ══ ground ════════════════════════════════════════════════════════════
    a(f'  <rect width="{W}" height="{H}" rx="22" fill="url(#bg)"/>')
    a(f'  <rect width="{W}" height="{H}" rx="22" fill="url(#fine)"/>')
    a(f'  <rect width="{W}" height="{H}" rx="22" fill="url(#coarse)"/>')
    a(f'  <rect width="{W}" height="{H}" rx="22" fill="url(#sky)"/>')

    # Motes in the air: static, faint, unevenly placed. They cost nothing and
    # they stop the large empty areas reading as flat paint.
    seed = 71624
    for _ in range(46):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        px = 20 + (seed >> 9) % (W - 40)
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        py = 16 + (seed >> 9) % (H - 32)
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        rr = 0.7 + ((seed >> 11) % 100) / 110.0
        op = 0.05 + ((seed >> 5) % 100) / 620.0
        a(f'  <circle cx="{px}" cy="{py}" r="{rr:.2f}" fill="#bfe3ff" '
          f'opacity="{op:.3f}"/>')

    a(f'  <rect width="{W}" height="{H}" rx="22" fill="url(#vig)"/>')
    a(f'  <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="22" fill="none" '
      f'stroke="#7dd3fc" stroke-opacity=".13"/>')

    # Corner brackets: instrument-panel detail, not lettering.
    for cx0, cy0, sx, sy in ((16, 16, 1, 1), (W - 16, 16, -1, 1),
                             (16, H - 16, 1, -1), (W - 16, H - 16, -1, -1)):
        a(f'  <path d="M{cx0} {cy0 + sy * 26} V{cy0 + sy * 8} '
          f'Q{cx0} {cy0} {cx0 + sx * 8} {cy0} H{cx0 + sx * 26}" fill="none" '
          f'stroke="#7dd3fc" stroke-opacity=".34" stroke-width="1.6"/>')

    # ══ links ═════════════════════════════════════════════════════════════
    for i in range(COLS - 1):
        x1 = centre(i) + R_OUT + 8
        x2 = centre(i + 1) - R_OUT - 8
        begin = i * STAGGER
        a("  <g>")
        # A wide, very faint stroke under the core reads as glow. Doing it this
        # way rather than with a blur filter keeps it predictable through
        # GitHub's proxy, which is not consistent about filters.
        a(f'    <line x1="{x1:.1f}" y1="{CY}" x2="{x2:.1f}" y2="{CY}" '
          f'stroke="url(#rail{i})" stroke-opacity=".16" stroke-width="9" '
          f'stroke-linecap="round"/>')
        a(f'    <line x1="{x1:.1f}" y1="{CY}" x2="{x2:.1f}" y2="{CY}" '
          f'stroke="url(#rail{i})" stroke-width="2.1" stroke-linecap="round"/>')
        # The secondary rail: a hairline below the core, dashed, which is the
        # detail that stops the connector looking like a drawn line.
        a(f'    <line x1="{x1 + 6:.1f}" y1="{CY + 6}" x2="{x2 - 6:.1f}" y2="{CY + 6}" '
          f'stroke="url(#rail{i})" stroke-opacity=".30" stroke-width="1" '
          f'stroke-dasharray="3 5"/>')
        # Illuminated pips where the link meets each ring.
        for px, col in ((x1, STAGES[i][4]), (x2, STAGES[i + 1][4])):
            a(f'    <circle cx="{px:.1f}" cy="{CY}" r="4.6" fill="{col}" '
              f'fill-opacity=".28"/>')
            a(f'    <circle cx="{px:.1f}" cy="{CY}" r="2.3" fill="{col}"/>')
        # Two particles per gap, the second half a beat behind, so the flow
        # reads as a stream rather than a single ball.
        for k, (rr, op) in enumerate(((3.3, 1.0), (2.1, 0.6))):
            a(f'    <circle cx="{x1:.1f}" cy="{CY}" r="{rr}" fill="#f0faff" '
              f'opacity="{op}">')
            a(f'      <animate attributeName="cx" from="{x1:.1f}" to="{x2:.1f}" '
              f'dur="{LINK_DUR}s" begin="{begin + k * 0.16:.2f}s" '
              f'repeatCount="indefinite"/>')
            a("    </circle>")
        # Chevrons below the rail, lighting left to right.
        cxm = (x1 + x2) / 2
        for k in range(3):
            chx = cxm + (k - 1) * 9
            a(f'      <path d="M{chx:.1f} {CY + 20} l4.4 4.4 -4.4 4.4" fill="none" '
              f'stroke="{STAGES[i + 1][4]}" stroke-width="1.8" stroke-linecap="round" '
              f'stroke-linejoin="round" opacity=".22">')
            a(f'        <animate attributeName="opacity" values=".22;.95;.22" '
              f'dur="{CYCLE:.2f}s" begin="{begin + k * 0.13:.2f}s" '
              f'repeatCount="indefinite"/>')
            a("      </path>")
        a("  </g>")

    # ══ nodes ═════════════════════════════════════════════════════════════
    for i, (title, d1, d2, badge, accent, ikey) in enumerate(STAGES):
        cx = centre(i)
        begin = i * STAGGER
        a("  <g>")

        # 1. atmosphere
        a(f'    <circle cx="{cx:.1f}" cy="{CY}" r="{R_GLOW}" fill="url(#halo{i})" '
          f'opacity=".5">')
        a(f'      <animate attributeName="opacity" values=".5;1;.5" '
          f'dur="{CYCLE:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite" '
          f'calcMode="spline" keyTimes="0;0.16;1" '
          f'keySplines="0.3 0 0.2 1;0.4 0 0.3 1"/>')
        a("    </circle>")

        # 2. technical ticks on the rim -- top and bottom arcs only.
        #
        # A full ring of them put ticks at 0 and 180 degrees, which is exactly
        # where the connector attaches, so the link's illuminated pip landed on
        # top of a tick. Skipping everything within 30 degrees of horizontal
        # reads as deliberate instrumentation rather than a gap.
        HORIZONTAL = {2, 3, 4, 8, 9, 10}
        for k in range(12):
            if k in HORIZONTAL:
                continue
            ang = math.radians(k * 30 - 90)
            ln = 8 if k % 3 == 0 else 5
            xa = cx + R_TICK * math.cos(ang)
            ya = CY + R_TICK * math.sin(ang)
            xb = cx + (R_TICK + ln) * math.cos(ang)
            yb = CY + (R_TICK + ln) * math.sin(ang)
            a(f'    <line x1="{xa:.1f}" y1="{ya:.1f}" x2="{xb:.1f}" y2="{yb:.1f}" '
              f'stroke="{accent}" stroke-opacity="{0.62 if k % 3 == 0 else 0.32}" '
              f'stroke-width="1.5" stroke-linecap="round"/>')

        # 3. two hairlines: one at the arc radius, one out at the tick radius.
        #    Two concentric hairlines is what gives the module its depth; one
        #    ring, however bright, reads flat.
        a(f'    <circle cx="{cx:.1f}" cy="{CY}" r="{R_TICK}" fill="none" '
          f'stroke="{accent}" stroke-opacity=".13" stroke-width="1"/>')
        a(f'    <circle cx="{cx:.1f}" cy="{CY}" r="{R_OUT}" fill="none" '
          f'stroke="{accent}" stroke-opacity=".30" stroke-width="1.3"/>')

        # 4. two arcs, counter-rotating. Opposed directions is most of why the
        #    node reads as a mechanism rather than a spinning ring.
        for rad, frac, sw, dur, direction in ((R_OUT, 0.30, 3.8, 8.0, 1),
                                              (R_MID, 0.19, 2.5, 6.0, -1)):
            circ = 2 * math.pi * rad
            frm = 0 if direction > 0 else 360
            to = 360 if direction > 0 else 0
            a(f'    <circle cx="{cx:.1f}" cy="{CY}" r="{rad}" fill="none" '
              f'stroke="{accent}" stroke-width="{sw}" stroke-linecap="round" '
              f'stroke-dasharray="{circ * frac:.1f} {circ:.1f}" '
              f'transform="rotate({-90 + i * 47} {cx:.1f} {CY})">')
            a(f'      <animateTransform attributeName="transform" type="rotate" '
              f'from="{frm} {cx:.1f} {CY}" to="{to} {cx:.1f} {CY}" dur="{dur}s" '
              f'begin="{-i * 1.1:.1f}s" repeatCount="indefinite"/>')
            a("    </circle>")

        # 5. illuminated inner ring, brightening as the pulse lands
        a(f'    <circle cx="{cx:.1f}" cy="{CY}" r="{R_INNER}" fill="none" '
          f'stroke="{accent}" stroke-width="1.7" stroke-opacity=".52">')
        a(f'      <animate attributeName="stroke-opacity" values=".45;1;.45" '
          f'dur="{CYCLE:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite"/>')
        a("    </circle>")

        # 6. the seat
        a(f'    <circle cx="{cx:.1f}" cy="{CY}" r="{R_DISC}" fill="#070e1a"/>')
        a(f'    <circle cx="{cx:.1f}" cy="{CY}" r="{R_DISC}" fill="url(#disc{i})"/>')

        # 7. a ring that expands out of the node on activation
        a(f'    <circle cx="{cx:.1f}" cy="{CY}" r="{R_INNER}" fill="none" '
          f'stroke="{accent}" stroke-width="1.6" opacity="0">')
        a(f'      <animate attributeName="r" values="{R_INNER};{R_GLOW - 4}" '
          f'dur="{CYCLE:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite" '
          f'keyTimes="0;1" calcMode="spline" keySplines="0.2 0 0.3 1"/>')
        a("    </circle>")
        a(f'    <circle cx="{cx:.1f}" cy="{CY}" r="{R_INNER}" fill="none" '
          f'stroke="{accent}" stroke-width="1.6" opacity="0">')
        a(f'      <animate attributeName="opacity" values="0;.75;0" '
          f'dur="{CYCLE:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite" '
          f'keyTimes="0;0.06;0.30"/>')
        a("    </circle>")

        # 8. the icon
        s = ICON / 24
        a(f'    <g transform="translate({cx - ICON / 2:.1f} {CY - ICON / 2:.1f}) '
          f'scale({s:.4f})">')
        for p in icon(ikey, "#f2f9ff"):
            a("      " + p)
        a("    </g>")

        # ── number, stem, labels ──
        a(f'    <text x="{cx:.1f}" y="{Y_NUM}" text-anchor="middle" '
          f'font-family="{MONO}" font-size="20" font-weight="700" '
          f'letter-spacing="1.6" fill="{accent}">{i + 1:02d}</text>')
        a(f'    <line x1="{cx:.1f}" y1="{Y_STEM[0]}" x2="{cx:.1f}" y2="{Y_STEM[1]}" '
          f'stroke="{accent}" stroke-opacity=".45" stroke-width="1.2" '
          f'stroke-dasharray="2 3"/>')
        a(f'    <text x="{cx:.1f}" y="{Y_TITLE}" text-anchor="middle" '
          f'font-family="{FONT}" font-size="15.5" font-weight="700" '
          f'letter-spacing=".1" fill="{INK}">{esc(title)}</text>')
        for yy, line in ((Y_DESC1, d1), (Y_DESC2, d2)):
            a(f'    <text x="{cx:.1f}" y="{yy}" text-anchor="middle" '
              f'font-family="{FONT}" font-size="11.5" fill="{DIM}">{esc(line)}</text>')
        bw = 15 + len(badge) * 6.05
        a(f'    <rect x="{cx - bw / 2:.1f}" y="{Y_BADGE}" width="{bw:.1f}" '
          f'height="{BADGE_H}" rx="{BADGE_H / 2:.0f}" fill="{accent}" '
          f'fill-opacity=".11" stroke="{accent}" stroke-opacity=".40"/>')
        a(f'    <text x="{cx:.1f}" y="{Y_BADGE + 17.4:.1f}" text-anchor="middle" '
          f'font-family="{FONT}" font-size="10.6" font-weight="600" '
          f'fill="{accent}">{esc(badge)}</text>')
        a("  </g>")

    a("</svg>")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    dest = pathlib.Path(sys.argv[1])
    svg = build()
    dest.write_text(svg, encoding="utf-8")
    print(f"wrote {dest}  ({len(svg):,} chars)")
    print(f"  stages            : {len(STAGES)}   links: {COLS - 1}")
    print(f"  ring layers/node  : glow, ticks, hairline, 2 arcs, inner, disc, burst")
    print(f"  <animate>         : {svg.count('<animate ')}")
    print(f"  <animateTransform>: {svg.count('<animateTransform')}")
    print(f"  pulse cycle       : {CYCLE:.2f}s")
