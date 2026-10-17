"""
The look shared by the character sheet PDF and the chronicle PDF (docs/CHRONICLE.md): black ink on
white, the double frame with diamond corners, the line-art sigil, the section rule (a Cinzel
heading between hairlines ending in diamonds), the italic footer, and the fonts.

Fonts (backend/assets/fonts, SIL OFL 1.1, licence files next to them):
- Cinzel for headings and labels. Caps only and no Greek, so it never shows user text.
- EB Garamond for everything people wrote, Greek included.
"""

from __future__ import annotations

import math
import os
import re
import threading
from typing import Optional

from reportlab.lib.pagesizes import A4, LETTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")

CINZEL = "SR-Cinzel"
CINZEL_BOLD = "SR-Cinzel-Bold"
SERIF = "SR-Garamond"
SERIF_ITALIC = "SR-Garamond-Italic"
_FONT_FILES = {
    CINZEL: "Cinzel-Regular.ttf",
    CINZEL_BOLD: "Cinzel-Bold.ttf",
    SERIF: "EBGaramond-Regular.ttf",
    SERIF_ITALIC: "EBGaramond-Italic.ttf",
}

PAPER = {"a4": A4, "letter": LETTER}

_fonts_lock = threading.Lock()
_fonts_ready = False


def ensure_fonts() -> None:
    global _fonts_ready
    if _fonts_ready:
        return
    with _fonts_lock:
        if _fonts_ready:
            return
        for name, fn in _FONT_FILES.items():
            pdfmetrics.registerFont(TTFont(name, os.path.join(FONT_DIR, fn)))
        _fonts_ready = True


# ---------------------------------------------------------------------------------------------
# Sigil (assets/logos/shadowrealms-sigil.svg, our own art) as line art.

_SIGIL_PATHS = [
    # (path data, stroke width in sigil units, filled)
    ("M0,-47L10.741,-40.086L23.5,-40.703L29.345,-29.345L40.703,-23.5L40.086,-10.741L47,0L40.086,10.741"
     "L40.703,23.5L29.345,29.345L23.5,40.703L10.741,40.086L0,47L-10.741,40.086L-23.5,40.703"
     "L-29.345,29.345L-40.703,23.5L-40.086,10.741L-47,0L-40.086,-10.741L-40.703,-23.5"
     "L-29.345,-29.345L-23.5,-40.703L-10.741,-40.086Z", 1.6, False),
    ("CIRCLE 36", 0.8, False),
    ("M11.48 -27.72L12.82 -30.95M27.72 -11.48L30.95 -12.82M27.72 11.48L30.95 12.82M11.48 27.72"
     "L12.82 30.95M-11.48 27.72L-12.82 30.95M-27.72 11.48L-30.95 12.82M-27.72 -11.48L-30.95 -12.82"
     "M-11.48 -27.72L-12.82 -30.95", 1.4, False),
    ("M-24 -14 L24 -14 L0 28 Z", 1.8, False),
    ("M6 -33 A9 9 0 1 0 6 -17 A7.2 7.2 0 0 1 6 -33 Z", 1.2, False),
    ("M0 -12 C3.6 -7.4 6.2 -3.6 6.2 0.6 A6.2 6.2 0 0 1 -6.2 0.6 C-6.2 -3.6 -3.6 -7.4 0 -12 Z", 0.8, True),
]


def _arc_points(x1, y1, rx, ry, large, sweep, x2, y2, steps=24):
    """SVG elliptical arc (no rotation) as points, per the SVG implementation notes."""
    dx, dy = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    lam = (dx * dx) / (rx * rx) + (dy * dy) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx * rx * ry * ry - rx * rx * dy * dy - ry * ry * dx * dx
    den = rx * rx * dy * dy + ry * ry * dx * dx
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        co = -co
    cxp, cyp = co * rx * dy / ry, -co * ry * dx / rx
    cx, cy = cxp + (x1 + x2) / 2.0, cyp + (y1 + y2) / 2.0
    a1 = math.atan2((dy - cyp) / ry, (dx - cxp) / rx)
    a2 = math.atan2((-dy - cyp) / ry, (-dx - cxp) / rx)
    da = a2 - a1
    if sweep and da < 0:
        da += 2 * math.pi
    elif not sweep and da > 0:
        da -= 2 * math.pi
    return [(cx + rx * math.cos(a1 + da * i / steps), cy + ry * math.sin(a1 + da * i / steps))
            for i in range(1, steps + 1)]


def _draw_svg_path(p, d: str, tf) -> None:
    toks = re.findall(r"[MLCAZ]|-?\d*\.?\d+(?:e-?\d+)?", d)
    i, cmd, cur, start = 0, None, (0.0, 0.0), (0.0, 0.0)

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v

    while i < len(toks):
        if toks[i] in "MLCAZ":
            cmd = toks[i]
            i += 1
            if cmd == "Z":
                p.close()
                cur = start
                continue
        if cmd == "M":
            cur = start = (num(), num())
            p.moveTo(*tf(*cur))
            cmd = "L"
        elif cmd == "L":
            cur = (num(), num())
            p.lineTo(*tf(*cur))
        elif cmd == "C":
            pts = [(num(), num()) for _ in range(3)]
            p.curveTo(*tf(*pts[0]), *tf(*pts[1]), *tf(*pts[2]))
            cur = pts[2]
        elif cmd == "A":
            rx, ry, _rot, large, sweep, x, y = (num() for _ in range(7))
            for pt in _arc_points(cur[0], cur[1], rx, ry, int(large), int(sweep), x, y):
                p.lineTo(*tf(*pt))
            cur = (x, y)


def draw_sigil(c, cx: float, cy: float, size: float) -> None:
    k = size / 100.0

    def tf(x, y):
        return cx + x * k, cy - y * k  # SVG y grows downwards

    c.saveState()
    c.setStrokeGray(0)
    c.setFillGray(0)
    c.setLineCap(1)
    c.setLineJoin(1)
    for d, width, filled in _SIGIL_PATHS:
        c.setLineWidth(max(0.3, width * k))
        if d.startswith("CIRCLE"):
            c.circle(cx, cy, float(d.split()[1]) * k, stroke=1, fill=0)
            continue
        p = c.beginPath()
        _draw_svg_path(p, d, tf)
        c.drawPath(p, stroke=1, fill=1 if filled else 0)
    c.restoreState()


HAIR = 0.45
RULE = 0.8


def _ellipsize(text: str, font: str, size: float, width: float) -> str:
    """Cut text to fit width on one line, ending in '…' when cut."""
    if pdfmetrics.stringWidth(text, font, size) <= width:
        return text
    lo, hi = 0, min(len(text), 400)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if pdfmetrics.stringWidth(text[:mid].rstrip() + "…", font, size) <= width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + "…"


def draw_diamond(c, x, y, r, fill=True):
    p = c.beginPath()
    p.moveTo(x, y + r)
    p.lineTo(x + r, y)
    p.lineTo(x, y - r)
    p.lineTo(x - r, y)
    p.close()
    c.drawPath(p, stroke=1, fill=1 if fill else 0)


def draw_frame(c, W: float, H: float, M: float) -> None:
    """The double frame with a diamond and a quarter circle in each corner, M from the paper's edge."""
    c.saveState()
    c.setLineWidth(RULE)
    c.rect(M, M, W - 2 * M, H - 2 * M)
    c.setLineWidth(HAIR)
    g = 3.0
    c.rect(M + g, M + g, W - 2 * (M + g), H - 2 * (M + g))
    for (cx, cy, sx, sy) in ((M, M, 1, 1), (W - M, M, -1, 1), (M, H - M, 1, -1), (W - M, H - M, -1, -1)):
        c.setLineWidth(HAIR)
        c.setFillGray(1)
        c.rect(cx + sx * 0 - (14 if sx < 0 else 0), cy - (14 if sy < 0 else 0), 14, 14, stroke=1, fill=1)
        c.setFillGray(0)
        draw_diamond(c, cx + sx * 7, cy + sy * 7, 3.6, fill=True)
        p = c.beginPath()
        p.arc(cx + sx * 7 - 11, cy + sy * 7 - 11, cx + sx * 7 + 11, cy + sy * 7 + 11,
              startAng={(1, 1): 0, (-1, 1): 90, (-1, -1): 180, (1, -1): 270}[(sx, sy)], extent=90)
        c.drawPath(p, stroke=1, fill=0)
    c.restoreState()


def _hline(c, x0, x1, y, w=HAIR):
    c.saveState()
    c.setLineWidth(w)
    c.line(x0, y, x1, y)
    c.restoreState()


def canvas_text(c):
    """A text(x, y, s, font, size, align) drawing straight on canvas c (the sheet passes its own)."""
    def text(x, y, s, font=SERIF, size=9, align="left"):
        c.setFont(font, size)
        if align == "center":
            c.drawCentredString(x, y, s)
        elif align == "right":
            c.drawRightString(x, y, s)
        else:
            c.drawString(x, y, s)
    return text


def draw_section(c, title: str, y: float, x0: float, x1: float, size: float = 9.0, text=None,
                 font: str = CINZEL_BOLD) -> float:
    """Centered heading (Cinzel caps) between hairlines ending in diamonds; returns the y below it."""
    text = text or canvas_text(c)
    mid = (x0 + x1) / 2
    s = _ellipsize(title.upper(), font, size, max(20.0, x1 - x0 - 40))  # a long heading stays inside the rule
    tw = pdfmetrics.stringWidth(s, font, size)
    base = y - 9
    text(mid, base, s, font, size, "center")
    ly = base + 3
    _hline(c, x0 + 4, mid - tw / 2 - 10, ly)
    _hline(c, mid + tw / 2 + 10, x1 - 4, ly)
    draw_diamond(c, x0 + 2, ly, 1.8)
    draw_diamond(c, x1 - 2, ly, 1.8)
    draw_diamond(c, mid - tw / 2 - 6, ly, 1.3, fill=False)
    draw_diamond(c, mid + tw / 2 + 6, ly, 1.3, fill=False)
    return y - 15


def draw_footer(c, W: float, M: float, x1: float, left: str, page: int, pages: Optional[int],
                link: Optional[str] = None, text=None) -> None:
    """The italic footer line, centred, and 'page / pages' at the right; with `link`, the line is a link."""
    text = text or canvas_text(c)
    y = M + 9
    room = 2 * (x1 - 8 - 30 - W / 2)  # centred, clear of the page number
    line = _ellipsize(" ".join(left.split()), SERIF_ITALIC, 7.5, room)
    text(W / 2, y, line, SERIF_ITALIC, 7.5, "center")
    if link:
        tw = pdfmetrics.stringWidth(line, SERIF_ITALIC, 7.5)
        c.linkURL(link, (W / 2 - tw / 2, y - 2, W / 2 + tw / 2, y + 7.5), relative=0)
    text(x1 - 8, y, f"{page} / {pages}" if pages else str(page), SERIF_ITALIC, 7.5, "right")
