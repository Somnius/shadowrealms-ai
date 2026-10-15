"""Loresheets: one sheet per printed page in the Tier-1 ranges (core pr 382-406, PG pr 223-229).

Per page: the title (the large type line), the restriction in brackets under it when printed
("(Ventrue characters only)", "(Bloodline; Hecata characters only)"), and the five level names.

Level names are the bold "Name:" lines. The Players Guide prints the rating as dot glyphs in
the text; the corebook draws its dots as graphics with no text, so the rating is read from
geometry: each dot pushes the name right by DOT_WIDTH points from the column's left edge
(checked on the rendered corebook pr 383: 1..5 dots = +8..+40 pt). A sheet whose ratings are
not exactly 1-5 once each is reported, never guessed.
"""

from __future__ import annotations

import re

from ..sources.base import Line
from . import common as c

DOT_WIDTH = 8.0
TITLE_MIN_HEIGHT = 35.0
_LEVEL = re.compile(r"^(?P<dots>[•●]{1,5})?\s*(?P<name>[A-Z][^:]{1,48}?):")
CLAN_WORDS = {"banu haqim", "brujah", "gangrel", "hecata", "lasombra", "malkavian", "ministry",
              "nosferatu", "ravnos", "salubri", "toreador", "tremere", "tzimisce", "ventrue"}


def _column_anchor(x: float, body: list[Line]) -> float | None:
    left = [b.x for b in body if b.x is not None and b.x <= x + 0.5 and x - b.x < 50]
    return min(left) if left else None


def parse_page(lines: list[Line], level_heights: set | None = None) -> tuple[dict | None, list[str]]:
    report: list[str] = []
    titles = [ln for ln in lines if (ln.height or 0) >= TITLE_MIN_HEIGHT and len(ln.text.strip()) > 2]
    if not titles:
        return None, report
    title = " ".join(c.norm_space(t.text) for t in titles)
    page = titles[0].page
    restriction = None
    for ln in lines:
        m = re.fullmatch(r"\((.+)\)", c.norm_space(ln.text))
        if m and "only" in m.group(1).lower():
            restriction = m.group(1)
            break
    body_h = {}
    for ln in lines:
        body_h[ln.height] = body_h.get(ln.height, 0) + 1
    body = [ln for ln in lines if ln.height == max(body_h, key=body_h.get)]
    levels = {}
    skip = set()
    for i, ln in enumerate(lines):
        if i in skip:
            continue
        text = c.norm_space(ln.text.replace("\u00ad", ""))
        m = _LEVEL.match(text)
        if not m and i + 1 < len(lines) and ":" not in text and len(text) <= 40 \
                and (level_heights is None or ln.height in level_heights):
            # a name wrapped before its colon ("Where the Bodies Are" / "Buried: ...")
            nxt = c.norm_space(lines[i + 1].text.replace("\u00ad", ""))
            joined = c.join_wrapped(text, nxt) if text.endswith("-") else f"{text} {nxt}"
            m2 = _LEVEL.match(joined)
            if m2 and len(m2.group("name")) <= 48 and nxt.find(":") <= 25 \
                    and not re.search("[\u2022\u25cf]", joined):
                m = m2
                skip.add(i + 1)
        if not m:
            continue
        name = m.group("name").strip()
        if m.group("dots"):
            dots = len(m.group("dots"))
        else:
            if level_heights is not None and ln.height not in level_heights:
                continue
            anchor = _column_anchor(ln.x or 0, body)
            if anchor is None:
                continue
            dots = round(((ln.x or 0) - anchor) / DOT_WIDTH)
            if not 1 <= dots <= 5 or abs((ln.x - anchor) - dots * DOT_WIDTH) > 2.5:
                continue
        if dots in levels:
            report.append(f"- loresheet {title!r} p.{page}: two names for rating {dots}: "
                          f"{levels[dots]!r} and {name!r}")
            continue
        levels[dots] = name
    rec = {
        "id": f"loresheet:{c.slug(title)}", "name": c.title_case(title), "source": "pdf",
        "book": lines[0].book, "page": page, "restriction": restriction,
        "levels": [{"dots": d, "name": levels[d]} for d in sorted(levels)],
    }
    if sorted(levels) != [1, 2, 3, 4, 5]:
        report.append(f"- loresheet {title!r} p.{page}: ratings found {sorted(levels)} (expected 1-5)")
    rec.update(structured_restriction(restriction))
    return rec, report


def structured_restriction(text: str | None) -> dict:
    """'(Ventrue characters only)' -> clans_only; 'Bloodline; Hecata characters only' too."""
    out = {"clans_only": None, "disciplines_only": None, "thin_blood_only": False}
    if not text:
        return out
    low = text.lower()
    m = re.search(r"([a-z ,]+?) characters only", low)
    if m:
        part = m.group(1).split(";")[-1].strip()
        names = [x.strip() for x in re.split(r",| and ", part) if x.strip()]
        if names and all(n in CLAN_WORDS for n in names):
            out["clans_only"] = [f"clan:{c.slug(n)}" for n in names]
    if "thin-blood" in low:
        out["thin_blood_only"] = True
    return out


def parse(pages: list[list[Line]], level_heights: set | None = None) -> tuple[list[dict], list[str]]:
    out, report = [], []
    for lines in pages:
        rec, rep = parse_page(lines, level_heights)
        report += rep
        if rec:
            out.append(rec)
    return out, report
