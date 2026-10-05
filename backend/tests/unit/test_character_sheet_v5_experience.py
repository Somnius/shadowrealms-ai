from services.character_sheet_v5 import sanity_check_v5


def _xp(**kw):
    xp = {
        "total": 15,
        "spent": 13,
        "unspent": 2,
        "log": [
            {"kind": "attribute", "trait": "resolve", "what": "Resolve", "from": 1, "to": 2, "cost": 10},
            {"kind": "specialty", "trait": "Stocks", "skill": "finance", "what": "Finance specialty: Stocks",
             "from": 0, "to": 1, "cost": 3},
        ],
    }
    xp.update(kw)
    return {"experience": xp}


def test_experience_is_optional_and_accepts_the_forge_shape():
    assert sanity_check_v5(wod_meta={}) == []
    assert sanity_check_v5(wod_meta=_xp()) == []
    assert sanity_check_v5(wod_meta=_xp(total=35, spent=0, unspent=35, log=[])) == []
    ritual = {"kind": "ritual", "trait": "Blood Walk", "what": "Ritual: Blood Walk", "from": 0, "to": 2, "cost": 6}
    assert sanity_check_v5(wod_meta=_xp(spent=6, unspent=9, log=[ritual])) == []


def test_experience_totals_are_consistent():
    assert sanity_check_v5(wod_meta={"experience": "15"})
    assert sanity_check_v5(wod_meta=_xp(spent=16, unspent=0))  # spent > total
    assert sanity_check_v5(wod_meta=_xp(unspent=5))  # unspent != total - spent
    assert sanity_check_v5(wod_meta=_xp(total=None))
    assert sanity_check_v5(wod_meta=_xp(total=-1, spent=0, unspent=0, log=[]))
    assert sanity_check_v5(wod_meta=_xp(spent=12, unspent=3))  # log costs 13, spent 12
    assert sanity_check_v5(wod_meta=_xp(spent=14, unspent=1))  # log costs 13, spent 14
    # XP is also awarded in play, so total isn't tied to the age grant
    assert sanity_check_v5(wod_meta=_xp(total=60, unspent=47)) == []
    assert sanity_check_v5(wod_meta=_xp(total=10001, unspent=9988))


def test_experience_log_entries_are_bounded():
    bad = [
        {"kind": "attribute", "trait": "strength", "what": "Strength", "from": 5, "to": 6, "cost": 30},  # above 5
        {"kind": "attribute", "trait": "strength", "what": "Strength", "from": 3, "to": 3, "cost": 0},  # to <= from
        {"kind": "humanity", "trait": "humanity", "what": "Humanity", "from": 7, "to": 8, "cost": 0},  # unknown kind
        {"trait": "brawl", "what": "Brawl", "from": 0, "to": 1, "cost": 3},  # no kind
        {"kind": "skill", "trait": "brawl", "what": "", "from": 0, "to": 1, "cost": 3},  # no what
        {"kind": "skill", "what": "Brawl", "from": 0, "to": 1, "cost": 3},  # no trait
        {"kind": "skill", "trait": "x" * 121, "what": "Brawl", "from": 0, "to": 1, "cost": 3},  # trait too long
        {"kind": "skill", "trait": "brawl", "what": "Brawl", "from": 0, "to": 1},  # no cost
        {"kind": "skill", "trait": "brawl", "what": "Brawl", "to": 1, "cost": 3},  # no from
        {"kind": "specialty", "trait": "Stocks", "what": "Stocks", "from": 0, "to": 1, "cost": 3},  # no skill
        {"kind": "specialty", "trait": "Stocks", "skill": "banking", "what": "Stocks", "from": 0, "to": 1, "cost": 3},
        {"kind": "skill", "trait": "academics", "specialty": "", "what": "Academics", "from": 0, "to": 1, "cost": 3},
    ]
    for entry in bad:
        cost = entry.get("cost") if isinstance(entry.get("cost"), int) else 0
        assert sanity_check_v5(wod_meta=_xp(total=100, spent=cost, unspent=100 - cost, log=[entry])), entry
    free = {"kind": "skill", "trait": "academics", "specialty": "History", "what": "Academics",
            "from": 0, "to": 1, "cost": 3}
    assert sanity_check_v5(wod_meta=_xp(spent=3, unspent=12, log=[free])) == []
    assert sanity_check_v5(wod_meta=_xp(log="Resolve"))
    assert sanity_check_v5(wod_meta=_xp(
        spent=0, unspent=15, log=[{"kind": "skill", "trait": "x", "what": "x", "from": 0, "to": 1, "cost": 0}] * 201))
