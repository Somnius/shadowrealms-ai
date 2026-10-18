"""The composer's slash list (services/ai_slash_commands.COMMANDS, GET /api/ai/slash/commands): in step with
the /ai verbs, EN + EL for every entry, admin verbs only for site admins, /ai help names every verb."""

import sqlite3

import pytest

from services import ai_slash_commands as sc
from tests.unit.chronicle_fixtures import Conn
from tests.unit.test_roll_explainer import ai_routes, stub_psycopg  # noqa: F401 - fixtures

LOCAL = {"/roll", "/me", "/chat"}


def test_list_matches_the_verbs():
    listed = {c["name"][len("/ai "):] for c in sc.COMMANDS if c["name"].startswith("/ai ")}
    assert listed == set(sc.SUPPORTED_AI_SLASH_VERBS)
    assert {c["name"] for c in sc.COMMANDS if not c["name"].startswith("/ai ")} == LOCAL


def test_every_entry_has_english_and_greek():
    for c in sc.COMMANDS:
        for d in [c["description"]] + [c[e]["description"] for e in ("classic", "v5") if e in c]:
            assert d["en"].strip() and d["el"].strip(), c["name"]
            assert any("Ͱ" <= ch <= "Ͽ" for ch in d["el"]), c["name"]


def test_help_names_every_verb():
    text = sc.execute_help_command(1)["display_markdown"]
    for v in sc.SUPPORTED_AI_SLASH_VERBS:
        assert f"/ai {v}" in text, v
    assert len(sc.FUTURE_COMMAND_SUGGESTIONS) == len(sc.SUPPORTED_AI_SLASH_VERBS)


def test_admin_verbs_only_for_admins():
    assert all(not c["admin"] for c in sc.commands_for(False))
    assert len(sc.commands_for(True)) == len(sc.COMMANDS)
    assert "/ai explain" in {c["name"] for c in sc.commands_for(False)}


@pytest.fixture
def client(ai_routes, monkeypatch):
    from flask import Flask
    from flask_jwt_extended import JWTManager, create_access_token

    raw = sqlite3.connect(":memory:", check_same_thread=False)
    raw.executescript("CREATE TABLE users (id INTEGER PRIMARY KEY, role TEXT);"
                      "INSERT INTO users VALUES (1, 'admin'), (2, 'player');")
    monkeypatch.setattr(ai_routes, "get_db", lambda: Conn(raw))
    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(ai_routes.bp, url_prefix="/api/ai")
    with app.app_context():
        tokens = {uid: create_access_token(identity=str(uid)) for uid in (1, 2)}
    c = app.test_client()
    return lambda uid: c.get("/api/ai/slash/commands", headers={"Authorization": f"Bearer {tokens[uid]}"})


def test_endpoint_filters_by_role(client):
    admin, player = client(1).get_json(), client(2).get_json()
    assert admin["version"] == player["version"] == 1
    names = {c["name"] for c in player["commands"]}
    assert "/ai health" not in names and "/ai explain" in names and "/roll" in names
    assert "/ai health" in {c["name"] for c in admin["commands"]}
