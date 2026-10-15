"""Per-chronicle V5 creation settings (services/creation_settings.py)."""

import json

import pytest

from services.creation_settings import (
    DEFAULTS,
    book_allowed,
    creation_problems,
    entry_books,
    normalize_creation_settings,
    validate_creation_settings,
)
from services.request_validation import RequestValidationError


def test_defaults_for_empty_and_bad_rows():
    for raw in (None, "", "{}", "not json", "[1, 2]", 42, {}):
        assert normalize_creation_settings(raw) == DEFAULTS


def test_normalise_round_trip_from_json_text():
    s = {
        "v": 1,
        "allowed_clans": ["Brujah", " Hecata ", "Brujah", ""],
        "allowed_predators": ["Alleycat"],
        "allowed_ages": ["neonate", "elder"],
        "flaws_max_dots": 4,
        "fledgling_humanity_8": False,
        "saved_points": {"advantage_dots_cap": 3, "allow_specialty": False},
        "st_mode": "ai",
        "house_rules": "  No Malkavians in Elysium.  ",
    }
    out = normalize_creation_settings(json.dumps(s))
    assert out["allowed_clans"] == ["Brujah", "Hecata"]
    assert out["allowed_ages"] == ["neonate"]
    assert out["flaws_max_dots"] == 4
    assert out["fledgling_humanity_8"] is False
    assert out["saved_points"] == {"advantage_dots_cap": 3, "allow_specialty": False}
    assert out["st_mode"] == "ai"
    assert out["house_rules"] == "No Malkavians in Elysium."
    assert out["allowed_books"] is None


def test_normalise_drops_bad_values():
    out = normalize_creation_settings(
        {"flaws_max_dots": True, "st_mode": "god", "allowed_ages": ["elder"], "saved_points": "x"}
    )
    assert out["flaws_max_dots"] is None
    assert out["st_mode"] == "human"
    assert out["allowed_ages"] is None
    assert out["saved_points"] == DEFAULTS["saved_points"]


def test_validate_accepts_partial_and_fills_defaults():
    out = validate_creation_settings({"allowed_clans": ["Ventrue"]})
    assert out["allowed_clans"] == ["Ventrue"]
    assert out["st_mode"] == "human"


@pytest.mark.parametrize(
    "bad",
    [
        [],
        {"wat": 1},
        {"allowed_clans": []},
        {"allowed_clans": "Brujah"},
        {"allowed_clans": [""]},
        {"allowed_clans": ["x" * 61]},
        {"allowed_ages": ["elder"]},
        {"flaws_max_dots": 1},
        {"flaws_max_dots": True},
        {"fledgling_humanity_8": "yes"},
        {"saved_points": {"advantage_dots_cap": 21}},
        {"saved_points": {"other": 1}},
        {"saved_points": {"allow_specialty": 1}},
        {"st_mode": "god"},
        {"house_rules": "x" * 2001},
        {"v": 2},
    ],
)
def test_validate_refuses(bad):
    with pytest.raises(RequestValidationError):
        validate_creation_settings(bad)


def test_problems_none_when_all_allowed():
    meta = {"clan": "Brujah", "predator_type": "Alleycat", "age": "neonate", "flaws": []}
    assert creation_problems(None, meta) == []
    assert creation_problems("{}", meta) == []


def test_problems_clan_predator_age():
    settings = {
        "allowed_clans": ["Ventrue", "Toreador"],
        "allowed_predators": ["siren"],
        "allowed_ages": ["neonate"],
    }
    meta = {"clan": "Brujah", "predator_type": "Alleycat", "age": "ancilla"}
    problems = creation_problems(settings, meta)
    assert len(problems) == 3
    ok = {"clan": "toreador", "predator_type": "Siren", "age": "neonate"}
    assert creation_problems(settings, ok) == []


def test_problems_thin_blood_without_predator():
    settings = {"allowed_predators": ["Siren"]}
    assert creation_problems(settings, {"clan": "Thin-blood", "predator_type": None}) == []


def test_flaw_cap_counts_own_flaws_only():
    settings = {"flaws_max_dots": 3}
    meta = {
        "flaws": [
            {"name": "Prey Exclusion", "dots": 1, "kind": "predator"},
            {"name": "Obvious Predator", "dots": 2, "kind": "predator"},
            {"name": "Dark Secret", "dots": 2, "kind": "flaw"},
            {"name": "Enemy", "dots": 1, "kind": "flaw"},
        ]
    }
    assert creation_problems(settings, meta) == []
    meta["flaws"].append({"name": "Shunned", "dots": 1, "kind": "flaw"})
    assert len(creation_problems(settings, meta)) == 1


def test_flaw_cap_under_4_needs_ancillae_left_out():
    with pytest.raises(RequestValidationError):
        validate_creation_settings({"flaws_max_dots": 3})
    with pytest.raises(RequestValidationError):
        validate_creation_settings({"flaws_max_dots": 2, "allowed_ages": ["neonate", "ancilla"]})
    out = validate_creation_settings({"flaws_max_dots": 3, "allowed_ages": ["childer", "neonate"]})
    assert out["flaws_max_dots"] == 3
    assert validate_creation_settings({"flaws_max_dots": 4})["flaws_max_dots"] == 4


def test_age_problem_reads_as_words():
    problems = creation_problems({"allowed_ages": ["neonate"]}, {"age": "childer"})
    assert problems == ["The Storyteller doesn't allow childe / fledgling characters in this chronicle."]
    # an unknown age stored by an old sheet doesn't crash
    assert creation_problems({"allowed_ages": ["neonate"]}, {"age": "elder"})


# ---------- allowed books (Forge v2) ----------

def test_entry_books_own_book_first_then_also_in():
    entry = {"book": "v5-players-guide", "also_in": [{"book": "v5-companion", "page": 6}, "v5-cults", {"page": 3}, None, "v5-companion"]}
    assert entry_books(entry) == ["v5-players-guide", "v5-companion", "v5-cults"]
    for bad in (None, "x", [], {}, {"book": 3, "also_in": "v5-companion"}, {"book": " "}):
        assert entry_books(bad) == []


def test_book_allowed_by_its_own_book_or_one_it_is_also_printed_in():
    ravnos = {"name": "Ravnos", "book": "v5-players-guide", "also_in": [{"book": "v5-companion", "page": 6}]}

    def books(lst):
        return normalize_creation_settings({"allowed_books": lst})

    assert book_allowed(normalize_creation_settings(None), ravnos)  # null: every book
    assert book_allowed(books(["v5-players-guide"]), ravnos)
    assert book_allowed(books(["v5-corebook", "v5-companion"]), ravnos)  # through also_in
    assert not book_allowed(books(["v5-corebook"]), ravnos)
    # an entry without a book (the v5.json fallback) or no entry: nothing to check
    assert book_allowed(books(["v5-corebook"]), {"name": "Brujah"})
    assert book_allowed(books(["v5-corebook"]), None)
    # any book id, also a supplement the catalog adds later
    assert book_allowed(books(["v5-in-memoriam"]), {"book": "v5-in-memoriam"})


def test_allowed_books_are_stored_as_sent():
    out = validate_creation_settings({"allowed_books": ["v5-corebook", "v5-companion"]})
    assert out["allowed_books"] == ["v5-corebook", "v5-companion"]
    assert validate_creation_settings({"allowed_books": None})["allowed_books"] is None
    with pytest.raises(RequestValidationError):
        validate_creation_settings({"allowed_books": []})  # at least one (null allows all)
