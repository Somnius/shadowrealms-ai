"""
V5 ghoul creation check on the server (docs/rules/V5.md §7).

    validate_ghoul_creation(payload, catalog, settings, domitor) -> [{"code": str, "params": dict}]

A ghoul's sheet is a V5 row with wod_meta.sheet_kind = 'ghoul' and a wod_meta.ghoul block
(docs/CHARACTER_SHEET_BLOCKS.md). It is built on one of five templates (wod_meta.ghoul.template):

- the corebook's mortal templates (p. 185), what the domitor's Retainers buy (p. 194): 'weak',
  'average', 'gifted', 'deadly': a fixed Attribute spread and Skill distribution, a number of
  specialties, up to N Advantage points and up to M Flaw points (no minimum);
- 'player', the Players Guide's ghoul (pp. 140-142): the vampire Attribute spread and Skill
  distributions, 7 Advantage dots and at least 2 Flaw dots, Humanity 7, 1-3 Convictions.

Every ghoul has one level-1 power of a Discipline its domitor has (core p. 234, Players Guide
p. 141), stored as a wod_meta.disciplines row at level 1. Advantages are checked against the catalog
as for vampires (services/v5_chargen.py), without the clan rules; ghoul-only entries are open, and
the Domain, Feeding and Herd groups and the thin-blood, Caitiff and coterie entries are not (PG
p. 141). House readings (Flaws on top of the Advantage points, the automatic specialties with a
template, Humanity optional on a retainer, the first power one the domitor has) are documented in
V5.md §7; a Storyteller who reads them otherwise uses the creation override.

`domitor` is the domitor's row ({id, name, user_id, campaign_id, rules_edition, wod_meta}) or None
(then the checks that need it are skipped). Codes are shared with the client (i18nErrors.js) and
the shared vectors (docs/rules/v5/tests/creation-cases.json, kind 'ghoul'). Pure: no Flask, no
DB; never raises on malformed input.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from services.character_sheet_v5 import GHOUL_TEMPLATES, is_ghoul
from services.creation_settings import normalize_creation_settings
from services.v5_chargen import (  # the vampire check's readers, shared on purpose
    ADVANTAGE_DOTS,
    ATTRIBUTE_SPREAD,
    CONVICTIONS,
    FLAWS_MIN_DOTS,
    FREE_SPECIALTY_SKILLS,
    NAME_MAX,
    SKILL_KEYS,
    STARTING_HUMANITY,
    _Catalog,
    _check_exclusions,
    _check_rows,
    _dicts,
    check_repeats,
    _int,
    _name_variants,
    _norm,
    _power_name,
    _Problems,
    _Sheet,
    _sid,
    _skill_problems,
    _spec_key,
    _specialty_problems,
    _str,
    requirement_met,
)

# ---------- rule constants (docs/rules/v5.json mortal_templates / ghoul; test_v5_ghoul_chargen.py checks them) ----------

MORTAL_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "weak": {"attributes": (2, 2, 1, 1, 1, 1, 1, 1, 1), "skills": {2: 3, 1: 5}, "specialties": 0,
             "advantages_max": 0, "flaws_max": 0, "retainer_dots": 1},
    "average": {"attributes": (3, 3, 2, 2, 2, 1, 1, 1, 1), "skills": {3: 3, 2: 4, 1: 5}, "specialties": 0,
                "advantages_max": 3, "flaws_max": 2, "retainer_dots": 2},
    "gifted": {"attributes": (4, 3, 3, 2, 2, 1, 1, 1, 1), "skills": {4: 2, 3: 4, 2: 4, 1: 4}, "specialties": 1,
               "advantages_max": 10, "flaws_max": 4, "retainer_dots": 3},
    "deadly": {"attributes": (5, 5, 4, 4, 3, 3, 2, 2, 2), "skills": {5: 1, 4: 3, 3: 5, 2: 6}, "specialties": 3,
               "advantages_max": 15, "flaws_max": 0, "retainer_dots": None},
}
PLAYER = "player"
POWERS_AT_CREATION = 1
POWER_LEVEL = 1
GHOUL_HUMANITY = STARTING_HUMANITY  # PG p. 142: ghouls start at Humanity 7
RETAINER_CONVICTIONS = (0, 3)
# Retainers •• buys a ghoul built with no Advantages (core p. 194): an Average ghoul at Retainers 2.
RETAINER_GHOUL_NO_ADVANTAGES_AT = 2
CANNOT_BUY_GROUPS = ("Domain", "Feeding", "Herd")
CANNOT_BUY_FLAGS = ("thin_blood", "caitiff", "coterie")
BOND_STRENGTH_MAX = 6
BONDS_MAX = 2
TWO_MASTERS = "flaw:two-masters"
CRONES_CURSE = "flaw:ghoul-crones-curse"
CRONES_CURSE_HEALTH = -1
# wod_meta keys only a vampire has: a ghoul's sheet leaves them out (its age is wod_meta.ghoul.age).
# Not `experience`: ghouls earn XP too (Players Guide p. 141), the app just doesn't spend it yet.
VAMPIRE_FIELDS = ("clan", "sire", "generation", "age", "predator_type", "hunger", "blood_potency",
                  "saved", "rituals", "thin_blood_merits", "thin_blood_flaws")

# Every code validate_ghoul_creation can return (the client's translations cover the same list).
GHOUL_PROBLEM_CODES = (
    "ghoul_template", "ghoul_domitor", "ghoul_retainer_dots", "ghoul_vampire_field",
    "ghoul_attr_spread", "skill_dist", "ghoul_specialty_count", "ghoul_template_specialty", "specialty_count",
    "specialty_skill", "specialty_missing", "specialty_duplicate", "name_length",
    "ghoul_power_count", "ghoul_power_level", "ghoul_power_discipline", "ghoul_power_not_domitors", "power_unknown",
    "adv_over", "flaw_under", "ghoul_flaws_over", "flaw_over", "adv_dots_range", "adv_unknown", "loresheet_levels",
    "custom_row", "book_not_allowed", "adv_requires", "adv_excluded", "adv_repeat", "ghoul_adv_restricted",
    "ghoul_bonds", "derived_value", "conviction_count", "conviction_pairs",
)


def _obj(v: Any) -> Dict[str, Any]:
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return {}
    return v if isinstance(v, dict) else {}


def _present(v: Any) -> bool:
    return v not in (None, "", [], {})


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _has_entry(rows: List[dict], entry_id: str) -> bool:
    """A row of this catalog id, or named after it ('Two Masters', 'Crone's Curse (…)')."""
    name = _norm(entry_id.split(":")[-1].replace("ghoul-", "").replace("-", " "))
    for r in rows:
        if _sid(r.get("id")) == entry_id:
            return True
        names = {_norm(n).replace("'", "").replace("’", "") for n in _name_variants(r.get("name"))}
        if name in names:
            return True
    return False


class _Domitor:
    """The domitor's row as the check reads it: its Disciplines (catalog names) and their powers."""

    def __init__(self, row: Any, cat: _Catalog) -> None:
        self.row = row if isinstance(row, dict) else None
        meta = _obj(self.row.get("wod_meta")) if self.row else {}
        self.meta = meta
        self.discs: Dict[str, set] = {}
        for d in _dicts(meta.get("disciplines")):
            name = _str(d.get("name"))
            if not name or _int(d.get("level")) < 1:
                continue
            entry = cat.discipline(name)
            key = _norm(entry["name"] if entry else name)
            powers = {_norm(x) for x in (_power_name(v) for v in (d.get("powers") if isinstance(d.get("powers"), list) else [])) if x}
            for pw in entry["powers"] if entry else []:
                if pw["keys"] & powers:
                    powers.add(_norm(pw["name"]))
            self.discs.setdefault(key, set()).update(powers)

    def is_vampire(self) -> bool:
        r = self.row or {}
        v5 = _str(r.get("rules_edition")).lower() == "v5" or _str(self.meta.get("edition")).lower() == "v5"
        system = _str(r.get("system_type")).lower()
        return v5 and system in ("", "vampire") and not is_ghoul(self.meta)


def validate_ghoul_creation(payload: Any, catalog: Any, settings: Any = None, domitor: Any = None) -> List[Dict[str, Any]]:
    """Problems with a new ghoul's sheet as [{code, params}]; empty = it follows the creation rules."""
    p = _Problems()
    s = normalize_creation_settings(settings)
    cat = _Catalog(catalog)
    sh = _Sheet(payload, cat)
    meta = sh.meta
    g = _obj(meta.get("ghoul"))
    template = g.get("template") if isinstance(g.get("template"), str) else None
    tpl = MORTAL_TEMPLATES.get(template) if template else None
    if template not in GHOUL_TEMPLATES:
        p.add("ghoul_template", template=template)
    dom = _Domitor(domitor, cat) if domitor is not None else None
    _check_vampire_fields(p, sh)
    _check_domitor(p, g, dom)
    _check_retainer_dots(p, g, template, tpl)
    if tpl or template == PLAYER:
        _check_attributes(p, sh, template, tpl)
        _check_skills(p, sh, template, tpl)
        _check_budget(p, sh, template, tpl, g, s)
    _check_power(p, sh, cat, dom)
    _check_rows_of(p, sh, cat, s)
    _check_bonds(p, sh, g)
    _check_derived(p, sh, template)
    _check_convictions(p, sh, template == PLAYER)
    return p.items


def _check_vampire_fields(p: _Problems, sh: _Sheet) -> None:
    """Keys only a vampire's sheet has (clan, generation, Hunger, predator type rows...)."""
    for k in VAMPIRE_FIELDS:
        if _present(sh.meta.get(k)):
            p.add("ghoul_vampire_field", field=k)
    if any(r.get("kind") == "predator" for r in sh.advantages + sh.flaws):
        p.add("ghoul_vampire_field", field="predator_rows")


def _check_domitor(p: _Problems, g: Dict[str, Any], dom: Optional[_Domitor]) -> None:
    """wod_meta.ghoul.domitor names a character; given its row, that row is a V5 vampire."""
    cid = _obj(g.get("domitor")).get("character_id")
    if not _is_int(cid) or cid < 1:
        p.add("ghoul_domitor", why="missing")
    elif dom is not None:
        if _int((dom.row or {}).get("id")) != cid:
            p.add("ghoul_domitor", why="mismatch")
        elif not dom.is_vampire():
            p.add("ghoul_domitor", why="not_vampire")


def _check_retainer_dots(p: _Problems, g: Dict[str, Any], template: Optional[str], tpl: Optional[dict]) -> None:
    """The Retainers dots the domitor pays, when the sheet names them, are the template's (core
    p. 194, one to one: • Weak, •• Average, ••• Gifted; no rating buys a Deadly mortal)."""
    dots = g.get("retainer_dots")
    if not tpl or not _is_int(dots):
        return
    need = tpl["retainer_dots"]
    if need is None or dots != need:
        p.add("ghoul_retainer_dots", template=template, dots=dots, need=need)


def _check_attributes(p: _Problems, sh: _Sheet, template: str, tpl: Optional[dict]) -> None:
    """The template's spread (a player ghoul: the vampire one, PG p. 140)."""
    spread = tpl["attributes"] if tpl else ATTRIBUTE_SPREAD
    vals = sorted(sh.final_attrs.values(), reverse=True)
    if vals != sorted(spread, reverse=True):
        p.add("ghoul_attr_spread", template=template)


def _check_skills(p: _Problems, sh: _Sheet, template: str, tpl: Optional[dict]) -> None:
    """The template's Skill counts (its key is skills.distribution), or a player ghoul's distribution
    (PG p. 141); specialties: the template's own plus one per rated Academics/Craft/Performance/
    Science (house reading), or the vampire rule for a player ghoul."""
    skills = sh.final_skills
    dist_key = sh.skills_doc.get("distribution")
    for code, params in _skill_problems(skills, dist_key, {template: tpl["skills"]} if tpl else None):
        p.add(code, **params)
    specs = [sp for sp in _dicts(sh.skills_doc.get("specialties")) if sp.get("skill") and _str(sp.get("name"))]
    if tpl is None:
        for code, params in _specialty_problems(specs, skills):
            p.add(code, **params)
    else:
        allowed = tpl["specialties"] + sum(1 for k in FREE_SPECIALTY_SKILLS if skills.get(k, 0) > 0)
        if len(specs) > allowed:
            p.add("ghoul_specialty_count", template=template, max=allowed, have=len(specs))
        _check_template_specialties(p, specs, skills, template, tpl)
        for sp in specs:
            if sp.get("skill") not in SKILL_KEYS or skills.get(sp.get("skill"), 0) < 1:
                p.add("specialty_skill", skill=sp.get("skill"))
        for k in FREE_SPECIALTY_SKILLS:
            if skills.get(k, 0) > 0 and not any(sp.get("skill") == k for sp in specs):
                p.add("specialty_missing", skill=k)
    seen = set()
    for sp in specs:
        if len(_str(sp.get("name"))) > NAME_MAX:
            p.add("name_length", max=NAME_MAX)
        key = _spec_key(sp.get("skill"), sp.get("name"))
        if key in seen:
            p.add("specialty_duplicate", skill=sp.get("skill"), name=_str(sp.get("name")))
        seen.add(key)


def template_specialties(specs: List[dict], skills: Dict[str, int]) -> List[dict]:
    """The template's own specialties: all but the first one on each rated Academics, Craft,
    Performance or Science (that one is the free specialty, core p. 159)."""
    free_taken: set = set()
    out = []
    for sp in specs:
        k = sp.get("skill")
        if k in FREE_SPECIALTY_SKILLS and skills.get(k, 0) > 0 and k not in free_taken:
            free_taken.add(k)
            continue
        out.append(sp)
    return out


def _check_template_specialties(p: _Problems, specs: List[dict], skills: Dict[str, int], template: str,
                                tpl: dict) -> None:
    """The template's own specialties are all there (Gifted 1, Deadly 3; core p. 185), and the Gifted
    one sits on one of its two Skills at 4 ("two at 4, one with a specialty")."""
    own = template_specialties(specs, skills)
    need = tpl["specialties"]
    if len(own) < need:
        p.add("ghoul_template_specialty", template=template, why="count", need=need, have=len(own))
    elif template == "gifted" and need and not any(skills.get(sp.get("skill"), 0) == 4 for sp in own):
        p.add("ghoul_template_specialty", template=template, why="rating", need=need, have=len(own))


def _check_budget(p: _Problems, sh: _Sheet, template: str, tpl: Optional[dict], g: Dict[str, Any],
                  s: Dict[str, Any]) -> None:
    """Advantage and Flaw dots: the template's caps (no minimum), a Retainers •• ghoul none at all
    (core p. 194); a player ghoul 7 and at least 2 (PG p. 141); the chronicle's Flaw cap on top."""
    adv = sum(_int(r.get("dots")) for r in sh.advantages if r.get("kind") != "predator")
    flaws = sum(_int(r.get("dots")) for r in sh.flaws if r.get("kind") != "predator")
    if tpl is None:
        adv_max, flaw_min, flaw_max = ADVANTAGE_DOTS, FLAWS_MIN_DOTS, None
    else:
        no_adv = template == "average" and g.get("retainer_dots") == RETAINER_GHOUL_NO_ADVANTAGES_AT
        adv_max, flaw_min, flaw_max = (0 if no_adv else tpl["advantages_max"]), 0, tpl["flaws_max"]
    if adv > adv_max:
        p.add("adv_over", max=adv_max, have=adv)
    if flaws < flaw_min:
        p.add("flaw_under", min=flaw_min, have=flaws)
    if flaw_max is not None and flaws > flaw_max:
        p.add("ghoul_flaws_over", template=template, max=flaw_max, have=flaws)
    cap = s.get("flaws_max_dots")
    if cap is not None and flaws > cap:
        p.add("flaw_over", max=cap, have=flaws)


def _check_power(p: _Problems, sh: _Sheet, cat: _Catalog, dom: Optional[_Domitor]) -> None:
    """One level-1 power, of a Discipline the domitor has; the power itself one the domitor has when
    its sheet lists powers (core p. 234: the level-1 power is one the vampire has)."""
    rows = [d for d in _dicts(sh.meta.get("disciplines")) if _str(d.get("name"))]
    chosen = [(d, x) for d in rows for x in (_power_name(v) for v in (d.get("powers") if isinstance(d.get("powers"), list) else [])) if x]
    if len(chosen) != POWERS_AT_CREATION:
        p.add("ghoul_power_count", have=len(chosen), want=POWERS_AT_CREATION)
    for d in rows:
        entry = cat.discipline(d.get("name"))
        name = entry["name"] if entry else _str(d.get("name"))
        if _int(d.get("level")) != POWER_LEVEL:
            p.add("ghoul_power_level", discipline=name, power=None, level=_int(d.get("level")))
        if dom is not None and _norm(name) not in dom.discs:
            p.add("ghoul_power_discipline", discipline=name)
        for row, pw_name in chosen:
            if row is not d:
                continue
            pw = next((x for x in entry["powers"] if _norm(pw_name) in x["keys"]), None) if entry and entry["powers"] else None
            if entry and entry["powers"] and pw is None:
                p.add("power_unknown", discipline=name, power=pw_name)
                continue
            if pw is not None and pw["level"] > POWER_LEVEL:
                p.add("ghoul_power_level", discipline=name, power=pw["name"], level=pw["level"])
                continue
            have = dom.discs.get(_norm(name)) if dom is not None else None
            names = (pw["keys"] | {_norm(pw["name"])}) if pw else {_norm(pw_name)}
            if have and not (names & have):
                p.add("ghoul_power_not_domitors", discipline=name, power=pw["name"] if pw else pw_name)


def _restriction(entry: Optional[dict], loresheet: bool) -> Optional[str]:
    """Why a ghoul can't take a catalog entry (PG p. 141), or None."""
    if entry is None:
        return None
    if loresheet:
        return "thin_blood" if entry.get("thin_blood_only") is True else None
    group = _norm(entry.get("group"))
    for g in CANNOT_BUY_GROUPS:
        if group == _norm(g):
            return g.lower()
    return next((f for f in CANNOT_BUY_FLAGS if entry.get(f) is True), None)


def _check_rows_of(p: _Problems, sh: _Sheet, cat: _Catalog, s: Dict[str, Any]) -> None:
    """The vampire row rules without a clan (ratings, custom rows, loresheet levels, books,
    requirements, exclusions), then what ghouls can't buy."""
    own_adv = [r for r in sh.advantages if r.get("kind") != "predator"]
    own_flaws = [r for r in sh.flaws if r.get("kind") != "predator"]
    _check_rows(p, cat, None, own_adv, own_flaws, sh.access, s)
    if not cat.advantages and not cat.loresheets:
        return
    for row, flaw in [(r, False) for r in own_adv] + [(r, True) for r in own_flaws]:
        if row.get("custom") is True:
            continue
        lore = not flaw and (row.get("kind") == "loresheet" or _sid(row.get("id")).startswith("loresheet:"))
        entry = cat.loresheet(row) if lore else cat.advantage(row, flaw, None)
        why = _restriction(entry, lore)
        if why:
            p.add("ghoul_adv_restricted", name=_str(row.get("name")), why=why)
        if entry is not None and not lore and requirement_met(entry, _int(row.get("dots")), sh.advantages, sh.level,
                                                              None, cat) is False:
            p.add("adv_requires", name=_str(row.get("name")), requires=_str(entry.get("requires")))
    _check_exclusions(p, sh, cat)
    check_repeats(p, cat, sh.advantages, sh.flaws, own_adv + own_flaws, None)


def _check_bonds(p: _Problems, sh: _Sheet, g: Dict[str, Any]) -> None:
    """1-2 Blood Bonds, the first to the domitor, strength 0-6 or not set (core pp. 233-234); a
    second only with the Two Masters Flaw (Blood-Stained Love p. 151)."""
    bonds = g.get("bonds")
    rows = _dicts(bonds)
    if not isinstance(bonds, list) or not 1 <= len(bonds) <= BONDS_MAX or len(rows) != len(bonds):
        p.add("ghoul_bonds", why="count")
        return
    cid = _obj(g.get("domitor")).get("character_id")
    if rows[0].get("character_id") != cid:
        p.add("ghoul_bonds", why="domitor")
    for b in rows:
        st = b.get("strength")
        if st is not None and not (_is_int(st) and 0 <= st <= BOND_STRENGTH_MAX):
            p.add("ghoul_bonds", why="strength")
    if len(rows) > 1 and not _has_entry(sh.flaws, TWO_MASTERS):
        p.add("ghoul_bonds", why="two_masters")


def _check_derived(p: _Problems, sh: _Sheet, template: Optional[str]) -> None:
    """Health Stamina + 3 (one less with Crone's Curse, PG p. 141), Willpower Composure + Resolve;
    Humanity 7 when the sheet tracks it (a player ghoul always does, PG p. 142)."""
    meta = sh.meta
    humanity = meta.get("humanity")
    if humanity is None and template == PLAYER:
        p.add("derived_value", trait="humanity", have=0, want=GHOUL_HUMANITY)
    elif humanity is not None and _int(humanity) != GHOUL_HUMANITY:
        p.add("derived_value", trait="humanity", have=_int(humanity), want=GHOUL_HUMANITY)
    crone = CRONES_CURSE_HEALTH if _has_entry(sh.flaws, CRONES_CURSE) else 0

    def track(key: str) -> Any:
        return meta[key].get("max") if isinstance(meta.get(key), dict) else None

    for trait, have, want in (
        ("health", track("health"), sh.final_attrs["stamina"] + 3 + crone),
        ("willpower", track("willpower"), sh.final_attrs["composure"] + sh.final_attrs["resolve"]),
    ):
        if have is not None and _int(have) != want:
            p.add("derived_value", trait=trait, have=_int(have), want=want)


def _check_convictions(p: _Problems, sh: _Sheet, player: bool) -> None:
    """Convictions with their Touchstones: 1-3 for a player ghoul (PG p. 142), up to 3 on a retainer."""
    convictions = [t for t in _dicts(sh.meta.get("touchstones")) if _str(t.get("conviction"))]
    lo, hi = CONVICTIONS if player else RETAINER_CONVICTIONS
    if not (lo <= len(convictions) <= hi):
        p.add("conviction_count", min=lo, max=hi, have=len(convictions))
    elif any(not _str(t.get("name")) for t in convictions):
        p.add("conviction_pairs")
