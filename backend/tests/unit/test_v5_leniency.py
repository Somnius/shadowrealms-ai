"""V5 room leniency switches (no_bestial / no_messy / min_successes) and the per-edition
`/ai dice-diff` command and admin dice-leniency route."""

import json
import random
import sys
import types

import pytest

from services.request_validation import RequestValidationError
from services.v5_dice import (
    describe_v5_leniency,
    format_v5_roll_markdown,
    normalize_v5_leniency,
    roll_v5,
    validate_v5_leniency,
    willpower_reroll,
)

SEEDS = range(400)


def lenient(no_bestial=False, no_messy=False, min_successes=0):
    return {"no_bestial": no_bestial, "no_messy": no_messy, "min_successes": min_successes}


class FixedRng:
    """randint pops the next value (checked against the range); shuffle reverses."""

    def __init__(self, values):
        self.values = list(values)

    def randint(self, lo, hi):
        v = self.values.pop(0)
        assert lo <= v <= hi, (v, lo, hi)
        return v

    def shuffle(self, seq):
        seq.reverse()


# --- dice -----------------------------------------------------------------------------------

def test_no_switches_is_exactly_plain_d10s():
    for seed in range(50):
        plain = random.Random(seed)
        expected = [plain.randint(1, 10) for _ in range(7)]
        r = roll_v5(7, 3, 2, rng=random.Random(seed))
        assert r["normal_dice"] + r["hunger_dice"] == expected
        assert r["v5_leniency"] is None
        r = roll_v5(7, 3, 2, v5_leniency=lenient(), rng=random.Random(seed))
        assert r["normal_dice"] + r["hunger_dice"] == expected and r["v5_leniency"] is None


def test_no_bestial_hunger_dice_never_show_1():
    normal_faces = set()
    hunger_faces = set()
    for seed in SEEDS:
        r = roll_v5(5, 4, 4, v5_leniency=lenient(no_bestial=True), rng=random.Random(seed))
        assert 1 not in r["hunger_dice"]
        assert not r["is_bestial_failure"]
        normal_faces.update(r["normal_dice"])
        hunger_faces.update(r["hunger_dice"])
    assert hunger_faces == set(range(2, 11))
    assert normal_faces == set(range(1, 11))  # normal dice keep their 1s


def test_no_messy_hunger_dice_never_show_10():
    hunger_faces = set()
    normal_faces = set()
    for seed in SEEDS:
        r = roll_v5(6, 3, 1, v5_leniency=lenient(no_messy=True), rng=random.Random(seed))
        assert 10 not in r["hunger_dice"]
        assert not r["is_messy_critical"]
        hunger_faces.update(r["hunger_dice"])
        normal_faces.update(r["normal_dice"])
    assert hunger_faces == set(range(1, 10))
    assert 10 in normal_faces  # normal 10s (and plain criticals) still happen


def test_both_hunger_switches():
    for seed in SEEDS:
        r = roll_v5(3, 3, 2, v5_leniency=lenient(True, True), rng=random.Random(seed))
        assert all(2 <= d <= 9 for d in r["hunger_dice"])


@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("pool,hunger", [(1, 0), (1, 1), (2, 2), (3, 1), (5, 2), (8, 5)])
def test_min_successes(n, pool, hunger):
    seen = set()
    for seed in SEEDS:
        r = roll_v5(pool, hunger, 1, v5_leniency=lenient(min_successes=n), rng=random.Random(seed))
        dice = r["normal_dice"] + r["hunger_dice"]
        assert sum(1 for d in dice if d >= 6) >= min(n, pool)
        assert len(r["hunger_dice"]) == min(hunger, pool)
        seen.add(tuple(dice))
    assert len(seen) >= (5 if pool == 1 else 20)  # still random, not a fixed pool


def test_min_successes_with_no_messy_keeps_hunger_below_10():
    for seed in SEEDS:
        r = roll_v5(3, 3, 1, v5_leniency=lenient(no_messy=True, min_successes=3), rng=random.Random(seed))
        assert all(6 <= d <= 9 for d in r["hunger_dice"])


def test_min_successes_redraws_only_the_shortfall_normal_dice_first():
    # normal [2, 3, 7], hunger [4]: 1 success, 2 short. Failing normal dice are idx 0, 1
    # (shuffle reverses -> 1, 0); both re-drawn (8, 6). The Hunger die is left alone.
    r = roll_v5(4, 1, 1, v5_leniency=lenient(min_successes=3), rng=FixedRng([2, 3, 7, 4, 8, 6]))
    assert r["normal_dice"] == [6, 8, 7]
    assert r["hunger_dice"] == [4]


def test_min_successes_uses_hunger_dice_only_when_normal_dice_run_out():
    # normal [7, 2], hunger [1, 3]: 1 success, 2 short -> normal idx1 (9), then one Hunger
    # die (shuffle reverses [0, 1] -> idx 1 first) re-drawn 6. Hunger idx 0 keeps its 1.
    r = roll_v5(4, 2, 5, v5_leniency=lenient(min_successes=3), rng=FixedRng([7, 2, 1, 3, 9, 6]))
    assert r["normal_dice"] == [7, 9]
    assert r["hunger_dice"] == [1, 6]
    assert r["is_bestial_failure"]  # min_successes alone doesn't remove bestial failures


def test_min_successes_already_met_rolls_nothing_extra():
    rng = FixedRng([6, 7, 9])
    r = roll_v5(3, 1, 1, v5_leniency=lenient(min_successes=3), rng=rng)
    assert r["results"] == [6, 7, 9] and rng.values == []


def test_reroll_is_plain_d10s():
    r = willpower_reroll([2, 3], [1], 2, [0, 1], rng=FixedRng([1, 10]))
    assert r["normal_dice"] == [1, 10]


# --- settings -------------------------------------------------------------------------------

def test_normalize():
    assert normalize_v5_leniency(None) is None
    assert normalize_v5_leniency("not json") is None
    assert normalize_v5_leniency(lenient()) is None
    assert normalize_v5_leniency('{"no_messy": true}') == lenient(no_messy=True)
    assert normalize_v5_leniency({"min_successes": 9, "no_bestial": "yes"}) == lenient(min_successes=3)


@pytest.mark.parametrize(
    "bad",
    [
        [],
        "on",
        {"no_bestial": 1},
        {"no_messy": "true"},
        {"min_successes": 4},
        {"min_successes": -1},
        {"min_successes": True},
        {"min_successes": 1.0},
        {"floor": 7},
    ],
)
def test_validate_refuses(bad):
    with pytest.raises(RequestValidationError):
        validate_v5_leniency(bad)


def test_validate_accepts():
    assert validate_v5_leniency(None) is None
    assert validate_v5_leniency({}) is None
    assert validate_v5_leniency({"no_bestial": True, "min_successes": 2}) == lenient(True, False, 2)


def test_texts_name_the_active_switches():
    assert describe_v5_leniency(None) == ""
    d = describe_v5_leniency(lenient(True, True, 1))
    assert "no bestial failure" in d and "no messy critical" in d and "at least 1 die shows 6+" in d
    r = roll_v5(3, 1, 1, v5_leniency=lenient(min_successes=2), rng=random.Random(1))
    md = format_v5_roll_markdown(r)
    assert "Room leniency (V5):** at least 2 dice show 6+" in md

    from services.dice_service import DiceService

    r["message"] = "x"
    assert "Room leniency (V5, this roll): at least 2 dice show 6+" in DiceService.format_v5_roll_for_chat(r)
    r["rerolled"] = True
    assert "first roll only" in DiceService.format_v5_roll_for_chat(r)


# --- fake database --------------------------------------------------------------------------

class FakeDB:
    def __init__(self, edition="v5", floor=None, v5=None, role="admin"):
        self.edition, self.role = edition, role
        self.loc = {"dice_leniency_floor": floor, "dice_leniency_v5": v5}

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class FakeCursor:
    def __init__(self, db):
        self.db, self.row = db, None

    def execute(self, sql, params=()):
        q = " ".join(sql.split())
        loc = self.db.loc
        if q.startswith("SELECT role FROM users"):
            self.row = {"role": self.db.role}
        elif q.startswith("SELECT game_system, rules_edition FROM campaigns"):
            self.row = {"game_system": "vampire", "rules_edition": self.db.edition}
        elif "c.rules_edition" in q:
            self.row = {**loc, "rules_edition": self.db.edition}
        elif q.startswith("SELECT dice_leniency"):
            self.row = dict(loc)
        elif q.startswith("UPDATE locations SET dice_leniency_floor = NULL, dice_leniency_v5 = NULL"):
            loc.update(dice_leniency_floor=None, dice_leniency_v5=None)
        elif q.startswith("UPDATE locations SET dice_leniency_v5 = %s"):
            loc["dice_leniency_v5"] = params[0]
        elif q.startswith("UPDATE locations SET dice_leniency_floor = %s"):
            loc["dice_leniency_floor"] = params[0]
        else:
            self.row = None

    def fetchone(self):
        return self.row

    def fetchall(self):
        return []

    def close(self):
        pass


@pytest.fixture
def stub_psycopg(monkeypatch):
    if "psycopg2" not in sys.modules:
        pg = types.ModuleType("psycopg2")
        pg.extras = types.ModuleType("psycopg2.extras")
        monkeypatch.setitem(sys.modules, "psycopg2", pg)
        monkeypatch.setitem(sys.modules, "psycopg2.extras", pg.extras)


@pytest.fixture
def dice_diff(stub_psycopg, monkeypatch):
    import database
    from services import ai_slash_commands as sc

    def run(payload, db):
        monkeypatch.setattr(database, "get_db", lambda: db)
        return sc.execute_dice_diff_command(payload, 1, 3, 4)

    return run


# --- /ai dice-diff --------------------------------------------------------------------------

def test_v5_switches_set_and_confirm(dice_diff):
    db = FakeDB("v5")
    r = dice_diff("no-bestial on", db)
    assert json.loads(db.loc["dice_leniency_v5"]) == lenient(no_bestial=True)
    assert r["dice_leniency_v5"] == lenient(no_bestial=True)
    assert "bestial failure" in r["display_markdown"] and "(V5)" in r["display_markdown"]
    dice_diff("no-messy on", db)
    r = dice_diff("successes 2", db)
    assert json.loads(db.loc["dice_leniency_v5"]) == lenient(True, True, 2)
    assert "at least 2 dice show 6+" in r["display_markdown"]
    dice_diff("no-bestial off", db)
    dice_diff("no-messy off", db)
    r = dice_diff("successes 0", db)
    assert db.loc["dice_leniency_v5"] is None and r["dice_leniency_v5"] is None


def test_v5_show_and_restore(dice_diff):
    db = FakeDB("v5", floor=7, v5=json.dumps(lenient(no_messy=True)))
    r = dice_diff("", db)
    assert "no messy critical" in r["display_markdown"] and "Classic floor" in r["display_markdown"]
    r = dice_diff("restore", db)
    assert db.loc == {"dice_leniency_floor": None, "dice_leniency_v5": None}
    assert "All V5 switches are cleared" in r["display_markdown"]


@pytest.mark.parametrize("payload", ["7", "2", "no-bestial", "no-bestial yes", "successes 4", "successes x",
                                     "successes", "foo", "no-messy on off"])
def test_v5_refusals(dice_diff, payload):
    db = FakeDB("v5")
    with pytest.raises(RequestValidationError) as ei:
        dice_diff(payload, db)
    assert db.loc["dice_leniency_v5"] is None
    if payload in ("7", "2", "foo"):
        assert "no-bestial on|off" in ei.value.public_message


def test_classic_floor_unchanged(dice_diff):
    db = FakeDB("classic")
    r = dice_diff("7", db)
    assert db.loc["dice_leniency_floor"] == 7 and r["dice_leniency_floor"] == 7
    assert "leniency floor **7** (Classic)" in r["display_markdown"]
    r = dice_diff("restore", db)
    assert db.loc["dice_leniency_floor"] is None and r["dice_leniency_floor"] is None


@pytest.mark.parametrize("payload", ["no-bestial on", "no-messy off", "successes 2"])
def test_classic_refuses_v5_switches(dice_diff, payload):
    db = FakeDB("classic")
    with pytest.raises(RequestValidationError) as ei:
        dice_diff(payload, db)
    assert "V5" in ei.value.public_message and "<2–10>" in ei.value.public_message
    assert db.loc == {"dice_leniency_floor": None, "dice_leniency_v5": None}


def test_help_is_edition_specific(monkeypatch):
    from services import ai_slash_commands as sc

    monkeypatch.setattr(sc, "_fetch_campaign_rules", lambda cid: ("vampire", "v5"))
    v5 = sc.execute_help_command(1, campaign_id=3)["display_markdown"]
    assert "no-bestial on|off" in v5 and "<2–10>" not in v5
    monkeypatch.setattr(sc, "_fetch_campaign_rules", lambda cid: ("", "classic"))
    classic = sc.execute_help_command(1, campaign_id=3)["display_markdown"]
    assert "<2–10>" in classic and "no-bestial" not in classic


# --- admin route ----------------------------------------------------------------------------

@pytest.fixture
def loc_client(stub_psycopg, monkeypatch):
    from flask import Flask
    from flask_jwt_extended import JWTManager, create_access_token

    from routes import locations

    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(locations.locations_bp, url_prefix="/api")
    with app.app_context():
        token = create_access_token(identity="7")
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    def use(db):
        monkeypatch.setattr(locations, "get_db", lambda: db)
        return client

    return use


URL = "/api/campaigns/3/locations/4/dice-leniency"


def test_route_v5_get_put(loc_client):
    db = FakeDB("v5")
    c = loc_client(db)
    assert c.get(URL).get_json() == {"rules_edition": "v5", "dice_leniency_floor": None, "dice_leniency_v5": None}
    r = c.put(URL, json={"dice_leniency_v5": {"no_bestial": True, "min_successes": 1}})
    assert r.status_code == 200
    assert r.get_json()["dice_leniency_v5"] == lenient(True, False, 1)
    assert json.loads(db.loc["dice_leniency_v5"]) == lenient(True, False, 1)
    assert c.get(URL).get_json()["dice_leniency_v5"] == lenient(True, False, 1)
    r = c.put(URL, json={"dice_leniency_v5": None})
    assert r.status_code == 200 and db.loc["dice_leniency_v5"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"dice_leniency_v5": {"min_successes": 5}},
        {"dice_leniency_v5": {"no_messy": "yes"}},
        {"dice_leniency_v5": {"extra": True}},
        {"dice_leniency_v5": [1]},
        {"dice_leniency_floor": 7},
        {},
        [1],
    ],
)
def test_route_v5_refuses(loc_client, body):
    db = FakeDB("v5")
    r = loc_client(db).put(URL, json=body)
    assert r.status_code == 400
    assert db.loc == {"dice_leniency_floor": None, "dice_leniency_v5": None}


def test_route_classic_keeps_floor_api(loc_client):
    db = FakeDB("classic")
    c = loc_client(db)
    r = c.put(URL, json={"dice_leniency_floor": 8})
    assert r.status_code == 200 and r.get_json()["dice_leniency_floor"] == 8 and db.loc["dice_leniency_floor"] == 8
    assert c.put(URL, json={"dice_leniency_floor": 11}).status_code == 400
    assert c.put(URL, json={"dice_leniency_v5": {"no_bestial": True}}).status_code == 400
    assert c.get(URL).get_json() == {"rules_edition": "classic", "dice_leniency_floor": 8}
    r = c.put(URL, json={"dice_leniency_floor": None})
    assert r.status_code == 200 and db.loc["dice_leniency_floor"] is None


def test_route_admin_only(loc_client):
    assert loc_client(FakeDB("v5", role="player")).get(URL).status_code == 403
