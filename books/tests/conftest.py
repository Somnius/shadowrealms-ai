"""Tests for the rule-book importer. All PDFs are synthetic (generated with PyMuPDF here);
no book text is used."""
import os
import sys

import pytest

BOOKS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BOOKS not in sys.path:
    sys.path.insert(0, BOOKS)

W, H = 612, 792


def make_pdf(path, pages, toc=None):
    """pages: list of pages, each a list of (x, y, text, font, size). font: PyMuPDF base-14 short
    names: tiro (Times-Roman), tibo (bold), tiit (italic), helv (Helvetica)."""
    import pymupdf
    doc = pymupdf.open()
    for items in pages:
        page = doc.new_page(width=W, height=H)
        for x, y, text, font, size in items:
            page.insert_text((x, y), text, fontname=font, fontsize=size)
    if toc:
        doc.set_toc(toc)
    doc.save(path)
    doc.close()
    return str(path)


def book(**kw):
    b = {"book_id": "test-book", "path": "x.pdf", "title": "Test Book", "edition": "classic", "line": "vampire",
         "version": "revised", "kind": "rules", "precedence": 10, "year": 2000, "official": True}
    b.update(kw)
    return b


@pytest.fixture
def mk(tmp_path):
    def _mk(pages, toc=None, name="t.pdf"):
        return make_pdf(tmp_path / name, pages, toc)
    return _mk
