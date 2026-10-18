"""The Storyteller's memory of the chronicle (services/chronicle_memory.py): what goes in, what is cut
first, the off switch, the cache, and /ai context."""

import json
from datetime import datetime

import pytest

from services import chronicle_memory as cm
from services import chronicle_settings as cs
from tests.unit.chronicle_fixtures import Conn
from tests.unit.test_chronicle_routes import api, write  # noqa: F401 - fixtures
from tests.unit.test_roll_explainer import ai_routes, stub_psycopg  # noqa: F401 - fixtures


@pytest.fixture(autouse=True)
def fresh_cache():
    cm.forget()
    yield
    cm.forget()


def chapter(lid, n, first, last, room="Room", notes=()):
    return {"key": f"k{lid}-{n}", "location_id": lid, "kind": "story", "first_id": first, "last_id": last,
            "started_at": datetime(2026, 10, n, 21), "room": room,
            "chapter": {"title": f"Night {n} in {room}", "summary": [f"Summary {n} of {room}.", "Second paragraph."],
                        "st_notes": [{"text": t, "ids": []} for t in notes]}}


def mat(**kw):
    m = {"memory": True, "lang": "en",
         "digest": {"tldr": "The coterie found the note.", "threads_open": [{"text": "Who has the key?", "nights": [1]}],
                    "st_so_far": ["The locksmith is a ghoul."]},
         "chapters": [chapter(101, 1, 1, 10, "Basement", notes=["A hidden roll failed."]),
                      chapter(102, 2, 11, 20, "Elysium"), chapter(101, 3, 21, 30, "Basement"),
                      chapter(101, 4, 31, 40, "Basement")]}
    m.update(kw)
    return m


def test_block_holds_the_story_threads_room_nights_others_and_st_text():
    block, n = cm.build_block(mat(), 101, None, 1500)
    assert block.startswith(cm.HEADER["en"])
    for s in ("The coterie found the note.", "Who has the key?", "Night 4 in Basement", "Night 3 in Basement",
              "Night 1 in Basement", "A hidden roll failed.", "Elysium: Night 2 in Elysium — Summary 2 of Elysium.",
              "The locksmith is a ghoul."):
        assert s in block, s
    assert "Second paragraph." in block and n == 4
    assert block.index("Night 1 in Basement") < block.index("Night 4 in Basement")  # newest last


def test_nights_the_history_already_holds_are_skipped():
    block, _ = cm.build_block(mat(), 101, 35, 1500)  # night 4 ends at 40, inside the history
    assert "Night 4 in Basement" not in block and "Night 3 in Basement" in block


def test_only_the_last_three_nights_of_the_room():
    chs = [chapter(101, i, i * 10, i * 10 + 5, "Basement") for i in range(1, 6)]
    block, _ = cm.build_block(mat(chapters=chs), 101, None, 1500)
    assert "Night 1 in" not in block and "Night 2 in" not in block and "Night 5 in" in block


def test_the_budget_drops_lowest_priority_first():
    full, _ = cm.build_block(mat(), 101, None, 1500)
    small, _ = cm.build_block(mat(), 101, None, 80)
    assert len(small) < len(full)
    assert "The coterie found the note." in small and "Who has the key?" in small
    assert "The locksmith is a ghoul." not in small  # Storyteller-only paragraphs go first
    assert cm.build_block(mat(), 101, None, 0) == ("", 0)


def test_empty_when_off_or_nothing_written():
    assert cm.build_block(mat(memory=False), 101, None, 1500) == ("", 0)
    assert cm.build_block(mat(digest=None, chapters=[]), 101, None, 1500) == ("", 0)


def test_greek_header():
    block, _ = cm.build_block(mat(lang="el"), 101, None, 1500)
    assert block.startswith(cm.HEADER["el"]) and "Η ιστορία ως τώρα" in block


def test_errors_give_an_empty_block():
    def broken():
        raise RuntimeError("db down")

    assert cm.storyteller_block(broken, 10, 101, None, 1000) == ("", 0)

    class Cur:
        def execute(self, *a):
            raise RuntimeError("bad query")

    class C:
        def cursor(self):
            return Cur()

        def rollback(self):
            pass

        def close(self):
            pass

    assert cm.storyteller_block(lambda: C(), 10, 101, None, 1000) == ("", 0)


def test_built_from_a_written_chronicle_and_switched_off(api):  # noqa: F811
    raw = api.raw
    assert cm.storyteller_block(lambda: Conn(raw), 10, 101, None, 1500) == ("", 0)  # nothing written yet
    write(api)
    cm.forget()
    block, n = cm.storyteller_block(lambda: Conn(raw), 10, 101, None, 1500)
    assert block.startswith(cm.HEADER["el"]) and n >= 1
    assert "Κωνσταντίνος" in block  # the fake writer's Greek summary
    raw.execute("UPDATE campaigns SET chronicle_settings = ? WHERE id = 10", (json.dumps({"memory": False}),))
    cm.forget(10)
    assert cm.storyteller_block(lambda: Conn(raw), 10, 101, None, 1500) == ("", 0)


def test_cache_within_ttl_and_a_new_digest_invalidates(api):  # noqa: F811
    write(api)
    raw = api.raw
    calls = []

    class Counting(Conn):
        def cursor(self):
            calls.append(1)
            return super().cursor()

    now = [1000.0]
    clock = lambda: now[0]  # noqa: E731
    first = cm.material(Counting(raw).cursor(), 10, clock=clock)
    calls.clear()

    class NoCursor:
        def execute(self, *a):
            raise AssertionError("cursor used within the TTL")

    now[0] += 30
    assert cm.material(NoCursor(), 10, clock=clock) is first
    now[0] += 60  # past the TTL, same stamp: the same material
    assert cm.material(Conn(raw).cursor(), 10, clock=clock) is first
    raw.execute("UPDATE chronicle_digests SET source_hash = 'new' WHERE kind = 'final'")
    now[0] += 61
    assert cm.material(Conn(raw).cursor(), 10, clock=clock) is not first


def test_settings_memory_switch():
    assert cs.normalize({})["memory"] is True
    assert cs.normalize({"memory": "yes"})["memory"] is True
    assert cs.normalize({"memory": False})["memory"] is False
    cur = cs.normalize({})
    assert cs.validate({"memory": False}, cur, [], False)["memory"] is False
    for bad in ("no", 0, None):
        with pytest.raises(Exception):
            cs.validate({"memory": bad}, cur, [], False)


def _prompt(ai_routes, monkeypatch, block):  # noqa: F811
    seen = {}

    class LLM:
        def generate_response(self, message, context, config, raise_on_error=False):
            seen["system"] = context["system_prompt"]
            return "ok"

    monkeypatch.setattr(ai_routes, "get_llm_service", lambda: LLM())
    monkeypatch.setattr(ai_routes, "get_campaign_context", lambda cid: "CAMPAIGN")
    monkeypatch.setattr(ai_routes, "get_character_context", lambda uid, cid: {"has_character": False})
    monkeypatch.setattr(ai_routes, "get_location_context", lambda lid, cid: {"formatted": "LOCATION"})
    monkeypatch.setattr(ai_routes, "get_location_npcs", lambda lid, cid: {"count": 0})
    monkeypatch.setattr(ai_routes, "get_recent_messages",
                        lambda lid, cid, limit=0: {"messages": [{"id": 77, "role": "user", "content": "hi",
                                                                 "username": "bob"}]})
    monkeypatch.setattr(ai_routes, "get_campaign_rules", lambda cid: ("v5", "vampire"))
    import services.ai_roles as roles

    monkeypatch.setattr(roles, "storyteller_context_tokens", lambda: 8192)
    args = {}

    def fake_block(get_db, cid, lid, oldest, max_tokens, reply_lang=None):
        args.update(cid=cid, lid=lid, oldest=oldest, max_tokens=max_tokens, reply_lang=reply_lang)
        return block, 1

    monkeypatch.setattr(cm, "storyteller_block", fake_block)
    import services.language as language

    monkeypatch.setattr(language, "user_ui_language", lambda uid: None)
    assert ai_routes._storyteller_reply("efficient", "what now?", 3, 4, 7) == "ok"
    return seen["system"], args


def test_the_storyteller_prompt_carries_the_memory_after_the_campaign(ai_routes, monkeypatch):  # noqa: F811
    system, args = _prompt(ai_routes, monkeypatch, "MEMORY BLOCK")
    assert system.index("CAMPAIGN") < system.index("MEMORY BLOCK") < system.index("LOCATION")
    assert args["reply_lang"] == "en"
    assert args["oldest"] == 77 and 0 < args["max_tokens"] <= 8192 * ai_routes.CHRONICLE_BUDGET_SHARE


def test_no_memory_block_when_off(ai_routes, monkeypatch):  # noqa: F811
    system, _ = _prompt(ai_routes, monkeypatch, "")
    assert "CAMPAIGN\n\nLOCATION" in system


def test_ai_context_shows_the_memory(ai_routes, monkeypatch):  # noqa: F811
    from services import ai_slash_commands as sc

    monkeypatch.setattr(ai_routes, "get_campaign_context", lambda cid: "CAMPAIGN")
    monkeypatch.setattr(ai_routes, "get_location_context", lambda lid, cid: {"formatted": "LOCATION"})
    monkeypatch.setattr(ai_routes, "get_recent_messages",
                        lambda lid, cid, limit=0: {"messages": [{"id": 5}], "formatted": "RECENT"})
    monkeypatch.setattr(cm, "storyteller_block", lambda *a: ("MEMORY BLOCK", 2))
    res = sc.execute_context_command(1, 3, 4)
    assert "display_markdown" not in res and res["private_kind"] == "context"  # never saved to the room
    out = res["private_markdown"]
    assert "### Chronicle memory" in out and "MEMORY BLOCK" in out
    monkeypatch.setattr(cm, "storyteller_block", lambda *a: ("", 0))
    assert "(none: off, or nothing written yet)" in sc.execute_context_command(1, 3, 4)["private_markdown"]


def test_a_night_is_cut_not_replaced_by_shorter_lower_items():
    long_night = chapter(101, 4, 31, 40, "Basement")
    long_night["chapter"]["summary"] = ["word " * 400]
    block, _ = cm.build_block(mat(chapters=[long_night]), 101, None, 200)
    assert "Night 4 in Basement" in block and "[…]" in block
    assert "The locksmith is a ghoul." not in block  # nothing after the cut item


def test_switch_off_and_language_change_stick_after_the_ttl_without_forget(api):  # noqa: F811
    write(api)
    raw = api.raw
    now = [1000.0]
    clock = lambda: now[0]  # noqa: E731
    assert cm.material(Conn(raw).cursor(), 10, clock=clock)["memory"] is True
    # another worker turns it off: no forget() here
    raw.execute("UPDATE campaigns SET chronicle_settings = ? WHERE id = 10", (json.dumps({"memory": False}),))
    now[0] += 61
    assert cm.material(Conn(raw).cursor(), 10, clock=clock)["memory"] is False
    raw.execute("UPDATE campaigns SET chronicle_settings = ? WHERE id = 10", (json.dumps({"memory": True}),))
    now[0] += 61
    assert cm.material(Conn(raw).cursor(), 10, clock=clock)["lang"] == "el"
    raw.execute("UPDATE campaigns SET language = 'en' WHERE id = 10")
    now[0] += 61
    assert cm.material(Conn(raw).cursor(), 10, clock=clock)["lang"] == "en"


def test_a_stored_translation_is_used_for_the_reply_language_only_when_it_exists(api):  # noqa: F811
    write(api)
    raw = api.raw
    assert cm.material(Conn(raw).cursor(), 10, "en")["lang"] == "el"  # no translation stored: own language
    row = raw.execute("SELECT digest, source_hash FROM chronicle_digests WHERE kind = 'final' AND lang = 'el'").fetchone()
    d = json.loads(row[0])
    d["tldr"] = "The translated story so far."
    raw.execute("INSERT INTO chronicle_digests (campaign_id, kind, era, lang, digest, source_hash, translated_from) "
                "VALUES (10, 'final', 0, 'en', ?, ?, 'el')", (json.dumps(d), row[1]))
    cm.forget()
    m = cm.material(Conn(raw).cursor(), 10, "en")
    assert m["lang"] == "en" and m["digest"]["tldr"] == "The translated story so far."
    assert m["chapters"]  # the nights weren't translated: their own language
    assert cm.material(Conn(raw).cursor(), 10, "el")["lang"] == "el"
