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


def test_advantages_and_loresheets_load_with_level_descriptions(cat_dir):
    assert v5_catalog.load_catalog()["advantages"] == []  # not installed: empty lists
    assert v5_catalog.load_catalog()["loresheets"] == []
    _write(cat_dir, "advantages", [{"id": "background:allies", "name": "Allies", "kind": "background",
                                    "levels": [{"dots": 1, "name": "One ally"}]}])
    _write(cat_dir, "loresheets", [{"id": "loresheet:the-bahari", "name": "The Bahari",
                                    "levels": [{"dots": n, "name": f"Level {n}"} for n in range(1, 6)]}])
    (cat_dir / "descriptions" / "loresheets.json").write_text(json.dumps({
        "loresheet:the-bahari": {"en": "Followers of Lilith.", "el": "Οπαδοί της Lilith."},
        "loresheet:the-bahari:2": {"en": "Scar yourself for Willpower.", "el": "Χαράζεσαι για Willpower."},
    }))
    data = v5_catalog.load_catalog()
    assert data["advantages"][0]["name"] == "Allies"
    sheet = v5_catalog.find(data, "loresheets", "the bahari")
    assert sheet["desc"]["el"] == "Οπαδοί της Lilith."
    assert sheet["levels"][1]["desc"] == {"en": "Scar yourself for Willpower.", "el": "Χαράζεσαι για Willpower."}
    assert "desc" not in sheet["levels"][0]
    assert "desc" not in data["advantages"][0]["levels"][0]


def test_book_ids_for_the_allowed_books_check(cat_dir, monkeypatch):
    assert v5_catalog.book_ids() is None  # a catalog without books.json: allowed_books unchecked
    _write(cat_dir, "books", [{"book_id": "v5-corebook", "title": "Corebook"}, {"title": "no id"}, {"book_id": 3}])
    assert v5_catalog.book_ids() == ["v5-corebook"]
    monkeypatch.setattr(v5_catalog, "load_catalog", lambda: None)
    assert v5_catalog.book_ids() is None

    def broken():
        raise ValueError("bad json")

    monkeypatch.setattr(v5_catalog, "load_catalog", broken)
    assert v5_catalog.book_ids() is None


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
    assert len(data["advantages"]) == 279 and len(data["loresheets"]) == 157
    ashur = v5_catalog.find(data, "loresheets", "Harbingers of Ashur")
    assert all(lv["desc"]["en"] and lv["desc"]["el"] for lv in ashur["levels"])


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
