"""Reply-language detection: Greek letters ratio; Latin text is English only when clearly so."""

from services import language as lang


def test_greek_text_is_el():
    assert lang.detect_language("Η Έλενα κοιτάζει τον Πρίγκιπα και ψιθυρίζει.") == "el"
    assert lang.detect_language("Ρίχνω 5 ζάρια για Dexterity + Brawl") == "el"  # mostly Greek


def test_english_is_en_and_greeklish_is_undecided():
    assert lang.detect_language("Elena looks at the Prince and whispers.") == "en"
    assert lang.detect_language("I sneak past the guards") == "en"
    assert lang.detect_language("Rixnw 5 zaria gia to Dex") is None
    assert lang.detect_language("Kanw Dominate sto ghoul na mou pei pou koimatai o Prince") is None
    assert lang.detect_language("Ksekinaw na trexw pros ti varka, ti roll kanw?") is None
    assert lang.detect_language("Dominate!") is None  # one name: can't tell


def test_greeklish_follows_ui_language(monkeypatch):
    monkeypatch.setattr(lang, "user_ui_language", lambda uid: {7: "el", 8: "en"}.get(uid))
    assert lang.resolve_reply_language("Rixnw 5 zaria gia to Dex", 7) == "el"
    assert lang.resolve_reply_language("Rixnw 5 zaria gia to Dex", 8) == "en"
    assert lang.resolve_reply_language("Rixnw 5 zaria gia to Dex", None) == "en"
    assert lang.resolve_reply_language("What do I roll to sneak?", 7) == "en"


def test_too_short_is_undecided():
    assert lang.detect_language("ok") is None
    assert lang.detect_language("5d10 +1") is None
    assert lang.detect_language("") is None
    assert lang.detect_language("να") == "el"  # any Greek letters decide even when short


def test_mixed_threshold():
    # 3 Greek letters of 13 (~0.23) -> English; mostly Greek -> Greek
    assert lang.detect_language("Hello there αβγ") == "en"
    assert lang.greek_ratio("αβγδ abc") > 0.5


def test_resolve_falls_back_to_ui_language(monkeypatch):
    monkeypatch.setattr(lang, "user_ui_language", lambda uid: "el" if uid == 7 else None)
    assert lang.resolve_reply_language("ok", 7) == "el"
    assert lang.resolve_reply_language("ok", 8) == "en"
    assert lang.resolve_reply_language("I open the door slowly", 7) == "en"  # message wins


def test_instruction_mentions_language():
    assert "Greek" in lang.reply_language_instruction("el")
    assert "English" in lang.reply_language_instruction("en")
    assert lang.normalize_language("EL-gr") == "el"
    assert lang.normalize_language("fr") is None


def test_non_storyteller_instruction_keeps_format():
    el = lang.reply_language_instruction("el", storyteller=False)
    assert "Greek" in el and "format" in el
    assert "English" in lang.reply_language_instruction("en", storyteller=False)
