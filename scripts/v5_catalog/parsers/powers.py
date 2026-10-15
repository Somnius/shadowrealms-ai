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


def title_heights(lines: list[Line]) -> set:
    """Heights of the lines right after a 'Level N' heading: the book's entry-title style."""
    out = set()
    for i, ln in enumerate(lines[:-1]):
        if LEVEL_RE.match(ln.text.strip()) and c.looks_like_name(lines[i + 1].text):
            out.add(lines[i + 1].height)
    return out


def parse(lines: list[Line]) -> tuple[list[dict], list[str]]:
    """-> (records, report lines)."""
    body = body_heights(lines)
    titles = title_heights(lines)
    report: list[str] = []
    records: list[dict] = []
    kind = discipline = None
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

        if _is_heading(ln, body.get(ln.page, 0)):
            key = low
            if key == "thin-blood" and i + 1 < len(lines) and lines[i + 1].text.strip().lower() == "alchemy":
                i += 1
            close()
            kind, discipline = SECTIONS.get(key, (None, None))
            level = None
            field = None
            i += 1
            continue

        m = LEVEL_RE.match(text)
        if m and h > body.get(ln.page, 0) + 2:
            close()
            level = int(m.group(1))
            field = None
            i += 1
            continue

        if kind and level and h in titles and c.looks_like_name(text) and low not in NOT_ENTRIES:
            # merge a title broken over several lines (same height, nothing in between)
            parts = [text]
            j = i + 1
            while j < len(lines) and c.looks_like_name(lines[j].text) \
                    and (lines[j].height == h
                         or (c.norm_space(parts[-1]).endswith("-") and lines[j].height in titles)) \
                    and not c.label(lines[j].text) and lines[j].page == ln.page:
                parts.append(lines[j].text.strip())
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
                and c.looks_like_name(text) and low not in NOT_ENTRIES:
            ahead = [c.label(x.text) for x in lines[i + 1:i + 7]]
            if any(a and a[0] in CONFIRM for a in ahead):
                report.append(f"- possible entry title in another type size, not taken: {text!r} "
                              f"({ln.book} p.{ln.page}, height {h})")

        if cur is not None:
            lab = c.label(text)
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
                elif field == "prerequisite" and re.search(r"(?:\bor|\band|\beither|,|-)$",
                                                             cur["prerequisite_text"] or ""):
                    prev = cur["prerequisite_text"]
                    cur["prerequisite_text"] = prev[:-1] + t if prev.endswith("-") else f"{prev} {t}"
                elif field == "cost":
                    cur["cost_text"] = f"{cur['cost_text']} {t}".strip()
                elif field == "dice_pool":
                    cur["dice_pool_text"] = f"{cur['dice_pool_text']} {t}".strip()
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
