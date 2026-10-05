"""
Rules edition helpers (pure, no DB).

A campaign picks its rules edition at creation and it never changes:
- ``classic`` — Old World of Darkness, Vampire: The Masquerade Revised (default; every
  existing campaign/character is classic).
- ``v5`` — Vampire: The Masquerade 5th Edition. Only allowed for game_system ``vampire``.

Characters copy the edition of their campaign when they are created.
"""

from __future__ import annotations

import re
from typing import Any, Optional, Tuple

CLASSIC = "classic"
V5 = "v5"
RULES_EDITIONS = (CLASSIC, V5)
DEFAULT_RULES_EDITION = CLASSIC

# game_system values that may use V5
V5_GAME_SYSTEMS = frozenset({"vampire"})

_ALIASES = {
    "classic": CLASSIC,
    "revised": CLASSIC,
    "owod": CLASSIC,
    "v5": V5,
    "5e": V5,
    "vtm5": V5,
}


def normalize_rules_edition(value: Any, default: Optional[str] = DEFAULT_RULES_EDITION) -> Optional[str]:
    """
    Map a stored/user value to ``'classic'`` / ``'v5'``.
    Empty/None → ``default``. Unknown values → None (caller decides; see validate).
    """
    if value is None:
        return default
    s = str(value).strip().lower()
    if not s:
        return default
    return _ALIASES.get(s)


def edition_of(row: Any) -> str:
    """Rules edition of a DB row (campaign or character); missing/unknown → classic."""
    if not row:
        return DEFAULT_RULES_EDITION
    try:
        raw = row.get("rules_edition")
    except AttributeError:
        raw = None
    return normalize_rules_edition(raw) or DEFAULT_RULES_EDITION


def is_v5(row_or_value: Any) -> bool:
    if isinstance(row_or_value, str) or row_or_value is None:
        return normalize_rules_edition(row_or_value) == V5
    return edition_of(row_or_value) == V5


def validate_rules_edition(value: Any, game_system: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Validate a requested edition for a campaign's game_system.
    Returns (edition, None) on success or (None, error_message).
    """
    ed = normalize_rules_edition(value)
    if ed is None:
        return None, "rules_edition must be 'classic' or 'v5'"
    gs = str(game_system or "").strip().lower()
    if ed == V5 and gs not in V5_GAME_SYSTEMS:
        return None, "rules_edition 'v5' is only available for game_system 'vampire'"
    return ed, None


def rules_edition_label(edition: Any) -> str:
    ed = normalize_rules_edition(edition) or DEFAULT_RULES_EDITION
    return "V5 (5th Edition)" if ed == V5 else "Classic (Revised)"


_CLASSIC_BRIEF = """RULES: Classic World of Darkness (Revised Storyteller system). Use ONLY these mechanics.
- Dice: pools of d10 = Attribute + Ability. Difficulty is a target number 2-10 (default 6); each die >= difficulty is a success.
- Each 1 cancels one success. Botch only if no die succeeded and at least one 1 showed. 4 successes = exceptional, 5+ = phenomenal.
- Specialty: natural 10s count and are rerolled (rerolls only add). Willpower: spend 1 point before rolling for 1 automatic success.
- Traits: Attributes (Physical/Social/Mental), Abilities (Talents/Skills/Knowledges), Backgrounds, Virtues, Willpower, Humanity/Path.
- Never use V5 terms (Hunger dice, Rouse checks, messy criticals, Blood Potency) in this chronicle."""

_CLASSIC_VAMPIRE_EXTRA = """- Vampires: blood pool (by Generation), spend blood for Disciplines/healing/boosting Physical Attributes; Frenzy and Rotschreck are Virtue rolls (Self-Control/Courage)."""

_V5_BRIEF = """RULES: Vampire: The Masquerade 5th Edition (V5). Use ONLY these mechanics.
- Dice: pools of d10 = Attribute + Skill. Each die showing 6-10 is a success. Difficulty = number of successes needed. No botches; 1s cancel nothing.
- Each pair of 10s adds 2 extra successes (a pair = 4). Critical win = a pair of 10s and the roll succeeds.
- Hunger (0-5) replaces that many dice with Hunger dice. A critical with a Hunger 10 is a MESSY critical (the Beast shapes the success). A failed roll with a Hunger 1 is a BESTIAL failure (compulsion or loss of control).
- Rouse check: roll one die when using blood (Disciplines, Blood Surge, waking); 6+ no change, otherwise Hunger +1. Feeding lowers Hunger.
- Willpower: spend to reroll up to 3 normal (non-Hunger) dice after a roll.
- Health and Willpower take Superficial and Aggravated damage. Humanity 0-10 with Stains; Blood Potency; Predator Type; Convictions and Touchstones; Compulsions by clan.
- Never use Revised terms (blood pool points, difficulty target numbers, botches, Virtues) in this chronicle."""


def storyteller_rules_brief(edition: Any, game_system: Any = "") -> str:
    """Short rules summary injected into the storyteller system prompt."""
    ed = normalize_rules_edition(edition) or DEFAULT_RULES_EDITION
    if ed == V5:
        return _V5_BRIEF
    gs = str(game_system or "").strip().lower()
    if gs == "vampire":
        return _CLASSIC_BRIEF + "\n" + _CLASSIC_VAMPIRE_EXTRA
    if reroll_ones_cancel(gs):
        return _CLASSIC_BRIEF.replace("(rerolls only add)", "(a 1 on a reroll cancels a success)")
    return _CLASSIC_BRIEF


# ---------------------------------------------------------------------------
# Rule book retrieval (docs/rules/RULE_BOOKS_RAG.md is the data contract)
# ---------------------------------------------------------------------------

RULE_BOOK_COLLECTIONS = {V5: "rule_books_v5", CLASSIC: "rule_books_classic"}
CHRONICLE_BOOKS_COLLECTION = "rule_books_chronicle"
ALL_RULE_BOOK_COLLECTIONS = (*RULE_BOOK_COLLECTIONS.values(), CHRONICLE_BOOKS_COLLECTION)

GAME_LINES = ("vampire", "werewolf", "mage")
RULE_KINDS = ("rules", "sidebar", "example")
LORE_KINDS = ("lore", "adventure")
RULES_INTENTS = frozenset({"rules_question", "dice", "combat"})
# Laya's intent counts only at this score or above (same as smart_model_router).
INTENT_MIN_SCORE = 0.6

DEFAULT_RULE_BOOK_MAX_DISTANCE = 0.45
DEFAULT_RULE_BOOK_STRICT_MAX_DISTANCE = 0.42


def game_line(game_system: Any) -> Optional[str]:
    """'vampire' / 'werewolf' / 'mage' from a campaign's game_system; None for custom and the rest."""
    gs = str(game_system or "").strip().lower()
    if re.search(r"vampire|masquerade|vtm", gs):
        return "vampire"
    if re.search(r"werewolf|apocalypse|garou|wta", gs):
        return "werewolf"
    if re.search(r"mage|ascension|mta", gs):
        return "mage"
    return None


def rule_book_lines(game_system: Any, rules_edition: Any) -> Optional[list]:
    """
    Values of the chunk ``line`` a chronicle may get: its own line plus ``all``. V5 is
    Vampire only. A custom (or unknown) game system gets every line (None = no filter):
    it uses the shared Storyteller dice and its owner picked no line, so no book is
    more right than another.
    """
    if normalize_rules_edition(rules_edition) == V5:
        return ["vampire", "all"]
    line = game_line(game_system)
    return [line, "all"] if line else None


def _env_float(name: str, default: float) -> float:
    import os

    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def rule_book_max_distance() -> float:
    """RULE_BOOK_MAX_DISTANCE: cosine distance above which a chunk is dropped."""
    return _env_float("RULE_BOOK_MAX_DISTANCE", DEFAULT_RULE_BOOK_MAX_DISTANCE)


def rule_book_strict_max_distance() -> float:
    """RULE_BOOK_STRICT_MAX_DISTANCE: the cutoff when Laya's intent is unknown."""
    return _env_float("RULE_BOOK_STRICT_MAX_DISTANCE", DEFAULT_RULE_BOOK_STRICT_MAX_DISTANCE)


def rule_book_plan(intent: Any) -> Optional[dict]:
    """
    What to search for one message, from Laya's intent ({label, score} or None):
    - rules_question / dice / combat: kinds rules|sidebar|example, k=4;
    - roleplay: kinds lore|adventure, k=2;
    - general: None (no rule book search);
    - unknown (no classifier, low score): rules and lore kinds, k=4, stricter cutoff.
    Returns {kinds, k, max_distance, rules} or None.
    """
    label, score = None, 0.0
    if isinstance(intent, dict):
        label = intent.get("label")
        try:
            score = float(intent.get("score") or 0)
        except (TypeError, ValueError):
            score = 0.0
    if label and score >= INTENT_MIN_SCORE:
        if label in RULES_INTENTS:
            return {"kinds": list(RULE_KINDS), "k": 4, "max_distance": rule_book_max_distance(), "rules": True}
        if label == "roleplay":
            return {"kinds": list(LORE_KINDS), "k": 2, "max_distance": rule_book_max_distance(), "rules": False}
        if label == "general":
            return None
    return {"kinds": list(RULE_KINDS + LORE_KINDS), "k": 4,
            "max_distance": rule_book_strict_max_distance(), "rules": True}


def _and(clauses: list) -> dict:
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def rule_book_queries(campaign_id: Any, rules_edition: Any, game_system: Any, kinds: list) -> list:
    """
    (collection name, where) pairs to search: the edition's global books (line-filtered)
    and the books attached to this chronicle (rule_books_chronicle, campaign_id = it).
    Chronicle books were attached on purpose, so only the kinds narrow them.
    """
    ed = normalize_rules_edition(rules_edition) or DEFAULT_RULES_EDITION
    kind_filter = {"kind": {"$in": list(kinds)}}
    global_where = [kind_filter]
    lines = rule_book_lines(game_system, ed)
    if lines:
        global_where.append({"line": {"$in": lines}})
    out = [(RULE_BOOK_COLLECTIONS[ed], _and(global_where))]
    try:
        cid = int(campaign_id)
    except (TypeError, ValueError):
        cid = 0
    if cid > 0:
        out.append((CHRONICLE_BOOKS_COLLECTION, _and([{"campaign_id": cid}, kind_filter])))
    return out


def rule_book_citation(metadata: Any) -> str:
    """'Title › heading_path, p. N' for a chunk."""
    meta = metadata or {}
    title = str(meta.get("title") or meta.get("book_id") or "Rule book")
    head = str(meta.get("heading_path") or "").strip()
    cite = f"{title} › {head}" if head else title
    page = meta.get("page")
    return f"{cite}, p. {page}" if page not in (None, "", 0) else cite


def rule_book_text(document: Any, metadata: Any) -> str:
    """The chunk text without the '{title} › {heading_path}' line the document starts with."""
    doc = str(document or "")
    meta = metadata or {}
    head = f"{meta.get('title') or ''} › {meta.get('heading_path') or ''}"
    if meta.get("title") and doc.startswith(head):
        return doc[len(head):].lstrip("\n")
    return doc


def reroll_ones_cancel(game_system: Any) -> bool:
    """
    Whether 1s on Classic specialty rerolls cancel successes. Mage Revised says they do
    ("A botch on a re-roll does cancel a success as always"); Werewolf Revised says they
    don't ("any ones rolled on bonus dice granted by a specialty do not subtract"), Vampire Revised is silent, so every other line keeps "rerolls only add".
    """
    return game_line(game_system) == "mage"
