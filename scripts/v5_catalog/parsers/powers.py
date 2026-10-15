"""Discipline powers, Blood Sorcery rituals, Oblivion ceremonies and Thin-Blood Alchemy formulae.

All four share one layout in the Tier-1 books: a big section heading (the Discipline, or
"Rituals" / "Blood Sorcery Rituals" / "Oblivion Ceremonies" / "Thin-Blood Alchemy"), then
"Level N" headings (PG: "Level N Rituals", "Level N Formulae"), then entries. An entry is a
title line in the book's title style (corebook and Companion: lower-case small caps; Players
Guide: capitals), optionally followed by "Amalgam:" / "Prerequisite:" lines, then body text
with labelled lines (Cost, Dice Pools, System, Duration, Ingredients, ...).

A title is accepted only when a labelled line (Cost / System / Ingredients / Duration /
Dice Pool / Process) follows it before the next title; everything else is left in the report.
Title heights are learned per book from the lines that directly follow a "Level N" heading,
so sidebars set in a different size are not taken for entries.
"""

from __future__ import annotations

import re
from collections import Counter

from ..sources.base import Line
from . import common as c

SECTION_MIN_HEIGHT = 24.0
LEVEL_RE = re.compile(r"^Level ([1-5])(?: (?:Rituals?|Formulae|Ceremonies))?$", re.I)
# supplements also print "Level 1 Power", "Level 4 Powers", "Level 2 Ceremony", "Level 1 Formula"
SUPPLEMENT_LEVEL_RE = re.compile(r"^Level ([1-5])(?: (?:Rituals?|Formulae|Formulas?|Ceremony|Ceremonies|Powers?))?$", re.I)
CONFIRM = {"cost", "system", "ingredients", "duration", "dice_pool", "process"}

# section heading text (lower case, letter-spacing collapsed) -> (kind, discipline)
SECTIONS = {d.lower(): ("power", d) for d in c.DISCIPLINES}
SECTIONS.update({
    "rituals": ("ritual", "Blood Sorcery"),
    "blood sorcery rituals": ("ritual", "Blood Sorcery"),
    "oblivion ceremonies": ("ceremony", "Oblivion"),
    "thin-blood alchemy": ("formula", "Thin-Blood Alchemy"),
    "thin-blood": ("formula", "Thin-Blood Alchemy"),
})
# extra section headings the supplements print (supplement mode only, so Tier-1 parsing is unchanged)
SUPPLEMENT_SECTIONS = {
    "new blood sorcery rituals": ("ritual", "Blood Sorcery"),
    "blood sorcery ritual": ("ritual", "Blood Sorcery"),
    "blood sorcery rituals": ("ritual", "Blood Sorcery"),
    "koldunic sorcery": ("ritual", "Blood Sorcery"),
    "oblivion ceremony": ("ceremony", "Oblivion"),
    "oblivion ceremonies": ("ceremony", "Oblivion"),
    "ceremonies": ("ceremony", "Oblivion"),
    "new thin-blood alchemy formulae": ("formula", "Thin-Blood Alchemy"),
    "thin-blood alchemy formulae": ("formula", "Thin-Blood Alchemy"),
    "thin-blood alchemy formula": ("formula", "Thin-Blood Alchemy"),
    "formulae": ("formula", "Thin-Blood Alchemy"),
    "new rituals": ("ritual", "Blood Sorcery"),
    "new ritual": ("ritual", "Blood Sorcery"),
}
_SPACED_CAP = re.compile(r"(?<![A-Za-z'])([A-Z]) (?=[a-z])")


def fix_spaced_caps(text: str) -> str:
    """Small caps set as a capital plus the rest ('H aruspex', 'T racing the B lood') -> joined;
    a possessive glued to the next word ('Predator’sLure') -> split."""
    return re.sub(r"([’'])s(?=[A-Z])", r"\1s ", _SPACED_CAP.sub(r"\1", text))


def _label_text(text: str) -> str:
    """'S ystem : On a win' -> 'System: On a win' (Blood Sigils sets its labels this way)."""
    return re.sub(r"^(\W*[A-Za-z][A-Za-z ]{1,30}?)\s+:", r"\1:", fix_spaced_caps(text))


def _supplement_name(text: str) -> bool:
    """Supplement titles are often Title Case; the Tier-1 rule (one case) is relaxed."""
    t = c.norm_space(c.strip_bullet(fix_spaced_caps(text)))
    if not (2 <= len(t) <= 48) or ":" in t or not c._NAME_RE.match(t):
        return False
    return c.looks_like_name(t) or t[0].isupper()


def _prereq_goes_on(prev: str, nxt: str) -> bool:
    """Supplement prerequisites wrap: an open bracket ('Necrotic Plague (Players'), a next line
    that starts with 'or'/'and', or a short next line after a capitalised word ('… or Oblivion’s'
    / 'Sight'). Body text lines are long, so they are not taken."""
    if prev.count("(") > prev.count(")"):
        return True
    if re.match(r"(?:or|and)\b", nxt) or re.search(r"\((?:Players Guide|Vampire|Cults|Chicago)", nxt):
        return True
    last = prev.split()[-1] if prev.split() else ""
    return len(nxt) <= 22 and last[:1].isupper() and not prev.rstrip().endswith((".", ")"))


# a few headings in the ranges that are titles of sidebars or rules, never entries
NOT_ENTRIES = {"characteristics", "general rules", "amalgam powers", "wards", "ingredients",
               "distillation methods", "example", "examples"}


def _is_heading(line: Line, body: float) -> bool:
    return (line.height or 0) >= SECTION_MIN_HEIGHT and (line.height or 0) > body * 1.6


def body_heights(lines: list[Line]) -> dict:
    """Most common line height per page = body text height."""
    per: dict = {}
    for ln in lines:
        per.setdefault(ln.page, Counter())[ln.height] += 1
    return {p: cnt.most_common(1)[0][0] for p, cnt in per.items()}


def title_heights(lines: list[Line], name_ok=c.looks_like_name, level_re=LEVEL_RE) -> set:
    """Heights of the lines right after a 'Level N' heading: the book's entry-title style."""
    out = set()
    for i, ln in enumerate(lines[:-1]):
        if level_re.match(ln.text.strip()) and name_ok(lines[i + 1].text):
            out.add(lines[i + 1].height)
    return out


def parse(lines: list[Line], supplement: bool = False, start: tuple | None = None,
          section_min: float = 18.0) -> tuple[list[dict], list[str]]:
    """-> (records, report lines).

    supplement=True (Tier-2 books): a section heading may be smaller (>= section_min) but must
    name a known section (a Discipline, rituals, ceremonies, formulae; two heading lines may be
    joined, "New Blood Sorcery" + "Rituals"); other large lines (sidebar titles, art captions)
    are skipped instead of ending the section; `start` = (kind, discipline) for a range that
    opens mid-section; Title Case titles and small caps set as "T racing the B lood" are read."""
    body = body_heights(lines)
    name_ok = _supplement_name if supplement else c.looks_like_name
    level_re = SUPPLEMENT_LEVEL_RE if supplement else LEVEL_RE
    titles = title_heights(lines, name_ok, level_re)
    sections = dict(SECTIONS, **SUPPLEMENT_SECTIONS) if supplement else SECTIONS
    report: list[str] = []
    records: list[dict] = []
    kind, discipline = start if start else (None, None)
    level = None
    cur: dict | None = None
    field: str | None = None
    i = 0

    def close():
        nonlocal cur
        if cur is None:
            return
        if not cur.pop("_confirmed", False):
            report.append(f"- dropped title without Cost/System/Duration lines: {cur['name']!r} "
                          f"({cur['book']} p.{cur['page']})")
        else:
            records.append(cur)
        cur = None

    while i < len(lines):
        ln = lines[i]
        text = ln.text.strip()
        low = c.norm_space(text).lower()
        h = ln.height or 0.0

        if supplement and h >= section_min and h > body.get(ln.page, 0) + 3 and not level_re.match(text):
            key, step = low, 1
            if key not in sections and i + 1 < len(lines) and (lines[i + 1].height or 0) >= section_min:
                key, step = f"{low} {c.norm_space(lines[i + 1].text).lower()}", 2
            if key in sections:
                close()
                kind, discipline = sections[key]
                level = None
                field = None
                i += step
                continue
            if h >= SECTION_MIN_HEIGHT:  # a big line that names no section: skip it
                i += 1
                continue

        if not supplement and _is_heading(ln, body.get(ln.page, 0)):
            key = low
            if key == "thin-blood" and i + 1 < len(lines) and lines[i + 1].text.strip().lower() == "alchemy":
                i += 1
            close()
            kind, discipline = SECTIONS.get(key, (None, None))
            level = None
            field = None
            i += 1
            continue

        m = level_re.match(text)
        if m and h > body.get(ln.page, 0) + 2:
            close()
            level = int(m.group(1))
            field = None
            i += 1
            continue

        if kind and level and h in titles and name_ok(text) and low not in NOT_ENTRIES:
            # merge a title broken over several lines (same height, nothing in between)
            parts = [fix_spaced_caps(text) if supplement else text]
            j = i + 1
            while j < len(lines) and name_ok(lines[j].text) \
                    and (lines[j].height == h
                         or (c.norm_space(parts[-1]).endswith("-") and lines[j].height in titles)) \
                    and not c.label(lines[j].text) and lines[j].page == ln.page:
                parts.append(fix_spaced_caps(lines[j].text.strip()) if supplement else lines[j].text.strip())
                j += 1
            name = ""
            for p in parts:
                p = c.norm_space(p)
                if name.endswith("-"):
                    name = name[:-1].rstrip() + p
                else:
                    name = f"{name} {p}".strip()
            close()
            name = c.title_case(name)
            cur = {
                "kind": kind, "name": name, "discipline": discipline, "level": level,
                "source": "pdf", "book": ln.book, "page": ln.page, "page_pdf": ln.page_pdf,
                "amalgam": None, "prerequisite_text": None, "cost_text": None,
                "rouse_cost": None, "dice_pool_text": None, "dice_pool": None,
                "snippet": "", "_confirmed": False,
            }
            field = "head"
            i = j
            continue

        if not c.strip_bullet(text):
            i += 1
            continue

        if kind and level and h not in titles and abs(h - body.get(ln.page, 0)) > 0.3 \
                and name_ok(text) and low not in NOT_ENTRIES:
            ahead = [c.label(_label_text(x.text) if supplement else x.text) for x in lines[i + 1:i + 7]]
            if any(a and a[0] in CONFIRM for a in ahead):
                report.append(f"- possible entry title in another type size, not taken: {text!r} "
                              f"({ln.book} p.{ln.page}, height {h})")

        if cur is not None:
            lab = c.label(_label_text(text) if supplement else text)
            if lab:
                key, rest = lab
                field = key
                if key in CONFIRM:
                    cur["_confirmed"] = True
                if key == "amalgam":
                    cur["amalgam_text"] = rest
                elif key == "prerequisite":
                    cur["prerequisite_text"] = rest
                elif key == "cost" and cur["cost_text"] is None:
                    cur["cost_text"] = rest
                elif key == "dice_pool" and cur["dice_pool_text"] is None:
                    cur["dice_pool_text"] = rest
                else:
                    field = key if key in ("amalgam", "prerequisite") else "other"
            else:
                t = c.strip_bullet(text)
                if field == "amalgam" and not re.search(r"\d\s*$", cur.get("amalgam_text") or ""):
                    cur["amalgam_text"] = f"{cur.get('amalgam_text', '')} {t}".strip()
                elif field == "prerequisite" and (
                        re.search(r"(?:\bor|\band|\beither|\bof|\bthe|,|-)$", cur["prerequisite_text"] or "")
                        or (supplement and _prereq_goes_on(cur["prerequisite_text"] or "", t))):
                    prev = cur["prerequisite_text"]
                    cur["prerequisite_text"] = prev[:-1] + t if prev.endswith("-") else f"{prev} {t}"
                    if supplement:
                        field = "prerequisite"  # it may wrap more than once
                        i += 1
                        continue
                elif field == "cost":
                    cur["cost_text"] = c.join_wrapped(cur["cost_text"], t)
                elif field == "dice_pool":
                    cur["dice_pool_text"] = c.join_wrapped(cur["dice_pool_text"], t)
                if len(cur["snippet"]) < 200:
                    cur["snippet"] = f"{cur['snippet']} {t}".strip()[:200]
                if field in ("head", "amalgam", "prerequisite"):
                    field = "body"
        i += 1
    close()

    for r in records:
        r["amalgam"] = parse_amalgam(r.pop("amalgam_text", None), report, r)
        r["rouse_cost"], r["rouse_cost_conditional"] = c.rouse_cost(r["cost_text"])
        r["dice_pool"] = c.dice_pool(r["dice_pool_text"])
        if r["kind"] == "power":
            r["id"] = c.power_id(r["discipline"], r["name"])
        else:
            r["id"] = f"{r['kind']}:{c.slug(r['name'])}"
        r["confidence"] = 0.9
    return records, report


def parse_amalgam(text: str | None, report: list[str], rec: dict) -> dict | None:
    if not text:
        return None
    m = re.fullmatch(r"\s*([A-Za-z][A-Za-z -]*?)\s*([1-5])\s*\.?\s*", text)
    if m and m.group(1).strip().lower() in c.DISCIPLINE_BY_KEY:
        return {"discipline": c.DISCIPLINE_BY_KEY[m.group(1).strip().lower()], "level": int(m.group(2))}
    report.append(f"- amalgam not parsed for {rec['name']!r} ({rec['book']} p.{rec['page']}): {text!r}")
    rec["amalgam_unparsed"] = text
    return None


def section_pages(lines: list[Line]) -> list[dict]:
    """Where each Discipline / rituals / ceremonies / formulae section starts."""
    body = body_heights(lines)
    out = []
    for i, ln in enumerate(lines):
        if not _is_heading(ln, body.get(ln.page, 0)):
            continue
        key = c.norm_space(ln.text).lower()
        if key == "thin-blood" and i + 1 < len(lines) and lines[i + 1].text.strip().lower() == "alchemy":
            key = "thin-blood alchemy"
        if key in SECTIONS:
            kind, discipline = SECTIONS[key]
            out.append({"kind": kind, "discipline": discipline, "book": ln.book, "page": ln.page})
    return out
