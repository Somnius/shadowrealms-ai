"""Merits, Backgrounds and Flaws.

Two readings of the Tier-1 books, compared with each other:

1. The Players Guide "Advantages Master List" (PG pr 232-238): one line per Advantage,
   "NAME DOTS" in capitals, then a short summary ending with the page it is defined on
   ("V:tM, p. 182" = corebook, "p. 119" = Players Guide). Section headings give the kind
   (Backgrounds / Merits / Flaws) and the special groups (Haven, Caitiff, Ghoul, Thin-Blood,
   Coterie, Clan Coterie). This gives the list of entries, their printed ratings and pages.
2. The chapters themselves (corebook pr 179-199, PG pr 109-151): every printed entry line
   ("Flaw: (••) Name.", "•• Name:", "NAME ••", the thin-blood "Name:" lists), with the
   heading it sits under (that heading is the entry's group: Looks, Feeding, Allies, ...).

The master list is the spine; each entry is located in its chapter for the group, the page
and a second reading of the dots. Every difference is reported, nothing is reconciled by
guessing. Summary text is never kept: names, ratings, groups and pages only.
"""

from __future__ import annotations

import re

from ..sources.base import Line
from . import common as c

DOT = "•"
_DOTSPEC = r"\(?\s*[•]+(?:\s*\+|\s+(?:TO|OR|to|or)\s+[•]+\s*\+?)?\s*\)?"
_MASTER_ENTRY = re.compile(rf"^(?P<name>[A-ZÉ][A-ZÉ’'\-:,. ]*?[A-ZÉ])\s*(?P<dots>{_DOTSPEC})?$")
_REF = re.compile(r"(?P<vtm>V:tM,?\s*)?pp?\.\s*(?P<page>\d{1,3})")

# master-list section heading -> (kind, group, flags)
MASTER_SECTIONS = {
    "backgrounds": ("background", None, {}),
    "merits": ("merit", None, {}),
    "flaws": ("flaw", None, {}),
    "haven merits": ("merit", "Haven", {}),
    "haven flaws": ("flaw", "Haven", {}),
    "caitiff merits": ("merit", "Caitiff", {"caitiff": True}),
    "caitiff flaws": ("flaw", "Caitiff", {"caitiff": True}),
    "ghoul merits": ("merit", "Ghoul", {"ghoul_only": True}),
    "ghoul flaws": ("flaw", "Ghoul", {"ghoul_only": True}),
    "thin-blood merits": ("merit", "Thin-blood", {"thin_blood": True}),
    "thin-blood flaws": ("flaw", "Thin-blood", {"thin_blood": True}),
    "coterie merits": ("merit", "Coterie", {"coterie": True}),
    "clan coterie merits": ("merit", "Clan Coterie", {"coterie": True}),
    "coterie advantages": (None, None, {}),
}
# where a section's entries are defined when the line itself cites no page
SECTION_DEFAULT_REF = {
    "Haven": ("v5-corebook", 189), "Caitiff/merit": ("v5-players-guide", 126),
    "Caitiff/flaw": ("v5-players-guide", 127), "Ghoul": ("v5-players-guide", 141),
    "Coterie": ("v5-players-guide", 171),
}
CLAN_PREFIX = {
    "banu haqim": "banu-haqim", "brujah": "brujah", "gangrel": "gangrel", "hecata": "hecata",
    "lasombra": "lasombra", "malkavian": "malkavian", "the ministry": "ministry",
    "nosferatu": "nosferatu", "ravnos": "ravnos", "salubri": "salubri", "toreador": "toreador",
    "tremere": "tremere", "tzimisce": "tzimisce", "ventrue": "ventrue", "caitiff": "caitiff",
    "thin-blood": "thin-blood",
}
# groups whose entries get the group in their id (several groups reuse a name, e.g. Clan Curse)
PREFIXED_GROUPS = {"Caitiff": "caitiff", "Thin-blood": "thin-blood", "Ghoul": "ghoul",
                   "Coterie": "coterie", "Clan Coterie": "coterie"}


def key(name: str) -> str:
    """Spacing/case/punctuation-free match key ('H eliophobia' == 'HELIOPHOBIA')."""
    return re.sub(r"[^a-z]", "", c.norm_space(name).lower().replace("é", "e"))


def parse_dots(spec: str | None) -> dict | None:
    """'• TO ••••' -> {min 1, max 4}; '•+' -> {min 1, max None}; '•• OR •••' -> {allowed [2,3]};
    '(••)' -> {min 2, max 2}; None -> None."""
    if not spec or DOT not in spec:
        return None
    s = spec.strip().strip("()").strip()
    runs = [len(r) for r in re.findall(rf"{DOT}+", s)]
    if re.search(r"\bOR\b", s, re.I):
        return {"allowed": runs}
    if re.search(r"\bTO\b", s, re.I):
        return {"min": runs[0], "max": runs[1] if not s.endswith("+") else None}
    if s.endswith("+"):
        return {"min": runs[0], "max": None}
    return {"min": runs[0], "max": runs[0]}


def entry_id(kind: str, name: str, group: str | None) -> str:
    prefix = PREFIXED_GROUPS.get(group or "")
    return f"{kind}:{prefix + '-' if prefix else ''}{c.slug(name)}"


# --------------------------------------------------------------------------- master list

def parse_master(lines: list[Line]) -> tuple[list[dict], list[str]]:
    report: list[str] = []
    out: list[dict] = []
    kind = group = None
    flags: dict = {}
    cur = None

    def close():
        if cur is None:
            return
        refs = list(_REF.finditer(_refs_text(cur.pop("_text"))))
        if refs:
            r = refs[-1]
            cur["ref"] = ("v5-corebook" if r.group("vtm") else "v5-players-guide", int(r.group("page")))
        else:
            d = SECTION_DEFAULT_REF.get(f"{cur['group']}/{cur['kind']}") or SECTION_DEFAULT_REF.get(cur["group"] or "")
            cur["ref"] = d
        out.append(cur)

    for ln in lines:
        t = c.norm_space(ln.text)
        low = t.lower()
        if (ln.height or 0) >= 18 and low in MASTER_SECTIONS:
            close()
            cur = None
            kind, group, flags = MASTER_SECTIONS[low]
            continue
        if kind is None:
            continue
        m = _MASTER_ENTRY.match(t)
        if m and 13.5 <= (ln.height or 0) <= 14.3 and len(m.group("name")) >= 3:
            close()
            raw = m.group("name").strip()
            clans_only = None
            name = raw
            if group == "Clan Coterie" and ":" in raw:
                clan, name = [x.strip() for x in raw.split(":", 1)]
                cl = CLAN_PREFIX.get(clan.lower())
                clans_only = [f"clan:{cl}"] if cl else None
                if not cl:
                    report.append(f"- master list: unknown clan in {raw!r}")
            name = c.title_case(name)
            cur = {"name": name, "kind": kind, "group": group, "dots": parse_dots(m.group("dots")),
                   "dots_text": m.group("dots"), "master_page": ln.page, "clans_only": clans_only,
                   "_text": ""}
            cur.update(flags)
            continue
        if cur is not None:
            cur["_text"] += " " + t
    close()
    return out, report


# --------------------------------------------------------------------------- chapters

_CORE_FLAW = re.compile(r"^(?P<kind>Merit|Flaw):\s*\((?P<dots>[\u2022]+)\)\s*(?P<name>[A-Z][A-Za-z’'\- ]{1,40}?)\.")
_DOTS_NAME = re.compile(r"^(?P<dots>[\u2022]{1,5})\s+(?P<name>[A-Z][A-Za-z’'\- ]{1,30}):")
_NAME_COLON = re.compile(r"^(?P<name>[A-Z][A-Za-z’'\- ]{1,30}):")
_DOTS_ONLY = re.compile(r"^[\u2022]{1,5}$")
_TITLE_DOTS = re.compile(rf"^(?P<name>[A-Z][A-Za-z’'\- ]{{2,40}}?)\s*(?P<dots>{_DOTSPEC})$")
_COMPANION = re.compile(r"^(?P<dots>[\u25cf ]+?)\s+(?P<name>[A-Z][A-Z’'\- ]{2,40}?)\s*\((?P<tag>[A-Za-z ]+?)(?:\)|$)")
RUN_IN = ("linguistics", "looks", "substance use", "archaic", "bonding", "feeding",
          "mythic merits and flaws", "infamy")
BACKGROUND_NAMES = {"Allies", "Contacts", "Fame", "Haven", "Herd", "Influence", "Loresheet",
                    "Loresheets", "Mask", "Mawla", "Resources", "Retainers", "Status"}
GROUP_MAP = {
    "linguistics": "Linguistics", "looks": "Looks", "substance use": "Substance Use",
    "archaic": "Archaic", "bonding": "Bonding", "feeding": "Feeding",
    "mythic merits and flaws": "Mythic", "looks merits": "Looks", "looks flaws": "Looks",
    "feeding merit": "Feeding", "feeding flaw": "Feeding", "mythic merits": "Mythic",
    "mythic flaws": "Mythic", "other merits": "Other", "other flaws": "Other",
    "thin - blood flaws": "Thin-blood", "thin - blood merits": "Thin-blood",
    "thin-blood merits": "Thin-blood", "thin-blood flaws": "Thin-blood",
    "coterie merits": "Coterie", "coterie flaws": "Coterie",
    "psychological flaw": "Psychological", "psychological merit": "Psychological",
}


def scan_chapter(lines: list[Line]) -> list[dict]:
    """Every entry-looking line with its page, printed dots and the group it sits in.

    group: inside a Background's block (corebook 17.1 pt / PG 28.6 pt heading naming a
    Background) the Background; elsewhere the last group heading (corebook small-caps
    headings, also run into the paragraph as 'feeding Several different...'; PG 19.6 pt
    headings; Companion '(Psychological Flaw)' tags)."""
    out = []
    bg = sub = None
    prev_dots = None
    pending = None  # PG 'CLAN COTERIE MERIT: CALL TO' / 'PURPOSE ••'
    last_book = None
    for ln in lines:
        if ln.book != last_book:
            bg = sub = None
            last_book = ln.book
        raw = ln.text
        t = c.norm_space(c.strip_bullet(raw))
        h = ln.height or 0
        if not t:
            continue
        hit = None
        if pending:
            t = f"{pending} {t}"
            pending = None
        if t.upper().startswith("CLAN COTERIE MERIT:"):
            rest = t.split(":", 1)[1].strip()
            m = _MASTER_ENTRY.match(rest)
            if m and m.group("dots"):
                hit = (m.group("name"), m.group("dots"), None)
            else:
                pending = t
                continue
        if h > 32 and not 38 <= h <= 39:
            continue  # art captions ('Junkie', 'Mafioso' at 33 / 83 pt), not section headings
        me = _MASTER_ENTRY.match(t.upper())
        if not hit and 16.4 <= h and len(t) <= 40 and not re.match(r"^[A-Z] [a-z]", t) \
                and not (me and me.group("dots")) and h != 17.0:
            if t in BACKGROUND_NAMES:
                bg, sub = ("Loresheets" if t == "Loresheet" else t), None
                hit = (t, None, "heading")
            elif h >= 25 and t != "Backgrounds":
                bg, sub = None, t.lower()
            elif bg is None:
                sub = t.lower()
            else:
                hit = (t, None, "subheading")  # 'Enemies' under Allies, 'Bloodline' under Loresheets
            prev_dots = None
            if not hit:
                continue
        if not hit and h in (10.8, 15.4) and t == t.lower() and len(t) <= 40:
            sub = t
            if bg is None:
                hit = (t, None, "heading")  # e.g. 'linguistics' names the Merit too
            else:
                hit = (t, None, "subheading")
        if not hit:
            m = re.match(r"^([a-z][a-z ]+?) [A-Z]", t)
            if m and m.group(1) in RUN_IN:
                if bg is None:
                    sub = m.group(1)
                    continue
                hit = (m.group(1), None, "subheading")  # 'infamy You are famous...'
        if not hit and 16 <= h < 18 and len(t) <= 34 and "." not in t and re.match(r"^[A-Z]", t):
            fixed = re.sub(r"\b([A-Z]) (?=[a-z])", r"\1", t).replace(" -", "-")
            m = _TITLE_DOTS.match(fixed)
            hit = (m.group("name"), m.group("dots"), None) if m else (fixed, None, None)
        if not hit:
            m = _CORE_FLAW.match(t)
            if m and not m.group("name").startswith("You"):
                hit = (m.group("name"), "(" + m.group("dots") + ")", m.group("kind").lower())
        if not hit:
            m = _COMPANION.match(t)
            if m and "\u25cf" in m.group("dots"):
                hit = (m.group("name"), m.group("dots").replace(" ", "").replace("\u25cf", DOT), m.group("tag"))
        if not hit:
            m = _MASTER_ENTRY.match(t)
            if m and t.upper() == t and len(m.group("name")) >= 3 and (m.group("dots") or 14.5 < h < 18):
                hit = (m.group("name"), m.group("dots"), None)
        if not hit and re.match(r"^[A-Z] [a-z]", t) and 16 <= h < 18:  # 'H eliophobia', 'W ord -S carred (•)'
            fixed = re.sub(r"\b([A-Z]) (?=[a-z])", r"\1", t).replace(" -", "-")
            m = _TITLE_DOTS.match(fixed)
            hit = (m.group("name"), m.group("dots"), None) if m else (fixed, None, None)
        if not hit:
            m = _TITLE_DOTS.match(t)
            if m and len(t) <= 45 and not t.endswith("."):
                hit = (m.group("name"), m.group("dots"), None)
        if not hit:
            m = _DOTS_NAME.match(t)
            if m:
                hit = (m.group("name"), m.group("dots"), None)
        if not hit and prev_dots:
            m = _NAME_COLON.match(t)
            if m:
                hit = (m.group("name"), prev_dots, None)
        if not hit and sub and "thin" in sub:
            m = _NAME_COLON.match(t)
            if m and raw.strip().startswith("\u25a0") or (m and h == 12.2):
                hit = (m.group("name"), None, None)
        prev_dots = t if _DOTS_ONLY.match(t) else None
        if hit:
            name, dots, tag = hit
            group = bg
            if tag and tag.lower() in GROUP_MAP:
                group = GROUP_MAP[tag.lower()]
            elif group is None and sub:
                group = GROUP_MAP.get(sub)
            out.append({"name": name.strip(), "key": key(name), "dots_text": dots, "tag": tag,
                        "book": ln.book, "page": ln.page, "group": group})
    return out


def _refs_text(text: str) -> str:
    """Summary text minus any 'See ...' pointer to other books."""
    return re.split(r"\bSee\b", text)[0]


def match(master: list[dict], hits: list[dict], report: list[str], precedence: dict) -> None:
    """Locate each master entry in its chapter: group, page check, a second dots reading."""
    by_key: dict = {}
    for h in hits:
        by_key.setdefault(h["key"], []).append(h)
    for e in master:
        cands = [h for h in by_key.get(key(e["name"]), []) if h["tag"] != "subheading" or e["kind"] != "background"]
        if e["group"] in PREFIXED_GROUPS:  # Clan Curse is both a Caitiff and a thin-blood Flaw
            cands = [h for h in cands if h["group"] in (None, e["group"])]
        ref = e.get("ref")
        near = [h for h in cands if ref and h["book"] == ref[0] and abs(h["page"] - ref[1]) <= 1]
        e["also_in"] = []
        if near:
            pick = near[0]
        elif cands:
            pick = sorted(cands, key=lambda h: (precedence.get(h["book"], 99), h["page"]))[0]
            if ref and pick["book"] == ref[0]:
                report.append(f"- {e['name']}: master list (PG p.{e['master_page']}) cites "
                              f"{ref[0]} p.{ref[1]}, the entry is printed on p.{pick['page']}; "
                              f"chapter page kept")
                e["ref"] = (pick["book"], pick["page"])
            elif ref:
                e["also_in"].append({"book": pick["book"], "page": pick["page"]})
            else:
                e["ref"] = (pick["book"], pick["page"])
        else:
            pick = None
        e["chapter_group"] = pick["group"] if pick else None
        if pick is None:
            report.append(f"- {e['name']} ({e['kind']}): no entry line found in the chapter text "
                          f"(master list cites {ref[0] + ' p.' + str(ref[1]) if ref else 'nothing'})")
        for h in cands:
            if h is pick or (h["book"], h["page"]) == tuple(e["ref"] or ()):
                continue
            loc = {"book": h["book"], "page": h["page"]}
            if loc not in e["also_in"] and h["book"] != (e["ref"] or ("",))[0]:
                e["also_in"].append(loc)
        for h in ([pick] if pick else []) + [h for h in cands if h is not pick]:
            cd = parse_dots(h["dots_text"])
            if cd is not None and e["dots"] is not None and cd != e["dots"]:
                report.append(f"- {e['name']}: master list (PG p.{e['master_page']}) prints "
                              f"{e['dots_text']!r}, {h['book']} p.{h['page']} prints {h['dots_text']!r}")


def chapter_only(master: list[dict], hits: list[dict]) -> list[dict]:
    """Chapter entries the master list does not name (first sighting each)."""
    known = {key(e["name"]) for e in master}
    seen = set()
    out = []
    for h in hits:
        if h["key"] in known or h["key"] in seen or h["tag"] in ("heading", "subheading"):
            continue
        seen.add(h["key"])
        out.append(h)
    return out


def background_levels(lines: list[Line], heading: str) -> list[dict]:
    """Rating names of a Background ('•• Middle Class:'), in the block under its heading.

    Only when every rating from 1 up has a name and none repeats; otherwise []."""
    names: dict = {}
    inside = False
    prev = None
    for ln in lines:
        t = c.norm_space(ln.text)
        if (ln.height or 0) >= 16.4 and len(t) <= 40:
            if inside:
                break
            inside = t == heading
            continue
        if not inside:
            continue
        m = _DOTS_NAME.match(t)
        dots = name = None
        if m:
            dots, name = len(m.group("dots")), m.group("name")
        elif prev and _NAME_COLON.match(t):
            dots, name = len(prev), _NAME_COLON.match(t).group("name")
        prev = t if _DOTS_ONLY.match(t) else None
        if dots is None:
            continue
        if dots in names:
            break
        names[dots] = name.strip()
    if not names or sorted(names) != list(range(1, len(names) + 1)) or len(names) < 3:
        return []
    return [{"dots": d, "name": names[d]} for d in sorted(names)]
