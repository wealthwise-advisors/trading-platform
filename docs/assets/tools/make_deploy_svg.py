"""
Generate docs/assets/deploy.svg -- the deployment pipeline in the README.

WHAT THIS IS TRYING TO BE
-------------------------
The section had a mermaid flowchart, which renders as grey boxes with an emoji
glued to the front of each label. That is fine as a sketch and poor as the
picture of the one guarantee this pipeline exists to make: a deploy asks the
running server which commit it is serving and FAILS unless it matches.

So the decision is drawn as a decision -- a diamond with two lettered exits,
one green and one red -- rather than as another box in the queue. The stages
light in sequence, and the run only reaches "confirmed" through the check.

ON LOGOS
--------
The reference for this drawing had GitHub's and Amazon's marks in it. They are
not reproduced here, for the same reason components/SymbolMark.tsx gives for
not fetching logos: shipping another company's trademarked artwork inside a
commercial product is a different thing from linking a badge service that
serves it. The stages are drawn glyphs and the names are set as text, which
identifies each step without redistributing anyone's mark.

SMIL NOTES (same three make_pipeline_svg.py learned the hard way)
----------------------------------------------------------------
* One <animate> per attribute per element.
* An animated attribute must ALSO be set statically.
* GitHub proxies this image: SMIL survives, CSS animation and script do not.
"""

import pathlib
import sys

W = 1280
H = 268
PAD = 26

BOX_W, BOX_H, GAP = 138, 74, 24
ROW_Y = 88

DIA_CX, DIA_RX, DIA_RY = 900, 66, 52
OUT_X = 1000
OUT_W = W - OUT_X - PAD
OUT_H = 60

FONT = ("ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "Roboto,Helvetica,Arial,sans-serif")
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

INK, DIM = "#eaf3ff", "#8ba1bc"
OK, BAD, DEC = "#22c55e", "#ef4444", "#a855f7"

# stage: label line 1, label line 2, accent, glyph key
STAGES = [
    ("Pull Request", "", "#3b82f6", "branch"),
    ("CI", "6 checks", "#22c55e", "check"),
    ("Merge to", "master", "#a855f7", "merge"),
    ("Deploy", "workflow", "#f43f5e", "rocket"),
    ("AWS EC2", "Docker Compose", "#f59e0b", "cloud"),
]

CYCLE = 9.0
STEP_T = 0.62
T_DEC = len(STAGES) * STEP_T + 0.3
T_OUT = T_DEC + 0.7


def lit(begin: float, lo: float, hi: float, attr: str = "opacity") -> str:
    """Light at `begin` and hold, so the path taken stays readable."""
    return (
        f'<animate attributeName="{attr}" values="{lo};{lo};{hi};{hi}" '
        f'keyTimes="0;{begin/CYCLE:.4f};{(begin+0.34)/CYCLE:.4f};1" '
        f'begin="0s" dur="{CYCLE}s" repeatCount="indefinite"/>'
    )


def glyph(key: str, cx: float, cy: float, colour: str) -> str:
    """A drawn mark per stage. No brand artwork -- see the module docstring."""
    a = (f'fill="none" stroke="{colour}" stroke-width="1.9" '
         f'stroke-linecap="round" stroke-linejoin="round"')
    g = f'<g transform="translate({cx-10:.1f},{cy-10:.1f})">'
    if key == "branch":       # a pull request: two lines rejoining
        g += (f'<path d="M4 3 v14" {a}/><circle cx="4" cy="3" r="2.2" {a}/>'
              f'<circle cx="4" cy="17" r="2.2" {a}/>'
              f'<path d="M16 6 v5 a4 4 0 0 1-4 4 H6" {a}/>'
              f'<circle cx="16" cy="4" r="2.2" {a}/>')
    elif key == "check":      # CI passing
        g += f'<circle cx="10" cy="10" r="8" {a}/><path d="M6.2 10.3 l2.6 2.6 l5-5.4" {a}/>'
    elif key == "merge":      # two branches becoming one
        g += (f'<circle cx="5" cy="4" r="2.2" {a}/><circle cx="5" cy="16" r="2.2" {a}/>'
              f'<circle cx="15" cy="10" r="2.2" {a}/>'
              f'<path d="M5 6.2 v3.6 a4 4 0 0 0 4 4 h3.8" {a}/>'
              f'<path d="M5 13.8 V10" {a}/>')
    elif key == "rocket":     # the deploy run
        g += (f'<path d="M10 2 c3.4 2.6 5 6 5 9.4 L10 17 L5 11.4 C5 8 6.6 4.6 10 2 Z" {a}/>'
              f'<circle cx="10" cy="8.4" r="1.9" {a}/>')
    else:                     # the server it lands on
        g += (f'<rect x="2.5" y="3" width="15" height="6" rx="1.6" {a}/>'
              f'<rect x="2.5" y="11" width="15" height="6" rx="1.6" {a}/>'
              f'<path d="M5.6 6 h.01M5.6 14 h.01" {a}/>')
    return g + "</g>"


def build() -> str:
    o: list[str] = []
    o.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" aria-label="Pull request, CI, merge '
        f'to master, deploy workflow and AWS EC2; the run then checks whether the '
        f'served commit equals github.sha and only confirms the deployment if it does">'
    )
    o.append(
        '<defs>'
        '<linearGradient id="pbg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#0d1424"/>'
        '<stop offset="100%" stop-color="#0a0f1c"/></linearGradient>'
        f'<marker id="pa" markerWidth="8" markerHeight="8" refX="6.5" refY="4" '
        f'orient="auto"><path d="M0 1 L7 4 L0 7 z" fill="{DIM}"/></marker>'
        f'<marker id="pok" markerWidth="8" markerHeight="8" refX="6.5" refY="4" '
        f'orient="auto"><path d="M0 1 L7 4 L0 7 z" fill="{OK}"/></marker>'
        f'<marker id="pbad" markerWidth="8" markerHeight="8" refX="6.5" refY="4" '
        f'orient="auto"><path d="M0 1 L7 4 L0 7 z" fill="{BAD}"/></marker>'
        '</defs>'
    )
    o.append(f'<rect width="{W}" height="{H}" rx="16" fill="url(#pbg)"/>')
    o.append(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="16" '
             f'fill="none" stroke="#1e2a44"/>')
    o.append(f'<text x="{PAD}" y="34" font-family="{MONO}" font-size="14" '
             f'letter-spacing="1.4" fill="{DIM}">EVERY DEPLOY PROVES WHAT IT SERVED</text>')

    # ── the five stages ───────────────────────────────────────────────────
    for i, (l1, l2, colour, key) in enumerate(STAGES):
        x = PAD + i * (BOX_W + GAP)
        cy = ROW_Y + BOX_H / 2
        t = i * STEP_T
        o.append(f'<rect x="{x}" y="{ROW_Y}" width="{BOX_W}" height="{BOX_H}" rx="11" '
                 f'fill="#101a2c" stroke="{colour}" stroke-opacity="0.28"/>')
        # the lit state, over the resting one
        o.append(f'<rect x="{x}" y="{ROW_Y}" width="{BOX_W}" height="{BOX_H}" rx="11" '
                 f'fill="{colour}" fill-opacity="0" stroke="{colour}" '
                 f'stroke-opacity="0" stroke-width="1.8">'
                 f'{lit(t, 0, 0.09, "fill-opacity")}{lit(t, 0, 0.85, "stroke-opacity")}</rect>')
        o.append(f'<rect x="{x+12}" y="{ROW_Y+18}" width="38" height="38" rx="9" '
                 f'fill="{colour}" fill-opacity="0.12"/>')
        o.append(glyph(key, x + 31, ROW_Y + 37, colour))
        ty = cy + (0 if not l2 else -5)
        o.append(f'<text x="{x+60}" y="{ty:.1f}" font-family="{FONT}" font-size="14" '
                 f'font-weight="600" fill="{INK}">{l1}</text>')
        if l2:
            o.append(f'<text x="{x+60}" y="{ty+15:.1f}" font-family="{FONT}" '
                     f'font-size="13" fill="{DIM}">{l2}</text>')
        if i < len(STAGES) - 1:
            ax = x + BOX_W + 4
            o.append(f'<path d="M {ax} {cy:.1f} L {ax+GAP-11} {cy:.1f}" stroke="{DIM}" '
                     f'stroke-width="1.8" marker-end="url(#pa)" opacity="0.25">'
                     f'{lit(t+0.3, 0.25, 1)}</path>')

    # ── the decision ──────────────────────────────────────────────────────
    last_r = PAD + (len(STAGES) - 1) * (BOX_W + GAP) + BOX_W
    dcy = ROW_Y + BOX_H / 2
    o.append(f'<path d="M {last_r+4} {dcy:.1f} L {DIA_CX-DIA_RX-10} {dcy:.1f}" '
             f'stroke="{DIM}" stroke-width="1.8" marker-end="url(#pa)" opacity="0.25">'
             f'{lit(T_DEC-0.3, 0.25, 1)}</path>')
    o.append(f'<path d="M {DIA_CX} {dcy-DIA_RY:.1f} L {DIA_CX+DIA_RX} {dcy:.1f} '
             f'L {DIA_CX} {dcy+DIA_RY:.1f} L {DIA_CX-DIA_RX} {dcy:.1f} Z" '
             f'fill="#101a2c" stroke="{DEC}" stroke-opacity="0.35"/>')
    o.append(f'<path d="M {DIA_CX} {dcy-DIA_RY:.1f} L {DIA_CX+DIA_RX} {dcy:.1f} '
             f'L {DIA_CX} {dcy+DIA_RY:.1f} L {DIA_CX-DIA_RX} {dcy:.1f} Z" '
             f'fill="{DEC}" fill-opacity="0" stroke="{DEC}" stroke-opacity="0" '
             f'stroke-width="1.8">{lit(T_DEC, 0, 0.10, "fill-opacity")}'
             f'{lit(T_DEC, 0, 0.9, "stroke-opacity")}</path>')
    for k, line in enumerate(("Served commit", "==", "github.sha ?")):
        o.append(f'<text x="{DIA_CX}" y="{dcy-14+k*15:.1f}" text-anchor="middle" '
                 f'font-family="{MONO}" font-size="14" fill="{INK}">{line}</text>')

    # ── the two exits ─────────────────────────────────────────────────────
    oy_ok = ROW_Y - 12
    oy_bad = ROW_Y + BOX_H + 6
    for label, colour, oy, marker, edge, t in (
        ("Deployment confirmed", OK, oy_ok, "pok", "yes", T_OUT),
        ("Fail the run", BAD, oy_bad, "pbad", "no", T_OUT),
    ):
        mid = oy + OUT_H / 2
        o.append(f'<path d="M {DIA_CX+DIA_RX+4} {dcy:.1f} C {OUT_X-34} {dcy:.1f}, '
                 f'{OUT_X-34} {mid:.1f}, {OUT_X-9} {mid:.1f}" fill="none" '
                 f'stroke="{colour}" stroke-width="1.8" marker-end="url(#{marker})" '
                 f'opacity="0">{lit(t, 0, 0.9)}</path>')
        o.append(f'<text x="{OUT_X-40}" y="{(dcy+mid)/2-6:.1f}" text-anchor="middle" '
                 f'font-family="{MONO}" font-size="12" fill="{colour}" opacity="0">'
                 f'{edge}{lit(t, 0, 1)}</text>')
        o.append(f'<rect x="{OUT_X}" y="{oy}" width="{OUT_W}" height="{OUT_H}" rx="11" '
                 f'fill="{colour}" fill-opacity="0.07" stroke="{colour}" '
                 f'stroke-opacity="0" stroke-width="1.8">{lit(t, 0, 0.85, "stroke-opacity")}</rect>')
        o.append(f'<text x="{OUT_X+18}" y="{mid+4.5:.1f}" font-family="{FONT}" '
                 f'font-size="14" font-weight="600" fill="{colour}" opacity="0.45">'
                 f'{label}{lit(t, 0.45, 1)}</text>')

    o.append(f'<text x="{PAD}" y="{H-16}" font-family="{FONT}" font-size="13" '
             f'fill="{DIM}">A deploy that quietly leaves the old build running is the '
             f'exact failure the last step exists to catch.</text>')
    o.append("</svg>")
    return "".join(o)


if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parents[1] / "deploy.svg"
    svg = build()
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out}  ({len(svg):,} bytes, {len(STAGES)} stages, {CYCLE}s loop)",
          file=sys.stderr)
