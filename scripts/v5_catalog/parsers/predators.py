"""Predator types: the grant bullets under each type heading, plus the hunting pools.

The parser pulls out what has one obvious reading (specialty choices, the Discipline dot
choice, Humanity and Blood Potency changes, the printed pool) and keeps every bullet's text
in the local intermediate. Advantage/Flaw grants need judgement ("three dots between Fame and
Herd", "Dark Secret or Shunned"), so the committed structured grants come from the manual
record (docs/rules/v5/catalog/manual/predator_types.json); the build compares the two on
the fields the parser does extract and reports every disagreement.
"""

from __future__ import annotations

import re

from ..sources.base import Line
from . import common as c

NAMES = (
    "Alleycat", "Bagger", "Blood Leech", "Cleaver", "Consensualist", "Farmer", "Osiris",
    "Sandman", "Scene Queen", "Siren", "Extortionist", "Graverobber", "Grim Reaper",
    "Montero", "Pursuer", "Trapdoor", "Roadside Killer", "Tithe Collector",
)
_BY_KEY = {n.lower(): n for n in NAMES}
# list markers: corebook "■ ■", Players Guide U+0083 (an unmapped glyph), LTSRR "•"
_BULLET = re.compile("^\\s*(?:\u25a0\\s*)+|^\\s*[\\u0083\\uf0a7\\uf0b7]\\s*|^\\s*\u2022\\s*")
_STARTS = re.compile(r"(?i)^(add a specialty|add one dot|gain |lose one|increase blood|spend |distribute )")


def _is_bullet(text: str) -> bool:
    return bool(_BULLET.match(text)) or bool(_STARTS.match(text.strip()))


def _join(prev: str, nxt: str) -> str:
    """Join a wrapped line, undoing end-of-line hyphenation ('Lock-' + 'picking')."""
    if prev.endswith("-") and nxt[:1].islower():
        return prev[:-1] + nxt
    return f"{prev} {nxt}".strip()


def parse(lines: list[Line]) -> tuple[list[dict], list[str]]:
    report: list[str] = []
    out: list[dict] = []
    cur = None
    bullet = None
    pool = False
    for ln in lines:
        text = ln.text.strip()
        name = _BY_KEY.get(c.norm_space(text).lower())
        if name and (ln.height or 0) >= 18:
            if cur:
                out.append(cur)
            cur = {"id": f"predator:{c.slug(name)}", "name": name, "source": "pdf",
                   "book": ln.book, "page": ln.page, "page_pdf": ln.page_pdf,
                   "bullets": [], "pool_text": None}
            bullet = None
            pool = False
            continue
        if cur is None:
            continue
        if (ln.height or 0) >= 18:  # next section heading
            out.append(cur)
            cur = None
            continue
        if text.startswith("Predator Pool"):
            cur["pool_text"] = text.split(":", 1)[1].strip() if ":" in text else ""
            pool = True
            bullet = None
            continue
        if _is_bullet(text):
            t = _BULLET.sub("", text).strip()
            if not t:  # a marker printed on its own line: the text is on the next line(s)
                continue
            cur["bullets"].append(t)
            bullet = len(cur["bullets"]) - 1
            pool = False
            continue
        if bullet is not None:
            cur["bullets"][bullet] = _join(cur["bullets"][bullet], text)
        elif pool and cur["pool_text"] is not None and len(cur["pool_text"]) < 200:
            cur["pool_text"] = f"{cur['pool_text']} {text}".strip()
    if cur:
        out.append(cur)
    for r in out:
        interpret(r, report)
    return out, report


_SPEC = re.compile(r"([A-Z][A-Za-z]+(?: [A-Z][a-z]+)?) \(([^)]+)\)")


def interpret(r: dict, report: list[str]) -> None:
    r["specialty_choice"] = []
    r["discipline_choice"] = []
    r["humanity"] = 0
    r["blood_potency"] = 0
    r["other_bullets"] = []
    for b in r["bullets"]:
        t = c.norm_space(b.replace("–", "-"))
        low = t.lower()
        if low.startswith("add a specialty"):
            body = t.split(":", 1)[1] if ":" in t else t[len("add a specialty"):]
            r["specialty_choice"] = [{"skill": s, "name": n} for s, n in _SPEC.findall(body)]
            if not r["specialty_choice"]:
                report.append(f"- {r['name']}: specialty bullet not parsed: {t!r}")
        elif re.match(r"(?i)(gain|add) one dot of (?!humanity|the |either |contacts|resources|haven|retainers|allies)", t):
            body = re.sub(r"(?i)^(gain|add) one dot of ", "", t)
            for part in re.split(r"\s+or\s+", body):
                m = re.match(r"([A-Za-z -]+?)\s*(?:\(([^)]+?) only\))?\s*$", part.strip())
                if not m or m.group(1).strip().lower() not in c.DISCIPLINE_BY_KEY:
                    report.append(f"- {r['name']}: discipline option not parsed: {part!r}")
                    continue
                opt = {"discipline": c.DISCIPLINE_BY_KEY[m.group(1).strip().lower()]}
                if m.group(2):
                    opt["clans_only"] = [x.strip() for x in m.group(2).split(" and ")]
                r["discipline_choice"].append(opt)
        elif re.match(r"(?i)lose one dot of humanity", t):
            r["humanity"] = -1
        elif re.match(r"(?i)gain one dot of humanity", t):
            r["humanity"] = 1
        elif re.match(r"(?i)increase blood potency by one", t):
            r["blood_potency"] = 1
        else:
            r["other_bullets"].append(t)


def parse_pools(lines: list[Line]) -> dict:
    """Corebook p.307-308 'name : Attribute + Skill: ...' lines -> {name: pool text}."""
    out = {}
    for ln in lines:
        m = re.match(r"^([A-Za-z -]+?)\s*:\s*(.+)$", ln.text.strip())
        if not m:
            continue
        key = re.sub(r"\s*-\s*", " ", m.group(1)).strip().lower()
        if key in _BY_KEY:
            rest = m.group(2)
            pool = rest.split(":", 1)[0].strip() if ":" in rest else None
            out[_BY_KEY[key]] = {"pool_text": pool, "page": ln.page}
    return out
