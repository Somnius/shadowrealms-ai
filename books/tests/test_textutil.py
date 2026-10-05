from rbimport.textutil import (HyphenVocab, TokenCounter, clean_line, join_lines, label_to_int, letterspaced,
                               split_sentences)


def test_clean_line_keeps_typography():
    s = clean_line("  “It’s late” — she saidﬁ  ")
    assert s == "“It’s late” — she saidfi"


def test_dot_leaders_collapse():
    assert clean_line("Etiquette.......... Insight") == "Etiquette … Insight"
    assert clean_line("Wait... what") == "Wait... what"


def test_dehyphenate_split_word():
    assert join_lines(["This is impor-", "tant text."]) == "This is important text."


def test_dehyphenate_keeps_compound_seen_in_book():
    v = HyphenVocab()
    v.add("a blood-bound servant walks")
    v.add("another blood-bound thrall")
    assert join_lines(["the blood-", "bound ghoul"], v.keep_hyphen) == "the blood-bound ghoul"
    assert join_lines(["the dis-", "cipline"], v.keep_hyphen) == "the discipline"


def test_hyphen_before_capital_is_kept():
    assert join_lines(["Camarilla-", "Anarch war"]) == "Camarilla-Anarch war"


def test_em_dash_joins_without_space():
    assert join_lines(["the Beast—", "and then"]) == "the Beast—and then"


def test_split_sentences_abbreviations():
    s = split_sentences("Roll Wits + Awareness (see p. 121). Then e.g. add one. Mr. Smith waits. Done!")
    assert s == ["Roll Wits + Awareness (see p. 121).", "Then e.g. add one.", "Mr. Smith waits.", "Done!"]


def test_split_sentences_quotes():
    s = split_sentences("He said “Run.” Then she ran. 3 dice remain.")
    assert s == ["He said “Run.”", "Then she ran.", "3 dice remain."]


def test_letterspaced():
    assert letterspaced("C O R E B O O K")
    assert not letterspaced("A B testing works")


def test_labels():
    assert label_to_int("121") == 121
    assert label_to_int("xiv") == 14
    assert label_to_int("Errata 6") is None
    assert label_to_int("Coveri") is None


def test_token_estimate():
    c = TokenCounter("estimate")
    assert c.name == "estimate"
    assert c.count("one two three four") == 6
