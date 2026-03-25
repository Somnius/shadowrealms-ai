"""
Classic / Revised Storyteller (Old World of Darkness) d10 pool resolution.

Rules implemented (Revised Storyteller style, widely used in late oWoD):
- Pool: roll that many d10.
- Difficulty (target number): 2–10; each die showing value >= TN is a success.
- 1s never count as successes; each 1 cancels one success (successes cannot go below 0).
- Botch: zero net successes after cancellations and the roll included at least one 1.

See: https://whitewolf.fandom.com/wiki/Botch (Revised vs original botch differs;
we use the Revised rule: at least one 1 and no successes after canceling.)
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class StorytellerRollResult:
    dice: List[int]
    difficulty: int
    raw_successes: int
    ones: int
    net_successes: int
    botch: bool
    pool: int


def parse_pool_expression(pool_str: str) -> int:
    """Parse pool like '7', '4+3', '6-2+1' (digits with + or -, no spaces required)."""
    s = re.sub(r"\s+", "", (pool_str or "").strip())
    if not s:
        raise ValueError("Dice pool is empty.")
    if not re.fullmatch(r"\d+([+-]\d+)*", s):
        raise ValueError(
            "Invalid pool. Use digits with + or -, e.g. `5`, `4+3`, `7-1` (wound penalties)."
        )
    parts = re.split(r"(?=[+-])", s)
    total = sum(int(p) for p in parts)
    if total < 1:
        raise ValueError("Pool must be at least 1 die.")
    if total > 50:
        raise ValueError("Pool capped at 50 dice for this command.")
    return total


def parse_roll_expression(expr: str, default_difficulty: int = 6) -> Tuple[int, int]:
    """
    Parse `/ai roll` payload.
    Forms:
      - `7` — 7 dice, default difficulty
      - `4+3@8` — pool 7, difficulty 8
      - `5 @ 7` — spaces allowed
    """
    raw = (expr or "").strip()
    if not raw:
        raise ValueError(
            "Missing roll expression. Examples: `5`, `4+3`, `6@7` (pool@difficulty), TN 6–10."
        )

    difficulty = default_difficulty
    pool_part = raw

    if "@" in raw:
        left, _, right = raw.rpartition("@")
        pool_part = left.strip()
        diff_part = right.strip()
        if not pool_part:
            raise ValueError("Missing dice pool before `@`.")
        if not diff_part.isdigit():
            raise ValueError(f"Invalid difficulty after `@`: {diff_part!r} (use 6–10).")
        difficulty = int(diff_part)
    else:
        m = re.match(r"^(.+?)(?:tn|diff)\s*(\d+)\s*$", raw, re.IGNORECASE)
        if m:
            pool_part = m.group(1).strip()
            difficulty = int(m.group(2))

    pool = parse_pool_expression(pool_part)

    if difficulty < 2 or difficulty > 10:
        raise ValueError("Difficulty (target number) must be between 2 and 10.")

    return pool, difficulty


def roll_storyteller_pool(pool: int, difficulty: int) -> StorytellerRollResult:
    dice = [random.randint(1, 10) for _ in range(pool)]
    raw_successes = sum(1 for d in dice if d >= difficulty)
    ones = sum(1 for d in dice if d == 1)
    net = raw_successes - ones
    if net < 0:
        net = 0
    botch = net == 0 and ones > 0
    return StorytellerRollResult(
        dice=sorted(dice),
        difficulty=difficulty,
        raw_successes=raw_successes,
        ones=ones,
        net_successes=net,
        botch=botch,
        pool=pool,
    )


def format_storyteller_roll_markdown(
    result: StorytellerRollResult, game_system: str = ""
) -> str:
    sys_note = ""
    if game_system:
        sys_note = f"\n**Campaign system:** {game_system}\n"

    dice_show = ", ".join(str(d) for d in result.dice)
    if result.botch:
        outcome = "**BOTCH** (no successes after 1s cancel, and at least one 1 was rolled)."
    elif result.net_successes == 0:
        outcome = "**Failure** (no net successes)."
    elif result.net_successes == 1:
        outcome = "**1 success**."
    else:
        outcome = f"**{result.net_successes} successes**."

    return (
        "**`/ai roll`** — Old World of Darkness (Storyteller d10)\n"
        f"{sys_note}\n"
        f"- **Pool:** {result.pool} dice · **Difficulty:** {result.difficulty}+\n"
        f"- **Dice:** {dice_show}\n"
        f"- **Raw successes (≥{result.difficulty}):** {result.raw_successes} · "
        f"**1s (cancel successes):** {result.ones}\n"
        f"- **Net successes:** {result.net_successes}\n\n"
        f"{outcome}\n\n"
        "_Revised Storyteller: 1s cancel successes; botch = no net successes with any 1._\n"
        "_Syntax: `pool`, `4+3`, `6-1`, or `5@8` for pool@TN._"
    )
