"""Guided mode (Forge v2 part E): the committed question set, its checker and GET /api/rules/v5/guided.

The content test reads docs/rules/v5/guided/questions.json and the committed catalog (repo checkout
in CI, /app/project_docs in the backend container): every weight key must be a catalog clan or
predator type name, an Attribute category or key, a skill key or a distribution, and every text
needs English and Greek.
"""

import copy
import json

import pytest

from services import v5_catalog, v5_guided
from services.character_sheet_v5 import V5_SKILLS


@pytest.fixture(scope="module")
def repo():
    v5_guided._cache.update(key=None, data=None, etag=None)
    v5_catalog._cache.update(key=None, data=None, etag=None)
    data, catalog = v5_guided.load_guided(), v5_catalog.load_catalog()
    if data is None or catalog is None:
        pytest.skip("docs/rules/v5 (guided questions or catalog) not on disk here")
    return data, catalog


def test_the_committed_question_set_is_valid(repo):
    data, catalog = repo
    assert v5_guided.problems(data, catalog) == []


def test_every_weight_key_resolves_and_both_languages_exist(repo):
    """The same rules as problems(), spelled out on the real file."""
    data, catalog = repo
    clans = {c["name"] for c in catalog["clans"]}
    predators = {p["name"] for p in catalog["predator_types"]}
    skills = {k for names in V5_SKILLS.values() for k in names}
    attributes = {"physical", "social", "mental", "strength", "dexterity", "stamina", "charisma",
                  "manipulation", "composure", "intelligence", "wits", "resolve"}
    known = {"clan": clans, "predator": predators, "attributes": attributes, "skills": skills,
             "distribution": {"jack", "balanced", "specialist"}}
    for q in data["questions"]:
        assert q["text"]["en"].strip() and q["text"]["el"].strip(), q["id"]
        for o in q["options"]:
            assert o["text"]["en"].strip() and o["text"]["el"].strip(), (q["id"], o["id"])
            for axis, weights in o["weights"].items():
                unknown = set(weights) - known[axis]
                assert not unknown, (q["id"], o["id"], axis, unknown)


def test_the_placeholder_set_reaches_every_clan_and_predator_type(repo):
    """Our placeholder set gives every clan and predator type some weight (Mario's may differ)."""
    data, catalog = repo
    if "placeholder" not in str(data.get("author", "")).lower():
        pytest.skip("not the placeholder set")
    seen = {"clan": set(), "predator": set()}
    for q in data["questions"]:
        for o in q["options"]:
            for axis in seen:
                seen[axis] |= set(o["weights"].get(axis, {}))
    assert {c["name"] for c in catalog["clans"]} == seen["clan"]
    assert {p["name"] for p in catalog["predator_types"]} == seen["predator"]
    assert len(data["questions"]) == 8


# ---------- the checker on broken sets ----------

CATALOG = {"clans": [{"name": "Brujah"}, {"name": "Thin-blood"}], "predator_types": [{"name": "Alleycat"}]}


def _good():
    option = {"id": "a", "text": {"en": "Hit him.", "el": "Τον χτυπάς."},
              "weights": {"clan": {"Brujah": 2}, "predator": {"Alleycat": 1}, "attributes": {"physical": 1, "wits": 1},
                          "skills": {"brawl": 2, "animal_ken": 1}, "distribution": {"specialist": 1}}}
    other = {"id": "b", "text": {"en": "Walk away.", "el": "Φεύγεις."}, "weights": {"clan": {"Thin-blood": 1}}}
    return {"version": 1, "author": "test", "thresholds": {"min_score_share": 0.3, "min_lead": 2},
            "questions": [{"id": "q1", "axis": "violence", "text": {"en": "Fight?", "el": "Καβγάς;"},
                           "options": [option, other]}]}


def test_a_good_set_has_no_problems():
    assert v5_guided.problems(_good(), CATALOG) == []


@pytest.mark.parametrize(
    "mutate, expect",
    [
        (lambda d: d["questions"][0]["options"][0]["weights"]["clan"].update({"Brujha": 1}), "unknown key 'Brujha'"),
        (lambda d: d["questions"][0]["options"][0]["weights"]["predator"].update({"Siren": 1}), "unknown key 'Siren'"),
        (lambda d: d["questions"][0]["options"][0]["weights"]["skills"].update({"Animal Ken": 1}), "unknown key 'Animal Ken'"),
        (lambda d: d["questions"][0]["options"][0]["weights"]["attributes"].update({"brains": 1}), "unknown key 'brains'"),
        (lambda d: d["questions"][0]["options"][0]["weights"]["distribution"].update({"generalist": 1}), "unknown key 'generalist'"),
        (lambda d: d["questions"][0]["options"][0]["weights"].update({"disciplines": {"Potence": 1}}), "unknown weight group"),
        (lambda d: d["questions"][0]["options"][0].update({"weigths": {}}), "unknown key 'weigths'"),
        (lambda d: d["questions"][0]["options"][0]["weights"]["clan"].update({"Brujah": 0}), "whole number from 1 to 5"),
        (lambda d: d["questions"][0]["options"][0]["weights"]["clan"].update({"Brujah": 1.5}), "whole number from 1 to 5"),
        (lambda d: d["questions"][0]["options"][0]["weights"]["clan"].update({"Brujah": True}), "whole number from 1 to 5"),
        (lambda d: d["questions"][0]["options"][0]["text"].pop("el"), "text.el is missing"),
        (lambda d: d["questions"][0]["text"].update({"el": "  "}), "text.el is missing"),
        (lambda d: d["questions"][0]["text"].update({"en": "x" * 301}), "longer than 300"),
        (lambda d: d["questions"][0]["options"][1].update({"id": "a"}), "used twice in this question"),
        (lambda d: d["questions"].append(copy.deepcopy(d["questions"][0])), "id 'q1' is used twice"),
        (lambda d: d["questions"][0].update({"id": "Q 1"}), "id must be lowercase"),
        (lambda d: d["questions"][0]["options"].pop(), "needs 2 to 10 options"),
        (lambda d: d["thresholds"].update({"min_score_share": 1.5}), "min_score_share"),
        (lambda d: d["thresholds"].update({"min_lead": -1}), "min_lead"),
        (lambda d: d.update({"version": "1"}), "version"),
        (lambda d: d.update({"questions": []}), "non-empty list"),
    ],
)
def test_the_checker_catches(mutate, expect):
    data = _good()
    mutate(data)
    found = v5_guided.problems(data, CATALOG)
    assert any(expect in p for p in found), found


# ---------- loader and route ----------


@pytest.fixture
def guided_file(tmp_path, monkeypatch):
    path = tmp_path / "questions.json"
    path.write_text(json.dumps(_good()), encoding="utf-8")
    monkeypatch.setenv("V5_GUIDED_FILE", str(path))
    v5_guided._cache.update(key=None, data=None, etag=None)
    yield path
    v5_guided._cache.update(key=None, data=None, etag=None)


def test_loader_reads_the_file_and_the_etag_follows_it(guided_file):
    data = v5_guided.load_guided()
    assert data["questions"][0]["id"] == "q1"
    first = v5_guided.guided_etag()
    assert first
    changed = _good()
    changed["version"] = 2
    guided_file.write_text(json.dumps(changed, indent=1), encoding="utf-8")
    assert v5_guided.load_guided()["version"] == 2
    assert v5_guided.guided_etag() != first


def test_loader_refuses_broken_json(guided_file):
    guided_file.write_text("{ not json", encoding="utf-8")
    assert v5_guided.load_guided() is None
    assert v5_guided.guided_etag() is None


@pytest.fixture
def client(guided_file):
    from flask import Flask
    from flask_jwt_extended import JWTManager, create_access_token

    from routes import rules

    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(rules.bp, url_prefix="/api/rules")
    with app.app_context():
        token = create_access_token(identity="1")
    return app.test_client(), {"Authorization": f"Bearer {token}"}


def test_route_needs_login_and_serves_with_etag(client):
    c, auth = client
    assert c.get("/api/rules/v5/guided").status_code == 401
    r = c.get("/api/rules/v5/guided", headers=auth)
    assert r.status_code == 200
    body = r.get_json()
    assert body["questions"][0]["options"][0]["weights"]["clan"] == {"Brujah": 2}
    assert body["thresholds"] == {"min_score_share": 0.3, "min_lead": 2}
    assert body["etag"] and r.headers["ETag"] == f'"{body["etag"]}"'
    assert r.headers["Cache-Control"] == "private, no-cache"
    again = c.get("/api/rules/v5/guided", headers={**auth, "If-None-Match": f'"{body["etag"]}"'})
    assert again.status_code == 304
    assert again.headers["Cache-Control"] == "private, no-cache"


def test_route_404_without_the_file(client, monkeypatch, tmp_path):
    c, auth = client
    monkeypatch.setenv("V5_GUIDED_FILE", str(tmp_path / "nothing.json"))
    monkeypatch.setattr(v5_guided, "_CANDIDATES", ())
    assert c.get("/api/rules/v5/guided", headers=auth).status_code == 404
