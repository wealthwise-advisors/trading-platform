"""
Generate the Licence / Ownership / Developed By / Project Link cards.

    legal-license.svg    the licence, its copyright line and the link to it
    legal-ownership.svg  who owns the project
    legal-developed.svg  who built it
    legal-project.svg    where to find it running and where the code lives

WHY THESE ARE DRAWN AND NOT WRITTEN
-----------------------------------
The design asked for is rounded cards with a thin blue-to-violet border, an
icon on a raised tile, and a row of labelled columns. A GitHub README cannot do
any of it: <style> is stripped, class attributes are ignored, and the table
borders you are left with are grey hairlines the theme owns. SVG renders, so
the cards are drawn.

WHAT THAT COSTS, AND WHAT IS DONE ABOUT IT
------------------------------------------
Text inside an image cannot be selected, copied, searched or read aloud, and an
<img> carries at most ONE link -- the <a> wrapped around it. That is a bad deal
for an email address or a URL, which exist to be clicked and copied. So every
card is wrapped in a link to its own target, and the README keeps the addresses
as real text beneath the Project Link card. The picture is the presentation;
the text under it is the part that works.

NO BRAND MARKS
--------------
The reference has GitHub's and LinkedIn's logos in it. Those are not reproduced
here, for the reason components/SymbolMark.tsx gives for not fetching logos:
redistributing another company's trademarked artwork inside a commercial
product is a different thing from linking to them. The icons are drawn.

ONLY REAL VALUES
----------------
FIELDS below carries what the repository actually knows -- the licence holder,
the git remote, the deploy target and the git author identity. A field with no
source in the project is absent rather than invented, and its column simply is
not drawn. Add the value and the column appears; nothing else needs changing.
"""

import pathlib
import sys

# ── palette ──────────────────────────────────────────────────────────────────
BG = "#080b12"
CARD = "#0b0f1a"
TILE = "#0d1526"
EDGE = "#1b2438"
INK = "#f1f5f9"
DIM = "#94a3b8"
VAL = "#cbd5e1"
BLUE = "#3b82f6"
BLUE_L = "#60a5fa"
VIOLET = "#a855f7"
VIOLET_L = "#c084fc"

FONT = ("ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "Roboto,Helvetica,Arial,sans-serif")

W = 980
PAD = 34


# ── the data, and only what the project actually holds ───────────────────────
# label, value, icon key, accent. A None value drops the column entirely --
# see the module docstring. The two phone numbers and the LinkedIn URLs in the
# reference design were sample values and have no counterpart here, so there
# are no columns for them.
OWNERSHIP = [
    ("Owner", "WealthWise Advisors", "org", BLUE_L),
    ("Email", None, "mail", BLUE_L),
    ("Contact", None, "phone", INK),
    ("GitHub", "github.com/wealthwise-advisors", "branch", VIOLET_L),
    ("LinkedIn", None, "badge", VIOLET_L),
]

DEVELOPED = [
    ("Developer", "Akash Yadav", "person", BLUE_L),
    ("Email", "akashyadav110502@gmail.com", "mail", BLUE_L),
    ("Contact", "+91 70053 63923", "phone", INK),
    ("GitHub", "github.com/akxyverse", "branch", VIOLET_L),
    ("LinkedIn", "linkedin.com/in/akash-yadav-122a75288", "badge", VIOLET_L),
]

# label, shown text, accent
PROJECT = [
    # The "github.com/" prefix is dropped: the label already says Repository,
    # and those eleven characters were a third of the button.
    ("Repository", "wealthwise-advisors/trading-platform", BLUE_L),
    ("Live app", "3-218-23-37.sslip.io", VIOLET_L),
    ("Local", "localhost:5173", DIM),
]


# ── icons, on the same 24x24 grid as every other icon in docs/assets ─────────
ICONS = {
    "license": ['<path d="M5.6 3.4h7.4L17 7.2v5.1"/>', '<path d="M17 16.4v4.2H5.6V3.4"/>',
                '<path d="M12.7 3.6v3.9H16.6"/>', '<path d="M8.3 11.2h4.4M8.3 14.3h3"/>',
                '<path d="M18.9 12.1l3.3 1.4v2.7c0 2-1.4 3.9-3.3 4.4-1.9-.5-3.3-2.4-3.3-4.4v-2.7z"/>',
                '<path d="m17.6 16.3 1 1 1.7-1.9"/>'],
    "org":     ['<path d="M4.2 20.4V6.1l7.3-2.5v16.8"/>', '<path d="M11.5 9.1h8.3v11.3"/>',
                '<path d="M2.6 20.4h18.8"/>', '<path d="M7 8.4h1.4M7 11.6h1.4M7 14.8h1.4"/>',
                '<path d="M14.6 12.4h2.2M14.6 15.6h2.2"/>'],
    "code":    ['<path d="M8.6 8.4 4.6 12l4 3.6"/>', '<path d="M15.4 8.4 19.4 12l-4 3.6"/>',
                '<path d="M13.4 5.6 10.6 18.4"/>'],
    "globe":   ['<circle cx="12" cy="12" r="8.6"/>', '<path d="M3.4 12h17.2"/>',
                '<path d="M12 3.4c2.2 2.3 3.4 5.4 3.4 8.6S14.2 18.3 12 20.6"/>',
                '<path d="M12 3.4C9.8 5.7 8.6 8.8 8.6 12s1.2 6.3 3.4 8.6"/>'],
    "person":  ['<circle cx="12" cy="8" r="3.6"/>',
                '<path d="M5.2 20c0-3.5 3-6.2 6.8-6.2s6.8 2.7 6.8 6.2"/>'],
    "mail":    ['<rect x="3.2" y="5.4" width="17.6" height="13.2" rx="2.2"/>',
                '<path d="m3.6 7 8.4 6 8.4-6"/>'],
    "phone":   ['<path d="M8.1 3.8 10 8l-2 1.9a12 12 0 0 0 6.1 6.1L16 14l4.2 1.9v3.2c0 .9-.8 1.6-1.7 1.5'
                'C9.7 20 4 14.3 3.4 5.5c-.1-.9.6-1.7 1.5-1.7z"/>'],
    "badge":   ['<rect x="3.6" y="3.6" width="16.8" height="16.8" rx="3.2"/>',
                '<path d="M8 10.6v6.2"/>', '<circle cx="8" cy="7.6" r="1.1"/>',
                '<path d="M12.2 16.8v-6.2M12.2 13.4c0-1.6 1.1-2.9 2.5-2.9s2.5 1.3 2.5 2.9v3.4"/>'],
    # A git branch, standing in for "GitHub". The octocat is a trademark
    # and is deliberately not reproduced -- see the module docstring.
    "branch":  ['<path d="M6.4 6.6v10.8"/>', '<circle cx="6.4" cy="4.6" r="2.1"/>',
                '<circle cx="6.4" cy="19.4" r="2.1"/>', '<circle cx="17.6" cy="6" r="2.1"/>',
                '<path d="M17.6 8.1v3.3a4.4 4.4 0 0 1-4.4 4.4H8.5"/>'],
    "out":     ['<path d="M14 4.4h5.6V10"/>', '<path d="M19.6 4.4 11.4 12.6"/>',
                '<path d="M17.4 13.6v5.2c0 .9-.7 1.6-1.6 1.6H5.6c-.9 0-1.6-.7-1.6-1.6V8.4'
                'c0-.9.7-1.6 1.6-1.6h5.2"/>'],
}


def icon(key, ink, x, y, s=1.0, sw=1.7):
    return (f'<g transform="translate({x:.1f} {y:.1f}) scale({s:.3f})" fill="none" '
            f'stroke="{ink}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round">{"".join(ICONS[key])}</g>')


def fits(text, width, want, advance=0.52, floor=11.0):
    """The largest size at or below `want` that keeps `text` inside `width`."""
    if not text:
        return want
    return max(floor, min(want, width / (len(text) * advance)))


def esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def head(h, label):
    """Card shell: the rounded panel and its blue-to-violet hairline border."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" '
        f'width="{W}" height="{h}" role="img" aria-label="{esc(label)}">'
        '<defs>'
        '<linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{BLUE}" stop-opacity=".85"/>'
        f'<stop offset="55%" stop-color="{VIOLET}" stop-opacity=".55"/>'
        f'<stop offset="100%" stop-color="{VIOLET}" stop-opacity=".8"/>'
        '</linearGradient>'
        '<linearGradient id="mark" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{BLUE_L}"/>'
        f'<stop offset="100%" stop-color="{VIOLET}"/>'
        '</linearGradient>'
        '<linearGradient id="tile" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="#101a2e"/>'
        f'<stop offset="100%" stop-color="{TILE}"/>'
        '</linearGradient>'
        '</defs>'
        f'<rect width="{W}" height="{h}" rx="18" fill="{BG}"/>'
        f'<rect x="1.1" y="1.1" width="{W-2.2}" height="{h-2.2}" rx="17" '
        f'fill="{CARD}" stroke="url(#edge)" stroke-width="1.4"/>'
    )


def tile(key, x, y, size):
    """The raised square the card's icon sits on."""
    return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{size*0.24:.1f}" '
            f'fill="url(#tile)" stroke="{EDGE}"/>'
            + icon(key, "url(#mark)", x + size * 0.22, y + size * 0.22,
                   size * 0.56 / 24, sw=1.9))


MIN_ONE_LINE = 15.0   # under this, one line is too small to be worth keeping


def wrap(value, width, size):
    """One line, or two split after a separator.

    Wrapping is a last resort: the test is against MIN_ONE_LINE, not against
    the target size, so "github.com/akxyverse" stays on one line at 16px
    instead of being split when it did not need to be.

    When it is needed, the break goes after a "/" or an "@" so each line still
    reads as part of one address -- "linkedin.com/in/" over the profile id,
    the way the reference design sets it, and "akashyadav110502@" over
    "gmail.com", which on a single line had been squeezed to 13px.
    """
    if len(value) * 0.52 * MIN_ONE_LINE <= width:
        return [value]
    # +2 on the bound: rfind's end is EXCLUSIVE, and the "@" in this email
    # sits at exactly 0.62 of its length, so the search window stopped one
    # character short of the only separator it had and never split at all.
    cut = max(value.rfind(c, 0, int(len(value) * 0.62) + 2) for c in "/@")
    if cut <= 0:
        return [value]
    return [value[:cut + 1], value[cut + 1:]]


def columns(o, items, x0, x1, y, label_size=19, value_size=19):
    """A row of labelled fields, hairline between each.

    Column widths follow the length of what is in them. Equal fifths would put
    "Akash Yadav" (11 characters) and a 37-character URL in the same box.
    """
    live = [it for it in items if it[1]]
    if not live:
        return
    span = x1 - x0
    # +8 so a short field keeps enough room for its own label and icon.
    # A column has to hold its LABEL as well as its value. Weighted on the
    # value alone, "Developer" over "Akash Yadav" got a box its own heading
    # ran out of, straight into the next column's icon.
    # Weighted on what each column will actually hold once wrapped, measured
    # against an even share first. Passing the whole span meant nothing ever
    # looked like it would wrap, so the email was weighted as 26 characters,
    # given a column too narrow for 26 characters, and shrunk to 13px.
    nominal = span / len(live) - 22
    wrapped = [wrap(it[1], nominal, value_size) for it in live]
    weights = [max(len(it[0]) * 0.85 + 4, *(len(w) for w in ws)) + 6
               for it, ws in zip(live, wrapped)]
    total = sum(weights)
    cx = x0
    for i, (label, value, key, accent) in enumerate(live):
        cw = span * weights[i] / total
        if i:
            o.append(f'<line x1="{cx-12:.1f}" y1="{y-24}" x2="{cx-12:.1f}" y2="{y+40}" '
                     f'stroke="{EDGE}" stroke-width="1.2"/>')
        o.append(icon(key, accent, cx, y - 15, 0.86, sw=1.8))
        o.append(f'<text x="{cx+30:.1f}" y="{y}" font-family="{FONT}" '
                 f'font-size="{fits(label, cw-38, label_size):.1f}" font-weight="600" '
                 f'fill="{accent}">{esc(label)}</text>')
        lines = wrap(value, cw - 22, value_size)
        size = min(fits(w, cw - 22, value_size) for w in lines)
        for j, line in enumerate(lines):
            o.append(f'<text x="{cx:.1f}" y="{y+34+j*22}" font-family="{FONT}" '
                     f'font-size="{size:.1f}" fill="{VAL}">{esc(line)}</text>')
        cx += cw


# ── the four cards ───────────────────────────────────────────────────────────
def license_card():
    H = 246
    o = [head(H, "Licence: proprietary, copyright WealthWise Advisors, "
                 "all rights reserved")]
    o.append(tile("license", PAD + 6, 44, 108))
    tx = PAD + 142
    o.append(f'<text x="{tx}" y="80" font-family="{FONT}" font-size="38" '
             f'font-weight="700" fill="{INK}">License</text>')
    o.append(f'<text x="{tx}" y="118" font-family="{FONT}" font-size="24" '
             f'font-weight="600" fill="{BLUE_L}">Proprietary</text>')
    o.append(f'<text x="{tx}" y="152" font-family="{FONT}" font-size="20" '
             f'fill="{VAL}">© <tspan font-weight="700" fill="{INK}">WealthWise '
             f'Advisors.</tspan> All rights reserved.</text>')
    # the call to action. The <a> that makes it work is in the README, wrapped
    # around the whole image -- an <img> carries one link and this is it.
    o.append(f'<rect x="{tx}" y="176" width="248" height="52" rx="10" '
             f'fill="{BLUE}" fill-opacity="0.07" stroke="{BLUE}" stroke-opacity="0.5"/>')
    o.append(icon("out", BLUE_L, tx + 22, 190, 0.9, sw=1.9))
    o.append(f'<text x="{tx+62}" y="209" font-family="{FONT}" font-size="21" '
             f'font-weight="600" fill="{INK}">View License</text>')
    o.append("</svg>")
    return "".join(o)


def party_card(title, subtitle, key, items, label):
    # 272: a wrapped value sets a second line under the first.
    H = 272
    o = [head(H, label)]
    o.append(tile(key, PAD + 6, 38, 92))
    tx = PAD + 126
    o.append(f'<text x="{tx}" y="78" font-family="{FONT}" font-size="34" '
             f'font-weight="700" fill="{INK}">{esc(title)}</text>')
    o.append(f'<text x="{tx}" y="112" font-family="{FONT}" font-size="20" '
             f'fill="{DIM}">{esc(subtitle)}</text>')
    o.append(f'<line x1="{PAD+6}" y1="152" x2="{W-PAD-6}" y2="152" '
             f'stroke="{EDGE}" stroke-width="1.2"/>')
    columns(o, items, PAD + 6, W - PAD - 6, 194)
    o.append("</svg>")
    return "".join(o)


def project_card():
    H = 224
    o = [head(H, "Project links: the repository, the deployed app and the "
                 "local development address")]
    o.append(tile("globe", PAD + 6, 30, 84))
    tx = PAD + 118
    o.append(f'<text x="{tx}" y="66" font-family="{FONT}" font-size="34" '
             f'font-weight="700" fill="{INK}">Project Link</text>')
    o.append(f'<text x="{tx}" y="98" font-family="{FONT}" font-size="20" '
             f'fill="{DIM}">Where the code lives, and where it runs.</text>')

    # Buttons are sized to what is in them, not cut into equal thirds. The
    # repository URL is more than twice the length of "localhost:5173", so equal
    # widths shrank it to 12px while leaving the short one half empty. The +12
    # stops a very short label collapsing to nothing but its own padding.
    x0, x1 = PAD + 6, W - PAD - 6
    gap = 14
    room = (x1 - x0) - gap * (len(PROJECT) - 1)
    weights = [len(v) + 12 for _, v, _ in PROJECT]
    total = sum(weights)
    bx = x0
    for i, (label, value, accent) in enumerate(PROJECT):
        bw = room * weights[i] / total
        o.append(f'<rect x="{bx:.1f}" y="132" width="{bw:.1f}" height="62" rx="11" '
                 f'fill="{accent}" fill-opacity="0.06" stroke="{accent}" '
                 f'stroke-opacity="0.42"/>')
        o.append(icon("out", accent, bx + 18, 145, 0.72, sw=2.0))
        o.append(f'<text x="{bx+46:.1f}" y="158" font-family="{FONT}" font-size="17" '
                 f'font-weight="600" fill="{accent}">{esc(label)}</text>')
        o.append(f'<text x="{bx+18:.1f}" y="182" font-family="{FONT}" '
                 f'font-size="{fits(value, bw-32, 18):.1f}" fill="{VAL}">'
                 f'{esc(value)}</text>')
        bx += bw + gap
    o.append("</svg>")
    return "".join(o)


CARDS = {
    "legal-license.svg": license_card,
    "legal-ownership.svg": lambda: party_card(
        "Ownership", "The organization that owns this project.", "org", OWNERSHIP,
        "Ownership: WealthWise Advisors, github.com/wealthwise-advisors"),
    "legal-developed.svg": lambda: party_card(
        "Developed By", "The developer who built this project.", "code", DEVELOPED,
        "Developed by Akash Yadav, akashyadav110502@gmail.com, github.com/akxyverse"),
    "legal-project.svg": project_card,
}


if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parents[1]
    for name, fn in CARDS.items():
        svg = fn()
        (out / name).write_text(svg, encoding="utf-8")
        print(f"wrote {out / name}  ({len(svg):,} bytes)", file=sys.stderr)
    missing = [f"{t}.{lab}" for t, items in (("ownership", OWNERSHIP),
                                             ("developed", DEVELOPED))
               for lab, val, _, _ in items if not val]
    if missing:
        print("no value in the project, column omitted: " + ", ".join(missing),
              file=sys.stderr)
