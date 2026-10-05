from services.character_sheet_v5 import sanity_check_v5


def test_rituals_are_optional_and_bounded():
    assert sanity_check_v5(wod_meta={"rituals": [{"name": "Blood Walk", "level": 1}]}) == []
    assert sanity_check_v5(wod_meta={}) == []
    assert sanity_check_v5(wod_meta={"rituals": "Blood Walk"})
    assert sanity_check_v5(wod_meta={"rituals": [{"name": "", "level": 1}]})
    assert sanity_check_v5(wod_meta={"rituals": [{"name": "x" * 121, "level": 1}]})
    assert sanity_check_v5(wod_meta={"rituals": [{"name": "Blood Walk", "level": 6}]})
    assert sanity_check_v5(wod_meta={"rituals": [{"name": f"R{i}", "level": 1} for i in range(11)]})
