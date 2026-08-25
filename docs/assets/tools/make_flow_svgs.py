"""
Generate the three flow diagrams that used to be mermaid blocks in the README:

    architecture.svg   data sources -> core engine -> interfaces
    workflow.svg       idea -> research -> ... -> deploy -> live
    execution.svg      bars -> signal -> broker -> fill -> P&L -> metrics

WHY THEY ARE NOT MERMAID ANY MORE
---------------------------------
GitHub injects its own pan/zoom control cluster into every rendered mermaid
block -- eight buttons floating over the bottom-right corner of the diagram.
There is no markdown-level way to turn them off. On a page whose other eight
figures are plain <img>, the four mermaid blocks were the only ones wearing
chrome, and the buttons overlapped the last node of two of them.

Drawing them as SVG removes the chrome and puts every figure in the README in
one visual language. The cost is that layout is now explicit rather than
computed, which is why the geometry below is derived from a few constants
instead of typed per node.

WHAT WAS KEPT
-------------
Every node label, every sub-line, every edge and every accent colour is carried
across from the mermaid source unchanged. The mermaid classDef palette is the
palette here: teal for the nodes that matter, slate for the rest, sky/violet/
teal for the three architecture bands, amber for the two execution nodes that
charge money.

A fourth mermaid block, the follow-live loop in Live Replay, is not reproduced
here. live-tape.svg sits immediately above it in that section and its lower
panel already draws that exact flow, so the block was removed rather than
redrawn.

WHAT THE MOTION DOES
--------------------
One dot per diagram, travelling the chain once per cycle, with the node it
reaches brightening as it lands. Same language as pipeline.svg. No rotation, no
filters, nothing looping for decoration.

SMIL NOTES (the same three every generator here carries)
--------------------------------------------------------
* Two <animate> on the SAME attribute of the SAME element: the later silently
  wins from t=0. One animation per attribute, always.
* An animated attribute must ALSO be set statically, or it renders at its
  default until its begin time arrives.
* GitHub proxies these: SMIL survives, CSS animation and script do not.
"""
import pathlib
import sys

W = 1280
FONT = ("ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "Roboto,Helvetica,Arial,sans-serif")
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

INK = "#e2e8f0"
DIM = "#94a3b8"
SLATE = "#334155"
BG = "#060b14"
PANEL = "#0b1220"

TEAL = "#2dd4bf"
SKY = "#38bdf8"
VIOLET = "#a78bfa"
AMBER = "#f59e0b"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def card(x, y, w, h, title, sub, accent, begin, cycle, strong):
    """One node. Border brightens as the travelling dot reaches it."""
    o = []
    op = "0.55" if strong else "0.30"
    o.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="10" '
             f'fill="{PANEL}" stroke="{accent}" stroke-opacity="{op}" '
             f'stroke-width="{2 if strong else 1.2}">')
    o.append(f'<animate attributeName="stroke-opacity" '
             f'values="{op};1;{op};{op}" keyTimes="0;0.06;0.30;1" '
             f'begin="{begin:.2f}s" dur="{cycle:.2f}s" repeatCount="indefinite"/>')
    o.append("</rect>")
    cx = x + w / 2
    ty = y + (h / 2) + (0 if sub else 5)
    o.append(f'<text x="{cx:.0f}" y="{ty - (8 if sub else 0):.0f}" text-anchor="middle" '
             f'font-family="{FONT}" font-size="14" font-weight="700" '
             f'fill="{INK}">{esc(title)}</text>')
    if sub:
        for i, line in enumerate(sub if isinstance(sub, list) else [sub]):
            o.append(f'<text x="{cx:.0f}" y="{ty + 11 + i * 15:.0f}" text-anchor="middle" '
                     f'font-family="{FONT}" font-size="12.5" font-style="italic" '
                     f'fill="{DIM}">{esc(line)}</text>')
    return o


def arrow_h(x1, x2, y, accent="#3a4a63"):
    """A straight horizontal connector with a small head."""
    return [f'<path d="M {x1:.0f} {y:.0f} H {x2 - 7:.0f}" stroke="{accent}" '
            f'stroke-width="1.5" fill="none"/>',
            f'<path d="M {x2 - 7:.0f} {y - 4:.0f} L {x2:.0f} {y:.0f} '
            f'L {x2 - 7:.0f} {y + 4:.0f} Z" fill="{accent}"/>']


def arrow_v(x, y1, y2, accent="#3a4a63"):
    return [f'<path d="M {x:.0f} {y1:.0f} V {y2 - 7:.0f}" stroke="{accent}" '
            f'stroke-width="1.5" fill="none"/>',
            f'<path d="M {x - 4:.0f} {y2 - 7:.0f} L {x:.0f} {y2:.0f} '
            f'L {x + 4:.0f} {y2 - 7:.0f} Z" fill="{accent}"/>']


def dot(pts, begin, dur, accent, by_distance=False):
    """
    One dot walking a list of (x, y) stops, once per cycle.

    by_distance spaces the keyTimes by segment length instead of evenly, so a
    path with elbow points (workflow's row wrap) travels at a constant speed
    rather than crawling through the three short corner segments.
    """
    n = len(pts)
    if by_distance:
        d = [0.0]
        for a, b in zip(pts, pts[1:]):
            d.append(d[-1] + ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5)
        kt = ";".join(f"{v / d[-1]:.3f}" for v in d)
    else:
        kt = ";".join(f"{i / (n - 1):.3f}" for i in range(n))
    xs = ";".join(f"{p[0]:.0f}" for p in pts)
    ys = ";".join(f"{p[1]:.0f}" for p in pts)
    return [
        f'<circle r="3.4" fill="{accent}" opacity="0">',
        f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.04;0.90;1" '
        f'begin="{begin:.2f}s" dur="{dur:.2f}s" repeatCount="indefinite"/>',
        f'<animate attributeName="cx" values="{xs}" keyTimes="{kt}" '
        f'begin="{begin:.2f}s" dur="{dur:.2f}s" repeatCount="indefinite"/>',
        f'<animate attributeName="cy" values="{ys}" keyTimes="{kt}" '
        f'begin="{begin:.2f}s" dur="{dur:.2f}s" repeatCount="indefinite"/>',
        "</circle>",
    ]


def head(h, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" '
            f'width="{W}" height="{h}" role="img" aria-label="{esc(label)}">'
            f'<rect width="100%" height="100%" fill="{BG}"/>')


# ══ chain diagrams: workflow and execution ════════════════════════════════
def chain(nodes, rows, label, accent_default=SLATE):
    """
    nodes: (title, sub|None, accent|None, strong)
    rows : how many rows to break the chain over. Eight nodes on one row give
           138px cards, too narrow for "Backtest & Replay"; two rows of four
           give 290px and the text sits comfortably.
    """
    PAD, GAP, CH = 26, 22, 74
    ROW_GAP = 40
    per = -(-len(nodes) // rows)
    CW = (W - 2 * PAD - GAP * (per - 1)) / per
    H = 30 + rows * CH + (rows - 1) * ROW_GAP + 30
    step = 1.0
    cycle = len(nodes) * step

    o = [head(H, label)]
    stops = []
    for i, (title, sub, accent, strong) in enumerate(nodes):
        r, c = divmod(i, per)
        x = PAD + c * (CW + GAP)
        y = 30 + r * (CH + ROW_GAP)
        o += card(x, y, CW, CH, title, sub, accent or accent_default,
                  i * step, cycle, strong)
        stops.append((x + CW / 2, y + CH / 2))
        if c < per - 1 and i < len(nodes) - 1:
            o += arrow_h(x + CW, x + CW + GAP, y + CH / 2)
        elif i < len(nodes) - 1:
            # wrap to the next row: down the right edge, back along, into row 2
            y2 = y + CH + ROW_GAP
            o.append(f'<path d="M {x + CW / 2:.0f} {y + CH:.0f} V {y + CH + 20:.0f} '
                     f'H {PAD + CW / 2:.0f} V {y2:.0f}" stroke="#3a4a63" '
                     f'stroke-width="1.5" fill="none" stroke-dasharray="4 4"/>')
    o += dot(stops, 0, cycle, TEAL)
    o.append("</svg>")
    return "\n".join(o) + "\n"


# == About the Platform: card headers and rules ============================
# Not diagrams. GitHub strips style attributes and <style> blocks from README
# markdown, so a heading number, an icon and a horizontal rule cannot be given
# a colour in markup -- the only way to put an accent colour on the page is to
# ship it as an image. These are the smallest images that do that: the prose
# they sit above stays real text.
def about_header(num, key, accent):
    """A numbered chip and its icon, drawn inline above a card's title."""
    w, h = 108, 46
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}" role="img" '
            f'aria-label="Step {num}">'
            f'<rect x="1" y="5" width="44" height="36" rx="10" fill="{accent}" '
            f'fill-opacity=".10" stroke="{accent}" stroke-opacity=".65" '
            f'stroke-width="1.4"/>'
            f'<text x="23" y="30" text-anchor="middle" font-family="{MONO}" '
            f'font-size="19" font-weight="700" fill="{accent}">{num}</text>'
            + icon(key, accent, 60, 2, 1.75) +
            '</svg>\n')


def about_rule(accent):
    """A one-colour rule, stretched to the card width by the img tag."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 2" '
            'width="100" height="2" preserveAspectRatio="none" role="img" '
            'aria-label="">'
            f'<rect width="100" height="2" rx="1" fill="{accent}" '
            'fill-opacity=".55"/></svg>\n')


ABOUT = [("01", "book", SKY), ("02", "scales", AMBER), ("03", "trusted", VIOLET)]


# == workflow: eight numbered stages over two rows =========================
def workflow():
    """
    Eight stages, four to a row. Each card carries its step number, an icon,
    the stage name and its one supporting line. Verify and Deploy are the two
    checkpoints, so they get the accent border and a heavier stroke.

    Two rows, not one: eight cards across 1280px give 138px each, and
    "Backtest & Replay" does not fit in 138px. Four give 288px.
    """
    PAD, GAP, CW, CH = 28, 24, 288, 140
    ROW_GAP, TOP = 74, 24
    H = TOP + 2 * CH + ROW_GAP + 24

    nodes = [
        ("01", "Idea", None, "bulb", SKY, False),
        ("02", "Research", "measure it", "search", SKY, False),
        ("03", "Implement", "+ tests that can fail", "code", SKY, False),
        ("04", "Verify", "1,853 tests \u00b7 ruff \u00b7 tsc", "shield", TEAL, True),
        ("05", "Backtest & Replay", "against real bars", "bars", VIOLET, False),
        ("06", "Pull Request", "6 CI checks", "branch", VIOLET, False),
        ("07", "Merge", None, "merge", VIOLET, False),
        ("08", "Deploy", "SHA asserted", "rocket", TEAL, True),
    ]
    step = 1.0
    cycle = len(nodes) * step

    o = [head(H, "A change travels from idea through research, implementation, "
                 "verification, backtest, pull request and merge to a deploy "
                 "whose commit is asserted")]
    stops = []
    for i, (num, title, sub, ic, accent, strong) in enumerate(nodes):
        r, c = divmod(i, 4)
        x = PAD + c * (CW + GAP)
        y = TOP + r * (CH + ROW_GAP)
        cx = x + CW / 2
        op = "0.55" if strong else "0.26"

        o.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{CW}" height="{CH}" rx="14" '
                 f'fill="{PANEL}" stroke="{accent}" stroke-opacity="{op}" '
                 f'stroke-width="{2 if strong else 1.2}">')
        o.append(f'<animate attributeName="stroke-opacity" values="{op};0.95;{op};{op}" '
                 f'keyTimes="0;0.04;0.22;1" begin="{i * step:.2f}s" '
                 f'dur="{cycle:.2f}s" repeatCount="indefinite"/>')
        o.append("</rect>")

        # step number, in its own chip so it reads as an index, not as data
        o.append(f'<rect x="{x + 16:.0f}" y="{y + 16}" width="36" height="22" rx="6" '
                 f'fill="{accent}" fill-opacity=".12"/>')
        o.append(f'<text x="{x + 34:.0f}" y="{y + 31}" text-anchor="middle" '
                 f'font-family="{MONO}" font-size="11.5" font-weight="700" '
                 f'letter-spacing=".5" fill="{accent}" fill-opacity=".85">{num}</text>')

        o.append(icon(ic, accent, cx - 18, y + 46, 1.5))
        o.append(f'<text x="{cx:.0f}" y="{y + 107}" text-anchor="middle" '
                 f'font-family="{FONT}" font-size="17" font-weight="700" '
                 f'fill="{INK}">{esc(title)}</text>')
        if sub:
            o.append(f'<text x="{cx:.0f}" y="{y + 127}" text-anchor="middle" '
                     f'font-family="{FONT}" font-size="12.5" '
                     f'fill="{DIM}">{esc(sub)}</text>')
        stops.append((cx, y + CH / 2))
        if c < 3:
            o += arrow_h(x + CW, x + CW + GAP, y + CH / 2,
                         "#3d7ea6" if r == 0 else "#6350a0")

    # The row wrap. Drawn as a real routed connector -- down out of Verify,
    # back along the gutter, down into Backtest -- because a diagonal across
    # the whole figure would read as a shortcut past stages 05 to 07.
    y_elbow = TOP + CH + ROW_GAP / 2
    x_v, x_b = stops[3][0], stops[4][0]
    y_top, y_bot = TOP + CH, TOP + CH + ROW_GAP
    o.append(f'<path d="M {x_v:.0f} {y_top} V {y_elbow:.0f} H {x_b:.0f} V {y_bot - 8:.0f}" '
             f'fill="none" stroke="{TEAL}" stroke-opacity=".5" stroke-width="1.5" '
             f'stroke-dasharray="5 5"/>')
    o.append(f'<path d="M {x_b - 4.5:.0f} {y_bot - 8:.0f} L {x_b:.0f} {y_bot:.0f} '
             f'L {x_b + 4.5:.0f} {y_bot - 8:.0f} Z" fill="{TEAL}" fill-opacity=".6"/>')

    # The dot follows that same routing rather than cutting the corner.
    path = stops[:4] + [(x_v, y_elbow), (x_b, y_elbow)] + stops[4:]
    o += dot(path, 0, cycle, TEAL, by_distance=True)
    o.append("</svg>")
    return "\n".join(o) + "\n"


# ══ architecture: three bands, top to bottom ══════════════════════════════
# Icons on a 24x24 grid, outlined at one weight so they read as one family
# rather than as clip art collected from three places.
ICONS = {
    "cloud": ['<path d="M7.4 18.4h9.2a4.1 4.1 0 0 0 .6-8.15 5.7 5.7 0 0 0-11 1.5 3.4 3.4 0 0 0 1.2 6.65z"/>'],
    "doc": ['<path d="M6.6 3.6h7.6L18.4 8v12.4H6.6z"/>', '<path d="M14 3.8V8.2h4.2"/>',
            '<path d="M9.4 12.4h6M9.4 15.6h6"/>'],
    "db": ['<ellipse cx="12" cy="6.2" rx="6.4" ry="2.6"/>',
           '<path d="M5.6 6.2v11.6c0 1.44 2.87 2.6 6.4 2.6s6.4-1.16 6.4-2.6V6.2"/>',
           '<path d="M5.6 12c0 1.44 2.87 2.6 6.4 2.6s6.4-1.16 6.4-2.6"/>'],
    "code": ['<path d="M8.6 8.4 4.6 12l4 3.6"/>', '<path d="M15.4 8.4 19.4 12l-4 3.6"/>',
             '<path d="M13.4 5.6 10.6 18.4"/>'],
    "bars": ['<path d="M5 19.4V13M10.4 19.4V7.6M15.6 19.4v-8M20.4 19.4V4.6"/>'],
    "target": ['<circle cx="12" cy="12" r="7.4"/>', '<circle cx="12" cy="12" r="3.2"/>',
               '<path d="M12 1.8v2.6M12 19.6v2.6M1.8 12h2.6M19.6 12h2.6"/>'],
    "receipt": ['<path d="M6.4 3.6h11.2v16.8l-2.24-1.5-1.86 1.5-1.86-1.5-1.86 1.5-1.86-1.5-1.52 1.5z"/>',
                '<path d="M9.4 8.4h5.2M9.4 11.6h5.2M9.4 14.8h2.8"/>'],
    "clock": ['<circle cx="12" cy="12" r="8.4"/>', '<path d="M12 7v5.2l3.4 2"/>',
              '<path d="M4.2 5.2 6.4 7.4M19.8 5.2l-2.2 2.2"/>'],
    "server": ['<rect x="3.6" y="4.4" width="16.8" height="15.2" rx="2.2"/>',
               '<path d="M7 9.6l2.6 2.4L7 14.4"/>', '<path d="M12.6 14.8h4.4"/>'],
    "chart": ['<rect x="3.6" y="4.4" width="16.8" height="15.2" rx="2.2"/>',
              '<path d="M7.2 14.8 10.4 11l2.6 2.2 3.8-4.8"/>'],
    "bulb": ['<path d="M12 2.8a6.3 6.3 0 0 0-3.7 11.4v2.2h7.4v-2.2A6.3 6.3 0 0 0 12 2.8z"/>',
             '<path d="M9.6 19h4.8"/>', '<path d="M10.6 21.4h2.8"/>'],
    "search": ['<circle cx="10.7" cy="10.7" r="6.5"/>', '<path d="M15.4 15.4 20.4 20.4"/>'],
    "shield": ['<path d="M12 2.8 4.9 5.8v5.9c0 4.4 3 8.5 7.1 9.7 4.1-1.2 7.1-5.3 7.1-9.7V5.8z"/>',
               '<path d="m8.8 11.9 2.4 2.4 4.2-4.7"/>'],
    "branch": ['<path d="M6.6 3.8v12.4"/>', '<circle cx="17.4" cy="6.2" r="2.2"/>',
               '<circle cx="6.6" cy="18.4" r="2.2"/>',
               '<path d="M17.4 8.4a8.6 8.6 0 0 1-8.6 8.4"/>'],
    "merge": ['<circle cx="6.4" cy="4.8" r="2.2"/>', '<circle cx="17.6" cy="4.8" r="2.2"/>',
              '<circle cx="12" cy="19.2" r="2.2"/>',
              '<path d="M6.4 7v1.9a3.5 3.5 0 0 0 3.5 3.5h4.2a3.5 3.5 0 0 0 3.5-3.5V7"/>',
              '<path d="M12 12.4v4.6"/>'],
    "rocket": ['<path d="M12 2.6c3 2.3 4.8 5.9 4.8 9.7 0 2.3-.7 4.5-1.9 6.3H9.1a11.7 11.7 0 0 1-1.9-6.3c0-3.8 1.8-7.4 4.8-9.7z"/>',
               '<circle cx="12" cy="10.2" r="2"/>',
               '<path d="M7.4 13.3 4.6 16.1v3.3h3"/>',
               '<path d="M16.6 13.3l2.8 2.8v3.3h-3"/>',
               '<path d="M10.4 20.6c.5.9 1 1.6 1.6 2.1.6-.5 1.1-1.2 1.6-2.1"/>'],
    "book": ['<path d="M12 6.4v13.4"/>',
             '<path d="M12 6.4C10.2 4.9 7.8 4.2 4.4 4.2v12.6c3.4 0 5.8.7 7.6 2.2"/>',
             '<path d="M12 6.4c1.8-1.5 4.2-2.2 7.6-2.2v12.6c-3.4 0-5.8.7-7.6 2.2"/>'],
    "scales": ['<circle cx="12" cy="4.6" r="1.5"/>', '<path d="M12 6.1v13.3"/>',
               '<path d="M5 7.4h14"/>', '<path d="M8.4 19.4h7.2"/>',
               '<path d="M5 7.4 2.4 12.8h5.2z"/>', '<path d="M19 7.4l-2.6 5.4h5.2z"/>'],
    "trusted": ['<circle cx="9.6" cy="6.6" r="2.9"/>',
                '<path d="M3.8 19.6a5.8 5.8 0 0 1 5.8-5.8c.9 0 1.8.2 2.6.6"/>',
                '<path d="M17.4 11.2 21.6 12.7v3.3c0 2.3-1.7 4.4-4.2 5.2-2.5-.8-4.2-2.9-4.2-5.2v-3.3z"/>',
                '<path d="m15.6 16.2 1.3 1.3 2.3-2.6"/>'],
    "down": ['<path d="M12 3.8v10"/>', '<path d="M8 10l4 4 4-4"/>',
             '<path d="M4.8 16.6v2.6a1.6 1.6 0 0 0 1.6 1.6h11.2a1.6 1.6 0 0 0 1.6-1.6v-2.6"/>'],
}


def icon(key, ink, x, y, s=1.0):
    """Draw an icon's 24x24 grid at (x, y)."""
    body = "".join(ICONS[key])
    return (f'<g transform="translate({x:.1f} {y:.1f}) scale({s:.3f})" fill="none" '
            f'stroke="{ink}" stroke-width="1.6" stroke-linecap="round" '
            f'stroke-linejoin="round">{body}</g>')


def architecture():
    PAD, GAP, CH = 28, 20, 84
    LBL = 30          # room for the band caption above its row
    BAND_GAP = 62     # room for the arrow between bands

    bands = [
        ("Data Sources", SKY, 0, [
            ("Schwab API", "live \u00b7 ~180 days", "cloud"),
            ("CSV archive", "18 years", "doc"),
            ("Synthetic", "deterministic", "db"),
        ]),
        ("Core Engine \u00b7 src/", VIOLET, 4, [
            ("Resampler", "one shared aggregator", "code"),
            ("Analysis", "waves \u00b7 patterns \u00b7 VWAP", "bars"),
            ("Strategies", "five, one interface", "target"),
            ("Paper Broker", "commission \u00b7 slippage", "receipt"),
            ("Replay Engine", "shared market clock", "clock"),
        ]),
        ("Interfaces", TEAL, 0, [
            ("FastAPI", "REST + WebSocket", "server"),
            ("React Dashboard", None, "chart"),
            ("Export", "CSV \u00b7 XLSX \u00b7 PDF \u00b7 DOCX", "down"),
        ]),
    ]
    H = 22 + sum(LBL + CH for _ in bands) + BAND_GAP * (len(bands) - 1) + 26

    o = [head(H, "Three data sources feed one core engine, which the interfaces "
                 "read; the replay engine feeds back to the resampler and the "
                 "engine imports nothing from either side")]
    y, edges = 22, []
    step, cycle = 1.15, 3.45

    for bi, (name, accent, chain_len, items) in enumerate(bands):
        o.append(f'<text x="{PAD}" y="{y + 13}" font-family="{MONO}" font-size="12.5" '
                 f'font-weight="700" letter-spacing="1.4" fill="{accent}" '
                 f'fill-opacity=".9">{esc(name.upper())}</text>')
        yy = y + LBL
        n = len(items)
        cw = (W - 2 * PAD - GAP * (n - 1)) / n
        for i, (title, sub, ic) in enumerate(items):
            x = PAD + i * (cw + GAP)
            strong = i == 0
            op = "0.55" if strong else "0.30"
            o.append(f'<rect x="{x:.0f}" y="{yy}" width="{cw:.0f}" height="{CH}" rx="11" '
                     f'fill="{PANEL}" stroke="{accent}" stroke-opacity="{op}" '
                     f'stroke-width="{2 if strong else 1.2}">')
            o.append(f'<animate attributeName="stroke-opacity" values="{op};0.95;{op};{op}" '
                     f'keyTimes="0;0.06;0.30;1" begin="{bi * step:.2f}s" '
                     f'dur="{cycle:.2f}s" repeatCount="indefinite"/>')
            o.append("</rect>")
            o.append(icon(ic, accent, x + 18, yy + CH / 2 - 15, 1.25))
            tx = x + 54
            o.append(f'<text x="{tx:.0f}" y="{yy + (CH / 2) - (5 if sub else -5):.0f}" '
                     f'font-family="{FONT}" font-size="15" font-weight="700" '
                     f'fill="{INK}">{esc(title)}</text>')
            if sub:
                o.append(f'<text x="{tx:.0f}" y="{yy + CH / 2 + 15:.0f}" '
                         f'font-family="{FONT}" font-size="12.5" '
                         f'fill="{DIM}">{esc(sub)}</text>')
            if i < chain_len - 1:
                o += arrow_h(x + cw, x + cw + GAP, yy + CH / 2, "#4c3a72")
        edges.append((yy, yy + CH, cw))
        y = yy + CH + BAND_GAP

    # Between bands: one arrow down the middle. Sources feed the engine; the
    # engine feeds the interfaces.
    for a, b in zip(edges, edges[1:]):
        o += arrow_v(W / 2, a[1], b[0] , "#5b6a86")

    # The feedback edge: replay engine back to STRATEGIES, not to the
    # resampler. ReplayEngine.step() calls self.strategy.on_bar() once per
    # bar and never touches the resampler -- so the loop is the engine driving
    # the strategy each tick, which is what makes a replay deterministic
    # rather than a one-way pass. Drawn dashed and beneath, as a return path.
    cw_core = edges[1][2]
    x_res = PAD + 2 * (cw_core + GAP) + cw_core / 2   # Strategies, index 2
    x_rep = PAD + 4 * (cw_core + GAP) + cw_core / 2   # Replay Engine, index 4
    y_core_bot = edges[1][1]
    y_loop = y_core_bot + 26
    o.append(f'<path d="M {x_rep:.0f} {y_core_bot} V {y_loop:.0f} H {x_res:.0f} V {y_core_bot}" '
             f'fill="none" stroke="{VIOLET}" stroke-opacity=".45" stroke-width="1.4" '
             f'stroke-dasharray="5 5"/>')
    o.append(f'<path d="M {x_res - 4:.0f} {y_core_bot + 7:.0f} L {x_res:.0f} {y_core_bot:.0f} '
             f'L {x_res + 4:.0f} {y_core_bot + 7:.0f} Z" fill="{VIOLET}" fill-opacity=".55"/>')

    o += dot([(W / 2, edges[0][1]), (W / 2, edges[1][0]),
              (W / 2, edges[1][1]), (W / 2, edges[2][0])], 0, cycle, TEAL)
    o.append("</svg>")
    return "\n".join(o) + "\n"


DIAGRAMS = {
    "workflow.svg": workflow,
    "execution.svg": lambda: chain([
        ("Bars", None, None, False),
        ("Strategy", "signal", None, False),
        ("Paper Broker", None, AMBER, True),
        ("Fill", "+ slippage, + commission", AMBER, True),
        ("Position & P&L", None, None, False),
        ("Metrics", None, None, False),
    ], rows=1, label="Bars produce a strategy signal, the paper broker fills it with "
                     "slippage and commission, and the position becomes P&L and metrics"),
    "architecture.svg": architecture,
    "about-01.svg": lambda: about_header("01", "book", SKY),
    "rule-01.svg": lambda: about_rule(SKY),
    "about-02.svg": lambda: about_header("02", "scales", AMBER),
    "rule-02.svg": lambda: about_rule(AMBER),
    "about-03.svg": lambda: about_header("03", "trusted", VIOLET),
    "rule-03.svg": lambda: about_rule(VIOLET),
}


if __name__ == "__main__":
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(".")
    for name, fn in DIAGRAMS.items():
        svg = fn()
        p = out / name
        p.write_text(svg, encoding="utf-8")
        print(f"wrote {p}  ({len(svg):,} chars, "
              f"{svg.count('<animate ')} animations, "
              f"{svg.count('type=\"rotate\"')} rotations, "
              f"{svg.count('<filter')} filters)")
