import pytest

from routes.ui_language import UI_LANGUAGES, parse_ui_language


def test_valid_codes():
    assert UI_LANGUAGES == ("en", "el")
    assert parse_ui_language("en") == "en"
    assert parse_ui_language("el") == "el"
    assert parse_ui_language(" EL ") == "el"


def test_clear_choice():
    assert parse_ui_language(None) is None
    assert parse_ui_language("") is None
    assert parse_ui_language("   ") is None


@pytest.mark.parametrize("bad", ["de", "el-GR", "english", "gr", 1, True, ["el"], {"lang": "el"}])
def test_rejects_everything_else(bad):
    with pytest.raises(ValueError):
        parse_ui_language(bad)
