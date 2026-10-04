"""
Dice animation markers (chat rows with ai_message_kind dice_animation[_hidden]:<id>).

Since v0.9 phase 2 the dice API (routes/dice.py: /roll, /roll/<id>/reroll, /rouse) saves the
marker and the result line itself, so a dice card in chat always comes from a real server roll.
Players can no longer post dice_* kinds through POST /campaigns/<c>/locations/<l>
(routes/messages.py); only site admins can (the /ai roll slash flow, which is admin-only).

- build_marker(): Python port of frontend/src/dice/diceMarker.js buildDiceMarker(), plus
  roll_id (the dice_rolls row) so the client can tell a server roll.
- sanitize_marker(): whitelist keys/values and clamp the timing of an admin-posted marker
  (duration at most MAX_DURATION_MS, start within START_SKEW_MS of now), so a marker can't
  hold every client's overlay open or replay an old roll as fresh.
"""

from __future__ import annotations

import json
import secrets
import time
from typing import Any, Dict, Optional

MARKER_KEYS = frozenset({
    "animation_id", "started_at_ms", "duration_ms", "rules_edition", "difficulty", "successes",
    "is_botch", "dice_preview", "hunger_flags", "extra_dice_count", "pool_size", "margin",
    "outcome", "is_critical", "is_messy_critical", "is_bestial_failure", "is_total_failure",
    "is_exceptional", "specialty", "specialty_rerolls", "willpower", "diceFinal",
    "roll_id", "roll_kind",
})
MAX_MARKER_CHARS = 2000
MAX_PREVIEW_DICE = 10
DEFAULT_DURATION_MS = 3000
MAX_DURATION_MS = 8000
START_SKEW_MS = 60_000
_MAX_MARKER_STR = 64
_MAX_MARKER_LIST = 40

# ai_message_kind prefixes only the server (or a site admin) may write.
DICE_KIND_PREFIXES = ("dice_animation", "dice_roll", "dice_rouse")


def is_dice_kind(kind: Optional[str]) -> bool:
    k = str(kind or "").strip().lower()
    return k.startswith(DICE_KIND_PREFIXES)


def now_ms() -> int:
    return int(time.time() * 1000)


def new_animation_id(roll_id: Any) -> str:
    """Unique per post (a reroll posts a second marker for the same roll)."""
    return f"r{int(roll_id)}-{secrets.token_hex(4)}"


def _num(v, default=0):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v) if "." in str(v) else int(v)
    except (TypeError, ValueError):
        return default


def build_marker(result: Dict[str, Any], *, animation_id: str, roll_id: int,
                 roll_kind: str = "manual", started_at_ms: Optional[int] = None,
                 duration_ms: int = DEFAULT_DURATION_MS) -> Dict[str, Any]:
    r = result or {}
    base = {
        "animation_id": animation_id,
        "started_at_ms": int(started_at_ms if started_at_ms is not None else now_ms()),
        "duration_ms": int(min(max(duration_ms, 0), MAX_DURATION_MS)),
        "roll_id": int(roll_id),
        "roll_kind": roll_kind,
    }
    if str(r.get("rules_edition") or "").lower() == "v5":
        normal = list(r.get("normal_dice") or [])
        hunger = list(r.get("hunger_dice") or [])
        difficulty = _num(r.get("difficulty"), 1)
        successes = _num(r.get("successes", r.get("net_successes")))
        hunger_p = hunger[:MAX_PREVIEW_DICE]
        normal_p = normal[:max(0, MAX_PREVIEW_DICE - len(hunger_p))]
        total = len(normal) + len(hunger)
        return {
            **base,
            "rules_edition": "v5",
            "difficulty": difficulty,
            "successes": successes,
            "is_botch": False,
            "dice_preview": normal_p + hunger_p,
            "hunger_flags": [False] * len(normal_p) + [True] * len(hunger_p),
            "extra_dice_count": max(0, total - len(normal_p) - len(hunger_p)),
            "pool_size": total,
            "margin": _num(r.get("margin"), successes - difficulty),
            "outcome": "win" if r.get("outcome") == "win" else "fail",
            "is_critical": bool(r.get("is_critical")),
            "is_messy_critical": bool(r.get("is_messy_critical")),
            "is_bestial_failure": bool(r.get("is_bestial_failure")),
            "is_total_failure": bool(r.get("is_total_failure")),
        }
    results = list(r.get("results") or r.get("dice") or [])
    preview = results[:MAX_PREVIEW_DICE]
    exceptional = bool(r.get("is_exceptional"))
    return {
        **base,
        "rules_edition": "classic",
        "difficulty": _num(r.get("difficulty"), 6),
        "successes": _num(r.get("successes", r.get("net_successes"))),
        "is_botch": bool(r.get("is_botch", r.get("botch"))),
        "dice_preview": preview,
        "extra_dice_count": max(0, len(results) - len(preview)),
        "pool_size": len(results),
        "is_critical": exceptional,
        "is_exceptional": exceptional,
        "specialty": bool(r.get("specialty")),
        "specialty_rerolls": list(r.get("specialty_rerolls") or [])[:MAX_PREVIEW_DICE],
        "willpower": bool(r.get("willpower")),
    }


def _value_ok(v) -> bool:
    if v is None or isinstance(v, (bool, int, float)):
        return True
    if isinstance(v, str):
        return len(v) <= _MAX_MARKER_STR
    if isinstance(v, list):
        return len(v) <= _MAX_MARKER_LIST and all(
            x is None or isinstance(x, (bool, int, float)) for x in v
        )
    return False


def clamp_timing(marker: Dict[str, Any], now: Optional[int] = None) -> Dict[str, Any]:
    """duration_ms in [0, MAX_DURATION_MS]; started_at_ms within ±START_SKEW_MS of now."""
    now = now_ms() if now is None else int(now)
    out = dict(marker)
    d = out.get("duration_ms")
    d = DEFAULT_DURATION_MS if isinstance(d, bool) or not isinstance(d, (int, float)) else int(d)
    out["duration_ms"] = min(max(d, 0), MAX_DURATION_MS)
    s = out.get("started_at_ms")
    s = now if isinstance(s, bool) or not isinstance(s, (int, float)) else int(s)
    out["started_at_ms"] = min(max(s, now - START_SKEW_MS), now + START_SKEW_MS)
    return out


def sanitize_marker(content: str, ai_message_kind: Optional[str],
                    now: Optional[int] = None) -> Optional[str]:
    """
    The cleaned marker JSON for a dice_animation[_hidden]:<id> row, or None if it isn't a valid
    marker (unknown keys, nested values, id mismatch, too long).
    """
    kind = str(ai_message_kind or "").strip().lower()
    prefix, _, anim_id = kind.partition(":")
    if prefix not in ("dice_animation", "dice_animation_hidden") or not anim_id:
        return None
    if not isinstance(content, str) or len(content) > MAX_MARKER_CHARS:
        return None
    try:
        obj = json.loads(content)
    except (TypeError, ValueError):
        return None
    if not isinstance(obj, dict) or str(obj.get("animation_id")).lower() != anim_id:
        return None
    if not set(obj) <= MARKER_KEYS or not all(_value_ok(v) for v in obj.values()):
        return None
    return json.dumps(clamp_timing(obj, now), separators=(",", ":"))
