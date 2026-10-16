"""
Character sheet as a fillable PDF (GET /api/characters/<id>/sheet.pdf).

Black ink on white only, so it prints clean on a mono laser printer: hairlines, line-art sigil,
no grey fills. Every value is an AcroForm field pre-filled from the saved sheet: text fields for
names and notes, one checkbox per dot or box so players can fill and clear them.

V5 sheets given the rules catalog get Reference page(s) after the two sheet pages: the catalog's
short descriptions of the clan (bane, compulsion), predator type, Discipline powers, rituals,
ceremonies and formulae on the sheet, in the requester's language. Page text only, no fields.
A ghoul's sheet (wod_meta.sheet_kind 'ghoul') has its own two pages: the ghoul power and Blood
Bond & feeding instead of Disciplines; a V5 ghoul has no vitae track, Hunger or Blood Potency. A
Background or Notes text too long for its box on page 2 keeps what fits there and goes on over
'Background & Notes (continued)' page(s) right after it, before the Reference pages.

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
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfdoc, pdfmetrics
from reportlab.pdfbase._glyphlist import _glyphname2unicode
from reportlab.pdfbase.acroform import PDFFromString
from reportlab.pdfbase.ttfonts import TTFont, TTFontFile
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Paragraph

from services.character_sheet_v5 import ghoul_feeding
from services.classic_ghoul import BLOOD_BOND_DRINKS, ghoul_pool, kind_label

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
# Form font encoding: WinAnsi, with Greek and Latin Extended letters (Turkish, Polish, Czech,
# Hungarian...) moved into codes whose WinAnsi characters are rare (unused codes, typographic odds
# and ends, Icelandic letters) and, once those run out, the control codes 1-31 (all but tab, LF, CR).
# Kept characters stay at their WinAnsi codes, so a viewer that encodes typed text through the base
# encoding still picks the right glyph. A viewer that regenerates a field (NeedAppearances, Windows
# viewers) can only show characters this encoding holds: anything else vanishes.

_GREEK = (
    [c for c in range(0x391, 0x3AA) if c != 0x3A2]  # Α-Ω
    + list(range(0x3B1, 0x3CA))                      # α-ω (incl. ς)
    + [0x386, 0x388, 0x389, 0x38A, 0x38C, 0x38E, 0x38F,  # Ά Έ Ή Ί Ό Ύ Ώ
       0x3AC, 0x3AD, 0x3AE, 0x3AF, 0x3CC, 0x3CD, 0x3CE,  # ά έ ή ί ό ύ ώ
       0x3CA, 0x3CB, 0x390, 0x3B0, 0x3AA, 0x3AB, 0x387]  # ϊ ϋ ΐ ΰ Ϊ Ϋ ·
)
# Latin Extended letters that aren't in WinAnsi: Turkish first, then Hungarian, Czech, Polish...
_LATIN_EXT = [ord(c) for c in "ğĞıİşŞőŐűŰčČłŁćĆśŚęĘąĄżŻ"]
_KEEP_HIGH = (set("€…‘’“”•–—œŒ\xa0£«°·»") | set("ÀÁÂÄÇÈÉÊËÍÎÏÑÓÔÖØÚÜßàáâäçèéêëíîïñóôöøúü")
              | set("ŠšŽžãõå"))
# The overflow (ΐ ΰ Ϊ Ϋ ·, then the Latin Extended letters) goes to control codes 1-31, minus tab, LF
# and CR. Checked by hand in Edge 155 on Windows (it rebuilds field appearances): those letters show
# and can be typed correctly, so this stays as it is.
_CONTROL_CODES = [b for b in range(1, 32) if b not in (9, 10, 13)]


def _winansi(b: int) -> Optional[str]:
    try:
        ch = bytes([b]).decode("cp1252")
    except UnicodeDecodeError:
        return None
    return None if b == 0x7F else ch


def _build_encoding() -> Tuple[Dict[int, int], Dict[int, int]]:
    """(byte -> unicode for the codes in use, the bytes that differ from WinAnsi -> unicode)."""
    table: Dict[int, int] = {}
    free = []
    for b in range(32, 256):
        ch = _winansi(b)
        if b < 127 or (ch is not None and ch in _KEEP_HIGH):
            table[b] = ord(ch)
        else:
            free.append(b)
    free += _CONTROL_CODES
    extra = _GREEK + _LATIN_EXT
    assert len(free) >= len(extra), "form font encoding has no room for Greek and Latin Extended"
    diffs = dict(zip(free, extra))
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
    first = min(_BYTE_TO_UNI)
    widths = [face.charWidths.get(_BYTE_TO_UNI.get(b, 0x20), face.defaultWidth) for b in range(first, 256)]
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
        "FirstChar": first,
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


def _voice(ch: Dict[str, Any]) -> str:
    """The voice gender line (read-out voices, docs/VOICE.md); blank when not set."""
    g = _s(ch.get("gender")).lower()
    return g.title() if g in ("female", "male", "neutral") else ""


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
    """reportlab canvas plus black-and-white form helpers.

    flat=True (the print version): the same layout with every value and mark drawn as page content
    and no form at all, so it looks the same in every viewer.
    """

    def __init__(self, paper: str = "a4", title: str = "", author: str = "", flat: bool = False):
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
        self.flat = flat
        self.form = None
        if not flat:
            self._init_form()
        self._ink()

    def _init_form(self):
        c = self.c
        form = c.acroForm  # registers /AcroForm in the catalog
        form.fonts[FORM_FONT_KEY] = _add_form_font(c._doc)
        # reportlab writes one /Font key per font into /DR; with two fonts, write /DR here instead.
        # /ZaDb is for viewers that redraw the checkboxes' /MK marks themselves.
        zadb = form.getRefStr(PDFFromString("<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats /Name /ZaDb >>"))
        form.extras["DR"] = PDFFromString(
            f"<< /Font << /{FORM_FONT_KEY} {form.fonts[FORM_FONT_KEY]} /ZaDb {zadb} >> >>")
        self.form = form

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
        if self.flat:
            c.saveState()
            c.translate(x, y)
            p = c.beginPath()
            p.rect(1, 0.5, w - 2, h - 1)
            c.clipPath(p, stroke=0, fill=0)
            c.setFillGray(0)
            if value:
                self._draw_value(value, w, h, size, multiline, align)
            c.restoreState()
            self._ink()
            if underline:
                self.hline(x, x + w, y)
            return name
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
        if self.flat:  # page text: the font is set per string
            def draw(x, y, s, size, align="left"):
                self.text(x, y, s, SERIF, size, align)
        else:
            def draw(x, y, s, size, align="left"):
                c.setFont(SERIF, size)
                {"left": c.drawString, "center": c.drawCentredString, "right": c.drawRightString}[align](x, y, s)
        if multiline:
            s, lines = _fit_lines(value, w - 2 * pad, h - 2, size)
            leading = s * 1.17
            block = (len(lines) - 1) * leading + s * 1.1  # ascender to descender
            if h < 24:  # one- or two-line answer on an underline: centre it in the box
                y = (h + block) / 2 - s * 0.82
            else:
                y = h - pad - s * 0.82
            for ln in lines:
                if y < -s * 0.2:
                    break
                draw(pad, y, ln, s)
                y -= leading
            return s
        width = pdfmetrics.stringWidth(value, SERIF, size)
        s = size if width <= w - 2 * pad else max(6.0, size * (w - 2 * pad) / width)
        y = max(1.6, min(3.2, (h - s * 0.66) / 2))  # sit on the underline
        x = {"center": w / 2, "right": w - pad}.get(align, pad)
        draw(x, y, value, s, align)
        return s

    @staticmethod
    def _check_ops(mark: str, size: float, state: str) -> str:
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
        return "\n".join(ops)

    def _check_ap(self, mark: str, size: float, state: str):
        key = (mark, round(size, 2), state)
        if key in self._cb_refs:
            return self._cb_refs[key]
        s = size
        stream = self.form.makeStream(s, s, self._check_ops(mark, size, state),
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
        if self.flat:
            if checked:
                c.saveState()
                c.translate(x, y)
                c._code.append(self._check_ops(mark, size, "Yes"))
                c.restoreState()
            return name
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


SMALL_HEADER_H = 38.0


def _small_header(sc: SheetCanvas, name: str, sub: str, y: float, right: str = "Character Sheet") -> float:
    draw_sigil(sc.c, sc.W / 2, y - 14, 28)
    room = sc.W / 2 - 24 - sc.x0  # up to the sigil
    sc.text(sc.x0, y - 14, _ellipsize(" ".join(name.split()), SERIF, 13, room), SERIF, 13)
    sc.text(sc.x0, y - 25, _ellipsize(" ".join(sub.split()), SERIF_ITALIC, 8.5, room), SERIF_ITALIC, 8.5)
    sc.label(sc.x1, y - 14, right, size=9, bold=True, align="right")
    sc.text(sc.x1, y - 25, "ShadowRealms AI", SERIF_ITALIC, 8.5, "right")
    return y - SMALL_HEADER_H


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


# Background & Notes that don't fit their box on page 2 go on "Background & Notes (continued)"
# page(s) right after it: the box keeps the part that fits (as a field, at the box's own size),
# the rest goes into full-width fields, as many pages as it takes. Text that fits at
# CONT_MIN_SIZE or more still shrinks into the box as before.
CONT_MIN_SIZE = 7.0
LONG_TEXT_MAX = 40000   # characters of Background or Notes printed across the pages
CONT_LABEL_H = 12.0     # label above a box (as _notes_box)
CONT_GAP = 8.0


def _field_lines(h: float, size: float) -> int:
    """Lines a multiline field of height h shows at `size` (the test _fit_lines uses)."""
    room = h - 2
    return int((room - size * 1.1) // (size * 1.17)) + 1 if room >= size * 1.1 else 0


def _wrap_width(w: float) -> float:
    # what _fit_lines estimates a line at (w - 2 * pad, then 94 %): wrapping at it means the field
    # never shrinks a part that was cut to fit
    return (w - 4) * 0.94


def _fits(text: str, w: float, h: float, size: float) -> bool:
    """Does the text fit a w x h multiline field at CONT_MIN_SIZE or more?"""
    if not text:
        return True
    s, lines = _fit_lines(text, w - 4, h - 2, size)
    return s >= CONT_MIN_SIZE and (len(lines) - 1) * s * 1.17 + s * 1.1 <= h - 2


def _split_text(text: str, w: float, h: float, size: float) -> Tuple[str, str]:
    """(head, tail): as much of the text as a w x h field shows at `size`, cut between words, and
    the rest. Paragraphs (newlines) are kept; spaces inside the cut paragraph are single."""
    room = _field_lines(h, size)
    paras = text.split("\n")
    used = 0
    for i, para in enumerate(paras):
        lines = simpleSplit(para, SERIF, size, _wrap_width(w)) or [""]
        if used + len(lines) <= room:
            used += len(lines)
            continue
        take = room - used
        words = para.split()
        n = sum(len(ln.split()) for ln in lines[:take]) if take > 0 else 0
        head = paras[:i] + ([" ".join(words[:n])] if n else [])
        tail = [" ".join(words[n:])] + paras[i + 1:]
        return "\n".join(head), "\n".join(tail)
    return text, ""


def _text_height(text: str, w: float, size: float) -> float:
    """Height of a field that shows all of the text at `size`."""
    n = sum(len(simpleSplit(p, SERIF, size, _wrap_width(w)) or [""]) for p in text.split("\n"))
    return (n - 1) * size * 1.17 + size * 1.1 + 4


ContItem = Tuple[str, str, str, float, int]  # (field key, title, text, field height, part)


def _layout_continuation(sc: SheetCanvas, items: List[Tuple[str, str, str]], size: float) -> List[List[ContItem]]:
    """Pages of full-width boxes for what didn't fit on page 2: [(key, title, text, height, part)]."""
    w = sc.x1 - sc.x0
    top = sc.top - SMALL_HEADER_H - 15
    pages: List[List[ContItem]] = []
    y = None
    for key, title, text in items:
        part = 0
        while text:
            if y is None or y - sc.bottom - CONT_LABEL_H - 2 < 3 * size * 1.17 + 4:
                pages.append([])
                y = top
            avail = y - sc.bottom - CONT_LABEL_H - 2
            head, tail = _split_text(text, w, avail, size)
            if not head.strip() and tail:
                if y == top:  # nothing fits a whole page (a word wider than the page): cut it
                    head, tail = text[:MAX_LINE], text[MAX_LINE:]
                else:
                    y = None
                    continue
            box_h = avail if tail else min(avail, _text_height(head, w, size))
            pages[-1].append((key, title, head, box_h, part))
            part += 1
            y -= CONT_LABEL_H + box_h + CONT_GAP
            text = tail.strip("\n") if tail.strip() else ""
    return pages


def _break_long_words(text: str, w: float, size: float) -> str:
    """Words wider than a w-wide field's line (a URL, a pasted line with no spaces) cut into pieces
    that fit, so the box and the continued pages show them whole instead of clipping them."""
    limit = _wrap_width(w)

    def wide(word: str) -> bool:
        return pdfmetrics.stringWidth(word, SERIF, size) > limit

    paras = []
    for para in text.split("\n"):
        words = para.split(" ")
        if not any(wide(wd) for wd in words):
            paras.append(para)
            continue
        pieces = []
        for wd in words:
            while len(wd) > 1 and wide(wd):
                lo, hi = 1, len(wd)
                while lo < hi:  # the longest prefix that fits
                    mid = (lo + hi + 1) // 2
                    if wide(wd[:mid]):
                        hi = mid - 1
                    else:
                        lo = mid
                pieces.append(wd[:lo])
                wd = wd[lo:]
            pieces.append(wd)
        paras.append(" ".join(pieces))
    return "\n".join(paras)


def _background_notes(sc: SheetCanvas, y: float, background: str, notes: str, size: float) -> List[List[ContItem]]:
    """'Background & Notes' at the foot of page 2: Background (60 %) and Notes boxes down to the
    bottom. A text too long for its box keeps what fits there and goes on in the returned
    continuation pages (_render_continuation draws them); the box title says on which page."""
    y = sc.section("Background & Notes", y)
    h = max(30.0, y - sc.bottom - 2)
    bw = (sc.x1 - sc.x0 - 14) * 0.6
    boxes = (("background", "Background", sc.x0, bw, background),
             ("notes", "Notes", sc.x0 + bw + 14, sc.x1 - sc.x0 - bw - 14, notes))
    heads, rest = [], []
    for key, title, _x, w, text in boxes:
        text = _break_long_words(_cap(_s(text), LONG_TEXT_MAX), w, size)
        if _fits(text, w, h - CONT_LABEL_H, size):
            heads.append(text)
            continue
        head, tail = _split_text(text, w, h - CONT_LABEL_H, size)
        heads.append(head)
        rest.append((key, title, tail))
    pages = _layout_continuation(sc, rest, size)
    first = {}
    for i, page in enumerate(pages):
        for item in page:
            first.setdefault(item[0], i)
    for (key, title, x, w, _), head in zip(boxes, heads):
        label = f"{title} (continued on p. {3 + first[key]})" if key in first else title
        _notes_box(sc, key, label, x, y, w, h, head, size=size)
    return pages


def _render_continuation(sc: SheetCanvas, pages: List[List[ContItem]], name: str, sub: str, footer: str,
                         first: int, total: int, size: float) -> None:
    """The 'Background & Notes (continued)' pages, numbered from `first`."""
    w = sc.x1 - sc.x0
    for k, items in enumerate(pages):
        sc.page()
        sc.frame()
        y = _small_header(sc, name, sub, sc.top)
        y = sc.section("Background & Notes (continued)", y)
        for key, title, text, box_h, part in items:
            label = f"{title} (continued)"
            sc.label(sc.x0, y - 8, label, size=7, bold=True)
            sc.rect(sc.x0, y - CONT_LABEL_H - box_h, w, box_h)
            sc.field(f"{key}.cont{part + 1}", sc.x0, y - CONT_LABEL_H - box_h, w, box_h, text, size=size,
                     multiline=True, underline=False, tooltip=label)
            y -= CONT_LABEL_H + box_h + CONT_GAP
        sc.footer(footer, first + k, total)


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


def _v5_specialties(sk: Dict[str, Any]) -> Tuple[Dict[str, List[str]], List[str]]:
    """Specialties by Skill key, and 'Skill: name' for those on keys the sheet doesn't print."""
    known = {k for ks in V5_SKILLS.values() for k in ks}
    spec: Dict[str, List[str]] = {}
    other_spec = []
    for s in _list(sk.get("specialties")):
        if isinstance(s, dict) and _s(s.get("name")):
            if s.get("skill") in known:
                spec.setdefault(s["skill"], []).append(_s(s["name"]))
            else:
                other_spec.append(f"{_label(_s(s.get('skill')))}: {_s(s['name'])}")
    return spec, other_spec


def _v5_attributes_skills(sc: SheetCanvas, y: float, attrs: Dict[str, Any], sk: Dict[str, Any],
                          spec: Dict[str, List[str]]) -> float:
    """Page 1's Attributes and Skills (with their specialties); returns the y below them."""
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
    return y - (9 + 8 * pitch + 10)


def _advantage_rows(sc: SheetCanvas, y: float, advs: List[Dict[str, Any]], flaws: List[Dict[str, Any]],
                    rows: int) -> float:
    """'Advantages & Flaws': Merits & Backgrounds beside Flaws, `rows` lines each."""
    y = sc.section("Advantages & Flaws", y)
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
    return y - (21 + (rows - 1) * 13 + 10)


def _health_willpower(sc: SheetCanvas, x: float, ty: float, wm: Dict[str, Any], attrs: Dict[str, Any],
                      health_fallback: int) -> None:
    """Health and Willpower boxes (superficial / aggravated rows) from ty down, 84 points tall."""
    hmax, hsup, hagg = _track(wm.get("health"), health_fallback)
    wmax, wsup, wagg = _track(wm.get("willpower"), _n(attrs.get("composure"), 0, 10) + _n(attrs.get("resolve"), 0, 10))
    for i, (lbl, key, mx, sup, agg) in enumerate((("Health", "health", hmax, hsup, hagg),
                                                  ("Willpower", "willpower", wmax, wsup, wagg))):
        by = ty - i * 42
        n = max(10, mx)
        sc.label(x, by, lbl, size=7.2, bold=True)
        sc.text(x + pdfmetrics.stringWidth(lbl.upper(), CINZEL_BOLD, 7.2) + 5, by, f"max {mx}",
                SERIF_ITALIC, 7.5)
        for r, (hint, mark, count) in enumerate((("superficial", "slash", sup), ("aggravated", "cross", agg))):
            ry = by - 13 - r * 12
            sc.text(x + 56, ry, hint, SERIF_ITALIC, 7.5, "right")
            sc.dots(f"{key}.{hint}", x + 62, ry - 2, 0, n=n, size=8.4, gap=1.8, mark=mark, shape="square",
                    solid=mx, checked=[j < count for j in range(n)], tooltip=f"{lbl}: {hint}")


def _humanity_stains(sc: SheetCanvas, x: float, ty: float, w: float, wm: Dict[str, Any]) -> None:
    hum = _n(wm.get("humanity"), 0, 10)
    stains = _n(wm.get("stains"), 0, 10)
    sc.tracker("humanity", "Humanity", x, ty, w, [j < hum for j in range(10)], mark="fill", label_w=78)
    sc.tracker("stains", "Stains", x, ty - 14, w, [j >= 10 - stains for j in range(10)], mark="slash", label_w=78)


def _convictions(sc: SheetCanvas, y: float, touch: List[Dict[str, Any]], rows: int) -> float:
    """'Convictions & Touchstones', `rows` pairs; returns the y below them."""
    y = sc.section("Convictions & Touchstones", y)
    cols2, cw2 = _columns(sc, 2, gap=22)
    _col_title(sc, cols2[0], cw2, y - 8, "Conviction")
    _col_title(sc, cols2[1], cw2, y - 8, "Touchstone")
    rh = 21.0
    for i in range(rows):
        t = touch[i] if i < len(touch) else {}
        by = y - 12 - (i + 1) * rh
        sc.field(f"conviction{i + 1}", cols2[0], by, cw2, rh - 2, t.get("conviction"), size=8.2, multiline=True)
        sc.field(f"touchstone{i + 1}", cols2[1], by, cw2, rh - 2, t.get("name"), size=8.2, multiline=True)
        sc.diamond((cols2[0] + cw2 + cols2[1]) / 2, by + rh / 2, 1.4)
    return y - (12 + rows * rh + 4)


def _render_v5(sc: SheetCanvas, ch: Dict[str, Any], chronicle: str, player: str, pages: int = 2) -> int:
    """The two V5 sheet pages, then any 'Background & Notes (continued)' pages; returns how many
    of those it drew (build_sheet_pdf counts them into `pages`)."""
    wm = _obj(ch.get("wod_meta"))
    attrs = _obj(ch.get("attributes"))
    sk = _obj(ch.get("skills"))
    name = _s(ch.get("name"))
    spec, other_spec = _v5_specialties(sk)
    footer = f"{name} · {chronicle}" if chronicle else name

    # ---- page 1: identity, attributes, skills, disciplines
    sc.frame()
    y = _header(sc, "Vampire", "The Masquerade · Fifth Edition", sc.top)
    y = _identity(sc, [
        [("Name", "name", name), ("Concept", "concept", wm.get("concept") or ch.get("concept")),
         ("Predator", "predator_type", wm.get("predator_type")), ("Player", "player", player)],
        [("Chronicle", "chronicle", chronicle), ("Ambition", "ambition", wm.get("ambition")),
         ("Desire", "desire", wm.get("desire")), ("Voice", "voice_gender", _voice(ch))],
        [("Clan", "clan", wm.get("clan")), ("Generation", "generation", wm.get("generation")),
         ("Sire", "sire", wm.get("sire")), ("Age", "age", wm.get("age"))],
    ], y)
    y = _v5_attributes_skills(sc, y, attrs, sk, spec)

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
    sc.footer(footer, 1, pages)
    sc.page()

    # ---- page 2: advantages, trackers, convictions, rituals, XP, notes
    sc.frame()
    sub = " · ".join(p for p in (_s(wm.get("clan")), chronicle) if p)
    y = _small_header(sc, name, sub, sc.top)

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

    y = _advantage_rows(sc, y, advs, flaws, adv_rows)

    y = sc.section("Trackers", y)
    (left, right), cw2 = _columns(sc, 2, gap=22)
    ty = y - 10
    _health_willpower(sc, left, ty, wm, attrs, _n(attrs.get("stamina"), 0, 10) + 3)
    _humanity_stains(sc, right, ty, cw2, wm)
    sc.tracker("hunger", "Hunger", right, ty - 30, cw2, [j < _n(wm.get("hunger"), 0, 5) for j in range(5)],
               mark="fill", label_w=78)
    bp = _n(wm.get("blood_potency"), 0, 10)
    sc.tracker("blood_potency", "Blood Potency", right, ty - 46, cw2, [j < bp for j in range(10)], mark="dot",
               shape="circle", label_w=78)
    y = ty - 84

    y = _convictions(sc, y, touch, touch_rows)
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

    mf = _obj(ch.get("merits_flaws"))
    notes = "\n".join(p for p in (_s(mf.get("notes")),
                                  ("Specialties: " + "; ".join(other_spec)) if other_spec else "",
                                  *overflow) if p)
    cont = _background_notes(sc, y, _s(ch.get("background")), notes, 8.2)
    sc.footer(footer, 2, pages)
    _render_continuation(sc, cont, name, sub, footer, 3, pages, 8.2)
    return len(cont)


# ---------------------------------------------------------------------------------------------
# V5 ghoul (wod_meta.sheet_kind 'ghoul', services/v5_ghoul_chargen.py): the same Attributes,
# Skills and Advantages; a ghoul power and a Blood Bond & feeding block instead of Disciplines; no
# Hunger, Blood Potency, predator type, rituals; Humanity only when the sheet tracks it.

GHOUL_TEMPLATE_NAMES = {"weak": "Weak mortal", "average": "Average mortal", "gifted": "Gifted mortal",
                        "deadly": "Deadly mortal", "player": "Player ghoul"}
BOND_FLAWS = (("flaw:bondslave", "Bondslave"), ("flaw:two-masters", "Two Masters"), ("flaw:bond-junkie", "Bond Junkie"),
              ("flaw:long-bond", "Long Bond"))


def _ghoul_domitor_name(ch: Dict[str, Any], g: Dict[str, Any]) -> str:
    """The domitor's name: GET's resolved `domitor`, else the name the sheet stored."""
    dom = ch.get("domitor") if isinstance(ch.get("domitor"), dict) else {}
    return _s(dom.get("name")) or _s(_obj(g.get("domitor")).get("name"))


def _ghoul_template_text(g: Dict[str, Any]) -> str:
    """'Gifted mortal · Retainers •••'."""
    t = GHOUL_TEMPLATE_NAMES.get(_s(g.get("template")), _s(g.get("template")))
    dots = _n(g.get("retainer_dots"), 0, 5)
    return " · ".join(p for p in (t, f"Retainers {'•' * dots}" if dots else "") if p)


def _bond_flaws(flaws: List[Dict[str, Any]]) -> str:
    """The Bond Flaws on the sheet ('Bondslave · Two Masters'), by id or name."""
    found = []
    for fid, label in BOND_FLAWS:
        if any(_s(f.get("id")) == fid or _norm(_s(f.get("name"))).startswith(_norm(label)) for f in flaws):
            found.append(label)
    return " · ".join(found)


def _ghoul_footer(name: str, domitor: str, chronicle: str) -> str:
    return " · ".join(p for p in (name, f"Ghoul of {domitor}" if domitor else "Ghoul", chronicle) if p)


def _render_v5_ghoul(sc: SheetCanvas, ch: Dict[str, Any], chronicle: str, player: str, pages: int = 2) -> int:
    """A ghoul's two sheet pages and any continuation pages (returns how many); see _render_v5."""
    wm = _obj(ch.get("wod_meta"))
    g = _obj(wm.get("ghoul"))
    attrs = _obj(ch.get("attributes"))
    sk = _obj(ch.get("skills"))
    name = _s(ch.get("name"))
    domitor = _ghoul_domitor_name(ch, g)
    dom_clan = _s(_obj(ch.get("domitor")).get("clan")) or _s(_obj(g.get("domitor")).get("clan"))
    spec, other_spec = _v5_specialties(sk)
    footer = _ghoul_footer(name, domitor, chronicle)
    flaws = [a for a in _list(wm.get("flaws")) if isinstance(a, dict)]

    # ---- page 1: identity, attributes, skills, ghoul power, Blood Bond & feeding
    sc.frame()
    y = _header(sc, "Ghoul", "Vampire: The Masquerade · Fifth Edition", sc.top)
    age, looks = _s(g.get("age")), _s(g.get("apparent_age"))
    y = _identity(sc, [
        [("Name", "name", name), ("Concept", "concept", wm.get("concept")),
         ("Domitor", "ghoul.domitor", domitor), ("Player", "player", player)],
        [("Chronicle", "chronicle", chronicle), ("Ambition", "ambition", wm.get("ambition")),
         ("Desire", "desire", wm.get("desire")), ("Voice", "voice_gender", _voice(ch))],
        [("Template", "ghoul.template", _ghoul_template_text(g)),
         ("Age / looks", "ghoul.age", " / ".join(p for p in (age, looks) if p)),
         ("Ghoul since", "ghoul.since", g.get("ghouled_since")), ("Domitor's clan", "ghoul.domitor_clan", dom_clan)],
    ], y)
    y = _v5_attributes_skills(sc, y, attrs, sk, spec)

    y = sc.section("Ghoul Power  ·  Blood Bond & Feeding", y)
    avail = y - sc.bottom - 4
    gap = 12.0
    lw = (sc.x1 - sc.x0 - gap) * 0.42
    rx, rw = sc.x0 + lw + gap, sc.x1 - sc.x0 - lw - gap
    pad = 6.0
    sc.rect(sc.x0, y - avail, lw, avail)
    sc.rect(rx, y - avail, rw, avail)

    # left: the power(s), one dot of their Discipline (PG p. 141); blank lines for powers bought later
    discs = [d for d in _list(wm.get("disciplines")) if isinstance(d, dict)]
    power_lines = [(d, p) for d in discs for p in (_power_names(d.get("powers")) or [""])]
    first = power_lines[0] if power_lines else ({}, "")
    x, w = sc.x0 + pad, lw - 2 * pad
    sc.label(x, y - 11, "Ghoul Power", size=7.2, bold=True)
    sc.named_trait("power.discipline", x, y - 26, w, _s(first[0].get("name")), 1 if _s(first[0].get("name")) else 0)
    sc.field("power.name", x, y - 42, w, 12, first[1], size=8.8, tooltip="Power (level 1)")
    more = [f"{_s(d.get('name'))}: {p}" if p else _s(d.get("name")) for d, p in power_lines[1:]]
    py = y - 58
    for i in range(3):  # more level-1 powers, 10 XP each (PG p. 141)
        sc.diamond(x + 2, py + 3.5, 1.1, fill=False)
        sc.field(f"power{i + 2}.name", x + 6, py, w - 6, 11.5, more[i] if i < len(more) else "", size=8.4,
                 tooltip="Another level-1 power")
        py -= 14
    if len(more) > 3:
        other_spec.append("More powers: " + "; ".join(more[3:]))
    note = ("Counts as one dot (Players Guide p. 141). A power above level 1 costs 1 Aggravated, "
            "not a Rouse Check (core p. 234). More level-1 powers of the domitor's Disciplines: 10 XP each.")
    for i, line in enumerate(simpleSplit(note, SERIF_ITALIC, 7.2, w)):
        if py - 4 - i * 8.6 < y - avail + 4:
            break
        sc.text(x, py - 4 - i * 8.6, line, SERIF_ITALIC, 7.2)

    # right: Blood Bond(s) and a feeding note (core pp. 233-234): a note, never a pool or boxes
    x, w = rx + pad, rw - 2 * pad
    bonds = [b for b in _list(g.get("bonds")) if isinstance(b, dict)] or [{"name": domitor}]
    by = y - 11
    for i, b in enumerate(bonds[:2]):
        key = "bond" if i == 0 else "bond2"
        sc.label(x, by, "Blood Bond" if i == 0 else "Second Blood Bond", size=7.2, bold=True)
        sc.label(x, by - 14, "Regnant", size=6.6)
        sc.field(f"{key}.regnant", x + 46, by - 17, w * 0.5 - 46, 12, b.get("name") or (domitor if i == 0 else ""),
                 size=8.8, tooltip="Regnant")
        sx = x + w * 0.5 + 8
        sc.label(sx, by - 14, "Strength", size=6.6)
        st = b.get("strength")
        sc.dots(f"{key}.strength", sx + 44, by - 16, _n(st, 0, 6), n=6, tooltip="Bond Strength (0-6)")
        if st is None:
            sc.text(sx + 44 + SheetCanvas.dots_width(6) + 4, by - 14, "not set", SERIF_ITALIC, 7)
        sc.field(f"{key}.note", x, by - 42, w, 22, b.get("note"), size=7.8, multiline=True, tooltip="Bond note")
        by -= 52
    sc.label(x, by, "Bond Flaws", size=6.6)
    sc.field("bond.flaws", x + 56, by - 3, w - 56, 12, _bond_flaws(flaws), size=8.4, tooltip="Bond Flaws")
    by -= 16
    rules = ("Strength = drinks of the regnant's Blood, up to 6; -1 for each month without. To act against "
             "the regnant: Resolve + Intelligence vs Bond Strength (core p. 234).")
    for line in simpleSplit(rules, SERIF_ITALIC, 7.2, w):
        sc.text(x, by, line, SERIF_ITALIC, 7.2)
        by -= 8.6
    by -= 6
    feeding = ghoul_feeding(g)
    sc.label(x, by, "Feeding", size=7.2, bold=True)
    sc.label(x, by - 14, "Last fed", size=6.6)
    sc.field("feeding.last", x + 46, by - 17, w - 46, 12, feeding.get("last"), size=8.8,
             tooltip="Last fed on the domitor's Blood")
    by -= 30
    cadence = ("A Rouse Check's worth of the domitor's Blood keeps a ghoul about a month (core p. 234). "
               "A V5 ghoul has no vitae track, Hunger or Blood Potency.")
    for line in simpleSplit(cadence, SERIF_ITALIC, 7.2, w):
        sc.text(x, by, line, SERIF_ITALIC, 7.2)
        by -= 8.6
    vh = max(24.0, by - (y - avail) - 6)
    sc.field("feeding.note", x, by - vh, w, vh, feeding.get("note"), size=7.8, multiline=True, tooltip="Feeding note")
    sc.footer(footer, 1, pages)
    sc.page()

    # ---- page 2: advantages, trackers, convictions, experience, notes
    sc.frame()
    sub = " · ".join(p for p in (f"Ghoul of {domitor}" if domitor else "Ghoul", chronicle) if p)
    y = _small_header(sc, name, sub, sc.top)
    advs = [a for a in _list(wm.get("advantages")) if isinstance(a, dict)]
    touch = [t for t in _list(wm.get("touchstones")) if isinstance(t, dict)]
    adv_rows = min(12, max(6, len(advs), len(flaws)))
    touch_rows = min(6, max(2, len(touch)))
    overflow = _v5_overflow(advs[adv_rows:], flaws[adv_rows:], touch[touch_rows:], [])
    y = _advantage_rows(sc, y, advs, flaws, adv_rows)

    y = sc.section("Trackers", y)
    (left, right), cw2 = _columns(sc, 2, gap=22)
    ty = y - 10
    crone = any(_s(f.get("id")) == "flaw:ghoul-crones-curse" for f in flaws)
    _health_willpower(sc, left, ty, wm, attrs, _n(attrs.get("stamina"), 0, 10) + 3 - (1 if crone else 0))
    if wm.get("humanity") is not None:
        _humanity_stains(sc, right, ty, cw2, wm)
    heal = ("Ghouls heal twice as fast as mortals, except fire (Players Guide p. 142). Fresh Blood from the "
            "vein heals one Aggravated level per Rouse Check the vampire makes, a turn each (p. 139).")
    hy = ty - (34 if wm.get("humanity") is not None else 0)
    for line in simpleSplit(heal, SERIF_ITALIC, 7.2, cw2):
        sc.text(right, hy, line, SERIF_ITALIC, 7.2)
        hy -= 8.6
    y = ty - 84

    y = _convictions(sc, y, touch, touch_rows)
    y = sc.section("Experience", y)
    y = _experience(sc, _obj(wm.get("experience")), sc.x0, y, sc.x1 - sc.x0)

    mf = _obj(ch.get("merits_flaws"))
    notes = "\n".join(p for p in (_s(mf.get("notes")),
                                  ("Specialties: " + "; ".join(other_spec)) if other_spec else "",
                                  *overflow) if p)
    cont = _background_notes(sc, y, _s(ch.get("background")), notes, 8.2)
    sc.footer(footer, 2, pages)
    _render_continuation(sc, cont, name, sub, footer, 3, pages, 8.2)
    return len(cont)


# ---------------------------------------------------------------------------------------------
# V5 Reference page(s): catalog descriptions (services/v5_catalog.py) of the sheet's clan, predator
# type, Discipline powers, rituals, ceremonies and formulae, Merits, Backgrounds and Flaws, and
# loresheets with the levels taken. Page text only, no fields. Names stay English (as in the
# books); descriptions in the requester's language, English when missing.

BOOK_SHORT = {"v5-corebook": "Corebook", "v5-players-guide": "Players Guide", "v5-companion": "Companion"}
RITUAL_KINDS = (("ritual", "rituals", "Rituals"), ("ceremony", "ceremonies", "Ceremonies"),
                ("formula", "formulae", "Formulae"))
REF_ITEMS = OVERFLOW_ITEMS  # powers / rituals looked up per sheet
REF_DESC_MAX = 2000
REF_SIZE, REF_LEADING, REF_INDENT = 8.4, 10.2, 9.0
REF_ENTRY_GAP, REF_SECTION_GAP, REF_GROUP_H = 3.0, 5.0, 13.0
REF_KEY_MAX = 200  # longer sheet text is never a catalog name or id


def _norm(s: Any) -> str:
    """Lookup key, as v5_catalog.find compares: case and runs of spaces ignored."""
    return " ".join(str(s).split()).lower()


def _names(e: Dict[str, Any]) -> List[str]:
    return [n for n in (e.get("id"), e.get("name"), *_list(e.get("aliases"))) if isinstance(n, str)]


def _index(entries: Any) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for e in _list(entries):
        if isinstance(e, dict):
            for n in _names(e):
                idx.setdefault(_norm(n), e)  # the first entry wins, as in find()
    return idx


def _lookup(idx: Dict[str, Any], *keys: Any) -> Any:
    """First match for the keys (id, name), then for them without a trailing '(…)' such as a level."""
    keys_ = [k for k in (_s(k) for k in keys) if 0 < len(k) <= REF_KEY_MAX]
    bare = [k[:k.rindex("(")].rstrip() for k in keys_ if k.endswith(")") and "(" in k]
    for k in keys_ + bare:
        hit = idx.get(_norm(k))
        if hit is not None:
            return hit
    return None


def _book_ref(books: Dict[str, str], book: Any, page: Any) -> str:
    """'Players Guide, p. 23' (short names as in the forge's bookRef)."""
    b = _s(book)
    label = BOOK_SHORT.get(b) or books.get(b) or b
    p = _n(page, 0, 100000)
    return f"{label}, p. {p}" if label and p else label


# Entries whose facts come from the Paradox wiki (catalog source "online") say so, as CC BY-SA asks.
WIKI_CREDIT = {"en": "facts from vtm.paradoxwikis.com (CC BY-SA)",
               "el": "στοιχεία από το vtm.paradoxwikis.com (CC BY-SA)"}


def _ref_entry(name: Any, e: Dict[str, Any], lang: str, books: Dict[str, str], *, book: Any = None,
               prefix: str = "", level: Any = None) -> Dict[str, Any]:
    d = e.get("desc")
    desc = _s(d.get(lang) or d.get("en")) if isinstance(d, dict) else ""
    credit = WIKI_CREDIT.get(lang, WIKI_CREDIT["en"]) if e.get("source") == "online" else ""
    return {"name": _cap(_s(name), MAX_LINE), "prefix": prefix, "level": _n(level, 0, 10),
            "desc": _cap(desc, REF_DESC_MAX), "ref": _book_ref(books, book or e.get("book"), e.get("page")),
            "credit": credit}


def v5_reference(ch: Dict[str, Any], catalog: Optional[Dict[str, Any]], lang: str = "en") -> List[Tuple[str, Any]]:
    """
    What the Reference page lists, in order: ('section', title), ('group', Discipline name) and
    ('entry', {name, prefix, level, desc, ref, credit}). Only names with a catalog match (id, name or alias);
    an empty list means no Reference page.
    """
    if not isinstance(catalog, dict):
        return []
    lang = _s(lang).lower()[:2] or "en"
    wm = _obj(ch.get("wod_meta"))
    books = {_s(b.get("book_id")): _s(b.get("title")) for b in _list(catalog.get("books")) if isinstance(b, dict)}
    out: List[Tuple[str, Any]] = []

    if wm.get("sheet_kind") == "ghoul":  # what the domitor's Retainers buy (core p. 194)
        retainers = next((a for a in _list(catalog.get("advantages"))
                          if isinstance(a, dict) and a.get("id") == "background:retainers"), None)
        if retainers:
            out += [("section", "Ghoul"), ("entry", _ref_entry(retainers.get("name"), retainers, lang, books))]
    clan = _lookup(_index(catalog.get("clans")), wm.get("clan_id"), wm.get("clan"))
    if clan:
        out += [("section", "Clan"), ("entry", _ref_entry(clan.get("name"), clan, lang, books))]
        for key, label in (("bane", "Bane"), ("compulsion", "Compulsion")):
            part = clan.get(key)
            if isinstance(part, dict) and _s(part.get("name")):
                out.append(("entry", _ref_entry(part.get("name"), part, lang, books,
                                                book=part.get("book") or clan.get("book"), prefix=label)))

    pred = _lookup(_index(catalog.get("predator_types")), wm.get("predator_id"), wm.get("predator_type"))
    if pred:
        out += [("section", "Predator Type"), ("entry", _ref_entry(pred.get("name"), pred, lang, books))]

    # powers: one index over every Discipline (power names are unique across them), grouped under the
    # catalog Discipline in the order the sheet first names it
    powers: Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]] = {}
    for d in _list(catalog.get("disciplines")):
        if isinstance(d, dict):
            for p in _list(d.get("powers")):
                if isinstance(p, dict):
                    for n in _names(p):
                        powers.setdefault(_norm(n), (d, p))
    groups: Dict[str, Tuple[str, List[Dict[str, Any]]]] = {}
    seen = set()
    wanted = [p for d in _list(wm.get("disciplines")) if isinstance(d, dict) for p in _list(d.get("powers"))]
    for p in wanted[:REF_ITEMS]:
        hit = _lookup(powers, *((p.get("id"), p.get("name")) if isinstance(p, dict) else (p,)))
        if hit is None or id(hit[1]) in seen:
            continue
        disc, power = hit
        seen.add(id(power))
        groups.setdefault(_s(disc.get("id")) or _s(disc.get("name")), (_s(disc.get("name")), []))[1].append(
            _ref_entry(power.get("name"), power, lang, books, level=power.get("level")))
    if groups:
        out.append(("section", "Discipline Powers"))
        for title, entries in groups.values():
            out.append(("group", title))
            out += [("entry", e) for e in entries]

    # rituals, ceremonies and formulae share wod_meta.rituals; a stated kind is searched first
    idx = {kind: _index(catalog.get(cat)) for kind, cat, _ in RITUAL_KINDS}
    found: Dict[str, List[Dict[str, Any]]] = {kind: [] for kind, _, _ in RITUAL_KINDS}
    for r in _list(wm.get("rituals"))[:REF_ITEMS]:
        keys = (r.get("id"), r.get("name")) if isinstance(r, dict) else (r,)
        stated = _s(r.get("kind")).lower() if isinstance(r, dict) else ""
        for kind in sorted(idx, key=lambda k: k != stated):
            e = _lookup(idx[kind], *keys)
            if e is not None:
                if id(e) not in seen:
                    seen.add(id(e))
                    found[kind].append(_ref_entry(e.get("name"), e, lang, books, level=e.get("level")))
                break
    for kind, _, title in RITUAL_KINDS:
        if found[kind]:
            out.append(("section", title))
            out += [("entry", e) for e in found[kind]]
    return out + _reference_advantages(wm, catalog, clan, lang, books, seen)


def _advantage_indexes(catalog: Dict[str, Any], prefer: str) -> Dict[bool, Dict[str, Dict[str, Any]]]:
    """{is_flaw: index} of advantages.json; a name shared by several entries ("Clan Curse") finds
    the `prefer` one ('caitiff' / 'thin_blood') first, then the plain one."""
    entries = [a for a in _list(catalog.get("advantages")) if isinstance(a, dict)]

    def rank(a: Dict[str, Any]) -> int:
        if prefer and a.get(prefer):
            return 0
        return 2 if a.get("caitiff") or a.get("thin_blood") else 1

    return {flaw: _index(sorted((a for a in entries if (a.get("kind") == "flaw") == flaw), key=rank))
            for flaw in (False, True)}


def _reference_advantages(wm: Dict[str, Any], catalog: Dict[str, Any], clan: Any, lang: str,
                          books: Dict[str, str], seen: set) -> List[Tuple[str, Any]]:
    """'Advantages' (Merits & Backgrounds, Flaws, thin-blood ones included) and 'Loresheets' (each
    sheet, then the levels the sheet took, prefixed with its name)."""
    clan = clan if isinstance(clan, dict) else {}
    special = "caitiff" if clan.get("caitiff") else "thin_blood" if clan.get("thin_blood") else ""
    adv_idx = _advantage_indexes(catalog, special)
    thin_idx = _advantage_indexes(catalog, "thin_blood")
    lore_idx = _index(catalog.get("loresheets"))
    groups: Dict[bool, List[Dict[str, Any]]] = {False: [], True: []}
    lore: List[Tuple[str, Any]] = []

    def add(flaw: bool, e: Any, prefix: str = "") -> None:
        if e is not None and id(e) not in seen:
            seen.add(id(e))
            groups[flaw].append(_ref_entry(e.get("name"), e, lang, books, prefix=prefix))

    rows = [(a, False) for a in _list(wm.get("advantages"))] + [(a, True) for a in _list(wm.get("flaws"))]
    for a, flaw in rows[:REF_ITEMS]:
        if not isinstance(a, dict) or a.get("custom"):
            continue
        keys = (a.get("id"), a.get("name"))
        is_lore = _s(a.get("kind")) == "loresheet" or _s(a.get("id")).startswith("loresheet:")
        e = None if is_lore else _lookup(adv_idx[flaw], *keys)
        if e is not None:
            add(flaw, e)
            continue
        ls = None if flaw else _lookup(lore_idx, *keys)  # an imported sheet may not say "loresheet"
        if ls is None or id(ls) in seen:
            continue
        seen.add(id(ls))
        name = _s(ls.get("name"))
        taken = {_n(x, 0, 10) for x in _list(a.get("levels"))}
        lore.append(("entry", _ref_entry(name, ls, lang, books, level=sum(t for t in taken if t))))
        for lv in _list(ls.get("levels")):
            if isinstance(lv, dict) and _n(lv.get("dots"), 0, 10) in taken - {0}:
                # the Anarch sheets: our sources give no English level names
                lv_name = lv.get("name") or f"Level {_n(lv.get('dots'), 0, 10)}"
                lore.append(("entry", _ref_entry(lv_name, lv, lang, books, prefix=name, level=lv.get("dots"))))
    for flaw, key in ((False, "thin_blood_merits"), (True, "thin_blood_flaws")):
        for n in _list(wm.get(key))[:REF_ITEMS]:
            add(flaw, _lookup(thin_idx[flaw], n.get("id") if isinstance(n, dict) else None,
                              n.get("name") if isinstance(n, dict) else n), prefix="Thin-blood")

    out: List[Tuple[str, Any]] = []
    if groups[False] or groups[True]:
        out.append(("section", "Advantages"))
        for flaw, title in ((False, "Merits & Backgrounds"), (True, "Flaws")):
            if groups[flaw]:
                out.append(("group", title))
                out += [("entry", e) for e in groups[flaw]]
    if lore:
        out += [("section", "Loresheets")] + lore
    return out


_REF_STYLE = ParagraphStyle("sr-reference", fontName=SERIF, fontSize=REF_SIZE, leading=REF_LEADING,
                            leftIndent=REF_INDENT, firstLineIndent=-REF_INDENT)


def _ref_paragraph(e: Dict[str, Any]) -> Paragraph:
    """'NAME •• — description (Book, p. N)': name in Cinzel, level as dots, the reference in italic."""
    esc = _xml_escape
    parts = []
    if e["prefix"]:
        parts.append(f'<font name="{SERIF_ITALIC}">{esc(e["prefix"])}:</font> ')
    parts.append(f'<font name="{CINZEL_BOLD}" size="{REF_SIZE - 1:g}">{esc(e["name"])}</font>')
    if e["level"]:
        parts.append(" " + "•" * e["level"])
    if e["desc"]:
        parts.append(" — " + esc(e["desc"]))
    if e["ref"]:
        parts.append(f' <font name="{SERIF_ITALIC}">({esc(e["ref"])})</font>')
    if e.get("credit"):
        parts.append(f' <font name="{SERIF_ITALIC}">· {esc(e["credit"])}</font>')
    return Paragraph("".join(parts), _REF_STYLE)


RefPage = List[Tuple[str, Any, float, float]]


def _flow_reference(sc: SheetCanvas, queue: List[Tuple[str, Any, bool]], bottom: float, section: str = "",
                    group: str = "", limit: int = 0) -> Optional[Tuple[List[RefPage], List[tuple]]]:
    """
    Flow (kind, obj, carried) items down two columns per page, from under the small header to
    `bottom`: pages of (kind, obj, x, y_top), and per page what was left when it began
    (items, section, group) so it can be flowed again. Headings keep two lines of text with them;
    an entry that doesn't fit splits across columns; a section carried onto a new page repeats its
    title. With a page `limit`, None when the items need more pages or overfill a column.
    """
    cols, cw = _columns(sc, 2, gap=22)
    top = sc.top - SMALL_HEADER_H
    queue = list(queue)
    pages: List[RefPage] = []
    starts: List[tuple] = []
    at = {"col": 1, "y": bottom, "empty": True}

    def next_frame() -> bool:
        """Next column; True when it starts a new page."""
        new_page = at["col"] == 1
        if new_page:
            pages.append([])
        at.update(col=0 if new_page else 1, y=top, empty=True)
        return new_page

    def height(kind: str, obj: Any, empty: bool) -> float:
        if kind == "section":
            return 15 + (0 if empty else REF_SECTION_GAP)
        if kind == "group":
            return REF_GROUP_H + (0 if empty else 2)
        return obj.wrap(cw, 10 ** 6)[1] + REF_ENTRY_GAP

    next_frame()
    i = 0
    while i < len(queue):
        kind, obj, cont = queue[i]
        room = at["y"] - bottom
        h = height(kind, obj, at["empty"])
        need = h
        if kind != "entry":  # keep a heading with what follows it
            j = i + 1
            if j < len(queue) and queue[j][0] == "group":
                need += REF_GROUP_H + 2
                j += 1
            if j < len(queue) and queue[j][0] == "entry":
                need += 2 * REF_LEADING
        if need > room:
            if kind == "entry" and room - REF_ENTRY_GAP >= 2 * REF_LEADING:
                parts = obj.split(cw, room - REF_ENTRY_GAP)
                if len(parts) == 2:
                    queue[i:i + 1] = [("entry", parts[0], cont), ("entry", parts[1], True)]
                    continue
            if not at["empty"]:
                if limit and at["col"] == 1 and len(pages) >= limit:
                    return None
                if next_frame() and kind != "section" and section:
                    carry = [("section", f"{section} (cont.)", True)]
                    if group and kind != "group":
                        carry.append(("group", group, True))
                    queue[i:i] = carry
                continue
            if limit and h > room:
                return None
            # otherwise an empty column takes it anyway: nothing would fit better
        if not pages[-1]:
            starts.append((queue[i:], section, group))
        y = at["y"] - (0 if at["empty"] or kind == "entry" else (REF_SECTION_GAP if kind == "section" else 2))
        pages[-1].append((kind, obj, cols[at["col"]], y))
        at.update(y=at["y"] - h, empty=False)
        if not cont:
            if kind == "section":
                section, group = obj, ""
            elif kind == "group":
                group = obj
        i += 1
    return pages, starts


def _layout_reference(sc: SheetCanvas, items: List[Tuple[str, Any]]) -> List[RefPage]:
    """Reference pages for v5_reference() items; the last page's two columns are balanced."""
    if not items:
        return []
    queue = [(k, _ref_paragraph(o) if k == "entry" else o, False) for k, o in items]
    pages, starts = _flow_reference(sc, queue, sc.bottom)
    rest, section, group = starts[-1]
    top = sc.top - SMALL_HEADER_H
    lo, hi, last = 0.0, top - sc.bottom, pages[-1]
    while hi - lo > 2:  # the shortest columns that still hold the last page
        mid = (lo + hi) / 2
        trial = _flow_reference(sc, rest, top - mid, section, group, limit=1)
        if trial:
            hi, last = mid, trial[0][0]
        else:
            lo = mid
    return pages[:-1] + [last]


def _render_reference(sc: SheetCanvas, ch: Dict[str, Any], chronicle: str, pages: List[RefPage], first: int,
                      total: int) -> None:
    name = _s(ch.get("name"))
    wm = _obj(ch.get("wod_meta"))
    if wm.get("sheet_kind") == "ghoul":
        domitor = _ghoul_domitor_name(ch, _obj(wm.get("ghoul")))
        sub = " · ".join(p for p in (f"Ghoul of {domitor}" if domitor else "Ghoul", chronicle) if p)
        footer = _ghoul_footer(name, domitor, chronicle)
    else:
        sub = " · ".join(p for p in (_s(wm.get("clan")), chronicle) if p)
        footer = f"{name} · {chronicle}" if chronicle else name
    _, cw = _columns(sc, 2, gap=22)
    for k, placed in enumerate(pages):
        sc.page()
        sc.frame()
        _small_header(sc, name, sub, sc.top, right="Reference")
        for kind, obj, x, y in placed:
            if kind == "section":
                sc.section(obj, y, x0=x, x1=x + cw)
            elif kind == "group":
                sc.text(x, y - 9.5, obj, SERIF_ITALIC, 9.5)
                sc.hline(x, x + cw, y - 12, w=0.3, dash=(0.6, 1.8))
            else:  # wrapped again: the balancing trials may have wrapped it last (same width, same lines)
                obj.drawOn(sc.c, x, y - obj.wrap(cw, 10 ** 6)[1])
        sc._ink()
        sc.footer(footer, first + k, total)


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


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _classic_domitor_text(ch: Dict[str, Any], g: Dict[str, Any]) -> str:
    """'Theodore Doukas (Ventrue, 12th)': GET's resolved `domitor`, else what the sheet stored."""
    dom = ch.get("domitor") if isinstance(ch.get("domitor"), dict) else {}
    stored = _obj(g.get("domitor"))
    name = _s(dom.get("name")) or _s(stored.get("name"))
    clan = _s(dom.get("clan")) or _s(stored.get("clan"))
    gen = dom.get("generation") if dom.get("generation") is not None else stored.get("generation")
    gen_text = _ordinal(gen) if isinstance(gen, int) and not isinstance(gen, bool) and 3 <= gen <= 15 else ""
    extra = ", ".join(p for p in (clan, gen_text) if p)
    return f"{name} ({extra})" if name and extra else name or extra


def _classic_kind_text(g: Dict[str, Any]) -> str:
    """'Vassal' / 'Independent' / 'Revenant: Zantosa'."""
    kind = _s(g.get("kind"))
    family = _s(g.get("family")) if kind == "revenant" else ""
    return f"{kind_label(kind)}: {family}" if family else kind_label(kind)


def _classic_bond_text(g: Dict[str, Any]) -> str:
    """'3/3 drinks · Third drink in 1994' (a Classic ghoul's Blood Bond to its domitor)."""
    bond = _obj(g.get("bond"))
    stage = bond.get("stage")
    head = f"{_n(stage, 0, BLOOD_BOND_DRINKS)}/{BLOOD_BOND_DRINKS} drinks" if stage not in (None, "") else ""
    return " · ".join(p for p in (head, _s(bond.get("note"))) if p)


def _potence_first(discs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """A ghoul's Disciplines with Potence on the first line, as the 1997 ghoul sheet prints it."""
    pot = [d for d in discs if _s(d.get("name")).lower() == "potence"]
    rest = [d for d in discs if _s(d.get("name")).lower() != "potence"]
    return (pot[:1] or [{"name": "Potence", "dots": 1}]) + pot[1:] + rest


def _render_classic(sc: SheetCanvas, ch: Dict[str, Any], chronicle: str, player: str, pages: int = 2) -> int:
    """The two Classic sheet pages and any continuation pages (returns how many). A Classic ghoul
    (vampire line, wod_meta.sheet_kind 'ghoul') gets the 1997 ghoul sheet's page 1: Domitor /
    Duties / Kind, Potence first, a Blood Pool of 10, Blood Bond and Overdosing? lines."""
    line = _s(ch.get("system_type")).lower()
    line = line if line in LINE_TITLES else "vampire"
    wm0 = _obj(ch.get("wod_meta"))
    wm = {**wm0, **_obj(wm0.get("vampire"))} if isinstance(wm0.get("vampire"), dict) else wm0
    attrs = _obj(ch.get("attributes"))
    sk = _obj(ch.get("skills"))
    name = _s(ch.get("name"))
    g = _obj(wm0.get("ghoul")) if line == "vampire" and wm0.get("sheet_kind") == "ghoul" else None
    title, sub = ("Ghoul", "Vampire: The Masquerade · Revised") if g is not None else LINE_TITLES[line]

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
    if g is not None:
        third = [("Domitor", "ghoul.domitor", _classic_domitor_text(ch, g)),
                 ("Duties", "ghoul.duties", g.get("duties")), ("Kind", "ghoul.kind", _classic_kind_text(g))]
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
        if g is not None:
            discs = _potence_first(discs)
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
    if g is not None:
        # a ghoul's Blood Pool: 10 (one row), 1 point per turn (Fatal Addiction); more only for old ghouls
        pool = ghoul_pool(wm)
        mx, per_turn, cur_b = pool["max"], pool["per_turn"], pool["current"]
        sc.text(x + cw / 2, yy, "Blood Pool", SERIF_ITALIC, 8.6, "center")
        bw = SheetCanvas.dots_width(10)
        nrows = 2 if mx > 10 else 1
        for r in range(nrows):
            sc.dots(f"blood.r{r + 1}", x + (cw - bw) / 2, yy - 12 - r * 10, 0, n=10, mark="fill",
                    shape="square", solid=max(0, min(10, mx - r * 10)),
                    checked=[r * 10 + j < cur_b for j in range(10)])
        by = yy - 38 + (2 - nrows) * 10
        sc.label(x + (cw - bw) / 2, by, "Per turn", size=6.5)
        sc.field("blood.per_turn", x + (cw - bw) / 2 + 42, by - 3, 24, 11, str(per_turn), size=8.6, align="center")
        sc.label(x + (cw - bw) / 2 + 76, by, "Max", size=6.5)
        sc.field("blood.max", x + (cw - bw) / 2 + 96, by - 3, 24, 11, str(mx), size=8.6, align="center")
        yy = by - 14
    elif line == "vampire":
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
    if g is not None:
        # the 1997 ghoul sheet's "Weakness/Blood Bond" and "Overdosing?" lines (13 pt each, so
        # Experience stays above the band's last row)
        lw = max(pdfmetrics.stringWidth(t.upper(), CINZEL, 7) for t in ("Blood Bond", "Overdosing?")) + 4
        sc.label(x, hy, "Blood Bond", size=7)
        sc.field("bond", x + lw, hy - 3, cw - lw, 12, _classic_bond_text(g), size=8.4,
                 tooltip="Drinks of the domitor's vitae: the third binds (Blood Bond)")
        hy -= 13
        sc.label(x, hy, "Overdosing?", size=7)
        sc.field("overdosing", x + lw, hy - 3, cw - lw, 12, g.get("overdosing"), size=8.4,
                 tooltip="One extra point per dot of Stamina; Stamina roll, difficulty 8 (Fatal Addiction)")
        hy -= 13
    elif line == "vampire":
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
    footer = f"{name} · {chronicle}" if chronicle else name
    if g is not None:
        footer = _ghoul_footer(name, _ghoul_domitor_name(ch, g), chronicle)
    sc.footer(footer, 1, pages)
    sc.page()

    # ---- page 2: rituals, XP log, background, notes
    sc.frame()
    sub = " · ".join(p for p in (_s(wm.get("clan") or wm.get("tribe") or wm.get("tradition")), chronicle) if p)
    y = _small_header(sc, name, sub, sc.top)
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
    if g is not None:  # a ghoul: its ages are in wod_meta.ghoul, and it was ghouled, not Embraced
        desc = tuple(("Ghouled", "ghouled_since") if k == "rip" else (lbl, k) for lbl, k in desc)
    dcols, dcw = _columns(sc, 4, gap=12)
    for i, (lbl, key) in enumerate(desc):
        x = dcols[i % 4]
        base = y - 10 - (i // 4) * 15
        lw = pdfmetrics.stringWidth(lbl.upper(), CINZEL, 6.6) + 4
        val = wm.get(key)
        if g is not None and key in ("age", "apparent_age", "ghouled_since") and _s(g.get(key)):
            val = g.get(key)
        sc.label(x, base, lbl, size=6.6)
        sc.field(f"desc.{key}", x + lw, base - 2.5, dcw - lw, 12, val, size=8.6)
    y -= 10 + 15 + 10

    y = sc.section("Possessions", y)
    third_box = {"vampire": ("Feeding Grounds", "feeding_grounds"), "werewolf": ("Fetishes", "fetishes"),
                 "mage": ("Wonders", "wonders")}[line]
    texts = {}
    if g is not None:  # a ghoul's feeding on its domitor's vitae (wod_meta.ghoul.feeding)
        third_box = ("Feeding", "feeding")
        fd = ghoul_feeding(g)
        last, fnote = _s(fd.get("last")), _s(fd.get("note"))
        texts["feeding"] = "\n".join(p for p in (f"Last fed: {last}" if last else "", fnote) if p)
    pcols, pcw = _columns(sc, 3, gap=12)
    for x, (lbl, key) in zip(pcols, (("Gear", "equipment"), third_box, ("Havens", "havens"))):
        _notes_box(sc, f"poss.{key}", lbl, x, y, pcw, 66, texts.get(key, _s(wm.get(key))))
    y -= 70
    if log:
        y = sc.section("Experience Log", y)
        sc.rect(sc.x0, y - 60, sc.x1 - sc.x0, 60)
        sc.field("xp.log", sc.x0, y - 60, sc.x1 - sc.x0, 60, log, size=7.8, multiline=True, underline=False)
        y -= 66
    notes = "\n".join(p for p in (_s(mf.get("notes")), _s(sk.get("notes")), *overflow) if p)
    cont = _background_notes(sc, y, _s(ch.get("background")), notes, 8.4)
    sc.footer(footer, 2, pages)
    _render_continuation(sc, cont, name, sub, footer, 3, pages, 8.4)
    return len(cont)


# ---------------------------------------------------------------------------------------------


def build_sheet_pdf(character: Dict[str, Any], *, paper: str = "a4", chronicle_name: str = "",
                    player_name: str = "", catalog: Optional[Dict[str, Any]] = None, lang: str = "en",
                    flat: bool = False) -> bytes:
    """
    Fillable two-page PDF for a character dict (as returned by GET /api/characters/<id>; a ghoul's
    sheet, wod_meta.sheet_kind 'ghoul', gets the ghoul pages: V5's own, or the Classic sheet's
    ghoul page 1). A Background or Notes too long for
    its box goes on over 'Background & Notes (continued)' page(s) after those two. A V5 sheet given
    the rules catalog (v5_catalog.load_catalog()) gets Reference page(s) last when anything on it
    matches, with descriptions in `lang` ('en' / 'el', English when missing). flat=True is the print
    version: the same pages with every value drawn as page text and no form fields.
    """
    ch = dict(character or {})
    name = _s(ch.get("name")) or "Character"
    edition = _s(ch.get("rules_edition")).lower()
    if not edition:
        edition = "v5" if _s(_obj(ch.get("wod_meta")).get("edition")).lower() == "v5" else "classic"
    chronicle = _s(chronicle_name or ch.get("campaign_name"))
    ghoul = edition == "v5" and _obj(ch.get("wod_meta")).get("sheet_kind") == "ghoul"
    items = v5_reference(ch, catalog, lang) if edition == "v5" and catalog else []

    def build(cont: int) -> Tuple[SheetCanvas, int]:
        sc = SheetCanvas(paper if paper in PAPER else "a4", title=name, author=_s(player_name), flat=flat)
        ref = _layout_reference(sc, items)
        total = 2 + cont + len(ref)
        if edition != "v5":
            drawn = _render_classic(sc, ch, chronicle, _s(player_name), pages=total)
        else:
            drawn = (_render_v5_ghoul if ghoul else _render_v5)(sc, ch, chronicle, _s(player_name), pages=total)
        if ref:
            _render_reference(sc, ch, chronicle, ref, 3 + drawn, total)
        return sc, drawn

    # Background & Notes continuation pages are known once page 2 is laid out: with any, the
    # sheet is drawn again so every footer counts them (only long texts pay for that)
    sc, drawn = build(0)
    if drawn:
        sc, _ = build(drawn)
    return sc.finish()


def safe_filename(name: str, fallback: str = "character") -> str:
    """'Κωνσταντίνος / X' -> 'Κωνσταντίνος X' (letters, digits, space, - _ . only)."""
    s = re.sub(r"[^\w\- .]+", " ", str(name or ""), flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return (s or fallback)[:80]
