"""
The horror look for the chronicle PDFs (docs/CHRONICLE.md): stained paper, a double blood-red frame
with thorned corners, blood splatters in the margins and drips at the top of the first page.

The paper is a raster image made once on a workstation and committed (backend/assets/pdf, see the
README there); there is no browser in the backend. Everything drawn on it is vector: the frame,
corners, blood (the geometry of the print PDFs' builder: blob, splatter, drips, corner) and the text.
Geometry is in millimetres from the top-left corner, as in the builder's SVG, and is turned into
points from the bottom-left here. A fixed seed per page keeps the output the same every time.
"""

from __future__ import annotations

import math
import os
import random
import threading
from typing import List, Tuple

from reportlab.lib.colors import HexColor

from services.pdf_look import _arc_points

ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "pdf")
PAPER_IMAGE = {"a4": os.path.join(ASSET_DIR, "paper-a4.jpg"), "letter": os.path.join(ASSET_DIR, "paper-letter.jpg")}

BLOOD = HexColor("#6a0a0a")
BLOOD_D = HexColor("#3a0505")
BLOOD_L = HexColor("#860d0d")
INK = HexColor("#1c1109")
INK_SOFT = HexColor("#3b2615")

MM = 72.0 / 25.4
FRAME_MM = 6.5  # the frame's distance from the paper's edge


class _Page:
    """mm (from the top-left) to points (from the bottom-left)."""

    def __init__(self, c, H):
        self.c, self.H = c, H

    def pt(self, x, y):
        return x * MM, self.H - y * MM


def _quad(p, page, p0, ctrl, end):
    """A quadratic curve from p0 as a cubic (reportlab paths have no quadratic)."""
    c1 = (p0[0] + 2 / 3 * (ctrl[0] - p0[0]), p0[1] + 2 / 3 * (ctrl[1] - p0[1]))
    c2 = (end[0] + 2 / 3 * (ctrl[0] - end[0]), end[1] + 2 / 3 * (ctrl[1] - end[1]))
    p.curveTo(*page.pt(*c1), *page.pt(*c2), *page.pt(*end))


def _poly(page, pts: List[Tuple[float, float]], fill, alpha=1.0):
    c = page.c
    p = c.beginPath()
    p.moveTo(*page.pt(*pts[0]))
    for q in pts[1:]:
        p.lineTo(*page.pt(*q))
    p.close()
    c.setFillColor(fill)
    c.setFillAlpha(alpha)
    c.drawPath(p, stroke=0, fill=1)


def blob(page, cx, cy, r, rnd, alpha, pts=22, jag=0.35):
    """A jagged round stain: points on a wobbly circle joined by quadratic curves through the midpoints."""
    d = []
    for k in range(pts):
        a = 2 * math.pi * k / pts
        rr = r * (1 + rnd.uniform(-jag, jag) * (0.6 if k % 2 else 1))
        d.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    c = page.c
    p = c.beginPath()
    p.moveTo(*page.pt(*d[0]))
    cur = d[0]
    for i in range(len(d)):
        p1, p2 = d[i], d[(i + 1) % len(d)]
        mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        _quad(p, page, cur, p1, mid)
        cur = mid
    p.close()
    c.setFillColor(BLOOD)
    c.setFillAlpha(alpha)
    c.drawPath(p, stroke=0, fill=1)
    # the builder's radial gradient, as a darker rim and a lighter heart
    c.setFillColor(BLOOD_L)
    c.setFillAlpha(alpha * 0.55)
    x, y = page.pt(cx - r * 0.15, cy - r * 0.15)
    c.circle(x, y, r * 0.45 * MM, stroke=0, fill=1)


def splatter(page, cx, cy, r, rnd, alpha=0.82):
    """A stain with droplets thrown outwards, some with a streak towards them."""
    c = page.c
    blob(page, cx, cy, r, rnd, alpha)
    c.setFillColor(BLOOD)
    c.setStrokeColor(BLOOD)
    c.setLineCap(1)
    for _ in range(rnd.randint(14, 26)):
        a = rnd.uniform(0, 2 * math.pi)
        dist = r * rnd.uniform(1.2, 3.6)
        dr = max(0.18, r * rnd.uniform(0.04, 0.22) * (1.6 - dist / (r * 3.6)))
        x, y = cx + dist * math.cos(a), cy + dist * math.sin(a)
        c.setFillAlpha(alpha)
        c.circle(*page.pt(x, y), dr * MM, stroke=0, fill=1)
        if rnd.random() < 0.35:
            x2, y2 = cx + (dist - dr * 4) * math.cos(a), cy + (dist - dr * 4) * math.sin(a)
            c.setStrokeAlpha(alpha * 0.9)
            c.setLineWidth(dr * 0.9 * MM)
            c.line(*page.pt(x2, y2), *page.pt(x, y))


def drips(page, w, rnd, n=9, maxlen=22.0):
    """Blood running down from the top edge."""
    c = page.c
    c.setFillColor(BLOOD)
    c.setFillAlpha(1)
    p = c.beginPath()
    p.moveTo(*page.pt(0, 0))
    p.lineTo(*page.pt(w, 0))
    p.lineTo(*page.pt(w, 2.2))
    _quad(p, page, (w, 2.2), (w * 0.5, 4.2), (0, 2.2))
    p.close()
    c.drawPath(p, stroke=0, fill=1)
    for _ in range(n):
        x = rnd.uniform(4, w - 4)
        L = rnd.uniform(6, maxlen)
        wd = rnd.uniform(0.9, 2.4)
        p = c.beginPath()
        p.moveTo(*page.pt(x - wd, 0))
        p.curveTo(*page.pt(x - wd * 0.7, L * 0.5), *page.pt(x - wd * 0.45, L * 0.8), *page.pt(x - wd * 0.55, L))
        # the round drop at the end (the builder's arc: large, counter-clockwise)
        for q in _arc_points(x - wd * 0.55, L, wd * 0.95, wd * 0.95, 1, 0, x + wd * 0.55, L):
            p.lineTo(*page.pt(*q))
        p.curveTo(*page.pt(x + wd * 0.45, L * 0.8), *page.pt(x + wd * 0.7, L * 0.5), *page.pt(x + wd, 0))
        p.close()
        c.setFillColor(BLOOD_D if L > maxlen * 0.8 else BLOOD)
        c.drawPath(p, stroke=0, fill=1)


def corner(page, x, y, sx, sy):
    """The thorned corner (builder's corner()), at (x, y) mm, mirrored by sx, sy."""
    c = page.c

    def t(lx, ly):
        return x + sx * lx, y + sy * ly

    def stroke(points, width):
        p = c.beginPath()
        p.moveTo(*page.pt(*t(*points[0])))
        for q in points[1:]:
            p.lineTo(*page.pt(*t(*q)))
        c.setLineWidth(width * MM)
        c.drawPath(p, stroke=1, fill=0)

    c.setStrokeColor(BLOOD_D)
    c.setStrokeAlpha(1)
    stroke([(0, 16), (0, 0), (16, 0)], 0.35)
    stroke([(2.2, 13), (2.2, 2.2), (13, 2.2)], 0.2)
    stroke([(0, 0), (6, 6)], 0.3)
    _poly(page, [t(*q) for q in ((6, 6), (7.4, 3.8), (8.2, 6), (10.4, 6.8), (8.2, 7.6), (7.4, 9.8), (6.6, 7.6),
                                 (4.4, 6.8))], BLOOD)
    c.setLineWidth(0.3 * MM)
    for p0, ctrl, end in (((16, 0), (19, 1.6), (17.2, 3.4)), ((0, 16), (1.6, 19), (3.4, 17.2))):
        p = c.beginPath()
        p.moveTo(*page.pt(*t(*p0)))
        _quad(p, page, t(*p0), t(*ctrl), t(*end))
        c.drawPath(p, stroke=1, fill=0)
    for a in (5, 10):
        _poly(page, [t(a, 0), t(a + 0.6, -1.4), t(a + 1.2, 0)], BLOOD_D)
        _poly(page, [t(0, a), t(-1.4, a + 0.6), t(0, a + 1.2)], BLOOD_D)


_PAPER_DATA = {}
_PAPER_LOCK = threading.Lock()


def _paper_jpeg(paper: str):
    """(bytes, width, height, colour space) of a paper JPEG, read once per paper size and kept."""
    with _PAPER_LOCK:
        got = _PAPER_DATA.get(paper)
        if got is None:
            from reportlab.pdfbase import pdfutils

            with open(PAPER_IMAGE[paper], "rb") as fh:
                info = pdfutils.readJPEGInfo(fh)
                fh.seek(0)
                data = fh.read()
            got = (data, info[0], info[1], "DeviceRGB" if info[2] == 3 else "DeviceGray")
            _PAPER_DATA[paper] = got
        return got


def _draw_paper(c, paper: str, W: float, H: float) -> None:
    """Draw the paper over the whole page. The JPEG's bytes go into the PDF unchanged, once per file
    (DCTDecode only; reportlab's own loader would ASCII85-encode them, +25%)."""
    from reportlab.pdfbase import pdfdoc

    paper = paper if paper in PAPER_IMAGE else "a4"
    name = f"srpaper{paper}"
    reg = c._doc.getXObjectName(name)
    if reg not in c._doc.idToObject:
        data, w, h, cs = _paper_jpeg(paper)
        obj = pdfdoc.PDFImageXObject(name)
        obj.width, obj.height, obj.bitsPerComponent, obj.colorSpace = w, h, 8, cs
        obj.streamContent, obj._filters, obj.mask = data, ("DCTDecode",), None
        c._setXObjects(obj)
        c._doc.Reference(obj, reg)
        c._doc.addForm(name, obj)
    c._currentPageHasImages = 1
    c._formsinuse.append(name)  # the page lists it in its resources
    c.saveState()
    c.scale(W, H)
    c._code.append(f"/{reg} Do")
    c.restoreState()


def draw_page(c, W: float, H: float, paper: str, page_no: int) -> None:
    """Paper, frame, corners and blood for one page (page_no from 1). Text goes on top afterwards."""
    w, h = W / MM, H / MM
    page = _Page(c, H)
    c.saveState()
    _draw_paper(c, paper, W, H)
    m = FRAME_MM
    c.setStrokeColor(BLOOD_D)
    c.setLineWidth(0.5 * MM)
    c.rect(m * MM, m * MM, W - 2 * m * MM, H - 2 * m * MM, stroke=1, fill=0)
    c.setLineWidth(0.18 * MM)
    g = m + 1.3
    c.rect(g * MM, g * MM, W - 2 * g * MM, H - 2 * g * MM, stroke=1, fill=0)
    for (x, y, sx, sy) in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
        corner(page, x, y, sx, sy)
    rnd = random.Random(26 + page_no)
    if page_no == 1:
        splatter(page, w - 12, h - 46, 2.6, rnd, 0.85)
        splatter(page, 12, h - 34, 1.4, rnd, 0.6)
        drips(page, w, rnd)
    elif page_no % 2:
        splatter(page, 11, h - 30 - 40 * (page_no % 3), 2.0, rnd, 0.7)
    else:
        splatter(page, w - 10, 30 + 40 * (page_no % 3), 2.0, rnd, 0.7)
    c.restoreState()
