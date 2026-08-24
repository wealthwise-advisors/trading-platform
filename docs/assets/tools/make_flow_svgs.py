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


def dot(pts, begin, dur, accent):
    """One dot walking a list of (x, y) stops, once per cycle."""
    n = len(pts)
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


# ══ architecture: three bands ═════════════════════════════════════════════
def architecture():
    PAD, GAP, CH = 26, 20, 70
    BAND_LBL = 26
    # The third field says how many LEADING boxes form a left-to-right chain.
    # This matters and is easy to get wrong: the three data sources are
    # alternatives, not a pipeline -- in the mermaid original all three fed the
    # resampler independently, and drawing Schwab -> CSV -> Synthetic would
    # claim a sequence that does not exist. Same for the interfaces. Only the
    # core has a real chain, and only for its first four: the replay engine
    # branches off the resampler rather than following the paper broker.
    bands = [
        ("Data Sources", SKY, 0, [
            ("Schwab API", "live · ~180 days"),
            ("CSV archive", "18 years"),
            ("Synthetic", "deterministic"),
        ]),
        ("Core Engine · src/", VIOLET, 4, [
            ("Resampler", "one shared aggregator"),
            ("Analysis", "waves · patterns · VWAP"),
            ("Strategies", "five, one interface"),
            ("Paper Broker", "commission · slippage"),
            ("Replay Engine", "shared market clock"),
        ]),
        ("Interfaces", TEAL, 0, [
            ("FastAPI", "REST + WebSocket"),
            ("React Dashboard", None),
            ("Export", "CSV · XLSX · PDF · DOCX"),
        ]),
    ]
    BAND_GAP = 54
    H = 24 + sum(BAND_LBL + CH for _ in bands) + BAND_GAP * (len(bands) - 1) + 26

    o = [head(H, "Data sources feed one core engine, which the interfaces read; "
                 "the engine imports nothing from them")]
    y = 24
    band_mid = []
    step, cycle = 1.1, 3.3
    for bi, (name, accent, chain_len, items) in enumerate(bands):
        o.append(f'<text x="{PAD}" y="{y + 13}" font-family="{MONO}" font-size="12.5" '
                 f'letter-spacing="1" fill="{accent}" fill-opacity=".85">'
                 f'{esc(name.upper())}</text>')
        yy = y + BAND_LBL
        n = len(items)
        cw = (W - 2 * PAD - GAP * (n - 1)) / n
        for i, (title, sub) in enumerate(items):
            x = PAD + i * (cw + GAP)
            o += card(x, yy, cw, CH, title, sub, accent, bi * step, cycle, i == 0)
            # only inside a real chain, and never past its end
            if i < chain_len - 1:
                o += arrow_h(x + cw, x + cw + GAP, yy + CH / 2, "#2a3a52")
        if chain_len and chain_len < n:
            # the branch: this box hangs off the first, it does not follow the last
            bx = PAD + chain_len * (cw + GAP)
            o.append(f'<path d="M {PAD + cw / 2:.0f} {yy + CH:.0f} V {yy + CH + 16:.0f} '
                     f'H {bx + cw / 2:.0f} V {yy + CH:.0f}" fill="none" '
                     f'stroke="#2a3a52" stroke-width="1.4" stroke-dasharray="4 4"/>')
        band_mid.append((yy, yy + CH))
        y = yy + CH + BAND_GAP

    for a, b in zip(band_mid, band_mid[1:]):
        o += arrow_v(W / 2, a[1], b[0])
    o += dot([(W / 2, band_mid[0][1]), (W / 2, band_mid[1][0]),
              (W / 2, band_mid[1][1]), (W / 2, band_mid[2][0])], 0, cycle, TEAL)
    o.append("</svg>")
    return "\n".join(o) + "\n"


DIAGRAMS = {
    "workflow.svg": lambda: chain([
        ("Idea", None, None, False),
        ("Research", "measure it", None, False),
        ("Implement", "+ tests that can fail", None, False),
        ("Verify", "1,853 tests · ruff · tsc", TEAL, True),
        ("Backtest & Replay", "against real bars", None, False),
        ("Pull Request", "6 CI checks", None, False),
        ("Merge", None, None, False),
        ("Deploy", "SHA asserted", TEAL, True),
    ], rows=2, label="A change travels from idea through research, implementation, "
                     "verification, backtest, pull request and merge to a deploy "
                     "whose commit is asserted"),
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
