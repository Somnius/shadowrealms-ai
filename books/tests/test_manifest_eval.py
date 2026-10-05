"""Manifest validation (incl. the real books/manifest.yaml) and the eval scoring."""
import os

import pytest
import yaml
from conftest import BOOKS, book

from rbimport import evaluate, manifest


def test_real_manifest_is_valid():
    with open(os.path.join(BOOKS, "manifest.yaml"), encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert manifest.validate(data) == []
    ids = [b["book_id"] for b in data["books"]]
    assert len(ids) == len(set(ids))
    by_id = {b["book_id"]: b for b in data["books"]}
    assert by_id["v5-corebook"]["precedence"] == 10 and by_id["v5-players-guide"]["precedence"] == 20
    assert manifest.parse_pages(by_id["v5-corebook"]["exclude"]) == [(431, 436)]
    assert all(b["line"] == "vampire" for b in data["books"] if b["edition"] == "v5")
    paths = {b["path"] for b in data["books"]}
    assert not paths & {x["path"] for x in data["excluded"]}


def test_validate_catches_problems():
    good = book()
    assert manifest.validate({"books": [good]}) == []
    bad = [dict(good, edition="v4"), dict(good, book_id="Bad Id", path="y"), dict(good, line="mummy", book_id="b2", path="z"),
           dict(good, official=False, book_id="b3", path="w"), dict(good, include="5-1", book_id="b4", path="v"),
           dict(good, edition="v5", line="werewolf", version="v5", book_id="b5", path="u"), dict(good, colour="red", book_id="b6", path="t")]
    errs = manifest.validate({"books": [good] + bad + [dict(good)]})
    text = "\n".join(errs)
    for needle in ("edition must be", "lowercase slug", "line must be", "only official", "bad page range",
                   "V5 books are Vampire only", "unknown field colour", "duplicate book_id"):
        assert needle in text


def test_page_list():
    assert manifest.page_list({"include": "1-10", "exclude": "3-4, 9"}, 8) == [1, 2, 5, 6, 7, 8]
    assert manifest.page_list({"include": "253-504"}, 504)[0] == 253
    with pytest.raises(manifest.ManifestError):
        manifest.parse_pages("a-b")


def test_eval_scoring_and_leaks():
    b5 = book(book_id="v5-x", edition="v5", version="v5")
    bc = book(book_id="cl-x", edition="classic", line="vampire")
    q5 = [{"book_id": "v5-x", "section": "S", "query": "Hunger", "style": "heading", "gold_pages_pdf": [10, 12]}]
    qc = [{"book_id": "cl-x", "section": "S", "query": "Blood", "style": "heading", "gold_pages_pdf": [5, 5]}]

    def fake(collection, text, k, where):
        if collection == "rule_books_v5":
            assert where is None
            return [{"book_id": "v5-other", "page_pdf": 11, "edition": "v5"},
                    {"book_id": "v5-x", "page_pdf": 11, "edition": "v5"}]
        assert where == {"line": {"$in": ["vampire", "all"]}}
        return [{"book_id": "cl-x", "page_pdf": 5, "edition": "classic", "line": "vampire"},
                {"book_id": "w", "page_pdf": 1, "edition": "v5", "line": "werewolf"}]

    rep = evaluate.run([b5, bc], {"v5-x": q5, "cl-x": qc}, fake, k=5)
    assert rep["per_book"]["v5-x"]["heading"]["hit@1"] == 0 and rep["per_book"]["v5-x"]["heading"]["mrr"] == 0.5
    assert rep["per_book"]["cl-x"]["heading"]["hit@1"] == 1
    assert rep["leaks"]["edition"] == 1 and rep["leaks"]["line"] == 1


def test_sample_queries_seeded():
    ext = {"sections": [{"id": i, "title": f"Topic {i}", "path": ["Ch", f"Topic {i}"], "leaf": True, "page_pdf": i,
                         "page_end_pdf": i + 1} for i in range(1, 60)] +
           [{"id": 99, "title": "Introduction", "path": ["Introduction"], "leaf": True, "page_pdf": 1, "page_end_pdf": 1}]}
    chunks = [{"metadata": {"heading_path": f"Ch › Topic {i}"}} for i in range(1, 60)] + \
             [{"metadata": {"heading_path": "Introduction"}}]
    a = evaluate.sample_queries(book(), ext, chunks, n=10, seed=1)
    b = evaluate.sample_queries(book(), ext, chunks, n=10, seed=1)
    assert a == b and len(a) == 20
    assert not any(q["query"] == "Introduction" for q in a)
    assert {q["style"] for q in a} == {"heading", "paraphrase"}
