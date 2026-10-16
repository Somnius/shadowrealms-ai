"""Read along (0.22): text spoken in sentence chunks (one TTS job each), roll requests and dice
said in the listener's language, NPC characters speak with their gender, the Storyteller deletes
a chronicle's recordings, roll tags kept out of the translator."""

import json

import pytest

from services import voice_tts as vt
from tests.unit.test_creation_validation_routes import Conn
from tests.unit.test_voice_clips import speech  # noqa: F401  (fixture)
from tests.unit.test_voice_tts import api, row  # noqa: F401  (fixture)


def test_split_chunks_sentences_quotes_and_cap():
    assert vt.split_chunks("Short one. Another? «Ναι!» είπε.") == ["Short one. Another? «Ναι!» είπε."]
    long = ("The rain falls on the old church and the night is deep and cold. " * 3).strip()
    parts = vt.split_chunks(long)
    assert len(parts) == 3 and all(len(p) <= vt.CHUNK_MAX for p in parts)
    assert vt.split_chunks('He said "Run." Then nothing.', cap=20) == ['He said "Run."', "Then nothing."]
    words = "λέξη " * 120
    assert all(len(p) <= vt.CHUNK_MAX for p in vt.split_chunks(words))
    assert vt.split_chunks("Τι θέλεις; Φύγε τώρα.", cap=12) == ["Τι θέλεις;", "Φύγε τώρα."]
    assert vt.split_chunks("") == []


def test_roll_request_read_in_listener_language():
    st = row(role="assistant", content="Κοιτάς γύρω. [[roll: Intelligence + Investigation | 7 dice | 1 hunger | difficulty 2]]")
    el = vt.spoken_parts(st, "storyteller", "el")
    assert el[0] == {"text": "Κοιτάς γύρω. Intelligence + Investigation", "lang": "el"}
    assert el[-1] == {"text": "Ρίψη: Intelligence συν Investigation, 7 ζάρια, Πείνα 1, δυσκολία 2.", "lang": "el"}
    en = vt.spoken_parts(st, "storyteller", "en")
    assert en[-1] == {"text": "Roll: Intelligence plus Investigation, 7 dice, 1 Hunger, difficulty 2.", "lang": "en"}
    assert "[[" not in " ".join(p["text"] for p in el)
    assert vt.strip_roll_tags("a [[roll: X | 2 dice]] b [[roll: junk]]") == "a **X** b "


def test_dice_sentence_from_marker():
    marker = {"rules_edition": "v5", "dice_preview": [1, 2, 6, 10, 10, 7, 8], "successes": 6,
              "difficulty": 3, "is_critical": True}
    d = row(content="Mira rolls (V5) for **Intelligence + Investigation**", ai_message_kind="dice_roll:a1")
    el = vt.spoken_parts(d, "dice", "el", marker)
    assert el == [{"text": "Mira: Ρίψη Intelligence συν Investigation, 7 ζάρια, 6 επιτυχίες, κρίσιμη επιτυχία.", "lang": "el"}]
    en = vt.spoken_parts(d, "dice", "en", {**marker, "is_critical": False, "is_messy_critical": True})
    assert en[0]["text"] == "Mira: Roll Intelligence plus Investigation, 7 dice, 6 successes, messy critical."
    classic = {"dice_preview": [1, 3], "successes": 0, "difficulty": 6, "is_botch": True}
    assert vt.spoken_parts(d, "dice", "en", classic)[0]["text"].endswith("2 dice, 0 successes, botch.")
    assert vt.spoken_parts(d, "dice", "el", None)[0]["lang"] == "en"  # no marker: never the Greek voice


def test_tts_bodies_per_chunk_language():
    st = row(role="assistant", content="Η βροχή πέφτει. [[roll: Wits + Awareness | 5 dice | difficulty 6]]")
    bodies = vt.tts_bodies(st, None, {}, {"narrator_voice_el": "el-spyros"}, listen_lang="en")
    assert [b["lang"] for b in bodies] == ["el", "en"]
    assert bodies[0]["voice"] == "el-spyros" and bodies[1]["role"] == "narrator"
    assert vt.tts_request(st, None, {}, {}, chunk=5) is None


def test_route_chunks(api):  # noqa: F811
    api.raw.execute("UPDATE messages SET content = ? WHERE id = 1",
                    ("First sentence is here and it is long enough to stand. Second one follows it closely now.",))
    r = api("POST", "/api/voice/tts/jobs", 5, {"message_id": 1, "chunk": 0}).get_json()
    assert r["chunks"] == 2 and r["chunk"] == 0 and r["text"].startswith("Mira: First")
    r1 = api("POST", "/api/voice/tts/jobs", 5, {"message_id": 1, "chunk": 1}).get_json()
    assert r1["text"] == "Second one follows it closely now." and r1["key"] != r["key"]
    assert api("GET", f"/api/voice/audio/{r1['key']}", 5).status_code == 200  # each chunk indexed
    assert api("POST", "/api/voice/tts/jobs", 5, {"message_id": 1, "chunk": 2}).status_code == 400
    assert api("POST", "/api/voice/tts/jobs", 5, {"message_id": 1, "chunk": -1}).status_code == 400


def test_route_dice_in_ui_language(api):  # noqa: F811
    from database import ensure_messages_ai_message_kind_column

    ensure_messages_ai_message_kind_column(Conn(api.raw).cursor())
    marker = {"rules_edition": "v5", "dice_preview": [6, 7, 2], "successes": 2, "difficulty": 2}
    api.raw.execute("INSERT INTO messages (id, campaign_id, location_id, user_id, content, ai_message_kind) "
                    "VALUES (20, 10, 100, 3, ?, 'dice_animation:zz')", (json.dumps(marker),))
    api.raw.execute("INSERT INTO messages (id, campaign_id, location_id, user_id, content, ai_message_kind) "
                    "VALUES (21, 10, 100, 3, 'pl rolls (V5) for **Brawl**', 'dice_roll:zz')")
    r = api("POST", "/api/voice/tts/jobs", 5, {"message_id": 21, "lang": "el"}).get_json()
    assert r["text"] == "pl: Ρίψη Brawl, 3 ζάρια, 2 επιτυχίες, επιτυχία."
    sent = [b for m, p, b in api.speech["calls"] if p == "/tts"][-1]
    assert sent["lang"] == "el" and sent["role"] == "narrator"


def test_npc_character_speaks_with_its_gender(api):  # noqa: F811
    """NPC lines in rooms are characters (is_npc) speaking: their characters.gender picks the voice.
    The npcs table's lines (npc_messages) are AI context only and never posted to a room."""
    from database import ensure_characters_gender_column

    ensure_characters_gender_column(Conn(api.raw).cursor())
    api.raw.execute("UPDATE characters SET gender = 'male' WHERE id = 7")
    api("POST", "/api/voice/tts/jobs", 5, {"message_id": 1})
    sent = [b for m, p, b in api.speech["calls"] if p == "/tts"][-1]
    assert sent["gender"] == "male"


def test_storyteller_deletes_chronicle_recordings(api, speech):  # noqa: F811
    from database import ensure_messages_voice_columns, ensure_voice_clips_table

    cur = Conn(api.raw).cursor()
    ensure_voice_clips_table(cur)
    ensure_messages_voice_columns(cur)
    api.raw.execute("INSERT INTO voice_clips (clip_id, campaign_id, user_id, message_id) VALUES (?, 10, 3, 1)", ("a" * 32,))
    api.raw.execute("INSERT INTO voice_clips (clip_id, campaign_id, user_id, message_id) VALUES (?, 10, 3, NULL)", ("d" * 32,))
    api.raw.execute("UPDATE messages SET clip_id = ?, clip_ms = 4000, source = 'voice' WHERE id = 1", ("a" * 32,))
    assert api("DELETE", "/api/campaigns/10/voice-clips", 3).status_code == 403  # a player
    assert api("DELETE", "/api/campaigns/10/voice-clips", 4).status_code == 404  # not a member
    r = api("DELETE", "/api/campaigns/10/voice-clips", 2)
    assert r.status_code == 200 and r.get_json() == {"deleted": 1}
    assert speech["deleted"] == ["a" * 32]
    m = api.raw.execute("SELECT content, clip_id, source FROM messages WHERE id = 1").fetchone()
    assert m[0] == "Good evening" and m[1] is None and m[2] == "voice"
    assert api.raw.execute("SELECT clip_id FROM voice_clips").fetchall() == [("d" * 32,)]  # the unsent draft stays
    assert api("DELETE", "/api/campaigns/10/voice-clips", 1).status_code == 200  # an admin


def test_translator_gets_no_roll_tags(monkeypatch):
    from services import translation

    assert translation.strip_roll_tags("Look. [[roll: Wits + Awareness | 5 dice]]") == "Look. **Wits + Awareness**"


@pytest.mark.parametrize("text", ["Plain.", ""])
def test_no_rolls_no_extra_parts(text):
    assert len(vt.spoken_parts(row(role="assistant", content=text), "storyteller", "el")) == (1 if text else 0)
