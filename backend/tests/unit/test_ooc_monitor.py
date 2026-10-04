"""OOC monitor: staff exemptions, campaign-scoped bans (never users.*), one verdict per message."""

from datetime import datetime, timedelta

import pytest

from services import classifier as clf
from services import ooc_monitor as om


class FakeConn:
    def __init__(self, db):
        self.db = db

    def cursor(self):
        return FakeCur(self.db)

    def commit(self):
        pass

    def close(self):
        pass


class FakeCur:
    def __init__(self, db):
        self.db = db
        self._row = None

    def execute(self, sql, params=None):
        self.db["sql"].append(sql)
        s = " ".join(sql.split())
        if s.startswith("INSERT INTO ooc_violations"):
            self.db["violations"] += 1
        elif s.startswith("SELECT COUNT(*) AS n FROM ooc_violations"):
            self._row = {"n": self.db["violations"]}
        elif s.startswith("INSERT INTO campaign_bans"):
            user_id, campaign_id, until, reason = params
            self.db["bans"][(user_id, campaign_id)] = {"banned_until": until, "reason": reason}
        elif s.startswith("SELECT banned_until, reason FROM campaign_bans"):
            self._row = self.db["bans"].get(tuple(params))

    def fetchone(self):
        return self._row


@pytest.fixture
def db(monkeypatch):
    state = {"sql": [], "violations": 0, "bans": {}}
    monkeypatch.setattr(om, "_get_db", lambda: FakeConn(state))
    monkeypatch.setattr(om, "ooc_campaign_context", lambda cid: {"room": "OOC", "name": "C"})
    return state


@pytest.fixture
def verdict(monkeypatch):
    calls = []

    def fake(text, ctx=None):
        calls.append(text)
        return clf._result(1.0, "roleplay", 1.0, text, "llm")

    monkeypatch.setattr(clf, "classify_cached", fake)
    return calls


@pytest.mark.parametrize("role,owner,voice,exempt", [
    ("admin", False, None, True), ("helper", False, None, True), (" Admin ", False, None, True),
    ("player", True, None, True), ("player", False, "staff", True),
    ("player", False, "player", False), ("player", False, None, False), (None, False, "character", False),
])
def test_exemptions(role, owner, voice, exempt):
    assert om.is_exempt_from_ooc_moderation(role, owner, voice) is exempt


def test_staff_are_never_classified_or_warned(db, verdict):
    m = om.OOCMonitor()
    for kw in ({"site_role": "admin"}, {"site_role": "helper"}, {"is_campaign_owner": True},
               {"speaker_mode": "staff"}):
        assert m.check_message("*hisses at the Prince*", 7, 5, "ooc", **kw) == (False, "", False)
    assert verdict == [] and db["violations"] == 0


def test_third_warning_bans_from_that_campaign_only(db, verdict):
    m = om.OOCMonitor()
    for i in (1, 2):
        v, msg, ban = m.check_message("*hisses*", 7, 5, "OOC", site_role="player")
        assert v and not ban and f"({i}/3)" in msg
    v, msg, ban = m.check_message("*hisses*", 7, 5, "ooc", site_role="player")
    assert v and ban and "this campaign" in msg
    assert set(db["bans"]) == {(7, 5)}
    assert not any("UPDATE USERS" in " ".join(s.split()).upper() for s in db["sql"])
    assert m.check_user_ban(7, 5)[0] is True
    assert m.check_user_ban(7, 6) == (False, "")  # other campaign
    assert m.check_user_ban(8, 5) == (False, "")


def test_ic_rooms_are_not_moderated(db, verdict):
    assert om.OOCMonitor().check_message("*hisses*", 7, 5, "tavern") == (False, "", False)
    assert verdict == []


def test_campaign_ban_state_expiry():
    now = datetime(2026, 10, 4, 12, 0)
    assert om.campaign_ban_state(None, now) == (False, "")
    assert om.campaign_ban_state({"banned_until": now - timedelta(minutes=1)}, now) == (False, "")
    banned, msg = om.campaign_ban_state({"banned_until": now + timedelta(hours=2, minutes=5), "reason": "r"}, now)
    assert banned and "2h 5m" in msg
    assert om.campaign_ban_state({"banned_until": (now + timedelta(hours=1)).isoformat()}, now)[0]
