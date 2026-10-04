from services.rules_edition import (
    CLASSIC,
    V5,
    edition_of,
    is_v5,
    normalize_rules_edition,
    rules_edition_label,
    storyteller_rules_brief,
    validate_rules_edition,
)


def test_normalize():
    assert normalize_rules_edition(None) == CLASSIC
    assert normalize_rules_edition("") == CLASSIC
    assert normalize_rules_edition("V5") == V5
    assert normalize_rules_edition(" classic ") == CLASSIC
    assert normalize_rules_edition("revised") == CLASSIC
    assert normalize_rules_edition("v20") is None
    assert normalize_rules_edition(None, default=None) is None


def test_edition_of_rows():
    assert edition_of(None) == CLASSIC
    assert edition_of({}) == CLASSIC
    assert edition_of({"rules_edition": None}) == CLASSIC
    assert edition_of({"rules_edition": "v5"}) == V5
    assert edition_of({"rules_edition": "garbage"}) == CLASSIC
    assert is_v5({"rules_edition": "v5"})
    assert is_v5("v5")
    assert not is_v5(None)


def test_validate():
    assert validate_rules_edition(None, "vampire") == (CLASSIC, None)
    assert validate_rules_edition("v5", "vampire") == (V5, None)
    assert validate_rules_edition("v5", "Vampire") == (V5, None)
    ed, err = validate_rules_edition("v5", "werewolf")
    assert ed is None and "vampire" in err
    ed, err = validate_rules_edition("v20", "vampire")
    assert ed is None and err
    assert validate_rules_edition("classic", "mage") == (CLASSIC, None)


def test_labels_and_briefs():
    assert "V5" in rules_edition_label("v5")
    assert "Revised" in rules_edition_label("classic")
    v5 = storyteller_rules_brief("v5", "vampire")
    assert "Hunger" in v5 and "Rouse" in v5
    classic = storyteller_rules_brief("classic", "vampire")
    assert "botch" in classic.lower() and "blood pool" in classic.lower()
    assert "blood pool" not in storyteller_rules_brief("classic", "werewolf").lower()
