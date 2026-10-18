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


def cur(api):
    return Conn(api.raw).cursor()


def test_prompt_has_the_name_clan_story_and_nights(api):
    write(api)
    api.raw.execute("UPDATE characters SET wod_meta = '{\"clan\": \"Tremere\", \"background\": \"SECRET PAST\"}' WHERE id = 20")
    fake = Fake(GREEK_DEATH)
    text, generated = dw.write(cur(api), 20, "horrible", generate=fake)
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
    assert dw.write(cur(api), 20, "soft", generate=fake) == (dw.FALLBACK["el"]["soft"], False)


def test_missing_character_and_english_fallback(api):
    assert dw.write(cur(api), 999, "mid", generate=Fake("x")) == (dw.FALLBACK["en"]["mid"], False)
    api.raw.execute("UPDATE campaigns SET language = 'en' WHERE id = 10")
    assert dw.write(cur(api), 21, "mid", generate=Fake(exc=TimeoutError())) == (dw.FALLBACK["en"]["mid"], False)
    assert set(dw.FALLBACK["el"]) == set(dw.FALLBACK["en"]) == set(dw.DEATH_TYPES)


def _src(name):
    from pathlib import Path
    return (Path(__file__).resolve().parents[2] / "routes" / name).read_text(encoding="utf-8")


def test_kill_route_stores_it_and_says_whether_it_was_generated():
    src = _src("admin.py")
    kill = src[src.index("def kill_character"):src.index("@bp.route('/moderation-log'")]
    assert "death_writeup.write(" in kill and "'generated': generated" in kill and "TODO" not in kill


def test_create_campaign_defaults_to_the_creators_language():
    src = _src("campaigns.py")
    create = src[src.index("def create_campaign"):src.index("INSERT INTO campaigns")]
    assert "creator_language(cursor, user_id)" in create


def test_creator_language():
    from services.chronicle_digest import creator_language

    class C:
        def __init__(self, row=None, exc=None):
            self.row, self.exc = row, exc

        def execute(self, *a):
            if self.exc:
                raise self.exc

        def fetchone(self):
            return self.row

    assert creator_language(C({"ui_language": "EL "}), 1) == "el"
    assert creator_language(C({"ui_language": "fr"}), 1) is None
    assert creator_language(C(None), 1) is None
    assert creator_language(C(exc=RuntimeError()), 1) is None
