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
    bold and italic, and everything else (including any < or &) is escaped text."""
    out: List[str] = []
    bold = ital = False
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            out.append(escape(text[i + 1]))
            i += 2
            continue
        if text.startswith("**", i):
            out.append("</b>" if bold else "<b>")
            bold = not bold
            i += 2
            continue
        if ch == "_" and (ital or i == 0 or not text[i - 1].isalnum()) and (not ital or i + 1 >= n or not text[i + 1].isalnum()):
            out.append("</i>" if ital else "<i>")
            ital = not ital
            i += 1
            continue
        out.append(escape(ch))
        i += 1
    if ital:
        out.append("</i>")
    if bold:
        out.append("</b>")
    return "".join(out)


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

    def __init__(self, title: str):
        super().__init__()
        self.title = title

    def wrap(self, aw, ah):
        self.width = aw
        return aw, 22

    def draw(self):
        font, text = _caps(self.title)
        draw_section(self.canv, text, 20, 0, self.width, size=10 if font == CINZEL_BOLD else 10.5, font=font)


def _styles():
    body = ParagraphStyle("sr-body", fontName=SERIF, fontSize=10.5, leading=14, spaceAfter=6)
    return {
        "h1": ParagraphStyle("sr-h1", fontName=SERIF, fontSize=20, leading=24, alignment=TA_CENTER, spaceAfter=10),
        "h3": ParagraphStyle("sr-h3", fontName=SERIF_ITALIC, fontSize=12, leading=15, spaceBefore=6, spaceAfter=4),
        "p": body,
        "li": ParagraphStyle("sr-li", parent=body, leftIndent=12, bulletIndent=2, bulletFontName=SERIF, spaceAfter=3),
    }


def _register_family():
    from reportlab.lib.fonts import addMapping

    # EB Garamond has no bold file here: bold shows as the regular face (the sheet does the same)
    for bold, italic, face in ((0, 0, SERIF), (1, 0, SERIF), (0, 1, SERIF_ITALIC), (1, 1, SERIF_ITALIC)):
        addMapping(SERIF, bold, italic, face)
        addMapping(SERIF_ITALIC, bold, italic, SERIF_ITALIC)


def flowables(markdown: str, st_heading: Optional[str] = None) -> List[Flowable]:
    st = _styles()
    out: List[Flowable] = []
    for kind, text in blocks(markdown):
        if kind == "h1":
            out.append(Paragraph(inline(text), st["h1"]))
        elif kind == "h2":
            if st_heading and plain(text).strip() == st_heading:
                out.append(PageBreak())  # the Storyteller-only part starts on its own page
            else:
                out.append(CondPageBreak(60))
            out.append(SectionRule(plain(text)))
        elif kind == "h3":
            out.append(CondPageBreak(40))
            out.append(Paragraph(inline(text), st["h3"]))
        elif kind == "li":
            out.append(Paragraph(inline(text), st["li"], bulletText="•"))
        else:
            out.append(Paragraph(inline(text), st["p"]))
    if not out:
        out.append(Spacer(1, 1))
    return out


# ---------------------------------------------------------------------------------------------
# The document

def _canvas_class(footer: str, link: str, title: str):
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
                draw_footer(self, W, M, W - M - 18, footer, i, total, link=link)
                links = self._annotationCount
                super().showPage()
            super().save()

    return NumberedCanvas


def build_pdf(markdown: str, lang: str, paper: str = "a4", edited: bool = False, translated: bool = False,
              title: str = "") -> bytes:
    """The PDF of a story or minutes Markdown (its own footer line is replaced by the page footer)."""
    ensure_fonts()
    _register_family()
    W, H = PAPER.get(paper, PAPER["a4"])
    buf = io.BytesIO()
    x0, x1 = M + 30, W - M - 30
    top_first, top_later, bottom = H - M - 70, H - M - 40, M + 30

    def first(c, _doc):
        c.saveState()
        draw_frame(c, W, H, M)
        draw_sigil(c, W / 2, H - M - 36, 44)
        c.restoreState()

    def later(c, _doc):
        c.saveState()
        draw_frame(c, W, H, M)
        draw_sigil(c, W / 2, H - M - 20, 24)
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
    story = flowables(body, w["st_only"])
    footer = f"{cd.footer_text(lang, edited, translated)} · {cd.footer_url(lang)}"
    doc.build(story, canvasmaker=_canvas_class(footer, cd.footer_url(lang), title))
    return buf.getvalue()
