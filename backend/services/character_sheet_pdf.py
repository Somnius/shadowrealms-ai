"""
Character sheet as a fillable PDF (GET /api/characters/<id>/sheet.pdf).

Black ink on white only, so it prints clean on a mono laser printer: hairlines, line-art sigil,
no grey fills. Every value is an AcroForm field pre-filled from the saved sheet: text fields for
names and notes, one checkbox per dot or box so players can fill and clear them.

Fonts (backend/assets/fonts, SIL OFL 1.1, licence files next to them):
- Cinzel for headings and labels. Caps only and no Greek, so it never shows user text.
- EB Garamond for everything the player wrote, Greek included.

Form fields and Greek: reportlab's AcroForm helpers only know the 14 standard PDF fonts (no Greek),
so the widgets are written here by hand:
- each field's appearance (/AP) is a form XObject drawn with the embedded EB Garamond, so the
  pre-filled values show correctly in every viewer without regenerating anything;
- the field's /DA font, which a viewer uses to redraw the field after the player edits it, is a
  Latin + Greek cut of EB Garamond (EBGaramond-Form.ttf, see scripts/build_form_font.py) embedded
  whole as a simple TrueType font, with an encoding that names its Greek glyphs.
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import threading
from typing import Any, Dict, List, Optional, Sequence, Tuple

from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfdoc, pdfmetrics
from reportlab.pdfbase._glyphlist import _glyphname2unicode
from reportlab.pdfbase.acroform import PDFFromString
from reportlab.pdfbase.ttfonts import TTFont, TTFontFile
from reportlab.pdfgen import canvas as rl_canvas

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
FORM_FONT_FILE = "EBGaramond-Form.ttf"
FORM_FONT_KEY = "SRG"  # resource name in the AcroForm /DR

PAPER = {"a4": A4, "letter": LETTER}

_fonts_lock = threading.Lock()
_fonts_ready = False
_form_face: Optional[TTFontFile] = None
_form_font_bytes = b""


def _ensure_fonts() -> None:
    global _fonts_ready, _form_face, _form_font_bytes
    if _fonts_ready:
        return
    with _fonts_lock:
        if _fonts_ready:
            return
        for name, fn in _FONT_FILES.items():
            pdfmetrics.registerFont(TTFont(name, os.path.join(FONT_DIR, fn)))
        path = os.path.join(FONT_DIR, FORM_FONT_FILE)
        with open(path, "rb") as f:
            _form_font_bytes = f.read()
        _form_face = TTFontFile(path)
        _fonts_ready = True


# ---------------------------------------------------------------------------------------------
# Form font encoding: WinAnsi, with Greek moved into codes whose WinAnsi characters are rare
# (unused codes, typographic odds and ends, Icelandic letters). Kept characters stay at their WinAnsi
# codes, so a viewer that encodes typed text through the base encoding still picks the right glyph.

_GREEK = (
    [c for c in range(0x391, 0x3AA) if c != 0x3A2]  # Α-Ω
    + list(range(0x3B1, 0x3CA))                      # α-ω (incl. ς)
    + [0x386, 0x388, 0x389, 0x38A, 0x38C, 0x38E, 0x38F,  # Ά Έ Ή Ί Ό Ύ Ώ
       0x3AC, 0x3AD, 0x3AE, 0x3AF, 0x3CC, 0x3CD, 0x3CE,  # ά έ ή ί ό ύ ώ
       0x3CA, 0x3CB, 0x390, 0x3B0, 0x3AA, 0x3AB, 0x387]  # ϊ ϋ ΐ ΰ Ϊ Ϋ ·
)
_KEEP_HIGH = set("€…‘’“”•–—œŒ\xa0£«°·»") | set("ÀÁÂÄÇÈÉÊËÍÎÏÑÓÔÖØÚÜßàáâäçèéêëíîïñóôöøúü")


def _winansi(b: int) -> Optional[str]:
    try:
        ch = bytes([b]).decode("cp1252")
    except UnicodeDecodeError:
        return None
    return None if b == 0x7F else ch


def _build_encoding() -> Tuple[Dict[int, int], Dict[int, int]]:
    """(byte -> unicode for 32..255, the bytes that differ from WinAnsi -> unicode)."""
    table: Dict[int, int] = {}
    free = []
    for b in range(32, 256):
        ch = _winansi(b)
        if b < 127 or (ch is not None and ch in _KEEP_HIGH):
            table[b] = ord(ch)
        else:
            free.append(b)
    assert len(free) >= len(_GREEK), "form font encoding has no room for Greek"
    diffs = dict(zip(free, _GREEK))
    table.update(diffs)
    return table, diffs


_BYTE_TO_UNI, _DIFFS = _build_encoding()
FORM_CODES: Dict[int, int] = {u: b for b, u in _BYTE_TO_UNI.items()}  # unicode -> byte

_AGL = {}
for _name, _uni in _glyphname2unicode.items():
    if "." not in _name and not _name.startswith("uni") and _uni not in _AGL:
        _AGL[_uni] = _name


def _glyph_name(cp: int) -> str:
    # Greek gets uniXXXX names: some AGL names (Delta, Omega, mu) also mean math symbols.
    if 0x370 <= cp < 0x400 or cp not in _AGL:
        return "uni%04X" % cp
    return _AGL[cp]


def _to_unicode_cmap() -> str:
    pairs = sorted(_BYTE_TO_UNI.items())
    out = ["/CIDInit /ProcSet findresource begin", "12 dict begin", "begincmap",
           "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
           "/CMapName /SRG-UCS def", "/CMapType 2 def",
           "1 begincodespacerange", "<00> <FF>", "endcodespacerange"]
    for i in range(0, len(pairs), 100):
        chunk = pairs[i:i + 100]
        out.append("%d beginbfchar" % len(chunk))
        out.extend("<%02X> <%04X>" % (b, u) for b, u in chunk)
        out.append("endbfchar")
    out += ["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"]
    return "\n".join(out)


def _add_form_font(doc) -> str:
    """Embed the form font once per document; returns its reference string for /DR."""
    face = _form_face
    ff = pdfdoc.PDFStream(content=_form_font_bytes)
    ff.dictionary["Length1"] = len(_form_font_bytes)
    ff.filters = [pdfdoc.PDFZCompress]
    ff_ref = doc.Reference(ff, "SRFormFontFile")
    base = face.name.decode("latin-1") if isinstance(face.name, bytes) else str(face.name)
    descriptor = pdfdoc.PDFDictionary({
        "Type": pdfdoc.PDFName("FontDescriptor"),
        "FontName": pdfdoc.PDFName(base),
        "Flags": 32 | 2,  # nonsymbolic, serif
        "FontBBox": pdfdoc.PDFArray(face.bbox),
        "ItalicAngle": face.italicAngle,
        "Ascent": face.ascent,
        "Descent": face.descent,
        "CapHeight": face.capHeight,
        "StemV": face.stemV,
        "FontFile2": ff_ref,
    })
    tu = pdfdoc.PDFStream(content=_to_unicode_cmap())
    tu.filters = [pdfdoc.PDFZCompress]
    widths = [face.charWidths.get(_BYTE_TO_UNI.get(b, 0x20), face.defaultWidth) for b in range(32, 256)]
    diffs: List[Any] = []
    prev = None
    for code in sorted(_DIFFS):
        if prev is None or code != prev + 1:
            diffs.append(code)
        diffs.append(pdfdoc.PDFName(_glyph_name(_DIFFS[code])))
        prev = code
    font = pdfdoc.PDFDictionary({
        "Type": pdfdoc.PDFName("Font"),
        "Subtype": pdfdoc.PDFName("TrueType"),
        "BaseFont": pdfdoc.PDFName(base),
        "FirstChar": 32,
        "LastChar": 255,
        "Widths": pdfdoc.PDFArray(widths),
        "Encoding": pdfdoc.PDFDictionary({
            "Type": pdfdoc.PDFName("Encoding"),
            "BaseEncoding": pdfdoc.PDFName("WinAnsiEncoding"),
            "Differences": pdfdoc.PDFArray(diffs),
        }),
        "FontDescriptor": doc.Reference(descriptor, "SRFormFontDescriptor"),
        "ToUnicode": doc.Reference(tu, "SRFormFontToUnicode"),
    })
    ref = doc.Reference(font, "SRFormFont")
    return ref.format(doc).decode("latin-1")


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


# ---------------------------------------------------------------------------------------------
# Values


MAX_TEXT = 20000   # characters printed in a multiline field
MAX_LINE = 500     # characters printed in a one-line field
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_SURROGATE = re.compile(r"[\ud800-\udfff]")


def _clean(text: str) -> str:
    """Printable text: newlines kept, tabs as spaces, other C0 controls dropped, lone surrogates as U+FFFD."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    return _CONTROL.sub("", _SURROGATE.sub("\ufffd", text))


def _cap(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return ", ".join(x for x in (_s(x) for x in v[:500]) if x)
    if isinstance(v, dict):
        return _s(v.get("name"))
    return _clean(str(v)).strip()


def _n(v: Any, lo: int = 0, hi: int = 10) -> int:
    """Whole number clamped to lo..hi; anything unreadable (text, NaN, inf, 1e400) gives lo."""
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError):
        return lo
    if not math.isfinite(x):
        return lo
    return max(lo, min(hi, int(x)))


def _obj(v: Any) -> Dict[str, Any]:
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except (ValueError, TypeError):
            return {}
    return v if isinstance(v, dict) else {}


def _list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _label(key: str) -> str:
    return key.replace("_", " ").title()


# ---------------------------------------------------------------------------------------------
# Drawing + form widgets

MIN_TEXT = 5.5  # smallest size long text shrinks to


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


def _fit_lines(text: str, width: float, height: float, size: float) -> Tuple[float, List[str]]:
    """Largest size (down to MIN_TEXT) at which the wrapped text fits, and its lines.

    The size is estimated from each paragraph's width (one measurement per paragraph, no
    wrapping), then the text is wrapped once at that size, and once more a step smaller if
    word breaks made it a line too long.
    """
    paras = text.split("\n")
    unit = [pdfmetrics.stringWidth(p, SERIF, 1.0) for p in paras]

    def fits(s: float, n_lines: int) -> bool:
        return (n_lines - 1) * s * 1.17 + s * 1.1 <= height

    def estimate(s: float) -> int:
        return sum(max(1, math.ceil(u * s / (width * 0.94))) for u in unit)

    s = size
    while s > MIN_TEXT and not fits(s, estimate(s)):
        s -= 0.25
    s = max(MIN_TEXT, s)

    def wrap(s: float) -> List[str]:
        lines: List[str] = []
        max_lines = int(height / (s * 1.17)) + 2  # nothing past the box is drawn
        for p in paras:
            lines.extend(simpleSplit(p, SERIF, s, width) or [""])
            if len(lines) > max_lines:
                break
        return lines

    lines = wrap(s)
    if not fits(s, len(lines)) and s > MIN_TEXT:
        s = max(MIN_TEXT, s - 0.5)
        lines = wrap(s)
    return s, lines

HAIR = 0.45
RULE = 0.8


class SheetCanvas:
    """reportlab canvas plus black-and-white form helpers."""

    def __init__(self, paper: str = "a4", title: str = "", author: str = ""):
        _ensure_fonts()
        self.buf = io.BytesIO()
        self.W, self.H = PAPER.get(paper, A4)
        c = rl_canvas.Canvas(self.buf, pagesize=(self.W, self.H), pageCompression=1)
        c.setTitle(title)
        c.setAuthor(author)
        c.setSubject("Character sheet")
        c.setCreator("ShadowRealms AI")
        self.c = c
        self.M = 24.0
        self.x0 = self.M + 18
        self.x1 = self.W - self.M - 18
        self.top = self.H - self.M - 14
        self.bottom = self.M + 22
        self._names: Dict[str, int] = {}
        self._ap = 0
        self._cb_refs: Dict[Tuple[str, float, str], Any] = {}
        form = c.acroForm  # registers /AcroForm in the catalog
        form.fonts[FORM_FONT_KEY] = _add_form_font(c._doc)
        # reportlab writes one /Font key per font into /DR; with two fonts, write /DR here instead.
        # /ZaDb is for viewers that redraw the checkboxes' /MK marks themselves.
        zadb = form.getRefStr(PDFFromString("<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats /Name /ZaDb >>"))
        form.extras["DR"] = PDFFromString(
            f"<< /Font << /{FORM_FONT_KEY} {form.fonts[FORM_FONT_KEY]} /ZaDb {zadb} >> >>")
        self.form = form
        self._ink()

    # -- basics ------------------------------------------------------------------------------
    def _ink(self):
        self.c.setFillGray(0)
        self.c.setStrokeGray(0)

    def unique(self, name: str) -> str:
        base = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "field"
        k = self._names.get(base, 0)
        self._names[base] = k + 1
        return base if k == 0 else f"{base}_{k + 1}"

    def text(self, x, y, s, font=SERIF, size=9, align="left"):
        c = self.c
        c.setFont(font, size)
        if align == "center":
            c.drawCentredString(x, y, s)
        elif align == "right":
            c.drawRightString(x, y, s)
        else:
            c.drawString(x, y, s)

    def label(self, x, y, s, size=7.0, align="left", bold=False):
        self.text(x, y, s.upper(), CINZEL_BOLD if bold else CINZEL, size, align)

    def hline(self, x0, x1, y, w=HAIR, dash=None):
        c = self.c
        c.saveState()
        c.setLineWidth(w)
        if dash:
            c.setDash(*dash)
        c.line(x0, y, x1, y)
        c.restoreState()

    def rect(self, x, y, w, h, lw=HAIR, dash=None):
        c = self.c
        c.saveState()
        c.setLineWidth(lw)
        if dash:
            c.setDash(*dash)
        c.rect(x, y, w, h, stroke=1, fill=0)
        c.restoreState()

    def diamond(self, x, y, r, fill=True):
        p = self.c.beginPath()
        p.moveTo(x, y + r)
        p.lineTo(x + r, y)
        p.lineTo(x, y - r)
        p.lineTo(x - r, y)
        p.close()
        self.c.drawPath(p, stroke=1, fill=1 if fill else 0)

    # -- ornament ----------------------------------------------------------------------------
    def frame(self):
        c, M, W, H = self.c, self.M, self.W, self.H
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
            self.diamond(cx + sx * 7, cy + sy * 7, 3.6, fill=True)
            p = c.beginPath()
            p.arc(cx + sx * 7 - 11, cy + sy * 7 - 11, cx + sx * 7 + 11, cy + sy * 7 + 11,
                  startAng={(1, 1): 0, (-1, 1): 90, (-1, -1): 180, (1, -1): 270}[(sx, sy)], extent=90)
            c.drawPath(p, stroke=1, fill=0)
        c.restoreState()

    def section(self, title: str, y: float, x0: Optional[float] = None, x1: Optional[float] = None) -> float:
        """Centered Cinzel heading between hairlines ending in diamonds; returns the y below it."""
        x0 = self.x0 if x0 is None else x0
        x1 = self.x1 if x1 is None else x1
        mid = (x0 + x1) / 2
        size = 9.0
        tw = pdfmetrics.stringWidth(title.upper(), CINZEL_BOLD, size)
        base = y - 9
        self.label(mid, base, title, size=size, align="center", bold=True)
        ly = base + 3
        self.hline(x0 + 4, mid - tw / 2 - 10, ly)
        self.hline(mid + tw / 2 + 10, x1 - 4, ly)
        self.diamond(x0 + 2, ly, 1.8)
        self.diamond(x1 - 2, ly, 1.8)
        self.diamond(mid - tw / 2 - 6, ly, 1.3, fill=False)
        self.diamond(mid + tw / 2 + 6, ly, 1.3, fill=False)
        return y - 15

    def footer(self, left: str, page: int, pages: int):
        y = self.M + 9
        room = 2 * (self.x1 - 8 - 30 - self.W / 2)  # centred, clear of the page number
        self.text(self.W / 2, y, _ellipsize(" ".join(left.split()), SERIF_ITALIC, 7.5, room), SERIF_ITALIC, 7.5,
                  "center")
        self.text(self.x1 - 8, y, f"{page} / {pages}", SERIF_ITALIC, 7.5, "right")

    # -- widgets -----------------------------------------------------------------------------
    def _register(self, d: Dict[str, Any]):
        doc = self.c._doc
        d.setdefault("Type", pdfdoc.PDFName("Annot"))
        d.setdefault("Subtype", pdfdoc.PDFName("Widget"))
        d["P"] = doc.thisPageRef()
        d["F"] = 4  # print
        pd = pdfdoc.PDFDictionary(d)
        self.c._addAnnotation(pd)
        self.form.fields.append(doc.Reference(pd))

    def field(self, name: str, x, y, w, h, value: Any = "", size=9.0, multiline=False,
              align="left", underline=True, tooltip: str = "") -> str:
        """Editable text field; its appearance is drawn with the embedded EB Garamond."""
        c = self.c
        value = _s(value)
        if not multiline:
            value = " ".join(value.split("\n"))
        value = _cap(value, MAX_TEXT if multiline else MAX_LINE)
        name = self.unique(name)
        self._ap += 1
        xo = f"SRap{self._ap}"
        c.beginForm(xo, 0, 0, w, h)
        c._code.append("/Tx BMC")
        c.saveState()
        p = c.beginPath()
        p.rect(1, 0.5, w - 2, h - 1)
        c.clipPath(p, stroke=0, fill=0)
        c.setFillGray(0)
        if value:
            size = self._draw_value(value, w, h, size, multiline, align)
        c.restoreState()
        c._code.append("EMC")
        c.endForm()
        d = {
            "FT": pdfdoc.PDFName("Tx"),
            "T": pdfdoc.PDFString(name),
            "V": pdfdoc.PDFString(value),
            "Rect": pdfdoc.PDFArray([x, y, x + w, y + h]),
            "DA": pdfdoc.PDFString(f"/{FORM_FONT_KEY} {size:g} Tf 0 g"),
            "Q": {"left": 0, "center": 1, "right": 2}[align],
            "AP": pdfdoc.PDFDictionary({"N": pdfdoc.PDFObjectReference(pdfdoc.xObjectName(xo))}),
            "MK": pdfdoc.PDFDictionary({}),
        }
        if multiline:
            d["Ff"] = 1 << 12
        if tooltip:
            d["TU"] = pdfdoc.PDFString(tooltip)
        self._register(d)
        self._ink()
        if underline:
            self.hline(x, x + w, y)
        return name

    def _draw_value(self, value: str, w, h, size, multiline, align) -> float:
        """Draw the pre-filled value; returns the font size used (shrunk until the value fits)."""
        c = self.c
        pad = 2.0
        if multiline:
            s, lines = _fit_lines(value, w - 2 * pad, h - 2, size)
            leading = s * 1.17
            block = (len(lines) - 1) * leading + s * 1.1  # ascender to descender
            if h < 24:  # one- or two-line answer on an underline: centre it in the box
                y = (h + block) / 2 - s * 0.82
            else:
                y = h - pad - s * 0.82
            c.setFont(SERIF, s)
            for ln in lines:
                if y < -s * 0.2:
                    break
                c.drawString(pad, y, ln)
                y -= leading
            return s
        width = pdfmetrics.stringWidth(value, SERIF, size)
        s = size if width <= w - 2 * pad else max(6.0, size * (w - 2 * pad) / width)
        c.setFont(SERIF, s)
        y = max(1.6, min(3.2, (h - s * 0.66) / 2))  # sit on the underline
        if align == "center":
            c.drawCentredString(w / 2, y, value)
        elif align == "right":
            c.drawRightString(w - pad, y, value)
        else:
            c.drawString(pad, y, value)
        return s

    def _check_ap(self, mark: str, size: float, state: str):
        key = (mark, round(size, 2), state)
        if key in self._cb_refs:
            return self._cb_refs[key]
        s = size
        ops = ["q 0 g 0 G"]
        if state == "Yes":
            if mark == "dot":
                r = s / 2 - 1.15
                k = 0.5523 * r
                cx = cy = s / 2
                ops.append(
                    f"{cx + r:.3f} {cy:.3f} m "
                    f"{cx + r:.3f} {cy + k:.3f} {cx + k:.3f} {cy + r:.3f} {cx:.3f} {cy + r:.3f} c "
                    f"{cx - k:.3f} {cy + r:.3f} {cx - r:.3f} {cy + k:.3f} {cx - r:.3f} {cy:.3f} c "
                    f"{cx - r:.3f} {cy - k:.3f} {cx - k:.3f} {cy - r:.3f} {cx:.3f} {cy - r:.3f} c "
                    f"{cx + k:.3f} {cy - r:.3f} {cx + r:.3f} {cy - k:.3f} {cx + r:.3f} {cy:.3f} c f")
            elif mark == "fill":
                i = 1.3
                ops.append(f"{i:.2f} {i:.2f} {s - 2 * i:.2f} {s - 2 * i:.2f} re f")
            elif mark in ("slash", "cross"):
                i = 1.5
                ops.append(f"1.1 w 1 J {i:.2f} {i:.2f} m {s - i:.2f} {s - i:.2f} l S")
                if mark == "cross":
                    ops.append(f"{i:.2f} {s - i:.2f} m {s - i:.2f} {i:.2f} l S")
        ops.append("Q")
        stream = self.form.makeStream(s, s, "\n".join(ops),
                                      Resources=PDFFromString("<< /ProcSet [/PDF] >>"))
        ref = self.c._doc.Reference(stream)
        self._cb_refs[key] = ref
        return ref

    def checkbox(self, name: str, x, y, size, checked: bool, mark="dot", shape="circle",
                 dashed=False, tooltip: str = "") -> str:
        """One dot/box: the outline is page ink, the mark is the field's 'Yes' appearance."""
        name = self.unique(name)
        c = self.c
        c.saveState()
        c.setLineWidth(0.6 if not dashed else HAIR)
        if dashed:
            c.setDash(1, 1.2)
        if shape == "circle":
            c.circle(x + size / 2, y + size / 2, size / 2 - 0.3, stroke=1, fill=0)
        else:
            c.rect(x + 0.3, y + 0.3, size - 0.6, size - 0.6, stroke=1, fill=0)
        c.restoreState()
        state = "Yes" if checked else "Off"
        ca = {"dot": "l", "fill": "n", "slash": "8", "cross": "8"}[mark]
        d = {
            "FT": pdfdoc.PDFName("Btn"),
            "T": pdfdoc.PDFString(name),
            "V": pdfdoc.PDFName(state),
            "AS": pdfdoc.PDFName(state),
            "Rect": pdfdoc.PDFArray([x, y, x + size, y + size]),
            "AP": pdfdoc.PDFDictionary({"N": pdfdoc.PDFDictionary({
                "Yes": self._check_ap(mark, size, "Yes"),
                "Off": self._check_ap(mark, size, "Off"),
            })}),
            "MK": pdfdoc.PDFDictionary({"CA": pdfdoc.PDFString(ca)}),
            "DA": pdfdoc.PDFString("/ZaDb 0 Tf 0 g"),
            "H": pdfdoc.PDFName("N"),
        }
        if tooltip:
            d["TU"] = pdfdoc.PDFString(tooltip)
        self._register(d)
        return name

    def dots(self, name: str, x, y, value: int, n=5, size=7.6, gap=1.6, mark="dot",
             shape="circle", solid: Optional[int] = None, checked: Optional[Sequence[bool]] = None,
             tooltip: str = "") -> float:
        """Row of n checkboxes starting at x (bottom y); returns the x after the row."""
        for i in range(n):
            if i and i % 5 == 0:
                x += gap * 1.6
            on = checked[i] if checked is not None else i < value
            self.checkbox(f"{name}.{i + 1}", x, y, size, on, mark=mark, shape=shape,
                          dashed=solid is not None and i >= solid, tooltip=tooltip)
            x += size + gap
        return x

    @staticmethod
    def dots_width(n=5, size=7.6, gap=1.6) -> float:
        return n * size + (n - 1) * gap + (n - 1) // 5 * gap * 1.6

    def trait(self, name: str, label: str, x, y, w, value: int, n=5, size=8.6):
        """'Label ........ ooooo' row (y = baseline)."""
        self.text(x, y, label, SERIF, size)
        dw = self.dots_width(n)
        self.dots(name, x + w - dw, y - 1.2, value, n=n, tooltip=label)
        lw = pdfmetrics.stringWidth(label, SERIF, size)
        if x + lw + 4 < x + w - dw - 4:
            self.hline(x + lw + 3, x + w - dw - 3, y, w=0.3, dash=(0.6, 1.8))

    def named_trait(self, name: str, x, y, w, text: str, value: int, n=5, size=8.6, extra: str = ""):
        """Editable name + dots (Disciplines, Backgrounds, Merits)."""
        dw = self.dots_width(n)
        self.field(f"{name}.name", x, y - 2.5, w - dw - 5, 11.5, text, size=size, tooltip=extra or None)
        self.dots(name, x + w - dw, y - 1.2, value, n=n)

    def tracker(self, name: str, label: str, x, y, w, checks: Sequence[bool], mark="fill",
                shape="square", solid: Optional[int] = None, size=8.4, label_w=70, hint: str = ""):
        self.label(x, y, label, size=7.2, bold=True)
        if hint:
            self.text(x, y - 7.5, hint, SERIF_ITALIC, 6.6)
        self.dots(name, x + label_w, y - 2, 0, n=len(checks), size=size, gap=1.8, mark=mark,
                  shape=shape, solid=solid, checked=list(checks), tooltip=label)

    # -- output ------------------------------------------------------------------------------
    def page(self):
        self.c.showPage()
        self._ink()

    def finish(self) -> bytes:
        self.c.save()
        return self.buf.getvalue()


# ---------------------------------------------------------------------------------------------
# Shared blocks


def _header(sc: SheetCanvas, line_title: str, line_sub: str, y: float) -> float:
    draw_sigil(sc.c, sc.W / 2, y - 21, 44)
    sc.label(sc.x0, y - 16, line_title, size=16, bold=True)
    sc.label(sc.x0, y - 28, line_sub, size=6.8)
    sc.label(sc.x1, y - 16, "Character Sheet", size=10.5, bold=True, align="right")
    sc.text(sc.x1, y - 28, "ShadowRealms AI", SERIF_ITALIC, 8.5, "right")
    return y - 52


def _small_header(sc: SheetCanvas, name: str, sub: str, y: float) -> float:
    draw_sigil(sc.c, sc.W / 2, y - 14, 28)
    room = sc.W / 2 - 24 - sc.x0  # up to the sigil
    sc.text(sc.x0, y - 14, _ellipsize(" ".join(name.split()), SERIF, 13, room), SERIF, 13)
    sc.text(sc.x0, y - 25, _ellipsize(" ".join(sub.split()), SERIF_ITALIC, 8.5, room), SERIF_ITALIC, 8.5)
    sc.label(sc.x1, y - 14, "Character Sheet", size=9, bold=True, align="right")
    sc.text(sc.x1, y - 25, "ShadowRealms AI", SERIF_ITALIC, 8.5, "right")
    return y - 38


def _identity(sc: SheetCanvas, cols: Sequence[Sequence[Tuple[str, str, Any]]], y: float, pitch=19.0) -> float:
    gap = 14.0
    cw = (sc.x1 - sc.x0 - gap * (len(cols) - 1)) / len(cols)
    for ci, col in enumerate(cols):
        x = sc.x0 + ci * (cw + gap)
        lw = max(pdfmetrics.stringWidth(lbl.upper(), CINZEL, 7) for lbl, _, _ in col) + 5
        for ri, (lbl, key, val) in enumerate(col):
            base = y - 14 - ri * pitch
            sc.label(x, base, lbl, size=7)
            size = 10.5 if key == "name" else 9.0
            text = _s(val)
            # long answers (concept, ambition) wrap onto two smaller lines instead of shrinking away
            wrap = pdfmetrics.stringWidth(text, SERIF, size) > cw - lw - 4 and key != "name"
            # a wrapped answer may use the row's full height, up to the underline above
            sc.field(key, x + lw, base - 2.5, cw - lw, pitch - 0.5 if wrap else 16.5, text,
                     size=7.2 if wrap else size,
                     multiline=wrap, tooltip=lbl)
    return y - 14 - (max(len(c) for c in cols) - 1) * pitch - 10


def _columns(sc: SheetCanvas, n: int, gap: float = 16.0, x0=None, x1=None) -> Tuple[List[float], float]:
    x0 = sc.x0 if x0 is None else x0
    x1 = sc.x1 if x1 is None else x1
    cw = (x1 - x0 - gap * (n - 1)) / n
    return [x0 + i * (cw + gap) for i in range(n)], cw


def _col_title(sc: SheetCanvas, x, w, y, title):
    sc.text(x + w / 2, y, title, SERIF_ITALIC, 8.6, "center")


def _xp_strings(xp: Dict[str, Any]) -> Tuple[str, str, str, str]:
    log = xp.get("log")
    lines = []
    for e in _list(log)[-40:]:
        if isinstance(e, dict):
            amt = next((e.get(k) for k in ("amount", "xp", "cost", "points", "delta") if e.get(k) not in (None, "")), "")
            what = next((e.get(k) for k in ("note", "reason", "description", "what", "label", "item") if e.get(k)), "")
            when = next((e.get(k) for k in ("date", "at", "session", "when") if e.get(k)), "")
            when = str(when)[:10]
            if isinstance(amt, (int, float)) and amt > 0:
                amt = f"+{amt:g}"
            parts = [p for p in (when, f"{amt}" if amt != "" else "", _s(what)) if p]
            lines.append(" · ".join(parts))
        elif _s(e):
            lines.append(_s(e))
    if isinstance(log, str):
        lines.append(log.strip())

    def num(k):
        v = xp.get(k)
        return "" if v in (None, "") else _s(v)

    total, spent, unspent = num("total"), num("spent"), num("unspent")
    if not unspent and total and spent:
        t, sp = _n(total, -10**6, 10**6), _n(spent, -10**6, 10**6)
        if f"{t}" == total.strip() and f"{sp}" == spent.strip():
            unspent = str(t - sp)
    return total, spent, unspent, "\n".join(lines)


def _experience(sc: SheetCanvas, xp: Dict[str, Any], x, y, w, log_h: float = 0.0) -> float:
    total, spent, unspent, log = _xp_strings(xp)
    cols, cw = _columns(sc, 3, gap=10, x0=x, x1=x + w)
    for cx, (lbl, key, val) in zip(cols, (("Total", "xp.total", total), ("Spent", "xp.spent", spent),
                                          ("Unspent", "xp.unspent", unspent))):
        sc.label(cx, y - 10, lbl, size=7)
        lw = pdfmetrics.stringWidth(lbl.upper(), CINZEL, 7) + 5
        sc.field(key, cx + lw, y - 13, cw - lw, 13, val, size=9.5, align="center", tooltip=f"Experience {lbl}")
    y -= 18
    if log_h > 0:
        sc.rect(x, y - log_h, w, log_h)
        sc.field("xp.log", x, y - log_h, w, log_h, log, size=7.8, multiline=True, underline=False,
                 tooltip="Experience log")
        y -= log_h + 4
    return y


def _notes_box(sc: SheetCanvas, name: str, title: str, x, y, w, h, value: str, size=8.4):
    sc.label(x, y - 8, title, size=7, bold=True)
    sc.rect(x, y - h, w, h - 12)
    sc.field(name, x, y - h, w, h - 12, value, size=size, multiline=True, underline=False, tooltip=title)


def _ritual_rows(rituals: List[Any]) -> int:
    """Two columns, every saved ritual plus one blank line."""
    return max(2, math.ceil((len(rituals) + 1) / 2))


def _ritual_text(r: Any) -> str:
    if isinstance(r, dict):
        lvl = _n(r.get("level"), 0, 5)
        return f"{_s(r.get('name'))} ({lvl})" if lvl else _s(r.get("name"))
    return _s(r)


def _rituals(sc: SheetCanvas, rituals: List[Any], y: float, rows: Optional[int] = None) -> float:
    rows = rows or _ritual_rows(rituals)
    y = sc.section("Rituals", y)
    cols, cw = _columns(sc, 2, gap=22)
    for i in range(rows * 2):
        r = rituals[i] if i < len(rituals) else {}
        name = _s(r.get("name")) if isinstance(r, dict) else _s(r)
        lvl = _n(r.get("level"), 0, 5) if isinstance(r, dict) else 0
        x = cols[i // rows]
        base = y - 9 - (i % rows) * 13.5
        sc.named_trait(f"ritual{i + 1}", x, base, cw, name, lvl)
    return y - 9 - (rows - 1) * 13.5 - 9


# ---------------------------------------------------------------------------------------------
# V5

V5_ATTRS = {
    "physical": ("strength", "dexterity", "stamina"),
    "social": ("charisma", "manipulation", "composure"),
    "mental": ("intelligence", "wits", "resolve"),
}
V5_SKILLS = {
    "physical": ("athletics", "brawl", "craft", "drive", "firearms", "larceny", "melee", "stealth", "survival"),
    "social": ("animal_ken", "etiquette", "insight", "intimidation", "leadership", "performance",
               "persuasion", "streetwise", "subterfuge"),
    "mental": ("academics", "awareness", "finance", "investigation", "medicine", "occult", "politics",
               "science", "technology"),
}


def _track(track: Any, fallback_max: int) -> Tuple[int, int, int]:
    t = _obj(track)
    mx = _n(t.get("max"), 0, 20) or max(1, fallback_max)
    agg = _n(t.get("aggravated"), 0, mx)
    sup = _n(t.get("superficial"), 0, mx - agg)
    return mx, sup, agg


def _power_names(powers: Any) -> List[str]:
    out = []
    for p in _list(powers):
        if isinstance(p, dict):
            nm = _s(p.get("name"))
            if p.get("level") not in (None, "") and nm:
                nm = f"{nm} ({_s(p.get('level'))})"
            out.append(nm)
        else:
            out.append(_s(p))
    return [p for p in out if p]


V5_NOTES_MIN = 90.0  # height kept for Background & Notes at the foot of page 2


def _v5_page2_height(adv_rows: int, touch_rows: int, rit_rows: int, log_h: float) -> float:
    """Height of page 2 below the header, matching the drawing code in _render_v5."""
    h = 15 + 21 + (adv_rows - 1) * 13 + 10          # advantages & flaws
    h += 15 + 10 + 84                               # trackers
    h += 15 + 12 + touch_rows * 21 + 4 + 36         # convictions, touchstones, tenets
    if rit_rows:
        h += 15 + 9 + (rit_rows - 1) * 13.5 + 9
    h += 15 + 18 + (log_h + 4 if log_h else 0)      # experience
    return h + 15 + V5_NOTES_MIN


def _v5_page2_rows(avail: float, n_adv: int, n_flaw: int, n_touch: int, rituals: List[Any],
                   log_h: float) -> Tuple[int, int, int]:
    """Rows for advantages, touchstones and rituals so page 2 never runs off the paper.

    Blank rows go first; past that the longest list gives way, and what doesn't fit is listed
    under Notes (see _v5_overflow), so nothing saved is lost.
    """
    adv = min(12, max(6, n_adv, n_flaw))
    touch = min(6, max(3, n_touch))
    rit = min(10, _ritual_rows(rituals)) if rituals else 0
    floor = {"adv": min(adv, max(4, n_adv, n_flaw)), "touch": min(touch, max(2, n_touch)),
             "rit": min(rit, max(1, math.ceil(len(rituals) / 2))) if rituals else 0}
    while _v5_page2_height(adv, touch, rit, log_h) > avail:
        rows = {"adv": adv, "touch": touch, "rit": rit}
        spare = [k for k in rows if rows[k] > floor[k]]
        if not spare:
            floor = {"adv": 4, "touch": 2, "rit": 1 if rituals else 0}
            spare = [k for k in rows if rows[k] > floor[k]]
            if not spare:
                break
        k = max(spare, key=lambda k: rows[k] * (21 if k == "touch" else 13))
        if k == "adv":
            adv -= 1
        elif k == "touch":
            touch -= 1
        else:
            rit -= 1
    return adv, touch, rit


OVERFLOW_ITEMS = 300  # entries listed per "More ..." line; the Notes text is capped anyway


def _trait_text(a: Dict[str, Any]) -> str:
    nm = _s(a.get("name") or a.get("label") or a.get("key"))
    dots = _n(a.get("dots", a.get("level")), 0, 10)
    return f"{nm} ({dots})" if dots else nm


def _more(title: str, items: Sequence[Any], fmt=_trait_text) -> List[str]:
    """'More <title>: a (2); b (1)' for entries that didn't get a row of their own."""
    if not items:
        return []
    text = "; ".join(t for t in (fmt(i) for i in items[:OVERFLOW_ITEMS]) if t)
    if len(items) > OVERFLOW_ITEMS:
        text += f"; … {len(items) - OVERFLOW_ITEMS} more"
    return [f"More {title}: {text}"]


def _v5_overflow(advs, flaws, touch, rituals) -> List[str]:
    """Lines for the Notes box: entries that didn't get a row of their own."""
    def touchstone(t):
        return " — ".join(p for p in (_s(t.get("name")), _s(t.get("conviction"))) if p)
    return (_more("advantages", advs) + _more("flaws", flaws) + _more("touchstones", touch, touchstone)
            + _more("rituals", rituals, _ritual_text))


def _discipline_text(d: Dict[str, Any]) -> str:
    powers = _power_names(d.get("powers"))
    return _trait_text(d) + (": " + ", ".join(powers) if powers else "")


def _render_v5(sc: SheetCanvas, ch: Dict[str, Any], chronicle: str, player: str) -> None:
    wm = _obj(ch.get("wod_meta"))
    attrs = _obj(ch.get("attributes"))
    sk = _obj(ch.get("skills"))
    name = _s(ch.get("name"))
    known = {k for ks in V5_SKILLS.values() for k in ks}
    spec: Dict[str, List[str]] = {}
    other_spec = []
    for s in _list(sk.get("specialties")):
        if isinstance(s, dict) and _s(s.get("name")):
            if s.get("skill") in known:
                spec.setdefault(s["skill"], []).append(_s(s["name"]))
            else:
                other_spec.append(f"{_label(_s(s.get('skill')))}: {_s(s['name'])}")

    # ---- page 1: identity, attributes, skills, disciplines
    sc.frame()
    y = _header(sc, "Vampire", "The Masquerade · Fifth Edition", sc.top)
    y = _identity(sc, [
        [("Name", "name", name), ("Concept", "concept", wm.get("concept") or ch.get("concept")),
         ("Predator", "predator_type", wm.get("predator_type")), ("Player", "player", player)],
        [("Chronicle", "chronicle", chronicle), ("Ambition", "ambition", wm.get("ambition")),
         ("Desire", "desire", wm.get("desire"))],
        [("Clan", "clan", wm.get("clan")), ("Generation", "generation", wm.get("generation")),
         ("Sire", "sire", wm.get("sire")), ("Age", "age", wm.get("age"))],
    ], y)

    y = sc.section("Attributes", y)
    cols, cw = _columns(sc, 3, gap=22)
    for x, (cat, keys) in zip(cols, V5_ATTRS.items()):
        _col_title(sc, x, cw, y - 8, cat.title())
        for i, k in enumerate(keys):
            sc.trait(f"attr.{k}", _label(k), x, y - 21 - i * 13, cw, _n(attrs.get(k), 0, 5))
    y -= 21 + 2 * 13 + 10

    y = sc.section("Skills", y)
    pitch = 14.6
    for x, (cat, keys) in zip(cols, V5_SKILLS.items()):
        vals = _obj(sk.get(cat))
        for i, k in enumerate(keys):
            base = y - 9 - i * pitch
            lbl = _label(k)
            sc.text(x, base, lbl, SERIF, 8.6)
            dw = sc.dots_width()
            fx = x + 58
            sc.field(f"skill.{k}.specialty", fx, base - 2.5, cw - dw - 62, 11, ", ".join(spec.get(k, [])),
                     size=7.6, tooltip=f"{lbl} specialties")
            sc.dots(f"skill.{k}", x + cw - dw, base - 1.2, _n(vals.get(k), 0, 5), tooltip=lbl)
    y -= 9 + 8 * pitch + 10

    discs = [d for d in _list(wm.get("disciplines")) if isinstance(d, dict)]
    y = sc.section("Disciplines", y)
    ncols = 3
    avail = y - sc.bottom - 4
    # at most three rows of boxes, each tall enough for a name and three powers
    nrows = max(1, min(3, math.ceil(len(discs) / ncols), int((avail + 8) // 70)))
    nrows = max(nrows, min(2, int((avail + 8) // 70)))
    disc_overflow = _more("disciplines", discs[ncols * nrows:], _discipline_text)
    box_h = (avail - (nrows - 1) * 8) / nrows
    lines = max(3, min(6, int((box_h - 20) // 13)))
    dcols, dw_ = _columns(sc, ncols, gap=12)
    for i in range(ncols * nrows):
        d = discs[i] if i < len(discs) else {}
        x = dcols[i % ncols]
        top = y - (i // ncols) * (box_h + 8)
        sc.rect(x, top - box_h, dw_, box_h)
        pad = 5
        sc.named_trait(f"disc{i + 1}", x + pad, top - 13, dw_ - 2 * pad, _s(d.get("name")),
                       _n(d.get("level", d.get("dots")), 0, 5))
        powers = _power_names(d.get("powers"))
        if len(powers) > lines:  # keep every saved power: the last line holds the rest
            powers = powers[:lines - 1] + ["; ".join(powers[lines - 1:])]
        lh = (box_h - 22) / lines
        for j in range(lines):
            py = top - 22 - (j + 1) * lh + 2
            sc.diamond(x + pad + 2, py + 3.5, 1.1, fill=False)
            sc.field(f"disc{i + 1}.power{j + 1}", x + pad + 6, py, dw_ - 2 * pad - 6, min(11.5, lh - 1),
                     powers[j] if j < len(powers) else "", size=8.4, tooltip="Power")
    sc.footer(f"{name} · {chronicle}" if chronicle else name, 1, 2)
    sc.page()

    # ---- page 2: advantages, trackers, convictions, rituals, XP, notes
    sc.frame()
    y = _small_header(sc, name, " · ".join(p for p in (_s(wm.get("clan")), chronicle) if p), sc.top)

    advs = [a for a in _list(wm.get("advantages")) if isinstance(a, dict)]
    flaws = [a for a in _list(wm.get("flaws")) if isinstance(a, dict)]
    advs += [{"name": f"{_s(n)} (thin-blood)"} for n in _list(wm.get("thin_blood_merits"))[:500] if _s(n)]
    flaws += [{"name": f"{_s(n)} (thin-blood)"} for n in _list(wm.get("thin_blood_flaws"))[:500] if _s(n)]
    touch = [t for t in _list(wm.get("touchstones")) if isinstance(t, dict)]
    rituals = _list(wm.get("rituals"))
    xp = _obj(wm.get("experience"))
    log_h = 34.0 if _xp_strings(xp)[3] else 0.0
    adv_rows, touch_rows, rit_rows = _v5_page2_rows(y - sc.bottom, len(advs), len(flaws), len(touch),
                                                     rituals, log_h)
    overflow = disc_overflow + _v5_overflow(advs[adv_rows:], flaws[adv_rows:], touch[touch_rows:],
                                            rituals[rit_rows * 2:])

    y = sc.section("Advantages & Flaws", y)
    rows = adv_rows
    cols2, cw2 = _columns(sc, 2, gap=22)
    for col, (title, items, key) in enumerate((("Merits & Backgrounds", advs, "adv"), ("Flaws", flaws, "flaw"))):
        x = cols2[col]
        _col_title(sc, x, cw2, y - 8, title)
        for i in range(rows):
            a = items[i] if i < len(items) else {}
            nm = _s(a.get("name"))
            if nm and a.get("kind") == "predator":
                nm += " (predator)"
            sc.named_trait(f"{key}{i + 1}", x, y - 21 - i * 13, cw2, nm, _n(a.get("dots", a.get("level")), 0, 5),
                           extra=_s(a.get("kind")))
    y -= 21 + (rows - 1) * 13 + 10

    y = sc.section("Trackers", y)
    hmax, hsup, hagg = _track(wm.get("health"), _n(attrs.get("stamina"), 0, 10) + 3)
    wmax, wsup, wagg = _track(wm.get("willpower"), _n(attrs.get("composure"), 0, 10) + _n(attrs.get("resolve"), 0, 10))
    left, right = cols2
    ty = y - 10
    for i, (lbl, key, mx, sup, agg) in enumerate((("Health", "health", hmax, hsup, hagg),
                                                  ("Willpower", "willpower", wmax, wsup, wagg))):
        by = ty - i * 42
        n = max(10, mx)
        sc.label(left, by, lbl, size=7.2, bold=True)
        sc.text(left + pdfmetrics.stringWidth(lbl.upper(), CINZEL_BOLD, 7.2) + 5, by, f"max {mx}",
                SERIF_ITALIC, 7.5)
        for r, (hint, mark, count) in enumerate((("superficial", "slash", sup), ("aggravated", "cross", agg))):
            ry = by - 13 - r * 12
            sc.text(left + 56, ry, hint, SERIF_ITALIC, 7.5, "right")
            sc.dots(f"{key}.{hint}", left + 62, ry - 2, 0, n=n, size=8.4, gap=1.8, mark=mark, shape="square",
                    solid=mx, checked=[j < count for j in range(n)], tooltip=f"{lbl}: {hint}")
    hum = _n(wm.get("humanity"), 0, 10)
    stains = _n(wm.get("stains"), 0, 10)
    sc.tracker("humanity", "Humanity", right, ty, cw2, [j < hum for j in range(10)], mark="fill", label_w=78)
    sc.tracker("stains", "Stains", right, ty - 14, cw2, [j >= 10 - stains for j in range(10)], mark="slash",
               label_w=78)
    sc.tracker("hunger", "Hunger", right, ty - 30, cw2, [j < _n(wm.get("hunger"), 0, 5) for j in range(5)],
               mark="fill", label_w=78)
    bp = _n(wm.get("blood_potency"), 0, 10)
    sc.tracker("blood_potency", "Blood Potency", right, ty - 46, cw2, [j < bp for j in range(10)], mark="dot",
               shape="circle", label_w=78)
    y = ty - 84

    y = sc.section("Convictions & Touchstones", y)
    rows = touch_rows
    _col_title(sc, cols2[0], cw2, y - 8, "Conviction")
    _col_title(sc, cols2[1], cw2, y - 8, "Touchstone")
    rh = 21.0
    for i in range(rows):
        t = touch[i] if i < len(touch) else {}
        by = y - 12 - (i + 1) * rh
        sc.field(f"conviction{i + 1}", cols2[0], by, cw2, rh - 2, t.get("conviction"), size=8.2, multiline=True)
        sc.field(f"touchstone{i + 1}", cols2[1], by, cw2, rh - 2, t.get("name"), size=8.2, multiline=True)
        sc.diamond((cols2[0] + cw2 + cols2[1]) / 2, by + rh / 2, 1.4)
    y -= 12 + rows * rh + 4
    tenets = wm.get("chronicle_tenets")
    if isinstance(tenets, (list, tuple)):
        tenets = "\n".join(_s(t) for t in tenets if _s(t))
    sc.label(sc.x0, y - 8, "Chronicle Tenets", size=7, bold=True)
    th = 30.0
    sc.field("chronicle_tenets", sc.x0 + 100, y - th + 2, sc.x1 - sc.x0 - 100, th, _s(tenets), size=8.2,
             multiline=True)
    y -= th + 6

    if rituals:
        y = _rituals(sc, rituals, y, rit_rows)

    y = sc.section("Experience", y)
    y = _experience(sc, xp, sc.x0, y, sc.x1 - sc.x0, log_h)

    y = sc.section("Background & Notes", y)
    h = max(30.0, y - sc.bottom - 2)
    bw = (sc.x1 - sc.x0 - 14) * 0.6
    mf = _obj(ch.get("merits_flaws"))
    notes = "\n".join(p for p in (_s(mf.get("notes")),
                                  ("Specialties: " + "; ".join(other_spec)) if other_spec else "",
                                  *overflow) if p)
    _notes_box(sc, "background", "Background", sc.x0, y, bw, h, _s(ch.get("background")), size=8.2)
    _notes_box(sc, "notes", "Notes", sc.x0 + bw + 14, y, sc.x1 - sc.x0 - bw - 14, h, notes, size=8.2)
    sc.footer(f"{name} · {chronicle}" if chronicle else name, 2, 2)


# ---------------------------------------------------------------------------------------------
# Classic (Revised)

CLASSIC_ATTRS = {
    "physical": ("strength", "dexterity", "stamina"),
    "social": ("charisma", "manipulation", "appearance"),
    "mental": ("perception", "intelligence", "wits"),
}
CLASSIC_ABILITIES = {
    "talents": ("alertness", "athletics", "brawl", "dodge", "empathy", "expression", "intimidation",
                "leadership", "streetwise", "subterfuge"),
    "skills": ("animal_ken", "crafts", "drive", "etiquette", "firearms", "melee", "performance",
               "security", "stealth", "survival"),
    "knowledges": ("academics", "computer", "finance", "investigation", "law", "linguistics", "medicine",
                   "occult", "politics", "science"),
}
MTA_SPHERES = ("correspondence", "entropy", "forces", "life", "matter", "mind", "prime", "spirit", "time")
# docs/rules/classic.json generation_table: blood pool max / per turn
BLOOD_POOL = {4: (50, 10), 5: (40, 8), 6: (30, 6), 7: (20, 4), 8: (15, 3), 9: (14, 2), 10: (13, 1),
              11: (12, 1), 12: (11, 1)}
HEALTH_LEVELS = (("Bruised", ""), ("Hurt", "-1"), ("Injured", "-1"), ("Wounded", "-2"),
                 ("Mauled", "-2"), ("Crippled", "-5"), ("Incapacitated", ""))
LINE_TITLES = {
    "vampire": ("Vampire", "The Masquerade · Revised"),
    "werewolf": ("Werewolf", "The Apocalypse · Revised"),
    "mage": ("Mage", "The Ascension · Revised"),
}


def _render_classic(sc: SheetCanvas, ch: Dict[str, Any], chronicle: str, player: str) -> None:
    line = _s(ch.get("system_type")).lower()
    line = line if line in LINE_TITLES else "vampire"
    wm0 = _obj(ch.get("wod_meta"))
    wm = {**wm0, **_obj(wm0.get("vampire"))} if isinstance(wm0.get("vampire"), dict) else wm0
    attrs = _obj(ch.get("attributes"))
    sk = _obj(ch.get("skills"))
    name = _s(ch.get("name"))
    title, sub = LINE_TITLES[line]

    sc.frame()
    y = _header(sc, title, sub, sc.top)
    third = {
        "vampire": [("Clan", "clan", wm.get("clan")), ("Generation", "generation", wm.get("generation")),
                    ("Sire", "sire", wm.get("sire"))],
        "werewolf": [("Breed", "breed", wm.get("breed")), ("Auspice", "auspice", wm.get("auspice")),
                     ("Tribe", "tribe", wm.get("tribe"))],
        "mage": [("Tradition", "tradition", wm.get("tradition")), ("Essence", "essence", wm.get("essence")),
                 ("Cabal", "cabal", wm.get("cabal"))],
    }[line]
    y = _identity(sc, [
        [("Name", "name", name), ("Player", "player", player), ("Chronicle", "chronicle", chronicle)],
        [("Nature", "nature", wm.get("nature")), ("Demeanor", "demeanor", wm.get("demeanor")),
         ("Concept", "concept", wm.get("concept") or ch.get("concept"))],
        third,
    ], y)

    y = sc.section("Attributes", y)
    cols, cw = _columns(sc, 3, gap=22)
    for x, (cat, keys) in zip(cols, CLASSIC_ATTRS.items()):
        _col_title(sc, x, cw, y - 8, cat.title())
        for i, k in enumerate(keys):
            sc.trait(f"attr.{k}", _label(k), x, y - 21 - i * 13, cw, _n(attrs.get(k), 0, 5))
    y -= 21 + 2 * 13 + 10

    y = sc.section("Abilities", y)
    custom = _obj(sk.get("custom"))
    nrows = max(11, max(10 + len(_list(custom.get(c))) + 1 for c in CLASSIC_ABILITIES))
    nrows = min(nrows, 13)
    pitch = 12.6
    overflow: List[str] = []
    for x, (cat, keys) in zip(cols, CLASSIC_ABILITIES.items()):
        _col_title(sc, x, cw, y - 8, cat.title())
        vals = _obj(sk.get(cat))
        for i, k in enumerate(keys):
            sc.trait(f"{cat}.{k}", _label(k), x, y - 21 - i * pitch, cw, _n(vals.get(k), 0, 5))
        extras = [e for e in _list(custom.get(cat)) if isinstance(e, dict)]
        overflow += _more(cat, extras[nrows - len(keys):])
        for j in range(nrows - len(keys)):
            e = extras[j] if j < len(extras) else {}
            sc.named_trait(f"{cat}.custom{j + 1}", x, y - 21 - (len(keys) + j) * pitch, cw,
                           _s(e.get("label") or e.get("key")), _n(e.get("dots"), 0, 5))
    y -= 21 + (nrows - 1) * pitch + 10

    y = sc.section("Advantages", y)
    arow = 12.8
    if line == "vampire":
        discs = [d for d in _list(wm.get("disciplines")) if isinstance(d, dict)]
        bgs = [d for d in _list(wm.get("backgrounds")) if isinstance(d, dict)]
        rows = min(9, max(6, len(discs), len(bgs)))
        overflow += _more("disciplines", discs[rows:]) + _more("backgrounds", bgs[rows:])
        for x, (title2, items, key) in zip(cols[:2], (("Disciplines", discs, "disc"), ("Backgrounds", bgs, "bg"))):
            _col_title(sc, x, cw, y - 8, title2)
            for i in range(rows):
                d = items[i] if i < len(items) else {}
                sc.named_trait(f"{key}{i + 1}", x, y - 21 - i * arow, cw, _s(d.get("name")),
                               _n(d.get("dots", d.get("level")), 0, 5))
        _col_title(sc, cols[2], cw, y - 8, "Virtues")
        v = _obj(wm.get("virtues"))
        for i, (k, lbl) in enumerate((("conscience", "Conscience"), ("self_control", "Self-Control"),
                                      ("courage", "Courage"))):
            alt = {"conscience": "conviction", "self_control": "instinct"}.get(k)
            val = v.get(k) if v.get(k) is not None else v.get(alt) if alt else None
            sc.trait(f"virtue.{k}", lbl, cols[2], y - 21 - i * arow * 1.4, cw, _n(val, 0, 5))
    elif line == "werewolf":
        rows = 6
        _col_title(sc, cols[0], cw, y - 8, "Backgrounds")
        bgs = [d for d in _list(wm.get("backgrounds")) if isinstance(d, dict)]
        overflow += _more("backgrounds", bgs[rows:])
        for i in range(rows):
            d = bgs[i] if i < len(bgs) else {}
            sc.named_trait(f"bg{i + 1}", cols[0], y - 21 - i * arow, cw, _s(d.get("name")), _n(d.get("dots"), 0, 5))
        gx = cols[1]
        gw = cols[2] + cw - gx
        _col_title(sc, gx, gw, y - 8, "Gifts")
        gifts = wm.get("gifts_notes") or _s(wm.get("gifts"))
        sc.rect(gx, y - 21 - (rows - 1) * arow - 4, gw, (rows - 1) * arow + 12)
        sc.field("gifts", gx, y - 21 - (rows - 1) * arow - 4, gw, (rows - 1) * arow + 12, _s(gifts),
                 size=8.4, multiline=True, underline=False)
    else:  # mage
        rows = 5
        sph = _obj(wm.get("spheres"))
        for i, k in enumerate(MTA_SPHERES):
            x = cols[i // rows]
            if i == 0 or i == rows:
                _col_title(sc, x, cw, y - 8, "Spheres")
            sc.trait(f"sphere.{k}", _label(k), x, y - 21 - (i % rows) * arow, cw, _n(sph.get(k), 0, 5))
        _col_title(sc, cols[2], cw, y - 8, "Backgrounds")
        bgs = [d for d in _list(wm.get("backgrounds")) if isinstance(d, dict)]
        overflow += _more("backgrounds", bgs[rows:])
        for i in range(rows):
            d = bgs[i] if i < len(bgs) else {}
            sc.named_trait(f"bg{i + 1}", cols[2], y - 21 - i * arow, cw, _s(d.get("name")), _n(d.get("dots"), 0, 5))
    y -= 21 + (rows - 1) * arow + 10

    # bottom band: merits & flaws | humanity / willpower / blood | health
    mf = _obj(ch.get("merits_flaws"))
    entries = [e for e in _list(mf.get("entries")) if isinstance(e, dict)]
    y = sc.section("Merits & Flaws  ·  Traits  ·  Health", y)
    band_top = y
    x = cols[0]
    _col_title(sc, x, cw, y - 8, "Merits & Flaws")
    mrows = max(4, int((y - 21 - sc.bottom - 6) // 12.6) + 1)
    mrows = min(mrows, 14)
    mrows = sum(1 for i in range(mrows) if y - 21 - i * 12.6 >= sc.bottom + 6)

    def merit_text(e):
        pts = _n(e.get("points"), -99, 99)
        nm = _s(e.get("name")) + (f" ({_s(e['note'])})" if _s(e.get("note")) else "")
        return f"{nm} ({pts:+d})" if pts else nm
    overflow += _more("merits & flaws", entries[mrows:], merit_text)
    for i in range(mrows):
        e = entries[i] if i < len(entries) else {}
        base = y - 21 - i * 12.6
        pts = e.get("points")
        cost = "" if pts in (None, "") else (f"+{_n(pts, -99, 99)}" if _n(pts, -99, 99) > 0 else _s(pts))
        nm = _s(e.get("name"))
        if _s(e.get("note")):
            nm = f"{nm} ({_s(e['note'])})"
        sc.field(f"merit{i + 1}.name", x, base - 2.5, cw - 26, 11.5, nm, size=8.4)
        sc.field(f"merit{i + 1}.cost", x + cw - 22, base - 2.5, 22, 11.5, cost, size=8.4, align="center")

    x = cols[1]
    yy = y - 8
    wp = _n(wm.get("willpower"), 0, 10)
    if line == "vampire":
        path = wm.get("path")
        path_name = _s(path) if isinstance(path, str) and not path.strip().isdigit() else "Humanity"
        rating = _n(wm.get("path_rating") if path_name != "Humanity" and wm.get("path_rating") is not None
                    else (path if isinstance(path, (int, float)) or _s(path).isdigit() else wm.get("humanity")), 0, 10)
        sc.field("path.name", x + 18, yy - 4, cw - 36, 12, path_name, size=9, align="center", tooltip="Humanity / Path")
        sc.dots("path", x + (cw - SheetCanvas.dots_width(10)) / 2, yy - 17, rating, n=10)
        yy -= 32
    sc.text(x + cw / 2, yy, "Willpower", SERIF_ITALIC, 8.6, "center")
    dx = x + (cw - SheetCanvas.dots_width(10)) / 2
    sc.dots("willpower", dx, yy - 12, wp, n=10)
    cur = wm.get("willpower_current")
    sc.dots("willpower.current", dx, yy - 22, 0, n=10, mark="cross", shape="square",
            checked=[j < (wp - _n(cur, 0, 10) if cur is not None else 0) for j in range(10)])
    yy -= 38
    if line == "vampire":
        gen = _n(wm.get("generation"), 3, 16) if wm.get("generation") not in (None, "") else 13
        mx, per_turn = BLOOD_POOL.get(gen, (10, 1)) if gen >= 4 else (50, 10)
        cur_b = wm.get("blood_pool")
        cur_b = mx if cur_b in (None, "") else _n(cur_b, 0, 50)
        sc.text(x + cw / 2, yy, "Blood Pool", SERIF_ITALIC, 8.6, "center")
        bw = SheetCanvas.dots_width(10)
        for r in range(2):
            sc.dots(f"blood.r{r + 1}", x + (cw - bw) / 2, yy - 12 - r * 10, 0, n=10, mark="fill",
                    shape="square", solid=max(0, min(10, mx - r * 10)),
                    checked=[r * 10 + j < min(cur_b, 20) for j in range(10)])
        sc.label(x + (cw - bw) / 2, yy - 38, "Per turn", size=6.5)
        sc.field("blood.per_turn", x + (cw - bw) / 2 + 42, yy - 41, 24, 11, str(per_turn), size=8.6, align="center")
        sc.label(x + (cw - bw) / 2 + 76, yy - 38, "Max", size=6.5)
        sc.field("blood.max", x + (cw - bw) / 2 + 96, yy - 41, 24, 11, str(mx), size=8.6, align="center")
        yy -= 52
    else:
        pools = (("Rage", "rage"), ("Gnosis", "gnosis")) if line == "werewolf" else (
            ("Arete", "arete"), ("Quintessence", "quintessence"))
        for lbl, key in pools:
            v = _n(wm.get(key), 0, 10)
            sc.text(x + cw / 2, yy, lbl, SERIF_ITALIC, 8.6, "center")
            sc.dots(key, dx, yy - 12, v, n=10)
            sc.dots(f"{key}.current", dx, yy - 22, 0, n=10, mark="cross", shape="square", checked=[False] * 10)
            yy -= 34

    x = cols[2]
    _col_title(sc, x, cw, band_top - 8, "Health")
    dmg = _n(wm.get("health_damage"), 0, 7)
    for i, (lvl, pen) in enumerate(HEALTH_LEVELS):
        base = band_top - 21 - i * 12.4
        sc.text(x, base, lvl, SERIF, 8.6)
        sc.text(x + cw - 16, base, pen, SERIF, 8.6, "right")
        sc.checkbox(f"health.{i + 1}", x + cw - 9, base - 1.6, 8.4, i < dmg, mark="cross", shape="square",
                    tooltip=lvl)
    hy = band_top - 21 - 7 * 12.4 - 4
    if line == "vampire":
        sc.label(x, hy, "Weakness", size=7)
        sc.field("weakness", x + 50, hy - 3, cw - 50, 12, wm.get("weakness"), size=8.4)
        hy -= 16
    xp = _obj(wm.get("experience"))
    total, spent, unspent, log = _xp_strings(xp)
    _col_title(sc, x, cw, hy - 4, "Experience")
    for i, (lbl, key, val) in enumerate((("Total", "xp.total", total), ("Spent", "xp.spent", spent),
                                         ("Unspent", "xp.unspent", unspent))):
        base = hy - 18 - i * 14
        sc.label(x, base, lbl, size=7)
        sc.field(key, x + 50, base - 3, cw - 50, 12.5, val, size=9, align="center", tooltip=f"Experience {lbl}")
    sc.footer(f"{name} · {chronicle}" if chronicle else name, 1, 2)
    sc.page()

    # ---- page 2: rituals, XP log, background, notes
    sc.frame()
    y = _small_header(sc, name, " · ".join(p for p in (_s(wm.get("clan") or wm.get("tribe") or wm.get("tradition")),
                                                        chronicle) if p), sc.top)
    rituals = _list(wm.get("rituals"))
    if rituals:
        # what the rest of the page needs: other traits, combat, description, possessions,
        # the experience log and Background & Notes at its smallest
        rest = 74.5 + 87.5 + 50 + 85 + (81 if log else 0) + 15 + V5_NOTES_MIN
        fit = int((y - sc.bottom - rest - 33) // 13.5) + 1
        rit_rows = max(1, min(_ritual_rows(rituals), fit))
        overflow += _more("rituals", rituals[rit_rows * 2:], _ritual_text)
        y = _rituals(sc, rituals, y, rit_rows)
    y = sc.section("Other Traits", y)
    cols2, cw2 = _columns(sc, 2, gap=22)
    for i in range(8):
        sc.named_trait(f"other{i + 1}", cols2[i // 4], y - 9 - (i % 4) * 13.5, cw2, "", 0)
    y -= 9 + 3 * 13.5 + 10

    y = sc.section("Combat", y)
    heads = (("Weapon / Attack", 0.34), ("Diff.", 0.09), ("Damage", 0.13), ("Range", 0.1), ("Rate", 0.1),
             ("Clip", 0.1), ("Conceal", 0.14))
    tw = sc.x1 - sc.x0
    xs = [sc.x0]
    for _, f in heads:
        xs.append(xs[-1] + f * tw)
    for (h, _), cx, nx in zip(heads, xs, xs[1:]):
        sc.text((cx + nx) / 2, y - 8, h, SERIF_ITALIC, 8, "center")
    for r in range(4):
        base = y - 22 - r * 13.5
        for ci, ((h, _), cx, nx) in enumerate(zip(heads, xs, xs[1:])):
            sc.field(f"combat{r + 1}.{h.split()[0].lower().strip('.')}", cx + 2, base - 2.5, nx - cx - 6, 11.5, "",
                     size=8.4, align="left" if ci == 0 else "center")
    y -= 22 + 3 * 13.5 + 10

    y = sc.section("Description", y)
    desc = (("Age", "age"), ("Apparent Age", "apparent_age"), ("Date of Birth", "date_of_birth"),
            ("R.I.P.", "rip"), ("Hair", "hair"), ("Eyes", "eyes"), ("Nationality", "nationality"),
            ("Height", "height"))
    dcols, dcw = _columns(sc, 4, gap=12)
    for i, (lbl, key) in enumerate(desc):
        x = dcols[i % 4]
        base = y - 10 - (i // 4) * 15
        lw = pdfmetrics.stringWidth(lbl.upper(), CINZEL, 6.6) + 4
        sc.label(x, base, lbl, size=6.6)
        sc.field(f"desc.{key}", x + lw, base - 2.5, dcw - lw, 12, wm.get(key), size=8.6)
    y -= 10 + 15 + 10

    y = sc.section("Possessions", y)
    third_box = {"vampire": ("Feeding Grounds", "feeding_grounds"), "werewolf": ("Fetishes", "fetishes"),
                 "mage": ("Wonders", "wonders")}[line]
    pcols, pcw = _columns(sc, 3, gap=12)
    for x, (lbl, key) in zip(pcols, (("Gear", "equipment"), third_box, ("Havens", "havens"))):
        _notes_box(sc, f"poss.{key}", lbl, x, y, pcw, 66, _s(wm.get(key)))
    y -= 70
    if log:
        y = sc.section("Experience Log", y)
        sc.rect(sc.x0, y - 60, sc.x1 - sc.x0, 60)
        sc.field("xp.log", sc.x0, y - 60, sc.x1 - sc.x0, 60, log, size=7.8, multiline=True, underline=False)
        y -= 66
    y = sc.section("Background & Notes", y)
    h = max(30.0, y - sc.bottom - 2)
    bw = (sc.x1 - sc.x0 - 14) * 0.6
    notes = "\n".join(p for p in (_s(mf.get("notes")), _s(sk.get("notes")), *overflow) if p)
    _notes_box(sc, "background", "Background", sc.x0, y, bw, h, _s(ch.get("background")))
    _notes_box(sc, "notes", "Notes", sc.x0 + bw + 14, y, sc.x1 - sc.x0 - bw - 14, h, notes)
    sc.footer(f"{name} · {chronicle}" if chronicle else name, 2, 2)


# ---------------------------------------------------------------------------------------------


def build_sheet_pdf(character: Dict[str, Any], *, paper: str = "a4", chronicle_name: str = "",
                    player_name: str = "") -> bytes:
    """Fillable two-page PDF for a character dict (as returned by GET /api/characters/<id>)."""
    ch = dict(character or {})
    name = _s(ch.get("name")) or "Character"
    sc = SheetCanvas(paper if paper in PAPER else "a4", title=name, author=_s(player_name))
    edition = _s(ch.get("rules_edition")).lower()
    if not edition:
        edition = "v5" if _s(_obj(ch.get("wod_meta")).get("edition")).lower() == "v5" else "classic"
    chronicle = _s(chronicle_name or ch.get("campaign_name"))
    if edition == "v5":
        _render_v5(sc, ch, chronicle, _s(player_name))
    else:
        _render_classic(sc, ch, chronicle, _s(player_name))
    return sc.finish()


def safe_filename(name: str, fallback: str = "character") -> str:
    """'Κωνσταντίνος / X' -> 'Κωνσταντίνος X' (letters, digits, space, - _ . only)."""
    s = re.sub(r"[^\w\- .]+", " ", str(name or ""), flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return (s or fallback)[:80]
