"""Voice settings (0.16): validation, the effective read-out rule, and the two routes."""

import json
import sqlite3
import sys
import types

import pytest

from services.request_validation import RequestValidationError
from services.voice_settings import (
    effective_readout,
    normalize_campaign_voice_settings,
    normalize_user_voice_settings,
    validate_campaign_voice_settings,
    validate_user_voice_settings,
)
from tests.unit.test_creation_validation_routes import Conn


def test_user_defaults_and_lenient_normalize():
    s = normalize_user_voice_settings('{"rate": 9, "tts_source": "off", "junk": 1}')
    assert s["rate"] == 1.0 and s["tts_source"] == "off" and s["hear_lang"] == "written"
    assert normalize_user_voice_settings("not json")["tts_source"] == "server"


@pytest.mark.parametrize("body", [
    {"nope": 1}, {"rate": 2.5}, {"rate": True}, {"volume": -0.1}, {"tts_source": "cloud"},
    {"overrides": {"ooc": "yes"}}, {"overrides": {"weather": True}}, [],
])
def test_user_validation_rejects(body):
    with pytest.raises(RequestValidationError):
        validate_user_voice_settings(body)


def test_user_validation_merges_partial():
    cur = validate_user_voice_settings({"rate": 1.5})
    out = validate_user_voice_settings({"overrides": {"ooc": False}}, json.dumps(cur))
    assert out["rate"] == 1.5 and out["overrides"]["ooc"] is False and out["overrides"]["dice"] is None


@pytest.mark.parametrize("body", [
    {"defaults": {"ooc": 1}}, {"max_clip_seconds": 500}, {"allow_phone_stt": "no"}, {"x": 1},
])
def test_campaign_validation_rejects(body):
    with pytest.raises(RequestValidationError):
        validate_campaign_voice_settings(body)


def test_effective_override_beats_default_and_null_falls_through():
    camp = {"defaults": {"storyteller": True, "ic": True, "ooc": False, "dice": True}}
    user = {"overrides": {"storyteller": False, "ooc": None, "dice": None}}
    eff = effective_readout(user, camp)
    assert eff == {"storyteller": False, "ic": True, "ooc": False, "dice": True, "actions": True}
    assert effective_readout(None, None)["ooc"] is True
    assert normalize_campaign_voice_settings(None)["max_clip_seconds"] == 180


SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, role TEXT);
CREATE TABLE campaigns (id INTEGER PRIMARY KEY, created_by INTEGER);
CREATE TABLE campaign_players (campaign_id INTEGER, user_id INTEGER);
INSERT INTO users VALUES (1, 'admin'), (2, 'player'), (3, 'player'), (4, 'player');
INSERT INTO campaigns VALUES (10, 2);
INSERT INTO campaign_players VALUES (10, 3);
"""


@pytest.fixture
def api(monkeypatch):
    if "psycopg2" not in sys.modules:
        pg = types.ModuleType("psycopg2")
        pg.extras = types.ModuleType("psycopg2.extras")
        monkeypatch.setitem(sys.modules, "psycopg2", pg)
        monkeypatch.setitem(sys.modules, "psycopg2.extras", pg.extras)
    monkeypatch.delenv("DATABASE_TYPE", raising=False)
    from flask import Flask
    from flask_jwt_extended import JWTManager, create_access_token

    import database
    from routes import voice

    raw = sqlite3.connect(":memory:", check_same_thread=False)
    raw.executescript(SCHEMA)
    monkeypatch.setattr(voice, "get_db", lambda: Conn(raw))
    # the real ensure_* functions add the columns (SQLite branch), once per test
    monkeypatch.setattr(voice, "ensure_users_voice_settings_column",
                        lambda c: database._ensure_voice_settings_column(c, "users"))
    monkeypatch.setattr(voice, "ensure_campaigns_voice_settings_column",
                        lambda c: database._ensure_voice_settings_column(c, "campaigns"))
    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(voice.voice_bp, url_prefix="/api")
    with app.app_context():
        tokens = {uid: create_access_token(identity=str(uid)) for uid in (1, 2, 3, 4)}
    c = app.test_client()

    def call(method, url, uid, body=None):
        return c.open(url, method=method, json=body, headers={"Authorization": f"Bearer {tokens[uid]}"})

    return call


def test_user_settings_route(api):
    assert api("GET", "/api/voice/settings", 3).get_json()["tts_source"] == "server"
    assert api("PUT", "/api/voice/settings", 3, {"bogus": 1}).status_code == 400
    r = api("PUT", "/api/voice/settings", 3, {"rate": 1.25, "overrides": {"ooc": False}})
    assert r.status_code == 200
    assert api("GET", "/api/voice/settings", 3).get_json()["rate"] == 1.25


def test_campaign_settings_route(api):
    url = "/api/campaigns/10/voice-settings"
    assert api("PUT", url, 3, {"defaults": {"dice": False}}).status_code == 403
    assert api("GET", url, 4).status_code == 404
    r = api("PUT", url, 2, {"defaults": {"dice": False}})
    assert r.status_code == 200 and r.get_json()["can_edit"] is True
    assert api("PUT", url, 1, {"max_clip_seconds": 60}).status_code == 200
    api("PUT", "/api/voice/settings", 3, {"overrides": {"ooc": False}})
    out = api("GET", url, 3).get_json()
    assert out["can_edit"] is False and out["settings"]["max_clip_seconds"] == 60
    assert out["effective"]["dice"] is False and out["effective"]["ooc"] is False
    assert out["effective"]["storyteller"] is True
