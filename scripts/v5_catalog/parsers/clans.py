"""Clans: in-clan Disciplines, where the Bane is printed, the Compulsion name, PG bane variants.

Which printed pages hold each clan block comes from the Forge v2 book inventory (section 1);
the parser only looks inside those spans. Inside a span it reads the "Disciplines" section
(paragraphs that start with "<Discipline>:"), the page of the "Bane" heading and, where the
block has one, the "Compulsion: <name>" heading. The corebook prints the seven original
Compulsions in a separate list ("Brujah: Rebellion", pr 210-211), parsed by `parse_compulsions`.
"""

from __future__ import annotations

import re

from ..sources.base import Line
from . import common as c

CLAN_SPANS = {
    "v5-corebook": {
        "Brujah": (65, 68), "Gangrel": (69, 73), "Malkavian": (75, 79), "Nosferatu": (81, 85),
        "Toreador": (87, 91), "Tremere": (93, 97), "Ventrue": (99, 102), "Caitiff": (105, 107),
        "Thin-blood": (109, 113),
    },
    "v5-players-guide": {
        "Banu Haqim": (17, 21), "Hecata": (22, 28), "Lasombra": (29, 34), "Ministry": (35, 40),
        "Ravnos": (41, 45), "Salubri": (46, 51), "Tzimisce": (52, 55),
    },
    "v5-companion": {"Ravnos": (6, 11), "Salubri": (12, 15), "Tzimisce": (16, 23)},
}
CLANS = ("Banu Haqim", "Brujah", "Gangrel", "Hecata", "Lasombra", "Malkavian", "Ministry",
         "Nosferatu", "Ravnos", "Salubri", "Toreador", "Tremere", "Tzimisce", "Ventrue",
         "Caitiff", "Thin-blood")
_CLAN_KEY = {n.lower(): n for n in CLANS}
_CLAN_KEY.update({"the ministry": "Ministry", "thin-blood": "Thin-blood", "thin-bloods": "Thin-blood"})


def _heading(ln: Line, minimum: float = 16.0) -> bool:
    return (ln.height or 0) >= minimum


def parse_block(clan: str, lines: list[Line]) -> tuple[dict, list[str]]:
    report: list[str] = []
    rec = {"id": f"clan:{c.slug(clan)}", "name": clan, "source": "pdf",
           "book": lines[0].book if lines else None,
           "page": lines[0].page if lines else None,
           "disciplines": [], "disciplines_page": None, "bane_page": None,
           "compulsion": None, "compulsion_page": None}
    mode = None
    for i, ln in enumerate(lines):
        t = c.norm_space(ln.text)
        low = t.lower()
        if _heading(ln) and low == "disciplines":
            mode = "disc"
            rec["disciplines_page"] = ln.page
            continue
        if _heading(ln) and low == "bane":
            mode = None
            rec["bane_page"] = ln.page
            continue
        m = re.match(r"(?i)^compulsion:\s*(.*)$", t)
        if m and (ln.height or 0) >= 13.5:
            name = m.group(1).strip()
            j = i + 1
            # the name may continue on the next heading line(s) ("COMPULSION: AFFECTIVE" / "EMPATHY")
            while j < len(lines) and lines[j].height == ln.height \
                    and re.fullmatch(r"[A-Za-z' -]+", c.norm_space(lines[j].text)):
                name = f"{name} {c.norm_space(lines[j].text)}".strip()
                j += 1
            rec["compulsion"] = c.title_case(name)
            rec["compulsion_page"] = ln.page
            mode = None
            continue
        if _heading(ln) and mode == "disc":
            mode = None
        if mode == "disc":
            m = re.match(r"^([A-Za-z -]+?):", c.strip_bullet(t))
            if m and m.group(1).strip().lower() in c.DISCIPLINE_BY_KEY:
                d = c.DISCIPLINE_BY_KEY[m.group(1).strip().lower()]
                if d not in rec["disciplines"]:
                    rec["disciplines"].append(d)
    if clan not in ("Caitiff", "Thin-blood") and len(rec["disciplines"]) != 3:
        report.append(f"- {clan} ({rec['book']}): found {len(rec['disciplines'])} Disciplines "
                      f"{rec['disciplines']}, expected 3")
    if rec["bane_page"] is None:
        report.append(f"- {clan} ({rec['book']}): no Bane heading found in pages "
                      f"{CLAN_SPANS[rec['book']][clan]}")
    return rec, report


def parse_compulsions(lines: list[Line]) -> dict:
    """Corebook 'Clan Compulsions': '<Clan>: <Compulsion>' headings -> {clan: (name, page)}."""
    out = {}
    for ln in lines:
        m = re.match(r"^([A-Za-z -]+):\s*([A-Za-z' -]+)$", c.norm_space(ln.text))
        if m and (ln.height or 0) >= 16 and m.group(1).strip().lower() in _CLAN_KEY:
            out[_CLAN_KEY[m.group(1).strip().lower()]] = (c.title_case(m.group(2)), ln.page)
    return out


def parse_bane_variants(lines: list[Line]) -> tuple[dict, list[str]]:
    """PG pr 56-59 'Clan Bane Variants': '<Clan>: <Variant>' headings -> {clan: [{name, page}]}.

    One heading line can hold two variants side by side ('Toreador: X Tzimisce: Y'), and a
    heading can wrap ('Malkavian:' / 'Unnatural Manifestations').
    """
    out: dict = {}
    report: list[str] = []
    pending = None
    clan_alt = "|".join(sorted((re.escape(k) for k in _CLAN_KEY), key=len, reverse=True))
    pat = re.compile(rf"(?i)\b({clan_alt}):\s*(.*?)(?=\s+(?:{clan_alt}):|$)")
    for ln in lines:
        if (ln.height or 0) < 25:
            continue
        t = c.norm_space(ln.text)
        if pending:
            out.setdefault(pending[0], []).append({"name": c.title_case(t), "page": pending[1]})
            pending = None
            continue
        for m in pat.finditer(t):
            clan = _CLAN_KEY[m.group(1).lower()]
            name = m.group(2).strip()
            if not name:
                pending = (clan, ln.page)
            else:
                out.setdefault(clan, []).append({"name": c.title_case(name), "page": ln.page})
    return out, report
