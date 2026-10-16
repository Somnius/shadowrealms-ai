"""
Classic (Revised) ghoul sheets: rule constants and the sheet's bounds (docs/rules/CLASSIC_REVISED.md
§7; the creation rules are Ghouls: Fatal Addiction's, the book Revised p. 276 points to).

A Classic ghoul is a characters row with rules_edition 'classic', system_type 'vampire' and
wod_meta.sheet_kind = 'ghoul', no chronicle of its own, linked to its domitor like a V5 ghoul
(services/retainers.py). Unlike a V5 ghoul it HAS a Blood Pool: wod_meta.blood_pool {max 10,
current, per_turn 1} (FA ≈pp. 30-32).

FA page numbers are approximate: our scan has none, and its printed pages run about PDF + 5
(docs/rules/classic.json "ghoul".source).

Classic sheets have no server creation check (the Classic forge holds the budgets, as for Classic
vampires), so this module checks bounds only: sanity_check_classic_ghoul() -> [problem strings],
the same shape as character_sheet_v5.sanity_check_v5. Pure: no Flask, no DB.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

CLASSIC_GHOUL_RULES_VERSION = "classic-ghoul-v1"

# ---------- rule constants (docs/rules/classic.json "ghoul"; test_classic_ghoul.py checks them) ----------

KINDS = ("vassal", "independent", "revenant")
ATTRIBUTE_PRIORITIES = (6, 4, 3)
ABILITY_PRIORITIES = (11, 7, 4)
ABILITY_MAX_BEFORE_FREEBIES = 3
DISCIPLINE_CREATION_DOTS = 2  # Potence 1 + one other at 1
BACKGROUND_DOTS = 5
VIRTUE_DOTS = 7
FREEBIES = 21
FLAWS_MAX_POINTS = 7
FREEBIE_COSTS = {"discipline": 10, "attribute": 5, "ability": 2, "virtue": 2, "willpower": 1,
                 "humanity_or_path": 1, "background": 1}
BLOOD_POOL_MAX = 10
BLOOD_POOL_PER_TURN = 1
BLOOD_BOND_DRINKS = 3
# the highest Discipline level a ghoul learns from a donor of this generation (FA p. 70)
DISCIPLINE_CAP = {13: 1, 12: 1, 11: 1, 10: 1, 9: 1, 8: 1, 7: 2, 6: 3, 5: 4, 4: 5}
# Domitor Background dots by the domitor's generation (FA pp. 81-82)
DOMITOR_BACKGROUND = {1: (11, 15), 2: (9, 10), 3: (8, 8), 4: (7, 7), 5: (6, 6)}
NOT_ALLOWED_BACKGROUNDS = ("generation", "herd", "status")

ATTRIBUTES = ("strength", "dexterity", "stamina", "charisma", "manipulation", "appearance",
              "perception", "intelligence", "wits")
ABILITY_GROUPS = ("talents", "skills", "knowledges")
VIRTUES = ("conscience", "self_control", "courage")
# keys a Classic ghoul's sheet leaves out: a vampire's (clan, generation, sire) and V5's
NOT_ON_A_GHOUL = ("clan", "generation", "sire", "hunger", "blood_potency", "predator_type", "advantages", "flaws")

_TEXT = 200
_NOTE = 500
_NAME = 120


def domitor_generation(meta: Any, default: int = 13) -> int:
    """A Classic vampire's generation from its wod_meta ("12", 12, "12th"), else `default`."""
    g = meta.get("generation") if isinstance(meta, dict) else None
    if isinstance(g, bool):
        return default
    if isinstance(g, int):
        return g if 3 <= g <= 15 else default
    m = re.match(r"\s*(\d+)", str(g or ""))
    n = int(m.group(1)) if m else default
    return n if 3 <= n <= 15 else default


def discipline_cap(generation: Any) -> int:
    """Highest Discipline level a ghoul of a donor of this generation learns (FA p. 70)."""
    g = generation if isinstance(generation, int) and not isinstance(generation, bool) else 13
    if g >= 8:
        return 1
    return DISCIPLINE_CAP.get(max(4, g), 5)


def domitor_background_dots(generation: Any) -> int:
    """The Domitor Background's dots for a domitor of this generation (FA pp. 81-82)."""
    g = generation if isinstance(generation, int) and not isinstance(generation, bool) else 13
    for dots, (lo, hi) in sorted(DOMITOR_BACKGROUND.items()):
        if lo <= g <= hi:
            return dots
    return 5 if g < 6 else 1


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _range(errors: List[str], label: str, v: Any, lo: int, hi: int) -> None:
    if v is None:
        return
    if not _is_int(v):
        errors.append(f"{label} must be an integer")
    elif not lo <= v <= hi:
        errors.append(f"{label} must be between {lo} and {hi}")


def _text(errors: List[str], label: str, v: Any, limit: int) -> None:
    if v is not None and (not isinstance(v, str) or len(v) > limit):
        errors.append(f"{label} must be text of at most {limit} characters")


def _rows(errors: List[str], label: str, rows: Any) -> List[dict]:
    if rows is None:
        return []
    if not isinstance(rows, list) or len(rows) > 40:
        errors.append(f"{label} must be a list of at most 40 rows")
        return []
    out = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            errors.append(f"{label}[{i}] must be an object")
            continue
        _text(errors, f"{label}[{i}].name", r.get("name"), 60)
        _range(errors, f"{label}[{i}].dots", r.get("dots"), 0, 5)
        out.append(r)
    return out


def sanity_check_classic_ghoul(attributes: Any = None, skills: Any = None, wod_meta: Any = None) -> List[str]:
    """Problems with a Classic ghoul's sheet (empty = in bounds). Missing keys are fine except
    wod_meta.ghoul and the Potence row (every ghoul has Potence 1, Revised p. 276)."""
    errors: List[str] = []
    if attributes is not None:
        if not isinstance(attributes, dict):
            errors.append("attributes must be an object")
        else:
            for k in ATTRIBUTES:
                _range(errors, f"attributes.{k}", attributes.get(k), 1, 5)
    if skills is not None:
        if not isinstance(skills, dict):
            errors.append("skills must be an object")
        else:
            for group in ABILITY_GROUPS:
                g = skills.get(group)
                if g is None:
                    continue
                if not isinstance(g, dict):
                    errors.append(f"skills.{group} must be an object")
                    continue
                for k, v in g.items():
                    _range(errors, f"skills.{group}.{k}", v, 0, 5)
            custom = skills.get("custom")
            if isinstance(custom, dict):
                for group, rows in custom.items():
                    for i, r in enumerate(rows if isinstance(rows, list) else []):
                        if isinstance(r, dict):
                            _range(errors, f"skills.custom.{group}[{i}].dots", r.get("dots"), 0, 5)
    if wod_meta is None:
        return errors
    if not isinstance(wod_meta, dict):
        return errors + ["wod_meta must be an object"]
    m = wod_meta
    if m.get("sheet_kind") != "ghoul":
        errors.append("wod_meta.sheet_kind must be 'ghoul'")
    if m.get("edition") not in (None, "", "classic"):
        errors.append("wod_meta.edition must not be 'v5' on a Classic sheet")
    for k in NOT_ON_A_GHOUL:
        if m.get(k) not in (None, "", [], {}):
            errors.append(f"wod_meta.{k}: a Classic ghoul's sheet has no {k}")
    g = m.get("ghoul")
    if not isinstance(g, dict):
        errors.append("wod_meta.ghoul is required on a ghoul's sheet")
    else:
        if g.get("kind") not in KINDS:
            errors.append(f"wod_meta.ghoul.kind must be one of {', '.join(KINDS)}")
        dom = g.get("domitor")
        if not isinstance(dom, dict) or not _is_int(dom.get("character_id")) or dom["character_id"] < 1:
            errors.append("wod_meta.ghoul.domitor.character_id must be a character id")
        else:
            _text(errors, "wod_meta.ghoul.domitor.name", dom.get("name"), _NAME)
            _text(errors, "wod_meta.ghoul.domitor.clan", dom.get("clan"), _NAME)
            _range(errors, "wod_meta.ghoul.domitor.generation", dom.get("generation"), 3, 15)
        for k in ("duties", "ghouled_since"):
            _text(errors, f"wod_meta.ghoul.{k}", g.get(k), _TEXT)
        _range(errors, "wod_meta.ghoul.age", g.get("age"), 0, 1000)  # old ghouls are real (FA p. 31)
        _range(errors, "wod_meta.ghoul.apparent_age", g.get("apparent_age"), 0, 150)
        bond = g.get("bond")
        if bond is not None:
            if not isinstance(bond, dict):
                errors.append("wod_meta.ghoul.bond must be an object")
            else:
                _range(errors, "wod_meta.ghoul.bond.stage", bond.get("stage"), 0, BLOOD_BOND_DRINKS)
                _text(errors, "wod_meta.ghoul.bond.note", bond.get("note"), _NOTE)
                _text(errors, "wod_meta.ghoul.bond.dry_since", bond.get("dry_since"), 60)
        feeding = g.get("feeding")
        if feeding is not None:
            if not isinstance(feeding, dict):
                errors.append("wod_meta.ghoul.feeding must be an object")
            else:
                _text(errors, "wod_meta.ghoul.feeding.last", feeding.get("last"), 60)
                _text(errors, "wod_meta.ghoul.feeding.note", feeding.get("note"), _NOTE)
        _text(errors, "wod_meta.ghoul.overdosing", g.get("overdosing"), _NAME)
        _text(errors, "wod_meta.ghoul.family", g.get("family"), 60)  # a revenant's family
    pool = m.get("blood_pool")
    if pool is not None:
        if not isinstance(pool, dict):
            errors.append("wod_meta.blood_pool must be an object {max, current, per_turn}")
        else:
            mx = pool.get("max")
            _range(errors, "wod_meta.blood_pool.max", mx, 1, 20)
            hi = mx if _is_int(mx) and 1 <= mx <= 20 else BLOOD_POOL_MAX
            _range(errors, "wod_meta.blood_pool.current", pool.get("current"), 0, hi)
            _range(errors, "wod_meta.blood_pool.per_turn", pool.get("per_turn"), 1, BLOOD_POOL_PER_TURN)
    discs = _rows(errors, "wod_meta.disciplines", m.get("disciplines"))
    if not any(str(d.get("name") or "").strip().lower() == "potence" and _is_int(d.get("dots")) and d["dots"] >= 1
               for d in discs):
        errors.append("wod_meta.disciplines: every ghoul has Potence 1 or more (Revised p. 276)")
    for i, b in enumerate(_rows(errors, "wod_meta.backgrounds", m.get("backgrounds"))):
        if str(b.get("name") or "").strip().lower() in NOT_ALLOWED_BACKGROUNDS:
            errors.append(f"wod_meta.backgrounds[{i}]: ghouls take no {b.get('name')} (Fatal Addiction)")
    virtues = m.get("virtues")
    if virtues is not None:
        if not isinstance(virtues, dict):
            errors.append("wod_meta.virtues must be an object")
        else:
            for k in VIRTUES:
                _range(errors, f"wod_meta.virtues.{k}", virtues.get(k), 1, 5)
    _range(errors, "wod_meta.humanity", m.get("humanity"), 0, 10)
    _text(errors, "wod_meta.path", m.get("path") if isinstance(m.get("path"), str) else None, 60)
    _range(errors, "wod_meta.path_rating", m.get("path_rating"), 0, 10)
    wp = m.get("willpower")
    _range(errors, "wod_meta.willpower", wp, 1, 10)
    _range(errors, "wod_meta.willpower_current", m.get("willpower_current"), 0,
           wp if _is_int(wp) and 1 <= wp <= 10 else 10)
    _range(errors, "wod_meta.health_damage", m.get("health_damage"), 0, 7)
    for k in ("concept", "nature", "demeanor"):
        _text(errors, f"wod_meta.{k}", m.get(k), _TEXT)
    xp = m.get("experience")
    if xp is not None and not isinstance(xp, dict):
        errors.append("wod_meta.experience must be an object")
    elif isinstance(xp, dict):
        for k in ("total", "spent", "unspent"):
            _range(errors, f"wod_meta.experience.{k}", xp.get(k), 0, 10000)
    return errors


def ghoul_pool(meta: Any) -> Dict[str, int]:
    """wod_meta.blood_pool of a Classic ghoul as {max, current, per_turn} (defaults 10 / 0 / 1)."""
    pool = meta.get("blood_pool") if isinstance(meta, dict) else None
    pool = pool if isinstance(pool, dict) else {}

    def num(v: Any, d: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, v)) if _is_int(v) else d

    mx = num(pool.get("max"), BLOOD_POOL_MAX, 1, 20)
    return {"max": mx, "current": num(pool.get("current"), 0, 0, mx),
            "per_turn": num(pool.get("per_turn"), BLOOD_POOL_PER_TURN, 1, 1)}


def kind_label(kind: Optional[str]) -> str:
    return {"vassal": "Vassal", "independent": "Independent", "revenant": "Revenant"}.get(kind or "", kind or "")
