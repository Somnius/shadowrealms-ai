"""
Turn a stored character row into a compact text block for the storyteller LLM (pure).

The row is a dict with the TEXT JSON columns used by the character forge
(attributes, skills, merits_flaws, wod_meta) plus name/system_type/background,
and optionally the legacy d20 columns (character_class, level, character_data).
Classic and V5 sheets share the columns but use different keys; see
docs/CHARACTER_SHEET_BLOCKS.md and services/character_sheet_v5.py.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional

from services.character_sheet_v5 import ghoul_feeding
from services.classic_ghoul import BLOOD_BOND_DRINKS, ghoul_pool, kind_label
from services.rules_edition import edition_of

MAX_BACKGROUND_CHARS = 400
# Every player-written value (names, concept, ambition, tenets, touchstones, discipline
# and power names, sheet keys...) is cleaned and capped before it reaches the prompt, and
# lists are capped, so one sheet can't flood or restructure the storyteller prompt.
MAX_FIELD_CHARS = 200
MAX_NAME_CHARS = 100
MAX_LABEL_CHARS = 60
MAX_LIST_ITEMS = 25
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")
_WS_RE = re.compile(r"\s+")

CLASSIC_ATTRIBUTE_GROUPS = (
    ("Physical", ("strength", "dexterity", "stamina")),
    ("Social", ("charisma", "manipulation", "appearance")),
    ("Mental", ("perception", "intelligence", "wits")),
)
V5_ATTRIBUTE_GROUPS = (
    ("Physical", ("strength", "dexterity", "stamina")),
    ("Social", ("charisma", "manipulation", "composure")),
    ("Mental", ("intelligence", "wits", "resolve")),
)


def _json(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        out = json.loads(value)
    except (TypeError, ValueError):
        return default
    return out if isinstance(out, type(default)) else default


def _clean(value: Any, limit: int = MAX_FIELD_CHARS) -> str:
    """One line of plain text: control characters (newlines included) become spaces,
    whitespace is collapsed, and the result is capped at ``limit`` characters."""
    s = _WS_RE.sub(" ", _CTRL_RE.sub(" ", str(value))).strip()
    return s if len(s) <= limit else s[: max(0, limit - 3)].rstrip() + "..."


def _label(key: str) -> str:
    return _clean(str(key).replace("_", " ").strip().title(), MAX_LABEL_CHARS)


def _num(v: Any) -> Optional[int]:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str) and v.strip().lstrip("-").isdigit():
        return int(v.strip())
    return None


def _rated(d: Dict[str, Any], keys: Optional[Iterable[str]] = None, *, skip_zero: bool = True) -> str:
    """'Strength 3, Dexterity 2' from a {key: dots} dict."""
    parts = []
    for k in list(keys if keys is not None else d.keys())[:MAX_LIST_ITEMS]:
        n = _num(d.get(k))
        if n is None or (skip_zero and n == 0):
            continue
        parts.append(f"{_label(k)} {n}")
    return ", ".join(parts)


def _named_list(items: Any, dots_keys=("dots", "level", "rating", "points", "value")) -> str:
    """'Celerity 2, Presence 1' from [{name, dots}] or {name: dots}."""
    if isinstance(items, dict):
        return _rated(items)
    if not isinstance(items, list):
        return ""
    parts = []
    for it in items[:MAX_LIST_ITEMS]:
        if isinstance(it, str):
            if it.strip():
                parts.append(_clean(it))
            continue
        if not isinstance(it, dict):
            continue
        name = it.get("name") or it.get("label") or it.get("key")
        if not name:
            continue
        dots = None
        for k in dots_keys:
            if it.get(k) is not None:
                dots = it.get(k)
                break
        s = _clean(name) if dots is None else f"{_clean(name)} {_clean(dots, 20)}"
        extra = it.get("powers")
        if isinstance(extra, list) and extra:
            s += " (" + ", ".join(
                _clean(p.get("name", ""), MAX_FIELD_CHARS) if isinstance(p, dict) else _clean(p)
                for p in extra[:MAX_LIST_ITEMS]
            ) + ")"
        elif it.get("note"):
            s += f" ({_clean(it['note'])})"
        parts.append(s)
    return ", ".join(parts)


def _attributes_lines(attrs: Dict[str, Any], groups) -> List[str]:
    lines = []
    known = set()
    for gname, keys in groups:
        known.update(keys)
        s = _rated(attrs, keys, skip_zero=False)
        if s:
            lines.append(f"  {gname}: {s}")
    rest = {k: v for k, v in attrs.items() if k not in known and _num(v) is not None}
    if rest:
        lines.append(f"  Other: {_rated(rest)}")
    return lines


def _classic_abilities_lines(skills: Dict[str, Any]) -> List[str]:
    lines = []
    custom = skills.get("custom") if isinstance(skills.get("custom"), dict) else {}
    for group in ("talents", "skills", "knowledges"):
        g = skills.get(group)
        parts = []
        if isinstance(g, dict):
            s = _rated(g)
            if s:
                parts.append(s)
        c = _named_list(custom.get(group)) if custom else ""
        if c:
            parts.append(c)
        if parts:
            lines.append(f"  {_label(group)}: {', '.join(parts)}")
    return lines


def _v5_skills_lines(skills: Dict[str, Any]) -> List[str]:
    lines = []
    for group in ("physical", "social", "mental"):
        g = skills.get(group)
        if isinstance(g, dict):
            s = _rated(g)
            if s:
                lines.append(f"  {_label(group)}: {s}")
    sp = skills.get("specialties")
    if isinstance(sp, list) and sp:
        items = []
        for it in sp[:MAX_LIST_ITEMS]:
            if isinstance(it, dict) and it.get("name"):
                items.append(
                    f"{_label(it.get('skill', ''))}: {_clean(it['name'])}" if it.get("skill") else _clean(it["name"])
                )
        if items:
            lines.append(f"  Specialties: {', '.join(items)}")
    return lines


def _track(v: Any) -> str:
    """V5 health/willpower {max, superficial, aggravated} → '7 (2 superficial, 1 aggravated)'."""
    if isinstance(v, dict):
        mx = v.get("max")
        sup = _num(v.get("superficial")) or 0
        agg = _num(v.get("aggravated")) or 0
        dmg = []
        if sup:
            dmg.append(f"{sup} superficial")
        if agg:
            dmg.append(f"{agg} aggravated")
        return _clean(mx, 20) + (f" ({', '.join(dmg)} damage)" if dmg else " (undamaged)")
    if v is None:
        return ""
    return _clean(v, 40)


def _merits_flaws_line(mf: Any) -> str:
    if not isinstance(mf, dict):
        return ""
    parts = []
    s = _named_list(mf.get("entries"))
    if s:
        parts.append(s)
    notes = mf.get("notes")
    if isinstance(notes, str) and notes.strip():
        parts.append(_clean(notes))
    return "; ".join(parts)


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _classic_ghoul_lines(meta: Dict[str, Any]) -> List[str]:
    """A Classic (Revised) ghoul's sheet: domitor, kind, duties, its Blood Pool (vitae it holds, max 10,
    1 point per turn; Fatal Addiction), Blood Bond in drinks, feeding, overdosing, frenzy. There is
    no Hunger and no Rouse Check on it."""
    g = meta.get("ghoul") if isinstance(meta.get("ghoul"), dict) else {}
    dom = g.get("domitor") if isinstance(g.get("domitor"), dict) else {}
    dom_name = _clean(dom.get("name") or "an unnamed vampire", MAX_NAME_CHARS)
    head = f"Ghoul of {dom_name}"
    gen = _num(dom.get("generation"))
    extra = [p for p in (_clean(dom.get("clan") or "", MAX_LABEL_CHARS),
                         f"{_ordinal(gen)} generation" if gen and 3 <= gen <= 15 else "") if p]
    if extra:
        head += f" ({', '.join(extra)})"
    parts = [head]
    if g.get("kind"):
        kind = _clean(kind_label(str(g["kind"])), MAX_LABEL_CHARS)
        if g.get("kind") == "revenant" and g.get("family"):
            kind += f" ({_clean(g['family'], MAX_LABEL_CHARS)} family)"
        parts.append(kind)
    if g.get("duties"):
        parts.append(f"Duties: {_clean(g['duties'])}")
    lines = [" · ".join(parts)]
    age = [f"{_label(k)} {_num(g[k])}" for k in ("age", "apparent_age") if _num(g.get(k)) is not None]
    if age:
        lines.append(", ".join(age))
    if g.get("ghouled_since"):
        lines.append(f"Ghoul since: {_clean(g['ghouled_since'])}")
    pool = ghoul_pool(meta)
    lines.append(
        f"Blood Pool {pool['current']}/{pool['max']} (vitae; spend 1 point per turn: heal 1 health level, or +1 to "
        "a Physical Attribute for the scene up to twice the original; Disciplines need at least 1 point; soaks "
        "lethal damage while holding vitae; no Hunger, no Rouse Checks)")
    bond = g.get("bond") if isinstance(g.get("bond"), dict) else {}
    stage = _num(bond.get("stage"))
    if stage is not None or bond.get("note"):
        line = f"Blood Bond to {dom_name}: "
        if stage is not None:
            stage = max(0, min(BLOOD_BOND_DRINKS, stage))
            line += f"{stage}/{BLOOD_BOND_DRINKS} drinks" + (", fully Bound" if stage >= BLOOD_BOND_DRINKS else "")
        else:
            line += "drinks not set"
        if bond.get("note"):
            line += f" ({_clean(bond['note'])})"
        lines.append(line)
    feeding = ghoul_feeding(g)
    if feeding.get("last"):
        lines.append(f"Last fed on the domitor's vitae: {_clean(feeding['last'], 60)}")
    if feeding.get("note"):
        lines.append(f"Feeding note: {_clean(feeding['note'])}")
    if g.get("overdosing"):
        lines.append(f"Overdosing: {_clean(g['overdosing'])}")
    lines.append("Frenzy: Self-Control, difficulties two lower than a vampire's (Revised; Fatal Addiction: three), "
                 "no more dice than Blood Points held")
    return lines


def _classic_meta_lines(meta: Dict[str, Any]) -> List[str]:
    lines = _classic_ghoul_lines(meta) if meta.get("sheet_kind") == "ghoul" else []
    ident = []
    for k in ("clan", "generation", "sect", "breed", "auspice", "tribe", "tradition", "arete"):
        if meta.get(k) not in (None, ""):
            ident.append(f"{_label(k)}: {_clean(meta[k])}")
    if ident:
        lines.append(" | ".join(ident))
    for k in ("nature", "demeanor"):
        if meta.get(k):
            lines.append(f"{_label(k)}: {_clean(meta[k])}")
    vamp = meta.get("vampire") if isinstance(meta.get("vampire"), dict) else {}
    src = {**meta, **vamp}
    if vamp:
        ident2 = []
        for k in ("clan", "generation", "sire"):
            if vamp.get(k) not in (None, "") and not meta.get(k):
                ident2.append(f"{_label(k)}: {_clean(vamp[k])}")
        if ident2:
            lines.append(" | ".join(ident2))
    disc = _named_list(src.get("disciplines"))
    if disc:
        lines.append(f"Disciplines: {disc}")
    bg = _named_list(src.get("backgrounds"))
    if bg:
        lines.append(f"Backgrounds: {bg}")
    virtues = src.get("virtues")
    if isinstance(virtues, dict):
        v = _rated(virtues)
        if v:
            lines.append(f"Virtues: {v}")
    stats = []
    for k in ("humanity", "path", "willpower", "blood_pool", "rage", "gnosis", "quintessence", "paradox"):
        v = src.get(k)
        if v not in (None, "") and not isinstance(v, (dict, list)):
            stats.append(f"{_label(k)} {_clean(v, 40)}")
    if stats:
        lines.append(", ".join(stats))
    for k in ("gifts", "spheres", "rotes"):
        s = _named_list(src.get(k))
        if s:
            lines.append(f"{_label(k)}: {s}")
    return lines


GHOUL_TEMPLATES = {"weak": "Weak mortal", "average": "Average mortal", "gifted": "Gifted mortal",
                   "deadly": "Deadly mortal", "player": "Players Guide ghoul"}
MAX_RETAINERS = 2
MAX_RETAINER_CHARS = 700


def _ghoul_meta_lines(meta: Dict[str, Any]) -> List[str]:
    """A ghoul's sheet (wod_meta.sheet_kind 'ghoul'): domitor, template, Blood Bond, when it last fed
    on the domitor's Blood, power. A V5 ghoul has no vitae track, Hunger or Blood Potency, so none is
    printed; feeding is a note, not a resource."""
    g = meta.get("ghoul") if isinstance(meta.get("ghoul"), dict) else {}
    dom = g.get("domitor") if isinstance(g.get("domitor"), dict) else {}
    lines = []
    head = f"Ghoul of {_clean(dom.get('name') or 'an unnamed vampire', MAX_NAME_CHARS)}"
    if dom.get("clan"):
        head += f" ({_clean(dom['clan'], MAX_LABEL_CHARS)})"
    tpl = g.get("template")
    parts = [head]
    if tpl:
        parts.append(f"{_clean(GHOUL_TEMPLATES.get(tpl, tpl), MAX_LABEL_CHARS)} template")
    if _num(g.get("retainer_dots")):
        parts.append(f"Retainers {_num(g['retainer_dots'])}")
    lines.append(" · ".join(parts))
    age = [f"{_label(k)} {_num(g[k])}" for k in ("age", "apparent_age") if _num(g.get(k)) is not None]
    if age:
        lines.append(", ".join(age))
    if g.get("ghouled_since"):
        lines.append(f"Ghoul since: {_clean(g['ghouled_since'])}")
    discs = meta.get("disciplines") if isinstance(meta.get("disciplines"), list) else []
    powers = []
    for d in discs[:MAX_LIST_ITEMS]:
        if isinstance(d, dict) and d.get("name"):
            names = [_clean(p.get("name", "") if isinstance(p, dict) else p) for p in (d.get("powers") or [])[:MAX_LIST_ITEMS]]
            powers.append(f"{_clean(d['name'])} 1" + (f" ({', '.join(n for n in names if n)})" if any(names) else ""))
    if powers:
        lines.append(f"Ghoul power: {'; '.join(powers)} (powers above level 1 cost 1 Aggravated, no Rouse Checks)")
    for b in (g.get("bonds") if isinstance(g.get("bonds"), list) else [])[:2]:
        if not isinstance(b, dict):
            continue
        st = _num(b.get("strength"))
        line = f"Blood Bond to {_clean(b.get('name') or 'the domitor', MAX_NAME_CHARS)}: " + (
            f"Strength {st}/6" if st is not None else "Strength not set")
        if b.get("note"):
            line += f" ({_clean(b['note'])})"
        lines.append(line)
    feeding = ghoul_feeding(g)
    if feeding.get("last"):
        lines.append(f"Last fed on the domitor's Blood: {_clean(feeding['last'], 60)}")
    if feeding.get("note"):
        lines.append(f"Feeding note: {_clean(feeding['note'])}")
    for k in ("ambition", "desire"):
        if meta.get(k):
            lines.append(f"{_label(k)}: {_clean(meta[k])}")
    if meta.get("humanity") is not None:
        h = f"Humanity {_clean(meta['humanity'], 10)}"
        if _num(meta.get("stains")):
            h += f" ({_num(meta['stains'])} stains)"
        lines.append(h)
    for k in ("health", "willpower"):
        t = _track(meta.get(k))
        if t:
            lines.append(f"{_label(k)}: {t}")
    for label, key in (("Advantages", "advantages"), ("Flaws", "flaws")):
        text = _named_list(meta.get(key))
        if text:
            lines.append(f"{label}: {text}")
    lines.extend(_touchstone_lines(meta))
    return lines


def _touchstone_lines(meta: Dict[str, Any]) -> List[str]:
    tc = meta.get("touchstones")
    if not isinstance(tc, list) or not tc:
        return []
    items = []
    for t in tc[:MAX_LIST_ITEMS]:
        if isinstance(t, dict) and t.get("name"):
            items.append(f"{_clean(t['name'])} — {_clean(t['conviction'])}" if t.get("conviction") else _clean(t["name"]))
    return [f"Touchstones/Convictions: {'; '.join(items)}"] if items else []


def _v5_meta_lines(meta: Dict[str, Any]) -> List[str]:
    if meta.get("sheet_kind") == "ghoul":
        return _ghoul_meta_lines(meta)
    lines = []
    ident = []
    for k in ("clan", "generation", "sire", "predator_type"):
        if meta.get(k) not in (None, ""):
            ident.append(f"{_label(k)}: {_clean(meta[k])}")
    if ident:
        lines.append(" | ".join(ident))
    for k in ("ambition", "desire"):
        if meta.get(k):
            lines.append(f"{_label(k)}: {_clean(meta[k])}")
    stats = []
    if meta.get("hunger") is not None:
        stats.append(f"Hunger {_clean(meta['hunger'], 10)}/5")
    if meta.get("humanity") is not None:
        h = f"Humanity {_clean(meta['humanity'], 10)}"
        if _num(meta.get("stains")):
            h += f" ({_num(meta['stains'])} stains)"
        stats.append(h)
    if meta.get("blood_potency") is not None:
        stats.append(f"Blood Potency {_clean(meta['blood_potency'], 10)}")
    if stats:
        lines.append(", ".join(stats))
    for k in ("health", "willpower"):
        t = _track(meta.get(k))
        if t:
            lines.append(f"{_label(k)}: {t}")
    disc = _named_list(meta.get("disciplines"))
    if disc:
        lines.append(f"Disciplines: {disc}")
    rit = _named_list(meta.get("rituals"))
    if rit:
        lines.append(f"Rituals: {rit}")
    adv = _named_list(meta.get("advantages"))
    if adv:
        lines.append(f"Advantages: {adv}")
    fl = _named_list(meta.get("flaws"))
    if fl:
        lines.append(f"Flaws: {fl}")
    lines.extend(_touchstone_lines(meta))
    tenets = meta.get("chronicle_tenets")
    if tenets:
        if isinstance(tenets, (list, tuple)):
            text = ", ".join(_clean(t) for t in tenets[:MAX_LIST_ITEMS] if str(t).strip())
        else:
            text = _clean(tenets)
        if text:
            lines.append(f"Chronicle tenets: {text}")
    return lines


def format_character_for_prompt(row: Dict[str, Any], edition: str = "classic", role: Optional[str] = None) -> str:
    """Compact character sheet text for the storyteller system prompt. role='retainer': a player
    character's ghoul, listed after the character (format_retainers_for_prompt)."""
    edition = "v5" if str(edition or "").lower() == "v5" else "classic"
    attrs = _json(row.get("attributes"), {})
    skills = _json(row.get("skills"), {})
    meta = _json(row.get("wod_meta"), {})
    mf = _json(row.get("merits_flaws"), {})

    system = _clean(row.get("system_type") or row.get("game_system") or "unknown", MAX_LABEL_CHARS)
    name = _clean(row.get("name") or "Unnamed", MAX_NAME_CHARS)
    ghoul = meta.get("sheet_kind") == "ghoul"  # V5 or Classic
    if role == "retainer":
        header = f"Retainer: {name}" + (" (ghoul)" if ghoul else "")
    else:
        header = f"Character: {name}" + (" (ghoul)" if ghoul else "")
    lines = [header, f"Sheet: {system} — {'V5' if edition == 'v5' else 'Classic (Revised)'} rules"]
    if meta.get("concept"):
        lines.append(f"Concept: {_clean(meta['concept'])}")

    lines.extend(_v5_meta_lines(meta) if edition == "v5" else _classic_meta_lines(meta))

    if attrs:
        a_lines = _attributes_lines(attrs, V5_ATTRIBUTE_GROUPS if edition == "v5" else CLASSIC_ATTRIBUTE_GROUPS)
        if a_lines:
            lines.append("Attributes:")
            lines.extend(a_lines)
    if skills:
        s_lines = _v5_skills_lines(skills) if edition == "v5" else _classic_abilities_lines(skills)
        if s_lines:
            lines.append("Skills:" if edition == "v5" else "Abilities:")
            lines.extend(s_lines)

    mfl = _merits_flaws_line(mf)
    if mfl:
        lines.append(f"Merits/Flaws: {mfl}")

    bg = row.get("background")
    if isinstance(bg, str) and bg.strip():
        lines.append(f"Background: {_clean(bg, MAX_BACKGROUND_CHARS)}")

    # Legacy d20 columns (older characters only)
    if row.get("character_class"):
        lines.append(f"Class/Clan (legacy): {_clean(row['character_class'])}")
    legacy = _json(row.get("character_data"), {})
    if legacy and not attrs:
        for k in ("clan", "generation", "nature", "demeanor"):
            if legacy.get(k):
                lines.append(f"{_label(k)}: {_clean(legacy[k])}")

    return "\n".join(lines)


def _row_edition(row: Dict[str, Any]) -> str:
    """A row's rules edition (its rules_edition column; without one, wod_meta.edition)."""
    if row.get("rules_edition"):
        return edition_of(row)
    return "v5" if str(_json(row.get("wod_meta"), {}).get("edition") or "").lower() == "v5" else "classic"


def format_retainers_for_prompt(pc_name: Any, rows: Iterable[Dict[str, Any]], limit: int = MAX_RETAINERS,
                                max_chars: int = MAX_RETAINER_CHARS) -> str:
    """The player character's ghouls (services/retainers.ghouls_of), at most `limit`, each block cut
    at a line under `max_chars`: the Storyteller plays them, the player directs them. '' for none.
    Each ghoul is formatted by its own rules edition (a V5 vampire's ghouls are V5, a Classic one's
    Classic)."""
    blocks = []
    for row in list(rows)[:max(0, limit)]:
        text = format_character_for_prompt(row, _row_edition(row), role="retainer")
        if len(text) > max_chars:
            cut = text[:max_chars]
            text = (cut[:cut.rfind("\n")] if "\n" in cut else cut).rstrip() + "\n..."
        blocks.append(text)
    if not blocks:
        return ""
    head = (f"Retainers of {_clean(pc_name or 'the character', MAX_NAME_CHARS)} "
            "(ghouls; the Storyteller plays them, the player directs them):")
    return "\n".join([head, *blocks])
