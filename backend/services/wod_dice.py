"""
Classic / Revised Storyteller (Old World of Darkness) d10 pool resolution.

This is the ONE classic implementation in the app; ``DiceService.roll_d10_pool``
and the ``/ai roll`` slash command both go through it.

Rules (Vampire: The Masquerade Revised core):
- Pool: roll that many d10.
- Difficulty (target number): 2-10, default 6; each die showing >= difficulty is a success.
- Each 1 cancels one success (net successes never go below 0).
- Botch: only when NO die was a success before cancelling AND at least one 1 showed.
  If there were successes but 1s cancelled them all, it is a simple failure.
- Specialty: each natural 10 counts as a success and is rolled again; a 10 on the
  reroll explodes again. 1s from the original pool cancel successes from the pool and
  from rerolls alike. A 1 on a reroll depends on the game line (``reroll_ones_cancel``,
  services.rules_edition.reroll_ones_cancel):
  - Mage (Mage: The Ascension Revised: "A botch on a re-roll does cancel a success as
    always"): a rerolled 1 cancels one success.
  - Werewolf (Revised: "any ones rolled on bonus dice granted by a specialty do not
    subtract successes"),
    Vampire (Revised is silent; app ruling) and custom systems: a rerolled 1 cancels
    nothing, rerolls only add.
- Willpower: declared before the roll, adds 1 automatic success that 1s cannot
  cancel. A willpower roll therefore never botches and always has >= 1 net success.
- 5+ net successes is an "exceptional success" (the Revised term; not "critical").

Every function that rolls takes an optional ``rng`` (anything with ``randint`` and
``shuffle``, e.g. ``random.Random(seed)``) so tests can be deterministic.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Tuple

from services.request_validation import RequestValidationError

MAX_POOL = 50
EXCEPTIONAL_THRESHOLD = 5
# Hard cap on specialty explosions so a pathological rng cannot loop forever.
MAX_SPECIALTY_REROLLS = 100


@dataclass
class StorytellerRollResult:
    dice: List[int]
    difficulty: int
    raw_successes: int
    ones: int
    net_successes: int
    botch: bool
    pool: int
    leniency_floor: Optional[int] = None
    specialty: bool = False
    specialty_rerolls: List[int] = field(default_factory=list)
    reroll_successes: int = 0
    # 1s among the rerolls, and whether they cancelled successes (Mage).
    reroll_ones: int = 0
    reroll_ones_cancel: bool = False
    willpower: bool = False
    exceptional: bool = False


def parse_pool_expression(pool_str: str) -> int:
    """Parse pool like '7', '4+3', '6-2+1' (digits with + or -, no spaces required)."""
    s = re.sub(r"\s+", "", (pool_str or "").strip())
    if not s:
        raise RequestValidationError("Dice pool is empty.")
    # Short terms only: a huge digit string would make int() raise its own ValueError.
    if len(s) > 60 or not re.fullmatch(r"\d{1,4}([+-]\d{1,4})*", s):
        raise RequestValidationError(
            "Invalid pool. Use digits with + or -, e.g. `5`, `4+3`, `7-1` (wound penalties)."
        )
    parts = re.split(r"(?=[+-])", s)
    total = sum(int(p) for p in parts)
    if total < 1:
        raise RequestValidationError("Pool must be at least 1 die.")
    if total > MAX_POOL:
        raise RequestValidationError(f"Pool capped at {MAX_POOL} dice for this command.")
    return total


def parse_roll_expression(expr: str, default_difficulty: int = 6) -> Tuple[int, int]:
    """
    Parse classic `/ai roll` payload.
    Forms:
      - `7` — 7 dice, default difficulty
      - `4+3@8` — pool 7, difficulty 8
      - `5 @ 7` — spaces allowed
      - `6 tn 7` / `6 diff 7`
    """
    raw = (expr or "").strip()
    if not raw:
        raise RequestValidationError(
            "Missing roll expression. Examples: `5`, `4+3`, `6@7` (pool@difficulty), TN 2–10."
        )

    difficulty = default_difficulty
    pool_part = raw

    if "@" in raw:
        left, _, right = raw.rpartition("@")
        pool_part = left.strip()
        diff_part = right.strip()
        if not pool_part:
            raise RequestValidationError("Missing dice pool before `@`.")
        if not diff_part.isdigit() or len(diff_part) > 2:
            raise RequestValidationError("Invalid difficulty after `@` (use 2–10).")
        difficulty = int(diff_part)
    else:
        m = re.match(r"^(.+?)(?:tn|diff)\s*(\d{1,2})\s*$", raw, re.IGNORECASE)
        if m:
            pool_part = m.group(1).strip()
            difficulty = int(m.group(2))

    pool = parse_pool_expression(pool_part)

    if difficulty < 2 or difficulty > 10:
        raise RequestValidationError("Difficulty (target number) must be between 2 and 10.")

    return pool, difficulty


def _rng(rng: Any = None) -> Any:
    return rng if rng is not None else random


def _valid_leniency_floor(leniency_floor: Any) -> Optional[int]:
    if leniency_floor is None:
        return None
    try:
        v = int(leniency_floor)
    except (TypeError, ValueError):
        return None
    return v if 2 <= v <= 10 else None


def _lenient_d10_pool(pool: int, floor: int, rng: Any = None) -> List[int]:
    """
    Room leniency: no 1s on any die; one die is always in [floor, 10];
    others are in [2, 10]. Order is shuffled.
    """
    r = _rng(rng)
    f = max(2, min(10, int(floor)))
    if pool < 1:
        return []
    if pool == 1:
        return [r.randint(f, 10)]
    dice = [r.randint(f, 10)]
    dice.extend(r.randint(2, 10) for _ in range(pool - 1))
    r.shuffle(dice)
    return dice


def roll_d10s(pool: int, leniency_floor: Optional[int] = None, rng: Any = None) -> List[int]:
    """Roll ``pool`` d10s, honouring a room leniency floor when one is set."""
    r = _rng(rng)
    lf = _valid_leniency_floor(leniency_floor)
    if lf is not None:
        return _lenient_d10_pool(pool, lf, rng=r)
    return [r.randint(1, 10) for _ in range(pool)]


def roll_specialty_rerolls(dice: Sequence[int], rng: Any = None) -> List[int]:
    """One reroll per natural 10 in ``dice``; each 10 on a reroll explodes again."""
    r = _rng(rng)
    pending = sum(1 for d in dice if d == 10)
    out: List[int] = []
    while pending > 0 and len(out) < MAX_SPECIALTY_REROLLS:
        pending -= 1
        d = r.randint(1, 10)
        out.append(d)
        if d == 10:
            pending += 1
    return out


def resolve_classic(
    dice: Sequence[int],
    difficulty: int,
    *,
    specialty_rerolls: Sequence[int] = (),
    willpower: bool = False,
    leniency_floor: Optional[int] = None,
    specialty: Optional[bool] = None,
    reroll_ones_cancel: bool = False,
) -> StorytellerRollResult:
    """
    Resolve an already-rolled classic pool (pure; no randomness).

    ``dice`` are the original pool; ``specialty_rerolls`` are the extra dice rolled
    for natural 10s (only meaningful for specialty rolls). ``reroll_ones_cancel``: 1s
    on rerolls cancel successes too (Mage; see the module docstring).
    """
    dice = [int(d) for d in dice]
    rerolls = [int(d) for d in specialty_rerolls]
    raw_successes = sum(1 for d in dice if d >= difficulty)
    ones = sum(1 for d in dice if d == 1)
    reroll_successes = sum(1 for d in rerolls if d >= difficulty)
    reroll_ones = sum(1 for d in rerolls if d == 1)
    cancelling = ones + (reroll_ones if reroll_ones_cancel else 0)
    dice_net = max(0, raw_successes + reroll_successes - cancelling)
    net = dice_net + (1 if willpower else 0)
    botch = (not willpower) and raw_successes == 0 and ones > 0
    return StorytellerRollResult(
        dice=dice,
        difficulty=difficulty,
        raw_successes=raw_successes,
        ones=ones,
        net_successes=net,
        botch=botch,
        pool=len(dice),
        leniency_floor=_valid_leniency_floor(leniency_floor),
        specialty=bool(rerolls) if specialty is None else bool(specialty),
        specialty_rerolls=rerolls,
        reroll_successes=reroll_successes,
        reroll_ones=reroll_ones,
        reroll_ones_cancel=bool(reroll_ones_cancel),
        willpower=bool(willpower),
        exceptional=net >= EXCEPTIONAL_THRESHOLD,
    )


def roll_classic(
    pool: int,
    difficulty: int = 6,
    *,
    specialty: bool = False,
    willpower: bool = False,
    leniency_floor: Optional[int] = None,
    rng: Any = None,
    reroll_ones_cancel: bool = False,
) -> StorytellerRollResult:
    """Roll and resolve a classic pool."""
    r = _rng(rng)
    dice = roll_d10s(pool, leniency_floor=leniency_floor, rng=r)
    rerolls = roll_specialty_rerolls(dice, rng=r) if specialty else []
    return resolve_classic(
        dice,
        difficulty,
        specialty_rerolls=rerolls,
        willpower=willpower,
        leniency_floor=leniency_floor,
        specialty=specialty,
        reroll_ones_cancel=reroll_ones_cancel,
    )


def roll_storyteller_pool(
    pool: int,
    difficulty: int,
    leniency_floor: Optional[int] = None,
    *,
    specialty: bool = False,
    willpower: bool = False,
    reroll_ones_cancel: bool = False,
    rng: Any = None,
) -> StorytellerRollResult:
    """Backwards-compatible name for :func:`roll_classic` (dice returned sorted)."""
    res = roll_classic(
        pool,
        difficulty,
        specialty=specialty,
        willpower=willpower,
        reroll_ones_cancel=reroll_ones_cancel,
        leniency_floor=leniency_floor,
        rng=rng,
    )
    res.dice = sorted(res.dice)
    return res


def classic_outcome_label(result: StorytellerRollResult) -> str:
    if result.botch:
        return "Botch"
    if result.net_successes == 0:
        return "Failure"
    if result.exceptional:
        return "Exceptional success"
    return "Success"


def format_storyteller_roll_markdown(
    result: StorytellerRollResult, game_system: str = ""
) -> str:
    sys_note = ""
    if game_system:
        sys_note = f"\n**Campaign system:** {game_system} · **Rules:** Classic (Revised)\n"
    if result.leniency_floor is not None:
        sys_note += (
            f"\n**Room leniency (floor {result.leniency_floor}):** "
            "no **1**s; with 2+ dice, at least one die is **≥ floor**. "
            "Botches from 1s cannot occur.\n"
        )

    dice_show = ", ".join(str(d) for d in result.dice)
    n = result.net_successes
    if result.botch:
        outcome = "**BOTCH** (no die succeeded and at least one 1 was rolled)."
    elif n == 0:
        outcome = "**Failure** (no net successes)."
    elif result.exceptional:
        outcome = f"**Exceptional success** — {n} successes."
    elif n == 1:
        outcome = "**1 success**."
    else:
        outcome = f"**{n} successes**."

    extra = ""
    if result.specialty_rerolls:
        extra += (
            f"- **Specialty rerolls (10s):** {', '.join(str(d) for d in result.specialty_rerolls)}"
            f" → +{result.reroll_successes}"
            + (f", {result.reroll_ones} × 1 cancel" if result.reroll_ones_cancel and result.reroll_ones else "")
            + "\n"
        )
    if result.willpower:
        extra += "- **Willpower:** +1 automatic success (cannot be cancelled)\n"

    return (
        "**`/ai roll`** — Old World of Darkness (Storyteller d10)\n"
        f"{sys_note}\n"
        f"- **Pool:** {result.pool} dice · **Difficulty:** {result.difficulty}+\n"
        f"- **Dice:** {dice_show}\n"
        f"- **Raw successes (≥{result.difficulty}):** {result.raw_successes} · "
        f"**1s (cancel successes):** {result.ones}\n"
        f"{extra}"
        f"- **Net successes:** {n}\n\n"
        f"{outcome}\n\n"
        "_Revised: 1s cancel successes; botch only if no die succeeded and a 1 showed. "
        "5+ successes = exceptional._\n"
        "_Syntax: `pool`, `4+3`, `6-1`, or `5@8` for pool@difficulty._"
    )
