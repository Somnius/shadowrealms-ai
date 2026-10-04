"""database.once_per_process: helpers become no-ops only after migrate_db()'s COMMIT."""

import importlib
import sys
import types

import pytest


@pytest.fixture()
def db(monkeypatch):
    # database.py imports psycopg2 at module level; the unit image doesn't have it.
    if "psycopg2" not in sys.modules:
        pg = types.ModuleType("psycopg2")
        pg.extras = types.ModuleType("psycopg2.extras")
        monkeypatch.setitem(sys.modules, "psycopg2", pg)
        monkeypatch.setitem(sys.modules, "psycopg2.extras", pg.extras)
    monkeypatch.setenv("DATABASE_TYPE", "postgresql")
    mod = importlib.import_module("database")
    monkeypatch.setattr(mod, "_SCHEMA_ENSURED", set())
    return mod


def _counter(db):
    calls = []

    @db.once_per_process
    def ensure_probe(cursor):
        calls.append(cursor)

    return ensure_probe, calls


def test_request_path_never_marks_done(db):
    """A request may roll back the DDL, so a call outside migrate_db() runs every time."""
    ensure_probe, calls = _counter(db)
    ensure_probe("req1")  # then the request rolls back...
    ensure_probe("req2")  # ...so this must run the DDL again
    assert calls == ["req1", "req2"]


def test_marked_done_after_successful_migration(db):
    ensure_probe, calls = _counter(db)
    with db.schema_migration():
        ensure_probe("migrate")
    ensure_probe("req")
    assert calls == ["migrate"]


def test_failed_migration_marks_nothing(db):
    ensure_probe, calls = _counter(db)

    def failing_migration():
        with db.schema_migration():
            ensure_probe("migrate")
            raise RuntimeError("COMMIT failed")

    pytest.raises(RuntimeError, failing_migration)
    ensure_probe("req")
    assert calls == ["migrate", "req"]
    assert db._MIGRATION_PENDING is None


def test_sqlite_is_never_cached(db, monkeypatch):
    monkeypatch.setenv("DATABASE_TYPE", "sqlite")
    ensure_probe, calls = _counter(db)
    with db.schema_migration():
        ensure_probe("a")
    ensure_probe("b")
    assert calls == ["a", "b"]


def test_every_decorated_helper_runs_in_migrate_db():
    """Request paths rely on migrate_db() having marked every helper done."""
    import ast
    import os

    backend = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    decorated = set()
    for root, _dirs, files in os.walk(backend):
        if "tests" in root.split(os.sep):
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            with open(os.path.join(root, f), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and any(
                    getattr(d, "id", None) == "once_per_process" for d in node.decorator_list
                ):
                    decorated.add(node.name)
    with open(os.path.join(backend, "database.py"), encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    migrate = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "migrate_db")
    pg_branch = next(n for n in migrate.body if isinstance(n, ast.If))
    called = {
        n.func.id for n in ast.walk(pg_branch) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert decorated, "no decorated helpers found"
    assert decorated <= called, f"not run by migrate_db: {sorted(decorated - called)}"
