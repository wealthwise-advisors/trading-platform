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
H = 740

# ── panels ────────────────────────────────────────────────────────────────
PA = (16, 16, W - 32, 340)          # chart panel: x, y, w, h
PB = (16, 372, W - 32, 352)         # flowchart panel

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
# Cards are square-ish now, with the icon high and the label under it, and a
# status light plus a floor pool below. The pool is what stops the row reading
# as shapes floating on a flat backdrop, and it needs vertical room.
CARD_W, CARD_H = 108, 112
CARD_GAP = 26
CARD_X0 = 40
FLOW_Y = PB[1] + 168                # centre line the cards sit on

# The decision node's energy ring expands to DIAMOND_R + 20. At the first
# attempt the node sat at 872 with R=62, so that ring reached back to x=776 and
# swallowed the right-hand edge of the Poll card. Placed and sized so the widest
# moment of the animation still clears the card.
# The decision node is the focal point, so it is larger than anything else and
# carries three halo rings. Its widest ring reaches DIAMOND_R + 34; the last
# card ends at 40 + 5*134 = 710, so the node clears it.
DIAMOND_CX = 800
DIAMOND_R = 66
HALO_MAX = DIAMOND_R + 34

# The elbow both branches share before splitting up and down.
ELBOW_X = DIAMOND_CX + DIAMOND_R + 24

OUT_X, OUT_W, OUT_H = 962, 278, 78
YES_CY = FLOW_Y - 62
NO_CY = FLOW_Y + 66

# One pass of the travelling pulse.
#
# The five cards fire at 0, HOP, 2*HOP, 3*HOP, 4*HOP; the decision node at
# 5*HOP; the outcomes just after. CYCLE is the full loop, long enough that the
# last card has gone dark before the first lights again -- otherwise the wave
# has no head and no tail and reads as everything blinking at once.
HOP = 0.40
HOP_DUR = 1.5
CYCLE = 4.0

STAGES = [
    ("Load Data",      None,               "download", CYAN),
    ("Play",           None,               "play",     BLUE),
    ("Live edge",      "reached",           "trend",    SKY),
    ("Follow live",    "starts by itself",  "follow",   GREEN),
    ("Poll every 15s", None,               "clock",    SKY),
]


# ── the activation envelope ───────────────────────────────────────────────
# Every layer of a card brightens off THIS, so they cannot peak at different
# moments. Fast attack, slower decay, then dark: what switching on looks like,
# as opposed to breathing.
PULSE_KEYTIMES = "0;0.10;0.38;1"
PULSE_SPLINES = "0.15 0 0.1 1;0.35 0 0.45 1;0 0 1 1"


def pulse_b(attr: str, lo: float, hi: float, begin: float) -> str:
    """One <animate> for one attribute, on the shared activation envelope."""
    return (f'<animate attributeName="{attr}" values="{lo};{hi};{lo};{lo}" '
            f'dur="{CYCLE:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite" '
            f'calcMode="spline" keyTimes="{PULSE_KEYTIMES}" '
            f'keySplines="{PULSE_SPLINES}"/>')


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
            # Axes plus a series with its points marked. The first cut was the
            # bare arrow, which reads as "up", not as "the edge of a chart".
            f'<path d="M4 3.6v16.8h16.4" fill="none" stroke="{ink}" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" stroke-opacity=".65"/>',
            f'<path d="M6.8 16.4 10.6 11.6l3.3 2.6 5.1-6.8" fill="none" stroke="{ink}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
            f'<circle cx="10.6" cy="11.6" r="1.5" fill="{ink}"/>',
            f'<circle cx="19" cy="7.4" r="1.8" fill="{ink}"/>',
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
    a('    <radialGradient id="wash" cx="50%" cy="0%" r="80%">')
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
    a('    <pattern id="fineGrid" width="16" height="16" patternUnits="userSpaceOnUse">')
    a('      <path d="M16 0H0v16" fill="none" stroke="#8ec5ff" stroke-opacity=".028" '
      'stroke-width=".6"/>')
    a("    </pattern>")
    a('    <radialGradient id="skyB" cx="50%" cy="0%" r="85%">')
    a(f'      <stop offset="0%" stop-color="{CYAN}" stop-opacity=".10"/>')
    a(f'      <stop offset="60%" stop-color="{BLUE}" stop-opacity=".03"/>')
    a(f'      <stop offset="100%" stop-color="{BLUE}" stop-opacity="0"/>')
    a("    </radialGradient>")
    a('    <radialGradient id="vigB" cx="50%" cy="50%" r="72%">')
    a('      <stop offset="55%" stop-color="#000000" stop-opacity="0"/>')
    a('      <stop offset="100%" stop-color="#000000" stop-opacity=".45"/>')
    a("    </radialGradient>")
    a('    <linearGradient id="cardSurf" x1="0" y1="0" x2="0" y2="1">')
    a('      <stop offset="0%" stop-color="#ffffff" stop-opacity=".075"/>')
    a('      <stop offset="100%" stop-color="#ffffff" stop-opacity=".016"/>')
    a("    </linearGradient>")
    a('    <marker id="arViolet" viewBox="0 0 10 10" refX="8.4" refY="5" '
      'markerWidth="6.6" markerHeight="6.6" orient="auto-start-reverse">')
    a(f'      <path d="M0 1 9 5 0 9z" fill="{VIOLET}"/>')
    a("    </marker>")
    a('    <marker id="ar" viewBox="0 0 10 10" refX="8.4" refY="5" markerWidth="6.6" '
      'markerHeight="6.6" orient="auto-start-reverse">')
    a(f'      <path d="M0 1 9 5 0 9z" fill="{SKY}"/>')
    a("    </marker>")
    a('    <marker id="arPink" viewBox="0 0 10 10" refX="8.4" refY="5" markerWidth="6.6" '
      'markerHeight="6.6" orient="auto-start-reverse">')
    a(f'      <path d="M0 1 9 5 0 9z" fill="{PINK}"/>')
    a("    </marker>")
    a('    <marker id="arGreen" viewBox="0 0 10 10" refX="8.4" refY="5" markerWidth="6.6" '
      'markerHeight="6.6" orient="auto-start-reverse">')
    a(f'      <path d="M0 1 9 5 0 9z" fill="{GREEN}"/>')
    a("    </marker>")
    a("  </defs>")

    # ══ panel A: the tape ═════════════════════════════════════════════════
    x, y, w, h = PA
    a('  <g>')
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
    a('      <animate attributeName="opacity" values=".35;1;.35" dur="2.4s" '
      'repeatCount="indefinite"/>')
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
            a('        <animate attributeName="opacity" values=".3;.8;.3" dur="1.8s" '
              'repeatCount="indefinite"/>')
            a("      </circle>")
        a(f'    <line x1="{cx:.1f}" y1="{hy:.1f}" x2="{cx:.1f}" y2="{ly:.1f}" '
          f'stroke="{col}" stroke-opacity="{0.95 if last else 0.8}" '
          f'stroke-width="{1.9 if last else 1.5}" stroke-linecap="round"/>')
        a(f'    <rect x="{cx - bw / 2:.1f}" y="{top:.1f}" width="{bw:.1f}" '
          f'height="{hgt:.1f}" rx="2" fill="{col}" '
          f'fill-opacity="{0.95 if last else 0.85}">')
        if last:
            a('      <animate attributeName="fill-opacity" values=".62;1;.62" '
              'dur="1.8s" repeatCount="indefinite"/>')
        a("    </rect>")
        if last:
            # The ring beneath it: the "still forming" tell.
            fy = ly + 12
            a(f'    <ellipse cx="{cx:.1f}" cy="{fy:.1f}" rx="6" ry="2.4" fill="none" '
              f'stroke="{GREEN}" stroke-width="1.4" opacity=".9">')
            a('      <animate attributeName="rx" values="6;21;6" dur="2.6s" '
              'repeatCount="indefinite"/>')
            a("    </ellipse>")
            a(f'    <ellipse cx="{cx:.1f}" cy="{fy:.1f}" rx="6" ry="2.4" fill="none" '
              f'stroke="{GREEN}" stroke-width="1.2">')
            a('      <animate attributeName="opacity" values=".85;0;.85" dur="2.6s" '
              'repeatCount="indefinite"/>')
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
    a("  <g>")
    a(f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" '
      f'fill="url(#panel)" stroke="#ffffff" stroke-opacity=".075"/>')
    a(f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="url(#fineGrid)"/>')
    a(f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="url(#grid)"/>')
    a(f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="url(#skyB)"/>')

    # Circuit traces: right-angled runs at very low opacity. They are the
    # difference between a dark rectangle and a surface something is built on.
    tseed = 90210
    for _ in range(14):
        tseed = (tseed * 1103515245 + 12345) & 0x7FFFFFFF
        tx = x + 30 + (tseed >> 9) % (w - 60)
        tseed = (tseed * 1103515245 + 12345) & 0x7FFFFFFF
        ty = y + 20 + (tseed >> 9) % (h - 40)
        tseed = (tseed * 1103515245 + 12345) & 0x7FFFFFFF
        run = 26 + (tseed >> 11) % 70
        tseed = (tseed * 1103515245 + 12345) & 0x7FFFFFFF
        drop = 14 + (tseed >> 11) % 40
        sgn = 1 if (tseed >> 7) % 2 else -1
        a(f'    <path d="M{tx} {ty} h{run} l{sgn * 9} {sgn * 9} v{drop}" fill="none" '
          f'stroke="{CYAN}" stroke-opacity=".055" stroke-width="1"/>')
        a(f'    <circle cx="{tx}" cy="{ty}" r="1.6" fill="{CYAN}" opacity=".10"/>')

    # Motes.
    mseed = 4711
    for _ in range(38):
        mseed = (mseed * 1103515245 + 12345) & 0x7FFFFFFF
        px = x + 14 + (mseed >> 9) % (w - 28)
        mseed = (mseed * 1103515245 + 12345) & 0x7FFFFFFF
        py = y + 12 + (mseed >> 9) % (h - 24)
        mseed = (mseed * 1103515245 + 12345) & 0x7FFFFFFF
        a(f'    <circle cx="{px}" cy="{py}" r="{0.7 + ((mseed >> 11) % 90) / 120:.2f}" '
          f'fill="#bfe3ff" opacity="{0.05 + ((mseed >> 5) % 90) / 700:.3f}"/>')

    a(f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="url(#vigB)"/>')

    # HUD corner brackets, with a detached tick on the long arm.
    for cx0, cy0, sx, sy in ((x + 14, y + 14, 1, 1), (x + w - 14, y + 14, -1, 1),
                             (x + 14, y + h - 14, 1, -1), (x + w - 14, y + h - 14, -1, -1)):
        a(f'    <path d="M{cx0} {cy0 + sy * 30} V{cy0 + sy * 9} '
          f'Q{cx0} {cy0} {cx0 + sx * 9} {cy0} H{cx0 + sx * 34}" fill="none" '
          f'stroke="{CYAN}" stroke-opacity=".38" stroke-width="1.7"/>')
        a(f'    <path d="M{cx0 + sx * 42} {cy0} h{sx * 12}" stroke="{CYAN}" '
          f'stroke-opacity=".22" stroke-width="1.7"/>')

    # ── decorative panel chrome ────────────────────────────────────────────
    #
    # THESE ARE ORNAMENT. They are not controls, they do nothing, and there is
    # nothing behind them to wire up -- this is a static image in a README.
    # Added at the maintainer's explicit request to match the reference artwork.
    #
    # Deliberately given no <title>, no aria-label and no cursor hint, so a
    # screen reader announces nothing and nothing suggests they can be pressed.
    # If a future change makes this figure interactive, delete them rather than
    # trying to give them behaviour.
    BTN = 34
    BTN_GAP = 10
    btn_y = y + 22
    btn_right = x + w - 62          # clear of the corner bracket and its tick
    for k, kind in enumerate(("resize", "frame", "layers")):
        bx0 = btn_right - (3 - k) * BTN - (2 - k) * BTN_GAP
        # Glass: a faint outer halo, a translucent face, a thin cyan edge.
        a(f'    <rect x="{bx0 - 2}" y="{btn_y - 2}" width="{BTN + 4}" '
          f'height="{BTN + 4}" rx="11" fill="none" stroke="{CYAN}" '
          f'stroke-opacity=".08" stroke-width="2"/>')
        a(f'    <rect x="{bx0}" y="{btn_y}" width="{BTN}" height="{BTN}" rx="9" '
          f'fill="url(#cardSurf)"/>')
        a(f'    <rect x="{bx0}" y="{btn_y}" width="{BTN}" height="{BTN}" rx="9" '
          f'fill="none" stroke="{CYAN}" stroke-opacity=".30" stroke-width="1.1"/>')
        gx0, gy0 = bx0 + 8, btn_y + 8
        ink = CYAN
        if kind == "resize":                       # a double-headed arrow
            a(f'    <path d="M2 9h14M4.4 6.2 1.6 9l2.8 2.8M13.6 6.2 16.4 9l-2.8 2.8" '
              f'fill="none" stroke="{ink}" stroke-opacity=".8" stroke-width="1.5" '
              f'stroke-linecap="round" stroke-linejoin="round" '
              f'transform="translate({gx0} {gy0})"/>')
        elif kind == "frame":                      # four corner brackets
            a(f'    <path d="M1.6 5.4V2.6a1 1 0 0 1 1-1h2.8M12.6 1.6h2.8a1 1 0 0 1 1 '
              f'1v2.8M16.4 12.6v2.8a1 1 0 0 1-1 1h-2.8M5.4 16.4H2.6a1 1 0 0 1-1-1v-2.8" '
              f'fill="none" stroke="{ink}" stroke-opacity=".8" stroke-width="1.5" '
              f'stroke-linecap="round" transform="translate({gx0} {gy0})"/>')
        else:                                      # two offset panes
            a(f'    <rect x="1.6" y="1.6" width="10.4" height="10.4" rx="2" fill="none" '
              f'stroke="{ink}" stroke-opacity=".55" stroke-width="1.5" '
              f'transform="translate({gx0} {gy0})"/>')
            a(f'    <rect x="6" y="6" width="10.4" height="10.4" rx="2" fill="none" '
              f'stroke="{ink}" stroke-opacity=".85" stroke-width="1.5" '
              f'transform="translate({gx0} {gy0})"/>')

    # ── connectors between the five cards ──────────────────────────────────
    for i in range(len(STAGES) - 1):
        x1 = card_x(i) + CARD_W
        x2 = card_x(i + 1)
        col = STAGES[i + 1][3]
        begin = i * HOP
        a(f'    <line x1="{x1 + 4}" y1="{FLOW_Y}" x2="{x2 - 4}" y2="{FLOW_Y}" '
          f'stroke="{col}" stroke-opacity=".13" stroke-width="8" stroke-linecap="round"/>')
        a(f'    <line x1="{x1 + 4}" y1="{FLOW_Y}" x2="{x2 - 4}" y2="{FLOW_Y}" '
          f'stroke="{col}" stroke-opacity=".75" stroke-width="1.8" stroke-linecap="round"/>')
        a(f'    <line x1="{x1 + 8}" y1="{FLOW_Y + 6}" x2="{x2 - 8}" y2="{FLOW_Y + 6}" '
          f'stroke="{col}" stroke-opacity=".26" stroke-width="1" stroke-dasharray="3 5"/>')
        for px in (x1 + 4, x2 - 4):
            a(f'    <circle cx="{px}" cy="{FLOW_Y}" r="4.2" fill="{col}" fill-opacity=".26"/>')
            a(f'    <circle cx="{px}" cy="{FLOW_Y}" r="2.1" fill="{col}"/>')
        cm = (x1 + x2) / 2
        for k in range(2):
            chx = cm - 5 + k * 9
            a(f'    <path d="M{chx:.1f} {FLOW_Y - 4.6} l4.6 4.6 -4.6 4.6" fill="none" '
              f'stroke="{col}" stroke-width="1.9" stroke-linecap="round" '
              f'stroke-linejoin="round" opacity=".28">')
            a(f'      <animate attributeName="opacity" values=".28;1;.28" '
              f'dur="{CYCLE:.2f}s" begin="{begin + k * 0.14:.2f}s" '
              f'repeatCount="indefinite"/>')
            a("    </path>")
        for k, (rr, op) in enumerate(((3.2, 1.0), (2.0, 0.55))):
            a(f'    <circle cx="{x1 + 4}" cy="{FLOW_Y}" r="{rr}" fill="#f2fbff" '
              f'opacity="{op}">')
            a(f'      <animate attributeName="cx" from="{x1 + 4}" to="{x2 - 4}" '
              f'dur="{HOP_DUR}s" begin="{begin + k * 0.15:.2f}s" '
              f'repeatCount="indefinite"/>')
            a("    </circle>")

    # last card -> diamond
    x1 = card_x(4) + CARD_W
    x2 = DIAMOND_CX - DIAMOND_R
    a(f'    <line x1="{x1 + 4}" y1="{FLOW_Y}" x2="{x2 - 6}" y2="{FLOW_Y}" '
      f'stroke="{VIOLET}" stroke-opacity=".14" stroke-width="8" stroke-linecap="round"/>')
    a(f'    <line x1="{x1 + 4}" y1="{FLOW_Y}" x2="{x2 - 6}" y2="{FLOW_Y}" '
      f'stroke="{VIOLET}" stroke-opacity=".8" stroke-width="1.8" stroke-linecap="round"/>')
    for k in range(2):
        chx = (x1 + x2) / 2 - 5 + k * 9
        a(f'    <path d="M{chx:.1f} {FLOW_Y - 4.6} l4.6 4.6 -4.6 4.6" fill="none" '
          f'stroke="{VIOLET}" stroke-width="1.9" stroke-linecap="round" '
          f'stroke-linejoin="round" opacity=".28">')
        a(f'      <animate attributeName="opacity" values=".28;1;.28" dur="{CYCLE:.2f}s" '
          f'begin="{4 * HOP + k * 0.14:.2f}s" repeatCount="indefinite"/>')
        a("    </path>")
    a(f'    <circle cx="{x1 + 4}" cy="{FLOW_Y}" r="3.2" fill="#f0e6ff">')
    a(f'      <animate attributeName="cx" from="{x1 + 4}" to="{x2 - 6}" '
      f'dur="{HOP_DUR}s" begin="{4 * HOP:.2f}s" repeatCount="indefinite"/>')
    a("    </circle>")

    # ── the five cards ─────────────────────────────────────────────────────
    for i, (t1, t2, gkey, accent) in enumerate(STAGES):
        cx0 = card_x(i)
        ccx = cx0 + CARD_W / 2
        top = FLOW_Y - CARD_H / 2
        begin = i * HOP

        a("    <g>")
        # Outer glow: three rounded rects, growing and fading. Approximates a
        # blur without a filter, which GitHub's proxy renders inconsistently.
        for grow, op in ((10, 0.05), (6, 0.08), (3, 0.11)):
            a(f'      <rect x="{cx0 - grow}" y="{top - grow}" '
              f'width="{CARD_W + grow * 2}" height="{CARD_H + grow * 2}" '
              f'rx="{16 + grow}" fill="none" stroke="{accent}" '
              f'stroke-opacity="{op}" stroke-width="2"/>')
        a(f'      <rect x="{cx0}" y="{top}" width="{CARD_W}" height="{CARD_H}" rx="16" '
          f'fill="url(#cardSurf)"/>')
        a(f'      <rect x="{cx0}" y="{top}" width="{CARD_W}" height="{CARD_H}" rx="16" '
          f'fill="{accent}" fill-opacity=".05"/>')
        a(f'      <rect x="{cx0 + .7}" y="{top + .7}" width="{CARD_W - 1.4}" '
          f'height="{CARD_H - 1.4}" rx="15.4" fill="none" stroke="{accent}" '
          f'stroke-opacity=".55" stroke-width="1.4">')
        a(f'        <animate attributeName="stroke-opacity" values=".55;1;.55;.55" '
          f'dur="{CYCLE:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite" '
          f'calcMode="spline" keyTimes="{PULSE_KEYTIMES}" '
          f'keySplines="{PULSE_SPLINES}"/>')
        a("      </rect>")
        # Inner hairline: the detail that makes the surface read as glass.
        a(f'      <rect x="{cx0 + 5}" y="{top + 5}" width="{CARD_W - 10}" '
          f'height="{CARD_H - 10}" rx="12" fill="none" stroke="{accent}" '
          f'stroke-opacity=".14" stroke-width="1"/>')

        s = 34 / 24
        a(f'      <g transform="translate({ccx - 17:.1f} {top + 20:.1f}) scale({s:.4f})">')
        for p in glyph(gkey, accent):
            a("        " + p)
        a("      </g>")

        ty = top + 82
        a(f'      <text x="{ccx:.1f}" y="{ty}" text-anchor="middle" '
          f'font-family="{FONT}" font-size="12.8" font-weight="600" '
          f'fill="{INK}">{esc(t1)}</text>')
        if t2:
            a(f'      <text x="{ccx:.1f}" y="{ty + 16}" text-anchor="middle" '
              f'font-family="{FONT}" font-size="11" font-style="italic" '
              f'fill="{accent}">{esc(t2)}</text>')

        # Status light and the pool it throws on the floor. This is the detail
        # that gives the row a ground plane instead of leaving the cards
        # floating on a flat backdrop.
        dy = top + CARD_H + 14
        a(f'      <circle cx="{ccx:.1f}" cy="{dy}" r="7" fill="{accent}" fill-opacity=".22">')
        a("        " + pulse_b("fill-opacity", 0.10, 0.42, begin))
        a("      </circle>")
        a(f'      <circle cx="{ccx:.1f}" cy="{dy}" r="3.1" fill="{accent}"/>')
        for rx_, ry_, op in ((34, 7.5, 0.10), (23, 5, 0.16), (13, 3, 0.26)):
            a(f'      <ellipse cx="{ccx:.1f}" cy="{dy + 17}" rx="{rx_}" ry="{ry_}" '
              f'fill="none" stroke="{accent}" stroke-opacity="{op}" stroke-width="1.2"/>')
        a(f'      <ellipse cx="{ccx:.1f}" cy="{dy + 17}" rx="9" ry="2.2" fill="{accent}" '
          f'fill-opacity=".30">')
        a("        " + pulse_b("fill-opacity", 0.14, 0.60, begin))
        a("      </ellipse>")
        a("    </g>")

    # ── the decision node ──────────────────────────────────────────────────
    d = DIAMOND_R
    a("    <g>")
    a(f'      <circle cx="{DIAMOND_CX}" cy="{FLOW_Y}" r="{d + 34}" fill="url(#gViolet)" '
      f'opacity=".45">')
    a("        " + pulse_b("opacity", 0.28, 0.9, 5 * HOP))
    a("      </circle>")
    # Three concentric halo rings, the outer two dashed. They used to counter-
    # rotate at 22s and 15s. The spin was decoration -- it encoded nothing about
    # the tape -- and rotation is a transform no other diagram in docs/assets
    # uses. The rings themselves stay; they just no longer turn.
    for rad, dash, op in ((d + 30, (7, 11), 0.20),
                          (d + 19, (4, 9), 0.30),
                          (d + 9, (0, 0), 0.22)):
        if dash[0]:
            a(f'      <circle cx="{DIAMOND_CX}" cy="{FLOW_Y}" r="{rad}" fill="none" '
              f'stroke="{VIOLET}" stroke-opacity="{op}" stroke-width="1.2" '
              f'stroke-dasharray="{dash[0]} {dash[1]}"/>')
        else:
            a(f'      <circle cx="{DIAMOND_CX}" cy="{FLOW_Y}" r="{rad}" fill="none" '
              f'stroke="{VIOLET}" stroke-opacity="{op}" stroke-width="1"/>')
    # The ring that leaves the node when it fires.
    a(f'      <circle cx="{DIAMOND_CX}" cy="{FLOW_Y}" r="{d}" fill="none" '
      f'stroke="{VIOLET}" stroke-width="1.6" opacity="0">')
    a(f'        <animate attributeName="r" values="{d};{d + 40}" dur="{CYCLE:.2f}s" '
      f'begin="{5 * HOP:.2f}s" repeatCount="indefinite" calcMode="spline" '
      f'keyTimes="0;1" keySplines="0.2 0 0.3 1"/>')
    a("      </circle>")
    a(f'      <circle cx="{DIAMOND_CX}" cy="{FLOW_Y}" r="{d}" fill="none" '
      f'stroke="{VIOLET}" stroke-width="1.6" opacity="0">')
    a("        " + pulse_b("opacity", 0.0, 0.85, 5 * HOP))
    a("      </circle>")
    dpath = (f'M{DIAMOND_CX} {FLOW_Y - d} L{DIAMOND_CX + d} {FLOW_Y} '
             f'L{DIAMOND_CX} {FLOW_Y + d} L{DIAMOND_CX - d} {FLOW_Y}z')
    a(f'      <path d="{dpath}" fill="#0b1120" fill-opacity=".95"/>')
    a(f'      <path d="{dpath}" fill="{VIOLET}" fill-opacity=".07"/>')
    a(f'      <path d="{dpath}" fill="none" stroke="{VIOLET}" stroke-opacity=".9" '
      f'stroke-width="1.7"/>')
    # Small markers inside the four vertices: instrument detail.
    for vx, vy_, rot in ((DIAMOND_CX, FLOW_Y - d + 13, 90),
                         (DIAMOND_CX + d - 13, FLOW_Y, 180),
                         (DIAMOND_CX, FLOW_Y + d - 13, 270),
                         (DIAMOND_CX - d + 13, FLOW_Y, 0)):
        a(f'      <path d="M-3.4 -3.4 L2.6 0 L-3.4 3.4z" fill="{VIOLET}" '
          f'fill-opacity=".75" transform="translate({vx} {vy_}) rotate({rot})"/>')
    a(f'      <g transform="translate({DIAMOND_CX - 13} {FLOW_Y - 40}) scale(1.08)">')
    for p in glyph("candles", "#e9d5ff"):
        a("        " + p)
    a("      </g>")
    a(f'      <text x="{DIAMOND_CX}" y="{FLOW_Y + 8}" text-anchor="middle" '
      f'font-family="{FONT}" font-size="12.6" font-weight="600" fill="{INK}">New '
      f'closed</text>')
    a(f'      <text x="{DIAMOND_CX}" y="{FLOW_Y + 24}" text-anchor="middle" '
      f'font-family="{FONT}" font-size="12.6" font-weight="600" fill="{INK}">bar?</text>')
    a("    </g>")

    # ── the two branches ───────────────────────────────────────────────────
    bx = DIAMOND_CX + d
    for is_yes in (True, False):
        col = GREEN if is_yes else PINK
        mk = "arGreen" if is_yes else "arPink"
        cyb = YES_CY if is_yes else NO_CY
        lbl = "YES" if is_yes else "NO"
        bpath = (f'M{bx + 4} {FLOW_Y} L{ELBOW_X} {FLOW_Y} L{ELBOW_X} {cyb} '
                 f'L{OUT_X - 10} {cyb}')
        a(f'    <path d="{bpath}" fill="none" stroke="{col}" stroke-opacity=".16" '
          f'stroke-width="7" stroke-linejoin="round" stroke-linecap="round"/>')
        a(f'    <path d="{bpath}" fill="none" stroke="{col}" stroke-opacity=".8" '
          f'stroke-width="1.8" stroke-linejoin="round" marker-end="url(#{mk})"/>')
        cw = 40 if is_yes else 32
        chip_cx = (ELBOW_X + OUT_X) / 2
        a(f'    <rect x="{chip_cx - cw / 2 - 3:.1f}" y="{cyb - 16}" width="{cw + 6}" '
          f'height="32" rx="9" fill="none" stroke="{col}" stroke-opacity=".18"/>')
        a(f'    <rect x="{chip_cx - cw / 2:.1f}" y="{cyb - 13}" width="{cw}" height="26" '
          f'rx="7" fill="#0a1220" stroke="{col}" stroke-opacity=".85"/>')
        a(f'    <text x="{chip_cx:.1f}" y="{cyb + 4.6}" text-anchor="middle" '
          f'font-family="{FONT}" font-size="11.4" font-weight="700" letter-spacing=".6" '
          f'fill="{col}">{lbl}</text>')
        a(f'    <circle cx="{bx + 4}" cy="{FLOW_Y}" r="2.9" fill="{col}">')
        for attr, frm, to in (("cx", bx + 4, OUT_X - 12), ("cy", FLOW_Y, cyb)):
            a(f'      <animate attributeName="{attr}" from="{frm}" to="{to}" dur="1.25s" '
              f'begin="{5 * HOP + (0 if is_yes else 0.6):.2f}s" repeatCount="indefinite"/>')
        a("    </circle>")

    # ── outcome cards ──────────────────────────────────────────────────────
    def outcome(cy_, col, gkey, title, sub, begin):
        top_ = cy_ - OUT_H / 2
        a("    <g>")
        for grow, op in ((9, 0.05), (5, 0.09), (2, 0.12)):
            a(f'      <rect x="{OUT_X - grow}" y="{top_ - grow}" '
              f'width="{OUT_W + grow * 2}" height="{OUT_H + grow * 2}" rx="{15 + grow}" '
              f'fill="none" stroke="{col}" stroke-opacity="{op}" stroke-width="2"/>')
        a(f'      <rect x="{OUT_X}" y="{top_}" width="{OUT_W}" height="{OUT_H}" rx="15" '
          f'fill="url(#cardSurf)"/>')
        a(f'      <rect x="{OUT_X}" y="{top_}" width="{OUT_W}" height="{OUT_H}" rx="15" '
          f'fill="{col}" fill-opacity=".05"/>')
        a(f'      <rect x="{OUT_X + .7}" y="{top_ + .7}" width="{OUT_W - 1.4}" '
          f'height="{OUT_H - 1.4}" rx="14.4" fill="none" stroke="{col}" '
          f'stroke-opacity=".6" stroke-width="1.4">')
        a("        " + pulse_b("stroke-opacity", 0.45, 1.0, begin))
        a("      </rect>")
        if gkey == "loading":
            # Eight dots in a ring. They used to carry a graded 0.25-0.88
            # opacity, which was a comet trail chasing a 3.2s spin; with the
            # spin gone the gradient just made one arbitrary dot brightest, so
            # they are now uniform. The inner <g> went with it -- it existed
            # only to be the rotation target.
            a(f'      <g transform="translate({OUT_X + 38} {cy_:.0f})">')
            for k in range(8):
                ang = k * math.pi / 4
                a(f'        <circle cx="{15 * math.cos(ang):.1f}" '
                  f'cy="{15 * math.sin(ang):.1f}" r="2.5" fill="{col}" '
                  f'opacity=".55"/>')
            a("      </g>")
            tx0 = OUT_X + 68
        else:
            a(f'      <g transform="translate({OUT_X + 24} {cy_ - 15:.0f}) scale(1.25)">')
            for p in glyph(gkey, col):
                a("        " + p)
            a("      </g>")
            tx0 = OUT_X + 64
        a(f'      <text x="{tx0}" y="{cy_ + (5 if not sub else -3):.0f}" '
          f'font-family="{FONT}" font-size="14.5" font-weight="700" '
          f'fill="{INK}">{esc(title)}</text>')
        if sub:
            a(f'      <text x="{tx0}" y="{cy_ + 16:.0f}" font-family="{FONT}" '
              f'font-size="11.5" fill="{DIM}">{esc(sub)}</text>')
        dcx = OUT_X + OUT_W / 2
        dy = top_ + OUT_H + 13
        a(f'      <circle cx="{dcx:.0f}" cy="{dy:.0f}" r="6.4" fill="{col}" '
          f'fill-opacity=".22">')
        a("        " + pulse_b("fill-opacity", 0.10, 0.42, begin))
        a("      </circle>")
        a(f'      <circle cx="{dcx:.0f}" cy="{dy:.0f}" r="3" fill="{col}"/>')
        for rx_, ry_, op in ((30, 6.6, 0.10), (20, 4.4, 0.16), (11, 2.6, 0.26)):
            a(f'      <ellipse cx="{dcx:.0f}" cy="{dy + 15:.0f}" rx="{rx_}" ry="{ry_}" '
              f'fill="none" stroke="{col}" stroke-opacity="{op}" stroke-width="1.2"/>')
        a("    </g>")

    outcome(YES_CY, GREEN, "bars", "Tape advances", "VWAP · bands · signals",
            5 * HOP + 0.3)
    outcome(NO_CY, PINK, "loading", "Still forming…", None, 5 * HOP + 0.9)

    # ── the return path ────────────────────────────────────────────────────
    ret_y = NO_CY + OUT_H / 2 + 46
    poll_cx = card_x(4) + CARD_W / 2
    path_d = (f"M{OUT_X + OUT_W / 2:.0f} {NO_CY + OUT_H / 2 + 30:.0f} "
              f"L{OUT_X + OUT_W / 2:.0f} {ret_y:.0f} L{poll_cx:.0f} {ret_y:.0f} "
              f"L{poll_cx:.0f} {FLOW_Y + CARD_H / 2 + 52:.0f}")
    a(f'    <path d="{path_d}" fill="none" stroke="{VIOLET}" stroke-opacity=".14" '
      f'stroke-width="7" stroke-linejoin="round" stroke-linecap="round"/>')
    a(f'    <path d="{path_d}" fill="none" stroke="{VIOLET}" stroke-opacity=".7" '
      f'stroke-width="1.7" stroke-linejoin="round" stroke-dasharray="8 6" '
      f'marker-end="url(#arViolet)">')
    # Marching ants: what makes the loop read as a loop rather than a bracket.
    a('      <animate attributeName="stroke-dashoffset" from="28" to="0" dur="1.15s" '
      'repeatCount="indefinite"/>')
    a("    </path>")
    # Arrowheads along the horizontal run, so the direction is unambiguous.
    for k in range(3):
        axp = OUT_X + OUT_W / 2 - (k + 1) * (OUT_X + OUT_W / 2 - poll_cx) / 4
        a(f'    <path d="M3.6 0 L-3 3.6 L-3 -3.6z" fill="{VIOLET}" fill-opacity=".55" '
          f'transform="translate({axp:.0f} {ret_y:.0f}) rotate(180)"/>')
    a(f'    <text x="{(OUT_X + OUT_W / 2 + poll_cx) / 2:.0f}" y="{ret_y - 10:.0f}" '
      f'text-anchor="middle" font-family="{FONT}" font-size="11" fill="{VIOLET}" '
      f'fill-opacity=".8">poll again — the tape does not move</text>')
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
