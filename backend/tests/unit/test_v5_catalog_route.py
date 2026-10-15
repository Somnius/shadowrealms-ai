"""GET /api/rules/v5/catalog and services/v5_catalog.py (loader, descriptions overlay, lookup)."""

import json

import pytest

from services import v5_catalog


def _write(path, name, entries):
    (path / f"{name}.json").write_text(json.dumps({"catalog": name, "version": 1, "entries": entries}))


@pytest.fixture
def cat_dir(tmp_path, monkeypatch):
    _write(tmp_path, "clans", [{"id": "clan:hecata", "name": "Hecata", "disciplines": ["discipline:oblivion"]}])
    _write(
        tmp_path,
        "disciplines",
        [{"id": "discipline:oblivion", "name": "Oblivion", "powers": [{"id": "power:oblivion:shadow-cloak", "name": "Shadow Cloak", "level": 1}]}],
    )
    _write(tmp_path, "predator_types", [{"id": "predator:grim-reaper", "name": "Grim Reaper", "aliases": ["Reaper"]}])
    (tmp_path / "descriptions").mkdir()
    (tmp_path / "descriptions" / "disciplines.json").write_text(
        json.dumps({"power:oblivion:shadow-cloak": {"en": "Wrap in shadow.", "el": "Τυλίγεσαι στη σκιά."}})
    )
    monkeypatch.setenv("V5_CATALOG_DIR", str(tmp_path))
    v5_catalog._cache.update(key=None, data=None, etag=None)
    yield tmp_path
    v5_catalog._cache.update(key=None, data=None, etag=None)


def test_loads_overlays_and_finds(cat_dir):
    data = v5_catalog.load_catalog()
    assert [c["name"] for c in data["clans"]] == ["Hecata"]
    assert data["rituals"] == []  # a missing file is an empty list
    power = data["disciplines"][0]["powers"][0]
    assert power["desc"] == {"en": "Wrap in shadow.", "el": "Τυλίγεσαι στη σκιά."}
    assert v5_catalog.find(data, "predator_types", "  grim   REAPER ")["id"] == "predator:grim-reaper"
    assert v5_catalog.find(data, "predator_types", "reaper")["name"] == "Grim Reaper"
    assert v5_catalog.find(data, "clans", "Brujah") is None


def test_etag_changes_with_the_files(cat_dir):
    v5_catalog.load_catalog()
    first = v5_catalog.catalog_etag()
    _write(cat_dir, "rituals", [{"id": "ritual:blood-walk", "name": "Blood Walk", "level": 1}])
    v5_catalog.load_catalog()
    assert v5_catalog.catalog_etag() != first


def test_the_repo_catalog_loads():
    v5_catalog._cache.update(key=None, data=None, etag=None)
    data = v5_catalog.load_catalog()
    if data is None:
        pytest.skip("no catalog installed here")
    assert len(data["clans"]) == 16
    assert v5_catalog.find(data, "clans", "Hecata")


@pytest.fixture
def client(cat_dir):
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
    assert c.get("/api/rules/v5/catalog").status_code == 401
    r = c.get("/api/rules/v5/catalog", headers=auth)
    assert r.status_code == 200
    body = r.get_json()
    assert body["clans"][0]["name"] == "Hecata" and body["etag"]
    again = c.get("/api/rules/v5/catalog", headers={**auth, "If-None-Match": f'"{body["etag"]}"'})
    assert again.status_code == 304


def test_route_404_without_catalog(client, monkeypatch, tmp_path):
    c, auth = client
    monkeypatch.setenv("V5_CATALOG_DIR", str(tmp_path / "nothing"))
    monkeypatch.setattr(v5_catalog, "_CANDIDATES", ())
    assert c.get("/api/rules/v5/catalog", headers=auth).status_code == 404
