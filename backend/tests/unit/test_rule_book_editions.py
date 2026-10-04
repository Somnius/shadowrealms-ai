"""Rule book chunk edition tagging and the RAG where/fallback filters (pure parts)."""

from services.rules_edition import (
    BOOK_EDITIONS,
    rule_book_edition_allowed,
    rule_book_fallback_where,
    rule_book_where,
    rules_edition_for_book,
)


def test_rule_book_where():
    assert rule_book_where(0) == {"campaign_id": {"$in": [0]}}
    assert rule_book_where("7") == {"campaign_id": {"$in": [0, 7]}}
    assert rule_book_where(None) == {"campaign_id": {"$in": [0]}}
    assert rule_book_where(7, "v5") == {
        "$and": [{"campaign_id": {"$in": [0, 7]}}, {"rules_edition": "v5"}]
    }


def test_fallback_where_excludes_every_other_edition():
    w = rule_book_fallback_where(7, "classic")
    assert w["$and"][0] == {"campaign_id": {"$in": [0, 7]}}
    excluded = w["$and"][1]["rules_edition"]["$nin"]
    assert "v5" in excluded and "nwod" in excluded and "classic" not in excluded
    w = rule_book_fallback_where(7, "v5")
    excluded = w["$and"][1]["rules_edition"]["$nin"]
    assert set(excluded) == set(BOOK_EDITIONS) - {"v5"}


def test_edition_allowed_filter():
    assert rule_book_edition_allowed({"rules_edition": "classic"}, "classic")
    assert rule_book_edition_allowed({}, "classic")  # untagged legacy chunk
    assert rule_book_edition_allowed(None, "v5")
    assert not rule_book_edition_allowed({"rules_edition": "v5"}, "classic")
    assert not rule_book_edition_allowed({"rules_edition": "classic"}, "v5")
    assert not rule_book_edition_allowed({"rules_edition": "nwod"}, "classic")
    assert rule_book_edition_allowed({"rules_edition": "v5"}, None)


def test_edition_for_book():
    assert rules_edition_for_book("V5") == "v5"
    assert rules_edition_for_book("oWoD") == "classic"
    assert rules_edition_for_book("Classic World of Darkness") == "classic"
    assert rules_edition_for_book("nWoD") == "nwod"
    assert rules_edition_for_book("New World of Darkness") == "nwod"
    # folder decides when there is no category (the V5 corebook's file name has no "V5")
    assert rules_edition_for_book(
        None, "books/World_of_Darkness/V5/Vampire the Masquerade - Corebook.pdf"
    ) == "v5"
    assert rules_edition_for_book(
        None, "books/World_of_Darkness/Classic World of Darkness/Vampire/Vampire Revised.pdf"
    ) == "classic"
    assert rules_edition_for_book(None, None, "V5 Rules Errata 2.0") == "v5"
    assert rules_edition_for_book(None, None, "Vampire: The Masquerade 5th Edition") == "v5"
    assert rules_edition_for_book(None, None, "WOD - World Of Darkness (2nd ed)", "wod_2nd_ed") == "classic"
    assert rules_edition_for_book(None, None, "vampire_core", "Vampire: The Masquerade Core") == "classic"
    assert rules_edition_for_book() == "classic"
    # "v5" inside a longer token is not a match
    assert rules_edition_for_book(None, None, "dev5x notes") == "classic"
