""""Previously on…" (0.27): …/chronicle/recap and …/recap/visit. Every member gets it, built from the
stored player view only; rooms are checked again when read; no usernames, no hidden rolls."""

import json
from datetime import datetime, timedelta

from tests.unit.chronicle_fixtures import Conn  # noqa: I001  (stubs psycopg2 before the routes import)
from routes import chronicle
from tests.unit.test_chronicle_routes import (  # noqa: F401  (api is a fixture)
    ADMIN, HELPER_IN, OUTSIDER, PLAYER, ST, USERNAMES, _walk_keys, api, write,
)

URL = "/api/campaigns/10/chronicle/recap"


def away(api, uid, room, since):
    api.raw.execute("INSERT OR REPLACE INTO chronicle_room_visits (user_id, location_id, last_seen_at, away_since) "
                    "VALUES (?, ?, ?, ?)", (uid, room, datetime.now().isoformat(" "), since.isoformat(" ")))
    api.raw.commit()


def test_recap_for_players_in_rooms_they_can_read(api):
    write(api)
    away(api, PLAYER, 101, datetime(2026, 9, 30))
    r = api("GET", f"{URL}?location_id=101", PLAYER)
    assert r.status_code == 200
    body = r.get_json()
    assert [n["night"] for n in body["nights"]] == [1, 3]  # the basement's nights, newest last
    assert all(n["title"] and n["summary"] and n["first_message_id"] for n in body["nights"])
    assert body["so_far"] and body["lang"] == "el"
    text = json.dumps(body, ensure_ascii=False)
    assert not any(u in text for u in USERNAMES)
    assert not any(str(k).startswith("st_") for k in _walk_keys(body))
    assert "Sealed by the Storyteller" not in text and "The Crypt" not in text
    # only the nights since the absence began
    away(api, PLAYER, 101, datetime(2026, 10, 2, 12))
    assert [n["night"] for n in api("GET", f"{URL}?location_id=101", PLAYER).get_json()["nights"]] == [3]
    # nothing since: empty, unless the button asks for the room's recent nights
    away(api, PLAYER, 101, datetime(2026, 10, 9))
    assert api("GET", f"{URL}?location_id=101", PLAYER).get_json()["nights"] == []
    recent = api("GET", f"{URL}?location_id=101&recent=1", PLAYER).get_json()
    assert recent["recent"] is True and [n["night"] for n in recent["nights"]] == [1, 3]
    for uid in (ST, ADMIN, HELPER_IN):
        assert api("GET", f"{URL}?location_id=101", uid).status_code == 200


def test_outsiders_closed_rooms_and_bad_rooms_get_404(api):
    write(api)
    assert api("GET", f"{URL}?location_id=101", OUTSIDER).status_code == 404
    assert api("POST", f"{URL}/visit", OUTSIDER, {"location_id": 101}).status_code == 404
    assert api("GET", f"{URL}?location_id=103", PLAYER).status_code == 404  # closed by the Storyteller
    assert api("GET", f"{URL}?location_id=999", PLAYER).status_code == 404
    assert api("GET", URL, PLAYER).status_code == 400
    api.raw.execute("UPDATE locations SET is_open = 0 WHERE id = 101")
    api.raw.commit()
    assert api("GET", f"{URL}?location_id=101", PLAYER).status_code == 404  # checked again when read
    # the Storyteller can read the closed room, but the recap is the player view: no closed-room night
    away(api, ST, 103, datetime(2026, 9, 30))
    st = api("GET", f"{URL}?location_id=103&recent=1", ST).get_json()
    assert st["nights"] == [] and st["so_far"] is None  # the digest names a room closed since


def test_hidden_roll_night_shows_no_hidden_content(api):
    write(api)
    away(api, PLAYER, 102, datetime(2026, 9, 30))
    body = api("GET", f"{URL}?location_id=102", PLAYER).get_json()
    assert [n["night"] for n in body["nights"]] == [2]
    text = json.dumps(body, ensure_ascii=False)
    assert "rolled" not in text and "dice" not in text
    first = body["nights"][0]["first_message_id"]
    kind = api.raw.execute("SELECT ai_message_kind FROM messages WHERE id = ?", (first,)).fetchone()[0]
    assert not (kind or "").startswith(("dice_roll_hidden", "dice_animation_hidden"))


def test_no_digest_no_recap(api):
    away(api, PLAYER, 101, datetime(2026, 9, 30))
    body = api("GET", f"{URL}?location_id=101&recent=1", PLAYER).get_json()
    assert body["nights"] == [] and body["so_far"] is None


def test_visit_moves_away_since_only_after_12_hours():
    from tests.unit.chronicle_fixtures import build, db

    rows, marks = build("el", 1)
    cur = Conn(db(rows, marks)).cursor()
    t = datetime(2026, 10, 1, 20)
    assert chronicle.record_visit(cur, PLAYER, 101, t) is None  # the first visit
    assert chronicle.record_visit(cur, PLAYER, 101, t + timedelta(hours=11)) is None
    back = t + timedelta(hours=11 + 12)
    assert chronicle.record_visit(cur, PLAYER, 101, back) == t + timedelta(hours=11)
    # a reload a minute later keeps the same absence (the same recap)
    assert chronicle.record_visit(cur, PLAYER, 101, back + timedelta(minutes=1)) == t + timedelta(hours=11)


def test_visit_route(api):
    r = api("POST", f"{URL}/visit", PLAYER, {"location_id": 101})
    assert r.status_code == 200 and r.get_json()["away_since"] is None
    assert api("POST", f"{URL}/visit", PLAYER, {"location_id": 103}).status_code == 404


def test_read_it_with_server_voices(api, monkeypatch):
    from routes import voice as rv

    write(api)
    api.raw.execute("ALTER TABLE campaigns ADD COLUMN voice_settings TEXT")
    api.raw.commit()
    away(api, PLAYER, 101, datetime(2026, 9, 30))
    sent = []
    monkeypatch.setattr(rv, "_user_settings", lambda cur, uid: None)
    monkeypatch.setattr(rv, "_speech_tts", lambda cur, body, mid: (sent.append((body, mid)) or {"job_id": "ab", "state": "queued"}, 200))
    r = api("POST", f"{URL}/tts", PLAYER, {"location_id": 101, "chunk": 0})
    assert r.status_code == 200
    out = r.get_json()
    assert out["chunks"] >= 3 and out["text"] == "Προηγουμένως…"
    body, mid = sent[0]
    assert mid is None and body["lang"] == "el" and body["role"] == "narrator"
    every = " ".join(api("POST", f"{URL}/tts", PLAYER, {"location_id": 101, "chunk": i}).get_json()["text"]
                     for i in range(out["chunks"]))
    assert "Νύχτα 1" in every and "Νύχτα 3" in every and "Η ιστορία ως τώρα" in every
    assert not any(u in every for u in USERNAMES)
    assert api("POST", f"{URL}/tts", PLAYER, {"location_id": 101, "chunk": out["chunks"]}).status_code == 400
    assert api("POST", f"{URL}/tts", PLAYER, {"location_id": 103, "chunk": 0}).status_code == 404
    assert api("POST", f"{URL}/tts", OUTSIDER, {"location_id": 101, "chunk": 0}).status_code == 404
    away(api, PLAYER, 101, datetime(2026, 10, 9))  # nothing new: nothing to read
    assert api("POST", f"{URL}/tts", PLAYER, {"location_id": 101, "chunk": 0}).status_code == 400
    assert api("POST", f"{URL}/tts", PLAYER, {"location_id": 101, "chunk": 0, "recent": True}).status_code == 200
