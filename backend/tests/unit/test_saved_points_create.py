"""Creating a V5 character: wod_meta.saved is checked (adv_over) and then counted by the server,
never taken from the client alone (Forge v2 part D). Sheets come from the shared vectors."""

from test_creation_validation_routes import DOC, api, body  # noqa: F401  (fixture + helpers)

SAVER = "valid: 2 Advantage dots and the free specialty saved for later"
FULL = "valid: Brujah with no XP spent"


def _saved(api, r):
    assert r.status_code == 201, r.get_json()
    return api.meta(r.get_json()["character_id"])["saved"]


def test_the_vectors_carry_the_forges_saved_points():
    case = next(c for c in DOC["cases"] if c["name"] == SAVER)
    assert case["payload"]["wod_meta"]["saved"] == {"advantage_dots": 2, "specialty": 1}
    assert case["expect"] == []


def test_an_honest_balance_is_kept(api):
    assert _saved(api, api.call("POST", "/api/characters/", 3, body(SAVER))) == {"advantage_dots": 2, "specialty": 1}


def test_a_forged_balance_is_refused(api):
    b = body(FULL)  # spends all 7 dots and its free specialty
    b["wod_meta"]["saved"] = {"advantage_dots": 3, "specialty": 0}
    r = api.call("POST", "/api/characters/", 3, b)
    assert r.status_code == 400 and r.get_json()["error_code"] == "creation_invalid"
    assert r.get_json()["problems"] == [{"code": "adv_over", "params": {"max": 7, "have": 10}}]
    assert api.sql("SELECT COUNT(*) FROM characters") == [(0,)]


def test_an_override_never_keeps_a_forged_balance(api):
    b = body(FULL, creation_override={"reason": "imported sheet"})
    b["wod_meta"]["saved"] = {"advantage_dots": 3, "specialty": 1}
    assert _saved(api, api.call("POST", "/api/characters/", 2, b)) == {"advantage_dots": 0, "specialty": 0}


def test_no_balance_sent_gets_the_servers_count_and_a_lower_one_is_kept(api):
    b = body(SAVER)
    del b["wod_meta"]["saved"]
    assert _saved(api, api.call("POST", "/api/characters/", 3, b)) == {"advantage_dots": 2, "specialty": 1}
    b = body(SAVER, name="Modest")
    b["wod_meta"]["saved"] = {"advantage_dots": 1, "specialty": 0}
    assert _saved(api, api.call("POST", "/api/characters/", 3, b)) == {"advantage_dots": 1, "specialty": 0}


def test_the_chronicles_cap_and_specialty_switch(api):
    api.sql("""UPDATE campaigns SET creation_settings = '{"saved_points": {"advantage_dots_cap": 1, "allow_specialty": false}}' WHERE id = 10""")
    assert _saved(api, api.call("POST", "/api/characters/", 3, body(SAVER))) == {"advantage_dots": 1, "specialty": 0}


def test_the_bounds_check_still_comes_first(api):
    b = body(SAVER)
    b["wod_meta"]["saved"] = {"advantage_dots": 99}
    r = api.call("POST", "/api/characters/", 3, b)
    assert r.status_code == 400 and "wod_meta.saved.advantage_dots" in r.get_json()["error"]
