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
    """The printed restriction as fields the forge can check:
    '(Ventrue characters only)', 'Bloodline; Hecata characters only', 'Brujah Only',
    'Salubri or Tremere Only', 'Tremere and Banu Haqim only' -> clans_only;
    'Thin-blooded characters only' -> thin_blood_only; 'Thin-Blood Alchemists Only' -> also
    disciplines_only Thin-Blood Alchemy; 'Blood Sorcery Users Only' -> disciplines_only;
    'Unavailable to Nosferatu characters' -> clans_excluded (only present when printed)."""
    out = {"clans_only": None, "disciplines_only": None, "thin_blood_only": False}
    if not text:
        return out
    low = c.norm_space(text).lower()
    m = re.search(r"unavailable to ([a-z ,]+?) characters", low)
    if m:
        names = [x.strip() for x in re.split(r",| and | or ", m.group(1)) if x.strip()]
        if names and all(n in CLAN_WORDS for n in names):
            out["clans_excluded"] = [f"clan:{c.slug(n)}" for n in names]
        return out
    if "thin-blood" in low:
        out["thin_blood_only"] = True
        if "alchemist" in low:
            out["disciplines_only"] = ["discipline:thin-blood-alchemy"]
        return out
    if re.search(r"blood sorcery users? only", low):
        out["disciplines_only"] = ["discipline:blood-sorcery"]
        return out
    part = low.split(";")[-1]
    part = re.sub(r"\b(?:the|characters?|only|bloodline)\b", " ", part)
    names = [x.strip() for x in re.split(r",| and | or ", part) if x.strip()]
    if names and all(n in CLAN_WORDS for n in names):
        out["clans_only"] = [f"clan:{c.slug(n)}" for n in names]
    return out


_LEVEL_RESTRICTION = re.compile(r"^(?P<name>.+?)\s*\((?P<r>[^()]*\bonly)\)$", re.I)


def split_level_restriction(name: str) -> tuple[str, str | None]:
    """'Perception is Power (Banu Haqim characters only)' -> ('Perception is Power',
    'Banu Haqim characters only'): a restriction printed on one level, not the whole sheet."""
    m = _LEVEL_RESTRICTION.match(name)
    return (m.group("name").strip(), m.group("r").strip()) if m else (name, None)


def parse(pages: list[list[Line]], level_heights: set | None = None) -> tuple[list[dict], list[str]]:
    out, report = [], []
    for lines in pages:
        rec, rep = parse_page(lines, level_heights)
        report += rep
        if rec:
            out.append(rec)
    return out, report


# --------------------------------------------------------------------------- Tier-2 pages (boxes)
#
# The supplements print a sheet per page in one of two ways:
#   glyph books   the rating is a run of "•" either at the start of the level's name line
#                 ("•••• Relic Hound: …") or as a box of its own on the same baseline, left of
#                 the name box ("•••" at x 256, "A Taste So Sweet: …" at x 276);
#   no-glyph books the dots are drawn as graphics (Camarilla, Fall of London, Gehenna War, the
#                 L.A. by Night and Choice of Games handouts), laid out like the corebook: each dot
#                 pushes the name right by DOT_WIDTH from its column's left edge.
# Titles and restrictions are letter-spaced in most supplements ("BA NK ERS OF DU NSIR N"), so the
# parser keeps them only as a check: the build compares them, spaces removed, with the names in
# manual/loresheets.json "sheets" (which restore the word spacing) and reports any difference.

_GLYPH_RUN = re.compile(r"^([•●]{1,5})\s*(.*)$")
NAME_MAX = 60


def _is_title(b: dict) -> bool:
    """A sheet title: large type near the top of the page. A one-letter title (L.A. by Night's
    "X") is told from a drop cap by its size: drop caps are 55-90 pt tall, titles 35-45 pt."""
    n = len(despace(b["t"]))
    return b["h"] >= 30 and b["y"] < 260 and (n > 1 or (n == 1 and b["h"] <= 50 and b["y"] < 120))


def _bt(b: dict) -> str:
    return c.norm_space(b["t"].replace("­", ""))


def despace(s: str | None) -> str:
    """Letters and digits only, upper case: compares a letter-spaced heading with a name."""
    return re.sub(r"[^A-Z0-9]", "", (s or "").replace("’", "'").upper())


def _name_from(boxes: list[dict], start: dict, text: str) -> str | None:
    """The level name in `text` (up to the colon). A name without a colon on its line wraps:
    join the next line of the same column (the first box below it within 20 pt whose x is
    within 45 pt left of the name and not right of it by more than 2)."""
    q = re.match(r"^([^:?]{2,40}\?)\s", text)
    if ":" in text:
        name = text.split(":", 1)[0].strip()
    elif q:  # "Giorgio Who? You've ..." (a name that ends in a question mark, no colon)
        name = q.group(1).strip()
    else:
        below = [b for b in boxes if 4 < b["y"] - start["y"] <= 20 and -45 <= b["x"] - start["x"] <= 2
                 and not re.fullmatch(r"[•●]{1,5}", _bt(b))]
        if not below:
            return None
        nxt = _bt(min(below, key=lambda b: (b["y"], -b["x"])))
        joined = c.join_wrapped(text, nxt) if text.endswith("-") else f"{text} {nxt}"
        if ":" not in joined or nxt.find(":") > 30:
            return None
        name = joined.split(":", 1)[0].strip()
    if not name or len(name) > NAME_MAX or not re.match(r"^[^\w]{0,3}[A-Z0-9]", name):
        return None
    return name


def _anchors(boxes: list[dict], min_lines: int = 4, merge: float = 30.0) -> list[float]:
    counts: dict[int, int] = {}
    for b in boxes:
        counts[round(b["x"])] = counts.get(round(b["x"]), 0) + 1
    out: list[float] = []
    for x in sorted(k for k, n in counts.items() if n >= min_lines):
        if not out or x - out[-1] > merge:
            out.append(float(x))
    return out


def parse_boxes(boxes: list[dict], book: str, page: int, glyphs: bool) -> tuple[dict | None, list[str]]:
    """One supplement page (poppler boxes {t, x, y, h}) -> {title_raw, restriction_raw, levels}.
    Levels whose rating cannot be read are left out and reported (never guessed)."""
    from ..sources.pdf import is_noise

    report: list[str] = []
    boxes = [b for b in boxes if b["t"].strip() and not is_noise(b["t"], b["h"])]
    titles = sorted((b for b in boxes if _is_title(b)), key=lambda b: b["y"])
    if not titles:
        return None, report
    title = " ".join(_bt(t) for t in titles)
    restriction = None
    for b in sorted(boxes, key=lambda b: b["y"]):
        t = _bt(b)
        if b["y"] < titles[-1]["y"] + 90 and re.fullmatch(r"\(.+\)", t):
            restriction = t[1:-1].strip()
            break
    lore_y = min((b["y"] for b in boxes if despace(b["t"]) in ("LORE", "LORES")), default=0.0)
    body = [b for b in boxes if b["y"] > lore_y]
    found: dict[int, list[str]] = {}
    if glyphs:
        for b in body:
            m = _GLYPH_RUN.match(_bt(b))
            if not m:
                continue
            dots, rest, start = len(m.group(1)), m.group(2), b
            if not rest:
                right = [o for o in body if o is not b and abs(o["y"] - b["y"]) <= 2.0 and 0 < o["x"] - b["x"] <= 40]
                if not right:
                    continue
                start = min(right, key=lambda o: o["x"])
                rest = _bt(start)
            name = _name_from(body, start, rest)
            if name:
                found.setdefault(dots, []).append(name)
    else:
        # the name's indent from its column's body text gives the rating; the 4-dot graphic is
        # wider in some books (Camarilla: +36 pt, not +32), so when a page has exactly five names
        # whose indents grow in reading order, they are dots 1-5 in that order
        anchors = _anchors(body, min_lines=3)
        cands = []
        for b in body:
            left = [i for i, a in enumerate(anchors) if a <= b["x"] + 0.5 and b["x"] - a < 45]
            if not left:
                continue
            col = max(left)
            off = b["x"] - anchors[col]
            if not 6.0 <= off <= 45.0:
                continue
            name = _name_from(body, b, _bt(b))
            if name:
                cands.append((col, b["y"], off, name))
        cands.sort()
        offs = [x[2] for x in cands]
        if len(cands) == 5 and all(offs[i] < offs[i + 1] for i in range(4)):
            for i, x in enumerate(cands):
                found.setdefault(i + 1, []).append(x[3])
        else:
            for _col, _y, off, name in cands:
                dots = round(off / DOT_WIDTH)
                if 1 <= dots <= 5 and abs(off - dots * DOT_WIDTH) <= 2.5:
                    found.setdefault(dots, []).append(name)
    levels = {}
    for d in sorted(found):
        names = list(dict.fromkeys(found[d]))
        if len(names) > 1:
            report.append(f"- {book} p.{page}: two names for rating {d}: {names}")
            continue
        levels[d] = names[0]
    if sorted(levels) != [1, 2, 3, 4, 5]:
        report.append(f"- {book} p.{page} ({title!r}): ratings found {sorted(levels)} (expected 1-5)")
    return {
        "book": book, "page": page, "title_raw": title, "restriction_raw": restriction, "source": "pdf",
        "levels": [{"dots": d, "name": levels[d]} for d in sorted(levels)],
    }, report


def _page_title(boxes: list[dict]) -> str | None:
    from ..sources.pdf import is_noise

    t = [b for b in boxes if _is_title(b) and not is_noise(b["t"], b["h"])]
    return " ".join(_bt(b) for b in sorted(t, key=lambda b: b["y"])) if t else None


def parse_book(pages: list[tuple[int, list[dict]]], book: str, glyphs: bool) -> tuple[list[dict], list[str]]:
    """A book's loresheet pages -> one record per sheet. A page without a title, or whose title
    says CONTINUED, is the rest of the sheet before it (its boxes are appended below that sheet's,
    shifted down by 1000 pt per page so the geometry stays per page)."""
    groups: list[dict] = []
    for page, boxes in pages:
        title = _page_title(boxes)
        if groups and (title is None or "CONTINUED" in despace(title)):
            g = groups[-1]
            g["shift"] += 1000.0
            g["boxes"] += [dict(b, y=b["y"] + g["shift"]) for b in boxes]
            g["pages"].append(page)
        elif title is not None:
            groups.append({"page": page, "pages": [page], "boxes": list(boxes), "shift": 0.0})
    out, report = [], []
    for g in groups:
        rec, rep = parse_boxes(g["boxes"], book, g["page"], glyphs)
        report += rep
        if rec:
            if len(g["pages"]) > 1:
                rec["pages"] = g["pages"]
            out.append(rec)
    return out, report
