"""
Chat message actions (v0.10 phase 3): who may delete a message, reply quotes, older-history pages.

Rules (owner decision, docs/ROADMAP_v0.10.md):
- everyone can copy and reply;
- players delete their own messages (no editing);
- the chronicle's owner (Storyteller) and site admins delete any message;
- players can't delete dice rows (dice_* kinds: marker, result line, Rouse line) or AI
  (Storyteller, role assistant) messages, even when the row carries their user id.

Everything here is pure (no DB) so it can be unit tested; routes/messages.py does the queries.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from services.dice_markers import is_dice_kind

# Older-history pages (GET ...?before_id=<id>&limit=<n>).
OLDER_PAGE_DEFAULT = 50
OLDER_PAGE_MAX = 100

REPLY_EXCERPT_CHARS = 140

HIDDEN_KIND_PREFIXES = ("dice_animation_hidden", "dice_roll_hidden")
DICE_PAIR_PREFIXES = ("dice_animation", "dice_animation_hidden", "dice_roll", "dice_roll_hidden")

# 403 codes for DELETE /api/messages/<id>
DELETE_NOT_YOURS = "message_not_yours"
DELETE_DICE_STAFF_ONLY = "dice_message_staff_only"
DELETE_AI_STAFF_ONLY = "ai_message_staff_only"


def _kind(value: Any) -> str:
    return str(value or "").strip().lower()


def is_staff(site_role: Optional[str], actor_id: Any, campaign_created_by: Any) -> bool:
    """Site admin, or the chronicle's owner (its Storyteller)."""
    if _kind(site_role) == "admin":
        return True
    return campaign_created_by is not None and actor_id is not None and str(campaign_created_by) == str(actor_id)


def is_ai_message(row: Dict[str, Any]) -> bool:
    return _kind(row.get("role")) == "assistant" and not is_dice_kind(row.get("ai_message_kind"))


def is_hidden_kind(kind: Any) -> bool:
    return _kind(kind).startswith(HIDDEN_KIND_PREFIXES)


def delete_decision(row: Dict[str, Any], actor_id: Any, site_role: Optional[str],
                    campaign_created_by: Any) -> Tuple[bool, Optional[str]]:
    """(allowed, error code). row needs user_id, role, ai_message_kind."""
    if is_staff(site_role, actor_id, campaign_created_by):
        return True, None
    if is_dice_kind(row.get("ai_message_kind")):
        return False, DELETE_DICE_STAFF_ONLY
    if is_ai_message(row):
        return False, DELETE_AI_STAFF_ONLY
    if actor_id is None or str(row.get("user_id")) != str(actor_id):
        return False, DELETE_NOT_YOURS
    return True, None


def dice_pair_kinds(kind: Any) -> List[str]:
    """
    Every ai_message_kind of one roll's rows, for a dice marker or result kind
    (dice_animation[_hidden]:<id> + dice_roll[_hidden]:<id>), so deleting either removes both.
    [] for anything else (a Rouse line is a single row).
    """
    prefix, _, anim = _kind(kind).partition(":")
    if prefix not in DICE_PAIR_PREFIXES or not anim:
        return []
    return [f"{p}:{anim}" for p in DICE_PAIR_PREFIXES]


def parse_older_page(before_id: Any, limit: Any) -> Optional[Tuple[int, int]]:
    """(before_id, limit) for an older-history page, or None when before_id isn't a positive id."""
    try:
        b = int(before_id)
    except (TypeError, ValueError):
        return None
    if b <= 0:
        return None
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = OLDER_PAGE_DEFAULT
    return b, min(max(n, 1), OLDER_PAGE_MAX)


def older_page(rows_newest_first: List[Any], limit: int) -> Tuple[List[Any], bool]:
    """
    Rows fetched newest first with LIMIT limit+1 → (the page in chronological order, has_more).
    """
    has_more = len(rows_newest_first) > limit
    page = list(rows_newest_first[:limit])
    page.reverse()
    return page, has_more


_WS = re.compile(r"\s+")
_MD_NOISE = re.compile(r"[*_`#>~]+")
# [[roll: Label | 6 dice | ...]] (the AI's roll requests) reads as its label.
_ROLL_TAG = re.compile(r"\[\[\s*roll\s*:\s*([^\]|\n]*?)\s*(?:\|[^\]\n]*)?\]\]", re.IGNORECASE)


def reply_excerpt(content: Any, limit: int = REPLY_EXCERPT_CHARS) -> str:
    """One line of plain-ish text from a message for a reply quote."""
    text = _ROLL_TAG.sub(lambda m: m.group(1), str(content or ""))
    text = _MD_NOISE.sub("", text)
    text = _WS.sub(" ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def reply_author(role: Any, speaker_mode: Any, username: Any, character_name: Any) -> str:
    """Display name of a quoted message's author ('' for the AI: the client shows 'Storyteller')."""
    if _kind(role) == "assistant":
        return ""
    if _kind(speaker_mode) in ("", "character") and character_name:
        return str(character_name)
    return str(username or "")


def reply_payload(row: Dict[str, Any], allow_hidden: bool) -> Optional[Dict[str, Any]]:
    """
    reply_to for the GET payload from the reply_* columns of a joined row, or None.
    A hidden roll quoted to someone who can't see hidden rolls keeps only its id.
    """
    rid = row.get("reply_id")
    if rid is None:
        return None
    kind = row.get("reply_kind")
    if is_hidden_kind(kind) and not allow_hidden:
        return {"id": rid, "author": "", "excerpt": "", "role": "", "hidden": True}
    return {
        "id": rid,
        "author": reply_author(row.get("reply_role"), row.get("reply_speaker_mode"),
                               row.get("reply_username"), row.get("reply_character_name")),
        "excerpt": reply_excerpt(row.get("reply_content")),
        "role": _kind(row.get("reply_role")),
    }


def reply_target_error(target: Optional[Dict[str, Any]], campaign_id: int, location_id: int,
                       allow_hidden: bool) -> Optional[str]:
    """Why a message can't be replied to (None when it can). target: the row or None."""
    if not target:
        return "reply_target_not_found"
    if str(target.get("campaign_id")) != str(campaign_id) or str(target.get("location_id")) != str(location_id):
        return "reply_target_other_room"
    kind = _kind(target.get("ai_message_kind"))
    if kind.startswith(("dice_animation:", "dice_animation_hidden:")):
        return "reply_target_not_found"  # transport rows are never shown
    if is_hidden_kind(kind) and not allow_hidden:
        return "reply_target_not_found"
    return None


def hidden_dice_sql_filter(column: str = "m.ai_message_kind") -> str:
    """SQL condition that drops hidden dice rows (for viewers who can't see them)."""
    return (
        f" AND LOWER(COALESCE({column}, '')) NOT LIKE 'dice_animation_hidden%%'"
        f" AND LOWER(COALESCE({column}, '')) NOT LIKE 'dice_roll_hidden%%'"
    )


def ids_of(rows: Iterable[Dict[str, Any]]) -> List[int]:
    return [int(r["id"]) for r in rows]
