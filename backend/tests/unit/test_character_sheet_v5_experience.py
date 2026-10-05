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
    assert sanity_check_v5(wod_meta=_xp(spent=12, unspent=3))  # log costs 13 > 12 spent


def test_experience_log_entries_are_bounded():
    bad = [
        {"kind": "attribute", "what": "Strength", "from": 5, "to": 6, "cost": 30},  # level above 5
        {"kind": "attribute", "what": "Strength", "from": 3, "to": 3, "cost": 0},  # to not above from
        {"kind": "humanity", "what": "Humanity", "from": 7, "to": 8, "cost": 0},  # unknown kind
        {"kind": "skill", "what": "", "from": 0, "to": 1, "cost": 3},  # no what
        {"kind": "skill", "what": "Brawl", "from": 0, "to": 1},  # no cost
        {"kind": "skill", "what": "Brawl", "to": 1, "cost": 3},  # no from
    ]
    for entry in bad:
        assert sanity_check_v5(wod_meta=_xp(spent=13, unspent=2, log=[entry])), entry
    assert sanity_check_v5(wod_meta=_xp(log="Resolve"))
    assert sanity_check_v5(wod_meta=_xp(log=[{"kind": "skill", "what": "x", "from": 0, "to": 1, "cost": 0}] * 201))
