import random

import pytest

from services.wod_dice import (
    StorytellerRollResult,
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


def test_exceptional_at_five():
    r = resolve_classic([6, 6, 7, 8, 9], 6)
    assert r.net_successes == 5 and r.exceptional
    assert classic_outcome_label(r) == "Exceptional success"
    r4 = resolve_classic([6, 6, 7, 8], 6)
    assert not r4.exceptional


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


def test_formatter_uses_exceptional_not_critical():
    r = resolve_classic([6, 6, 7, 8, 9], 6)
    md = format_storyteller_roll_markdown(r, "vampire")
    assert "Exceptional success" in md
    assert "CRITICAL" not in md.upper().replace("EXCEPTIONAL", "")


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
