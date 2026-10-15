"""
V5 character creation check on the server (Forge v2 part C; docs/rules/V5.md §4).

    validate_creation(payload, catalog, settings) -> [{"code": str, "params": dict}]

`payload` is what the forge stores (POST /api/characters/: attributes, skills, wod_meta; built
by buildV5Payload in frontend/src/characterSheet/v5/validation.js). The stored values are final
(after the predator type and the starting XP), so the creation budget is recomputed from them:

- XP dots come off first, per wod_meta.experience.log, which is re-priced with the cost table
  (clan / other / Caitiff Discipline multipliers) and checked against the age's XP;
- the predator type's specialty: a `source: 'predator'` specialty, or a 0-dot Skill raised to 1
  (corebook p. 149), so one 1-dot Skill of the type's options may be that dot;
- Disciplines: 2 + 1 in clan Disciplines (Caitiff any, thin-bloods none) plus the predator dot
  from the type's options for that clan; powers per rating, amalgams, prerequisites;
- predator grant rows (kind 'predator') against the type's grants; own Advantages, own Flaws;
- Convictions, age and generation, derived values (Health, Willpower, Humanity, BP, Hunger);
- rituals and the Oblivion ceremony taken free at creation;
- the chronicle's creation settings (allowed clans, predator types, ages, Flaw cap, Humanity 8).

Advantages and loresheets are checked against the catalog (advantages.json, loresheets.json)
when it has them: dot ranges and clan restrictions. Without them only the totals are checked.
Rows the catalog doesn't know are fine (free-text rows); a row with an unknown `id` is not.

Codes are shared with the client (translations: frontend/src/characterSheet/i18nErrors.js) and
with the test vectors in docs/rules/v5/tests/creation-cases.json. Lenient by design for things
the forge does not send yet. Pure: no Flask, no DB; never raises on malformed input.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

from services.character_sheet_v5 import RITUALS_MAX, V5_ATTRIBUTES, V5_SKILLS
from services.creation_settings import normalize_creation_settings

# ---------- rule constants (docs/rules/v5.json; test_v5_chargen.py checks they match) ----------

ATTRIBUTE_SPREAD = (4, 3, 3, 3, 2, 2, 2, 2, 1)
# The forge's distribution keys (jack = "jack_of_all_trades" in v5.json): rating -> count.
SKILL_DISTRIBUTIONS = {
    "jack": {3: 1, 2: 8, 1: 10},
    "balanced": {3: 3, 2: 5, 1: 7},
    "specialist": {4: 1, 3: 3, 2: 3, 1: 3},
}
FREE_SPECIALTY_SKILLS = ("academics", "craft", "performance", "science")
DISCIPLINE_DOTS = (2, 1)
ADVANTAGE_DOTS = 7
FLAWS_MIN_DOTS = 2
CONVICTIONS = (1, 3)
THIN_BLOOD_MERITS = (1, 3)
STARTING_HUMANITY = 7
FLEDGLING_HUMANITY = 8
STARTING_HUNGER = 1
AGE_BRACKETS: Dict[str, Dict[str, Any]] = {
    "childer": {"generations": (12, 13, 14, 15, 16), "xp": 0},
    "neonate": {"generations": (12, 13), "xp": 15},
    "ancilla": {
        "generations": (10, 11),
        "xp": 35,
        "blood_potency_bonus": 1,
        "advantage_dots_bonus": 2,
        "flaw_dots_bonus": 2,
        "humanity_change": -1,
    },
}
# generation range -> (min BP, max BP, starting BP or None, thin-blood)
GENERATION_BP = (
    (4, 4, 5, 10, None, False),
    (5, 5, 4, 9, None, False),
    (6, 6, 3, 8, None, False),
    (7, 7, 3, 7, None, False),
    (8, 8, 2, 6, None, False),
    (9, 9, 2, 5, None, False),
    (10, 11, 1, 4, 2, False),
    (12, 13, 1, 3, 1, False),
    (14, 16, 0, 0, 0, True),
)
XP_COSTS = {
    "attribute": 5,
    "skill": 3,
    "specialty": 3,
    "clan_discipline": 5,
    "other_discipline": 7,
    "caitiff_discipline": 6,
    "ritual": 3,
}
XP_MAX_DOTS = 5
# Longest XP specialty or ritual name the forge accepts (V5_NAME_MAX in the frontend).
NAME_MAX = 100

THIN_BLOOD = "Thin-blood"
CAITIFF = "Caitiff"
BLOOD_SORCERY = "Blood Sorcery"
OBLIVION = "Oblivion"
ALCHEMY = "Thin-Blood Alchemy"

SKILL_KEYS = tuple(k for group in ("physical", "social", "mental") for k in V5_SKILLS[group])

# Every code validate_creation can return (the client's translations cover the same list).
PROBLEM_CODES = (
    "clan_missing", "age_missing", "age_generation", "thin_blood_generation", "generation_thin_blood",
    "attr_range", "attr_spread",
    "skill_dist", "specialty_count", "specialty_skill", "specialty_missing", "specialty_duplicate",
    "disc_thin_blood", "disc_pick", "disc_clan",
    "power_unknown", "power_level", "power_amalgam", "power_prereq", "power_duplicate", "power_count",
    "predator_missing", "predator_forbidden", "predator_specialty", "predator_discipline",
    "predator_grant", "predator_bp", "predator_ancilla",
    "adv_over", "flaw_under", "flaw_over", "adv_dots_range", "adv_unknown", "adv_restricted",
    "loresheet_restricted", "loresheet_levels", "custom_row", "caitiff_status",
    "thin_blood_merits", "thin_blood_only",
    "conviction_count", "conviction_pairs", "derived_value",
    "xp_none", "xp_total", "xp_log", "xp_price", "xp_over", "xp_max_dots", "name_length",
    "ritual_level", "ritual_blood_sorcery", "ritual_start", "ceremony_start", "ritual_count",
    "clan_not_allowed", "predator_not_allowed", "age_not_allowed", "fledgling_not_allowed",
)


# ---------- small helpers ----------

def _int(v: Any) -> int:
    """parseInt(v, 10) || 0, as the forge reads numbers."""
    if isinstance(v, bool):
        return 0
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v) if math.isfinite(v) else 0
    if isinstance(v, str):
        m = re.match(r"\s*([+-]?\d+)", v)
        return int(m.group(1)) if m else 0
    return 0


def _str(v: Any) -> str:
    return v.strip() if isinstance(v, str) else ""


def _norm(v: Any) -> str:
    """Case- and space-insensitive key for names."""
    return " ".join(str(v or "").split()).lower()


def _alnum(v: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _norm(v))


def _to_key(label: Any) -> str:
    """'Animal Ken' -> 'animal_ken' (the forge's toKey)."""
    return re.sub(r"[^a-z0-9]+", "_", str(label or "").strip().lower())


def _title_of(slug: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in slug.split("-"))


def _name_from_id(entry_id: Any) -> str:
    """'background:iron-gullet' -> 'Iron Gullet' (rulesData.nameFromId)."""
    return _title_of(str(entry_id or "").split(":")[-1])


def _dicts(v: Any) -> List[dict]:
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _loose_name_eq(a: Any, b: Any) -> bool:
    """Same specialty name, give or take spaces, punctuation or extra words ('Lock Picking')."""
    if _alnum(a) == _alnum(b):
        return True
    wa, wb = set(_norm(a).split()), set(_norm(b).split())
    return bool(wa and wb) and (wa <= wb or wb <= wa)


def _generation_row(gen: int) -> Optional[Tuple[int, int, int, int, Optional[int], bool]]:
    for row in GENERATION_BP:
        if row[0] <= gen <= row[1]:
            return row
    return None


class _Problems:
    def __init__(self) -> None:
        self.items: List[Dict[str, Any]] = []
        self._seen: set = set()

    def add(self, code: str, **params: Any) -> None:
        key = (code, tuple(sorted((k, repr(v)) for k, v in params.items())))
        if key not in self._seen:
            self._seen.add(key)
            self.items.append({"code": code, "params": params})


# ---------- the catalog, indexed by name ----------

def _list(v: Any) -> list:
    return v if isinstance(v, list) else []


def _strs(v: Any) -> List[str]:
    """The non-empty strings of a list (ids, aliases, clan lists); anything else is dropped."""
    return [x for x in _list(v) if isinstance(x, str) and x.strip()]


def _sid(v: Any) -> str:
    """An id as a string ('' for anything else), safe as a dict key."""
    return v if isinstance(v, str) else ""


def _keys_of(entry: dict) -> set:
    """The normalised name and aliases of a catalog entry."""
    return {_norm(n) for n in [_str(entry.get("name")), *_strs(entry.get("aliases"))] if n}


class _Catalog:
    """The parts of load_catalog() the check reads, by normalised name (aliases too). A malformed
    entry (an id that isn't a string, aliases that aren't a list...) is skipped or read as empty,
    never raised on."""

    def __init__(self, catalog: Optional[Dict[str, Any]]) -> None:
        cat = catalog if isinstance(catalog, dict) else {}
        self.disc_names: Dict[str, str] = {}
        power_names: Dict[str, str] = {}
        for d in _dicts(cat.get("disciplines")):
            if _sid(d.get("id")) and _str(d.get("name")):
                self.disc_names[d["id"]] = _str(d.get("name"))
            for pw in _dicts(d.get("powers")):
                if _sid(pw.get("id")) and _str(pw.get("name")):
                    power_names[pw["id"]] = _str(pw.get("name"))
        clan_names = {
            c["id"]: _str(c.get("name")) for c in _dicts(cat.get("clans")) if _sid(c.get("id")) and _str(c.get("name"))
        }

        def disc(ref: Any) -> str:
            return self.disc_names.get(_sid(ref)) or _name_from_id(_sid(ref))

        def clan(ref: Any) -> str:
            return clan_names.get(_sid(ref)) or _name_from_id(_sid(ref))

        def pname(ref: Any) -> str:
            rid = _sid(ref if isinstance(ref, str) else ref.get("power_id") if isinstance(ref, dict) else None)
            return power_names.get(rid) or _name_from_id(rid)

        def group(pr: Any) -> Optional[List[str]]:
            if not isinstance(pr, dict):
                return None
            if pr.get("power_id"):
                return [pname(pr)]
            if isinstance(pr.get("any_of"), list):
                return [pname(x) for x in pr["any_of"]]
            return None

        def prereq(pr: Any) -> List[List[str]]:
            """{power_id} | {any_of} | {all_of: [...]} -> every group needed, any name of a group."""
            if not isinstance(pr, dict):
                return []
            if isinstance(pr.get("all_of"), list):
                return [g for g in (group(x) for x in pr["all_of"]) if g]
            g = group(pr)
            return [g] if g else []

        def index(target: Dict[str, dict], keys: Iterable[Any], entry: dict) -> None:
            for n in keys:
                if isinstance(n, str) and n.strip():
                    target.setdefault(_norm(n), entry)

        self.clans: Dict[str, dict] = {}
        for c in _dicts(cat.get("clans")):
            creation = c.get("creation") if isinstance(c.get("creation"), dict) else {}
            entry = {
                "id": _sid(c.get("id")),
                "name": _str(c.get("name")),
                "disciplines": [disc(d) for d in _strs(c.get("disciplines"))],
                "caitiff": c.get("caitiff") is True or c.get("name") == CAITIFF,
                "thin_blood": c.get("thin_blood") is True or c.get("name") == THIN_BLOOD,
                # Caitiff: new x 6 for every Discipline, no positive Status (the clan's creation rules)
                "xp_multiplier": _int(creation.get("discipline_xp_multiplier")),
                "no_positive_status": creation.get("no_positive_status") is True,
            }
            index(self.clans, [c.get("name"), c.get("id"), *_strs(c.get("aliases"))], entry)

        self.disciplines: Dict[str, dict] = {}
        for d in _dicts(cat.get("disciplines")):
            powers = []
            for pw in _dicts(d.get("powers")):
                am = pw.get("amalgam") if isinstance(pw.get("amalgam"), dict) else None
                powers.append({
                    "id": _sid(pw.get("id")) or _norm(pw.get("name")),
                    "name": _str(pw.get("name")),
                    "keys": _keys_of(pw),
                    "level": _int(pw.get("level")),
                    "amalgam": (disc(am.get("discipline")), _int(am.get("level"))) if am else None,
                    "prerequisite": prereq(pw.get("prerequisite")),
                })
            index(self.disciplines, [d.get("name"), *_strs(d.get("aliases"))],
                  {"id": _sid(d.get("id")), "name": _str(d.get("name")), "powers": powers})
        self.discipline_list = [_str(d.get("name")) for d in _dicts(cat.get("disciplines")) if _str(d.get("name"))]

        self.advantages = _dicts(cat.get("advantages"))
        self.loresheets = _dicts(cat.get("loresheets"))
        self.adv_by_id = {a["id"]: a for a in self.advantages if _sid(a.get("id"))}
        self.clan_name = clan

        self.predators: Dict[str, dict] = {}
        for pt in _dicts(cat.get("predator_types")):
            mbp = pt.get("max_blood_potency")
            entry = {
                "name": _str(pt.get("name")),
                "specialties": [(_to_key(sp.get("skill")), _str(sp.get("name"))) for sp in _dicts(pt.get("specialty_choice"))],
                "disciplines": [
                    (disc(d.get("discipline")), [clan(c) for c in _strs(d.get("clans_only"))] or None)
                    for d in _dicts(pt.get("discipline_choice"))
                ],
                "advantages": self._grants(pt.get("advantages")),
                "flaws": self._grants(pt.get("flaws")),
                "humanity": _int(pt.get("humanity")),
                "blood_potency": _int(pt.get("blood_potency")),
                "max_blood_potency": mbp if isinstance(mbp, int) and not isinstance(mbp, bool) else None,
                "forbidden_clans": [clan(c) for c in _strs(pt.get("forbidden_clans"))],
                "ancilla_only": pt.get("ancilla_only") is True,
            }
            index(self.predators, [pt.get("name"), pt.get("id"), *_strs(pt.get("aliases"))], entry)

        def rituals(kind: str) -> Dict[str, dict]:
            out: Dict[str, dict] = {}
            for r in _dicts(cat.get(kind)):
                entry = {
                    "name": _str(r.get("name")), "level": _int(r.get("level")), "prerequisite": prereq(r.get("prerequisite")),
                }
                index(out, [r.get("name"), *_strs(r.get("aliases"))], entry)
            return out

        self.rituals = rituals("rituals")
        self.ceremonies = rituals("ceremonies")

    def _grants(self, grants: Any) -> List[dict]:
        """A predator type's grants: per option the names a row may carry, its label ("Contacts
        (criminal)"), and for a group option ("group": true, e.g. flaw:mythic = any Mythic Flaw)
        the names of every catalog entry of that kind and group."""
        out = []
        for g in _dicts(grants):
            opts = []
            for o in _dicts(g.get("options")):
                oid = _sid(o.get("id"))
                names = {_norm(_name_from_id(oid))} if oid else {_norm(o.get("name"))}
                adv = self.adv_by_id.get(oid)
                if adv:
                    names |= _keys_of(adv)
                names.discard("")
                members: set = set()
                member_ids: set = set()
                if o.get("group") is True and oid:
                    kind, grp = oid.split(":")[0], _norm(_name_from_id(oid))
                    for a in self.advantages:
                        if a.get("kind") == kind and _norm(a.get("group")) == grp:
                            members |= _keys_of(a)
                            if _sid(a.get("id")):
                                member_ids.add(a["id"])
                note = _str(o.get("note"))
                dots = o.get("dots")
                opts.append({
                    "id": oid,
                    "names": names,
                    "labels": {f"{n} ({_norm(note)})" if note else n for n in names},
                    "members": members,
                    "member_ids": member_ids,
                    "dots": dots if isinstance(dots, int) and not isinstance(dots, bool) else None,
                })
            total = g.get("dots_total")
            out.append({
                "pick": g.get("pick") if g.get("pick") in ("all", "one_of", "split") else "all",
                "dots_total": total if isinstance(total, int) and not isinstance(total, bool) else None,
                "options": opts,
            })
        return out

    def clan(self, name: Any) -> Optional[dict]:
        return self.clans.get(_norm(name)) if _norm(name) else None

    def discipline(self, name: Any) -> Optional[dict]:
        return self.disciplines.get(_norm(name)) if _norm(name) else None

    def predator(self, name: Any) -> Optional[dict]:
        return self.predators.get(_norm(name)) if _norm(name) else None

    def advantage(self, row: dict, flaw: bool, clan: Optional[dict]) -> Optional[dict]:
        """The catalog Merit/Background (or Flaw) a sheet row names: by id, else (or when the id is
        unknown: renamed, another book) by name/alias, as the forge's findAdvantage does."""
        rid = _sid(row.get("id"))
        if rid in self.adv_by_id:
            return self.adv_by_id[rid]
        want = {_norm(n) for n in _name_variants(row.get("name"))}
        hits = [a for a in self.advantages if (a.get("kind") == "flaw") == flaw and want & _keys_of(a)]
        if len(hits) > 1 and clan:
            # Caitiff and thin-blood entries share names with others ("Clan Curse"): prefer the clan's.
            mine = [
                a for a in hits
                if (a.get("caitiff") is True) == clan["caitiff"] and (a.get("thin_blood") is True) == clan["thin_blood"]
            ]
            hits = mine or hits
        return hits[0] if hits else None

    def loresheet(self, row: dict) -> Optional[dict]:
        """The catalog loresheet a row names: by id, else (or when the id is unknown) by name."""
        rid = _sid(row.get("id"))
        hit = next((ls for ls in self.loresheets if rid and ls.get("id") == rid), None)
        if hit is not None:
            return hit
        want = {_norm(n) for n in _name_variants(row.get("name"))}
        return next((ls for ls in self.loresheets if want & _keys_of(ls)), None)


def _name_variants(name: Any) -> List[str]:
    """'Allies (police)' -> also 'Allies'; 'Looks: Beautiful' -> also 'Beautiful'."""
    s = _str(name)
    out = [s]
    base = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    if base and base != s:
        out.append(base)
    if ":" in base:
        out.append(base.split(":", 1)[1].strip())
    return [x for x in out if x]


# ---------- the check ----------

def _named_rows(rows: Any) -> List[dict]:
    return [r for r in _dicts(rows) if _str(r.get("name"))]


def _power_name(p: Any) -> str:
    """A stored power: its name (str), or {id, name, level} (new sheets may carry the id)."""
    if isinstance(p, dict):
        if _str(p.get("name")):
            return _str(p.get("name"))
        return _name_from_id(p.get("id")) if p.get("id") else ""
    return _str(p)


def _names(v: Any) -> List[str]:
    """Names from a list of strings or {name} objects (thin-blood Merits and Flaws)."""
    out = []
    for x in v if isinstance(v, list) else []:
        n = _str(x) if isinstance(x, str) else _str(x.get("name")) if isinstance(x, dict) else ""
        if n:
            out.append(n)
    return out


def _skill_problems(pre: Dict[str, int], dist_key: Any) -> List[Tuple[str, dict]]:
    """validateV5Skills: the distribution's counts, exactly."""
    dist = SKILL_DISTRIBUTIONS.get(dist_key) if isinstance(dist_key, str) else None
    if not dist:
        return [("skill_dist", {"distribution": dist_key if isinstance(dist_key, str) else None})]
    vals = [pre.get(k, 0) for k in SKILL_KEYS]
    top = max(dist)
    have = Counter(v for v in vals if v > 0)
    if any(v < 0 or v > top for v in vals) or any(dist.get(r, 0) != have.get(r, 0) for r in set(dist) | set(have)):
        return [("skill_dist", {"distribution": dist_key})]
    return []


def _specialty_problems(free: List[dict], pre: Dict[str, int]) -> List[Tuple[str, dict]]:
    """validateV5Specialties over the free creation specialties (one per rated Academics/Craft/
    Performance/Science, plus one), on the Skills before the predator type's dot."""
    out: List[Tuple[str, dict]] = []
    allowed = sum(1 for k in FREE_SPECIALTY_SKILLS if pre.get(k, 0) > 0) + 1
    if len(free) > allowed:
        out.append(("specialty_count", {"max": allowed, "have": len(free)}))
    for sp in free:
        skill = sp.get("skill")
        if skill not in SKILL_KEYS or pre.get(skill, 0) < 1:
            out.append(("specialty_skill", {"skill": skill}))
    for k in FREE_SPECIALTY_SKILLS:
        if pre.get(k, 0) > 0 and not any(sp.get("skill") == k for sp in free):
            out.append(("specialty_missing", {"skill": k}))
    return out


def _spec_key(skill: Any, name: Any) -> Tuple[str, str]:
    return (str(skill or ""), _norm(name))


# ---------- the sheet, read once ----------

class _Sheet:
    """The stored sheet as the checks read it, with the starting XP's dots taken off."""

    def __init__(self, payload: Any, cat: _Catalog) -> None:
        doc = payload if isinstance(payload, dict) else {}
        attrs = doc.get("attributes") if isinstance(doc.get("attributes"), dict) else {}
        self.skills_doc = doc.get("skills") if isinstance(doc.get("skills"), dict) else {}
        self.meta = meta = doc.get("wod_meta") if isinstance(doc.get("wod_meta"), dict) else {}

        self.clan_raw = meta.get("clan")
        self.clan = cat.clan(self.clan_raw)
        self.clan_name = self.clan["name"] if self.clan else _str(self.clan_raw)
        self.thin = bool(self.clan and self.clan["thin_blood"])
        self.caitiff = bool(self.clan and self.clan["caitiff"])
        self.age = meta.get("age") if isinstance(meta.get("age"), str) else None
        self.bracket = AGE_BRACKETS.get(self.age)
        self.gen = _int(meta.get("generation"))

        self.pred_raw = meta.get("predator_type")
        self.pred = cat.predator(self.pred_raw)
        self.pred_name = self.pred["name"] if self.pred else _str(self.pred_raw)

        # What the XP log bought, so the creation values can be recovered.
        self.xp = meta.get("experience") if isinstance(meta.get("experience"), dict) else None
        self.log = _dicts(self.xp.get("log")) if self.xp else []
        self.xp_dots: Counter = Counter()
        for e in self.log:
            kind = e.get("kind")
            if kind in ("attribute", "skill"):
                self.xp_dots[(kind, _str(e.get("trait")))] += 1
            elif kind == "discipline":
                self.xp_dots[(kind, _norm(e.get("trait")))] += 1

        self.final_attrs = {k: _int(attrs.get(k)) for k in V5_ATTRIBUTES}
        self.final_skills: Dict[str, int] = {}
        for group in ("physical", "social", "mental"):
            g = self.skills_doc.get(group) if isinstance(self.skills_doc.get(group), dict) else {}
            for k in V5_SKILLS[group]:
                self.final_skills[k] = _int(g.get(k))
        self.creation_attrs = {k: v - self.xp_dots[("attribute", k)] for k, v in self.final_attrs.items()}
        self.creation_skills = {k: v - self.xp_dots[("skill", k)] for k, v in self.final_skills.items()}

        # Disciplines as stored (picks + predator dot + XP dots), with catalog names where known.
        self.discs: List[Tuple[str, int, list]] = []
        for d in _dicts(meta.get("disciplines")):
            name = _str(d.get("name"))
            if name and _int(d.get("level")) > 0:
                entry = cat.discipline(name)
                powers = d.get("powers") if isinstance(d.get("powers"), list) else []
                self.discs.append((entry["name"] if entry else name, _int(d.get("level")), powers))
        self.level = {_norm(n): lv for n, lv, _ in self.discs}

        self.advantages = _named_rows(meta.get("advantages"))
        self.flaws = _named_rows(meta.get("flaws"))
        self.rituals = _dicts(meta.get("rituals"))

    def creation_level(self, name: str) -> int:
        """A Discipline's dots before the starting XP (the picks and the predator dot)."""
        return self.level.get(_norm(name), 0) - self.xp_dots[("discipline", _norm(name))]

    def blood_potency(self) -> int:
        """deriveV5: the generation's starting BP, + ancilla and predator type, capped; thin-bloods 0."""
        row = _generation_row(self.gen or 13)
        if self.thin or (row and row[5]):
            return 0
        bp = row[4] if row and row[4] is not None else (row[2] if row else 1)
        bp += (self.bracket or AGE_BRACKETS["neonate"]).get("blood_potency_bonus", 0)
        bp += self.pred["blood_potency"] if self.pred else 0
        return min(bp, row[3]) if row else bp


def validate_creation(payload: Any, catalog: Any, settings: Any = None) -> List[Dict[str, Any]]:
    """Problems with a new V5 sheet as [{code, params}]; empty = it follows the creation rules."""
    p = _Problems()
    s = normalize_creation_settings(settings)
    cat = _Catalog(catalog)
    sh = _Sheet(payload, cat)
    _check_identity(p, sh)
    _check_attributes(p, sh)
    specialties = _check_skills(p, sh)
    _check_disciplines(p, sh, cat)
    _check_powers(p, sh, cat)
    _check_predator(p, sh, cat)
    _check_advantages(p, sh, cat, s)
    _check_experience(p, sh, cat, *specialties)
    _check_rituals(p, sh, cat)
    _check_settings(p, sh, s)
    _check_convictions(p, sh)
    _check_derived(p, sh, s)
    return p.items


def _check_identity(p: _Problems, sh: _Sheet) -> None:
    """Clan, age bracket and generation."""
    if not sh.clan:
        p.add("clan_missing", clan=sh.clan_raw if isinstance(sh.clan_raw, str) else None)
    if not sh.bracket:
        p.add("age_missing", age=sh.age)
    elif sh.gen not in sh.bracket["generations"]:
        gens = sh.bracket["generations"]
        p.add("age_generation", age=sh.age, generation=sh.gen, min=gens[0], max=gens[-1])
    if sh.thin and sh.gen < 14:
        p.add("thin_blood_generation", generation=sh.gen)
    if sh.clan and not sh.thin and sh.gen >= 14:
        p.add("generation_thin_blood", generation=sh.gen, clan=sh.clan_name)


def _check_attributes(p: _Problems, sh: _Sheet) -> None:
    """validateV5Attributes, before XP: 1-4, one at 4, three at 3, four at 2, one at 1."""
    vals = list(sh.creation_attrs.values())
    if any(v < 1 or v > 4 for v in vals):
        p.add("attr_range")
    elif sorted(vals, reverse=True) != sorted(ATTRIBUTE_SPREAD, reverse=True):
        p.add("attr_spread")


def _check_skills(p: _Problems, sh: _Sheet) -> Tuple[List[Tuple[str, str]], List[dict]]:
    """The Skill distribution and free specialties before XP, with the predator type's specialty:
    a `source: 'predator'` specialty, or one of the type's Skills raised from 0 to 1 (p. 149).
    Returns the creation specialties (keys) and the XP specialties, for the XP check."""
    specialties = [sp for sp in _dicts(sh.skills_doc.get("specialties")) if sp.get("skill") and _str(sp.get("name"))]
    pred_specs = [sp for sp in specialties if sp.get("source") == "predator"]
    xp_specs = [sp for sp in specialties if sp.get("source") == "xp"]
    free = [sp for sp in specialties if sp.get("source") not in ("predator", "xp")]
    # A first XP dot in Academics/Craft/Performance/Science brought its free specialty (no source).
    for i, e in enumerate(sh.log):
        if (
            e.get("kind") == "skill" and _int(e.get("from")) == 0
            and e.get("trait") in FREE_SPECIALTY_SKILLS and _str(e.get("specialty"))
        ):
            key = _spec_key(e.get("trait"), e.get("specialty"))
            hit = next((sp for sp in free if _spec_key(sp.get("skill"), sp.get("name")) == key), None)
            if hit is None:
                p.add("xp_log", index=i, trait=_str(e.get("trait")))
            else:
                free.remove(hit)

    pred = sh.pred
    pred_spec_ok = True
    bumps: List[Optional[str]] = [None]
    if pred:
        options = pred["specialties"]
        if len(pred_specs) > 1:
            pred_spec_ok = False
        elif len(pred_specs) == 1:
            sp = pred_specs[0]
            pred_spec_ok = any(sp.get("skill") == k and _loose_name_eq(sp.get("name"), n) for k, n in options)
        elif options:
            # No specialty: one of the type's Skills was at 0 and became 1, or nothing was picked.
            bumps = list(dict.fromkeys(k for k, _n in options if sh.creation_skills.get(k) == 1)) + [None]
    elif pred_specs and not _str(sh.pred_raw):
        pred_spec_ok = False

    results = []
    for b in bumps:
        pre = dict(sh.creation_skills)
        if b:
            pre[b] = 0
        results.append((b, _skill_problems(pre, sh.skills_doc.get("distribution")) + _specialty_problems(free, pre)))
    bump, errs = next((r for r in results if not r[1]), None) or min(results, key=lambda r: len(r[1]))
    for code, params in errs:
        p.add(code, **params)
    if pred and pred["specialties"] and not pred_specs and bump is None:
        pred_spec_ok = False
    if not pred_spec_ok:
        p.add("predator_specialty", predator=sh.pred_name or None)

    seen: List[Tuple[str, str]] = []
    for sp in free + pred_specs:
        key = _spec_key(sp.get("skill"), sp.get("name"))
        if key in seen:
            p.add("specialty_duplicate", skill=sp.get("skill"), name=_str(sp.get("name")))
        seen.append(key)
    return seen, xp_specs


def _check_disciplines(p: _Problems, sh: _Sheet, cat: _Catalog) -> None:
    """Two Disciplines at 2 and 1 dots in clan (Caitiff any, thin-bloods none), plus the predator
    type's dot on one of its options for the clan; XP dots come off first."""
    options = [] if not sh.pred or sh.thin else [
        n for n, clans in sh.pred["disciplines"] if not clans or sh.clan_name in clans
    ]
    if sh.pred and not sh.thin and not options:
        p.add("predator_discipline", predator=sh.pred_name)
    if sh.thin:
        if sh.discs:
            p.add("disc_thin_blood")
        return
    if not sh.clan:
        return
    names = [n for n, _, _ in sh.discs]
    if len({_norm(n) for n in names}) != len(names):
        p.add("disc_pick")
        return
    creation = {n: sh.creation_level(n) for n in names if sh.creation_level(n) > 0}
    in_clan = {_norm(d) for d in ([d for d in cat.discipline_list if d != ALCHEMY] if sh.caitiff else sh.clan["disciplines"])}

    def two_plus_one(levels: Dict[str, int]) -> bool:
        picked = sorted((lv for lv in levels.values() if lv > 0), reverse=True)
        return picked == sorted(DISCIPLINE_DOTS, reverse=True) and all(
            _norm(n) in in_clan for n, lv in levels.items() if lv > 0
        )

    def less_one(name: str) -> Dict[str, int]:
        return {n: lv - (1 if _norm(n) == _norm(name) else 0) for n, lv in creation.items()}

    if options:
        ok = any(_norm(o) in {_norm(n) for n in creation} and two_plus_one(less_one(o)) for o in options)
    else:
        ok = two_plus_one(creation)
    if ok:
        return
    allowed = in_clan | {_norm(o) for o in options}
    outside = [n for n in creation if _norm(n) not in allowed]
    if options and two_plus_one(creation):
        p.add("predator_discipline", predator=sh.pred_name)  # the 2 + 1 are there, the predator dot isn't
    elif outside:
        for n in outside:
            p.add("disc_clan", name=n, clan=sh.clan_name)
    else:
        p.add("disc_pick")


def _powers_taken(sh: _Sheet, cat: _Catalog, discipline: str) -> set:
    """Normalised names of the powers taken in a Discipline (the catalog name of an alias too)."""
    raw = next((r for n, _, r in sh.discs if _norm(n) == _norm(discipline)), [])
    names = {_norm(x) for x in (_power_name(v) for v in raw) if x}
    entry = cat.discipline(discipline)
    for pw in entry["powers"] if entry else []:
        if pw["keys"] & names:
            names.add(_norm(pw["name"]))
    return names


def _check_powers(p: _Problems, sh: _Sheet, cat: _Catalog) -> None:
    """validateV5Powers: each power of its Discipline, at most its rating, the amalgam Discipline
    at the printed level, the prerequisite taken, none twice in a Discipline, one per dot.
    A prerequisite may sit in another Discipline (Messenger's Command: Animal Messenger, and
    Compel or Mesmerize from Dominate). Disciplines the catalog has no powers for are free text."""
    pool = set().union(*(_powers_taken(sh, cat, n) for n, _, _ in sh.discs))
    for name, level, raw in sh.discs:
        entry = cat.discipline(name)
        if not entry or not entry["powers"]:
            continue
        chosen = [x for x in (_power_name(v) for v in raw) if x]
        if len(chosen) > level:
            p.add("power_count", discipline=name, have=len(chosen), max=level)
        taken = set()
        for pw_name in chosen:
            pw = next((x for x in entry["powers"] if _norm(pw_name) in x["keys"]), None)
            key = pw["id"] if pw else _norm(pw_name)
            if key in taken:
                p.add("power_duplicate", discipline=name, power=pw_name)
                continue
            taken.add(key)
            if not pw:
                p.add("power_unknown", discipline=name, power=pw_name)
                continue
            if pw["level"] > level:
                p.add("power_level", discipline=name, power=pw["name"], level=pw["level"], rating=level)
            if pw["amalgam"] and sh.level.get(_norm(pw["amalgam"][0]), 0) < pw["amalgam"][1]:
                p.add("power_amalgam", power=pw["name"], discipline=pw["amalgam"][0], level=pw["amalgam"][1])
            missing = next((g for g in pw["prerequisite"] if not any(_norm(x) in pool for x in g)), None)
            if missing:
                p.add("power_prereq", power=pw["name"], needs=" or ".join(missing))


def _check_predator(p: _Problems, sh: _Sheet, cat: _Catalog) -> None:
    """The predator type: chosen (thin-bloods may skip it), allowed for the clan and the age, under
    its Blood Potency cap, and its rows (kind 'predator') match its grants."""
    pred = sh.pred
    if not pred and (_str(sh.pred_raw) or not sh.thin):
        p.add("predator_missing", predator=_str(sh.pred_raw) or None)
    pred_adv = [r for r in sh.advantages if r.get("kind") == "predator"]
    pred_flaws = [r for r in sh.flaws if r.get("kind") == "predator"]
    if not pred:
        if pred_adv or pred_flaws:
            p.add("predator_grant", predator=_str(sh.pred_raw) or None)
        return
    if sh.clan_name and _norm(sh.clan_name) in {_norm(c) for c in pred["forbidden_clans"]}:
        p.add("predator_forbidden", predator=sh.pred_name, clan=sh.clan_name)
    if pred["ancilla_only"] and sh.age != "ancilla":
        p.add("predator_ancilla", predator=sh.pred_name)
    bp = sh.blood_potency()
    if pred["max_blood_potency"] is not None and bp > pred["max_blood_potency"]:
        p.add("predator_bp", predator=sh.pred_name, max=pred["max_blood_potency"], bp=bp)
    if not (_grants_ok(pred["advantages"], pred_adv, cat.adv_by_id) and _grants_ok(pred["flaws"], pred_flaws, cat.adv_by_id)):
        p.add("predator_grant", predator=sh.pred_name)


def _check_advantages(p: _Problems, sh: _Sheet, cat: _Catalog, s: Dict[str, Any]) -> None:
    """Own Advantages: at most 7 dots (+2 ancilla), the dots saved for later (wod_meta.saved,
    Forge v2 part D) included, so a sheet can't claim more saved dots than it left unspent; own
    Flaws: at least 2 (+2 ancilla) and at most the chronicle's cap; each row in its catalog range,
    or 1-5 when the catalog doesn't know it. The predator type's rows are extra (core p. 136).
    Thin-bloods: 1-3 thin-blood Merits and as many thin-blood Flaws."""
    bonus = AGE_BRACKETS["ancilla"] if sh.age == "ancilla" else {}
    adv_max = ADVANTAGE_DOTS + bonus.get("advantage_dots_bonus", 0)
    flaw_min = FLAWS_MIN_DOTS + bonus.get("flaw_dots_bonus", 0)
    own_adv = [r for r in sh.advantages if r.get("kind") != "predator"]
    own_flaws = [r for r in sh.flaws if r.get("kind") != "predator"]
    saved = sh.meta.get("saved") if isinstance(sh.meta.get("saved"), dict) else {}
    adv_dots = sum(_int(r.get("dots")) for r in own_adv) + max(0, _int(saved.get("advantage_dots")))
    flaw_dots = sum(_int(r.get("dots")) for r in own_flaws)
    if adv_dots > adv_max:
        p.add("adv_over", max=adv_max, have=adv_dots)
    if flaw_dots < flaw_min:
        p.add("flaw_under", min=flaw_min, have=flaw_dots)
    cap = s.get("flaws_max_dots")
    if cap is not None and flaw_dots > cap:
        p.add("flaw_over", max=cap, have=flaw_dots)
    _check_rows(p, cat, sh.clan, own_adv, own_flaws, sh.level)

    tb_merits = _names(sh.meta.get("thin_blood_merits"))
    tb_flaws = _names(sh.meta.get("thin_blood_flaws"))
    if sh.thin:
        lo, hi = THIN_BLOOD_MERITS
        if not (lo <= len(tb_merits) <= hi) or len(tb_flaws) != len(tb_merits):
            p.add("thin_blood_merits", merits=len(tb_merits), flaws=len(tb_flaws), min=lo, max=hi)
    elif sh.clan and (tb_merits or tb_flaws):
        p.add("thin_blood_only")


def _check_rituals(p: _Problems, sh: _Sheet, cat: _Catalog) -> None:
    """At creation one free Level 1 ritual (Blood Sorcery 1+) and one free Level 1 Oblivion
    ceremony (its prerequisite power taken); the XP ones match the XP log; at most RITUALS_MAX."""
    start = [r for r in sh.rituals if r.get("source") != "xp"]
    start_rituals = [r for r in start if (r.get("kind") or "ritual") != "ceremony"]
    start_ceremonies = [r for r in start if r.get("kind") == "ceremony"]
    if start_rituals:
        r = start_rituals[0]
        known = cat.rituals.get(_norm(r.get("name")))
        if (
            len(start_rituals) > 1
            or _int(r.get("level")) != 1
            or sh.level.get(_norm(BLOOD_SORCERY), 0) < 1
            or (known and known["level"] != 1)
        ):
            p.add("ritual_start")
    if start_ceremonies:
        c = start_ceremonies[0]
        known = cat.ceremonies.get(_norm(c.get("name")))
        taken = _powers_taken(sh, cat, OBLIVION)
        if (
            len(start_ceremonies) > 1
            or _int(c.get("level")) != 1
            or sh.level.get(_norm(OBLIVION), 0) < 1
            or (cat.ceremonies and not known)
            or (known and known["level"] != 1)
            or (known and any(not any(_norm(x) in taken for x in g) for g in known["prerequisite"]))
        ):
            p.add("ceremony_start")
    if len(sh.rituals) > RITUALS_MAX:
        p.add("ritual_count", max=RITUALS_MAX, have=len(sh.rituals))
    bought = Counter((_norm(r.get("name")), _int(r.get("level"))) for r in sh.rituals if r.get("source") == "xp")
    logged = Counter((_norm(e.get("trait")), _int(e.get("to"))) for e in sh.log if e.get("kind") == "ritual")
    if bought != logged:
        p.add("xp_log", index=None, trait="rituals")


def _check_settings(p: _Problems, sh: _Sheet, s: Dict[str, Any]) -> None:
    """The chronicle's allowed clans, predator types and ages (names case-insensitive)."""

    def allowed(key: str, value: str) -> bool:
        lst = s.get(key)
        return not lst or not value or _norm(value) in {_norm(x) for x in lst}

    if sh.clan_name and not allowed("allowed_clans", sh.clan_name):
        p.add("clan_not_allowed", clan=sh.clan_name)
    if sh.pred_name and not allowed("allowed_predators", sh.pred_name):
        p.add("predator_not_allowed", predator=sh.pred_name)
    if sh.age and s.get("allowed_ages") and sh.age not in s["allowed_ages"]:
        p.add("age_not_allowed", age=sh.age)


def _check_convictions(p: _Problems, sh: _Sheet) -> None:
    """1-3 Convictions, each with a Touchstone (wod_meta.touchstones: [{name, conviction}])."""
    convictions = [t for t in _dicts(sh.meta.get("touchstones")) if _str(t.get("conviction"))]
    lo, hi = CONVICTIONS
    if not (lo <= len(convictions) <= hi):
        p.add("conviction_count", min=lo, max=hi, have=len(convictions))
    elif any(not _str(t.get("name")) for t in convictions):
        p.add("conviction_pairs")


def _check_derived(p: _Problems, sh: _Sheet, s: Dict[str, Any]) -> None:
    """deriveV5's stored values: Humanity 7 (8 for a fledgling where the chronicle offers it) + the
    predator type, -1 for ancillae; Blood Potency; Hunger 1; Health and Willpower."""
    meta = sh.meta
    change = (sh.pred["humanity"] if sh.pred else 0) + (sh.bracket or AGE_BRACKETS["neonate"]).get("humanity_change", 0)
    want = max(0, min(10, STARTING_HUMANITY + change))
    fledgling = max(0, min(10, FLEDGLING_HUMANITY + change))
    humanity = meta.get("humanity")
    if humanity is not None:
        if sh.age == "childer" and _int(humanity) == fledgling and fledgling != want:
            if not s.get("fledgling_humanity_8", True):
                p.add("fledgling_not_allowed")
        elif _int(humanity) != want:
            p.add("derived_value", trait="humanity", have=_int(humanity), want=want)

    def track(key: str) -> Any:
        return meta[key].get("max") if isinstance(meta.get(key), dict) else None

    for trait, have, want_v in (
        ("blood_potency", meta.get("blood_potency"), sh.blood_potency()),
        ("hunger", meta.get("hunger"), STARTING_HUNGER),
        ("health", track("health"), sh.final_attrs["stamina"] + 3),
        ("willpower", track("willpower"), sh.final_attrs["composure"] + sh.final_attrs["resolve"]),
    ):
        if have is not None and _int(have) != want_v:
            p.add("derived_value", trait=trait, have=_int(have), want=want_v)


def _grants_ok(grants: List[dict], rows: List[dict], known_ids: Iterable[str] = ()) -> bool:
    """The predator rows match the type's grants exactly once: 'all' needs every option, 'one_of'
    one of them, 'split' its total across its options. Names: the forge's label ("Contacts
    (criminal)"), anything naming the option ("Looks: Beautiful", from the v5.json fallback), and
    for a group option ("any Mythic Flaw") any catalog entry of that group ("Folkloric Bane"). A
    row with an id (the advantages step stores it) must carry the option's id, or the picked
    entry's for a group, and still name it; an id the catalog doesn't know counts by the name."""
    known = set(known_ids)
    pool = [((_norm(r.get("name")), _sid(r.get("id"))), _int(r.get("dots"))) for r in rows]

    def names_it(name: str, opt: dict) -> bool:
        if any(n and n in name for n in opt["names"]):
            return True
        return bool(opt["members"]) and any(_norm(v) in opt["members"] for v in _name_variants(name))

    def matches(row: Tuple[str, str], opt: dict, strict: bool) -> bool:
        name, rid = row
        if rid and (rid == opt["id"] or rid in opt["member_ids"]):
            return name in opt["labels"] or names_it(name, opt)
        if rid and rid in known:  # another catalog entry
            return False
        return name in opt["labels"] if strict else names_it(name, opt)

    def dots_ok(opt: dict, dots: int) -> bool:
        return 1 <= dots <= 5 if opt["dots"] is None else dots == opt["dots"]

    def take(opts: List[dict]) -> Optional[int]:
        for strict in (True, False):
            for o in opts:
                for i, (row, dots) in enumerate(pool):
                    if matches(row, o, strict) and dots_ok(o, dots):
                        return i
        return None

    order = {"all": 0, "one_of": 1, "split": 2}
    for g in sorted(grants, key=lambda g: order.get(g["pick"], 0)):
        if g["pick"] == "split":
            idx = [i for i, (row, _d) in enumerate(pool) if any(matches(row, o, False) for o in g["options"])]
            total = sum(pool[i][1] for i in idx)
            if any(pool[i][1] < 1 for i in idx) or (g["dots_total"] is not None and total != g["dots_total"]):
                return False
            pool = [x for i, x in enumerate(pool) if i not in idx]
        elif g["pick"] == "one_of":
            i = take(g["options"])
            if i is None:
                return False
            pool.pop(i)
        else:
            for o in g["options"]:
                i = take([o])
                if i is None:
                    return False
                pool.pop(i)
    return not pool


def _dots_range(entry: dict) -> Optional[Tuple[int, int, Optional[List[int]]]]:
    """(min, max, allowed) from a catalog entry's dots: {min, max}, {allowed: [...]} or n; None when
    it has no rating. An open maximum ('•+', max null) stays at 5, as for any trait at creation."""

    def num(v: Any) -> Optional[int]:
        return v if isinstance(v, int) and not isinstance(v, bool) else None

    d = entry.get("dots")
    if num(d) is not None:
        return (d, d, None)
    if isinstance(d, dict):
        allowed = [x for x in _list(d.get("allowed")) if num(x) is not None]
        if allowed:
            return (min(allowed), max(allowed), allowed)
        lo = num(d.get("min")) if num(d.get("min")) is not None else num(d.get("fixed"))
        if lo is not None:
            hi = num(d.get("max")) if num(d.get("max")) is not None else (lo if "fixed" in d else 5)
            return (lo, hi, None)
    return None


def _check_rows(p: _Problems, cat: _Catalog, clan: Optional[dict], own_adv: List[dict],
                own_flaws: List[dict], final_level: Dict[str, int]) -> None:
    """Each own Advantage/Flaw row: a custom row needs the Storyteller (custom_row); a loresheet
    row costs its levels; any other row keeps to its catalog rating when advantages.json knows it
    (Allies 1-6, Mask 1 or 2), else 1-5. With the catalogs installed also the clan restrictions,
    and a row whose id and name both don't resolve is refused; Caitiff list no Status."""
    clan_keys = {_norm(clan["name"]), _norm(clan["id"])} if clan else set()

    def in_clans(ids: Iterable[Any]) -> bool:
        return any(_norm(c) in clan_keys or _norm(cat.clan_name(c)) in clan_keys for c in ids)

    for row, flaw in [(r, False) for r in own_adv] + [(r, True) for r in own_flaws]:
        name, dots, rid = _str(row.get("name")), _int(row.get("dots")), _sid(row.get("id"))
        if row.get("custom") is True:
            # The forge's "Custom (Storyteller approval)" row: free text, so only an override takes it.
            p.add("custom_row", name=name)
            if dots < 1 or dots > 5:
                p.add("adv_dots_range", name=name, dots=dots, min=1, max=5)
            continue
        loresheet_row = rid.startswith("loresheet:") or row.get("kind") == "loresheet"
        ls = entry = None
        # An id is only looked up when its catalog is installed (advantages.json / loresheets.json).
        if not rid or (cat.loresheets if rid.startswith("loresheet:") else cat.advantages):
            if not flaw and row.get("kind") in (None, "loresheet", "merit", "background"):
                ls = cat.loresheet(row)
            if ls is None and not loresheet_row:
                entry = cat.advantage(row, flaw, clan)
            if rid and ls is None and entry is None:
                p.add("adv_unknown", name=name)
        if row.get("kind") == "loresheet":
            _check_loresheet_levels(p, row, ls)
        else:
            lo, hi, allowed = (_dots_range(entry) if entry else None) or (1, 5, None)
            if dots < lo or dots > hi or (allowed and dots not in allowed):
                p.add("adv_dots_range", name=name, dots=dots, min=lo, max=hi)
        if not clan:
            continue
        if ls is not None and (
            (_strs(ls.get("clans_only")) and not in_clans(_strs(ls.get("clans_only"))))
            or (ls.get("thin_blood_only") is True and not clan["thin_blood"])
            or (_strs(ls.get("disciplines_only")) and not any(
                final_level.get(_norm(cat.disc_names.get(d) or _name_from_id(d)), 0) > 0
                for d in _strs(ls.get("disciplines_only"))))
        ):
            p.add("loresheet_restricted", name=name, clan=clan["name"])
        if entry is not None and (
            any(
                isinstance(c, dict) and (_norm(c.get("clan")) in clan_keys or _norm(cat.clan_name(c.get("clan"))) in clan_keys)
                for c in _list(entry.get("cannot_buy_for"))
            )
            or (_strs(entry.get("clans_only")) and not in_clans(_strs(entry.get("clans_only"))))
            or (entry.get("caitiff") is True and not clan["caitiff"])
            or (entry.get("thin_blood") is True and not clan["thin_blood"])
            or entry.get("ghoul_only") is True
            # a coterie's Background, not one character's (the forge never offers them either)
            or entry.get("coterie") is True
        ):
            p.add("adv_restricted", name=name, clan=clan["name"])
        # Caitiff start without positive Status (core p. 107): only a Status row they list.
        is_status = (
            (entry.get("kind") == "background" and _norm(entry.get("group")) == "status") if entry is not None
            else not flaw and not loresheet_row and "status" in {_norm(v) for v in _name_variants(name)}
        )
        if (clan["caitiff"] or clan["no_positive_status"]) and is_status and dots > 0:
            p.add("caitiff_status", clan=clan["name"])


def check_advantage_rows(meta: Any, rows: Any, catalog: Any) -> List[Dict[str, Any]]:
    """
    validate_creation's per-row check (catalog rating, Allies 1-6 and Mask 1 or 2 included,
    loresheet levels and restrictions, clan restrictions, custom rows) for Advantage rows of the
    sheet whose wod_meta is `meta` (its clan and Disciplines). services/saved_points.py checks the
    rows a saved-point spend makes with it, so both use one code path.
    """
    p = _Problems()
    cat = _Catalog(catalog)
    sh = _Sheet({"wod_meta": meta if isinstance(meta, dict) else {}}, cat)
    _check_rows(p, cat, sh.clan, _named_rows(rows), [], sh.level)
    return p.items


def advantage_entries(meta: Any, rows: Any, catalog: Any) -> List[Optional[dict]]:
    """The catalog entry (advantages.json / loresheets.json) each named Advantage row is, found
    the way validate_creation finds it (id, else name or alias; the clan's own first), or None."""
    cat = _Catalog(catalog)
    sh = _Sheet({"wod_meta": meta if isinstance(meta, dict) else {}}, cat)
    out: List[Optional[dict]] = []
    for row in _named_rows(rows):
        if row.get("kind") == "loresheet" or _sid(row.get("id")).startswith("loresheet:"):
            out.append(cat.loresheet(row))
        else:
            out.append(cat.advantage(row, False, sh.clan))
    return out


def _check_loresheet_levels(p: _Problems, row: dict, ls: Optional[dict]) -> None:
    """A loresheet row ({kind: 'loresheet', dots, levels: [n, ...]}): each level is an Advantage of
    its own, bought separately at its rating, and doesn't bring the lower ones (core p. 190), so
    levels are 1-5 (the sheet's), each once, and the dots are their sum (2 + 4 = 6 is fine)."""
    levels = row.get("levels")
    ints = [x for x in _list(levels) if isinstance(x, int) and not isinstance(x, bool)]
    valid = {lv.get("dots") for lv in _dicts(ls.get("levels"))} if ls else set()
    valid = {x for x in valid if isinstance(x, int) and not isinstance(x, bool)} or set(range(1, 6))
    if (
        not ints
        or len(ints) != len(_list(levels))
        or len(set(ints)) != len(ints)
        or any(x not in valid for x in ints)
        or sum(ints) != _int(row.get("dots"))
    ):
        p.add("loresheet_levels", name=_str(row.get("name")), dots=_int(row.get("dots")), levels=ints)


def _check_experience(p: _Problems, sh: _Sheet, cat: _Catalog, seen_specialties: List[Tuple[str, str]],
                      xp_specs: List[dict]) -> None:
    """xpLedger re-priced: the age's XP, each dot one at a time at new x the multiplier (clan /
    other / Caitiff Discipline), specialties flat, rituals level x 3 up to Blood Sorcery."""
    xp = sh.xp
    if xp is None:
        return
    total_xp = 0 if sh.thin else (sh.bracket or {}).get("xp", 0)
    if not total_xp:
        if sh.log:
            p.add("xp_none")
        elif _int(xp.get("total")) != 0:
            p.add("xp_total", have=_int(xp.get("total")), want=0)
        return
    if _int(xp.get("total")) != total_xp:
        p.add("xp_total", have=_int(xp.get("total")), want=total_xp)
    clan_discs = {_norm(d) for d in (sh.clan or {}).get("disciplines") or []}
    caitiff_mult = (sh.clan or {}).get("xp_multiplier") or XP_COSTS["caitiff_discipline"]
    bs_level = sh.level.get(_norm(BLOOD_SORCERY), 0)
    at: Dict[Tuple[str, str], int] = {}
    seen = list(seen_specialties)
    xp_spec_left = Counter(_spec_key(sp.get("skill"), sp.get("name")) for sp in xp_specs)
    spent = 0
    for i, e in enumerate(sh.log):
        kind = e.get("kind")
        trait = _str(e.get("trait"))
        frm, to, cost = _int(e.get("from")), _int(e.get("to")), _int(e.get("cost"))
        if kind in ("attribute", "skill", "discipline"):
            if kind == "attribute" and trait in sh.creation_attrs:
                base, mult = sh.creation_attrs[trait], XP_COSTS["attribute"]
            elif kind == "skill" and trait in sh.creation_skills:
                base, mult = sh.creation_skills[trait], XP_COSTS["skill"]
            elif kind == "discipline" and not sh.thin and cat.discipline(trait) and _norm(trait) != _norm(ALCHEMY):
                base = sh.creation_level(trait)  # below 0: the log buys dots the sheet hasn't got
                mult = (
                    caitiff_mult if sh.caitiff
                    else XP_COSTS["clan_discipline"] if _norm(trait) in clan_discs
                    else XP_COSTS["other_discipline"]
                )
            else:
                p.add("xp_log", index=i, trait=trait)
                continue
            key = (kind, _norm(trait))
            want_from = at.get(key, base)
            at[key] = want_from + 1
            if base < 0 or frm != want_from or to != want_from + 1:
                p.add("xp_log", index=i, trait=trait)
            if want_from + 1 > XP_MAX_DOTS:
                p.add("xp_max_dots", trait=trait, max=XP_MAX_DOTS)
            want_cost = (want_from + 1) * mult
            if kind == "skill" and want_from == 0 and trait in FREE_SPECIALTY_SKILLS:
                free_name = _str(e.get("specialty"))
                if not free_name:
                    p.add("specialty_missing", skill=trait)
                else:
                    if len(free_name) > NAME_MAX:
                        p.add("name_length", max=NAME_MAX)
                    k = _spec_key(trait, free_name)
                    if k in seen:
                        p.add("specialty_duplicate", skill=trait, name=free_name)
                    seen.append(k)
        elif kind == "specialty":
            skill = e.get("skill")
            if skill not in SKILL_KEYS or not trait or frm != 0 or to != 1:
                p.add("xp_log", index=i, trait=trait)
                continue
            if len(trait) > NAME_MAX:
                p.add("name_length", max=NAME_MAX)
            k = _spec_key(skill, trait)
            if k in seen:
                p.add("specialty_duplicate", skill=skill, name=trait)
            seen.append(k)
            if sh.final_skills.get(skill, 0) < 1:
                p.add("specialty_skill", skill=skill)
            if xp_spec_left[k] > 0:
                xp_spec_left[k] -= 1
            else:
                p.add("xp_log", index=i, trait=trait)
            want_cost = XP_COSTS["specialty"]
        elif kind == "ritual":
            if not trait or frm != 0 or not (1 <= to <= XP_MAX_DOTS):
                p.add("xp_log", index=i, trait=trait)
                continue
            if len(trait) > NAME_MAX:
                p.add("name_length", max=NAME_MAX)
            if to > bs_level:
                p.add("ritual_blood_sorcery", name=trait, level=to, rating=bs_level)
            known = cat.rituals.get(_norm(trait))
            if known and known["level"] != to:
                p.add("ritual_level", name=known["name"], level=to, want=known["level"])
            want_cost = to * XP_COSTS["ritual"]
        else:
            p.add("xp_log", index=i, trait=trait)
            continue
        if cost != want_cost:
            p.add("xp_price", index=i, trait=trait, cost=cost, want=want_cost)
        spent += want_cost
    if any(n > 0 for n in xp_spec_left.values()):
        p.add("xp_log", index=None, trait="specialties")
    if spent > total_xp:
        p.add("xp_over", spent=spent, total=total_xp)
