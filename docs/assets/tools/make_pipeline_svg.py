"""
Generate docs/assets/pipeline.svg -- the six-stage pipeline in the README.

WHY GENERATED RATHER THAN HAND-WRITTEN
--------------------------------------
Six nodes, five links, thirty-odd animations and every one of them needs a
begin time that lines up with its neighbour. Hand-typing that is how you get a
dot that arrives before the ring it belongs to lights up. Here the geometry and
the timings are computed from one set of constants, so the wave is correct by
construction and stays correct when a column moves.

WHAT IS DELIBERATELY ABSENT
---------------------------
The hero title, the subtitle, the "6 STEPS" chip, the row of adjectives along
the bottom and the closing slogan. Those were framing for a poster. This is a
diagram in a README explaining what the program does, and it does not need to
assert that its own results are trustworthy.

ANIMATION NOTES, LEARNED THE HARD WAY
-------------------------------------
* Two <animate> on the SAME attribute of the SAME element: the later one
  silently wins from t=0. So each attribute gets exactly one animation.
* `pathLength` is not inherited, so it does nothing on a <g>. Dash maths is
  done here in Python against the real circumference instead.
* GitHub serves this through its image proxy; SMIL survives, scripts and CSS
  animation do not. Hence <animate>, not a stylesheet.
"""
import math
import pathlib
import sys

W = 1280
H = 270

PAD = 40
COLS = 6
COL_W = (W - 2 * PAD) / COLS          # 200
RING_R = 36
GLYPH = 26                            # glyph box, drawn on a 24 grid then scaled

Y_NUM = 40                            # number baseline
Y_STEM = (48, 60)
CY = 104                              # ring centre
Y_TITLE = 180
Y_DESC1 = 201
Y_DESC2 = 217
Y_BADGE = 229
BADGE_H = 26

# One full pass of the wave. Each link's dot begins a fifth of the way later,
# so a single pulse walks 01 -> 06 rather than five dots drifting.
LINK_DUR = 1.9
LINK_STAGGER = 0.42
CYCLE = LINK_DUR + LINK_STAGGER * (COLS - 2)   # 3.58s

STAGES = [
    # (title, desc line 1, desc line 2, badge, accent, glyph key)
    ("Market Data",   "Raw bars from your",  "chosen source",     "Schwab · Rithmic · CSV", "#38bdf8", "download"),
    ("Resample",      "Normalise & align",   "across timeframes", "One aggregator",         "#2dd4bf", "database"),
    ("Analysis",      "Extract structure &", "market context",    "Waves · VWAP",           "#3b82f6", "waves"),
    ("Strategy",      "Apply rules &",       "generate signals",  "Signal",                 "#a855f7", "target"),
    ("Paper Broker",  "Simulate fills,",     "slippage & costs",  "Fills · Costs",          "#f97316", "receipt"),
    ("Scored Result", "Objective metrics",   "you can check",     "Sharpe · Drawdown",      "#22c55e", "trend"),
]

FONT = ("ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "Helvetica,Arial,sans-serif")


def centre(i: int) -> float:
    """Horizontal centre of column i."""
    return PAD + COL_W * (i + 0.5)


def glyph_paths(key: str) -> list[str]:
    """
    The glyph, as <path>/<rect> strings on a 24x24 grid.

    Same shapes as the app's symbol marks use, for the same reason: at this size
    only a silhouette reads, and the title underneath does the naming.
    """
    if key == "download":                       # bars into a tray
        return [
            '<path d="M12 3.2v9.1" stroke="{ink}" stroke-width="2.1" stroke-linecap="round"/>',
            '<path d="M8 9.4 12 13.4 16 9.4" fill="none" stroke="{ink}" '
            'stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>',
            '<path d="M4.6 16v3.1a1.6 1.6 0 0 0 1.6 1.6h11.6a1.6 1.6 0 0 0 1.6-1.6V16" '
            'fill="none" stroke="{ink}" stroke-width="2.1" stroke-linecap="round"/>',
        ]
    if key == "database":                       # a cylinder
        return [
            '<ellipse cx="12" cy="6.3" rx="7.2" ry="2.9" fill="none" '
            'stroke="{ink}" stroke-width="2"/>',
            '<path d="M4.8 6.3v11.4c0 1.6 3.2 2.9 7.2 2.9s7.2-1.3 7.2-2.9V6.3" '
            'fill="none" stroke="{ink}" stroke-width="2" stroke-linecap="round"/>',
            '<path d="M4.8 12c0 1.6 3.2 2.9 7.2 2.9s7.2-1.3 7.2-2.9" fill="none" '
            'stroke="{ink}" stroke-width="2"/>',
        ]
    if key == "waves":
        return [
            '<path d="M3.4 8.4c1.7-2 3.4-2 5.1 0s3.4 2 5.1 0 3.4-2 5.1 0" fill="none" '
            'stroke="{ink}" stroke-width="2" stroke-linecap="round"/>',
            '<path d="M3.4 13.2c1.7-2 3.4-2 5.1 0s3.4 2 5.1 0 3.4-2 5.1 0" fill="none" '
            'stroke="{ink}" stroke-width="2" stroke-linecap="round"/>',
            '<path d="M3.4 18c1.7-2 3.4-2 5.1 0s3.4 2 5.1 0 3.4-2 5.1 0" fill="none" '
            'stroke="{ink}" stroke-width="2" stroke-linecap="round"/>',
        ]
    if key == "target":
        return [
            '<circle cx="12" cy="12" r="8.4" fill="none" stroke="{ink}" stroke-width="1.9"/>',
            '<circle cx="12" cy="12" r="4.6" fill="none" stroke="{ink}" stroke-width="1.9"/>',
            '<circle cx="12" cy="12" r="1.5" fill="{ink}"/>',
        ]
    if key == "receipt":                        # a till slip with a torn foot
        return [
            '<path d="M6 3.3h12v15.9l-2 1.5-2-1.5-2 1.5-2-1.5-2 1.5-2-1.5z" fill="none" '
            'stroke="{ink}" stroke-width="1.9" stroke-linejoin="round"/>',
            '<path d="M9.2 8h5.6M9.2 11.6h5.6M9.2 15.2h3.4" stroke="{ink}" '
            'stroke-width="1.7" stroke-linecap="round"/>',
        ]
    # trend: a rising line with an arrow head
    return [
        '<path d="M3.6 17.4 9.4 11.6l3.6 3.6L20.4 8" fill="none" stroke="{ink}" '
        'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
        '<path d="M15.4 8h5v5" fill="none" stroke="{ink}" stroke-width="2.2" '
        'stroke-linecap="round" stroke-linejoin="round"/>',
    ]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build() -> str:
    out: list[str] = []
    a = out.append

    label = ("AutoTrader pipeline: market data is resampled, analysed, traded by "
             "the strategy, filled by the paper broker and scored")
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
      f'viewBox="0 0 {W} {H}" role="img" aria-label="{label}">')

    # ── defs ───────────────────────────────────────────────────────────────
    a("  <defs>")
    a('    <linearGradient id="panel" x1="0" y1="0" x2="0" y2="1">')
    a('      <stop offset="0%" stop-color="#0a1220"/>')
    a('      <stop offset="100%" stop-color="#070c16"/>')
    a("    </linearGradient>")
    # The wash that lifts the middle of the panel off the page.
    a('    <radialGradient id="wash" cx="50%" cy="0%" r="78%">')
    a('      <stop offset="0%" stop-color="#38bdf8" stop-opacity=".085"/>')
    a('      <stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/>')
    a("    </radialGradient>")
    # A technical grid, faint enough to read as texture rather than lines.
    a('    <pattern id="grid" width="34" height="34" patternUnits="userSpaceOnUse">')
    a('      <path d="M34 0H0v34" fill="none" stroke="#ffffff" stroke-opacity=".028" '
      'stroke-width="1"/>')
    a("    </pattern>")
    # Per-stage soft glow behind each ring.
    for i, (_, _, _, _, accent, _) in enumerate(STAGES):
        a(f'    <radialGradient id="glow{i}" cx="50%" cy="50%" r="50%">')
        a(f'      <stop offset="0%" stop-color="{accent}" stop-opacity=".42"/>')
        a(f'      <stop offset="62%" stop-color="{accent}" stop-opacity=".10"/>')
        a(f'      <stop offset="100%" stop-color="{accent}" stop-opacity="0"/>')
        a("    </radialGradient>")
    # Each link fades between the two stages it joins.
    for i in range(COLS - 1):
        lo, hi = STAGES[i][4], STAGES[i + 1][4]
        a(f'    <linearGradient id="rail{i}" gradientUnits="userSpaceOnUse" '
          f'x1="{centre(i) + RING_R + 6:.1f}" y1="{CY}" '
          f'x2="{centre(i + 1) - RING_R - 6:.1f}" y2="{CY}">')
        a(f'      <stop offset="0%" stop-color="{lo}" stop-opacity=".62"/>')
        a(f'      <stop offset="100%" stop-color="{hi}" stop-opacity=".62"/>')
        a("    </linearGradient>")
    a("  </defs>")

    # ── panel ──────────────────────────────────────────────────────────────
    a(f'  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20" fill="url(#panel)" '
      'stroke="#ffffff" stroke-opacity=".07"/>')
    a(f'  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20" fill="url(#grid)"/>')
    a(f'  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20" fill="url(#wash)"/>')

    # ── links, behind the nodes ────────────────────────────────────────────
    # Each runs edge to edge between two rings, so nothing crosses a circle.
    for i in range(COLS - 1):
        x1 = centre(i) + RING_R + 6
        x2 = centre(i + 1) - RING_R - 6
        begin = i * LINK_STAGGER
        a(f'  <g>')
        a(f'    <line x1="{x1:.1f}" y1="{CY}" x2="{x2:.1f}" y2="{CY}" '
          f'stroke="url(#rail{i})" stroke-width="2" stroke-linecap="round"/>')
        # The pip at each end, in the colour of the ring it touches.
        a(f'    <circle cx="{x1:.1f}" cy="{CY}" r="2.6" fill="{STAGES[i][4]}"/>')
        a(f'    <circle cx="{x2:.1f}" cy="{CY}" r="2.6" fill="{STAGES[i + 1][4]}"/>')
        # The travelling dot.
        #
        # cx is set as well as animated, and that is not redundant: a <circle>
        # with no cx defaults to ZERO, and a link whose begin time has not
        # arrived yet still renders. The later links therefore parked a bright
        # dot against the far-left edge of the panel until their turn came. With
        # cx at the link start it waits on top of the start pip, where it cannot
        # be seen.
        a(f'    <circle cx="{x1:.1f}" cy="{CY}" r="3.4" fill="#e0f2fe" opacity=".95">')
        a(f'      <animate attributeName="cx" from="{x1:.1f}" to="{x2:.1f}" '
          f'dur="{LINK_DUR}s" begin="{begin:.2f}s" '
          f'repeatCount="indefinite" fill="freeze"/>')
        a("    </circle>")
        a("  </g>")

    # ── stages ─────────────────────────────────────────────────────────────
    circ = 2 * math.pi * RING_R
    arc = circ * 0.24

    for i, (title, d1, d2, badge, accent, gkey) in enumerate(STAGES):
        cx = centre(i)
        # This stage lights as the wave reaches it.
        pulse_begin = i * LINK_STAGGER

        a(f'  <g>')

        # number
        a(f'    <text x="{cx:.1f}" y="{Y_NUM}" text-anchor="middle" '
          f'font-family="{FONT}" font-size="19" font-weight="700" '
          f'letter-spacing="1.4" fill="{accent}">{i + 1:02d}</text>')
        # stem
        a(f'    <line x1="{cx:.1f}" y1="{Y_STEM[0]}" x2="{cx:.1f}" y2="{Y_STEM[1]}" '
          f'stroke="{accent}" stroke-opacity=".5" stroke-width="1.4"/>')

        # glow, pulsing as the wave arrives
        a(f'    <circle cx="{cx:.1f}" cy="{CY}" r="{RING_R + 16}" fill="url(#glow{i})" '
          f'opacity=".45">')
        a(f'      <animate attributeName="opacity" values=".45;1;.45" '
          f'dur="{CYCLE:.2f}s" begin="{pulse_begin:.2f}s" '
          f'repeatCount="indefinite" calcMode="spline" '
          f'keyTimes="0;0.22;1" keySplines="0.4 0 0.2 1;0.4 0 0.2 1"/>')
        a("    </circle>")

        # the seat the glyph sits on
        a(f'    <circle cx="{cx:.1f}" cy="{CY}" r="{RING_R - 6.5:.1f}" fill="#0b1424"/>')
        a(f'    <circle cx="{cx:.1f}" cy="{CY}" r="{RING_R - 6.5:.1f}" fill="{accent}" '
          f'fill-opacity=".10"/>')

        # the faint full ring
        a(f'    <circle cx="{cx:.1f}" cy="{CY}" r="{RING_R}" fill="none" '
          f'stroke="{accent}" stroke-opacity=".28" stroke-width="1.6"/>')

        # the bright arc, rotating. One dash, one very long gap, so exactly one
        # arc exists whatever the circumference rounds to.
        a(f'    <circle cx="{cx:.1f}" cy="{CY}" r="{RING_R}" fill="none" '
          f'stroke="{accent}" stroke-width="2.6" stroke-linecap="round" '
          f'stroke-dasharray="{arc:.1f} {circ:.1f}" '
          f'transform="rotate(-90 {cx:.1f} {CY})">')
        a(f'      <animateTransform attributeName="transform" type="rotate" '
          f'from="-90 {cx:.1f} {CY}" to="270 {cx:.1f} {CY}" dur="7s" '
          f'begin="{-i * 0.9:.1f}s" repeatCount="indefinite"/>')
        a("    </circle>")

        # glyph, centred in the ring
        s = GLYPH / 24
        gx = cx - GLYPH / 2
        gy = CY - GLYPH / 2
        a(f'    <g transform="translate({gx:.1f} {gy:.1f}) scale({s:.4f})">')
        for p in glyph_paths(gkey):
            a("      " + p.replace("{ink}", "#e8f4ff"))
        a("    </g>")

        # title
        a(f'    <text x="{cx:.1f}" y="{Y_TITLE}" text-anchor="middle" '
          f'font-family="{FONT}" font-size="15" font-weight="700" '
          f'fill="#eaf2ff">{esc(title)}</text>')
        # description, two balanced lines so the rows stay level
        for y, line in ((Y_DESC1, d1), (Y_DESC2, d2)):
            a(f'    <text x="{cx:.1f}" y="{y}" text-anchor="middle" '
              f'font-family="{FONT}" font-size="11.5" fill="#8ea3bd">'
              f'{esc(line)}</text>')

        # badge, width fitted to the text so the pill never clips
        bw = 15 + len(badge) * 6.05
        a(f'    <rect x="{cx - bw / 2:.1f}" y="{Y_BADGE}" width="{bw:.1f}" '
          f'height="{BADGE_H}" rx="{BADGE_H / 2:.0f}" fill="{accent}" '
          f'fill-opacity=".12" stroke="{accent}" stroke-opacity=".42"/>')
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
    print(f"wrote {dest}  ({len(svg):,} bytes)")
    print(f"  stages       : {len(STAGES)}")
    print(f"  links        : {COLS - 1}")
    print(f"  <animate>    : {svg.count('<animate ')}")
    print(f"  <animateTransform>: {svg.count('<animateTransform')}")
    print(f"  wave cycle   : {CYCLE:.2f}s")
