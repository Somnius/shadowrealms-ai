import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import catalog, textprep  # noqa: E402
from app.cachekeys import tts_key  # noqa: E402
from app.limits import Refused, check_lang, check_probe, check_size, check_text  # noqa: E402


def test_markdown_stripped():
    t = textprep.normalise("**Bold** and *soft* [link](http://x) `code`\n# Head", "en")
    assert t == "Bold and soft link code\nHead"


def test_greek_numbers_and_question_mark():
    assert textprep.normalise("Έχεις 3 επιτυχίες?", "el") == "Έχεις τρία επιτυχίες;"
    assert textprep.greek_number(17) == "δεκαεπτά"
    assert textprep.greek_number(21) == "είκοσι ένα"
    assert textprep.greek_number(115) == "εκατόν δεκαπέντε"
    assert textprep.greek_number(200) == "διακόσια"
    assert textprep.greek_number(1005) == "χίλια πέντε"


def test_english_keeps_digits_and_question_mark():
    assert textprep.normalise("Roll 3 dice?", "en") == "Roll 3 dice?"


def test_split_parts():
    text = ("One sentence here. " * 200).strip()
    parts = textprep.split_parts(text, 100)
    assert all(len(p) <= 100 for p in parts)
    assert " ".join(parts) == text
    assert textprep.split_parts("x" * 250, 100) == ["x" * 100, "x" * 100, "x" * 50]


def test_cache_key_stable_and_distinct():
    a = tts_key("piper", "en_GB-alan-medium", "Hello", "24k")
    assert a == tts_key("piper", "en_GB-alan-medium", "Hello", "24k")
    assert a != tts_key("piper", "en_GB-alan-medium", "Hello.", "24k")
    assert a != tts_key("piper", "en_GB-cori-high", "Hello", "24k")
    assert a != tts_key("piper", "en_GB-alan-medium", "Hello", "16k")
    assert a.isalnum() and len(a) == 40


@pytest.mark.parametrize("lang,accent,gender,role,expect", [
    ("en", "us", "female", None, "en_US-lessac-medium"),
    ("en", "us", "male", None, "en_US-ryan-high"),
    ("en", "us", None, None, "en_US-lessac-medium"),
    ("en", "gb", "male", None, "en_GB-alan-medium"),
    ("en", "gb", "female", None, "en_GB-jenny_dioco-medium"),
    ("en", "gb", "neutral", None, "en_GB-cori-high"),
    ("en", None, "male", None, "en_US-ryan-high"),
    ("en", "xx", "male", None, "en_US-ryan-high"),
    ("el", None, "male", None, "el-kostas"),
    ("el", "gr", "female", None, "el-athina"),
    ("el", "gr", "neutral", None, "el-eleni"),
    ("el", "gr", "male", "narrator", "el-spyros"),
    ("en", "gb", "female", "narrator", "en_GB-alan-medium"),
])
def test_voice_mapping(lang, accent, gender, role, expect):
    assert catalog.resolve(lang, gender=gender, accent=accent, role=role) == expect


def test_greek_fallback_and_explicit_voice():
    assert catalog.resolve("el", gender="male", pocket_ok=False) == catalog.GREEK_FALLBACK
    assert catalog.resolve("en", voice="en_GB-cori-high") == "en_GB-cori-high"
    with pytest.raises(ValueError):
        catalog.resolve("en", voice="el-kostas")
    with pytest.raises(ValueError):
        catalog.resolve("fr")


def test_every_default_is_in_catalog():
    for table in catalog.DEFAULTS.values():
        assert set(table) == {"female", "male", "neutral", "narrator"}
        assert all(v in catalog.VOICES for v in table.values())


def _probe(fmt="ogg", codec="opus", dur="12.0", streams=None):
    return {"format": {"format_name": fmt, "duration": dur},
            "streams": streams if streams is not None else [{"codec_type": "audio", "codec_name": codec}]}


def test_limits():
    check_text("hi", 10)
    for bad in ("", "   ", "x" * 11):
        with pytest.raises(Refused):
            check_text(bad, 10)
    check_lang("el")
    with pytest.raises(Refused):
        check_lang("de")
    check_size(5, 10)
    for n in (0, 11):
        with pytest.raises(Refused):
            check_size(n, 10)


def test_probe_checks():
    assert check_probe(_probe(), 180) == 12.0
    assert check_probe(_probe(fmt="matroska,webm", dur=None), 180) is None
    cases = [_probe(dur="181"), _probe(dur="0.1"), _probe(fmt="avi"), _probe(codec="h264"),
             _probe(streams=[]), _probe(streams=[{"codec_type": "audio", "codec_name": "opus"},
                                                 {"codec_type": "video", "codec_name": "h264"}])]
    for p in cases:
        with pytest.raises(Refused):
            check_probe(p, 180)
