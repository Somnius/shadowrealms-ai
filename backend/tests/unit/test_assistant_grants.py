"""Only AI-issued text (or admins) may be saved as an assistant (Storyteller) message."""

import json
import os
import sys
import threading
import time
import types

import pytest

from services import assistant_grants as ag


class FakeCursor:
    """Emulates the UPDATE ... RETURNING of consume_grant over an in-memory grant list."""

    def __init__(self, grants):
        self.grants = grants  # list of dicts: user_id, campaign_id, location_id, sha, consumed
        self._row = None

    def execute(self, sql, params):
        user_id, campaign_id, location_id, sha = params
        self._row = None
        for g in self.grants:
            if (g["user_id"] == user_id and g["campaign_id"] == campaign_id
                    and g["location_id"] == location_id and g["sha"] == sha and not g["consumed"]):
                g["consumed"] = True
                self._row = {"id": 1}
                break

    def fetchone(self):
        return self._row


def grant(user=5, campaign=3, location=10, text="The Prince turns to face you."):
    return {"user_id": user, "campaign_id": campaign, "location_id": location,
            "sha": ag.content_hash(text), "consumed": False}


def test_player_cannot_post_arbitrary_storyteller_text():
    cur = FakeCursor([])
    assert not ag.assistant_post_allowed(cur, 5, 3, 10, "*The Storyteller says you win*", None, "player")


def test_issued_reply_is_allowed_once_and_only_for_that_user_and_room():
    cur = FakeCursor([grant()])
    assert not ag.assistant_post_allowed(cur, 6, 3, 10, "The Prince turns to face you.", None, "player")  # other user
    assert not ag.assistant_post_allowed(cur, 5, 3, 11, "The Prince turns to face you.", None, "player")  # other room
    assert not ag.assistant_post_allowed(cur, 5, 3, 10, "The Prince turns to face you. And bows.", None, "player")
    assert ag.assistant_post_allowed(cur, 5, 3, 10, "  The Prince turns to face you.\n", None, "player")  # trimmed
    assert not ag.assistant_post_allowed(cur, 5, 3, 10, "The Prince turns to face you.", None, "player")  # replay


def test_admin_may_post_as_storyteller():
    assert ag.assistant_post_allowed(FakeCursor([]), 1, 3, 10, "anything", None, "admin")


def test_players_get_no_dice_marker_exemption():
    """Dice markers are saved by the dice API now; a player-posted one is just an ungranted text."""
    marker = json.dumps({"animation_id": "abc123", "successes": 2})
    for kind in ("dice_animation:abc123", "dice_animation_hidden:abc123", "dice_roll:abc123"):
        assert not ag.assistant_post_allowed(FakeCursor([]), 5, 3, 10, marker, kind, "player")
    assert ag.assistant_post_allowed(FakeCursor([]), 1, 3, 10, marker, "dice_animation:abc123", "admin")


def test_only_user_and_assistant_roles_exist():
    assert ag.ALLOWED_ROLES == ("user", "assistant")


def test_grant_without_room_is_not_usable_anywhere():
    cur = FakeCursor([grant(location=None)])
    assert not ag.assistant_post_allowed(cur, 5, 3, 10, "The Prince turns to face you.", None, "player")


def test_no_grant_is_recorded_without_a_room(monkeypatch):
    calls = []
    fake_db = types.ModuleType("database")
    fake_db.get_db = lambda: calls.append("connect")
    monkeypatch.setitem(sys.modules, "database", fake_db)
    ag.grant_assistant_reply(5, 3, None, "text")
    ag.grant_assistant_reply(5, 3, 10, "")
    assert calls == []


def test_consume_sql_rechecks_consumed_at_outside_the_subquery():
    sql = []

    class Cur:
        rowcount = 0

        def execute(self, q, params):
            sql.append(q)

        def fetchone(self):
            return None

    assert not ag.consume_grant(Cur(), 5, 3, 10, "x")
    outer, inner = sql[0].split("SELECT id FROM ai_reply_grants", 1)
    assert "consumed_at IS NULL" in outer and "consumed_at IS NULL" in inner
    assert "location_id = %s" in inner and "location_id IS NULL" not in sql[0]


# --- against a real PostgreSQL (optional): SRAI_TEST_PG_DSN=postgresql://u:p@host/db ----------

PG_DSN = os.environ.get("SRAI_TEST_PG_DSN")


@pytest.mark.skipif(not PG_DSN, reason="SRAI_TEST_PG_DSN not set")
def test_parallel_consumes_of_one_grant_on_postgres():
    pytest.importorskip("psycopg2")
    import psycopg2
    import psycopg2.extras

    # A throwaway schema (no FKs to users/campaigns), dropped at the end.
    opts = "-c search_path=srai_grant_race_test"
    setup = psycopg2.connect(PG_DSN)
    setup.autocommit = True
    c = setup.cursor()
    c.execute("DROP SCHEMA IF EXISTS srai_grant_race_test CASCADE")
    c.execute("CREATE SCHEMA srai_grant_race_test")
    c.execute("SET search_path = srai_grant_race_test")
    c.execute("""
        CREATE TABLE ai_reply_grants (
            id BIGSERIAL PRIMARY KEY, user_id INTEGER NOT NULL, campaign_id INTEGER NOT NULL,
            location_id INTEGER, content_sha256 TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(), consumed_at TIMESTAMP)""")
    text = "The Prince turns to face you."
    try:
        for trial in range(5):
            c.execute("INSERT INTO ai_reply_grants (user_id, campaign_id, location_id, content_sha256) "
                      "VALUES (999001, 3, 10, %s)", (ag.content_hash(text),))
            results, barrier = [], threading.Barrier(8)

            def go():
                conn = psycopg2.connect(PG_DSN, options=opts, cursor_factory=psycopg2.extras.RealDictCursor)
                try:
                    cur = conn.cursor()
                    barrier.wait()
                    results.append(ag.consume_grant(cur, 999001, 3, 10, text))
                    time.sleep(0.05)  # save_message does more work before its COMMIT
                    conn.commit()
                finally:
                    conn.close()

            threads = [threading.Thread(target=go) for _ in range(8)]
            [t.start() for t in threads]
            [t.join() for t in threads]
            assert results.count(True) == 1, (trial, results)
    finally:
        c.execute("DROP SCHEMA IF EXISTS srai_grant_race_test CASCADE")
        setup.close()
