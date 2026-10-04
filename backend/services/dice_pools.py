"""
Dice pools from the character sheet (pure), and the Storyteller's roll tags.

The Storyteller used to guess pools ("Roll 3d10 for Stealth" when the sheet gives
Dexterity 3 + Stealth 3 = 6, and in V5 it ignored Hunger). Now:

1. The system prompt gets a short block of the character's common pools
   (`prompt_block`) and asks the model (`roll_instruction`) to request rolls with a tag:
   ``[[roll: Dexterity + Stealth, difficulty 6]]``.
2. After the reply, `apply_roll_tags` resolves every tag against the sheet and rewrites it
   into the canonical form the chat UI turns into a "Roll" chip, e.g.
   ``[[roll: Dexterity + Stealth | 6 dice | difficulty 6]]`` (classic) or
   ``[[roll: Charisma + Persuasion | specialty Seduction | 8 dice | 2 hunger | difficulty 3]]``
   (V5), and returns the same data as structured roll requests.

Rules (docs/rules/CLASSIC_REVISED.md §1.1, §1.4, §2.6; docs/rules/V5.md §1.1, §1.4, §1.6, §2.4):
- Classic: Attribute + Ability. An untrained Skill rolls the Attribute at +1 difficulty, an
  untrained Knowledge needs the Storyteller's leave. A specialty only flags the roll (10s are
  rerolled); classic sheets don't store specialties today, so this only fires when a sheet has
  a `skills.specialties` list. Wound penalties: classic sheets don't track health levels, so
  none are applied.
- V5: Attribute + Skill (or + Discipline, or Attribute + Attribute). Hunger dice = current
  Hunger, at most the pool (they replace regular dice, the pool size stays). One matching
  specialty adds 1 die. Impairment: a full Health track −2 to Physical pools, a full Willpower
  track −2 to Social and Mental pools, more Stains than free Humanity boxes −2 to all pools.
  Minimum pool 1. Willpower / Humanity rolls use the current undamaged value and get no Hunger.

Storage (docs/CHARACTER_SHEET_BLOCKS.md): `attributes` flat {key: dots}; classic `skills`
{talents|skills|knowledges: {key: dots}, custom: {group: [{key,label,dots}]}}; V5 `skills`
{physical|social|mental: {key: dots}, specialties: [{skill,name}]}; `wod_meta` disciplines
[{name, dots|level}] (classic may nest them under `wod_meta.vampire`).
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple

from services.character_prompt import MAX_NAME_CHARS, _clean

CLASSIC = "classic"
V5 = "v5"

CLASSIC_ATTRIBUTES = {
    "physical": ("strength", "dexterity", "stamina"),
    "social": ("charisma", "manipulation", "appearance"),
    "mental": ("perception", "intelligence", "wits"),
}
V5_ATTRIBUTES = {
    "physical": ("strength", "dexterity", "stamina"),
    "social": ("charisma", "manipulation", "composure"),
    "mental": ("intelligence", "wits", "resolve"),
}
CLASSIC_ABILITIES = {
    "talents": ("alertness", "athletics", "brawl", "dodge", "empathy", "expression",
                "intimidation", "leadership", "streetwise", "subterfuge"),
    "skills": ("animal_ken", "crafts", "drive", "etiquette", "firearms", "melee",
               "performance", "security", "stealth", "survival"),
    "knowledges": ("academics", "computer", "finance", "investigation", "law",
                   "linguistics", "medicine", "occult", "politics", "science"),
}
V5_SKILLS = {
    "physical": ("athletics", "brawl", "craft", "drive", "firearms", "larceny",
                 "melee", "stealth", "survival"),
    "social": ("animal_ken", "etiquette", "insight", "intimidation", "leadership",
               "performance", "persuasion", "streetwise", "subterfuge"),
    "mental": ("academics", "awareness", "finance", "investigation", "medicine",
               "occult", "politics", "science", "technology"),
}

# Other names for the same trait. English abbreviations and everyday words, the other
# edition's name (Security ↔ Larceny, …), and Greek. The Greek UI keeps trait names in
# English (frontend/src/i18n/locales/el has no translated trait labels), but Greek players
# and the model writing Greek use Greek words, so these are the usual Greek renderings.
# Keys are canonical keys; an alias that names a trait the edition doesn't have is resolved
# through CROSS_EDITION below.
ALIASES: Dict[str, Tuple[str, ...]] = {
    # Attributes
    "strength": ("str", "δύναμη", "σωματική δύναμη", "ρώμη"),
    "dexterity": ("dex", "agility", "επιδεξιότητα", "ευκινησία", "δεξιοτεχνία"),
    "stamina": ("sta", "stam", "endurance", "αντοχή"),
    "charisma": ("cha", "char", "χάρισμα", "γοητεία"),
    "manipulation": ("man", "manip", "χειραγώγηση"),
    "appearance": ("app", "looks", "εμφάνιση"),
    "composure": ("comp", "ψυχραιμία", "αυτοκυριαρχία", "νηφαλιότητα"),
    "perception": ("per", "perc", "αντίληψη", "παρατηρητικότητα"),
    "intelligence": ("int", "intel", "intellect", "ευφυΐα", "νοημοσύνη"),
    "wits": ("wit", "οξύνοια", "ετοιμότητα", "εξυπνάδα", "ευστροφία"),
    "resolve": ("res", "αποφασιστικότητα"),
    # Abilities / Skills
    "athletics": ("αθλητικά", "αθλητισμός", "αθλητικότητα"),
    "brawl": ("brawling", "unarmed", "fists", "πάλη", "καβγάς", "πυγμαχία", "μάχη σώμα με σώμα"),
    "craft": ("crafting", "χειροτεχνία", "κατασκευή"),
    "crafts": (),
    "drive": ("driving", "οδήγηση"),
    "firearms": ("guns", "shooting", "πυροβόλα", "πυροβόλα όπλα", "σκοποβολή"),
    "larceny": ("lockpicking", "theft", "κλοπή", "διάρρηξη", "λωποδυσία"),
    "security": ("ασφάλεια", "παραβίαση"),
    "melee": ("μάχη με όπλα", "μάχη με όπλο", "αγχέμαχη μάχη", "μάχη εκ του συστάδην"),
    "stealth": ("sneak", "sneaking", "μυστικότητα", "αθόρυβη κίνηση", "κρυφή κίνηση",
                "κλεφτή κίνηση", "απόκρυψη", "αθορυβία", "λαθραία κίνηση"),
    "survival": ("επιβίωση",),
    "animal_ken": ("animals", "ζώα", "χειρισμός ζώων", "γνώση ζώων"),
    "etiquette": ("manners", "εθιμοτυπία", "καλοί τρόποι", "ετικέτα"),
    "insight": ("διορατικότητα",),
    "empathy": ("ενσυναίσθηση",),
    "intimidation": ("intimidate", "εκφοβισμός", "τρομοκράτηση"),
    "leadership": ("ηγεσία", "ηγετικότητα"),
    "performance": ("perform", "ερμηνεία", "παράσταση", "καλλιτεχνική ερμηνεία"),
    "expression": ("έκφραση",),
    "persuasion": ("persuade", "πειθώ", "πειστικότητα"),
    "streetwise": ("γνώση του δρόμου", "νόμοι του δρόμου", "πονηριά του δρόμου"),
    "subterfuge": ("deception", "lying", "εξαπάτηση", "δόλος", "παραπλάνηση"),
    "academics": ("ακαδημαϊκά", "ακαδημαϊκές γνώσεις", "μόρφωση"),
    "awareness": ("επίγνωση",),
    "alertness": ("εγρήγορση", "επαγρύπνηση"),
    "dodge": ("αποφυγή",),
    "finance": ("οικονομικά",),
    "investigation": ("investigate", "έρευνα", "διερεύνηση", "εξιχνίαση"),
    "medicine": ("ιατρική",),
    "occult": ("απόκρυφα", "αποκρυφισμός"),
    "politics": ("πολιτική",),
    "science": ("επιστήμη", "επιστήμες"),
    "technology": ("tech", "τεχνολογία"),
    "computer": ("computers", "υπολογιστές"),
    "law": ("νομικά", "δίκαιο"),
    "linguistics": ("languages", "γλωσσολογία", "γλώσσες"),
    # Trackers / morality
    "willpower": ("wp", "θέληση", "δύναμη θέλησης"),
    "humanity": ("ανθρωπιά", "ανθρωπότητα"),
}

# A name from the other edition → this edition's trait (conversion-guide equivalents).
CROSS_EDITION = {
    V5: {"security": "larceny", "computer": "technology", "crafts": "craft", "empathy": "insight",
         "alertness": "awareness", "dodge": "athletics"},
    CLASSIC: {"larceny": "security", "technology": "computer", "craft": "crafts",
              "insight": "empathy", "awareness": "alertness"},
}

ATTRIBUTE_LABELS = {k: k.title() for g in (CLASSIC_ATTRIBUTES, V5_ATTRIBUTES) for ks in g.values() for k in ks}

# Common pools shown to the Storyteller (attribute, skill/ability).
COMMON_POOLS = {
    CLASSIC: (
        ("dexterity", "stealth"), ("dexterity", "athletics"), ("dexterity", "dodge"),
        ("strength", "brawl"), ("dexterity", "melee"), ("perception", "alertness"),
        ("charisma", "subterfuge"), ("manipulation", "subterfuge"), ("charisma", "etiquette"),
        ("manipulation", "intimidation"), ("perception", "empathy"), ("intelligence", "investigation"),
        ("wits", "streetwise"),
    ),
    V5: (
        ("dexterity", "stealth"), ("dexterity", "athletics"), ("strength", "brawl"),
        ("dexterity", "melee"), ("wits", "awareness"), ("charisma", "persuasion"),
        ("manipulation", "subterfuge"), ("manipulation", "persuasion"), ("composure", "insight"),
        ("charisma", "intimidation"), ("intelligence", "investigation"), ("wits", "streetwise"),
    ),
}

MAX_TAGS = 4
MAX_TRAITS = 3
_TAG_RE = re.compile(
    r"\[\[?\s*(?:roll|dice|ρίψη|ριψη|ρίξη|ριξη|ζαριά|ζαρια)\s*:\s*([^\[\]\n]{1,200}?)\s*\]\]?",
    re.IGNORECASE,
)
_DIFF_RE = re.compile(
    r"\(?\s*\b(?:difficulty|diff|dc|tn|δυσκολία|δυσκολια|δυσκ\.?)\s*[:=]?\s*(\d{1,2})\s*\)?",
    re.IGNORECASE,
)
_SPEC_RE = re.compile(
    r"^(?:specialty|speciality|specialisation|specialization|spec|ειδίκευση|ειδικευση|ειδικότητα|ειδικοτητα)\s*[:=]?\s*(.+)$",
    re.IGNORECASE,
)
_PAREN_RE = re.compile(r"\(([^()]{1,80})\)")
_NOISE_RE = re.compile(r"^\s*(?:\d+\s*(?:dice|d10|ζάρια|ζαρια)|\d+\s*hunger|hunger\s*\d+|pool\s*\d+)\s*$", re.IGNORECASE)


# --- helpers -----------------------------------------------------------------------------------


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


def norm(name: Any) -> str:
    """Lowercase, no accents, final sigma folded, only letters/digits: 'Animal Ken' → 'animalken'."""
    s = unicodedata.normalize("NFD", str(name or "")).lower()
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("ς", "σ")
    return "".join(c for c in s if c.isalnum())


_ALIAS_INDEX: Dict[str, str] = {}
for _key, _names in ALIASES.items():
    _ALIAS_INDEX.setdefault(norm(_key), _key)
    for _n in _names:
        _ALIAS_INDEX.setdefault(norm(_n), _key)


def _label(key: str) -> str:
    return str(key).replace("_", " ").strip().title()


def edition_of(edition: Any) -> str:
    return V5 if str(edition or "").strip().lower() == V5 else CLASSIC


# --- the sheet as a trait table ----------------------------------------------------------------


def _named_dots(items: Any) -> Dict[str, Tuple[str, int]]:
    """[{name, dots|level|rating}] or {name: dots} → {norm(name): (label, dots)}."""
    out: Dict[str, Tuple[str, int]] = {}
    if isinstance(items, dict):
        for k, v in items.items():
            n = _num(v)
            if n is not None:
                out[norm(k)] = (_label(k), n)
        return out
    if not isinstance(items, list):
        return out
    for it in items:
        if not isinstance(it, dict):
            continue
        name = it.get("name") or it.get("label") or it.get("key")
        if not name:
            continue
        dots = None
        for k in ("dots", "level", "rating", "value", "points"):
            dots = _num(it.get(k))
            if dots is not None:
                break
        out[norm(name)] = (str(name).strip()[:60], dots or 0)
    return out


class Sheet:
    """Trait lookup over one character row (any missing column is just empty)."""

    def __init__(self, row: Dict[str, Any], edition: str):
        self.edition = edition_of(edition)
        self.name = str((row or {}).get("name") or "").strip()
        row = row or {}
        self.attrs = _json(row.get("attributes"), {})
        self.skills = _json(row.get("skills"), {})
        self.meta = _json(row.get("wod_meta"), {})
        vamp = self.meta.get("vampire") if isinstance(self.meta.get("vampire"), dict) else {}
        self.src = {**vamp, **self.meta}  # classic sheets may nest vampire data
        # {norm key: (kind, canonical key, label, dots, category)}
        self.traits: Dict[str, Tuple[str, str, str, int, str]] = {}
        groups = V5_ATTRIBUTES if self.edition == V5 else CLASSIC_ATTRIBUTES
        for cat, keys in groups.items():
            for k in keys:
                self.traits[norm(k)] = ("attribute", k, _label(k), _num(self.attrs.get(k)) or 0, cat)
        for k, v in self.attrs.items():  # unknown extra attributes on the sheet
            if norm(k) not in self.traits and _num(v) is not None:
                self.traits[norm(k)] = ("attribute", k, _label(k), _num(v), "")
        if self.edition == V5:
            for cat, keys in V5_SKILLS.items():
                g = self.skills.get(cat) if isinstance(self.skills.get(cat), dict) else {}
                for k in keys:
                    self.traits[norm(k)] = ("skill", k, _label(k), _num(g.get(k)) or 0, cat)
                for k, v in g.items():
                    if norm(k) not in self.traits and _num(v) is not None:
                        self.traits[norm(k)] = ("skill", k, _label(k), _num(v), cat)
        else:
            custom = self.skills.get("custom") if isinstance(self.skills.get("custom"), dict) else {}
            for cat, keys in CLASSIC_ABILITIES.items():
                g = self.skills.get(cat) if isinstance(self.skills.get(cat), dict) else {}
                for k in keys:
                    self.traits[norm(k)] = ("ability", k, _label(k), _num(g.get(k)) or 0, cat)
                for k, v in g.items():
                    if norm(k) not in self.traits and _num(v) is not None:
                        self.traits[norm(k)] = ("ability", k, _label(k), _num(v), cat)
                for it in custom.get(cat) or []:
                    if isinstance(it, dict) and (it.get("label") or it.get("key")):
                        lab = str(it.get("label") or it.get("key")).strip()[:60]
                        self.traits.setdefault(norm(lab), ("ability", norm(lab), lab, _num(it.get("dots")) or 0, cat))
                        if it.get("key"):
                            self.traits.setdefault(norm(it["key"]), ("ability", norm(lab), lab, _num(it.get("dots")) or 0, cat))
        for nk, (lab, dots) in _named_dots(self.src.get("disciplines")).items():
            self.traits.setdefault(nk, ("discipline", nk, lab, dots, ""))
        if self.edition == CLASSIC:
            for nk, (lab, dots) in _named_dots(self.src.get("backgrounds")).items():
                self.traits.setdefault(nk, ("background", nk, lab, dots, ""))
            virtues = self.src.get("virtues") if isinstance(self.src.get("virtues"), dict) else {}
            for k, v in virtues.items():
                if _num(v) is not None:
                    self.traits.setdefault(norm(k), ("virtue", k, _label(k), _num(v), ""))
        # Trackers: classic rolls the permanent rating; V5 Willpower the current undamaged boxes (p. 119).
        wp = self.src.get("willpower")
        if self.edition == V5:
            self.traits[norm("willpower")] = ("tracker", "willpower", "Willpower", self._v5_track_left(wp, self._v5_wp_max()), "")
            # Humanity isn't a tracker pool in V5 (only Health and Willpower are, p. 118): a roll
            # uses the rating, Stains don't lower it (Remorse is a separate end-of-session roll).
            hum = _num(self.meta.get("humanity"))
            if hum is not None:
                self.traits[norm("humanity")] = ("tracker", "humanity", "Humanity", max(0, hum), "")
        else:
            if _num(wp) is not None:
                self.traits[norm("willpower")] = ("tracker", "willpower", "Willpower", _num(wp), "")
            if _num(self.src.get("humanity")) is not None:
                self.traits[norm("humanity")] = ("tracker", "humanity", "Humanity", _num(self.src.get("humanity")), "")

    def _v5_wp_max(self) -> int:
        return (_num(self.attrs.get("composure")) or 0) + (_num(self.attrs.get("resolve")) or 0)

    @staticmethod
    def _v5_track(track: Any, fallback_max: int) -> Tuple[int, int]:
        """(max, damaged boxes) of a V5 {max, superficial, aggravated} track."""
        if isinstance(track, dict):
            mx = _num(track.get("max"))
            mx = mx if mx is not None and mx > 0 else fallback_max
            dmg = max(0, _num(track.get("superficial")) or 0) + max(0, _num(track.get("aggravated")) or 0)
            return mx, min(dmg, mx)
        if _num(track) is not None:
            return _num(track), 0
        return fallback_max, 0

    def _v5_track_left(self, track: Any, fallback_max: int) -> int:
        mx, dmg = self._v5_track(track, fallback_max)
        return max(0, mx - dmg)

    def lookup(self, name: str) -> Optional[Tuple[str, str, str, int, str]]:
        n = norm(name)
        if not n:
            return None
        if n in self.traits:
            return self.traits[n]
        key = _ALIAS_INDEX.get(n)
        if key:
            key = CROSS_EDITION[self.edition].get(key, key)
            if norm(key) in self.traits:
                return self.traits[norm(key)]
        return None

    def specialties_for(self, skill_key: str) -> List[str]:
        sp = self.skills.get("specialties")
        if not isinstance(sp, list):
            return []
        out = []
        for it in sp:
            if isinstance(it, dict) and it.get("name") and norm(it.get("skill")) == norm(skill_key):
                out.append(str(it["name"]).strip()[:60])
        return out

    def hunger(self) -> int:
        h = _num(self.meta.get("hunger"))
        return max(0, min(5, h)) if h is not None else 0

    def v5_impairment(self) -> Dict[str, bool]:
        """Which V5 trackers are full (Impaired), and degeneration (Stains overflow)."""
        hmx, hdmg = self._v5_track(self.meta.get("health"), (_num(self.attrs.get("stamina")) or 0) + 3)
        wmx, wdmg = self._v5_track(self.meta.get("willpower"), self._v5_wp_max())
        hum = _num(self.meta.get("humanity"))
        stains = _num(self.meta.get("stains")) or 0
        return {
            "health": isinstance(self.meta.get("health"), dict) and hmx > 0 and hdmg >= hmx,
            "willpower": isinstance(self.meta.get("willpower"), dict) and wmx > 0 and wdmg >= wmx,
            "degeneration": hum is not None and stains > max(0, 10 - hum),
        }


# --- pools -------------------------------------------------------------------------------------


def compute_pool(row: Dict[str, Any], traits: Iterable[str], edition: str = CLASSIC,
                 specialty: Optional[str] = None, sheet: Optional[Sheet] = None) -> Dict[str, Any]:
    """
    The pool for some named traits (e.g. ["Dexterity", "Stealth"]) on this sheet.

    Returns a dict: ok (every trait found, and an Attribute among two or more), unknown (names not found), traits [{key, label,
    kind, dots}], label ("Dexterity + Stealth"), base (sum of dots), specialty (name or None),
    bonus (V5 specialty die), penalty (negative), notes (short English reasons), pool (dice to
    roll), hunger (V5 Hunger dice), difficulty_mod (classic untrained Skill +1), edition.
    """
    sheet = sheet or Sheet(row, edition)
    ed = sheet.edition
    found, unknown = [], []
    for t in list(traits)[:MAX_TRAITS]:
        t = str(t or "").strip()
        if not t:
            continue
        hit = sheet.lookup(t)
        if hit is None:
            unknown.append(t[:60])
            continue
        if any(f["key"] == hit[1] and f["kind"] == hit[0] for f in found):
            continue  # "Dexterity + Dexterity" style typos count once
        found.append({"key": hit[1], "label": hit[2], "kind": hit[0], "dots": max(0, hit[3]), "category": hit[4]})
    # Attribute first, then the rest in the order given.
    found.sort(key=lambda f: 0 if f["kind"] == "attribute" else 1)
    # Two or more traits need an Attribute among them ("Presence + Persuasion" is no pool in
    # either edition); one trait alone is fine (Willpower, a Virtue, a Background, Strength).
    shaped = len(found) == 1 or any(f["kind"] == "attribute" for f in found)
    out: Dict[str, Any] = {
        "edition": ed,
        "ok": bool(found) and not unknown and shaped,
        "unknown": unknown,
        "traits": [{k: f[k] for k in ("key", "label", "kind", "dots")} for f in found],
        "label": " + ".join(f["label"] for f in found),
        "base": sum(f["dots"] for f in found),
        "specialty": None,
        "bonus": 0,
        "penalty": 0,
        "notes": [],
        "difficulty_mod": 0,
        "hunger": 0,
    }
    skill = next((f for f in found if f["kind"] in ("skill", "ability")), None)
    tracker_roll = any(f["kind"] == "tracker" for f in found)

    # Specialty: only one that the sheet has for this skill, named in the request.
    if specialty and skill:
        want = norm(specialty)
        for sp in sheet.specialties_for(skill["key"]):
            if want and (norm(sp) == want or want in norm(sp) or norm(sp) in want):
                out["specialty"] = sp
                break
    if ed == V5:
        if out["specialty"]:
            out["bonus"] = 1
        if not tracker_roll:
            imp = sheet.v5_impairment()
            cat = (skill or (found[0] if found else {})).get("category", "")
            if imp["degeneration"]:
                out["penalty"] = -2
                out["notes"].append("impaired (degeneration)")
            elif imp["health"] and cat == "physical":
                out["penalty"] = -2
                out["notes"].append("impaired (Health)")
            elif imp["willpower"] and cat in ("social", "mental"):
                out["penalty"] = -2
                out["notes"].append("impaired (Willpower)")
        pool = max(1, out["base"] + out["bonus"] + out["penalty"]) if found else 0
        out["pool"] = pool
        out["hunger"] = 0 if tracker_roll else min(sheet.hunger(), pool)
    else:
        if skill and skill["dots"] == 0:
            if skill["category"] == "skills":
                out["difficulty_mod"] = 1
                out["notes"].append("untrained Skill: +1 difficulty")
            elif skill["category"] == "knowledges":
                out["notes"].append("untrained Knowledge: only with the Storyteller's leave")
        out["pool"] = max(0, out["base"] + out["penalty"])
    return out


# --- the prompt block --------------------------------------------------------------------------


def roll_instruction(edition: str) -> str:
    ed = edition_of(edition)
    diff = ("the difficulty is the number of successes needed: 1 easy, 2 average, 3 hard, 4 very hard, 5 extreme"
            if ed == V5 else "the difficulty is the target number per die: 6 standard, 4-5 easy, 7-9 hard")
    example = "[[roll: Dexterity + Stealth, difficulty 2]]" if ed == V5 else "[[roll: Dexterity + Stealth, difficulty 6]]"
    return (
        "Dice: when the player character attempts something risky or uncertain, end your reply by "
        f"asking for one roll with this exact tag: {example}  ({diff}). "
        "Write the trait names in English as on the sheet, even when you reply in Greek. "
        "Always give the difficulty in the tag. Don't explain the roll in words (no \"you need "
        "4 successes\", no \"roll 3d10\"): the app reads the tag and computes the pool from the sheet"
        + (", including Hunger dice" if ed == V5 else "")
        + ". Ask for a roll only when the outcome is in doubt, then stop and wait for the result. "
        "This tag is the one piece of game mechanics you may write."
    )


def prompt_block(row: Dict[str, Any], edition: str = CLASSIC) -> str:
    """Common pools of this character, for the system prompt (next to the sheet)."""
    sheet = Sheet(row, edition)
    ed = sheet.edition
    parts = []
    for a, s in COMMON_POOLS[ed]:
        r = compute_pool(row, [a, s], ed, sheet=sheet)
        if not r["ok"]:
            continue
        txt = f"{r['label']} {r['pool']}"
        sps = sheet.specialties_for(s)
        if ed == V5 and sps:
            txt += f" ({_clean(sps[0], 60)} specialty {r['pool'] + 1})"
        parts.append(txt)
    discs = [(lab, d) for (kind, _k, lab, d, _c) in sheet.traits.values() if kind == "discipline" and d > 0]
    name = _clean(sheet.name, MAX_NAME_CHARS) or "the character"
    if ed == V5:
        head = f"Dice pools from {name}'s sheet (V5, Hunger {sheet.hunger()}: the app turns that many dice into Hunger dice):"
    else:
        head = f"Dice pools from {name}'s sheet (Classic):"
    lines = [head, " · ".join(parts)]
    if discs:
        names = [f"{_clean(lab, 60)} {d}" for lab, d in discs[:6]]
        lines.append(f"Disciplines: {', '.join(names)}. A Discipline roll is Attribute + Discipline, "
                     "never Discipline + Skill.")
    return "\n".join(lines)


# --- roll tags ---------------------------------------------------------------------------------


def parse_tag_body(body: str) -> Dict[str, Any]:
    """'Dexterity + Stealth, difficulty 6' → {traits, difficulty, specialty}."""
    body = str(body or "")
    difficulty = None
    m = _DIFF_RE.search(body)
    if m:
        difficulty = int(m.group(1))
        body = body[: m.start()] + " " + body[m.end():]
    specialty = None
    segs = [s.strip() for s in re.split(r"[|,;]", body)]
    trait_part = ""
    for s in segs:
        if not s or _NOISE_RE.match(s):
            continue
        sm = _SPEC_RE.match(s)
        if sm:
            specialty = sm.group(1).strip()
            continue
        if not trait_part:
            trait_part = s
    pm = _PAREN_RE.search(trait_part)
    if pm:
        inner = pm.group(1).strip()
        sm = _SPEC_RE.match(inner)
        if specialty is None:
            specialty = sm.group(1).strip() if sm else inner
        trait_part = (trait_part[: pm.start()] + trait_part[pm.end():]).strip()
    trait_part = re.sub(r"\b(?:vs\.?|versus|against|at)\s*$", "", trait_part, flags=re.IGNORECASE).strip()
    # "Persuasion 3" / "Stealth (3)": the model's own dot counts are dropped, the sheet decides.
    traits = [re.sub(r"\s*\d+$", "", t.strip(" .:-")).strip(" .:-") for t in re.split(r"\s*(?:\+|&|\bplus\b|\band\b|\bκαι\b)\s*", trait_part, flags=re.IGNORECASE)]
    traits = [t for t in traits if t]
    return {"traits": traits[:MAX_TRAITS], "difficulty": difficulty, "specialty": specialty}


def _clamp_difficulty(d: Optional[int], ed: str, mod: int = 0) -> Optional[int]:
    if d is None:
        return 6 + mod if ed == CLASSIC else None
    if ed == V5:
        return max(1, min(10, d))
    return max(2, min(10, d + mod))


def canonical_tag(req: Dict[str, Any]) -> str:
    """The stored form the chat UI parses (frontend features/dice/rollRequests.js)."""
    parts = [req["label"]]
    if req.get("specialty"):
        parts.append(f"specialty {req['specialty']}")
    parts.append(f"{req['pool']} dice")
    if req["edition"] == V5:
        parts.append(f"{req['hunger']} hunger")
    if req.get("difficulty") is not None:
        parts.append(f"difficulty {req['difficulty']}")
    for n in req.get("notes") or []:
        parts.append(n)
    # Sheet text (specialty names, custom labels) is one plain line here, or the UI can't parse the tag.
    return "[[roll: " + " | ".join(
        _clean(p, 120).replace("|", "/").replace("]", ")").replace("[", "(") for p in parts
    ) + "]]"


def resolve_tag(body: str, row: Optional[Dict[str, Any]], edition: str,
                sheet: Optional[Sheet] = None) -> Optional[Dict[str, Any]]:
    """One tag body → a roll request dict, or None when it can't be resolved against the sheet."""
    if not row:
        return None
    spec = parse_tag_body(body)
    if not spec["traits"]:
        return None
    sheet = sheet or Sheet(row, edition)
    r = compute_pool(row, spec["traits"], sheet.edition, spec["specialty"], sheet=sheet)
    if not r["ok"]:
        return None
    ed = sheet.edition
    return {
        "edition": ed,
        "label": r["label"],
        "traits": r["traits"],
        "pool": r["pool"],
        "hunger": r["hunger"],
        "specialty": r["specialty"],
        "difficulty": _clamp_difficulty(spec["difficulty"], ed, r["difficulty_mod"]),
        "notes": r["notes"],
    }


def _plain(body: str) -> str:
    """An unresolvable tag shown as plain text (no brackets, so the UI shows no chip)."""
    spec = parse_tag_body(body)
    txt = " + ".join(spec["traits"]) or str(body).strip()
    if spec["difficulty"] is not None:
        txt += f", difficulty {spec['difficulty']}"
    return f"**{txt}**"


def apply_roll_tags(text: str, row: Optional[Dict[str, Any]], edition: str = CLASSIC,
                    character_id: Any = None) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Resolve the Storyteller's roll tags against the sheet.

    Returns (text with every tag rewritten, roll requests). Resolved tags become the canonical
    tag (canonical_tag); tags that can't be resolved (no character, unknown trait, more than
    MAX_TAGS) become bold plain text. Text without tags comes back unchanged.
    """
    if not text or "[" not in text:
        return text, []
    sheet = Sheet(row, edition) if row else None
    requests: List[Dict[str, Any]] = []

    def repl(m: "re.Match[str]") -> str:
        body = m.group(1)
        req = resolve_tag(body, row, edition, sheet=sheet) if len(requests) < MAX_TAGS else None
        if req is None:
            return _plain(body)
        if character_id is not None:
            req["character_id"] = character_id
        requests.append(req)
        return canonical_tag(req)

    return _TAG_RE.sub(repl, text), requests
