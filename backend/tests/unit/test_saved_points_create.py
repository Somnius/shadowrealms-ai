"""Creating a V5 character: wod_meta.saved is the server's count, not the client's (Forge v2 part D)."""

import json

from test_unassigned_characters import api  # noqa: F401  (the characters-route fixture)


def _create(api, name, saved=None, age="neonate", own_dots=5):
    meta = {
        "edition": "v5",
        "clan": "Brujah",
        "age": age,
        "advantages": [
            {"name": "Resources", "dots": own_dots, "kind": "background"},
            {"name": "Herd", "dots": 2, "kind": "predator"},
        ],
    }
    if saved is not None:
        meta["saved"] = saved
    body = {
        "name": name,
        "campaign_id": 10,
        "system_type": "vampire",
        "sheet_locked": False,
        "attributes": {},
        "skills": {"physical": {"brawl": 2}, "specialties": [{"skill": "brawl", "name": "Grappling"}]},
        "wod_meta": meta,
    }
    r = api.call("POST", "/api/characters/", 3, body)
    assert r.status_code == 201, r.get_json()
    (row,) = api.sql("SELECT wod_meta FROM characters WHERE id = ?", (r.get_json()["character_id"],))
    return json.loads(row[0])["saved"]


def test_a_forged_balance_is_replaced_by_the_servers_count(api):
    # 7 - 5 own dots = 2; the one free specialty is used
    assert _create(api, "Forged", {"advantage_dots": 20, "specialty": 1}) == {"advantage_dots": 2, "specialty": 0}


def test_no_balance_sent_gets_the_count_and_a_lower_one_is_kept(api):
    assert _create(api, "Old client") == {"advantage_dots": 2, "specialty": 0}
    assert _create(api, "Modest", {"advantage_dots": 1, "specialty": 0}) == {"advantage_dots": 1, "specialty": 0}


def test_the_chronicle_cap_and_the_ancilla_bonus(api):
    api.sql("ALTER TABLE campaigns ADD COLUMN creation_settings TEXT NOT NULL DEFAULT '{}'")
    assert _create(api, "Ancilla", {"advantage_dots": 4, "specialty": 0}, age="ancilla", own_dots=5) == {
        "advantage_dots": 4,
        "specialty": 0,
    }
    api.sql("""UPDATE campaigns SET creation_settings = '{"saved_points": {"advantage_dots_cap": 1}}' WHERE id = 10""")
    assert _create(api, "Capped", {"advantage_dots": 2, "specialty": 0}) == {"advantage_dots": 1, "specialty": 0}


def test_the_bounds_check_still_refuses_nonsense(api):
    body = {
        "name": "Nonsense", "campaign_id": 10, "system_type": "vampire", "sheet_locked": False,
        "wod_meta": {"edition": "v5", "saved": {"advantage_dots": 99}},
    }
    r = api.call("POST", "/api/characters/", 3, body)
    assert r.status_code == 400 and "wod_meta.saved.advantage_dots" in r.get_json()["error"]
