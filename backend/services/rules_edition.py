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
- Each 1 cancels one success. Botch only if no die succeeded and at least one 1 showed. 5+ successes = exceptional success.
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
    return _CLASSIC_BRIEF


# ---------------------------------------------------------------------------
# Rule book chunks (ChromaDB ``rule_books`` metadata)
# ---------------------------------------------------------------------------

# Every edition a rule book chunk may be stamped with (books/import_to_rag.py also uses 'nwod').
BOOK_EDITIONS = (CLASSIC, V5, "nwod")

_NWOD_CATEGORIES = frozenset({"nwod", "new world of darkness"})
_V5_TEXT_RE = re.compile(r"(?<![a-z0-9])(v5|5th ed(ition)?|fifth edition)(?![a-z0-9])")


def rules_edition_for_book(
    category: Any = None, path: Any = None, *names: Any
) -> str:
    """
    Rules edition of a rule book from what we know about it (pure).

    - ``category`` is the books/ sub-folder that parse_books.py stores ('V5', 'oWoD',
      'Classic World of Darkness', 'nWoD', 'New World of Darkness').
    - ``path`` is the PDF/JSON path; a folder named V5 / nWoD decides like a category.
    - ``names`` (filename, book name, book id) mark V5 when they say "V5" / "5th edition".
    Anything else is ``classic`` (the default edition).
    """
    cat = str(category or "").strip().lower()
    if cat == V5:
        return V5
    if cat in _NWOD_CATEGORIES:
        return "nwod"
    parts = [p.strip().lower() for p in re.split(r"[\\/]", str(path or "")) if p.strip()]
    for p in parts[:-1]:  # folders only
        if p == V5:
            return V5
        if p in _NWOD_CATEGORIES:
            return "nwod"
    text = " ".join(str(n or "") for n in (parts[-1] if parts else "", *names)).lower()
    if _V5_TEXT_RE.search(text):
        return V5
    return CLASSIC


def rule_book_edition_allowed(metadata: Any, rules_edition: Any) -> bool:
    """
    Whether a rule book chunk may be shown to a campaign of ``rules_edition``: chunks of
    that edition and untagged (legacy) chunks pass; chunks of any other edition never do.
    """
    want = normalize_rules_edition(rules_edition, default=None)
    if not want:
        return True
    try:
        tag = metadata.get("rules_edition") if metadata else None
    except AttributeError:
        tag = None
    tag = str(tag or "").strip().lower()
    return not tag or tag == want


def rule_book_where(campaign_id: Any, rules_edition: Optional[str] = None) -> dict:
    """
    ChromaDB ``where`` for rule book chunks: global books (campaign_id 0) plus this
    campaign's own uploads, optionally narrowed to one rules edition.
    """
    try:
        cid = int(campaign_id)
    except (TypeError, ValueError):
        cid = 0
    ids = [0] if cid == 0 else [0, cid]
    campaign_filter = {"campaign_id": {"$in": ids}}
    if rules_edition:
        return {"$and": [campaign_filter, {"rules_edition": str(rules_edition)}]}
    return campaign_filter


def rule_book_fallback_where(campaign_id: Any, rules_edition: str) -> dict:
    """
    Fallback ``where`` when no chunk is tagged with ``rules_edition``: the campaign
    filter minus every OTHER edition, so only untagged (legacy) chunks can match.
    Callers also check results with rule_book_edition_allowed, so this stays safe
    whatever ChromaDB does with chunks that lack the key.
    """
    others = [e for e in BOOK_EDITIONS if e != str(rules_edition)]
    return {"$and": [rule_book_where(campaign_id), {"rules_edition": {"$nin": others}}]}
