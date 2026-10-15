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
  {"kind": "saved_advantage", "items": [
      {"id": "background:allies", "name": "Allies (police)", "dots": 1, "kind": "background", "note": "police"},
      {"id": "loresheet:the-bahari", "name": "The Bahari", "kind": "loresheet", "levels": [2]}]}
      A Merit or Background item adds its dots to the player's own row with the same name (a raise),
      else it is a new row. A loresheet item takes levels (each costs its rating, core p. 190) on
      the player's row of that loresheet, or a new one; its dots are the sum of the levels.
  {"kind": "saved_specialty", "skill": "occult", "name": "Byzantine ritual manuscripts"}

The rows a spend makes are checked with validate_creation's own per-row check
(services/v5_chargen.check_advantage_rows: the catalog rating with Allies 1-6, loresheet levels and
restrictions, clan restrictions, custom rows), so creation and spends follow one code path.

Problem codes (validate_spend, {code, params}):
  saved_short {need, have}          more Advantage dots than are saved
  over_cap {cap, total}             all spends from saved points together go past the chronicle's cap
  from v5_chargen.check_advantage_rows (same codes and params as at creation):
    adv_dots_range {name, dots, min, max}, adv_unknown {name}, adv_restricted {name, clan},
    loresheet_levels {name, dots, levels}, loresheet_restricted {name, clan}, custom_row {name},
    caitiff_status {clan}
  adv_unknown {name}                also a name the installed catalog doesn't know (a spend has no
                                    custom rows: anything the catalog lacks needs a person)
  adv_repeat {name}                 a new row of something taken once (or max_instances times) already
  adv_requires {name, requires}     a prerequisite in the catalog the check can't verify
  book_not_allowed {name, book}     from a book the chronicle doesn't allow
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
from services.v5_chargen import (
    ADVANTAGE_DOTS,
    AGE_BRACKETS,
    FREE_SPECIALTY_SKILLS,
    advantage_entries,
    check_advantage_rows,
)

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


def _item(it: Any) -> Dict[str, Any]:
    if not isinstance(it, dict):
        raise RequestValidationError("Each item must be an object.")
    k = it.get("kind", "merit")
    if k not in ADVANTAGE_KINDS:
        raise RequestValidationError("An item's kind is merit, background or loresheet.")
    row: Dict[str, Any] = {"name": _text(it.get("name"), "An item's name", NAME_MAX), "kind": k}
    if k == "loresheet":
        levels = it.get("levels")
        if (
            not isinstance(levels, list)
            or not 1 <= len(levels) <= DOTS_MAX
            or not all(_is_int(x) and 1 <= x <= DOTS_MAX for x in levels)
            or len(set(levels)) != len(levels)
        ):
            raise RequestValidationError("A loresheet item takes levels: different numbers 1-5.")
        row["levels"] = sorted(levels)
        row["dots"] = sum(levels)
    else:
        dots = it.get("dots")
        if not (_is_int(dots) and 1 <= dots <= DOTS_MAX):
            raise RequestValidationError(f"Each item spends 1-{DOTS_MAX} dots.")
        row["dots"] = dots
    cid = it.get("id")
    if cid is not None:
        cid = _text(cid, "An item's id", NAME_MAX)
        if cid:
            row["id"] = cid
    note = _text(it.get("note"), "An item's note", NOTE_MAX, required=False)
    if note:
        row["note"] = note
    return row


def parse_spend(body: Any) -> Dict[str, Any]:
    """A client's spend request -> the normalised payload. Bad shapes raise RequestValidationError."""
    if not isinstance(body, dict):
        raise RequestValidationError("Send the spend as a JSON object.")
    kind = body.get("kind")
    if kind == "saved_advantage":
        items = body.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= ITEMS_MAX:
            raise RequestValidationError(f"items must be a list of 1-{ITEMS_MAX} Advantages.")
        return {"kind": kind, "items": [_item(it) for it in items]}
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
    """
    Index of the player's own row (not a predator grant) an item adds to: the same name (with its
    note, "Allies (police)"), a loresheet only to a loresheet row and the rest only to the rest.
    """
    lore = item["kind"] == "loresheet"
    for i, r in enumerate(rows):
        if (
            isinstance(r, dict)
            and r.get("kind") != "predator"
            and (r.get("kind") == "loresheet") == lore
            and _key(r.get("name")) == _key(item["name"])
        ):
            return i
    return None


def _apply_items(rows: List[Any], items: List[Dict[str, Any]]) -> Tuple[List[Any], List[Dict[str, Any]], List[int]]:
    """(rows, changes, touched row indexes) after adding the items to a copy of the rows."""
    rows = [dict(r) if isinstance(r, dict) else r for r in rows]
    changes: List[Dict[str, Any]] = []
    touched: List[int] = []
    for item in items:
        i = _own_row(rows, item)
        if i is None:
            row = {"name": item["name"], "dots": 0, "kind": item["kind"]}
            for k in ("id", "note"):
                if item.get(k):
                    row[k] = item[k]
            if item["kind"] == "loresheet":
                row["levels"] = []
            rows.append(row)
            i = len(rows) - 1
        row = rows[i]
        frm = row["dots"] if _is_int(row.get("dots")) else 0
        row["dots"] = frm + item["dots"]
        change = {"name": row.get("name") or item["name"], "kind": row.get("kind") or item["kind"], "from": frm, "to": row["dots"]}
        if item["kind"] == "loresheet":
            had = [x for x in row.get("levels") or [] if _is_int(x)]
            row["levels"] = sorted(had + item["levels"])
            change["levels"] = list(item["levels"])
        # How many of the row's dots came from saved points (the cap counts them).
        row["saved_dots"] = (row["saved_dots"] if _is_int(row.get("saved_dots")) else 0) + item["dots"]
        changes.append(change)
        if i not in touched:
            touched.append(i)
    return rows, changes, touched


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
    keys; after also has "changes" ([{name, kind, from, to, levels?}] or [{skill, name}]). The
    saved balance never goes below 0 (an approved house rule may spend more than was saved).
    """
    kind = payload["kind"]
    s = _state(state)
    before = snapshot(s, kind)
    meta = s["wod_meta"]
    have = saved_balance(meta)
    saved = dict(meta.get("saved")) if isinstance(meta.get("saved"), dict) else {}
    if kind == "saved_advantage":
        rows = meta["advantages"] if isinstance(meta.get("advantages"), list) else []
        meta["advantages"], changes, _ = _apply_items(rows, payload["items"])
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
        changes = [{"skill": payload["skill"], "name": payload["name"]}]
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


# ---------- saved points at creation (the server's own count) ----------

def saved_at_creation(wod_meta: Any, skills: Any, settings: Any) -> Dict[str, int]:
    """
    What a new V5 sheet may keep for later, counted from the sheet itself (the same rule as the
    forge's savedAtCreation in frontend/src/characterSheet/v5/validation.js):
      advantage_dots = min(cap, 7 (+2 for an ancilla) - the dots of the player's own Advantages)
      specialty = 1 when the chronicle saves it and fewer free specialties are named than
                  1 + the rated Academics / Craft / Performance / Science.
    Free specialties are the ones with no source (predator, xp and saved ones are not free).
    """
    s = normalize_creation_settings(settings)
    meta = wod_meta if isinstance(wod_meta, dict) else {}
    budget = ADVANTAGE_DOTS + (AGE_BRACKETS["ancilla"].get("advantage_dots_bonus", 0) if meta.get("age") == "ancilla" else 0)
    rows = meta.get("advantages") if isinstance(meta.get("advantages"), list) else []
    spent = sum(r["dots"] for r in rows if isinstance(r, dict) and r.get("kind") != "predator" and _is_int(r.get("dots")))
    dots = min(s["saved_points"]["advantage_dots_cap"], max(0, budget - spent))
    sk = skills if isinstance(skills, dict) else {}
    rated = sum(1 for k in FREE_SPECIALTY_SKILLS if _skills_dots(sk, k) > 0)
    specs = sk.get("specialties") if isinstance(sk.get("specialties"), list) else []
    named_free = sum(
        1 for sp in specs if isinstance(sp, dict) and not sp.get("source") and str(sp.get("name") or "").strip()
    )
    specialty = 1 if s["saved_points"]["allow_specialty"] and named_free < 1 + rated else 0
    return {"advantage_dots": dots, "specialty": specialty}


def clamp_saved(wod_meta: Any, skills: Any, settings: Any) -> Dict[str, int]:
    """
    wod_meta.saved for a new sheet: the server's count, or the forge's value when that is lower.
    The server sees the final skills (after the predator type's dot), the forge the creation ones,
    so the forge's number is never higher for an honest sheet; a forged balance can't go above
    what the sheet leaves unspent (and validate_creation refuses one that claims more: adv_over).
    """
    mine = saved_at_creation(wod_meta, skills, settings)
    sent = wod_meta.get("saved") if isinstance(wod_meta, dict) else None
    sent = sent if isinstance(sent, dict) else {}
    return {k: min(v, sent[k]) if _is_int(sent.get(k)) and sent[k] >= 0 else v for k, v in mine.items()}


# ---------- the rule check ----------

def _entry_books(entry: dict) -> List[str]:
    books = [entry.get("book")]
    for ref in entry.get("also_in") or []:
        books.append(ref.get("book") if isinstance(ref, dict) else ref)
    return [b for b in books if isinstance(b, str) and b]


def _spend_only(add, meta: dict, items, changes, item_entries, row_entries, settings, catalog) -> None:
    """What a spend adds to the creation row check: a name the catalog lacks (a spend has no custom
    rows), taken too often, a prerequisite to verify, a book the chronicle leaves out."""
    for item, change, entry in zip(items, changes, item_entries):
        name = item["name"]
        installed = bool(catalog.get("loresheets" if item["kind"] == "loresheet" else "advantages"))
        if entry is None:
            if installed:
                add("adv_unknown", name=name)
            continue
        if item["kind"] != "loresheet" and change["from"] == 0:
            n = sum(1 for e in row_entries if e is not None and e.get("id") == entry.get("id"))
            limit = entry.get("max_instances") if _is_int(entry.get("max_instances")) else None
            if (entry.get("repeatable") is False and n >= 1) or (limit is not None and n >= limit):
                add("adv_repeat", name=name)
        req = entry.get("requires")
        if isinstance(req, str) and req.strip():
            # "ancilla or older" is known from the sheet; anything else a person checks.
            if not (req.strip().lower() == "ancilla or older" and meta.get("age") == "ancilla"):
                add("adv_requires", name=name, requires=req.strip())
        allowed = settings["allowed_books"]
        books = _entry_books(entry)
        if allowed and books and not any(b in allowed for b in books):
            add("book_not_allowed", name=name, book=books[0])


def validate_spend(
    meta: Any,
    payload: Dict[str, Any],
    catalog: Optional[Dict[str, Any]] = None,
    settings: Any = None,
    skills: Any = None,
) -> Dict[str, Any]:
    """
    The deterministic rule check of a spend against the sheet (wod_meta + skills), the chronicle's
    creation settings and the V5 catalog (load_catalog(): clans, Disciplines, and when installed
    advantages.json / loresheets.json). {ok, problems: [{code, params}], house_rule}: house_rule =
    not ok (a human must decide).
    """
    s = normalize_creation_settings(settings)
    meta = meta if isinstance(meta, dict) else {}
    catalog = catalog if isinstance(catalog, dict) else {}
    have = saved_balance(meta)
    problems: List[Dict[str, Any]] = []
    seen: set = set()

    def add(code: str, **params: Any) -> None:
        key = (code, _canon(params))
        if key not in seen:
            seen.add(key)
            problems.append({"code": code, "params": params})

    if payload["kind"] == "saved_advantage":
        items = payload["items"]
        total = sum(it["dots"] for it in items)
        if total > have["advantage_dots"]:
            add("saved_short", need=total, have=have["advantage_dots"])
        # The cap is on everything spent from saved points, earlier approved spends included.
        rows = meta.get("advantages") if isinstance(meta.get("advantages"), list) else []
        before = sum(r["saved_dots"] for r in rows if isinstance(r, dict) and _is_int(r.get("saved_dots")))
        cap = s["saved_points"]["advantage_dots_cap"]
        if before + total > cap:
            add("over_cap", cap=cap, total=before + total)
        new_rows, changes, touched = _apply_items(rows, items)
        # The rows as they would be, through the creation check's own per-row rules.
        for p in check_advantage_rows(meta, [new_rows[i] for i in touched], catalog):
            add(p["code"], **p["params"])
        item_entries = advantage_entries(meta, items, catalog)
        row_entries = advantage_entries(meta, [r for r in rows if isinstance(r, dict) and r.get("kind") != "loresheet"], catalog)
        _spend_only(add, meta, items, changes, item_entries, row_entries, s, catalog)
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
