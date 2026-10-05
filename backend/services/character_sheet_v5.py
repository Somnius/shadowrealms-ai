"""
V5 character sheet sanity checks (pure). Bounds only — not a chargen validator.

Storage is the same TEXT JSON columns as classic sheets:
- attributes: flat {strength, dexterity, stamina, charisma, manipulation, composure,
  intelligence, wits, resolve} (1-5 in play; 0 accepted for unfinished drafts)
- skills: {physical{...}, social{...}, mental{...}, specialties[{skill,name}], distribution} (0-5)
- wod_meta: {edition:'v5', hunger 0-5, humanity 0-10, stains 0-10, blood_potency 0-10,
  generation, health{max,superficial,aggravated}, willpower{...}, disciplines[{name,level,powers}], ...}

Missing keys are fine (sheets are filled in over time); present values must be in range.
"""

from __future__ import annotations

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
                if not isinstance(rituals, list) or len(rituals) > 10:
                    errors.append("wod_meta.rituals must be a list of at most 10 rituals")
                else:
                    for i, r in enumerate(rituals):
                        if not isinstance(r, dict) or not isinstance(r.get("name"), str) \
                                or not r["name"].strip() or len(r["name"]) > 120:
                            errors.append(f"wod_meta.rituals[{i}] needs a name (at most 120 characters)")
                            continue
                        if r.get("level") is None:
                            errors.append(f"wod_meta.rituals[{i}].level is required")
                        _check_range(errors, f"wod_meta.rituals[{i}].level", r.get("level"), 1, 5)
            ed = wod_meta.get("edition")
            if ed is not None and ed != "v5":
                errors.append("wod_meta.edition must be 'v5' for a V5 character")

    return errors


def stamp_v5_meta(wod_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure wod_meta.edition = 'v5' (returns a new dict)."""
    out = dict(wod_meta or {})
    out["edition"] = "v5"
    return out
