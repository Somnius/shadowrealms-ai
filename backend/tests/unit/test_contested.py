"""DiceService contested rolls: V5 ties go to the acting character; flags follow the contest."""

import random

from services.dice_service import DiceService
from services.v5_dice import outcome_label, resolve_v5


def _v5(normal, hunger):
    return resolve_v5(normal, hunger, 0)


def test_v5_tie_goes_to_attacker():
    c = DiceService.resolve_contested_v5(_v5([6, 2], []), _v5([7, 3], []))
    assert c["winner"] == "attacker" and c["margin"] == 0
    assert c["attacker_roll"]["outcome"] == "win" and c["attacker_roll"]["contest_won"]
    assert c["defender_roll"]["outcome"] == "fail" and not c["defender_roll"]["contest_won"]


def test_v5_zero_vs_zero_goes_to_attacker():
    c = DiceService.resolve_contested_v5(_v5([2], []), _v5([3], []))
    assert c["winner"] == "attacker" and c["margin"] == 0


def test_v5_loser_with_hunger_one_is_bestial_even_with_successes():
    # attacker 2 successes incl. a Hunger 1, defender 3 successes
    c = DiceService.resolve_contested_v5(_v5([6, 7], [1]), _v5([6, 7, 8], []))
    a = c["attacker_roll"]
    assert c["winner"] == "defender" and c["margin"] == 1
    assert a["outcome"] == "fail" and a["is_bestial_failure"]
    assert outcome_label(a) == "Bestial failure"
    assert "Attacker: bestial failure" in c["message"]


def test_v5_loser_with_pair_of_tens_is_not_critical():
    # attacker: pair of 10s (one Hunger) = 4 successes; defender 5 successes
    c = DiceService.resolve_contested_v5(_v5([10], [10]), _v5([6, 7, 8, 9, 6], []))
    a = c["attacker_roll"]
    assert c["winner"] == "defender"
    assert not a["is_critical"] and not a["is_messy_critical"]
    assert a["outcome"] == "fail" and outcome_label(a) == "Failure"


def test_v5_winner_flags_critical_and_messy():
    c = DiceService.resolve_contested_v5(_v5([10], [10]), _v5([6], []))
    a = c["attacker_roll"]
    assert c["winner"] == "attacker" and c["margin"] == 3
    assert a["is_critical"] and a["is_messy_critical"]
    assert outcome_label(a) == "Messy critical"
    # defender wins with a clean pair
    c = DiceService.resolve_contested_v5(_v5([6], []), _v5([10, 10], [1]))
    d = c["defender_roll"]
    assert c["winner"] == "defender"
    assert d["is_critical"] and not d["is_messy_critical"]
    # a winner is never bestial, whatever its Hunger dice show
    assert not d["is_bestial_failure"]


def test_v5_winner_hunger_one_not_bestial_but_loser_is():
    c = DiceService.resolve_contested_v5(_v5([6, 7], [1]), _v5([6], [1]))
    assert not c["attacker_roll"]["is_bestial_failure"]
    assert c["defender_roll"]["is_bestial_failure"]


def test_v5_roll_contested_never_reports_tie_and_flags_consistent():
    rng = random.Random(1234)
    for _ in range(3000):
        c = DiceService.roll_contested(3, 3, rules_edition="v5", attacker_hunger=2,
                                       defender_hunger=1, rng=rng)
        a, d = c["attacker_roll"], c["defender_roll"]
        assert c["winner"] in ("attacker", "defender")
        assert (c["winner"] == "attacker") == (a["successes"] >= d["successes"])
        for side, won in ((a, c["winner"] == "attacker"), (d, c["winner"] == "defender")):
            assert side["outcome"] == ("win" if won else "fail")
            if not won:
                assert not side["is_critical"] and not side["is_messy_critical"]
                assert side["is_bestial_failure"] == (1 in side["hunger_dice"])
            else:
                assert not side["is_bestial_failure"]
                assert side["is_critical"] == (side["critical_pairs"] >= 1)


def test_classic_contested_ties_and_botch():
    rng = random.Random(7)
    seen = set()
    for _ in range(3000):
        c = DiceService.roll_contested(3, 3, 6, rng=rng)
        a, d = c["attacker_roll"], c["defender_roll"]
        seen.add(c["winner"])
        assert c["rules_edition"] == "classic"
        if a["is_botch"]:
            assert c["winner"] == "defender"
        elif d["is_botch"]:
            assert c["winner"] == "attacker"
        elif a["successes"] == d["successes"]:
            assert c["winner"] == "tie"
        else:
            assert c["winner"] == ("attacker" if a["successes"] > d["successes"] else "defender")
    assert seen == {"attacker", "defender", "tie"}
