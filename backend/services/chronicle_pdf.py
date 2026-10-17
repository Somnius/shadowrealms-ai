"""
"The chronicle so far" as a PDF in the character sheet's look (docs/CHRONICLE.md): black ink on
white, the sheet's frame, sigil, section rule, footer and fonts (services/pdf_look.py), A4 or Letter.

The PDF is drawn from the same Markdown the .md export gives (chronicle_digest.story_markdown or
minutes_markdown, built from the stored digest and chapter JSON), or from the Storyteller's edit
copy. Only a small part of Markdown is read: headings (#, ##, ###), paragraphs, "- " lists,
**bold**, _italic_ and backslash escapes. Everything else is printed as text: no markup, link or
image in the text ever becomes one in the PDF. The one link is the footer's, to the app's page on
lefteros.com in the file's language. The Storyteller-only part ("## Storyteller only") starts on a
new page. No model name, server or version goes in the file; the producer is "ShadowRealms AI".
"""

from __future__ import annotations

import io
import re
import unicodedata
from typing import List, Optional, Tuple
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import BaseDocTemplate, CondPageBreak, Flowable, Frame, PageBreak, PageTemplate, Paragraph, Spacer

from services import chronicle_digest as cd
from services.pdf_look import (
    CINZEL_BOLD,
    PAPER,
    SERIF,
    SERIF_ITALIC,
    draw_footer,
    draw_frame,
    draw_section,
    draw_sigil,
    ensure_fonts,
)

MAX_CHARS = 400_000  # an edit copy longer than this is cut (the box allows less)
M = 24.0              # frame distance from the paper's edge (as the sheet)


def _caps(text: str) -> Tuple[str, str]:
    """(font, text) for a section rule: Cinzel when the heading has no Greek (Cinzel has none),
    else EB Garamond in capitals without accents, as Greek capitals are written."""
    if not any(cd._is_greek(c) for c in text):
        return CINZEL_BOLD, text.upper()
    plain = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return SERIF, unicodedata.normalize("NFC", plain.upper())


# ---------------------------------------------------------------------------------------------
# Markdown, the small part we write

def inline(text: str) -> str:
    """One line of our Markdown as reportlab paragraph markup. Escapes are honoured, ** and _ toggle
    bold and italic, and everything else (including any < or &) is escaped text. Tags always close in
    order: crossed marks (**a _b** c_) close the inner tag and open it again."""
    out: List[str] = []
    stack: List[str] = []

    def toggle(tag):
        if tag in stack:
            inner = stack[stack.index(tag) + 1:]
            for t in reversed(inner):
                out.append(f"</{t}>")
            out.append(f"</{tag}>")
            stack.remove(tag)
            for t in inner:
                out.append(f"<{t}>")
        else:
            out.append(f"<{tag}>")
            stack.append(tag)

    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            out.append(escape(text[i + 1]))
            i += 2
            continue
        if text.startswith("**", i):
            toggle("b")
            i += 2
            continue
        ital = "i" in stack
        if ch == "_" and (ital or i == 0 or not text[i - 1].isalnum()) and (not ital or i + 1 >= n or not text[i + 1].isalnum()):
            toggle("i")
            i += 1
            continue
        out.append(escape(ch))
        i += 1
    for t in reversed(stack):
        out.append(f"</{t}>")
    return "".join(out)


def _para(md_text: str, style, **kw) -> Paragraph:
    """A Paragraph of our Markdown; if reportlab still refuses the markup, the escaped plain text."""
    try:
        return Paragraph(inline(md_text), style, **kw)
    except ValueError:
        return Paragraph(escape(plain(md_text)), style, **kw)


def blocks(markdown: str) -> List[Tuple[str, str]]:
    """[(kind, text)]: kind is h1, h2, h3, p or li; text is still Markdown. A rule (---) is dropped."""
    out: List[Tuple[str, str]] = []
    para: List[str] = []

    def flush():
        if para:
            out.append(("p", " ".join(para)))
            para.clear()

    for raw in str(markdown or "")[:MAX_CHARS].splitlines():
        line = raw.strip()
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if not line:
            flush()
        elif m:
            flush()
            level = min(len(m.group(1)), 3)
            out.append((f"h{level}", m.group(2).strip()))
        elif re.match(r"^(-{3,}|\*{3,}|_{3,})$", line):
            flush()
        elif re.match(r"^[-*+]\s+", line):
            flush()
            out.append(("li", re.sub(r"^[-*+]\s+", "", line)))
        elif out and out[-1][0] == "li" and raw.startswith(("  ", "\t")) and not para:
            out[-1] = ("li", out[-1][1] + " " + line)
        else:
            para.append(line)
    flush()
    return out


def plain(md_text: str) -> str:
    """A Markdown line as plain text (escapes and emphasis marks removed)."""
    return re.sub(r"<[^>]*>", "", inline(md_text)).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


# ---------------------------------------------------------------------------------------------
# Flowables

class SectionRule(Flowable):
    """The sheet's section heading: a centred title between hairlines ending in diamonds."""

    def __init__(self, title: str, fill=None, stroke=None):
        super().__init__()
        self.title = title
        self.fill, self.stroke = fill, stroke  # None: the sheet's black

    def wrap(self, aw, ah):
        self.width = aw
        return aw, 22

    def draw(self):
        font, text = _caps(self.title)
        if self.fill is not None:
            self.canv.setFillColor(self.fill)
            self.canv.setStrokeColor(self.stroke)
        draw_section(self.canv, text, 20, 0, self.width, size=10 if font == CINZEL_BOLD else 10.5, font=font)


def _styles(pal=None, accent=None):
    """pal: the horror look's palette (colour or print); accent: the sheet look's heading colour
    (None: black, the sheet as it always was)."""
    body = ParagraphStyle("sr-body", fontName=SERIF, fontSize=10.5, leading=14, spaceAfter=6)
    if pal is not None:
        BLOOD, INK = pal.heading, pal.ink

        body = ParagraphStyle("sr-hbody", fontName=SERIF, fontSize=10.5, leading=14.5, spaceAfter=6, textColor=INK)
        return {
            "h1": ParagraphStyle("sr-hh1", fontName=SERIF_BOLD, fontSize=20, leading=24, alignment=TA_CENTER,
                                 spaceAfter=12, textColor=BLOOD),
            "h3": ParagraphStyle("sr-hh3", fontName=SERIF_BOLD, fontSize=11.5, leading=15, spaceBefore=6, spaceAfter=4,
                                 textColor=BLOOD),
            "p": body,
            "li": ParagraphStyle("sr-hli", parent=body, leftIndent=12, bulletIndent=2, bulletFontName=SERIF,
                                 spaceAfter=3, bulletColor=BLOOD),
        }
    if accent is not None:
        return {
            "h1": ParagraphStyle("sr-ch1", fontName=SERIF, fontSize=20, leading=24, alignment=TA_CENTER, spaceAfter=10,
                                 textColor=accent),
            "h3": ParagraphStyle("sr-ch3", fontName=SERIF_ITALIC, fontSize=12, leading=15, spaceBefore=6, spaceAfter=4,
                                 textColor=accent),
            "p": body,
            "li": ParagraphStyle("sr-li", parent=body, leftIndent=12, bulletIndent=2, bulletFontName=SERIF, spaceAfter=3),
        }
    return {
        "h1": ParagraphStyle("sr-h1", fontName=SERIF, fontSize=20, leading=24, alignment=TA_CENTER, spaceAfter=10),
        "h3": ParagraphStyle("sr-h3", fontName=SERIF_ITALIC, fontSize=12, leading=15, spaceBefore=6, spaceAfter=4),
        "p": body,
        "li": ParagraphStyle("sr-li", parent=body, leftIndent=12, bulletIndent=2, bulletFontName=SERIF, spaceAfter=3),
    }


SERIF_BOLD = "SR-Garamond-Bold"  # EB Garamond Bold (static wght 700 from the OFL variable font); chronicle PDF only


def _register_family():
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    from services.pdf_look import FONT_DIR

    if SERIF_BOLD not in pdfmetrics.getRegisteredFontNames():
        import os

        pdfmetrics.registerFont(TTFont(SERIF_BOLD, os.path.join(FONT_DIR, "EBGaramond-Bold.ttf")))
    # one family; no bold italic file, so bold italic shows as bold. An italic style (SERIF_ITALIC)
    # maps back to (SERIF, italic), so <b> inside it is bold too.
    for bold, italic, face in ((1, 1, SERIF_BOLD), (0, 0, SERIF), (1, 0, SERIF_BOLD), (0, 1, SERIF_ITALIC)):
        addMapping(SERIF, bold, italic, face)


def flowables(markdown: str, st_heading: Optional[str] = None, pal=None, accent=None) -> List[Flowable]:
    st = _styles(pal, accent)
    rule = (pal.heading, pal.dark) if pal is not None else (accent, accent)
    out: List[Flowable] = []
    for kind, text in blocks(markdown):
        if kind == "h1":
            out.append(_para(text, st["h1"]))
        elif kind == "h2":
            if st_heading and plain(text).strip() == st_heading:
                out.append(PageBreak())  # the Storyteller-only part starts on its own page
            else:
                out.append(CondPageBreak(60))
                if out[:-1]:
                    out.append(Spacer(1, 8))
            out.append(SectionRule(plain(text), *rule))
        elif kind == "h3":
            out.append(CondPageBreak(40))
            out.append(_para(text, st["h3"]))
        elif kind == "li":
            out.append(_para(text, st["li"], bulletText="•"))
        else:
            out.append(_para(text, st["p"]))
    if not out:
        out.append(Spacer(1, 1))
    return out


# ---------------------------------------------------------------------------------------------
# The document

def _canvas_class(footer: str, link: str, title: str, look: str = "sheet", footer_color=None):
    class NumberedCanvas(rl_canvas.Canvas):
        """Pages are kept until the end, so each footer can say 'page / pages'."""

        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self._pages = []
            self.setTitle(title)
            self.setAuthor("ShadowRealms AI")
            self.setCreator("ShadowRealms AI")
            self.setProducer("ShadowRealms AI")
            self.setSubject(footer)

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            links = 0  # the saved page states each hold the old annotation count: keep names unique
            for i, state in enumerate(self._pages, 1):
                self.__dict__.update(state)
                self._annotationCount = max(links, getattr(self, "_annotationCount", 0))
                W, H = self._pagesize
                if look == "horror":
                    self.setFillColor(footer_color)
                    draw_footer(self, W, HM_FOOT, W - HM_FOOT - 18, footer, i, total, link=link)
                else:
                    draw_footer(self, W, M, W - M - 18, footer, i, total, link=link)
                links = self._annotationCount
                super().showPage()
            super().save()

    return NumberedCanvas


LOOKS = ("sheet", "horror")
COLORS = ("colour", "print")


def default_color(look: str) -> str:
    return "colour" if look == "horror" else "print"
# The horror look: text kept clear of the darkened edges, the frame, the corners and the blood.
HM_SIDE, HM_TOP_FIRST, HM_TOP, HM_BOTTOM, HM_FOOT = 70.0, 118.0, 74.0, 72.0, 34.0


def build_pdf(markdown: str, lang: str, paper: str = "a4", edited: bool = False, translated: bool = False,
              title: str = "", look: str = "sheet", color: Optional[str] = None) -> bytes:
    """The PDF of a story or minutes Markdown (its own footer line is replaced by the page footer).
    look is "sheet" (the default) or "horror" (stained paper and blood). color is "colour" or "print"
    (black and white, for home printers); the default is colour for horror and print for the sheet,
    and the sheet in print is exactly the sheet as it always was."""
    ensure_fonts()
    _register_family()
    W, H = PAPER.get(paper, PAPER["a4"])
    buf = io.BytesIO()
    color = color if color in COLORS else default_color(look)
    if look == "horror":
        return _build_horror(buf, markdown, lang, paper, W, H, edited, translated, title, color == "print")
    accent = None
    if color == "colour":
        from services.pdf_horror import BLOOD as accent
    x0, x1 = M + 30, W - M - 30
    top_first, top_later, bottom = H - M - 70, H - M - 40, M + 30

    def first(c, _doc):
        c.saveState()
        draw_frame(c, W, H, M)
        draw_sigil(c, W / 2, H - M - 36, 44, color=accent)
        c.restoreState()

    def later(c, _doc):
        c.saveState()
        draw_frame(c, W, H, M)
        draw_sigil(c, W / 2, H - M - 20, 24, color=accent)
        c.restoreState()

    doc = BaseDocTemplate(buf, pagesize=(W, H), leftMargin=x0, rightMargin=W - x1, topMargin=M, bottomMargin=bottom,
                          title=title, author="ShadowRealms AI", creator="ShadowRealms AI")
    doc.addPageTemplates([
        PageTemplate("first", [Frame(x0, bottom, x1 - x0, top_first - bottom, id="f1")], onPage=first,
                     autoNextPageTemplate="later"),
        PageTemplate("later", [Frame(x0, bottom, x1 - x0, top_later - bottom, id="f2")], onPage=later),
    ])
    body = cd.strip_footer(markdown)
    w = cd.words(lang)
    story = flowables(body, w["st_only"], accent=accent)
    footer = f"{cd.footer_text(lang, edited, translated)} · {cd.footer_link_text(lang)}"
    doc.build(story, canvasmaker=_canvas_class(footer, cd.footer_url(lang), title))
    return buf.getvalue()


def _build_horror(buf, markdown, lang, paper, W, H, edited, translated, title, print_mode=False) -> bytes:
    from services import pdf_horror

    pal = pdf_horror.PRINT if print_mode else pdf_horror.COLOUR

    x0, x1 = HM_SIDE, W - HM_SIDE
    bottom = HM_BOTTOM

    def on_page(c, doc):
        pdf_horror.draw_page(c, W, H, paper, doc.page, print_mode)

    doc = BaseDocTemplate(buf, pagesize=(W, H), leftMargin=x0, rightMargin=W - x1, topMargin=HM_TOP, bottomMargin=bottom,
                          title=title, author="ShadowRealms AI", creator="ShadowRealms AI")
    doc.addPageTemplates([
        PageTemplate("first", [Frame(x0, bottom, x1 - x0, H - HM_TOP_FIRST - bottom, id="h1")], onPage=on_page,
                     autoNextPageTemplate="later"),
        PageTemplate("later", [Frame(x0, bottom, x1 - x0, H - HM_TOP - bottom, id="h2")], onPage=on_page),
    ])
    body = cd.strip_footer(markdown)
    w = cd.words(lang)
    story = flowables(body, w["st_only"], pal=pal)
    footer = f"{cd.footer_text(lang, edited, translated)} · {cd.footer_link_text(lang)}"
    doc.build(story, canvasmaker=_canvas_class(footer, cd.footer_url(lang), title, look="horror", footer_color=pal.dark))
    return buf.getvalue()
