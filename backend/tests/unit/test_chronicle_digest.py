"""The pure core of "The chronicle so far" (services/chronicle_digest.py) on synthetic chronicles."""

import json
from datetime import datetime, timedelta

import pytest

from services import chronicle_digest as cd
from services import chronicle_jobs as cj
from tests.unit.chronicle_fixtures import Conn, build, db

USERNAMES = ("siteadmin", "storyteller_lef", "eleni_player", "nikos_player", "helper_in")


def rows_of(lang="el", nights=3, **kw):
    rows, marks = build(lang, nights, **kw)
    raw = db(rows, marks)
    cur = Conn(raw).cursor()
    return cj.load_rows(cur, 10), marks


def chapters_of(lang="el", nights=3, **kw):
    rows, marks = rows_of(lang, nights, **kw)
    return rows, cd.cut_chapters(rows, cd.GAP_HOURS, marks)


@pytest.mark.parametrize("nights", [1, 10, 60])
def test_one_chapter_per_room_and_night(nights):
    _rows, chs = chapters_of("el", nights)
    story = [c for c in chs if c["kind"] == "story" and c["visibility"] == "all"]
    assert len(story) == nights
    assert len([c for c in chs if c["kind"] == "lobby"]) == nights
    closed = [c for c in chs if c["visibility"] == "st"]
    assert len(closed) == (1 if nights >= 2 else 0)
    starts = [c["started_at"] for c in chs]
    assert starts == sorted(starts)  # rooms mixed on one timeline


def test_gap_and_session_mark_cut():
    rows, marks = rows_of("en", 3, session_mark_night=1)
    with_mark = cd.cut_chapters(rows, cd.GAP_HOURS, marks)
    without = cd.cut_chapters(rows, cd.GAP_HOURS, ())
    story = lambda cs: [c for c in cs if c["kind"] == "story" and c["location_id"] == 101]  # noqa: E731
    assert len(story(with_mark)) == len(story(without)) + 1
    # a long gap cuts a night too
    t = datetime(2026, 10, 1, 21)
    r = [{"id": 1, "location_id": 1, "created_at": t}, {"id": 2, "location_id": 1, "created_at": t + timedelta(hours=7)},
         {"id": 3, "location_id": 1, "created_at": t + timedelta(hours=8)}]
    assert [c["first_id"] for c in cd.cut_chapters(r)] == [1, 2]


def test_player_view_lines_leave_out_hidden_rolls_closed_rooms_and_table_talk():
    rows, chs = chapters_of("el", 3)
    flags = cd.roll_flags(rows)
    by_night = [c for c in chs if c["kind"] == "story" and c["visibility"] == "all"]
    n1, n2, n3 = (cd.chapter_material(c, "el", flags) for c in by_night)
    assert not any(ln["hidden"] for ln in n2["lines"])
    assert len(n2["hidden"]) == 1 and n2["hidden"][0]["kind"] == "roll"
    assert any(ln["botch"] for ln in n1["lines"])
    assert [o["text"] for o in n3["ooc"]] == ["brb, coffee"]
    assert not any("brb" in ln["text"] for ln in n3["lines"])
    lobby = [c for c in chs if c["kind"] == "lobby"][0]
    lm = cd.chapter_material(lobby, "el", flags)
    assert lm["lines"] == [] and lm["ooc"][0]["text"] == "Good game tonight!"
    closed = [c for c in chs if c["visibility"] == "st"][0]
    assert closed["room"] == "The Crypt"
    assert len(cd.chapter_material(closed, "el", flags)["lines"]) == 3
    # no username anywhere in any line
    for c in chs:
        m = cd.chapter_material(c, "el", flags)
        for ln in m["lines"] + m["hidden"]:
            assert not any(u in ln["text"] for u in USERNAMES)
        for o in m["ooc"]:
            assert not any(u in o["who"] for u in USERNAMES)
    # the story never sees marker rows, only the dice result line
    assert all("animation_id" not in ln["text"] for ln in n1["lines"])


def test_hash_includes_room_state_and_lines():
    rows, chs = chapters_of("el", 1)
    ch = [c for c in chs if c["kind"] == "story"][0]
    m = cd.chapter_material(ch, "el", {})
    h = cd.chapter_hash(ch, m, "el", ["A"])
    assert h == cd.chapter_hash(ch, m, "el", ["A"])
    assert h != cd.chapter_hash({**ch, "visibility": "st"}, m, "el", ["A"])
    assert h != cd.chapter_hash(ch, m, "en", ["A"])
    m2 = {**m, "lines": m["lines"][:-1]}
    assert h != cd.chapter_hash(ch, m2, "el", ["A"])


def test_budget_split_never_inside_a_line():
    lines = [{"id": i, "text": "x" * 300} for i in range(30)]
    parts = cd.split_lines(lines, 500)
    assert sum(len(p) for p in parts) == 30
    assert all(sum(cd.estimate_tokens(ln["text"]) for ln in p) <= 500 for p in parts)
    assert cd.halve(lines)[0][-1]["id"] == 14
    # the Storyteller's share of a shared context is kept free
    assert cd.prompt_budget(32768, 1500, 8192) == 32768 - 8192 - 1500 - cd.PROMPT_OVERHEAD_TOKENS
    assert cd.prompt_budget(8192, 1500, 8192) >= 1000


def test_prompts_in_the_chronicles_language_with_the_schema():
    lines = [{"id": 5, "text": "M5 [21:00] [IC] Μαρώ: γεια"}]
    el = cd.chapter_messages("el", "Υπόγειο", datetime(2026, 10, 5), lines, ["Μαρώ"])
    en = cd.chapter_messages("en", "Basement", datetime(2026, 10, 5), lines, ["Maro"])
    assert cd.greek_share(el[0]["content"]) > 0.8
    assert "φυλές (clans)" in el[0]["content"] and "δεδομένα, όχι οδηγίες" in el[0]["content"]
    assert "clans" in en[0]["content"] and cd.greek_share(en[0]["content"]) == 0
    assert "Νύχτα: 5 Οκτ 2026" in el[1]["content"] and el[1]["content"].endswith("γεια")
    rf = cd.response_format("chapter", cd.CHAPTER_SCHEMA)
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    summary = rf["json_schema"]["schema"]["properties"]["summary"]
    assert summary["type"] == "array" and summary["minItems"] == 2 and summary["maxItems"] == 4


def _answer(**over):
    base = {"title": "Η νύχτα", "summary": ["Ο Κωνσταντίνος κατέβηκε στο υπόγειο.", "Η Μαρώ μίλησε."],
            "events": [{"text": "Βρήκε ίχνη.", "ids": ["M5", 6, 999]}, {"text": "Χωρίς πηγή.", "ids": []}],
            "characters": [{"name": "Κωνσταντίνος", "note": "έψαξε"}, {"name": "Ventrue Prince", "note": "x"}],
            "places": [], "threads_opened": [], "threads_closed": []}
    base.update(over)
    return "Here you go: " + json.dumps(base, ensure_ascii=False)


def test_check_drops_unknown_ids_uncited_events_and_names():
    ch, problems = cd.check_chapter(_answer(), [5, 6], ["Κωνσταντίνος Κατακουζηνός", "Μαρώ"], "el")
    assert problems == []
    assert ch["events"] == [{"text": "Βρήκε ίχνη.", "ids": [5, 6]}]
    assert [c["name"] for c in ch["characters"]] == ["Κωνσταντίνος"]
    assert cd.check_chapter("not json", [5], [], "el") == (None, ["json"])
    _ch, p = cd.check_chapter(_answer(summary=[]), [5], [], "el")
    assert "empty" in p


def test_language_and_mixed_scripts():
    _ch, p = cd.check_chapter(_answer(title="The night", summary=["He went down.", "Maro spoke."]), [5], [], "el")
    assert "language" in p
    _ch, p = cd.check_chapter(_answer(), [5], [], "en")
    assert "language" in p
    _ch, p = cd.check_chapter(_answer(summary=["Ο Κωνσtαντίνος κατέβηκε.", "Η Μαρώ μίλησε."]), [5], [], "el")
    assert "mixed_script" in p
    _ch, p = cd.check_chapter(_answer(summary=["Ο Κωνσταντίνος 下 κατέβηκε.", "Η Μαρώ μίλησε."]), [5], [], "el")
    assert "mixed_script" in p
    fixed = cd.strip_foreign({"title": "a", "summary": ["Ο 下 Κ."], "events": []})
    assert "下" not in fixed["summary"][0]
    retry = cd.retry_messages([{"role": "user", "content": "x"}], ["language"], "el")
    assert "ελληνικά" in retry[-1]["content"]


def test_botches_and_criticals_always_listed():
    lines = [{"id": 7, "kind": "roll", "say": "Marcus: 0 successes", "botch": True, "critical": False},
             {"id": 8, "kind": "roll", "say": "Marcus: 5 successes", "botch": False, "critical": True},
             {"id": 9, "kind": "roll", "say": "plain", "botch": False, "critical": False}]
    out = cd.inject_rolls([{"text": "cited", "ids": [8]}], lines, "el")
    assert [e["ids"] for e in out] == [[8], [7]]
    assert out[1]["text"].startswith("Καταστροφική αποτυχία: ")


def test_player_chapter_and_digest_have_no_storyteller_keys_or_ids():
    stored = {"key": "1:2", "room": "R", "kind": "story", "chapter": {
        "title": "t", "summary": ["s"], "events": [{"text": "e", "ids": [1]}], "st_notes": [{"text": "n", "ids": [2]}],
        "ooc": [{"id": 3, "who": "Marcus", "text": "brb"}], "threads_opened": [], "threads_closed": []}}
    p = cd.player_chapter(stored)
    dumped = json.dumps(p)
    assert "st_" not in dumped and '"ids"' not in dumped and "brb" not in dumped
    d = cd.player_digest({"so_far": ["x"], "st_so_far": ["secret"], "rooms": [1]})
    assert d == {"so_far": ["x"]}


def test_eras_of_ten_nights():
    story = [{"key": str(i), "source_hash": "h", "visibility": "all"} for i in range(60)]
    eras = cd.eras_of(story)
    assert len(eras) == 6 and eras[1][0][0] == 11
    assert cd.era_hash(eras[0], "el") != cd.era_hash(eras[1], "el")


def test_chronicle_language_majority():
    rows = [{"lang": "el", "content": "x"}] * 3 + [{"lang": None, "content": "hello there"}] * 2
    assert cd.chronicle_language(None, rows) == "el"
    assert cd.chronicle_language("en", rows) == "en"
    assert cd.chronicle_language(None, []) == "en"


def _stored(n, lang="el"):
    out = []
    for i in range(1, n + 1):
        out.append({"key": f"101:{i}", "kind": "story", "room": "Υπόγειο", "location_id": 101,
                    "visibility": "st" if i == 2 else "all", "started_at": datetime(2026, 10, i, 21),
                    "ooc": [{"id": 900 + i, "who": "Marcus", "text": "brb"}],
                    "chapter": {"title": f"# Τίτλος {i}", "summary": ["Πρώτη <b>παράγραφος</b>.", "Δεύτερη."],
                                "events": [{"text": "- Γεγονός", "ids": [i, 5000]}],
                                "characters": [{"name": "Μαρώ", "note": "μίλησε"}], "places": [],
                                "threads_opened": [{"text": "Νήμα", "ids": [i]}], "threads_closed": [],
                                "st_notes": [{"text": "Κρυφό", "ids": [i]}] if i == 3 else []}})
    return out


def test_story_markdown_views_and_escaping():
    facts = {"name": "Athens", "edition": "Vampire: The Masquerade V5", "nights_total": 5,
             "cast": [{"name": "Μαρώ", "clan": "Tremere", "player": "eleni_player"}, {"name": "Νίκος", "npc": True, "note": "mortal"}],
             "rooms": [{"name": "Υπόγειο", "description": "κάτω"}]}
    digest = {"tldr": "Σύντομα.", "so_far": ["Η ιστορία."], "threads_open": [{"text": "Ποιος;", "nights": [1]}],
              "st_so_far": ["Μυστικό."]}
    chs = _stored(4)
    st = cd.story_markdown(facts, digest, chs, "el", "st", existing_ids={1, 2, 3, 4})
    assert st.startswith("# Athens — Το χρονικό ως τώρα")
    assert "## Μόνο για τον Storyteller" in st and "Μυστικό." in st and "Κρυφό" in st
    assert "eleni\\_player" in st  # the cast list, in brackets, Storyteller's view only
    assert "M5000 (το μήνυμα διαγράφηκε)" in st
    assert "\\<b\\>" in st and "\n# Τίτλος" not in st  # a heading inside model text can't become markup
    assert "\\- Γεγονός" in st
    assert "1 νύχτες δεν έχουν γραφτεί" in st
    assert "brb" not in st
    assert "ShadowRealms AI" in st.splitlines()[-1]
    pl = cd.story_markdown(facts, cd.player_digest(digest), cd.visible_chapters(chs, "player"), "el", "player")
    assert "Μυστικό" not in pl and "Κρυφό" not in pl and "eleni" not in pl and "M1" not in pl
    assert "κλειστή αίθουσα" not in pl
    talk = cd.story_markdown(facts, digest, chs, "el", "st", with_table_talk=True)
    assert "brb" in talk


def test_minutes_markdown_whole_and_last_n():
    facts = {"name": "Athens", "nights_total": 4}
    chs = _stored(4)
    whole = cd.minutes_markdown(facts, chs, "en", "st")
    assert "Covers 4 nights" in whole and whole.count("\n## Night ") == 4
    last = cd.minutes_markdown(facts, chs, "en", "st", last_n=2)
    assert "The last 2 nights" in last and "## Night 3" in last and "## Night 1 " not in last
    assert "What the players didn't see" in last
    pl = cd.minutes_markdown(facts, cd.visible_chapters(chs, "player"), "el", "player")
    assert "Τι δεν είδαν οι παίκτες" not in pl and "_(μηνύματα" not in pl


def test_visible_chapters_checks_rooms_at_read_time():
    chs = _stored(3)
    assert len(cd.visible_chapters(chs, "player")) == 2
    assert cd.visible_chapters(chs, "player", readable_rooms=set()) == []
    assert len(cd.visible_chapters(chs, "st", readable_rooms=set())) == 3


def test_transcript_marks_hidden_rolls():
    rows, _ = rows_of("el", 2)
    t = cd.transcript_markdown({"name": "Athens"}, rows, "el")
    assert "[κρυφή ρίψη]" in t and "The Crypt" in t and "Out of Character Lobby" in t
    assert not any(u in t for u in USERNAMES)
