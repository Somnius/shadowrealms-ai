import random

import pytest

from services.v5_dice import (
    apply_reroll,
    clamp_hunger,
    format_v5_roll_markdown,
    outcome_label,
    parse_v5_roll_expression,
    resolve_rouse,
    resolve_v5,
    roll_v5,
    rouse_check,
    validate_reroll_indices,
    willpower_reroll,
)


class FixedRng:
    def __init__(self, values):
        self.values = list(values)

    def randint(self, lo, hi):
        v = self.values.pop(0)
        assert lo <= v <= hi
        return v

    def shuffle(self, seq):
        pass


def test_basic_successes():
    r = resolve_v5([6, 7, 2, 5], [], 2)
    assert r["successes"] == 2
    assert r["outcome"] == "win"
    assert r["margin"] == 0
    assert not r["is_critical"]
    assert r["is_botch"] is False


def test_ones_do_not_cancel():
    r = resolve_v5([6, 1, 1], [], 1)
    assert r["successes"] == 1
    assert r["outcome"] == "win"


def test_pair_of_tens_is_four_successes_and_critical():
    r = resolve_v5([10, 10, 3], [], 3)
    assert r["successes"] == 4
    assert r["critical_pairs"] == 1
    assert r["is_critical"] and not r["is_messy_critical"]
    assert outcome_label(r) == "Critical win"


def test_three_tens_is_five_successes():
    r = resolve_v5([10, 10, 10], [], 1)
    assert r["successes"] == 5
    assert r["critical_pairs"] == 1


def test_four_tens_two_pairs():
    r = resolve_v5([10, 10, 10, 10], [], 1)
    assert r["successes"] == 8
    assert r["critical_pairs"] == 2


def test_messy_critical_when_hunger_ten_in_pair():
    r = resolve_v5([10, 4], [10, 2], 2)
    assert r["successes"] == 4
    assert r["is_critical"] and r["is_messy_critical"]
    assert outcome_label(r) == "Messy critical"


def test_critical_requires_win():
    r = resolve_v5([10, 10], [], 5)
    assert r["successes"] == 4
    assert r["outcome"] == "fail"
    assert not r["is_critical"]


def test_bestial_failure():
    r = resolve_v5([6, 3], [1], 3)
    assert r["outcome"] == "fail"
    assert r["is_bestial_failure"]
    assert outcome_label(r) == "Bestial failure"


def test_hunger_one_on_win_is_not_bestial():
    r = resolve_v5([6, 7], [1], 2)
    assert r["outcome"] == "win"
    assert not r["is_bestial_failure"]


def test_total_failure():
    r = resolve_v5([2, 3], [4], 1)
    assert r["successes"] == 0
    assert r["is_total_failure"]
    assert outcome_label(r) == "Total failure"


def test_difficulty_zero_still_fails_on_zero_successes():
    assert resolve_v5([2], [], 0)["outcome"] == "fail"
    assert resolve_v5([6], [], 0)["outcome"] == "win"


def test_roll_v5_splits_hunger_dice():
    rng = FixedRng([6, 7, 8, 10, 1])
    r = roll_v5(5, hunger=2, difficulty=2, rng=rng)
    assert r["normal_dice"] == [6, 7, 8]
    assert r["hunger_dice"] == [10, 1]
    assert r["hunger"] == 2
    assert r["successes"] == 4


def test_hunger_capped_by_pool():
    r = roll_v5(2, hunger=5, difficulty=1, rng=random.Random(1))
    assert len(r["hunger_dice"]) == 2
    assert r["normal_dice"] == []


def test_roll_v5_validation():
    with pytest.raises(ValueError):
        roll_v5(0)
    with pytest.raises(ValueError):
        roll_v5(51)
    with pytest.raises(ValueError):
        roll_v5(3, difficulty=11)


def test_seeded_rolls_obey_rules():
    rng = random.Random(99)
    for _ in range(2000):
        pool = rng.randint(1, 12)
        hunger = rng.randint(0, 5)
        diff = rng.randint(0, 6)
        r = roll_v5(pool, hunger, diff, rng=rng)
        assert len(r["normal_dice"]) + len(r["hunger_dice"]) == pool
        assert len(r["hunger_dice"]) == min(hunger, pool)
        tens = sum(1 for d in r["results"] if d == 10)
        base = sum(1 for d in r["results"] if d >= 6)
        assert r["successes"] == base + 2 * (tens // 2)
        if r["is_messy_critical"]:
            assert r["is_critical"] and 10 in r["hunger_dice"]
        if r["is_bestial_failure"]:
            assert r["outcome"] == "fail" and 1 in r["hunger_dice"]


def test_leniency_no_ones():
    rng = random.Random(5)
    for _ in range(300):
        r = roll_v5(4, 2, 1, leniency_floor=7, rng=rng)
        assert 1 not in r["results"]
        assert max(r["results"]) >= 7
        assert not r["is_bestial_failure"]


def test_willpower_reroll_only_normal_dice():
    r = willpower_reroll([2, 3, 9], [1], 2, [0, 1], rng=FixedRng([6, 10]))
    assert r["normal_dice"] == [6, 10, 9]
    assert r["hunger_dice"] == [1]
    assert r["successes"] == 3
    assert r["rerolled"] and r["rerolled_indices"] == [0, 1]
    assert r["rerolled_from"] == [2, 3]


def test_reroll_validation():
    with pytest.raises(ValueError):
        validate_reroll_indices([1, 2, 3, 4], [0, 1, 2, 3])  # more than 3
    with pytest.raises(ValueError):
        validate_reroll_indices([1, 2], [2])  # out of range (hunger dice not addressable)
    with pytest.raises(ValueError):
        validate_reroll_indices([1, 2], [0, 0])
    with pytest.raises(ValueError):
        validate_reroll_indices([1, 2], [])
    with pytest.raises(ValueError):
        apply_reroll([1, 2], [], 1, [0], [5, 6])


def test_rouse():
    assert resolve_rouse(6, 2) == {
        "die": 6, "success": True, "hunger_before": 2, "hunger_after": 2, "at_max_hunger": False,
    }
    r = resolve_rouse(5, 2)
    assert not r["success"] and r["hunger_after"] == 3
    r = resolve_rouse(1, 5)
    assert r["hunger_after"] == 5 and r["at_max_hunger"]
    assert rouse_check(0, rng=FixedRng([3]))["hunger_after"] == 1


def test_clamp_hunger():
    assert clamp_hunger(None) == 0
    assert clamp_hunger("3") == 3
    assert clamp_hunger(9) == 5
    assert clamp_hunger(-1) == 0


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("6", (6, 1, 0)),
        ("6@3", (6, 3, 0)),
        ("6h2", (6, 1, 2)),
        ("6@3h2", (6, 3, 2)),
        ("6 @ 3 h2", (6, 3, 2)),
        ("4+2@2h1", (6, 2, 1)),
        ("6h2@3", (6, 3, 2)),
        ("6@0", (6, 0, 0)),
    ],
)
def test_parse_v5_expression(expr, expected):
    assert parse_v5_roll_expression(expr) == expected


@pytest.mark.parametrize("expr", ["", "x", "6@11", "6h6", "6@3h2x", "0"])
def test_parse_v5_expression_errors(expr):
    with pytest.raises(ValueError):
        parse_v5_roll_expression(expr)


def test_markdown_mentions_outcome():
    r = resolve_v5([10, 4], [10], 2)
    r["leniency_floor"] = None
    md = format_v5_roll_markdown(r, "vampire")
    assert "Messy critical" in md
    assert "Hunger dice" in md


def test_three_tens_one_hunger_is_messy():
    # V5.md §1.4: two normal 10s plus a Hunger 10 — a 10 on a Hunger die makes it messy.
    r = resolve_v5([10, 10], [10], 1)
    assert r["successes"] == 5 and r["critical_pairs"] == 1
    assert r["is_critical"] and r["is_messy_critical"]
    assert outcome_label(r) == "Messy critical"
    # same dice failing a high difficulty: not a critical, not messy
    r = resolve_v5([10, 10], [10], 6)
    assert r["outcome"] == "fail" and not r["is_critical"] and not r["is_messy_critical"]


# --- Willpower spend (reroll cost) ----------------------------------------------------------

from services.v5_dice import NoWillpowerLeft, spend_willpower, willpower_track  # noqa: E402


def test_spend_marks_one_superficial():
    out = spend_willpower({"max": 5, "superficial": 1, "aggravated": 1})
    assert out["before"] == {"max": 5, "superficial": 1, "aggravated": 1}
    assert out["after"] == {"max": 5, "superficial": 2, "aggravated": 1}
    assert out["damage"] == "superficial"


def test_spend_on_full_track_turns_a_superficial_box_aggravated():
    out = spend_willpower({"max": 4, "superficial": 3, "aggravated": 1})
    assert out["after"] == {"max": 4, "superficial": 2, "aggravated": 2}
    assert out["damage"] == "aggravated"
    out = spend_willpower({"max": 4, "superficial": 4, "aggravated": 0})
    assert out["after"] == {"max": 4, "superficial": 3, "aggravated": 1}


def test_spend_on_all_aggravated_track_is_refused():
    with pytest.raises(NoWillpowerLeft):
        spend_willpower({"max": 3, "superficial": 0, "aggravated": 3})


def test_spend_does_not_mutate_input():
    track = {"max": 5, "superficial": 0, "aggravated": 0}
    spend_willpower(track)
    assert track == {"max": 5, "superficial": 0, "aggravated": 0}


def test_willpower_track_from_sheet_or_attributes():
    assert willpower_track({"willpower": {"max": 6, "superficial": 2, "aggravated": 1}}) == {
        "max": 6, "superficial": 2, "aggravated": 1}
    # missing damage counts as 0; strings and floats from older sheets are accepted
    assert willpower_track({"willpower": {"max": "5", "superficial": 1.0}}) == {
        "max": 5, "superficial": 1, "aggravated": 0}
    # out-of-range damage is clamped so superficial + aggravated <= max
    assert willpower_track({"willpower": {"max": 3, "superficial": 9, "aggravated": 2}}) == {
        "max": 3, "superficial": 1, "aggravated": 2}
    # no track: Composure + Resolve, undamaged
    assert willpower_track({}, {"composure": 2, "resolve": 3}) == {
        "max": 5, "superficial": 0, "aggravated": 0}
    assert willpower_track({"willpower": {"max": 0}}, {"composure": 1, "resolve": 1})["max"] == 2
    assert willpower_track({}, {}) is None
    assert willpower_track(None, None) is None
    assert willpower_track({"willpower": {"max": True}}, {"composure": True, "resolve": 2}) is None


def test_reroll_chat_line_shows_the_willpower_cost():
    from services.dice_service import DiceService

    base = {"normal_dice": [6, 2], "hunger_dice": [], "difficulty": 1, "successes": 1,
            "margin": 0, "outcome": "win", "rerolled": True, "rerolled_indices": [1]}
    assert "Willpower −1" in DiceService.format_v5_roll_for_chat({**base, "willpower_cost": "superficial"})
    line = DiceService.format_v5_roll_for_chat({**base, "willpower_cost": "aggravated"})
    assert "turned Aggravated" in line
    assert "Willpower −1" not in DiceService.format_v5_roll_for_chat(base)
