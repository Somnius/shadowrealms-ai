"""
Per-chronicle character creation settings (V5 forge), stored as JSON text in
campaigns.creation_settings. Pure: no Flask, no DB.

Shape (every key optional when sent; the normaliser fills defaults):
{
  "v": 1,
  "allowed_books": null | [book_id, ...],      # null = every catalog book, also ones added later (book_allowed)
  "allowed_clans": null | ["Brujah", ...],     # English names, as stored in wod_meta.clan
  "allowed_predators": null | ["Alleycat", ...],
  "allowed_ages": null | ["childer", "neonate", "ancilla"],
  "flaws_max_dots": null | 2-20,               # null = no cap (the corebook sets none)
  "fledgling_humanity_8": true,                # offer the just-Embraced Humanity 8 option
  "saved_points": {"advantage_dots_cap": 0-20, "allow_specialty": bool},  # part D
  "st_mode": "human" | "ai",                   # part D
  "house_rules": ""                            # at most 2000 characters, shown in the forge
}
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Optional

from services.request_validation import RequestValidationError

AGES = ("childer", "neonate", "ancilla")
ST_MODES = ("human", "ai")
LIST_KEYS = ("allowed_books", "allowed_clans", "allowed_predators", "allowed_ages")
NAME_MAX = 60
LIST_MAX = 100
HOUSE_RULES_MAX = 2000
FLAWS_MAX_RANGE = (2, 20)
SAVED_CAP_RANGE = (0, 20)
# Own Flaw dots an ancilla takes: 2 + 2 (docs/rules/v5.json creation.age_brackets.ancilla).
ANCILLA_FLAWS_MIN = 4
AGE_LABELS = {"childer": "childe / fledgling", "neonate": "neonate", "ancilla": "ancilla"}

DEFAULTS: Dict[str, Any] = {
    "v": 1,
    "allowed_books": None,
    "allowed_clans": None,
    "allowed_predators": None,
    "allowed_ages": None,
    "flaws_max_dots": None,
    "fledgling_humanity_8": True,
    "saved_points": {"advantage_dots_cap": 7, "allow_specialty": True},
    "st_mode": "human",
    "house_rules": "",
}


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _clean_list(value: Any) -> Optional[List[str]]:
    """Lenient: a list of distinct non-empty strings (trimmed, capped), else None."""
    if not isinstance(value, list):
        return None
    out: List[str] = []
    for item in value[:LIST_MAX]:
        if isinstance(item, str):
            s = item.strip()[:NAME_MAX]
            if s and s not in out:
                out.append(s)
    return out or None


def normalize_creation_settings(value: Any) -> Dict[str, Any]:
    """
    Stored setting (dict or JSON text) -> the full settings dict. Lenient: anything unknown or
    malformed falls back to its default, so a bad row never breaks the forge.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value) if value.strip() else {}
        except ValueError:
            value = {}
    if not isinstance(value, dict):
        value = {}
    out = copy.deepcopy(DEFAULTS)
    for key in LIST_KEYS:
        out[key] = _clean_list(value.get(key))
    if out["allowed_ages"]:
        out["allowed_ages"] = [a for a in out["allowed_ages"] if a in AGES] or None
    fm = value.get("flaws_max_dots")
    if _is_int(fm) and FLAWS_MAX_RANGE[0] <= fm <= FLAWS_MAX_RANGE[1]:
        out["flaws_max_dots"] = fm
    if isinstance(value.get("fledgling_humanity_8"), bool):
        out["fledgling_humanity_8"] = value["fledgling_humanity_8"]
    sp = value.get("saved_points")
    if isinstance(sp, dict):
        cap = sp.get("advantage_dots_cap")
        if _is_int(cap) and SAVED_CAP_RANGE[0] <= cap <= SAVED_CAP_RANGE[1]:
            out["saved_points"]["advantage_dots_cap"] = cap
        if isinstance(sp.get("allow_specialty"), bool):
            out["saved_points"]["allow_specialty"] = sp["allow_specialty"]
    if value.get("st_mode") in ST_MODES:
        out["st_mode"] = value["st_mode"]
    hr = value.get("house_rules")
    if isinstance(hr, str):
        out["house_rules"] = hr.strip()[:HOUSE_RULES_MAX]
    return out


def validate_creation_settings(value: Any) -> Dict[str, Any]:
    """
    Strict check of a client-sent setting (Storyteller API). Unknown keys, wrong types and values
    out of range are refused with a RequestValidationError; missing keys take their defaults.
    Returns the normalised settings.
    """
    if not isinstance(value, dict):
        raise RequestValidationError("creation_settings must be an object.")
    unknown = sorted(k for k in value if k not in DEFAULTS)
    if unknown:
        raise RequestValidationError(f"Unknown creation_settings key: {unknown[0]}.")
    for key in LIST_KEYS:
        lst = value.get(key)
        if lst is None:
            continue
        if not isinstance(lst, list) or len(lst) > LIST_MAX:
            raise RequestValidationError(f"{key} must be null or a list of at most {LIST_MAX} names.")
        if not lst:
            raise RequestValidationError(f"{key} needs at least one entry (null allows all).")
        for item in lst:
            if not isinstance(item, str) or not item.strip() or len(item.strip()) > NAME_MAX:
                raise RequestValidationError(f"{key} entries are names of 1-{NAME_MAX} characters.")
    for age in value.get("allowed_ages") or []:
        if age not in AGES:
            raise RequestValidationError("allowed_ages entries are childer, neonate or ancilla.")
    fm = value.get("flaws_max_dots")
    if fm is not None and not (_is_int(fm) and FLAWS_MAX_RANGE[0] <= fm <= FLAWS_MAX_RANGE[1]):
        raise RequestValidationError(
            f"flaws_max_dots must be null or an integer {FLAWS_MAX_RANGE[0]}-{FLAWS_MAX_RANGE[1]}."
        )
    if "fledgling_humanity_8" in value and not isinstance(value["fledgling_humanity_8"], bool):
        raise RequestValidationError("fledgling_humanity_8 must be true or false.")
    sp = value.get("saved_points")
    if sp is not None:
        if not isinstance(sp, dict) or any(k not in DEFAULTS["saved_points"] for k in sp):
            raise RequestValidationError("saved_points may only hold advantage_dots_cap and allow_specialty.")
        cap = sp.get("advantage_dots_cap", 7)
        if not (_is_int(cap) and SAVED_CAP_RANGE[0] <= cap <= SAVED_CAP_RANGE[1]):
            raise RequestValidationError(
                f"saved_points.advantage_dots_cap must be an integer {SAVED_CAP_RANGE[0]}-{SAVED_CAP_RANGE[1]}."
            )
        if "allow_specialty" in sp and not isinstance(sp["allow_specialty"], bool):
            raise RequestValidationError("saved_points.allow_specialty must be true or false.")
    if "st_mode" in value and value["st_mode"] not in ST_MODES:
        raise RequestValidationError("st_mode must be human or ai.")
    hr = value.get("house_rules")
    if hr is not None and (not isinstance(hr, str) or len(hr) > HOUSE_RULES_MAX):
        raise RequestValidationError(f"house_rules must be text of at most {HOUSE_RULES_MAX} characters.")
    v = value.get("v", 1)
    if v != 1:
        raise RequestValidationError("creation_settings.v must be 1.")
    out = normalize_creation_settings(value)
    # Ancillae take 2 more Flaw dots (4 in all, docs/rules/v5.json age_brackets), so a lower cap would shut them out.
    if (
        out["flaws_max_dots"] is not None
        and out["flaws_max_dots"] < ANCILLA_FLAWS_MIN
        and (out["allowed_ages"] is None or "ancilla" in out["allowed_ages"])
    ):
        raise RequestValidationError(
            f"Ancillae take {ANCILLA_FLAWS_MIN} Flaw dots: set flaws_max_dots to at least "
            f"{ANCILLA_FLAWS_MIN} or leave ancillae out of allowed_ages."
        )
    return out


def entry_books(entry: Any) -> List[str]:
    """
    The books a catalog entry is printed in: its own `book` first, then the ones of `also_in`
    ([{book, page}], or book ids). Empty for an entry without a book (the v5.json fallback).
    """
    if not isinstance(entry, dict):
        return []
    also = entry.get("also_in") if isinstance(entry.get("also_in"), list) else []
    out: List[str] = []
    for ref in [entry.get("book"), *also]:
        book = ref.get("book") if isinstance(ref, dict) else ref
        if isinstance(book, str) and book.strip() and book.strip() not in out:
            out.append(book.strip())
    return out


def book_allowed(settings: Any, entry: Any) -> bool:
    """
    May a chronicle use this catalog entry (clan, power, ritual, ceremony, formula, predator type,
    Merit, Background, Flaw, loresheet)? Yes when its allowed_books is null (every book, also the
    ones the catalog adds later), when the entry names no book, or when its own book or one it is
    also printed in (also_in) is allowed. `settings`: normalised (normalize_creation_settings).
    The creation check (v5_chargen) and the saved-points spend check both decide with this.
    """
    allowed = settings.get("allowed_books") if isinstance(settings, dict) else None
    if not allowed:
        return True
    books = entry_books(entry)
    return not books or any(b in allowed for b in books)


def creation_problems(settings: Any, wod_meta: Any) -> List[str]:
    """
    What a new V5 sheet breaks in its chronicle's creation settings (clan, predator type, age, Flaw
    cap). Empty list = allowed. Names are compared case-insensitively. Allowed books need the
    catalog: v5_chargen.validate_creation checks them (book_not_allowed).
    """
    s = normalize_creation_settings(settings)
    meta = wod_meta if isinstance(wod_meta, dict) else {}
    problems: List[str] = []

    def _allowed(key: str, val: Any) -> bool:
        allowed = s.get(key)
        if not allowed or not isinstance(val, str) or not val.strip():
            return True
        return val.strip().lower() in {a.lower() for a in allowed}

    clan = meta.get("clan")
    if not _allowed("allowed_clans", clan):
        problems.append(f"The Storyteller doesn't allow {clan} in this chronicle.")
    pred = meta.get("predator_type")
    if not _allowed("allowed_predators", pred):
        problems.append(f"The Storyteller doesn't allow the {pred} predator type in this chronicle.")
    age = meta.get("age")
    if s["allowed_ages"] and isinstance(age, str) and age and age not in s["allowed_ages"]:
        problems.append(f"The Storyteller doesn't allow {AGE_LABELS.get(age, age)} characters in this chronicle.")
    cap = s["flaws_max_dots"]
    if cap is not None:
        own = sum(
            f["dots"]
            for f in (meta.get("flaws") or [])
            if isinstance(f, dict) and f.get("kind") != "predator" and _is_int(f.get("dots"))
        )
        if own > cap:
            problems.append(f"This chronicle allows at most {cap} dots of Flaws of your own (you have {own}).")
    return problems
