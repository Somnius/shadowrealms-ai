import random

import pytest

from services.wod_dice import (
    StorytellerRollResult,
    classic_degree,
    classic_outcome_label,
    format_storyteller_roll_markdown,
    parse_pool_expression,
    parse_roll_expression,
    resolve_classic,
    roll_classic,
    roll_specialty_rerolls,
    roll_storyteller_pool,
)


class FixedRng:
    """randint returns queued values in order; shuffle is a no-op."""

    def __init__(self, values):
        self.values = list(values)

    def randint(self, lo, hi):
        v = self.values.pop(0)
        assert lo <= v <= hi, (v, lo, hi)
        return v

    def shuffle(self, seq):
        pass


# --- resolution (explicit dice) -------------------------------------------------

def test_plain_successes():
    r = resolve_classic([6, 7, 3, 2], 6)
    assert (r.raw_successes, r.ones, r.net_successes, r.botch) == (2, 0, 2, False)


def test_ones_cancel_successes():
    r = resolve_classic([8, 9, 1, 4], 6)
    assert r.net_successes == 1
    assert not r.botch


def test_book_example_is_failure_not_botch():
    # Revised p.192: 9,1,1,8,1 at difficulty 8 -> failure (successes were rolled)
    r = resolve_classic([9, 1, 1, 8, 1], 8)
    assert r.raw_successes == 2
    assert r.net_successes == 0
    assert r.botch is False
    assert classic_outcome_label(r) == "Failure"


def test_cancelled_to_exactly_zero_is_failure():
    r = resolve_classic([7, 1], 6)
    assert r.net_successes == 0 and not r.botch


def test_botch_requires_no_successes_and_a_one():
    r = resolve_classic([1, 3, 5], 6)
    assert r.botch is True
    assert classic_outcome_label(r) == "Botch"


def test_no_successes_no_ones_is_failure():
    r = resolve_classic([2, 3, 5], 6)
    assert r.net_successes == 0 and not r.botch


def test_ten_is_always_success_even_at_difficulty_10():
    r = resolve_classic([10, 9], 10)
    assert r.raw_successes == 1


def test_degrees_four_exceptional_five_phenomenal():
    # Revised core: "Four Successes — Exceptional", "Five or More Successes — Phenomenal".
    r = resolve_classic([6, 6, 7, 8, 9], 6)
    assert r.net_successes == 5 and r.phenomenal and not r.exceptional
    assert classic_outcome_label(r) == "Phenomenal success"
    r4 = resolve_classic([6, 6, 7, 8], 6)
    assert r4.exceptional and not r4.phenomenal
    assert classic_outcome_label(r4) == "Exceptional success"
    r3 = resolve_classic([6, 6, 7], 6)
    assert not r3.exceptional and not r3.phenomenal and classic_outcome_label(r3) == "Success"
    assert [classic_degree(n) for n in (0, 1, 2, 3, 4, 5, 9)] == [
        "none", "marginal", "moderate", "complete", "exceptional", "phenomenal", "phenomenal"]


def test_result_dict_flags():
    from services.dice_service import DiceService

    d4 = DiceService.classic_result_dict(resolve_classic([6, 6, 7, 8], 6))
    assert d4["is_exceptional"] and not d4["is_phenomenal"] and d4["is_critical"]
    assert d4["message"].startswith("**Exceptional success!**")
    d5 = DiceService.classic_result_dict(resolve_classic([6, 6, 7, 8, 9], 6))
    assert d5["is_phenomenal"] and not d5["is_exceptional"] and d5["is_critical"]
    assert d5["message"].startswith("**Phenomenal success!**")
    d3 = DiceService.classic_result_dict(resolve_classic([6, 6, 7], 6))
    assert not d3["is_critical"]


def test_willpower_adds_uncancellable_success():
    r = resolve_classic([7, 1, 1], 6, willpower=True)
    # 1 success - 2 ones -> 0 from dice, +1 willpower
    assert r.net_successes == 1
    assert not r.botch


def test_willpower_prevents_botch():
    r = resolve_classic([1, 2, 3], 6, willpower=True)
    assert r.botch is False
    assert r.net_successes == 1


def test_specialty_rerolls_add_successes_and_reroll_ones_do_not_cancel():
    r = resolve_classic([10, 4, 3], 6, specialty_rerolls=[7, 1])
    # 1 raw (the 10) + 1 reroll success (7); the reroll 1 cancels nothing
    assert r.raw_successes == 1
    assert r.reroll_successes == 1
    assert r.net_successes == 2


def test_original_ones_cancel_reroll_successes_too():
    r = resolve_classic([10, 1], 6, specialty_rerolls=[8])
    assert r.net_successes == 1  # 1 + 1 - 1


def test_formatter_uses_degrees_not_critical():
    md = format_storyteller_roll_markdown(resolve_classic([6, 6, 7, 8, 9], 6), "vampire")
    assert "**Phenomenal success** — 5 successes." in md
    assert "4 successes = exceptional, 5+ = phenomenal" in md
    assert "CRITICAL" not in md.upper()
    md4 = format_storyteller_roll_markdown(resolve_classic([6, 6, 7, 8], 6), "vampire")
    assert "**Exceptional success** — 4 successes." in md4


# --- rolling with injected rng ------------------------------------------------

def test_specialty_explodes_on_rerolled_tens():
    # pool [10, 3]; reroll 10 -> 10 again -> 4
    rng = FixedRng([10, 3, 10, 4])
    r = roll_classic(2, 6, specialty=True, rng=rng)
    assert r.dice == [10, 3]
    assert r.specialty_rerolls == [10, 4]
    assert r.net_successes == 2  # original 10 + rerolled 10
    assert rng.values == []


def test_no_specialty_no_rerolls():
    rng = FixedRng([10, 10, 2])
    r = roll_classic(3, 6, specialty=False, rng=rng)
    assert r.specialty_rerolls == []
    assert r.net_successes == 2


def test_roll_specialty_rerolls_count():
    assert roll_specialty_rerolls([1, 2, 3], rng=FixedRng([])) == []
    assert roll_specialty_rerolls([10, 10], rng=FixedRng([5, 6])) == [5, 6]


def test_seeded_rolls_are_reproducible():
    a = roll_classic(10, 6, specialty=True, rng=random.Random(42))
    b = roll_classic(10, 6, specialty=True, rng=random.Random(42))
    assert a == b


def test_many_seeded_rolls_obey_rules():
    rng = random.Random(1234)
    for _ in range(2000):
        pool = rng.randint(1, 12)
        diff = rng.randint(2, 10)
        r = roll_classic(pool, diff, specialty=rng.random() < 0.5, rng=rng)
        assert len(r.dice) == pool
        assert all(1 <= d <= 10 for d in r.dice)
        assert r.net_successes >= 0
        if r.botch:
            assert r.raw_successes == 0 and r.ones > 0
        if r.raw_successes > 0:
            assert not r.botch


def test_leniency_has_no_ones_and_one_die_at_floor():
    rng = random.Random(7)
    for _ in range(500):
        r = roll_classic(5, 6, leniency_floor=8, rng=rng)
        assert 1 not in r.dice
        assert max(r.dice) >= 8
        assert not r.botch


def test_roll_storyteller_pool_sorted_and_compatible():
    r = roll_storyteller_pool(6, 6, rng=random.Random(3))
    assert isinstance(r, StorytellerRollResult)
    assert r.dice == sorted(r.dice)


# --- parsing -----------------------------------------------------------------

def test_parse_pool_expression():
    assert parse_pool_expression("4+3") == 7
    assert parse_pool_expression("7 - 1") == 6
    with pytest.raises(ValueError):
        parse_pool_expression("0")
    with pytest.raises(ValueError):
        parse_pool_expression("51")
    with pytest.raises(ValueError):
        parse_pool_expression("abc")


def test_parse_roll_expression():
    assert parse_roll_expression("5") == (5, 6)
    assert parse_roll_expression("4+3@8") == (7, 8)
    assert parse_roll_expression("6 tn 7") == (6, 7)
    with pytest.raises(ValueError):
        parse_roll_expression("5@11")


# --- specialty reroll 1s per game line ------------------------------------------------------

def test_mage_reroll_ones_cancel_successes():
    # Mage Revised: "A botch on a re-roll does cancel a success as always"
    r = resolve_classic([10, 4, 3], 6, specialty_rerolls=[7, 1], reroll_ones_cancel=True)
    assert r.reroll_ones == 1
    assert r.net_successes == 1  # 1 raw + 1 reroll - 1 rerolled 1
    assert r.botch is False  # a reroll needs a 10, so never a botch
    r = resolve_classic([10, 2], 6, specialty_rerolls=[1], reroll_ones_cancel=True)
    assert r.net_successes == 0 and r.botch is False


def test_reroll_ones_rule_by_game_line():
    from services.rules_edition import reroll_ones_cancel

    assert reroll_ones_cancel("mage") is True
    assert reroll_ones_cancel("Mage: The Ascension") is True
    for gs in ("vampire", "werewolf", "custom", "", None):
        assert reroll_ones_cancel(gs) is False


def test_roll_classic_and_dice_service_pass_the_reroll_rule():
    from services.dice_service import DiceService

    r = roll_classic(2, 6, specialty=True, rng=FixedRng([10, 3, 1]), reroll_ones_cancel=True)
    assert r.specialty_rerolls == [1] and r.net_successes == 0
    r = roll_classic(2, 6, specialty=True, rng=FixedRng([10, 3, 1]))
    assert r.net_successes == 1
    d = DiceService.roll_d10_pool(2, 6, True, rng=FixedRng([10, 3, 1]), reroll_ones_cancel=True)
    assert d["successes"] == 0 and d["reroll_ones_cancel"] is True
    md = format_storyteller_roll_markdown(
        resolve_classic([10, 3], 6, specialty_rerolls=[1], reroll_ones_cancel=True), "mage")
    assert "1 × 1 cancel" in md


def test_mage_storyteller_brief_states_the_reroll_rule():
    from services.rules_edition import storyteller_rules_brief

    assert "a 1 on a reroll cancels a success" in storyteller_rules_brief("classic", "mage")
    assert "rerolls only add" in storyteller_rules_brief("classic", "werewolf")
