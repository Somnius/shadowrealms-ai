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


def _classic_meta_lines(meta: Dict[str, Any]) -> List[str]:
    lines = []
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


def _v5_meta_lines(meta: Dict[str, Any]) -> List[str]:
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
    tc = meta.get("touchstones")
    if isinstance(tc, list) and tc:
        items = []
        for t in tc[:MAX_LIST_ITEMS]:
            if isinstance(t, dict) and t.get("name"):
                items.append(
                    f"{_clean(t['name'])} — {_clean(t['conviction'])}" if t.get("conviction") else _clean(t["name"])
                )
        if items:
            lines.append(f"Touchstones/Convictions: {'; '.join(items)}")
    tenets = meta.get("chronicle_tenets")
    if tenets:
        if isinstance(tenets, (list, tuple)):
            text = ", ".join(_clean(t) for t in tenets[:MAX_LIST_ITEMS] if str(t).strip())
        else:
            text = _clean(tenets)
        if text:
            lines.append(f"Chronicle tenets: {text}")
    return lines


def format_character_for_prompt(row: Dict[str, Any], edition: str = "classic") -> str:
    """Compact character sheet text for the storyteller system prompt."""
    edition = "v5" if str(edition or "").lower() == "v5" else "classic"
    attrs = _json(row.get("attributes"), {})
    skills = _json(row.get("skills"), {})
    meta = _json(row.get("wod_meta"), {})
    mf = _json(row.get("merits_flaws"), {})

    system = _clean(row.get("system_type") or row.get("game_system") or "unknown", MAX_LABEL_CHARS)
    header = f"Character: {_clean(row.get('name') or 'Unnamed', MAX_NAME_CHARS)}"
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
