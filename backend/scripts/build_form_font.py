#!/usr/bin/env python3
"""Build backend/assets/fonts/EBGaramond-Form.ttf, the font the PDF sheet's form fields use.

PDF viewers redraw a text field with the font named in its /DA once the player types into it, and
only the glyphs embedded in that font can show. A reportlab subset holds just the characters that
were on the page, so the export embeds this small Latin + Greek cut of EB Garamond whole instead.

Run once after updating EBGaramond-Regular.ttf (needs fontTools, which the backend doesn't):
    pip install fonttools && python backend/scripts/build_form_font.py
"""

import os

from fontTools import subset

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts")
SRC = os.path.join(FONTS, "EBGaramond-Regular.ttf")
OUT = os.path.join(FONTS, "EBGaramond-Form.ttf")

UNICODES = [
    *range(0x20, 0x7F),      # ASCII
    *range(0xA0, 0x180),     # Latin-1, Latin Extended-A
    *range(0x370, 0x400),    # Greek and Coptic
    *range(0x2010, 0x2027),  # dashes, quotes, bullet, ellipsis
    0x2030, 0x2039, 0x203A, 0x20AC, 0x2122,
]


def main():
    opts = subset.Options()
    opts.layout_features = []  # no shaping in form fields
    opts.hinting = False
    opts.glyph_names = True
    opts.notdef_outline = True
    opts.name_IDs = ["*"]
    opts.name_languages = ["*"]
    font = subset.load_font(SRC, opts)
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=UNICODES)
    sub.subset(font)
    font.save(OUT)
    print(f"{OUT}: {os.path.getsize(OUT)} bytes, {len(font.getGlyphOrder())} glyphs")


if __name__ == "__main__":
    main()
