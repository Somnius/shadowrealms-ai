"""
RequestValidationError: only our own validation messages reach a 400 body; any other
exception (a stray ValueError included) gets a generic message.
"""

import sys
import types

import pytest

from services.request_validation import (
    RequestValidationError,
    body_object,
    chat_text,
    optional_str,
    strict_bool,
    strict_int,
)
from services.v5_dice import parse_v5_roll_expression, roll_v5, validate_reroll_indices
from services.wod_dice import parse_pool_expression, parse_roll_expression


def test_is_a_value_error_with_public_message():
    e = RequestValidationError("pool_size must be an integer")
    assert isinstance(e, ValueError)
    assert e.public_message == "pool_size must be an integer"
    assert str(e) == e.public_message


@pytest.mark.parametrize(
    "call",
    [
        lambda: body_object([1]),
        lambda: strict_int("abc", "n"),
        lambda: strict_int(9, "n", None, 0, 5),
        lambda: strict_bool("false", "flag"),
        lambda: optional_str(3, "s"),
        lambda: chat_text("  ", "Message"),
        lambda: parse_pool_expression(""),
        lambda: parse_pool_expression("4+x"),
        lambda: parse_pool_expression("99"),
        lambda: parse_roll_expression("5@x"),
        lambda: parse_roll_expression("5@11"),
        lambda: parse_v5_roll_expression("6@99"),
        lambda: parse_v5_roll_expression("nope"),
        lambda: roll_v5(0),
        lambda: validate_reroll_indices([1, 2, 3], []),
        lambda: validate_reroll_indices([1, 2, 3], [7]),
        lambda: validate_reroll_indices([1, 2, 3], [0, 0]),
    ],
)
def test_validators_raise_request_validation_error(call):
    with pytest.raises(RequestValidationError):
        call()


def test_huge_numbers_are_a_validation_error_not_a_python_error():
    # int() of a >4300-digit string raises Python's own ValueError; the parsers must
    # reject such input themselves so no library text reaches the client.
    huge = "9" * 5000
    for call in (
        lambda: parse_pool_expression(huge),
        lambda: parse_roll_expression(f"5@{huge}"),
        lambda: parse_roll_expression(f"5 tn {huge}"),
        lambda: parse_v5_roll_expression(f"5@{huge}"),
        lambda: parse_v5_roll_expression(f"5h{huge}"),
    ):
        with pytest.raises(RequestValidationError):
            call()


def test_messages_do_not_echo_odd_input():
    with pytest.raises(RequestValidationError) as ei:
        validate_reroll_indices([1, 2, 3], ["<b>x</b>"])
    assert "<b>" not in ei.value.public_message
    with pytest.raises(RequestValidationError) as ei:
        parse_roll_expression("5@<b>")
    assert "<b>" not in ei.value.public_message


def test_ui_language_raises_request_validation_error():
    from routes.ui_language import parse_ui_language

    with pytest.raises(RequestValidationError):
        parse_ui_language("fr")


# --- dice routes: 400 for our validation text, generic 500 for anything else -------------


@pytest.fixture
def dice_client(monkeypatch):
    # database.py imports psycopg2 at module level; the unit image doesn't have it.
    if "psycopg2" not in sys.modules:
        pg = types.ModuleType("psycopg2")
        pg.extras = types.ModuleType("psycopg2.extras")
        monkeypatch.setitem(sys.modules, "psycopg2", pg)
        monkeypatch.setitem(sys.modules, "psycopg2.extras", pg.extras)
    from flask import Flask
    from flask_jwt_extended import JWTManager, create_access_token

    from routes import dice

    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(dice.dice_bp, url_prefix="/api")
    with app.app_context():
        token = create_access_token(identity="7")
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client, dice


def test_dice_roll_returns_validation_message(dice_client):
    client, _ = dice_client
    r = client.post("/api/campaigns/1/roll", json={"pool_size": True})
    assert r.status_code == 400
    assert r.get_json() == {"error": "Invalid input: pool_size must be an integer, not a boolean"}

    r = client.post("/api/campaigns/1/roll", json={"pool_expression": "4+x"})
    assert r.status_code == 400
    assert r.get_json()["error"].startswith("Invalid input: Invalid pool.")

    r = client.post("/api/campaigns/1/roll", json=[1, 2])
    assert r.status_code == 400
    assert r.get_json() == {"error": "Invalid input: Request body must be a JSON object"}


class _FakeCursor:
    def close(self):
        pass


class _FakeConn:
    def cursor(self):
        return _FakeCursor()

    def close(self):
        pass


@pytest.mark.parametrize(
    "path, body",
    [
        ("/api/campaigns/1/roll", {"pool_size": 3}),
        ("/api/campaigns/1/roll/1/reroll", {"indices": [0]}),
        ("/api/campaigns/1/rouse", {"location_id": 2}),
        ("/api/campaigns/1/roll/contested", {"attacker_pool": 3, "defender_pool": 3}),
    ],
)
def test_dice_other_value_errors_get_a_generic_500(dice_client, monkeypatch, path, body):
    client, dice = dice_client
    monkeypatch.setattr(dice, "get_db", lambda: _FakeConn())
    monkeypatch.setattr(dice, "_user_can_access_campaign", lambda *a: True)

    def boom(*a, **k):
        raise ValueError("internal detail: relation dice_rolls column xyz")

    monkeypatch.setattr(dice, "_campaign_rules", boom)
    r = client.post(path, json=body)
    assert r.status_code == 500
    assert "internal detail" not in r.get_data(as_text=True)
    assert set(r.get_json()) == {"error"}
