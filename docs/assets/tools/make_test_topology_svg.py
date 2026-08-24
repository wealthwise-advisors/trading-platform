"""
Generate docs/assets/test-topology.svg -- the three kinds of test, in the README.

WHAT THIS IS
------------
The suite is not one undifferentiated pile of 1,853 assertions. It contains
three kinds of test, and what a failure MEANS is different in each. That
distinction lives in docs/ARCHITECTURE.md but has never been in the README,
where it matters most: a contributor reading a red baseline test needs to know
that re-baselining it throws away the verification that made it worth having.

One header bar for the suite, three cards beneath it, right-angle connectors
down to each. Not a left-to-right pipeline -- these are categories, not stages,
and drawing them as a sequence would imply an order that does not exist.

WHERE THE NUMBERS COME FROM
---------------------------
Every count below was read from `pytest --collect-only` on the current tree,
not estimated. The three cards name representative files rather than claiming
exhaustive category totals, because the categories are a reading of the suite
rather than a property pytest reports -- so a total would be a number this
drawing could not defend.

WHAT THE MOTION DOES
--------------------
One dot leaves the suite bar and travels down one elbow at a time, in card
order, and the receiving card's border brightens as it lands. That is the only
thing moving: it says "these three come out of the one suite" and nothing else.
No rotation, no glow, no particles, nothing looping for decoration.

A NOTE ON REDUCED MOTION
------------------------
SMIL cannot be gated by prefers-reduced-motion -- CSS loses to SMIL in the
cascade and this loads through an <img>. So the motion is kept quiet enough
that gating is not needed, rather than claiming a switch that does not exist.

SMIL NOTES, LEARNED THE HARD WAY (same three as the other generators)
---------------------------------------------------------------------
* Two <animate> on the SAME attribute of the SAME element: the later silently
  wins from t=0. One animation per attribute, always.
* An animated attribute must ALSO be set statically, or it renders at its
  default until its begin time arrives.
* GitHub proxies this image: SMIL survives, CSS animation and script do not.
"""
import pathlib
import sys

W = 1280
PAD = 26
GAP = 24
COLS = 3
CARD_W = (W - 2 * PAD - GAP * (COLS - 1)) // COLS

BAR_Y = 26
BAR_H = 46
CARD_Y = 150
CARD_H = 214
H = CARD_Y + CARD_H + 30

FONT = ("ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "Roboto,Helvetica,Arial,sans-serif")
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

INK = "#eaf3ff"
DIM = "#8ba1bc"
LINE = "#1e2d42"

STEP = 1.25
CYCLE = COLS * STEP


# kind, subtitle, [(file, count)], what a failure means, accent
KINDS = [
    ("Unit / engine",
     "One mechanism, in isolation",
     [("test_engine.py", "5")],
     "A mechanism broke.",
     "#22d3ee"),
    ("Behavioural matrix",
     "Every combination of a rule",
     [("test_follow_live_matrix.py", "107"),
      ("test_multi_replay.py", "89"),
      ("test_replay_follow_live.py", "29")],
     "A rule about what you are shown broke.",
     "#a855f7"),
    ("Confirmed baseline",
     "Output verified against real data",
     [("test_indicator_correctness.py", "790"),
      ("test_reference_platform_parity.py", "57"),
      ("test_swing_zigzag_regression.py", "48")],
     "Something already confirmed has changed.",
     "#22c55e"),
]


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build() -> str:
    o: list[str] = []
    o.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" '
        f'aria-label="The test suite splits into three kinds: unit, '
        f'behavioural matrix, and confirmed baseline. A failure means '
        f'something different in each.">'
    )
    o.append('<rect width="100%" height="100%" fill="#060b14"/>')

    # ── the suite bar ─────────────────────────────────────────────────────
    bar_w = W - 2 * PAD
    o.append(f'<rect x="{PAD}" y="{BAR_Y}" width="{bar_w}" height="{BAR_H}" '
             f'rx="10" fill="#0b1220" stroke="{LINE}"/>')
    o.append(f'<text x="{PAD + 18}" y="{BAR_Y + 29}" font-family="{FONT}" '
             f'font-size="13.5" font-weight="700" fill="{INK}">'
             f'The suite</text>')
    o.append(f'<text x="{PAD + 96}" y="{BAR_Y + 29}" font-family="{MONO}" '
             f'font-size="12" fill="{DIM}">'
             f'1,853 passing &#183; 1,557 Python &#183; 296 web</text>')
    o.append(f'<text x="{W - PAD - 18}" y="{BAR_Y + 29}" text-anchor="end" '
             f'font-family="{MONO}" font-size="11" letter-spacing="0.6" '
             f'fill="#4d6280">THREE KINDS</text>')

    # ── cards ─────────────────────────────────────────────────────────────
    for i, (title, sub, files, meaning, accent) in enumerate(KINDS):
        x = PAD + i * (CARD_W + GAP)
        cx = x + CARD_W / 2
        begin = i * STEP

        # right-angle elbow: down from the bar, across, down into the card
        y0 = BAR_Y + BAR_H
        ymid = y0 + (CARD_Y - y0) / 2
        o.append(f'<path d="M {W/2:.0f} {y0} V {ymid:.0f} H {cx:.0f} V {CARD_Y}" '
                 f'fill="none" stroke="{LINE}" stroke-width="1.4"/>')

        # the dot that travels the elbow once, in card order
        o.append(f'<circle r="3.2" fill="{accent}" opacity="0">')
        o.append(f'  <animate attributeName="opacity" values="0;1;1;0" '
                 f'keyTimes="0;0.08;0.72;1" begin="{begin:.2f}s" dur="{STEP:.2f}s" '
                 f'repeatCount="indefinite"/>')
        o.append(f'  <animate attributeName="cx" values="{W/2:.0f};{W/2:.0f};{cx:.0f};{cx:.0f}" '
                 f'keyTimes="0;0.30;0.68;1" begin="{begin:.2f}s" dur="{STEP:.2f}s" '
                 f'repeatCount="indefinite"/>')
        o.append(f'  <animate attributeName="cy" values="{y0};{ymid:.0f};{ymid:.0f};{CARD_Y}" '
                 f'keyTimes="0;0.30;0.68;1" begin="{begin:.2f}s" dur="{STEP:.2f}s" '
                 f'repeatCount="indefinite"/>')
        o.append("</circle>")

        # the card, its border brightening as the dot lands
        o.append(f'<rect x="{x}" y="{CARD_Y}" width="{CARD_W}" height="{CARD_H}" '
                 f'rx="12" fill="#0b1220" stroke="{accent}" stroke-opacity="0.28" '
                 f'stroke-width="1.4">')
        o.append(f'  <animate attributeName="stroke-opacity" '
                 f'values="0.28;0.9;0.28;0.28" keyTimes="0;0.06;0.34;1" '
                 f'begin="{begin + STEP * 0.9:.2f}s" dur="{CYCLE:.2f}s" '
                 f'repeatCount="indefinite"/>')
        o.append("</rect>")

        ty = CARD_Y + 32
        o.append(f'<text x="{x + 18}" y="{ty}" font-family="{FONT}" '
                 f'font-size="14" font-weight="700" fill="{INK}">{esc(title)}</text>')
        o.append(f'<text x="{x + 18}" y="{ty + 19}" font-family="{FONT}" '
                 f'font-size="11.5" fill="{DIM}">{esc(sub)}</text>')

        # representative files, each with its real collected count
        fy = ty + 46
        for fname, count in files:
            o.append(f'<rect x="{x + 18}" y="{fy - 11}" width="{CARD_W - 36}" '
                     f'height="20" rx="5" fill="{accent}" fill-opacity="0.07"/>')
            o.append(f'<text x="{x + 25}" y="{fy + 3.5}" font-family="{MONO}" '
                     f'font-size="10.5" fill="{accent}">{esc(fname)}</text>')
            o.append(f'<text x="{x + CARD_W - 25}" y="{fy + 3.5}" text-anchor="end" '
                     f'font-family="{MONO}" font-size="10.5" fill="{DIM}">{count}</text>')
            fy += 25

        # what a failure here means
        my = CARD_Y + CARD_H - 30
        o.append(f'<line x1="{x + 18}" y1="{my - 20}" x2="{x + CARD_W - 18}" '
                 f'y2="{my - 20}" stroke="{LINE}"/>')
        o.append(f'<text x="{x + 18}" y="{my - 4}" font-family="{MONO}" '
                 f'font-size="9.5" letter-spacing="0.5" fill="#4d6280">'
                 f'A FAILURE MEANS</text>')
        o.append(f'<text x="{x + 18}" y="{my + 13}" font-family="{FONT}" '
                 f'font-size="11.5" fill="{INK}">{esc(meaning)}</text>')

    o.append("</svg>")
    return "\n".join(o) + "\n"


if __name__ == "__main__":
    dest = pathlib.Path(sys.argv[1])
    svg = build()
    dest.write_text(svg, encoding="utf-8")
    print(f"wrote {dest}  ({len(svg):,} chars)")
    print(f"  cards            : {len(KINDS)}")
    print(f"  <animate>        : {svg.count('<animate ')}")
    print(f"  <animateTransform>: {svg.count('<animateTransform')}")
    print(f"  <filter>         : {svg.count('<filter')}")
