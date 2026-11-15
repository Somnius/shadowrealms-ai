"""database.ensure_downtime_tables on SQLite (the PostgreSQL form is checked by the CI schema job)."""

import sqlite3
import sys
import types

import pytest

BASE = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);
CREATE TABLE campaigns (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE characters (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE locations (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE dice_rolls (id INTEGER PRIMARY KEY AUTOINCREMENT);
INSERT INTO users VALUES (1, 'st');
INSERT INTO campaigns VALUES (10, 'Table');
INSERT INTO characters VALUES (100, 'Anna');
"""


@pytest.fixture
def db(monkeypatch):
    if "psycopg2" not in sys.modules:
        pg = types.ModuleType("psycopg2")
        pg.extras = types.ModuleType("psycopg2.extras")
        monkeypatch.setitem(sys.modules, "psycopg2", pg)
        monkeypatch.setitem(sys.modules, "psycopg2.extras", pg.extras)
    monkeypatch.delenv("DATABASE_TYPE", raising=False)
    import database

    raw = sqlite3.connect(":memory:")
    raw.execute("PRAGMA foreign_keys = ON")
    raw.executescript(BASE)
    database.ensure_downtime_tables(raw.cursor())
    database.ensure_downtime_tables(raw.cursor())  # idempotent
    return raw


def test_tables_exist(db):
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"downtime_rounds", "downtime_projects", "downtime_phases", "downtime_indicators",
            "chronicle_variables", "downtime_changes"} <= names


def test_one_live_round_per_campaign(db):
    db.execute("INSERT INTO downtime_rounds (campaign_id, status) VALUES (10, 'released')")
    db.execute("INSERT INTO downtime_rounds (campaign_id, status) VALUES (10, 'released')")
    db.execute("INSERT INTO downtime_rounds (campaign_id, status) VALUES (10, 'open')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO downtime_rounds (campaign_id, status) VALUES (10, 'resolving')")


def test_one_phase_per_project_per_round(db):
    db.execute("INSERT INTO downtime_rounds (id, campaign_id) VALUES (1, 10)")
    db.execute("INSERT INTO downtime_projects (id, campaign_id, character_id, character_name, title) "
               "VALUES (5, 10, 100, 'Anna', 'Buy the club')")
    db.execute("INSERT INTO downtime_phases (project_id, round_id, action) VALUES (5, 1, 'Ask around')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO downtime_phases (project_id, round_id, action) VALUES (5, 1, 'Again')")
    row = db.execute("SELECT difficulty_hidden, version, dice_roll_id FROM downtime_phases").fetchone()
    assert row == (0, 1, None)


def test_character_delete_keeps_project(db):
    db.execute("INSERT INTO downtime_projects (id, campaign_id, character_id, character_name, title) "
               "VALUES (5, 10, 100, 'Anna', 'Buy the club')")
    db.execute("DELETE FROM characters WHERE id = 100")
    assert db.execute("SELECT character_id, character_name FROM downtime_projects").fetchone() == (None, "Anna")


def test_campaign_delete_cascades(db):
    db.execute("INSERT INTO downtime_rounds (id, campaign_id) VALUES (1, 10)")
    db.execute("INSERT INTO downtime_projects (id, campaign_id, character_name, title) VALUES (5, 10, 'A', 'T')")
    db.execute("INSERT INTO downtime_phases (project_id, round_id, action) VALUES (5, 1, 'x')")
    db.execute("INSERT INTO downtime_indicators (project_id, name) VALUES (5, 'Pressure')")
    db.execute("INSERT INTO chronicle_variables (campaign_id, name) VALUES (10, 'Unrest')")
    db.execute("INSERT INTO downtime_changes (campaign_id, phase_id, target_kind, target_id, old_value, "
               "new_value, delta) VALUES (10, 1, 'variable', 1, 0, 1, 1)")
    db.execute("DELETE FROM campaigns WHERE id = 10")
    for t in ("downtime_rounds", "downtime_projects", "downtime_phases", "downtime_indicators",
              "chronicle_variables", "downtime_changes"):
        assert db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0, t


def test_init_schema_has_the_same_tables():
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "..", "init_postgresql_schema.sql")
    with open(path, encoding="utf-8") as f:
        sql = f.read()
    for t in ("downtime_rounds", "downtime_projects", "downtime_phases", "downtime_indicators",
              "chronicle_variables", "downtime_changes"):
        assert f"CREATE TABLE IF NOT EXISTS {t} (" in sql
    assert "uq_downtime_rounds_live" in sql
