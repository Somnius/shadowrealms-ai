"""
V5 character sheet sanity checks (pure). Bounds only — not a chargen validator.

Storage is the same TEXT JSON columns as classic sheets:
- attributes: flat {strength, dexterity, stamina, charisma, manipulation, composure,
  intelligence, wits, resolve} (1-5 in play; 0 accepted for unfinished drafts)
- skills: {physical{...}, social{...}, mental{...}, specialties[{skill,name}], distribution} (0-5)
- wod_meta: {edition:'v5', hunger 0-5, humanity 0-10, stains 0-10, blood_potency 0-10,
  generation, health{max,superficial,aggravated}, willpower{...}, disciplines[{name,level,powers}],
  rituals[{name,level,source}], experience{total,spent,unspent,log[{kind,trait,what,from,to,cost}]},
  saved{advantage_dots 0-20, specialty 0-1}, ...}

A ghoul is a V5 row too, told apart by wod_meta.sheet_kind = 'ghoul' (is_ghoul()); its
wod_meta.ghoul block is bounded here as well: {template, retainer_dots 1-3 | null, domitor
{character_id, name, clan}, age, apparent_age 0-150 | null, ghouled_since, bonds[<=2]
{character_id, name, strength 0-6 | null, note}, feeding {last, note}} and its Disciplines are at
most 1 dot (docs/CHARACTER_SHEET_BLOCKS.md, services/v5_ghoul_chargen.py). `feeding` is a note on
when the ghoul last drank the domitor's Blood, not a track: a V5 ghoul has no vitae, Hunger or Blood
Potency (core p. 234). Older sheets named it `vitae`; both keys are read and bounded.

Missing keys are fine (sheets are filled in over time); present values must be in range.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

V5_ATTRIBUTES = (
    "strength", "dexterity", "stamina",
    "charisma", "manipulation", "composure",
    "intelligence", "wits", "resolve",
)

V5_SKILLS = {
    "physical": ("athletics", "brawl", "craft", "drive", "firearms", "larceny",
                 "melee", "stealth", "survival"),
    "social": ("animal_ken", "etiquette", "insight", "intimidation", "leadership",
               "performance", "persuasion", "streetwise", "subterfuge"),
    "mental": ("academics", "awareness", "finance", "investigation", "medicine",
               "occult", "politics", "science", "technology"),
}

_META_BOUNDS = {
    "hunger": (0, 5),
    "humanity": (0, 10),
    "stains": (0, 10),
    "blood_potency": (0, 10),
    "generation": (3, 16),
}


GHOUL = "ghoul"
# The ghoul templates: the corebook's mortal templates (p. 185) and the Players Guide's player ghoul.
GHOUL_TEMPLATES = ("weak", "average", "gifted", "deadly", "player")
_GHOUL_TEXT_MAX = 200
_GHOUL_NOTE_MAX = 500


def is_ghoul(wod_meta: Any) -> bool:
    """True for a ghoul's sheet (wod_meta.sheet_kind == 'ghoul'); wod_meta may be a dict or its JSON text."""
    if isinstance(wod_meta, str):
        try:
            wod_meta = json.loads(wod_meta)
        except ValueError:
            return False
    return isinstance(wod_meta, dict) and wod_meta.get("sheet_kind") == GHOUL


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _check_range(errors: List[str], label: str, v: Any, lo: int, hi: int) -> None:
    if v is None:
        return
    if not _is_int(v):
        errors.append(f"{label} must be an integer")
    elif v < lo or v > hi:
        errors.append(f"{label} must be between {lo} and {hi}")


def _check_track(errors: List[str], label: str, track: Any) -> None:
    if track is None:
        return
    if not isinstance(track, dict):
        errors.append(f"{label} must be an object")
        return
    mx = track.get("max")
    _check_range(errors, f"{label}.max", mx, 1, 20)
    hi = mx if _is_int(mx) and 1 <= mx <= 20 else 20
    sup = track.get("superficial")
    agg = track.get("aggravated")
    _check_range(errors, f"{label}.superficial", sup, 0, hi)
    _check_range(errors, f"{label}.aggravated", agg, 0, hi)
    if _is_int(sup) and _is_int(agg) and sup + agg > hi:
        errors.append(f"{label}: superficial + aggravated cannot exceed max ({hi})")


_XP_KINDS = ("attribute", "skill", "specialty", "discipline", "ritual")
_ALL_SKILLS = tuple(k for names in V5_SKILLS.values() for k in names)
# Creation grants 15 (neonate) or 35 (ancilla), but XP is also awarded in play (V5.md: 1 per
# session + 1 per story), so total is only kept sane here, not tied to the age.
_XP_MAX = 10000
_NAME_MAX = 120
# Same cap as V5_RITUALS_MAX in frontend/src/characterSheet/v5/constants.js.
RITUALS_MAX = 12
_XP_LOG_MAX = 200


def _check_experience(errors: List[str], xp: Any) -> None:
    """wod_meta.experience: {total, spent, unspent, log: [{kind, trait, what, from, to, cost}]}.

    specialty entries also carry `skill`; a skill's first dot in Academics/Craft/Performance/
    Science may carry `specialty` (its free specialty). When a log is present, spent = its costs.
    """
    if xp is None:
        return
    if not isinstance(xp, dict):
        errors.append("wod_meta.experience must be an object")
        return
    for k in ("total", "spent", "unspent"):
        if xp.get(k) is None:
            errors.append(f"wod_meta.experience.{k} is required")
        _check_range(errors, f"wod_meta.experience.{k}", xp.get(k), 0, _XP_MAX)
    total, spent, unspent = xp.get("total"), xp.get("spent"), xp.get("unspent")
    if all(_is_int(v) for v in (total, spent, unspent)):
        if spent > total:
            errors.append("wod_meta.experience.spent cannot exceed total")
        elif unspent != total - spent:
            errors.append("wod_meta.experience.unspent must be total - spent")
    log = xp.get("log")
    if log is None:
        return
    if not isinstance(log, list) or len(log) > _XP_LOG_MAX:
        errors.append(f"wod_meta.experience.log must be a list of at most {_XP_LOG_MAX} entries")
        return
    cost_sum = 0
    for i, e in enumerate(log):
        label = f"wod_meta.experience.log[{i}]"
        if not isinstance(e, dict):
            errors.append(f"{label} must be an object")
            continue
        kind = e.get("kind")
        if kind not in _XP_KINDS:
            errors.append(f"{label}.kind must be one of {', '.join(_XP_KINDS)}")
        trait = e.get("trait")
        if not isinstance(trait, str) or not trait.strip() or len(trait) > _NAME_MAX:
            errors.append(f"{label}.trait is required (at most {_NAME_MAX} characters)")
        if kind == "specialty" and e.get("skill") not in _ALL_SKILLS:
            errors.append(f"{label}.skill must be a V5 skill key")
        sp = e.get("specialty")
        if sp is not None and (not isinstance(sp, str) or not sp.strip() or len(sp) > _NAME_MAX):
            errors.append(f"{label}.specialty must be a name of at most {_NAME_MAX} characters")
        what = e.get("what")
        if not isinstance(what, str) or not what.strip() or len(what) > 160:
            errors.append(f"{label}.what is required (at most 160 characters)")
        for k in ("from", "to"):
            if e.get(k) is None:
                errors.append(f"{label}.{k} is required")
            _check_range(errors, f"{label}.{k}", e.get(k), 0, 5)
        if _is_int(e.get("from")) and _is_int(e.get("to")) and e["to"] <= e["from"]:
            errors.append(f"{label}: to must be above from")
        if e.get("cost") is None:
            errors.append(f"{label}.cost is required")
        _check_range(errors, f"{label}.cost", e.get("cost"), 0, 100)
        if _is_int(e.get("cost")):
            cost_sum += e["cost"]
    if _is_int(spent) and cost_sum != spent:
        errors.append("wod_meta.experience.spent must equal the sum of the log costs")


def sanity_check_v5(
    attributes: Any = None, skills: Any = None, wod_meta: Any = None
) -> List[str]:
    """Return a list of human-readable problems (empty = OK)."""
    errors: List[str] = []

    if attributes is not None:
        if not isinstance(attributes, dict):
            errors.append("attributes must be an object")
        else:
            for k in V5_ATTRIBUTES:
                # 0 allowed so half-filled drafts save; V5 play needs 1-5.
                _check_range(errors, f"attributes.{k}", attributes.get(k), 0, 5)

    if skills is not None:
        if not isinstance(skills, dict):
            errors.append("skills must be an object")
        else:
            for group, names in V5_SKILLS.items():
                g = skills.get(group)
                if g is None:
                    continue
                if not isinstance(g, dict):
                    errors.append(f"skills.{group} must be an object")
                    continue
                for k in names:
                    _check_range(errors, f"skills.{group}.{k}", g.get(k), 0, 5)
            sp = skills.get("specialties")
            if sp is not None and not isinstance(sp, list):
                errors.append("skills.specialties must be a list")

    if wod_meta is not None:
        if not isinstance(wod_meta, dict):
            errors.append("wod_meta must be an object")
        else:
            for k, (lo, hi) in _META_BOUNDS.items():
                _check_range(errors, f"wod_meta.{k}", wod_meta.get(k), lo, hi)
            _check_track(errors, "wod_meta.health", wod_meta.get("health"))
            _check_track(errors, "wod_meta.willpower", wod_meta.get("willpower"))
            discs = wod_meta.get("disciplines")
            if discs is not None:
                if not isinstance(discs, list):
                    errors.append("wod_meta.disciplines must be a list")
                else:
                    for i, d in enumerate(discs):
                        if not isinstance(d, dict):
                            errors.append(f"wod_meta.disciplines[{i}] must be an object")
                            continue
                        _check_range(errors, f"wod_meta.disciplines[{i}].level", d.get("level"), 0, 5)
            rituals = wod_meta.get("rituals")
            if rituals is not None:
                if not isinstance(rituals, list) or len(rituals) > RITUALS_MAX:
                    errors.append(f"wod_meta.rituals must be a list of at most {RITUALS_MAX} rituals")
                else:
                    for i, r in enumerate(rituals):
                        if not isinstance(r, dict) or not isinstance(r.get("name"), str) \
                                or not r["name"].strip() or len(r["name"]) > 120:
                            errors.append(f"wod_meta.rituals[{i}] needs a name (at most 120 characters)")
                            continue
                        if r.get("level") is None:
                            errors.append(f"wod_meta.rituals[{i}].level is required")
                        _check_range(errors, f"wod_meta.rituals[{i}].level", r.get("level"), 1, 5)
            _check_experience(errors, wod_meta.get("experience"))
            saved = wod_meta.get("saved")
            if saved is not None:
                # Points left unspent at creation (Forge v2 part D, services/saved_points.py).
                if not isinstance(saved, dict):
                    errors.append("wod_meta.saved must be an object")
                else:
                    _check_range(errors, "wod_meta.saved.advantage_dots", saved.get("advantage_dots"), 0, 20)
                    _check_range(errors, "wod_meta.saved.specialty", saved.get("specialty"), 0, 1)
            ed = wod_meta.get("edition")
            if ed is not None and ed != "v5":
                errors.append("wod_meta.edition must be 'v5' for a V5 character")
            kind = wod_meta.get("sheet_kind")
            if kind is not None and kind != GHOUL:
                errors.append("wod_meta.sheet_kind must be 'ghoul' when present")
            if kind == GHOUL:
                _check_ghoul(errors, wod_meta)

    return errors


def _check_text(errors: List[str], label: str, v: Any, limit: int) -> None:
    if v is not None and (not isinstance(v, str) or len(v) > limit):
        errors.append(f"{label} must be text of at most {limit} characters")


def _check_ghoul(errors: List[str], wod_meta: Dict[str, Any]) -> None:
    """Bounds of a ghoul's sheet: wod_meta.ghoul and Disciplines of at most 1 dot."""
    for i, d in enumerate(wod_meta.get("disciplines") if isinstance(wod_meta.get("disciplines"), list) else []):
        if isinstance(d, dict):
            _check_range(errors, f"wod_meta.disciplines[{i}].level (a ghoul)", d.get("level"), 0, 1)
    g = wod_meta.get("ghoul")
    if not isinstance(g, dict):
        errors.append("wod_meta.ghoul is required on a ghoul's sheet")
        return
    if g.get("template") not in GHOUL_TEMPLATES:
        errors.append(f"wod_meta.ghoul.template must be one of {', '.join(GHOUL_TEMPLATES)}")
    _check_range(errors, "wod_meta.ghoul.retainer_dots", g.get("retainer_dots"), 1, 3)
    dom = g.get("domitor")
    if not isinstance(dom, dict) or not _is_int(dom.get("character_id")) or dom["character_id"] < 1:
        errors.append("wod_meta.ghoul.domitor.character_id must be a character id")
    else:
        _check_text(errors, "wod_meta.ghoul.domitor.name", dom.get("name"), 120)
        _check_text(errors, "wod_meta.ghoul.domitor.clan", dom.get("clan"), 120)
    for k in ("age", "apparent_age"):
        _check_range(errors, f"wod_meta.ghoul.{k}", g.get(k), 0, 150)
    _check_text(errors, "wod_meta.ghoul.ghouled_since", g.get("ghouled_since"), _GHOUL_TEXT_MAX)
    bonds = g.get("bonds")
    if bonds is not None:
        if not isinstance(bonds, list) or len(bonds) > 2:
            errors.append("wod_meta.ghoul.bonds must be a list of at most 2 Blood Bonds")
        else:
            for i, b in enumerate(bonds):
                if not isinstance(b, dict):
                    errors.append(f"wod_meta.ghoul.bonds[{i}] must be an object")
                    continue
                cid = b.get("character_id")
                if cid is not None and (not _is_int(cid) or cid < 1):
                    errors.append(f"wod_meta.ghoul.bonds[{i}].character_id must be a character id")
                _check_range(errors, f"wod_meta.ghoul.bonds[{i}].strength", b.get("strength"), 0, 6)
                _check_text(errors, f"wod_meta.ghoul.bonds[{i}].name", b.get("name"), 120)
                _check_text(errors, f"wod_meta.ghoul.bonds[{i}].note", b.get("note"), _GHOUL_NOTE_MAX)
    for key in ("feeding", "vitae"):  # `vitae`: the key's earlier name
        feeding = g.get(key)
        if feeding is None:
            continue
        if not isinstance(feeding, dict):
            errors.append(f"wod_meta.ghoul.{key} must be an object")
        else:
            _check_text(errors, f"wod_meta.ghoul.{key}.last", feeding.get("last"), 60)
            _check_text(errors, f"wod_meta.ghoul.{key}.note", feeding.get("note"), _GHOUL_NOTE_MAX)


def ghoul_feeding(ghoul: Any) -> Dict[str, Any]:
    """wod_meta.ghoul.feeding ({last, note}); a sheet from before the rename has it as `vitae`."""
    g = ghoul if isinstance(ghoul, dict) else {}
    f = g.get("feeding") if isinstance(g.get("feeding"), dict) else g.get("vitae")
    return f if isinstance(f, dict) else {}


def stamp_v5_meta(wod_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure wod_meta.edition = 'v5' (returns a new dict)."""
    out = dict(wod_meta or {})
    out["edition"] = "v5"
    return out
