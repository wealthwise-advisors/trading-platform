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
FONT = ("ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "Roboto,Helvetica,Arial,sans-serif")

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
    "out":     ['<path d="M14 4.4h5.6V10"/>', '<path d="M19.6 4.4 11.4 12.6"/>',
                '<path d="M17.4 13.6v5.2c0 .9-.7 1.6-1.6 1.6H5.6c-.9 0-1.6-.7-1.6-1.6V8.4'
                'c0-.9.7-1.6 1.6-1.6h5.2"/>'],
    "person":  ['<circle cx="12" cy="8" r="3.6"/>',
                '<path d="M5.2 20c0-3.5 3-6.2 6.8-6.2s6.8 2.7 6.8 6.2"/>'],
    "mail":    ['<rect x="3.2" y="5.4" width="17.6" height="13.2" rx="2.2"/>',
                '<path d="m3.6 7 8.4 6 8.4-6"/>'],
    "phone":   ['<path d="M8.1 3.8 10 8l-2 1.9a12 12 0 0 0 6.1 6.1L16 14l4.2 1.9v3.2'
                'c0 .9-.8 1.6-1.7 1.5C9.7 20 4 14.3 3.4 5.5c-.1-.9.6-1.7 1.5-1.7z"/>'],
    "badge":   ['<rect x="3.6" y="3.6" width="16.8" height="16.8" rx="3.2"/>',
                '<path d="M8 10.6v6.2"/>', '<circle cx="8" cy="7.6" r="1.1"/>',
                '<path d="M12.2 16.8v-6.2M12.2 13.4c0-1.6 1.1-2.9 2.5-2.9s2.5 1.3 2.5 2.9v3.4"/>'],
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


# ── small icons for the table headings ───────────────────────────────────────
HEAD_ICONS = {
    "legal-i-owner.svg": "person",
    "legal-i-org.svg": "org",
    "legal-i-dev.svg": "person",
    "legal-i-mail.svg": "mail",
    "legal-i-phone.svg": "phone",
    # LinkedIn's own mark is deliberately NOT drawn here. It was withdrawn from
    # simple-icons at LinkedIn's request and shields.io serves that badge with
    # no glyph at all, so there is no source that may supply it -- and drawing
    # a lookalike is the exact thing the request was about. GitHub's mark IS
    # published for this use and the README links to it directly.
    "legal-i-linkedin.svg": "badge",
}


def small_icon(key):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            'width="16" height="16" role="img" aria-label="" fill="none" '
            f'stroke="{INK}" stroke-width="1.9" stroke-linecap="round" '
            f'stroke-linejoin="round">{"".join(ICONS[key])}</svg>\n')


# ── the bordered link buttons ────────────────────────────────────────────────
# A plain outlined box: one hairline border, an external-link glyph and the
# address. No gradient and no fill, so it reads the same on either GitHub
# theme, and the whole image is one <a> in the README.
BTN_H = 44
BTN_TEXT = 16.0
LINK = "#58a6ff"
BORDER = "#3b82f6"

BUTTONS = {
    "legal-btn-license.svg": "View License",
    "legal-btn-repo.svg": "github.com/wealthwise-advisors/trading-platform",
    "legal-btn-live.svg": "3-218-23-37.sslip.io",
}


def button(text):
    tw = len(text) * 0.52 * BTN_TEXT
    w = 18 + 18 + 12 + tw + 18
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {BTN_H}" '
        f'width="{w:.0f}" height="{BTN_H}" role="img" aria-label="{text}">'
        f'<rect x="0.7" y="0.7" width="{w-1.4:.1f}" height="{BTN_H-1.4}" rx="9" '
        f'fill="none" stroke="{BORDER}" stroke-opacity="0.55" stroke-width="1.4"/>'
        f'<g transform="translate(18 {(BTN_H-18)/2:.0f}) scale(0.75)" fill="none" '
        f'stroke="{LINK}" stroke-width="2.1" stroke-linecap="round" '
        f'stroke-linejoin="round">{"".join(ICONS["out"])}</g>'
        f'<text x="{18+18+12}" y="{BTN_H/2 + 5.5:.0f}" font-family="{FONT}" '
        f'font-size="{BTN_TEXT}" fill="{LINK}">{text}</text>'
        '</svg>\n'
    )


if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parents[1]
    made = 0
    for group, fn in ((FILES, heading_icon), (HEAD_ICONS, small_icon)):
        for name, key in group.items():
            (out / name).write_text(fn(key), encoding="utf-8")
            made += 1
    for name, text in BUTTONS.items():
        (out / name).write_text(button(text), encoding="utf-8")
        made += 1
    print(f"wrote {made} files to {out}", file=sys.stderr)
