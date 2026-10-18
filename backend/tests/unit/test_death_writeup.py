"""The AI death description (services/death_writeup.py): the prompt's material, the canned sentence
on any failure, and the `generated` flag of the kill route."""

import pytest

from services import death_writeup as dw
from tests.unit.chronicle_fixtures import Conn
from tests.unit.test_chronicle_routes import api, write  # noqa: F401 - fixtures

GREEK_DEATH = "Η αυγή σε βρίσκει στο υπόγειο· το σημείωμα με τα σύμβολα πέφτει από τα χέρια σου."


class Fake:
    def __init__(self, text=None, exc=None):
        self.text, self.exc, self.calls = text, exc, []

    def __call__(self, role, messages, params, **kw):
        self.calls.append((role, messages, params, kw))
        if self.exc:
            raise self.exc
        return {"text": self.text}


def gdb(api):
    return lambda: Conn(api.raw)


def test_prompt_has_the_name_clan_story_and_nights(api):
    write(api)
    api.raw.execute("UPDATE characters SET wod_meta = '{\"clan\": \"Tremere\", \"background\": \"SECRET PAST\"}' WHERE id = 20")
    fake = Fake(GREEK_DEATH)
    text, generated = dw.write(gdb(api), 20, "horrible", generate=fake)
    assert (text, generated) == (GREEK_DEATH, True)
    role, msgs, params, kw = fake.calls[0]
    assert role == "chronicler_el" and params["max_tokens"] == dw.MAX_TOKENS and kw["budget_s"] == dw.TIMEOUT_S
    body = msgs[1]["content"]
    assert "Κωνσταντίνος Κατακουζηνός" in body and "Tremere" in body and "SECRET PAST" not in body
    assert "Η ιστορία ως τώρα" in body and "Οι τελευταίες νύχτες του" in body
    assert "βίαιος" in msgs[0]["content"]


@pytest.mark.parametrize("fake", [Fake(exc=RuntimeError("down")), Fake(""), Fake("Dawn finds you in the basement.")])
def test_failures_give_the_canned_greek_sentence(api, fake):
    write(api)
    assert dw.write(gdb(api), 20, "soft", generate=fake) == (dw.FALLBACK["el"]["soft"], False)


def test_missing_character_and_english_fallback(api):
    assert dw.write(gdb(api), 999, "mid", generate=Fake("x")) == (dw.FALLBACK["en"]["mid"], False)
    api.raw.execute("UPDATE campaigns SET language = 'en' WHERE id = 10")
    assert dw.write(gdb(api), 21, "mid", generate=Fake(exc=TimeoutError())) == (dw.FALLBACK["en"]["mid"], False)
    assert set(dw.FALLBACK["el"]) == set(dw.FALLBACK["en"]) == set(dw.DEATH_TYPES)


def _src(name):
    from pathlib import Path
    return (Path(__file__).resolve().parents[2] / "routes" / name).read_text(encoding="utf-8")


def test_kill_route_stores_it_and_says_whether_it_was_generated():
    src = _src("admin.py")
    kill = src[src.index("def kill_character"):src.index("@bp.route('/moderation-log'")]
    assert "death_writeup.write(get_db," in kill and "'generated': generated" in kill and "TODO" not in kill
    # retired in the same transaction as the log row, after the model call
    assert kill.index("death_writeup.write(") < kill.index("UPDATE characters SET is_active") < kill.index("INSERT INTO character_moderation")


def test_create_campaign_defaults_to_the_creators_language():
    src = _src("campaigns.py")
    create = src[src.index("def create_campaign"):src.index("INSERT INTO campaigns")]
    assert "creator_language(user_id)" in create


def test_creator_language(monkeypatch):
    import sqlite3

    import database
    from services.chronicle_digest import creator_language

    raw = sqlite3.connect(":memory:", check_same_thread=False)
    raw.row_factory = sqlite3.Row  # as database.get_db on SQLite: rows without .get
    raw.executescript("CREATE TABLE users (id INTEGER PRIMARY KEY, ui_language TEXT);"
                      "INSERT INTO users VALUES (1, 'EL'), (2, 'fr'), (3, NULL);")
    monkeypatch.setattr(database, "get_db", lambda: Conn(raw))
    assert creator_language(1) == "el"
    assert creator_language(2) is None and creator_language(3) is None and creator_language(99) is None

    def broken():
        raise RuntimeError("db down")

    monkeypatch.setattr(database, "get_db", broken)
    assert creator_language(1) is None


def test_whole_name_tokens_only():
    ch = lambda *names: {"chapter": {"characters": [{"name": n} for n in names]}}  # noqa: E731
    assert dw._named(ch("Κωνσταντίνος"), "Κωνσταντίνος Κατακουζηνός")
    assert dw._named(ch("Marcus Vell"), "Marcus Vell")
    assert not dw._named(ch("Ann"), "Anastasia Vell")
    assert not dw._named(ch("Anastasia"), "Ann")
    assert not dw._named(ch("Marcus Brandt"), "Marcus Vell")


def _night(lid, title, vis="all"):
    return {"key": title, "location_id": lid, "kind": "story", "visibility": vis, "room": "R",
            "chapter": {"title": title, "summary": [f"{title} summary."], "visibility": vis,
                        "st_notes": [{"text": "ST SECRET NOTE", "ids": []}],
                        "characters": [{"name": "Marcus", "note": "x"}]}}


def test_only_the_player_view_goes_in(api, monkeypatch):
    from services import chronicle_jobs as cj

    api.raw.execute("UPDATE campaigns SET language = 'en' WHERE id = 10")
    nights = [_night(101, "Open night"), _night(103, "Crypt night"), _night(102, "Hidden roll night", "st")]
    monkeypatch.setattr(cj, "stored_chapters", lambda cursor, cid, lang: nights)
    monkeypatch.setattr(cj, "stored_digest", lambda cursor, cid, lang, **kw: {
        "tldr": "", "so_far": ["The public story."], "st_so_far": ["ST ONLY PARAGRAPH"], "rooms": [101, 102]})
    fake = Fake("You fall in the basement as the dawn comes.")
    assert dw.write(gdb(api), 21, "mid", generate=fake)[1] is True
    body = fake.calls[0][1][1]["content"]
    assert "Open night" in body and "The public story." in body
    for hidden in ("Crypt night", "Hidden roll night", "ST SECRET NOTE", "ST ONLY PARAGRAPH"):
        assert hidden not in body, hidden


def test_a_digest_kept_back_by_a_closed_room_is_left_out(api, monkeypatch):
    from services import chronicle_jobs as cj

    api.raw.execute("UPDATE campaigns SET language = 'en' WHERE id = 10")
    monkeypatch.setattr(cj, "stored_chapters", lambda cursor, cid, lang: [])
    monkeypatch.setattr(cj, "stored_digest", lambda cursor, cid, lang, **kw: {"tldr": "Crypt secrets.", "rooms": [103]})
    fake = Fake("You fall as the dawn comes.")
    dw.write(gdb(api), 21, "mid", generate=fake)
    assert "Crypt secrets." not in fake.calls[0][1][1]["content"]


def test_the_model_is_called_after_the_read_connection_closed(api):
    events = []

    class C(Conn):
        def close(self):
            events.append("close")
            raise RuntimeError("connection already dead")  # must not lose the kill

    def gen(role, messages, params, **kw):
        events.append("model")
        return {"text": "Dawn finds you in the basement, and the note burns."}

    api.raw.execute("UPDATE campaigns SET language = 'en' WHERE id = 10")
    assert dw.write(lambda: C(api.raw), 21, "soft", generate=gen) == ("Dawn finds you in the basement, and the note burns.", True)
    assert events == ["close", "model"]
