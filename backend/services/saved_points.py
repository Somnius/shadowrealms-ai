"""
Saved points (Forge v2 part D). Pure: no Flask, no DB.

A V5 player may leave Advantage dots and the free specialty of their choice unspent at creation;
the forge stores them as wod_meta.saved = {advantage_dots, specialty} (at most the chronicle's
creation_settings.saved_points.advantage_dots_cap dots; the specialty only when allow_specialty).
Spending them later is a request (table character_spend_requests, routes/spend_requests.py) that
the Storyteller approves. In a chronicle with creation_settings.st_mode == 'ai' a spend that passes
validate_spend() is applied at once and logged with approver 'ai'; the human creator or staff can
reverse it. A spend that doesn't pass is a house rule: flagged, never approved automatically.

Spend payloads (parse_spend):
  {"kind": "saved_advantage", "items": [{"id": "background:resources" | None, "name": "Resources",
                                          "dots": 1, "kind": "merit|background|loresheet", "note": ""}]}
      dots are added: to a row of the player's own with the same id or name (a raise), else a new row.
  {"kind": "saved_specialty", "skill": "occult", "name": "Byzantine ritual manuscripts"}

Problem codes (validate_spend, {code, params}):
  saved_short {need, have}          more Advantage dots than are saved
  over_cap {cap, total}             more than the chronicle lets a player save
  dots_range {name, to}             a row would end outside 1-5 dots
  unknown_advantage {name}          not in the advantages catalog (only when that catalog exists)
  not_an_advantage {name}           the catalog lists it as a Flaw
  adv_dots_range {name, to, min, max}  outside the catalog's dot range for it
  book_not_allowed {name, book}     from a book the chronicle doesn't allow
  clan_only {name, clans}           for other clans only
  no_saved_specialty {}             no specialty saved
  specialty_not_allowed {}          the chronicle doesn't let players save a specialty
  skill_no_dot {skill}              the skill has no dot
  specialty_duplicate {skill, name} the skill already has that specialty
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Optional, Tuple

from services.character_sheet_v5 import V5_SKILLS
from services.creation_settings import normalize_creation_settings
from services.request_validation import RequestValidationError

SPEND_KINDS = ("saved_advantage", "saved_specialty")
ADVANTAGE_KINDS = ("merit", "background", "loresheet")
STATUSES = ("pending", "approved", "rejected", "reversed")
ITEMS_MAX = 10
NAME_MAX = 120
NOTE_MAX = 300
DOTS_MAX = 5

_SKILL_GROUP = {k: g for g, keys in V5_SKILLS.items() for k in keys}

# The sheet keys a spend touches: (column, key). Only these are snapshotted and restored.
TOUCHED = {
    "saved_advantage": (("wod_meta", "advantages"), ("wod_meta", "saved"), ("merits_flaws", "entries")),
    "saved_specialty": (("skills", "specialties"), ("wod_meta", "saved")),
}


class SheetChanged(Exception):
    """A reverse found the touched keys changed since the apply (a later spend or an edit)."""


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _key(text: Any) -> str:
    """Names compare without case and extra spaces."""
    return " ".join(str(text or "").split()).lower()


def _text(value: Any, label: str, max_len: int, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()) or len(value.strip()) > max_len:
        raise RequestValidationError(f"{label} must be text of 1-{max_len} characters.")
    return " ".join(value.split())


def parse_spend(body: Any) -> Dict[str, Any]:
    """A client's spend request -> the normalised payload. Bad shapes raise RequestValidationError."""
    if not isinstance(body, dict):
        raise RequestValidationError("Send the spend as a JSON object.")
    kind = body.get("kind")
    if kind == "saved_advantage":
        items = body.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= ITEMS_MAX:
            raise RequestValidationError(f"items must be a list of 1-{ITEMS_MAX} Advantages.")
        out = []
        for it in items:
            if not isinstance(it, dict):
                raise RequestValidationError("Each item must be an object.")
            dots = it.get("dots")
            if not (_is_int(dots) and 1 <= dots <= DOTS_MAX):
                raise RequestValidationError(f"Each item spends 1-{DOTS_MAX} dots.")
            k = it.get("kind", "merit")
            if k not in ADVANTAGE_KINDS:
                raise RequestValidationError("An item's kind is merit, background or loresheet.")
            row = {"name": _text(it.get("name"), "An item's name", NAME_MAX), "dots": dots, "kind": k}
            cid = it.get("id")
            if cid is not None:
                cid = _text(cid, "An item's id", NAME_MAX)
                if cid:
                    row["id"] = cid
            note = _text(it.get("note"), "An item's note", NOTE_MAX, required=False)
            if note:
                row["note"] = note
            out.append(row)
        return {"kind": kind, "items": out}
    if kind == "saved_specialty":
        skill = body.get("skill")
        if skill not in _SKILL_GROUP:
            raise RequestValidationError("skill must be a V5 skill key (e.g. occult).")
        return {"kind": kind, "skill": skill, "name": _text(body.get("name"), "The specialty", NAME_MAX)}
    raise RequestValidationError("kind must be saved_advantage or saved_specialty.")


def saved_balance(meta: Any) -> Dict[str, int]:
    """wod_meta.saved as {advantage_dots, specialty}, 0 for anything missing or malformed."""
    saved = meta.get("saved") if isinstance(meta, dict) else None
    saved = saved if isinstance(saved, dict) else {}
    out = {}
    for k in ("advantage_dots", "specialty"):
        v = saved.get(k)
        out[k] = v if _is_int(v) and v > 0 else 0
    return out


def _state(state: Any) -> Dict[str, Dict[str, Any]]:
    """{wod_meta, skills, merits_flaws} as deep-copied dicts."""
    src = state if isinstance(state, dict) else {}
    return {c: copy.deepcopy(src.get(c)) if isinstance(src.get(c), dict) else {} for c in ("wod_meta", "skills", "merits_flaws")}


def _own_row(rows: List[Any], item: Dict[str, Any]) -> Optional[int]:
    """Index of the player's own Advantage row (not a predator grant) that the item raises."""
    def own(r):
        return isinstance(r, dict) and r.get("kind") != "predator"

    if item.get("id"):
        for i, r in enumerate(rows):
            if own(r) and r.get("id") == item["id"]:
                return i
    for i, r in enumerate(rows):
        if own(r) and _key(r.get("name")) == _key(item["name"]):
            return i
    return None


def _mirror(entries: List[Any], change: Dict[str, Any]) -> None:
    """Keep merits_flaws.entries (the generic mirror) in step with an Advantage row."""
    for e in entries:
        if (
            isinstance(e, dict)
            and _key(e.get("name")) == _key(change["name"])
            and e.get("note") != "predator type"
            and _is_int(e.get("points"))
            and e["points"] >= 0
        ):
            e["points"] = change["to"]
            return
    entries.append({"name": change["name"], "points": change["to"], "note": change["kind"]})


def snapshot(state: Any, kind: str) -> Dict[str, Dict[str, Any]]:
    """The keys a spend of this kind touches (None = the key was absent)."""
    s = _state(state)
    out: Dict[str, Dict[str, Any]] = {}
    for col, key in TOUCHED[kind]:
        out.setdefault(col, {})[key] = copy.deepcopy(s[col].get(key))
    return out


def apply_spend(state: Any, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Apply a spend to the sheet: (new_state, before, after). before/after hold only the touched
    keys; after also has "changes" ([{name, kind, from, to}] or [{skill, name}]). The saved balance
    never goes below 0 (an approved house rule may spend more than was saved).
    """
    kind = payload["kind"]
    s = _state(state)
    before = snapshot(s, kind)
    meta = s["wod_meta"]
    have = saved_balance(meta)
    saved = dict(meta.get("saved")) if isinstance(meta.get("saved"), dict) else {}
    changes: List[Dict[str, Any]] = []
    if kind == "saved_advantage":
        rows = list(meta["advantages"]) if isinstance(meta.get("advantages"), list) else []
        for item in payload["items"]:
            i = _own_row(rows, item)
            if i is None:
                row = {"name": item["name"], "dots": 0, "kind": item["kind"]}
                if item.get("id"):
                    row["id"] = item["id"]
                if item.get("note"):
                    row["note"] = item["note"]
                rows.append(row)
                i = len(rows) - 1
            row = dict(rows[i])
            frm = row["dots"] if _is_int(row.get("dots")) else 0
            row["dots"] = frm + item["dots"]
            # How many of the row's dots came from saved points (reverse and later checks).
            row["saved_dots"] = (row["saved_dots"] if _is_int(row.get("saved_dots")) else 0) + item["dots"]
            rows[i] = row
            changes.append({"name": row.get("name") or item["name"], "kind": row.get("kind") or item["kind"], "from": frm, "to": row["dots"]})
        meta["advantages"] = rows
        saved["advantage_dots"] = max(0, have["advantage_dots"] - sum(it["dots"] for it in payload["items"]))
        entries = s["merits_flaws"].get("entries")
        entries = list(entries) if isinstance(entries, list) else []
        for ch in changes:
            _mirror(entries, ch)
        s["merits_flaws"]["entries"] = entries
    else:
        specs = s["skills"].get("specialties")
        specs = list(specs) if isinstance(specs, list) else []
        specs.append({"skill": payload["skill"], "name": payload["name"], "source": "saved"})
        s["skills"]["specialties"] = specs
        saved["specialty"] = max(0, have["specialty"] - 1)
        changes.append({"skill": payload["skill"], "name": payload["name"]})
    saved.setdefault("advantage_dots", have["advantage_dots"])
    saved.setdefault("specialty", have["specialty"])
    meta["saved"] = saved
    after = snapshot(s, kind)
    after["changes"] = changes
    return s, before, after


def _canon(v: Any) -> str:
    return json.dumps(v, sort_keys=True, ensure_ascii=False)


def reverse_spend(state: Any, kind: str, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """
    Put back only the touched keys from `before`, so anything else changed since (Hunger,
    Willpower, ...) stays. Raises SheetChanged when a touched key no longer holds what the apply
    wrote (a later spend or an edit): reverse the later one first.
    """
    s = _state(state)
    for col, key in TOUCHED[kind]:
        if _canon(s[col].get(key)) != _canon((after.get(col) or {}).get(key)):
            raise SheetChanged(f"{col}.{key}")
    for col, key in TOUCHED[kind]:
        value = (before.get(col) or {}).get(key)
        if value is None:
            s[col].pop(key, None)
        else:
            s[col][key] = copy.deepcopy(value)
    return s


def _skills_dots(skills: Any, skill: str) -> int:
    group = (skills or {}).get(_SKILL_GROUP.get(skill, "")) if isinstance(skills, dict) else None
    v = group.get(skill) if isinstance(group, dict) else None
    return v if _is_int(v) else 0


def _catalog_entry(catalog: Dict[str, Any], item: Dict[str, Any]) -> Tuple[bool, Optional[dict]]:
    """(checked, entry): checked is False when no advantages/loresheets catalog is installed."""
    pools = []
    if item["kind"] == "loresheet" and isinstance(catalog.get("loresheets"), list):
        pools.append(catalog["loresheets"])
    if isinstance(catalog.get("advantages"), list):
        pools.append(catalog["advantages"])
    if not pools:
        return False, None
    wants = [_key(item.get("id")), _key(item["name"])]
    for pool in pools:
        for want in wants:
            if not want:
                continue
            for e in pool:
                if not isinstance(e, dict):
                    continue
                names = [e.get("id"), e.get("name"), *(e.get("aliases") or [])]
                if any(isinstance(n, str) and _key(n) == want for n in names):
                    return True, e
    return True, None


def _dot_range(entry: dict) -> Optional[Tuple[int, int]]:
    fixed = entry.get("fixed")
    if _is_int(fixed):
        return fixed, fixed
    dots = entry.get("dots")
    if _is_int(dots):
        return dots, dots
    if isinstance(dots, dict) and _is_int(dots.get("min")) and _is_int(dots.get("max")):
        return dots["min"], dots["max"]
    return None


def _entry_books(entry: dict) -> List[str]:
    books = [entry.get("book")]
    for ref in entry.get("also_in") or []:
        books.append(ref.get("book") if isinstance(ref, dict) else ref)
    return [b for b in books if isinstance(b, str) and b]


def validate_spend(
    meta: Any,
    payload: Dict[str, Any],
    catalog: Optional[Dict[str, Any]] = None,
    settings: Any = None,
    skills: Any = None,
) -> Dict[str, Any]:
    """
    The deterministic rule check of a spend against the sheet (wod_meta + skills), the chronicle's
    creation settings and, when installed, the advantages/loresheets catalog.
    {ok, problems: [{code, params}], house_rule}: house_rule = not ok (a human must decide).
    """
    s = normalize_creation_settings(settings)
    meta = meta if isinstance(meta, dict) else {}
    have = saved_balance(meta)
    problems: List[Dict[str, Any]] = []

    def add(code: str, **params: Any) -> None:
        problems.append({"code": code, "params": params})

    if payload["kind"] == "saved_advantage":
        total = sum(it["dots"] for it in payload["items"])
        if total > have["advantage_dots"]:
            add("saved_short", need=total, have=have["advantage_dots"])
        cap = s["saved_points"]["advantage_dots_cap"]
        if total > cap:
            add("over_cap", cap=cap, total=total)
        _, _, after = apply_spend({"wod_meta": meta}, payload)
        for item, ch in zip(payload["items"], after["changes"]):
            if not 1 <= ch["to"] <= DOTS_MAX:
                add("dots_range", name=ch["name"], to=ch["to"])
            checked, entry = _catalog_entry(catalog or {}, item)
            if not checked:
                continue
            if entry is None:
                add("unknown_advantage", name=item["name"])
                continue
            if entry.get("kind") == "flaw":
                add("not_an_advantage", name=item["name"])
            rng = _dot_range(entry)
            if rng and not rng[0] <= ch["to"] <= rng[1]:
                add("adv_dots_range", name=item["name"], to=ch["to"], min=rng[0], max=rng[1])
            allowed = s["allowed_books"]
            books = _entry_books(entry)
            if allowed and books and not any(b in allowed for b in books):
                add("book_not_allowed", name=item["name"], book=books[0])
            clans = [c for c in entry.get("clans_only") or [] if isinstance(c, str)]
            if clans and _key(meta.get("clan")) not in {_key(c) for c in clans}:
                add("clan_only", name=item["name"], clans=clans)
    else:
        if not s["saved_points"]["allow_specialty"]:
            add("specialty_not_allowed")
        if have["specialty"] < 1:
            add("no_saved_specialty")
        if _skills_dots(skills, payload["skill"]) < 1:
            add("skill_no_dot", skill=payload["skill"])
        specs = (skills or {}).get("specialties") if isinstance(skills, dict) else None
        for sp in specs if isinstance(specs, list) else []:
            if isinstance(sp, dict) and sp.get("skill") == payload["skill"] and _key(sp.get("name")) == _key(payload["name"]):
                add("specialty_duplicate", skill=payload["skill"], name=payload["name"])
                break
    ok = not problems
    return {"ok": ok, "problems": problems, "house_rule": not ok}
