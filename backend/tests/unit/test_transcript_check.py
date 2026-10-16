"""Voice phase 6: transcript check (pure parts; Krikri faked)."""
import json

from services import transcript_check as tc

WORDS = "Ο Νίκος του λέει είσαι μεγάλη βλυχ άρα ρε μαλάκα.".split()
PROBS = [1, 1, 1, 1, 1, 1, 0.45, 0.5, 0.97, 0.9]


def fake(answer):
    def gen(messages):
        gen.messages = messages
        return {"text": answer}
    return gen


def test_split_word_joined_and_marked():
    segs = tc.check(WORDS, [{"i": 6, "p_laya": 0.8}], "el", ["Νίκος"], fake('{"1": "βλαχάρα"}'), probs=PROBS)
    assert tc.text_of(segs) == "Ο Νίκος του λέει είσαι μεγάλη βλαχάρα ρε μαλάκα."
    assert {"t": "βλαχάρα", "raw": "βλυχ άρα"} in segs


def test_only_flagged_spans_are_marked_for_krikri():
    gen = fake('{"1": "βλαχάρα"}')
    tc.check(WORDS, [{"i": 6, "p_laya": 0.8}, {"i": 9, "p_laya": 0.3}], "el", [], gen, probs=PROBS)
    line = gen.messages[-1]["content"]
    assert "[1: βλυχ άρα]" in line and "[2" not in line


def test_nothing_flagged_means_no_call_and_no_change():
    gen = fake('{"1": "x"}')
    assert tc.check(WORDS, [{"i": 6, "p_laya": 0.2}], "el", [], gen) is None
    assert not hasattr(gen, "messages")


def test_krikri_down_or_garbage_keeps_whisper_text():
    def down(_m):
        raise TimeoutError
    assert tc.check(WORDS, [{"i": 6, "p_laya": 0.9}], "el", [], down) is None
    assert tc.check(WORDS, [{"i": 6, "p_laya": 0.9}], "el", [], fake("sorry")) is None


def test_synonyms_rewrites_and_accent_only_changes_are_refused():
    w = "λέει σιγανά ο πρίγκιπας".split()
    s = [{"i": 1, "p_laya": 0.9}]
    assert tc.check(w, s, "el", [], fake('{"1": "ψιθυριστά"}')) is None   # not a mishearing
    assert tc.check(w, s, "el", [], fake('{"1": "σιγάνα"}')) is None      # accent only
    assert tc.check(w, s, "el", [], fake('{"1": "πολύ πολύ πιο σιγανά"}')) is None  # a rewrite


def test_punctuation_kept_and_swearing_untouched():
    w = "Αγαμώτο, ρε μαλάκα.".split()
    segs = tc.check(w, [{"i": 0, "p_laya": 0.9}], "el", [], fake('{"1": "Γαμώτο"}'))
    assert tc.text_of(segs) == "Γαμώτο, ρε μαλάκα."


def test_whisper_prompt_is_short_names_first():
    p = tc.whisper_prompt(["Νίκος", "Ελένη"] + [f"Name{i}" for i in range(200)], "el")
    assert p.startswith("Νίκος, Ελένη") and len(p) <= tc.PROMPT_MAX and "Καμαρίλα" in p


def test_checked_segments_round_trip():
    from services import voice_clips
    assert voice_clips.checked_segments({"transcript_checked": None}) is None
    assert voice_clips.checked_segments({"transcript_checked": "[]"}) == []
    segs = [{"t": "a"}, {"t": "b", "raw": "c"}]
    assert voice_clips.checked_segments({"transcript_checked": json.dumps(segs)}) == segs


def test_real_role_path_reaches_krikri(monkeypatch):
    """No fake generate: the check goes through ai_roles and its time budget really calls the model."""
    from services import ai_roles
    calls = []

    class Krikri:
        def generate(self, messages, params):
            calls.append(params)
            return '{"1": "βλαχάρα"}'

    monkeypatch.setitem(ai_roles.generate_for_role.__kwdefaults__, "builder", lambda name: Krikri())
    monkeypatch.setattr(ai_roles, "_load_failed_until", {})
    segs = tc.check(WORDS, [{"i": 6, "p_laya": 0.8}], "el", [], probs=PROBS)
    assert len(calls) == 1 and calls[0]["timeout"] <= tc.TIMEOUT_S
    assert tc.BUDGET_S > ai_roles.MIN_ATTEMPT_SEC
    assert tc.text_of(segs) == "Ο Νίκος του λέει είσαι μεγάλη βλαχάρα ρε μαλάκα."


def test_long_names_are_skipped():
    class Cur:
        def execute(self, sql, args):
            self.sql = sql

        def fetchall(self):
            return [{"name": "Dimitra"}, {"name": "x" * (tc.NAME_MAX + 1)}] if "characters" in self.sql else []

    assert tc.chronicle_names(Cur(), 1) == ["Dimitra"]


def test_numbered_pairs_survive_a_remark_inside_the_braces():
    answer = '{"1": "βλαχάρα", "βλυχ άρα" sounds like a misheard spelling of "βλαχάρα"} \n\n(Note: ...)'
    segs = tc.check(WORDS, [{"i": 6, "p_laya": 0.8}], "el", [], fake(answer), probs=PROBS)
    assert tc.text_of(segs) == "Ο Νίκος του λέει είσαι μεγάλη βλαχάρα ρε μαλάκα."
