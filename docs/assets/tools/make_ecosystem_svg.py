"""
Generate docs/assets/ecosystem.svg -- the repository ecosystem in the README.

WHAT THIS IS TRYING TO BE
-------------------------
The section's flowchart drew two boxes: trading-platform and data. But the
paragraph under it tells a different, larger story -- FIVE predecessor
repositories were consolidated here and retired, their 442 files stripped of
hardcoded credentials on the way in. None of the five appeared in the picture,
so the diagram showed the smallest part of what the section says.

This draws the consolidation: the five folding in one at a time, through the
redaction gate that produced legacy/REDACTIONS.md, into legacy/ inside this
repository -- with data alongside, because that is a live dependency rather
than a retired ancestor and should not look like one.

EVERY NUMBER HERE IS THE README'S OWN
-------------------------------------
Five repositories, 442 files, an 18-year 1-minute ES series. Nothing is
invented for the drawing; if the section's numbers change, these have to change
with them.

SMIL NOTES (same three make_pipeline_svg.py learned the hard way)
----------------------------------------------------------------
* One <animate> per attribute per element.
* An animated attribute must ALSO be set statically.
* GitHub proxies this image: SMIL survives, CSS animation and script do not.
"""

import pathlib
import sys

W = 1280
PAD = 30

# The five, in the order the README lists them.
RETIRED = ["trading-strategy", "trading-web", "Wealthwise", "backtest", "Project_work"]

CARD_W, CARD_H, CARD_GAP = 210, 40, 12
COL_X = PAD + 6
GATE_X = COL_X + CARD_W + 96
HUB_X = GATE_X + 128
HUB_W = 360
DATA_X = HUB_X + HUB_W + 120   # 74 left the arrow label overlapping both
                               # boxes; the gap has to fit the label, not
                               # just the arrow
DATA_W = W - DATA_X - PAD

TOP = 74
# The left column is the tallest thing here, so it sets the height. +96
# left 114px of empty box under the hub content.
H = TOP + len(RETIRED) * (CARD_H + CARD_GAP) + 48

FONT = ("ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "Roboto,Helvetica,Arial,sans-serif")
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

INK, DIM, GRID = "#eaf3ff", "#8ba1bc", "#243049"
RETIRE = "#64748b"          # retired: grey, deliberately not a live colour
GATE = "#f59e0b"            # the redaction step
HUB = "#2dd4bf"             # this repository
DATA = "#3b82f6"            # the live dependency

CYCLE = 12.0
STAGGER = 0.9               # one predecessor folds in every 0.9s
T_GATE = len(RETIRED) * STAGGER + 0.4
T_HUB = T_GATE + 0.9
T_DATA = T_HUB + 1.0

COL_MID_Y = TOP + (len(RETIRED) * (CARD_H + CARD_GAP) - CARD_GAP) / 2


def fade(begin: float, lo: float = 0.0, hi: float = 1.0, dur: float = 0.45) -> str:
    return (
        f'<animate attributeName="opacity" values="{lo};{lo};{hi};{hi}" '
        f'keyTimes="0;{begin/CYCLE:.4f};{(begin+dur)/CYCLE:.4f};1" '
        f'begin="0s" dur="{CYCLE}s" repeatCount="indefinite"/>'
    )


def build() -> str:
    o: list[str] = []
    o.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" aria-label="Five predecessor '
        f'repositories were consolidated through a redaction step into legacy/ '
        f'inside trading-platform, which reads full market history from the data '
        f'repository">'
    )
    o.append(
        '<defs>'
        '<linearGradient id="ebg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#0d1424"/>'
        '<stop offset="100%" stop-color="#0a0f1c"/></linearGradient>'
        f'<marker id="ah" markerWidth="9" markerHeight="9" refX="7" refY="4.5" '
        f'orient="auto"><path d="M0 1 L8 4.5 L0 8 z" fill="{HUB}"/></marker>'
        f'<marker id="ad" markerWidth="9" markerHeight="9" refX="7" refY="4.5" '
        f'orient="auto"><path d="M0 1 L8 4.5 L0 8 z" fill="{DATA}"/></marker>'
        '</defs>'
    )
    o.append(f'<rect width="{W}" height="{H}" rx="16" fill="url(#ebg)"/>')
    o.append(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="16" '
             f'fill="none" stroke="#1e2a44"/>')

    # ── column headings ───────────────────────────────────────────────────
    o.append(f'<text x="{COL_X}" y="46" font-family="{MONO}" font-size="19.9" '
             f'letter-spacing="1.3" fill="{RETIRE}">RETIRED · 5 REPOSITORIES</text>')
    o.append(f'<text x="{HUB_X}" y="46" font-family="{MONO}" font-size="19.9" '
             f'letter-spacing="1.3" fill="{HUB}">THIS REPOSITORY</text>')
    o.append(f'<text x="{DATA_X}" y="46" font-family="{MONO}" font-size="19.9" '
             f'letter-spacing="1.3" fill="{DATA}">LIVE DEPENDENCY</text>')

    # ── the five predecessors, each folding in on its own beat ────────────
    for i, name in enumerate(RETIRED):
        y = TOP + i * (CARD_H + CARD_GAP)
        cy = y + CARD_H / 2
        t = i * STAGGER
        o.append(
            f'<g opacity="0.30">{fade(t, 0.30, 1.0)}'
            f'<rect x="{COL_X}" y="{y}" width="{CARD_W}" height="{CARD_H}" rx="9" '
            f'fill="#101a2c" stroke="{RETIRE}" stroke-opacity="0.5"/>'
            f'<text x="{COL_X+14}" y="{cy+4.5}" font-family="{MONO}" font-size="19.2" '
            f'fill="{DIM}">{name}</text></g>'
        )
        # Converging feeder into the gate. An elbow, not a bezier: a curved
        # flowing line reads as decoration, and this is a technical diagram --
        # the connection has to be obvious, not pretty.
        elbow = GATE_X - 34
        o.append(
            f'<path d="M {COL_X+CARD_W+6} {cy:.1f} H {elbow} V {COL_MID_Y:.1f} '
            f'H {GATE_X-6}" '
            f'fill="none" stroke="{RETIRE}" stroke-width="1.6" stroke-opacity="0">'
            f'<animate attributeName="stroke-opacity" values="0;0;0.75;0.35;0.35" '
            f'keyTimes="0;{t/CYCLE:.4f};{(t+0.35)/CYCLE:.4f};{(t+0.9)/CYCLE:.4f};1" '
            f'begin="0s" dur="{CYCLE}s" repeatCount="indefinite"/></path>'
        )

    # ── the redaction gate ────────────────────────────────────────────────
    gh = 82
    gy = COL_MID_Y - gh / 2
    o.append(f'<rect x="{GATE_X}" y="{gy:.1f}" width="104" height="{gh}" rx="10" '
             f'fill="{GATE}" fill-opacity="0.08" stroke="{GATE}" stroke-opacity="0.55"/>')
    o.append(f'<text x="{GATE_X+52}" y="{gy+30:.1f}" text-anchor="middle" '
             f'font-family="{MONO}" font-size="19.2" font-weight="700" fill="{GATE}">'
             f'REDACTED</text>')
    o.append(f'<text x="{GATE_X+52}" y="{gy+48:.1f}" text-anchor="middle" '
             f'font-family="{FONT}" font-size="19.9" fill="{DIM}">credentials</text>')
    o.append(f'<text x="{GATE_X+52}" y="{gy+63:.1f}" text-anchor="middle" '
             f'font-family="{FONT}" font-size="19.9" fill="{DIM}">stripped</text>')
    # it lights when the last predecessor has arrived
    o.append(f'<rect x="{GATE_X}" y="{gy:.1f}" width="104" height="{gh}" rx="10" '
             f'fill="{GATE}" fill-opacity="0">'
             f'<animate attributeName="fill-opacity" values="0;0;0.22;0.06;0.06" '
             f'keyTimes="0;{T_GATE/CYCLE:.4f};{(T_GATE+0.3)/CYCLE:.4f};'
             f'{(T_GATE+1.1)/CYCLE:.4f};1" begin="0s" dur="{CYCLE}s" '
             f'repeatCount="indefinite"/></rect>')

    o.append(f'<path d="M {GATE_X+104} {COL_MID_Y:.1f} L {HUB_X-8} {COL_MID_Y:.1f}" '
             f'stroke="{HUB}" stroke-width="2" marker-end="url(#ah)" opacity="0">'
             f'{fade(T_GATE+0.2)}</path>')

    # ── this repository ───────────────────────────────────────────────────
    hub_y = TOP - 8
    hub_h = H - hub_y - 62
    o.append(f'<rect x="{HUB_X}" y="{hub_y}" width="{HUB_W}" height="{hub_h}" rx="12" '
             f'fill="#0c1a22" stroke="{HUB}" stroke-width="2" stroke-opacity="0.75"/>')
    o.append(f'<text x="{HUB_X+18}" y="{hub_y+30}" font-family="{FONT}" font-size="23.4" '
             f'font-weight="700" fill="{HUB}">trading-platform</text>')
    o.append(f'<text x="{HUB_X+18}" y="{hub_y+49}" font-family="{FONT}" font-size="18.5" '
             f'fill="{DIM}">the platform · you are here</text>')

    # legacy/ inside it
    ly = hub_y + 66
    o.append(f'<g opacity="0">{fade(T_HUB)}'
             f'<rect x="{HUB_X+18}" y="{ly}" width="{HUB_W-36}" height="62" rx="9" '
             f'fill="#101a2c" stroke="{RETIRE}" stroke-opacity="0.6" '
             f'stroke-dasharray="5 4"/>'
             f'<text x="{HUB_X+32}" y="{ly+26}" font-family="{MONO}" font-size="19.9" '
             f'font-weight="700" fill="{DIM}">legacy/</text>'
             f'<text x="{HUB_X+32}" y="{ly+45}" font-family="{FONT}" font-size="18.5" '
             f'fill="{RETIRE}">442 files · reference only — no lint, no tests, '
             f'no image</text></g>')

    # the running app, below it
    ay = ly + 78
    o.append(f'<rect x="{HUB_X+18}" y="{ay}" width="{HUB_W-36}" height="44" rx="9" '
             f'fill="{HUB}" fill-opacity="0.10" stroke="{HUB}" stroke-opacity="0.45"/>')
    o.append(f'<text x="{HUB_X+32}" y="{ay+28}" font-family="{FONT}" font-size="15" '
             f'fill="{INK}">api/ · src/ · web/ — what actually runs</text>')

    # ── data ──────────────────────────────────────────────────────────────
    dy = COL_MID_Y - 62
    o.append(f'<rect x="{DATA_X}" y="{dy:.1f}" width="{DATA_W}" height="124" rx="12" '
             f'fill="#0b1526" stroke="{DATA}" stroke-width="2" stroke-opacity="0.7"/>')
    o.append(f'<text x="{DATA_X+16}" y="{dy+30:.1f}" font-family="{FONT}" '
             f'font-size="23.4" font-weight="700" fill="{DATA}">data</text>')
    o.append(f'<text x="{DATA_X+16}" y="{dy+50:.1f}" font-family="{FONT}" '
             f'font-size="18.5" fill="{DIM}">market history · Git LFS</text>')
    o.append(f'<rect x="{DATA_X+16}" y="{dy+66:.1f}" width="{DATA_W-32}" height="52" '
             f'rx="8" fill="{DATA}" fill-opacity="0.10"/>')
    o.append(f'<text x="{DATA_X+28}" y="{dy+88:.1f}" font-family="{MONO}" '
             f'font-size="16" fill="{INK}">18-year 1-minute ES</text>')
    o.append(f'<text x="{DATA_X+28}" y="{dy+108:.1f}" font-family="{FONT}" '
             f'font-size="15" fill="{DIM}">too large for an ordinary repo</text>')

    o.append(f'<path d="M {HUB_X+HUB_W+6} {COL_MID_Y:.1f} L {DATA_X-8} {COL_MID_Y:.1f}" '
             f'stroke="{DATA}" stroke-width="2" marker-end="url(#ad)" opacity="0">'
             f'{fade(T_DATA)}</path>')
    o.append(f'<text x="{(HUB_X+HUB_W+DATA_X)/2:.1f}" y="{COL_MID_Y-11:.1f}" '
             f'text-anchor="middle" font-family="{FONT}" font-size="19.2" '
             f'fill="{DIM}" opacity="0">reads history{fade(T_DATA)}</text>')

    o.append(f'<text x="{PAD}" y="{H-18}" font-family="{FONT}" font-size="18.5" '
             f'fill="{DIM}">Five repositories were retired into one archive; what runs '
             f'today is a single platform reading one shared history.</text>')

    o.append("</svg>")
    return "".join(o)


if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parents[1] / "ecosystem.svg"
    svg = build()
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out}  ({len(svg):,} bytes, {len(RETIRED)} retired repos, "
          f"{CYCLE}s loop)", file=sys.stderr)
