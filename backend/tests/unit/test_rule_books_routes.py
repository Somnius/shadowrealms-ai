"""Rule books API: admin only; status pages through metadatas; delete by book (fake Chroma)."""

import sys
import types

import pytest

from tests.unit.test_rule_book_retrieval import CountingEF, FakeClient, FakeCol, chunk  # noqa: F401


@pytest.fixture
def api(monkeypatch):
    if "psycopg2" not in sys.modules:
        pg = types.ModuleType("psycopg2")
        pg.extras = types.ModuleType("psycopg2.extras")
        monkeypatch.setitem(sys.modules, "psycopg2", pg)
        monkeypatch.setitem(sys.modules, "psycopg2.extras", pg.extras)
    from flask import Flask
    from flask_jwt_extended import JWTManager, create_access_token

    from routes import admin, rule_books
    from services import rag_service

    roles = {"1": "admin", "2": "player"}

    class Cur:
        def execute(self, sql, args):
            self.uid = str(args[0])

        def fetchone(self):
            return {"role": roles[self.uid]}

        def close(self):
            pass

    class Conn:
        def cursor(self):
            return Cur()

        def close(self):
            pass

    monkeypatch.setattr(admin, "get_db", lambda: Conn())
    ef = CountingEF()
    client = FakeClient(ef)
    monkeypatch.setattr(rag_service, "connect_chroma", lambda cfg: client)

    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(rule_books.bp, url_prefix="/api/rule-books")
    with app.app_context():
        tokens = {r: create_access_token(identity=uid) for uid, r in roles.items()}
    c = app.test_client()

    def call(method, url, role="admin"):
        return c.open(url, method=method, headers={"Authorization": f"Bearer {tokens[role]}"})

    return types.SimpleNamespace(call=call, client=client, ef=ef, mod=rule_books)


def test_players_get_403(api):
    assert api.call("GET", "/api/rule-books/status", "player").status_code == 403
    assert api.call("DELETE", "/api/rule-books/vtm-revised-core", "player").status_code == 403


def test_old_endpoints_are_gone(api):
    for method, url in (("GET", "/scan"), ("POST", "/process"), ("POST", "/search"),
                        ("POST", "/context"), ("GET", "/systems")):
        assert api.call(method, "/api/rule-books" + url).status_code in (404, 405)


def test_status_pages_through_metadatas(api, monkeypatch):
    monkeypatch.setattr(api.mod, "PAGE", 2)
    seen = []
    col = FakeCol("rule_books_classic", api.ef, [
        chunk("vtm-revised-core", 1, 0), chunk("vtm-revised-core", 2, 0, kind="sidebar"),
        chunk("vtm-revised-core", 3, 0), chunk("wta-revised-core", 1, 0, line="werewolf"),
        chunk("wta-revised-core", 2, 0, line="werewolf", kind="lore"),
    ])
    orig_get = col.get

    def get(**kw):
        seen.append((kw.get("include"), kw.get("limit"), kw.get("offset")))
        return orig_get(**kw)

    col.get = get
    api.client.cols["rule_books_classic"] = col
    api.client.cols["rule_books_chronicle"] = FakeCol("rule_books_chronicle", api.ef, [
        chunk("night-adventure", 1, 0, kind="adventure", campaign_id=5)])
    r = api.call("GET", "/api/rule-books/status")
    assert r.status_code == 200
    cols = r.get_json()["collections"]
    assert cols["rule_books_v5"] == {"exists": False, "chunks": 0, "books": []}
    books = {b["book_id"]: b for b in cols["rule_books_classic"]["books"]}
    assert books["vtm-revised-core"]["chunks"] == 3
    assert books["vtm-revised-core"]["kinds"] == {"rules": 2, "sidebar": 1}
    assert books["wta-revised-core"]["line"] == "werewolf"
    assert books["vtm-revised-core"]["edition"] == "classic"
    assert cols["rule_books_classic"]["chunks"] == 5
    assert all(inc == ["metadatas"] and lim == 2 for inc, lim, _ in seen)
    assert [o for _, _, o in seen] == [0, 2, 4]
    assert cols["rule_books_chronicle"]["books"][0]["campaign_id"] == 5


def test_delete_book(api):
    api.client.cols["rule_books_classic"] = FakeCol("rule_books_classic", api.ef, [
        chunk("vtm-revised-core", 1, 0), chunk("wta-revised-core", 1, 0, line="werewolf")])
    api.client.cols["rule_books_chronicle"] = FakeCol("rule_books_chronicle", api.ef, [
        chunk("night-adventure", 1, 0, kind="adventure", campaign_id=5),
        chunk("night-adventure", 1, 0, kind="adventure", campaign_id=6)])
    r = api.call("DELETE", "/api/rule-books/vtm-revised-core")
    assert r.status_code == 200 and r.get_json()["deleted"] == {"rule_books_classic": 1}
    assert [m["book_id"] for _, _, m, _ in api.client.cols["rule_books_classic"].rows] == ["wta-revised-core"]
    assert api.call("DELETE", "/api/rule-books/vtm-revised-core").status_code == 404
    # global delete never touches chronicle books
    assert api.call("DELETE", "/api/rule-books/night-adventure").status_code == 404
    r = api.call("DELETE", "/api/rule-books/night-adventure?campaign_id=5")
    assert r.status_code == 200 and r.get_json()["deleted"] == {"rule_books_chronicle": 1}
    assert [m["campaign_id"] for _, _, m, _ in api.client.cols["rule_books_chronicle"].rows] == [6]
    assert api.call("DELETE", "/api/rule-books/night-adventure?campaign_id=x").status_code == 400
    assert api.call("DELETE", "/api/rule-books/Bad%20Id").status_code == 400
