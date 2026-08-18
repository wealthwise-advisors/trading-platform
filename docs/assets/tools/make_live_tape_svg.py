"""
Generate docs/assets/live-tape.svg -- the Live Replay figure in the README.

TWO PANELS
----------
Top: the tape as it looks while following live -- candles, VWAP, the deviation
bands, and the forming bar the app deliberately withholds.
Bottom: the control flow that produces it -- load, play, reach the live edge,
start following, poll, and the closed-bar decision that either advances the tape
or leaves it alone.

WHY GENERATED
-------------
Nine nodes, ten connectors, twenty-four candles and forty-odd animations whose
begin times have to agree with each other. Hand-typed, that is how you get a dot
arriving at a node before the node lights up. Everything here derives from one
block of constants, so the timing is right by construction.

ACCURACY NOTES
--------------
* The band labels are +2sigma / -2sigma, NOT "+20". They are standard
  deviations of VWAP, which is what the app computes and what the previous
  figure said. The reference image appears to have lost the sigma.
* "Poll every 15s" is the real interval; it was 60s until the lag work, and the
  measured arrival is 5.6-15.6s after a bar closes.
* The forming bar really is withheld -- trim_to_closed_bars drops it -- so the
  caption states one withheld rather than implying the tape shows a live bar.

SMIL NOTES, LEARNED THE HARD WAY
--------------------------------
* Two <animate> on the SAME attribute of the SAME element: the later silently
  wins from t=0. One animation per attribute, always.
* An attribute that is animated must also be SET, or it renders at its default
  (cx defaults to 0) before its begin time arrives.
* GitHub proxies this image. SMIL survives; CSS animation and script do not.
"""
import math
import pathlib
import sys

W = 1280
H = 650

# ── panels ────────────────────────────────────────────────────────────────
PA = (16, 16, W - 32, 340)          # chart panel: x, y, w, h
PB = (16, 372, W - 32, 262)         # pipeline panel

# ── chart ─────────────────────────────────────────────────────────────────
# The plot stops well short of the right edge so the axis labels and the
# "forming" tag above the last bar have somewhere to sit.
PLOT_L, PLOT_R = 76, 1096
PLOT_T, PLOT_B = 130, 290
N_CANDLES = 24
PITCH = (PLOT_R - PLOT_L) / N_CANDLES
BODY_W = 13.5
AXIS_X = 1112

GREEN = "#22c55e"
RED = "#ef4444"
VWAP_C = "#c084fc"                  # the one place purple leads, as it always has
CYAN = "#22d3ee"
BLUE = "#3b82f6"
SKY = "#38bdf8"
PINK = "#ec4899"
VIOLET = "#a855f7"
INK = "#e8f2ff"
DIM = "#8ea3bd"

FONT = ("ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "Helvetica,Arial,sans-serif")
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

# ── pipeline ──────────────────────────────────────────────────────────────
CARD_W, CARD_H = 108, 88
CARD_GAP = 30
CARD_X0 = 42
FLOW_Y = PB[1] + 112                # centre line the cards sit on

# The decision node's energy ring expands to DIAMOND_R + 20. At the first
# attempt the node sat at 872 with R=62, so that ring reached back to x=776 and
# swallowed the right-hand edge of the Poll card. Placed and sized so the widest
# moment of the animation still clears the card.
DIAMOND_CX = 790
DIAMOND_R = 54
HALO_MAX = DIAMOND_R + 20

# The elbow both branches share before splitting up and down.
ELBOW_X = DIAMOND_CX + DIAMOND_R + 22

OUT_X, OUT_W, OUT_H = 950, 282, 72
YES_CY = FLOW_Y - 52
NO_CY = FLOW_Y + 56

# One pass of the travelling pulse.
HOP = 0.40
HOP_DUR = 1.5

STAGES = [
    ("Load Data",      None,               "download", CYAN),
    ("Play",           None,               "play",     BLUE),
    ("Live edge",      "reached",           "trend",    SKY),
    ("Follow live",    "starts by itself",  "follow",   GREEN),
    ("Poll every 15s", None,               "clock",    SKY),
]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def card_x(i: int) -> float:
    return CARD_X0 + i * (CARD_W + CARD_GAP)


def glyph(key: str, ink: str) -> list[str]:
    """Icons on a 24x24 grid. Silhouettes only -- the label does the naming."""
    g = {
        "download": [
            f'<path d="M12 3.4v9" stroke="{ink}" stroke-width="2.1" stroke-linecap="round"/>',
            f'<path d="M8.1 9.5 12 13.4 15.9 9.5" fill="none" stroke="{ink}" '
            f'stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>',
            f'<path d="M4.8 16.2v2.9a1.6 1.6 0 0 0 1.6 1.6h11.2a1.6 1.6 0 0 0 1.6-1.6v-2.9" '
            f'fill="none" stroke="{ink}" stroke-width="2.1" stroke-linecap="round"/>',
        ],
        "play": [f'<path d="M8.4 5.2 19 12 8.4 18.8z" fill="{ink}"/>'],
        "trend": [
            f'<path d="M3.6 17.6 9.4 11.8l3.6 3.6L20.4 8" fill="none" stroke="{ink}" '
            f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
            f'<path d="M15.4 8h5v5" fill="none" stroke="{ink}" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round"/>',
        ],
        "follow": [                                    # a refresh arc
            f'<path d="M20 12a8 8 0 1 1-2.4-5.7" fill="none" stroke="{ink}" '
            f'stroke-width="2.2" stroke-linecap="round"/>',
            f'<path d="M20 3.6V8h-4.4" fill="none" stroke="{ink}" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round"/>',
        ],
        "clock": [
            f'<circle cx="12" cy="12" r="8.6" fill="none" stroke="{ink}" stroke-width="2"/>',
            f'<path d="M12 7.2V12l3.4 2.1" fill="none" stroke="{ink}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"/>',
        ],
        "candles": [                                   # two bars with wicks
            f'<path d="M9 3.6v3M9 17.4v3M15.4 5.6v3M15.4 19v2" stroke="{ink}" '
            f'stroke-width="1.7" stroke-linecap="round"/>',
            f'<rect x="6.6" y="6.6" width="4.8" height="10.8" rx="1.1" fill="none" '
            f'stroke="{ink}" stroke-width="1.8"/>',
            f'<rect x="13" y="8.6" width="4.8" height="10.4" rx="1.1" fill="none" '
            f'stroke="{ink}" stroke-width="1.8"/>',
        ],
        "bars": [
            f'<rect x="4.4" y="13.4" width="3.7" height="6.4" rx="1.1" fill="{ink}"/>',
            f'<rect x="10.15" y="9.4" width="3.7" height="10.4" rx="1.1" fill="{ink}"/>',
            f'<rect x="15.9" y="5" width="3.7" height="14.8" rx="1.1" fill="{ink}"/>',
        ],
        "pulse": [
            f'<path d="M2.8 12h4l2.4-6 3.4 12 2.6-6h5.8" fill="none" stroke="{ink}" '
            f'stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>',
        ],
        # A broadcast mark: a dot with arcs opening left and right. The first
        # cut drew a satellite dish as three quarter-arcs springing from the
        # bottom-left corner, which at 24px rendered as a squiggle.
        "dish": [
            f'<circle cx="12" cy="12" r="2.6" fill="{ink}"/>',
            f'<path d="M7.3 7.3a6.6 6.6 0 0 0 0 9.4M16.7 7.3a6.6 6.6 0 0 1 0 9.4" '
            f'fill="none" stroke="{ink}" stroke-width="1.9" stroke-linecap="round" '
            f'opacity=".85"/>',
            f'<path d="M4 4a11.3 11.3 0 0 0 0 16M20 4a11.3 11.3 0 0 1 0 16" '
            f'fill="none" stroke="{ink}" stroke-width="1.9" stroke-linecap="round" '
            f'opacity=".5"/>',
        ],
    }
    return g[key]


def candles() -> list[tuple[float, float, float, float, bool]]:
    """
    A deterministic rising series: (cx, open_y, close_y, high_y, low_y).

    Deterministic on purpose -- a random walk would redraw the figure on every
    regeneration and every commit would show a diff in the candles.
    """
    seed = 20260818

    def rnd() -> float:
        nonlocal seed
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        return (seed >> 16) / 32768.0

    def y(f: float) -> float:
        return PLOT_B - f * (PLOT_B - PLOT_T)

    out = []
    for i in range(N_CANDLES):
        # The trend the bar sits on, and the bar's OWN body, chosen separately.
        # Deriving open and close from consecutive trend levels -- the obvious
        # way -- makes the body equal to one step of the trend, which was ~3px:
        # twenty-four plus signs instead of candles.
        trend = 0.26 + 0.46 * (i / (N_CANDLES - 1))
        trend += (rnd() - 0.5) * 0.075                  # the tape is not a ruler
        half = 0.030 + rnd() * 0.048                    # body half-height
        up = rnd() > 0.38                               # a rising tape, not only up
        if i == N_CANDLES - 1:
            # The forming bar is drawn green, and everything attached to it --
            # the glow, the expanding ring, the "forming" tag -- is green too.
            # Left to the series it came out red, so the bar said one thing and
            # its own halo said another.
            up = True
            half = 0.062                                # and a touch taller, as a live bar looks
        o = trend - half if up else trend + half
        c = trend + half if up else trend - half
        wick_hi = 0.014 + rnd() * 0.040
        wick_lo = 0.014 + rnd() * 0.040
        hi = max(o, c) + wick_hi
        lo = min(o, c) - wick_lo
        out.append((PLOT_L + PITCH * (i + 0.5), y(o), y(c), y(hi), y(lo), up))
    return out


def vwap_points(cs) -> list[tuple[float, float]]:
    """
    A smoothed mean of each bar's midpoint -- the line the bands hang off.

    Midpoints, not closes: with bodies of a realistic size a close-based mean
    zig-zags by the body height and stops looking like a volume-weighted average
    of anything.
    """
    mids = [(o + c) / 2 for _cx, o, c, _h, _l, _up in cs]
    pts = []
    for i, (cx, *_rest) in enumerate(cs):
        lo = max(0, i - 5)
        window = mids[lo:i + 1]
        pts.append((cx, sum(window) / len(window)))
    return pts


def build() -> str:
    out: list[str] = []
    a = out.append
    cs = candles()
    vw = vwap_points(cs)

    label = ("Live Replay: candles arrive on their own about fifteen seconds after "
             "each bar closes, with VWAP and its two-sigma bands, the forming bar "
             "withheld, and the polling loop that decides when the tape advances")
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
      f'viewBox="0 0 {W} {H}" role="img" aria-label="{label}">')

    # ══ defs ══════════════════════════════════════════════════════════════
    a("  <defs>")
    a('    <linearGradient id="panel" x1="0" y1="0" x2="0" y2="1">')
    a('      <stop offset="0%" stop-color="#0a1322"/>')
    a('      <stop offset="100%" stop-color="#060b14"/>')
    a("    </linearGradient>")
    a('    <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">')
    a('      <path d="M32 0H0v32" fill="none" stroke="#ffffff" stroke-opacity=".026" '
      'stroke-width="1"/>')
    a("    </pattern>")
    a(f'    <radialGradient id="wash" cx="50%" cy="0%" r="80%">')
    a(f'      <stop offset="0%" stop-color="{CYAN}" stop-opacity=".07"/>')
    a(f'      <stop offset="100%" stop-color="{CYAN}" stop-opacity="0"/>')
    a("    </radialGradient>")
    # A soft glow used behind the forming bar and the decision node.
    for name, col in (("gGreen", GREEN), ("gViolet", VIOLET), ("gCyan", CYAN)):
        a(f'    <radialGradient id="{name}" cx="50%" cy="50%" r="50%">')
        a(f'      <stop offset="0%" stop-color="{col}" stop-opacity=".55"/>')
        a(f'      <stop offset="60%" stop-color="{col}" stop-opacity=".13"/>')
        a(f'      <stop offset="100%" stop-color="{col}" stop-opacity="0"/>')
        a("    </radialGradient>")
    # Card surfaces: translucent, lighter at the top edge.
    a('    <linearGradient id="card" x1="0" y1="0" x2="0" y2="1">')
    a('      <stop offset="0%" stop-color="#ffffff" stop-opacity=".055"/>')
    a('      <stop offset="100%" stop-color="#ffffff" stop-opacity=".014"/>')
    a("    </linearGradient>")
    a(f'    <marker id="ar" viewBox="0 0 10 10" refX="8.4" refY="5" markerWidth="6.6" '
      f'markerHeight="6.6" orient="auto-start-reverse">')
    a(f'      <path d="M0 1 9 5 0 9z" fill="{SKY}"/>')
    a("    </marker>")
    a(f'    <marker id="arPink" viewBox="0 0 10 10" refX="8.4" refY="5" markerWidth="6.6" '
      f'markerHeight="6.6" orient="auto-start-reverse">')
    a(f'      <path d="M0 1 9 5 0 9z" fill="{PINK}"/>')
    a("    </marker>")
    a(f'    <marker id="arGreen" viewBox="0 0 10 10" refX="8.4" refY="5" markerWidth="6.6" '
      f'markerHeight="6.6" orient="auto-start-reverse">')
    a(f'      <path d="M0 1 9 5 0 9z" fill="{GREEN}"/>')
    a("    </marker>")
    a("  </defs>")

    # ══ panel A: the tape ═════════════════════════════════════════════════
    x, y, w, h = PA
    a(f'  <g>')
    a(f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="url(#panel)" '
      f'stroke="#ffffff" stroke-opacity=".075"/>')
    a(f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="url(#grid)"/>')
    a(f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="url(#wash)"/>')

    # header: dish icon, title, divider
    a(f'    <circle cx="{x + 40}" cy="{y + 38}" r="21" fill="url(#gCyan)" opacity=".8"/>')
    a(f'    <g transform="translate({x + 27} {y + 25}) scale(1.1)">')
    for p in glyph("dish", CYAN):
        a("      " + p)
    a("    </g>")
    a(f'    <text x="{x + 72}" y="{y + 46}" font-family="{FONT}" font-size="21" '
      f'font-weight="700" fill="{INK}">Live Replay</text>')
    a(f'    <line x1="{x + 22}" y1="{y + 68}" x2="{x + w - 22}" y2="{y + 68}" '
      f'stroke="#ffffff" stroke-opacity=".08" stroke-width="1"/>')

    # status: pulsing dot + wording
    sy = y + 90
    a(f'    <circle cx="{x + 34}" cy="{sy}" r="9" fill="url(#gGreen)">')
    a(f'      <animate attributeName="opacity" values=".35;1;.35" dur="2.4s" '
      f'repeatCount="indefinite"/>')
    a("    </circle>")
    a(f'    <circle cx="{x + 34}" cy="{sy}" r="4.2" fill="{GREEN}"/>')
    a(f'    <text x="{x + 50}" y="{sy + 4.6}" font-family="{FONT}" font-size="12.5" '
      f'font-weight="700" letter-spacing="1.1" fill="{GREEN}">FOLLOWING LIVE</text>')
    a(f'    <text x="{x + 186}" y="{sy + 4.6}" font-family="{FONT}" font-size="12.5" '
      f'fill="{DIM}">new bars arrive on their own — no reload, no clicking</text>')

    # ── deviation bands (dashed) and VWAP ──
    # Wide enough that the bars sit inside the channel. At 26 the bodies broke
    # through both bands, which would be a two-sigma excursion on every bar.
    band = 46.0
    upper = " ".join(f"{px:.1f},{py - band:.1f}" for px, py in vw)
    lower = " ".join(f"{px:.1f},{py + band:.1f}" for px, py in vw)
    line = " ".join(f"{px:.1f},{py:.1f}" for px, py in vw)
    a(f'    <polyline points="{upper}" fill="none" stroke="{VWAP_C}" '
      f'stroke-opacity=".55" stroke-width="1.5" stroke-dasharray="5 5"/>')
    a(f'    <polyline points="{lower}" fill="none" stroke="{VWAP_C}" '
      f'stroke-opacity=".55" stroke-width="1.5" stroke-dasharray="5 5"/>')
    # A wide, faint stroke under the VWAP reads as glow without a filter, which
    # GitHub's proxy renders more predictably.
    a(f'    <polyline points="{line}" fill="none" stroke="{VWAP_C}" '
      f'stroke-opacity=".16" stroke-width="7" stroke-linecap="round"/>')
    a(f'    <polyline points="{line}" fill="none" stroke="{VWAP_C}" '
      f'stroke-width="2" stroke-linecap="round"/>')

    # ── candles ──
    for i, (cx, oy, cyy, hy, ly, up) in enumerate(cs):
        last = i == N_CANDLES - 1
        col = GREEN if up else RED
        top = min(oy, cyy)
        hgt = max(2.4, abs(cyy - oy))
        bw = BODY_W + (3.4 if last else 0)
        if last:
            # The forming bar: glowing, pulsing, and the only one that moves.
            a(f'      <circle cx="{cx:.1f}" cy="{(top + hgt / 2):.1f}" r="30" '
              f'fill="url(#gGreen)" opacity=".55">')
            a(f'        <animate attributeName="opacity" values=".3;.8;.3" dur="1.8s" '
              f'repeatCount="indefinite"/>')
            a("      </circle>")
        a(f'    <line x1="{cx:.1f}" y1="{hy:.1f}" x2="{cx:.1f}" y2="{ly:.1f}" '
          f'stroke="{col}" stroke-opacity="{0.95 if last else 0.8}" '
          f'stroke-width="{1.9 if last else 1.5}" stroke-linecap="round"/>')
        a(f'    <rect x="{cx - bw / 2:.1f}" y="{top:.1f}" width="{bw:.1f}" '
          f'height="{hgt:.1f}" rx="2" fill="{col}" '
          f'fill-opacity="{0.95 if last else 0.85}">')
        if last:
            a(f'      <animate attributeName="fill-opacity" values=".62;1;.62" '
              f'dur="1.8s" repeatCount="indefinite"/>')
        a("    </rect>")
        if last:
            # The ring beneath it: the "still forming" tell.
            fy = ly + 12
            a(f'    <ellipse cx="{cx:.1f}" cy="{fy:.1f}" rx="6" ry="2.4" fill="none" '
              f'stroke="{GREEN}" stroke-width="1.4" opacity=".9">')
            a(f'      <animate attributeName="rx" values="6;21;6" dur="2.6s" '
              f'repeatCount="indefinite"/>')
            a("    </ellipse>")
            a(f'    <ellipse cx="{cx:.1f}" cy="{fy:.1f}" rx="6" ry="2.4" fill="none" '
              f'stroke="{GREEN}" stroke-width="1.2">')
            a(f'      <animate attributeName="opacity" values=".85;0;.85" dur="2.6s" '
              f'repeatCount="indefinite"/>')
            a("    </ellipse>")

    # ── right-hand axis ──
    vy = vw[-1][1]
    for lbl, ly_, col, weight, size in (
        ("+2σ", vy - band, VWAP_C, "600", "12"),
        ("VWAP", vy, VWAP_C, "700", "12.5"),
        ("−2σ", vy + band, VWAP_C, "600", "12"),
    ):
        a(f'    <text x="{AXIS_X}" y="{ly_ + 4.2:.1f}" font-family="{MONO}" '
          f'font-size="{size}" font-weight="{weight}" fill="{col}">{lbl}</text>')
    # "forming" belongs to the last BAR, not to the price axis. On the axis it
    # sat 22px under VWAP, which is where the -2sigma label already was, and the
    # two overlapped.
    lastx = cs[-1][0]
    lasty = min(cs[-1][1], cs[-1][2]) - 16
    a(f'    <text x="{lastx:.1f}" y="{lasty:.1f}" text-anchor="middle" '
      f'font-family="{FONT}" font-size="10.5" font-weight="600" letter-spacing=".4" '
      f'fill="{GREEN}">forming</text>')
    a(f'    <line x1="{PLOT_L - 6}" y1="{PLOT_B + 16}" x2="{PLOT_R + 6}" '
      f'y2="{PLOT_B + 16}" stroke="#ffffff" stroke-opacity=".10" stroke-width="1"/>')

    # ── the withheld-bar caption ──
    cy_pill = y + h - 32
    pill_w = 322
    a(f'    <rect x="{x + 22}" y="{cy_pill - 17}" width="{pill_w}" height="34" rx="17" '
      f'fill="url(#card)" stroke="{CYAN}" stroke-opacity=".34"/>')
    a(f'    <circle cx="{x + 43}" cy="{cy_pill}" r="11" fill="{CYAN}" fill-opacity=".14"/>')
    a(f'    <g transform="translate({x + 33} {cy_pill - 10}) scale(.83)">')
    for p in glyph("pulse", CYAN):
        a("      " + p)
    a("    </g>")
    a(f'    <text x="{x + 62}" y="{cy_pill + 4.4}" font-family="{FONT}" font-size="12.5" '
      f'fill="{INK}" fill-opacity=".92">the newest bar is still forming '
      f'(1 withheld)</text>')
    a("  </g>")

    # ══ panel B: the loop ═════════════════════════════════════════════════
    x, y, w, h = PB
    a(f'  <g>')
    a(f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="url(#panel)" '
      f'stroke="#ffffff" stroke-opacity=".075"/>')
    a(f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="url(#grid)"/>')

    # ── connectors between the five cards ──
    for i in range(len(STAGES) - 1):
        x1 = card_x(i) + CARD_W
        x2 = card_x(i + 1)
        a(f'    <line x1="{x1 + 5}" y1="{FLOW_Y}" x2="{x2 - 7}" y2="{FLOW_Y}" '
          f'stroke="{SKY}" stroke-opacity=".5" stroke-width="1.8" marker-end="url(#ar)"/>')
        a(f'    <circle cx="{x1 + 5:.1f}" cy="{FLOW_Y}" r="2.8" fill="#dff3ff">')
        a(f'      <animate attributeName="cx" from="{x1 + 5:.1f}" to="{x2 - 9:.1f}" '
          f'dur="{HOP_DUR}s" begin="{i * HOP:.2f}s" repeatCount="indefinite"/>')
        a("    </circle>")

    # card -> diamond
    x1 = card_x(4) + CARD_W
    x2 = DIAMOND_CX - DIAMOND_R
    a(f'    <line x1="{x1 + 5}" y1="{FLOW_Y}" x2="{x2 - 7}" y2="{FLOW_Y}" '
      f'stroke="{VIOLET}" stroke-opacity=".55" stroke-width="1.8" '
      f'marker-end="url(#ar)"/>')
    a(f'    <circle cx="{x1 + 5:.1f}" cy="{FLOW_Y}" r="2.8" fill="#e9d5ff">')
    a(f'      <animate attributeName="cx" from="{x1 + 5:.1f}" to="{x2 - 9:.1f}" '
      f'dur="{HOP_DUR}s" begin="{4 * HOP:.2f}s" repeatCount="indefinite"/>')
    a("    </circle>")

    # ── the five cards ──
    for i, (t1, t2, gkey, accent) in enumerate(STAGES):
        cx0 = card_x(i)
        cyc = FLOW_Y
        a(f'    <g>')
        a(f'      <rect x="{cx0}" y="{cyc - CARD_H / 2:.0f}" width="{CARD_W}" '
          f'height="{CARD_H}" rx="13" fill="url(#card)" stroke="{accent}" '
          f'stroke-opacity=".42" stroke-width="1.3">')
        a(f'        <animate attributeName="stroke-opacity" values=".42;.95;.42" '
          f'dur="{HOP_DUR + HOP * 4:.2f}s" begin="{i * HOP:.2f}s" '
          f'repeatCount="indefinite"/>')
        a("      </rect>")
        gx = cx0 + CARD_W / 2 - 13
        gy = cyc - CARD_H / 2 + 15
        a(f'      <g transform="translate({gx:.1f} {gy:.1f}) scale(1.08)">')
        for p in glyph(gkey, accent):
            a("        " + p)
        a("      </g>")
        ty = cyc + 20
        a(f'      <text x="{cx0 + CARD_W / 2:.1f}" y="{ty}" text-anchor="middle" '
          f'font-family="{FONT}" font-size="12.4" font-weight="600" '
          f'fill="{INK}">{esc(t1)}</text>')
        if t2:
            a(f'      <text x="{cx0 + CARD_W / 2:.1f}" y="{ty + 15}" '
              f'text-anchor="middle" font-family="{FONT}" font-size="11" '
              f'font-style="italic" fill="{accent}" '
              f'fill-opacity=".95">{esc(t2)}</text>')
        # the three processing pips under each card
        for k in range(3):
            px = cx0 + CARD_W / 2 + (k - 1) * 11
            a(f'      <circle cx="{px:.1f}" cy="{cyc + CARD_H / 2 + 13:.0f}" r="2.5" '
              f'fill="{accent}" opacity=".3">')
            a(f'        <animate attributeName="opacity" values=".3;1;.3" dur="1.35s" '
              f'begin="{i * HOP + k * 0.16:.2f}s" repeatCount="indefinite"/>')
            a("      </circle>")
        a("    </g>")

    # ── the decision node ──
    d = DIAMOND_R
    a(f'    <g>')
    a(f'      <circle cx="{DIAMOND_CX}" cy="{FLOW_Y}" r="{d + 18}" fill="url(#gViolet)" '
      f'opacity=".5">')
    a(f'        <animate attributeName="opacity" values=".28;.72;.28" dur="2.8s" '
      f'repeatCount="indefinite"/>')
    a("      </circle>")
    # the rotating halo: one dashed ring, one animateTransform
    ring_r = d + 11
    circ = 2 * math.pi * ring_r
    a(f'      <circle cx="{DIAMOND_CX}" cy="{FLOW_Y}" r="{ring_r}" fill="none" '
      f'stroke="{VIOLET}" stroke-opacity=".5" stroke-width="1.4" '
      f'stroke-dasharray="{circ * 0.055:.1f} {circ * 0.045:.1f}">')
    a(f'        <animateTransform attributeName="transform" type="rotate" '
      f'from="0 {DIAMOND_CX} {FLOW_Y}" to="360 {DIAMOND_CX} {FLOW_Y}" dur="14s" '
      f'repeatCount="indefinite"/>')
    a("      </circle>")
    # the energy ring: expands and fades outward
    a(f'      <circle cx="{DIAMOND_CX}" cy="{FLOW_Y}" r="{d}" fill="none" '
      f'stroke="{VIOLET}" stroke-width="1.6">')
    a(f'        <animate attributeName="r" values="{d};{HALO_MAX};{d}" dur="2.8s" '
      f'repeatCount="indefinite"/>')
    a("      </circle>")
    a(f'      <circle cx="{DIAMOND_CX}" cy="{FLOW_Y}" r="{d}" fill="none" '
      f'stroke="{VIOLET}" stroke-width="1.4">')
    a(f'        <animate attributeName="opacity" values=".7;0;.7" dur="2.8s" '
      f'repeatCount="indefinite"/>')
    a("      </circle>")
    a(f'      <path d="M{DIAMOND_CX} {FLOW_Y - d} L{DIAMOND_CX + d} {FLOW_Y} '
      f'L{DIAMOND_CX} {FLOW_Y + d} L{DIAMOND_CX - d} {FLOW_Y}z" fill="#0d1424" '
      f'fill-opacity=".92" stroke="{VIOLET}" stroke-opacity=".85" stroke-width="1.6"/>')
    a(f'      <g transform="translate({DIAMOND_CX - 12} {FLOW_Y - 30}) scale(1.0)">')
    for p in glyph("candles", "#e9d5ff"):
        a("        " + p)
    a("      </g>")
    a(f'      <text x="{DIAMOND_CX}" y="{FLOW_Y + 12}" text-anchor="middle" '
      f'font-family="{FONT}" font-size="12" font-weight="600" fill="{INK}">New '
      f'closed</text>')
    a(f'      <text x="{DIAMOND_CX}" y="{FLOW_Y + 27}" text-anchor="middle" '
      f'font-family="{FONT}" font-size="12" font-weight="600" fill="{INK}">bar?</text>')
    a("    </g>")

    # ── yes / no branches ──
    # Both branches leave the diamond's RIGHT vertex and share one short stub
    # before splitting. The first cut started each branch inside the halo and cut
    # diagonally across the node, which read as two stray lines over the diamond.
    bx = DIAMOND_CX + d
    for is_yes in (True, False):
        col = GREEN if is_yes else PINK
        mk = "arGreen" if is_yes else "arPink"
        cyb = YES_CY if is_yes else NO_CY
        lbl = "yes" if is_yes else "no"
        a(f'    <path d="M{bx + 3} {FLOW_Y} L{ELBOW_X} {FLOW_Y} L{ELBOW_X} {cyb} '
          f'L{OUT_X - 9} {cyb}" fill="none" stroke="{col}" stroke-opacity=".62" '
          f'stroke-width="1.8" stroke-linejoin="round" marker-end="url(#{mk})"/>')
        # The chip sits on the final horizontal run, clear of both the elbow and
        # the card it points at.
        cw = 33 if is_yes else 27
        chip_cx = (ELBOW_X + OUT_X) / 2
        a(f'    <rect x="{chip_cx - cw / 2:.1f}" y="{cyb - 13}" width="{cw}" '
          f'height="26" rx="8" fill="#0c1522" stroke="{col}" stroke-opacity=".75"/>')
        a(f'    <text x="{chip_cx:.1f}" y="{cyb + 4.6}" text-anchor="middle" '
          f'font-family="{FONT}" font-size="11.5" font-weight="700" '
          f'fill="{col}">{lbl}</text>')
        # A dot running the branch, so which way the flow went is visible.
        a(f'    <circle cx="{bx + 3}" cy="{FLOW_Y}" r="2.6" fill="{col}">')
        a(f'      <animate attributeName="cx" from="{bx + 3}" to="{OUT_X - 11}" '
          f'dur="1.3s" begin="{5 * HOP + (0 if is_yes else 0.65):.2f}s" '
          f'repeatCount="indefinite"/>')
        a(f'      <animate attributeName="cy" from="{FLOW_Y}" to="{cyb}" dur="1.3s" '
          f'begin="{5 * HOP + (0 if is_yes else 0.65):.2f}s" '
          f'repeatCount="indefinite"/>')
        a("    </circle>")

    # yes card: the tape advances
    a(f'    <g>')
    a(f'      <rect x="{OUT_X}" y="{YES_CY - OUT_H / 2:.0f}" width="{OUT_W}" '
      f'height="{OUT_H}" rx="13" fill="url(#card)" stroke="{GREEN}" '
      f'stroke-opacity=".5" stroke-width="1.3"/>')
    a(f'      <g transform="translate({OUT_X + 20} {YES_CY - 21:.0f}) scale(1.05)">')
    for p in glyph("bars", GREEN):
        a("        " + p)
    a("      </g>")
    a(f'      <text x="{OUT_X + 56}" y="{YES_CY - 4:.0f}" font-family="{FONT}" '
      f'font-size="14" font-weight="700" fill="{INK}">Tape advances</text>')
    a(f'      <text x="{OUT_X + 56}" y="{YES_CY + 15:.0f}" font-family="{FONT}" '
      f'font-size="11.5" fill="{DIM}">VWAP · bands · signals</text>')
    a(f'      <circle cx="{OUT_X + OUT_W - 18}" cy="{YES_CY + OUT_H / 2 - 12:.0f}" '
      f'r="4" fill="{GREEN}">')
    a(f'        <animate attributeName="opacity" values=".35;1;.35" dur="1.9s" '
      f'repeatCount="indefinite"/>')
    a("      </circle>")
    a("    </g>")

    # no card: still forming
    a(f'    <g>')
    a(f'      <rect x="{OUT_X}" y="{NO_CY - OUT_H / 2:.0f}" width="{OUT_W}" '
      f'height="{OUT_H}" rx="13" fill="url(#card)" stroke="{PINK}" '
      f'stroke-opacity=".5" stroke-width="1.3"/>')
    # a ring of dots, rotating: "nothing has closed yet"
    a(f'      <g transform="translate({OUT_X + 32} {NO_CY:.0f})">')
    a(f'        <g>')
    for k in range(8):
        ang = k * math.pi / 4
        a(f'          <circle cx="{13 * math.cos(ang):.1f}" '
          f'cy="{13 * math.sin(ang):.1f}" r="2.2" fill="{PINK}" '
          f'opacity="{0.28 + 0.09 * k:.2f}"/>')
    a(f'          <animateTransform attributeName="transform" type="rotate" '
      f'from="0 0 0" to="360 0 0" dur="3.4s" repeatCount="indefinite"/>')
    a("        </g>")
    a("      </g>")
    a(f'      <text x="{OUT_X + 60}" y="{NO_CY + 5:.0f}" font-family="{FONT}" '
      f'font-size="14" font-weight="700" fill="{INK}">Still forming…</text>')
    a("    </g>")

    # ── the return path: back to polling ──
    ret_y = y + h - 26
    poll_cx = card_x(4) + CARD_W / 2
    a(f'    <path d="M{OUT_X + 20} {NO_CY + OUT_H / 2 + 6:.0f} '
      f'L{OUT_X + 20} {ret_y} L{poll_cx} {ret_y} L{poll_cx} {FLOW_Y + CARD_H / 2 + 26:.0f}" '
      f'fill="none" stroke="{PINK}" stroke-opacity=".5" stroke-width="1.6" '
      f'stroke-dasharray="7 6" stroke-linejoin="round" marker-end="url(#arPink)">')
    # marching ants, which is what makes the loop read as a loop
    a(f'      <animate attributeName="stroke-dashoffset" from="26" to="0" dur="1.1s" '
      f'repeatCount="indefinite"/>')
    a("    </path>")
    a(f'    <text x="{(OUT_X + 20 + poll_cx) / 2:.0f}" y="{ret_y - 8}" '
      f'text-anchor="middle" font-family="{FONT}" font-size="11" fill="{PINK}" '
      f'fill-opacity=".75">poll again — the tape does not move</text>')
    a("  </g>")

    a("</svg>")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    dest = pathlib.Path(sys.argv[1])
    svg = build()
    dest.write_text(svg, encoding="utf-8")
    print(f"wrote {dest}  ({len(svg):,} chars)")
    print(f"  candles           : {N_CANDLES} (last one forming)")
    print(f"  pipeline cards    : {len(STAGES)} + 1 decision + 2 outcomes")
    print(f"  <animate>         : {svg.count('<animate ')}")
    print(f"  <animateTransform>: {svg.count('<animateTransform')}")
