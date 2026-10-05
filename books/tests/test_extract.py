"""Extraction on synthetic PDFs: columns, running heads, page numbers, kinds, outline."""
from conftest import book

from rbimport.extract import column_starts, extract_book, order_page


def _col(x, y0, prefix, n, font="tiro", size=10, step=13):
    return [(x, y0 + i * step, f"{prefix} line n{i} goes here and on.", font, size) for i in range(n)]


def _texts(res):
    return " ".join(b["text"] for b in res["blocks"])


def test_column_starts_two_and_three():
    two = [dict(x0=50 + d, x1=250) for d in (0, 0, 5, 0)] + [dict(x0=320, x1=560) for _ in range(4)]
    assert column_starts(two, 612) == [50, 320]
    three = [dict(x0=x, x1=x + 150) for x in (40,) * 4 + (230,) * 4 + (420,) * 4]
    assert column_starts(three, 612) == [40, 230, 420]


def test_order_page_full_width_band_first():
    lines = [dict(x0=320, y0=200, x1=560, y1=210, text="right"), dict(x0=50, y0=200, x1=290, y1=210, text="left"),
             dict(x0=50, y0=100, x1=560, y1=115, text="title"), dict(x0=50, y0=214, x1=290, y1=224, text="left2"),
             dict(x0=320, y0=214, x1=560, y1=224, text="right2"), dict(x0=50, y0=228, x1=290, y1=238, text="left3"),
             dict(x0=320, y0=228, x1=560, y1=238, text="right3")]
    assert [l["text"] for l in order_page(lines, 612)] == ["title", "left", "left2", "left3", "right", "right2", "right3"]


def test_two_columns_running_heads_and_page_numbers(mk):
    pages = []
    for p in range(6):
        items = [(250, 30, "RUNNING HEAD", "tiro", 9), (300, 775, str(p + 11), "tiro", 9)]
        items += _col(50, 100, f"Left{p}", 12) + _col(330, 100, f"Right{p}", 12)
        pages.append(items)
    res = extract_book(mk(pages), book())
    text = _texts(res)
    assert res["status"] == "ok"
    assert "RUNNING HEAD" not in text
    assert " 11 " not in f" {text} "
    # reading order: whole left column, then the right column, page after page
    assert text.index("Left0 line n11") < text.index("Right0 line n0") < text.index("Left1 line n0")
    assert res["page_numbers"].startswith("footer offset +10")
    assert {b["page"] - b["page_pdf"] for b in res["blocks"]} == {10}


def test_three_columns(mk):
    items = _col(40, 100, "A", 10) + _col(230, 100, "B", 10) + _col(420, 100, "C", 10)
    res = extract_book(mk([items]), book())
    t = _texts(res)
    assert t.index("A line n9") < t.index("B line n0") < t.index("B line n9") < t.index("C line n0")


def test_dehyphenation_across_lines(mk):
    items = [(50, 100, "The vampire must make an impor-", "tiro", 10), (50, 113, "tant choice tonight.", "tiro", 10)]
    items += _col(50, 200, "Filler", 4)
    res = extract_book(mk([items]), book())
    assert "important choice" in _texts(res)


def test_kinds_fiction_example_sidebar(mk):
    items = _col(50, 80, "Body", 3)
    items += [(50, 130 + i * 13, f"She ran through the night {i} and on.", "tiit", 10) for i in range(5)]
    items += [(50, 220, "EXAMPLE:", "tibo", 10), (50, 233, "John rolls five dice and wins.", "tiro", 10)]
    items += [(50, 270 + i * 13, f"Sidebar rule text {i} goes on.", "helv", 10) for i in range(3)]
    res = extract_book(mk([items]), book(sidebar_fonts=["Helvetica"]))
    kinds = {}
    for b in res["blocks"]:
        kinds.setdefault(b["kind"], []).append(b["text"])
    assert any("She ran through the night 0" in t for t in kinds["fiction"])
    assert any(t.startswith("EXAMPLE: John rolls") for t in kinds["example"])
    assert any("Sidebar rule text 0" in t for t in kinds["sidebar"])
    assert all("Sidebar" not in t for t in kinds["body"])


def test_short_italic_run_is_body(mk):
    items = _col(50, 80, "Body", 3) + [(50, 130, "an italic aside", "tiit", 10)]
    res = extract_book(mk([items]), book())
    assert not [b for b in res["blocks"] if b["kind"] == "fiction"]


def test_outline_sections_and_typo_fix(mk):
    p1 = [(50, 80, "Chapter One", "tibo", 16)] + _col(50, 110, "Intro", 4)
    p1 += [(50, 200, "Clan Venture", "tibo", 12)] + _col(50, 220, "Ventrue", 4)
    p2 = [(50, 80, "Combat", "tibo", 16)] + _col(50, 110, "Fight", 4)
    toc = [[1, "Chapter One", 1], [2, "Clan Venture", 1], [1, "Combat", 2]]
    res = extract_book(mk([p1, p2], toc), book(toc_fixes={"Venture": "Ventrue"}))
    secs = {s["title"]: s for s in res["sections"]}
    assert secs["Clan Ventrue"]["path"] == ["Chapter One", "Clan Ventrue"]
    by_sec = {}
    for b in res["blocks"]:
        if b["kind"] != "heading":
            by_sec.setdefault(b["section"], []).append(b["text"])
    assert "Ventrue line n0" in " ".join(by_sec[secs["Clan Ventrue"]["id"]])
    assert "Intro line n0" in " ".join(by_sec[secs["Chapter One"]["id"]])
    assert "Fight line n0" in " ".join(by_sec[secs["Combat"]["id"]])
    # Combat starts at the top of page 2, so Chapter One ends on page 1
    assert secs["Chapter One"]["page_end_pdf"] == 1 and secs["Combat"]["leaf"]


def test_font_size_headings_without_outline(mk):
    p1 = [(50, 80, "Big Chapter", "tibo", 18)] + _col(50, 110, "One", 4) + [(50, 180, "Small Section", "tibo", 14)] + _col(50, 200, "Two", 4)
    p2 = [(50, 80, "Second Chapter", "tibo", 18)] + _col(50, 110, "Three", 4) + [(50, 180, "Other Section", "tibo", 14)] + _col(50, 200, "Four", 4)
    res = extract_book(mk([p1, p2]), book())
    assert res["outline"] == "font sizes"
    paths = [s["path"] for s in res["sections"]]
    assert ["Big Chapter", "Small Section"] in paths and ["Second Chapter", "Other Section"] in paths


def test_strip_lines_and_page_range(mk):
    pages = [[(50, 60, "file:///D|/x.htm (1 of 3)", "helv", 9)] + _col(50, 100, f"P{p}", 4) for p in range(4)]
    res = extract_book(mk(pages), book(strip_lines=[r"^file:///"], exclude="3-4"))
    t = _texts(res)
    assert "file:///" not in t and "P2 line" not in t and "P1 line" in t
    assert res["pages_used"] == 2


def test_image_only_detected(mk):
    res = extract_book(mk([[(50, 100, "x", "tiro", 10)]] * 3), book())
    assert res["status"] == "image-only"
