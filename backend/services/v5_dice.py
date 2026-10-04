"""
Vampire: The Masquerade 5th Edition (V5) dice resolution. Pure functions only.

Rules:
- Roll a pool of d10s. ``min(hunger, pool)`` of them are Hunger dice, the rest normal.
- 6-10 is a success. There is no botch and 1s cancel nothing.
- Every PAIR of 10s (normal and Hunger counted together) adds 2 extra successes,
  so a pair of 10s is worth 4 successes.
- Difficulty = successes needed (0-10, default 1). The roll wins when
  successes >= difficulty. App ruling: 0 successes is a total failure and never
  wins, even at difficulty 0 (difficulty 0 just means "count successes").
- Critical: at least one pair of 10s and the roll wins.
- Messy critical: a critical where at least one of the 10s is on a Hunger die.
- Bestial failure: the roll fails and any Hunger die shows a 1.
- Willpower reroll: after the roll, the roller may reroll up to 3 NORMAL dice once.
- Rouse check: roll 1 die; 6+ means no Hunger gain, otherwise Hunger +1 (max 5).

Every rolling function takes an optional ``rng`` (``randint``/``shuffle``).
"""

from __future__ import annotations

import random
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from services.request_validation import RequestValidationError

MAX_POOL = 50
MAX_HUNGER = 5
MAX_DIFFICULTY = 10
DEFAULT_DIFFICULTY = 1
MAX_WILLPOWER_REROLL = 3
SUCCESS_TN = 6


def _rng(rng: Any = None) -> Any:
    return rng if rng is not None else random


def clamp_hunger(hunger: Any) -> int:
    try:
        h = int(hunger)
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_HUNGER, h))


def _roll_dice(n: int, leniency_floor: Optional[int], rng: Any) -> List[int]:
    from services.wod_dice import roll_d10s

    return roll_d10s(n, leniency_floor=leniency_floor, rng=rng)


def resolve_v5(
    normal_dice: Sequence[int],
    hunger_dice: Sequence[int],
    difficulty: int = DEFAULT_DIFFICULTY,
) -> Dict[str, Any]:
    """Resolve already-rolled V5 dice (pure)."""
    normal = [int(d) for d in normal_dice]
    hunger = [int(d) for d in hunger_dice]
    difficulty = int(difficulty)
    all_dice = normal + hunger
    base = sum(1 for d in all_dice if d >= SUCCESS_TN)
    tens_normal = sum(1 for d in normal if d == 10)
    tens_hunger = sum(1 for d in hunger if d == 10)
    pairs = (tens_normal + tens_hunger) // 2
    successes = base + 2 * pairs
    win = successes >= difficulty and successes > 0
    is_critical = win and pairs >= 1
    is_messy = is_critical and tens_hunger > 0
    is_bestial = (not win) and any(d == 1 for d in hunger)
    return {
        "rules_edition": "v5",
        "results": all_dice,
        "normal_dice": normal,
        "hunger_dice": hunger,
        "pool": len(all_dice),
        "hunger": len(hunger),
        "difficulty": difficulty,
        "successes": successes,
        "critical_pairs": pairs,
        "margin": successes - difficulty,
        "outcome": "win" if win else "fail",
        "is_critical": is_critical,
        "is_messy_critical": is_messy,
        "is_bestial_failure": is_bestial,
        "is_total_failure": successes == 0,
        "is_botch": False,
    }


def roll_v5(
    pool: int,
    hunger: int = 0,
    difficulty: int = DEFAULT_DIFFICULTY,
    *,
    leniency_floor: Optional[int] = None,
    rng: Any = None,
) -> Dict[str, Any]:
    """Roll ``pool`` dice, of which ``min(hunger, pool)`` are Hunger dice."""
    r = _rng(rng)
    pool = int(pool)
    if pool < 1 or pool > MAX_POOL:
        raise RequestValidationError(f"Pool must be between 1 and {MAX_POOL}.")
    difficulty = int(difficulty)
    if difficulty < 0 or difficulty > MAX_DIFFICULTY:
        raise RequestValidationError(f"Difficulty must be between 0 and {MAX_DIFFICULTY}.")
    h = min(clamp_hunger(hunger), pool)
    dice = _roll_dice(pool, leniency_floor, r)
    # Leniency guarantees one high die somewhere in the list; which slots are
    # Hunger dice is fixed (last h), the list is already shuffled.
    normal, hunger_dice = dice[: pool - h], dice[pool - h:]
    res = resolve_v5(normal, hunger_dice, difficulty)
    res["leniency_floor"] = leniency_floor
    res["rerolled"] = False
    res["rerolled_indices"] = []
    return res


def validate_reroll_indices(normal_dice: Sequence[int], indices: Sequence[Any]) -> List[int]:
    """Return the cleaned index list or raise RequestValidationError."""
    if not isinstance(indices, (list, tuple)) or not indices:
        raise RequestValidationError("indices must be a non-empty list of normal-die positions.")
    out: List[int] = []
    for i in indices:
        # Only real integers: bools (int subclass), floats and strings are refused.
        if isinstance(i, bool) or not isinstance(i, int):
            raise RequestValidationError("Each die index must be an integer.")
        iv = i
        if iv < 0 or iv >= len(normal_dice):
            raise RequestValidationError(
                f"Die index {iv} is out of range (0–{len(normal_dice) - 1}, normal dice only)."
            )
        if iv in out:
            raise RequestValidationError(f"Die index {iv} given twice.")
        out.append(iv)
    if len(out) > MAX_WILLPOWER_REROLL:
        raise RequestValidationError(f"A Willpower reroll covers at most {MAX_WILLPOWER_REROLL} dice.")
    return out


def apply_reroll(
    normal_dice: Sequence[int],
    hunger_dice: Sequence[int],
    difficulty: int,
    indices: Sequence[Any],
    new_values: Sequence[int],
) -> Dict[str, Any]:
    """Replace the chosen normal dice with ``new_values`` and re-resolve (pure)."""
    idx = validate_reroll_indices(normal_dice, indices)
    if len(new_values) != len(idx):
        raise ValueError("new_values must match indices.")  # internal bug, not client input
    normal = list(normal_dice)
    before = [normal[i] for i in idx]
    for i, v in zip(idx, new_values):
        normal[i] = int(v)
    res = resolve_v5(normal, hunger_dice, difficulty)
    res["rerolled"] = True
    res["rerolled_indices"] = idx
    res["rerolled_from"] = before
    return res


def willpower_reroll(
    normal_dice: Sequence[int],
    hunger_dice: Sequence[int],
    difficulty: int,
    indices: Sequence[Any],
    *,
    leniency_floor: Optional[int] = None,
    rng: Any = None,
) -> Dict[str, Any]:
    """Reroll up to 3 normal dice once. Hunger dice are never rerolled."""
    r = _rng(rng)
    idx = validate_reroll_indices(normal_dice, indices)
    lf = leniency_floor
    if lf is not None:
        # Under leniency, rerolled dice also never show 1 (floor only applies to the
        # original "one die >= floor" guarantee, which is already satisfied).
        new_vals = [r.randint(2, 10) for _ in idx]
    else:
        new_vals = [r.randint(1, 10) for _ in idx]
    res = apply_reroll(normal_dice, hunger_dice, difficulty, idx, new_vals)
    res["leniency_floor"] = leniency_floor
    return res


class NoWillpowerLeft(Exception):
    """The Willpower track is full of Aggravated damage: there is nothing left to spend."""


def _as_int(v: Any) -> Optional[int]:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str) and v.strip().lstrip("+-").isdigit():
        return int(v.strip())
    return None


def willpower_track(wod_meta: Any, attributes: Any = None) -> Optional[Dict[str, int]]:
    """
    The character's Willpower track as {max, superficial, aggravated}, cleaned up.
    Uses wod_meta.willpower when it has a usable max; otherwise max = Composure + Resolve
    (core p. 157) with no damage. None when neither is on the sheet.
    """
    track = wod_meta.get("willpower") if isinstance(wod_meta, dict) else None
    mx = _as_int(track.get("max")) if isinstance(track, dict) else None
    if mx is None or mx < 1:
        attrs = attributes if isinstance(attributes, dict) else {}
        comp, res = _as_int(attrs.get("composure")), _as_int(attrs.get("resolve"))
        if comp is None or res is None or comp + res < 1:
            return None
        return {"max": comp + res, "superficial": 0, "aggravated": 0}
    agg = min(max(_as_int(track.get("aggravated")) or 0, 0), mx)
    sup = min(max(_as_int(track.get("superficial")) or 0, 0), mx - agg)
    return {"max": mx, "superficial": sup, "aggravated": agg}


def spend_willpower(track: Dict[str, int]) -> Dict[str, Any]:
    """
    Mark one spent Willpower point (core p. 122 / p. 126; docs/rules/V5.md §1.5).
    The spend is 1 Superficial Willpower damage, never halved. When every box is
    already filled, one Superficial box turns Aggravated instead. A track full of
    Aggravated damage has nothing left to spend: NoWillpowerLeft (app ruling, the
    book gives no further step). Pure; returns {'before', 'after', 'damage'} where
    damage is 'superficial' or 'aggravated'.
    """
    mx, sup, agg = track["max"], track["superficial"], track["aggravated"]
    if sup + agg < mx:
        after, damage = {"max": mx, "superficial": sup + 1, "aggravated": agg}, "superficial"
    elif sup > 0:
        after, damage = {"max": mx, "superficial": sup - 1, "aggravated": agg + 1}, "aggravated"
    else:
        raise NoWillpowerLeft()
    return {"before": dict(track), "after": after, "damage": damage}


def resolve_rouse(die: int, hunger_before: int) -> Dict[str, Any]:
    h = clamp_hunger(hunger_before)
    die = int(die)
    success = die >= SUCCESS_TN
    after = h if success else min(MAX_HUNGER, h + 1)
    return {
        "die": die,
        "success": success,
        "hunger_before": h,
        "hunger_after": after,
        # Failing at Hunger 5 cannot raise Hunger further; V5 calls for a hunger frenzy test.
        "at_max_hunger": (not success) and h >= MAX_HUNGER,
    }


def rouse_check(hunger_before: int, *, rng: Any = None) -> Dict[str, Any]:
    return resolve_rouse(_rng(rng).randint(1, 10), hunger_before)


def outcome_label(res: Dict[str, Any]) -> str:
    if res.get("outcome") == "win":
        if res.get("is_messy_critical"):
            return "Messy critical"
        if res.get("is_critical"):
            return "Critical win"
        return "Win"
    if res.get("is_bestial_failure"):
        return "Bestial failure"
    if res.get("is_total_failure"):
        return "Total failure"
    return "Failure"


_V5_EXPR_RE = re.compile(
    r"^(?P<pool>[\d\s+\-]+?)\s*"
    r"(?:(?:@\s*(?P<diff>\d{1,2}))\s*(?:h\s*(?P<h>\d{1,2}))?|(?:h\s*(?P<h2>\d{1,2}))\s*(?:@\s*(?P<diff2>\d{1,2}))?)?\s*$",
    re.IGNORECASE,
)


def parse_v5_roll_expression(
    expr: str, default_difficulty: int = DEFAULT_DIFFICULTY, default_hunger: int = 0
) -> Tuple[int, int, int]:
    """
    Parse V5 `/ai roll` payload: ``pool[@difficulty][h<hunger>]``.
    Examples: ``6``, ``6@3``, ``6h2``, ``6@3h2``, ``4+2@2 h1`` (``h2@3`` order also accepted).
    Returns (pool, difficulty, hunger).
    """
    from services.wod_dice import parse_pool_expression

    raw = (expr or "").strip()
    if not raw:
        raise RequestValidationError(
            "Missing roll expression. V5 examples: `6`, `6@3` (pool@successes needed), `6@3h2` (Hunger 2)."
        )
    m = _V5_EXPR_RE.match(raw)
    if not m:
        raise RequestValidationError(
            "Invalid V5 roll. Use `pool[@difficulty][h<hunger>]`, e.g. `6@3h2`."
        )
    pool = parse_pool_expression(m.group("pool"))
    diff_s = m.group("diff") or m.group("diff2")
    h_s = m.group("h") or m.group("h2")
    difficulty = int(diff_s) if diff_s is not None else int(default_difficulty)
    hunger = int(h_s) if h_s is not None else int(default_hunger)
    if difficulty < 0 or difficulty > MAX_DIFFICULTY:
        raise RequestValidationError("V5 difficulty (successes needed) must be between 0 and 10.")
    if hunger < 0 or hunger > MAX_HUNGER:
        raise RequestValidationError("Hunger must be between 0 and 5.")
    return pool, difficulty, hunger


def format_v5_roll_markdown(res: Dict[str, Any], game_system: str = "", command: str = "/ai roll") -> str:
    sys_note = ""
    if game_system:
        sys_note = f"\n**Campaign system:** {game_system} · **Rules:** V5\n"
    lf = res.get("leniency_floor")
    if lf is not None:
        sys_note += (
            f"\n**Room leniency (floor {lf}):** no **1**s; with 2+ dice, at least one die is **≥ floor**. "
            "Bestial failures cannot occur.\n"
        )
    normal = ", ".join(str(d) for d in res["normal_dice"]) or "—"
    hunger = ", ".join(str(d) for d in res["hunger_dice"]) or "—"
    label = outcome_label(res)
    margin = res["margin"]
    return (
        f"**`{command}`** — Vampire: The Masquerade V5\n"
        f"{sys_note}\n"
        f"- **Pool:** {res['pool']} dice ({res['hunger']} Hunger) · **Difficulty:** {res['difficulty']} successes\n"
        f"- **Normal dice:** {normal}\n"
        f"- **Hunger dice:** {hunger}\n"
        f"- **Successes:** {res['successes']} (pairs of 10s: {res['critical_pairs']}) · **Margin:** {margin:+d}\n\n"
        f"**{label}**\n\n"
        "_V5: 6+ succeeds, each pair of 10s = 4 successes; no botch. "
        "Hunger 10 in a critical = messy; Hunger 1 on a failure = bestial._\n"
        "_Syntax: `pool[@difficulty][h<hunger>]`, e.g. `6@3h2`._"
    )


def format_rouse_markdown(res: Dict[str, Any], character_name: Optional[str] = None) -> str:
    who = f"**{character_name}**" if character_name else "Rouse check"
    if res["success"]:
        tail = f"no Hunger gain (Hunger stays **{res['hunger_after']}**)."
    elif res.get("at_max_hunger"):
        tail = "failed at Hunger **5** — Hunger cannot rise further; test for **hunger frenzy**."
    else:
        tail = f"Hunger **{res['hunger_before']} → {res['hunger_after']}**."
    # Fixed English template: the frontend parses it (chat/messageModel.js parseRouseLine) to show
    # a translated line, so keep the wording in sync with that parser.
    prefix = f"{who} makes a Rouse check" if character_name else "**Rouse check**"
    return f"{prefix}: rolled **{res['die']}** — {'success' if res['success'] else 'failure'}, {tail}"
