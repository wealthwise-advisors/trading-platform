"""
Generate docs/assets/overview.svg -- the README's opening summary.

WHAT IT IS FOR
--------------
One picture that answers, in a few seconds and in this order: what is this,
how does it work, what is it built with, and is it alive. Nothing else. Every
line of text has to help a first-time reader understand the project; anything
that only sounds good comes out.

WHY THE BOXES ARE NEARLY EMPTY
------------------------------
The six workflow boxes carry a number, an icon and two or three words. They
used to carry the detail as well -- "3 sources", "one aggregator", "fills &
costs", "Sharpe / MaxDD" -- which turned a glance into a read. The detail is
already in the README sections underneath; the picture's job is the shape of
the pipeline, not its specification.

The headings work the same way. "Build With ->" and nothing else; the sentence
that used to follow ("Modern tools for a reliable and scalable platform") said
nothing the logos beneath it did not.

REAL MARKS, NOT EMOJI
---------------------
Every technology is its own brand mark, vendored under docs/assets/brand/.
Eight come from simple-icons in their official brand colours; the AWS wordmark
comes from devicon; the Charles Schwab mark is set as a wordmark because it IS
one -- italic serif over caps on their blue. Emoji were the previous approach
and they read as decoration, not as "this project runs on Docker".

THE NUMBERS ARE MEASURED, NEVER TYPED FROM MEMORY
-------------------------------------------------
Tests and coverage below are read from the tree and from CI, and both had
drifted badly before this file existed: the README simultaneously claimed 1,864
and 2,147 tests, and 77% and 78.2% coverage. A number on the first image
someone sees is the one they will quote back, so STATS carries where each came
from and how to re-check it.
"""

import pathlib
import re
import sys

W = 1080
PAD = 26

BG = "#05080f"
PANEL = "#0a0f1a"
EDGE = "#16202f"
INK = "#e8f0fa"
DIM = "#8ba0b8"
TEAL = "#2dd4bf"
BLUE = "#38bdf8"
GREEN = "#22c55e"
VIOLET = "#a855f7"
AMBER = "#f59e0b"

FONT = ("ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "Roboto,Helvetica,Arial,sans-serif")

QUOTE = "Turning trading ideas into data-driven results."

# Broken where it fits the panel, not where a sentence would naturally wrap:
# SVG text does not wrap, so an overlong line is drawn straight off the edge.
DEFINITION = [
    "AutoTrader is a futures trading research platform that lets",
    "you test, refine and deploy trading strategies using real",
    "market data with realistic costs.",
]

# number, label, accent. No descriptions -- see the module docstring.
STEPS = [
    ("01", "Market Data", BLUE),
    ("02", "Prepare Data", TEAL),
    ("03", "Analyze", BLUE),
    ("04", "Test Strategy", VIOLET),
    ("05", "Simulate Trades", AMBER),
    ("06", "Results", GREEN),
]

# file stem under docs/assets/brand/, label
TECH = [
    ("python", "Python"), ("fastapi", "FastAPI"), ("react", "React"),
    ("typescript", "TypeScript"), ("vite", "Vite"), ("pandas", "pandas"),
    ("tailwindcss", "Tailwind"), ("docker", "Docker"),
    ("aws", "AWS EC2"), ("schwab", "Schwab"),
]

# label, value, colour, where the value came from
STATS = [
    ("CI", "PASSING", GREEN, "the CI workflow's own conclusion"),
    ("DEPLOY", "LIVE", AMBER, "deploy asserts the served commit == github.sha"),
    ("TESTS", "2,183 PASSING", GREEN,
     "1,840 from `pytest --collect-only` + 343 from `vitest list`"),
    ("COVERAGE", "78.6%", BLUE, "CI: pytest --cov=src --cov=api, TOTAL line"),
]


BRAND = pathlib.Path(__file__).resolve().parents[1] / "brand"


def mark(stem, x, y, size):
    """A brand SVG inlined at (x, y), scaled to fit `size`.

    Inlined rather than referenced. An <image href="brand/x.svg"> resolves fine
    when the page loads this file directly, and loads NOTHING when the file is
    shown through an <img> -- which is exactly how GitHub renders a README
    image. The first version did that and every logo came out blank.
    """
    raw = (BRAND / f"{stem}.svg").read_text(encoding="utf-8")
    vb = re.search(r'viewBox="([\d.\s-]+)"', raw).group(1).split()
    vw, vh = float(vb[2]), float(vb[3])
    inner = re.sub(r"^.*?<svg[^>]*>|</svg>\s*$", "", raw, flags=re.S)
    inner = re.sub(r"<title>.*?</title>", "", inner, flags=re.S)
    root_fill = re.search(r'<svg[^>]*\sfill="([^"]+)"', raw)
    k = size / max(vw, vh)
    dx = x + (size - vw * k) / 2
    dy = y + (size - vh * k) / 2
    fill = f' fill="{root_fill.group(1)}"' if root_fill else ""
    return (f'<g transform="translate({dx:.2f},{dy:.2f}) scale({k:.4f})"{fill}>'
            f'{inner}</g>')


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fits(text, width, want, advance=0.52, floor=9.0):
    """Largest size at or below `want` keeping `text` inside `width`."""
    if not text:
        return want
    return max(floor, min(want, width / (len(text) * advance)))


def panel(o, x, y, w, h, stroke=EDGE, fill=PANEL, r=12, sw=1):
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
             f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def arrow(o, x, y, colour=TEAL, w=22):
    """The connector used between a heading and its content, and between steps."""
    o.append(f'<path d="M {x} {y} h {w-7}" stroke="{colour}" stroke-width="2" '
             f'stroke-linecap="round" fill="none"/>'
             f'<path d="M {x+w-9} {y-4.5} l 5 4.5 l -5 4.5" stroke="{colour}" '
             f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
             f'fill="none"/>')


def icon(o, key, x, y, colour):
    """Section glyphs, drawn on a 24x24 grid at (x, y)."""
    a = (f'fill="none" stroke="{colour}" stroke-width="1.9" '
         f'stroke-linecap="round" stroke-linejoin="round"')
    g = f'<g transform="translate({x},{y})">'
    if key == "book":
        g += (f'<path d="M3.5 4.5h6a3 3 0 0 1 3 3v13a2.4 2.4 0 0 0-2.4-2.4H3.5z" {a}/>'
              f'<path d="M20.5 4.5h-6a3 3 0 0 0-3 3v13a2.4 2.4 0 0 1 2.4-2.4h6.6z" {a}/>')
    elif key == "gear":
        g += (f'<circle cx="12" cy="12" r="3.4" {a}/>'
              f'<path d="M12 2.6v3M12 18.4v3M2.6 12h3M18.4 12h3'
              f'M5.4 5.4l2.1 2.1M16.5 16.5l2.1 2.1M18.6 5.4l-2.1 2.1'
              f'M7.5 16.5l-2.1 2.1" {a}/>')
    elif key == "tools":
        g += (f'<path d="M14.5 6.2a3.6 3.6 0 0 0 4.9 4.9L21 12.7 12.7 21 4.4 12.7'
              f'l1.6-1.6a3.6 3.6 0 0 0 4.9-4.9L12.7 3.8z" {a}/>')
    elif key == "shield":
        g += (f'<path d="M12 2.8 4.9 5.8v5.9c0 4.4 3 8.5 7.1 9.7 4.1-1.2 7.1-5.3 '
              f'7.1-9.7V5.8z" {a}/><path d="m8.8 11.9 2.4 2.4 4.2-4.7" {a}/>')
    else:                                   # scales -- the licence
        g += (f'<path d="M12 3.4v17.2M6.6 20.6h10.8" {a}/>'
              f'<path d="M12 6.2 5 8.2M12 6.2l7 2" {a}/>'
              f'<path d="M2.6 14.2 5 8.2l2.4 6a3.6 3.6 0 0 1-4.8 0z" {a}/>'
              f'<path d="M16.6 14.2 19 8.2l2.4 6a3.6 3.6 0 0 1-4.8 0z" {a}/>')
    return o.append(g + "</g>")


def build():
    o = []
    y = 0
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} 660" '
             f'width="{W}" height="660" role="img" aria-label="AutoTrader overview: '
             f'a futures trading research platform. Market data, prepare, analyze, '
             f'test strategy, simulate trades, results. Built with Python, FastAPI, '
             f'React, TypeScript, Vite, pandas, Tailwind, Docker, AWS EC2 and Schwab. '
             f'CI passing, deployed live, 2,183 tests passing, 78.6% coverage, '
             f'proprietary licence.">')
    o.append(f'<rect width="{W}" height="660" fill="{BG}"/>')

    # ── the quotation, and nothing above it ───────────────────────────────
    qh = 66
    panel(o, PAD + 300, 20, W - 2 * PAD - 600, qh, stroke=TEAL + "55", r=10)
    o.append(f'<text x="{W/2}" y="61" text-anchor="middle" font-family="{FONT}" '
             f'font-size="25" font-weight="700" fill="{INK}">'
             f'“Turning trading ideas into '
             f'<tspan fill="{TEAL}">data-driven results</tspan>.”</text>')

    # ── what it is ────────────────────────────────────────────────────────
    y = 104
    hh = 74
    panel(o, PAD, y, 470, hh)
    icon(o, "book", PAD + 22, y + 25, TEAL)
    o.append(f'<text x="{PAD+62}" y="{y+45}" font-family="{FONT}" font-size="21" '
             f'font-weight="700" fill="{INK}">What is AutoTrader?</text>')
    arrow(o, PAD + 300, y + 38, TEAL, 26)
    panel(o, PAD + 486, y, W - PAD - (PAD + 486), hh)
    for i, ln in enumerate(DEFINITION):
        o.append(f'<text x="{PAD+508}" y="{y+26+i*19}" font-family="{FONT}" '
                 f'font-size="14" fill="{DIM}">{esc(ln)}</text>')

    # ── how it works ──────────────────────────────────────────────────────
    y = 200
    panel(o, PAD, y, W - 2 * PAD, 150)
    icon(o, "gear", PAD + 22, y + 18, TEAL)
    o.append(f'<text x="{PAD+62}" y="{y+38}" font-family="{FONT}" font-size="21" '
             f'font-weight="700" fill="{INK}">How AutoTrader Works</text>')

    bx0, bw, gap = PAD + 18, 0, 30
    avail = W - 2 * (PAD + 18) - gap * (len(STEPS) - 1)
    bw = avail / len(STEPS)
    by, bh = y + 56, 76
    for i, (num, label, accent) in enumerate(STEPS):
        x = bx0 + i * (bw + gap)
        panel(o, x, by, bw, bh, stroke=accent + "88", fill="#0b1220", r=10)
        o.append(f'<text x="{x+12}" y="{by+21}" font-family="{FONT}" font-size="14" '
                 f'font-weight="700" fill="{accent}">{num}</text>')
        o.append(f'<text x="{x+bw/2:.1f}" y="{by+62}" text-anchor="middle" '
                 f'font-family="{FONT}" font-size="{fits(label, bw-14, 14):.1f}" '
                 f'font-weight="600" fill="{INK}">{esc(label)}</text>')
        if i < len(STEPS) - 1:
            arrow(o, x + bw + 5, by + bh / 2, accent, gap - 10)

    # ── build with ────────────────────────────────────────────────────────
    y = 368
    panel(o, PAD, y, W - 2 * PAD, 116)
    icon(o, "tools", PAD + 22, y + 34, TEAL)
    o.append(f'<text x="{PAD+62}" y="{y+54}" font-family="{FONT}" font-size="21" '
             f'font-weight="700" fill="{INK}">Build With</text>')
    arrow(o, PAD + 196, y + 47, TEAL, 26)

    tx0 = PAD + 244
    tw = (W - PAD - 16 - tx0) / len(TECH)
    for i, (stem, label) in enumerate(TECH):
        cx = tx0 + i * tw + tw / 2
        # 34px tall, centred: every mark carries its own explicit size, so
        # none of them can resolve to the full cell -- see make_legal_svgs.py.
        o.append(mark(stem, cx - 17, y + 24, 34))
        o.append(f'<text x="{cx:.1f}" y="{y+80}" text-anchor="middle" '
                 f'font-family="{FONT}" font-size="{fits(label, tw-6, 12):.1f}" '
                 f'fill="{DIM}">{esc(label)}</text>')

    # ── project status + licence ──────────────────────────────────────────
    y = 502
    panel(o, PAD, y, W - 2 * PAD, 92)
    icon(o, "shield", PAD + 22, y + 22, TEAL)
    o.append(f'<text x="{PAD+62}" y="{y+42}" font-family="{FONT}" font-size="21" '
             f'font-weight="700" fill="{INK}">Project Status</text>')
    arrow(o, PAD + 232, y + 35, TEAL, 26)

    sx = PAD + 254
    for label, value, colour, _src in STATS:
        lw = len(label) * 6.9 + 12
        vw = len(value) * 6.7 + 14
        panel(o, sx, y + 18, lw + vw, 34, stroke=EDGE, fill="#0d1522", r=7)
        o.append(f'<text x="{sx+lw/2:.1f}" y="{y+40}" text-anchor="middle" '
                 f'font-family="{FONT}" font-size="12" fill="{DIM}">{label}</text>')
        o.append(f'<rect x="{sx+lw}" y="{y+18}" width="{vw}" height="34" rx="7" '
                 f'fill="{colour}"/>')
        o.append(f'<text x="{sx+lw+vw/2:.1f}" y="{y+40}" text-anchor="middle" '
                 f'font-family="{FONT}" font-size="12" font-weight="700" '
                 f'fill="#04121c">{esc(value)}</text>')
        sx += lw + vw + 9

    # the licence sits on the same row, after a divider
    o.append(f'<line x1="{sx+6}" y1="{y+18}" x2="{sx+6}" y2="{y+52}" '
             f'stroke="{EDGE}" stroke-width="1.4"/>')
    icon(o, "scales", sx + 18, y + 23, TEAL)
    o.append(f'<text x="{sx+50}" y="{y+42}" font-family="{FONT}" font-size="18" '
             f'font-weight="700" fill="{INK}">License</text>')
    arrow(o, sx + 118, y + 35, TEAL, 20)
    lx = sx + 146
    panel(o, lx, y + 18, 64, 34, stroke=EDGE, fill="#0d1522", r=7)
    o.append(f'<text x="{lx+32}" y="{y+40}" text-anchor="middle" font-family="{FONT}" '
             f'font-size="11" fill="{DIM}">license</text>')
    o.append(f'<rect x="{lx+64}" y="{y+18}" width="78" height="34" rx="7" '
             f'fill="{VIOLET}"/>')
    o.append(f'<text x="{lx+103}" y="{y+40}" text-anchor="middle" font-family="{FONT}" '
             f'font-size="11" font-weight="700" fill="#150826">proprietary</text>')
    # A hard stop: if the row ever grows past the panel the badge is silently
    # clipped, which is how the first version shipped with "proprietar".
    assert lx + 142 <= W - PAD, f"status row overflows by {lx + 142 - (W - PAD)}px"

    o.append("</svg>")
    return "".join(o)


if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parents[1] / "overview.svg"
    svg = build()
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out}  ({len(svg):,} bytes)", file=sys.stderr)
    for label, value, _c, src in STATS:
        print(f"  {label:<9} {value:<14} <- {src}", file=sys.stderr)
