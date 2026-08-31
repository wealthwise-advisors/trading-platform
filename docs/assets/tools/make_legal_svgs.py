"""
Generate the four heading icons for the Licence / Ownership / Developed By /
Project Link section of the README.

    legal-license.svg    a document with a shield
    legal-ownership.svg  an office building
    legal-developed.svg  a code bracket
    legal-project.svg    a globe

WHY THIS FILE DRAWS ICONS AND NOTHING ELSE
------------------------------------------
It used to draw the whole section as four cards -- rounded panels, gradient
borders, raised icon tiles, and the values laid out inside the picture. That
was wrong twice over.

Wrong for the design, because the section is meant to be WRITTEN, not drawn: a
heading, a line of text, and columns separated by hairlines, with no panel
around any of it.

Wrong for the content, because an address drawn into an image cannot be
clicked, copied, searched or translated, and an <img> carries at most one link
no matter how many addresses are in it. Repeating them as text underneath to
compensate only printed everything twice.

So the section is markdown now: real headings, real text, a real table whose
rules ARE the dividers the design asks for, and real links. The one thing
markdown cannot supply is a line-art icon beside each heading, which is exactly
and only what this file makes.

WHITE, NOT ACCENTED
-------------------
Drawn in the foreground grey so each icon sits with the heading beside it
rather than competing with it. The blue in this section belongs to the links,
which GitHub colours itself.

`currentColor` would be better still -- the icon would follow the reader's
theme -- but GitHub serves README images through its camo proxy as standalone
files, where there is no inherited colour to follow.

NO BRAND MARKS
--------------
The reference has GitHub's and LinkedIn's logos in it. They are not reproduced,
for the reason components/SymbolMark.tsx gives for not fetching logos:
redistributing another company's trademarked artwork inside a commercial
product is a different thing from linking to them.
"""

import pathlib
import sys

INK = "#c9d1d9"

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
}


def heading_icon(key):
    """One 26x26 line-art icon, transparent behind, to sit beside a heading."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            'width="26" height="26" role="img" aria-label="" fill="none" '
            f'stroke="{INK}" stroke-width="1.7" stroke-linecap="round" '
            f'stroke-linejoin="round">{"".join(ICONS[key])}</svg>\n')


FILES = {
    "legal-license.svg": "license",
    "legal-ownership.svg": "org",
    "legal-developed.svg": "code",
    "legal-project.svg": "globe",
}


if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parents[1]
    for name, key in FILES.items():
        svg = heading_icon(key)
        (out / name).write_text(svg, encoding="utf-8")
        print(f"wrote {out / name}  ({len(svg)} bytes)", file=sys.stderr)
