"""Import flow without Chroma or LM Studio: state/Chroma checks, failures, cache validity, CLI guards,
the hand-written question file."""
import json
import os

import pytest
from conftest import BOOKS, book

import import_books
from rbimport import evaluate, manifest, pipeline
from rbimport.chunker import chunk_book
from rbimport.store import ImportFailed, upsert_book
from rbimport.textutil import TokenCounter, join_lines


class FakeCol:
    def __init__(self, store, fail_after=None):
        self.store, self.fail_after = store, fail_after

    def upsert(self, ids, documents, metadatas):
        if self.fail_after is not None and len(self.store.ids) >= self.fail_after:
            raise ConnectionError("LM Studio embeddings unreachable")
        self.store.ids.update(ids)


class FakeStore:
    def __init__(self, fail_after=None, down=False):
        self.ids, self.down, self.fail_after = set(), down, fail_after

    def collection(self, name):
        if self.down:
            raise ConnectionError("Could not connect to a Chroma server")
        return FakeCol(self, self.fail_after)

    def count_book(self, name, book_id, campaign_id=0):
        return len(self.ids)

    def delete_book(self, name, book_id, campaign_id=0):
        n = len(self.ids)
        self.ids.clear()
        return n


def _res(n=5):
    chunks = [{"id": f"test-book:{i:05d}", "document": f"d{i}", "metadata": {"content_sha": str(i)}} for i in range(n)]
    return {"chunks": chunks, "chunks_sha": "abc", "file_sha256": "f"}


def test_done_in_state_but_missing_in_chroma_is_reimported(tmp_path):
    state = pipeline.State(str(tmp_path / "state.json"))
    st = FakeStore()
    upsert_book(st, state, book(), _res(), batch=2, pace_ms=0, log=lambda m: None)
    assert state.entry("test-book")["status"] == "done" and len(st.ids) == 5
    st.ids.clear()   # e.g. the backend's admin DELETE
    logs = []
    upsert_book(st, state, book(), _res(), batch=2, pace_ms=0, log=logs.append)
    assert len(st.ids) == 5 and any("holds 0 of 5" in m for m in logs)
    logs.clear()
    upsert_book(st, state, book(), _res(), batch=2, pace_ms=0, log=logs.append)
    assert any("already imported" in m for m in logs)


def test_failures_leave_state_error_or_partial(tmp_path):
    state = pipeline.State(str(tmp_path / "state.json"))
    with pytest.raises(ImportFailed):
        upsert_book(FakeStore(down=True), state, book(), _res(), batch=2, pace_ms=0, log=lambda m: None)
    assert state.entry("test-book").get("status") is None   # never marked running
    with pytest.raises(ImportFailed, match="stopped at 2/5"):
        upsert_book(FakeStore(fail_after=2), state, book(), _res(), batch=2, pace_ms=0, log=lambda m: None)
    saved = json.load(open(tmp_path / "state.json"))["books"]["test-book"]
    assert saved["status"] == "partial" and saved["done"] == 2 and "unreachable" in saved["error"]
    with pytest.raises(ImportFailed):
        upsert_book(FakeStore(fail_after=0), pipeline.State(str(tmp_path / "s2.json")), book(), _res(), batch=2,
                    pace_ms=0, log=lambda m: None)
    assert json.load(open(tmp_path / "s2.json"))["books"]["test-book"]["status"] == "error"


def test_tokenizer_fallback_has_a_reason(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    monkeypatch.delenv("BGE_M3_TOKENIZER", raising=False)
    c = TokenCounter("auto")
    assert c.name == "estimate" and "not found" in c.fallback
    assert TokenCounter("estimate").fallback is None


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(data, fh)


def test_chunk_cache_validity_counter_and_dedup(tmp_path):
    paths = pipeline.Paths(str(tmp_path), str(tmp_path / "data"))
    core, supp = book(book_id="core", precedence=10), book(book_id="supp", precedence=40)
    for b in (core, supp):
        _write(paths.extract_file(b), {"key": "k-" + b["book_id"]})
    _write(paths.chunks_file(core), {"extract_key": "k-core", "chunker_version": pipeline.chunker.CHUNKER_VERSION,
                                     "counter": "bge-m3", "chunks_sha": "core-v1", "dedup_key": pipeline.dedup_key({})})
    _write(paths.chunks_file(supp), {"extract_key": "k-supp", "chunker_version": pipeline.chunker.CHUNKER_VERSION,
                                     "counter": "bge-m3", "chunks_sha": "s", "dedup_key": pipeline.dedup_key({"core": "core-v1"})})
    books = [core, supp]
    assert pipeline.load_chunks(supp, paths, counter_name="bge-m3", all_books=books) is not None
    assert pipeline.load_chunks(supp, paths, counter_name="estimate", all_books=books) is None
    # the corebook was chunked again with different results: the supplement's de-dup is stale
    d = json.load(open(paths.chunks_file(core)))
    d["chunks_sha"] = "core-v2"
    _write(paths.chunks_file(core), d)
    assert pipeline.load_chunks(supp, paths, counter_name="bge-m3", all_books=books) is None
    assert pipeline.load_chunks(core, paths, counter_name="bge-m3", all_books=books) is not None


def test_lore_kinds_and_document_prefix():
    ext = {"sections": [], "blocks": [
        {"section": -1, "page_pdf": 1, "page": 1, "kind": k, "text": f"Some {k} text here.", "runin": None,
         "headline": False, "small": False} for k in ("body", "sidebar", "fiction", "example")]}
    res = chunk_book(ext, book(kind="lore"), TokenCounter("estimate"))
    assert {c["metadata"]["kind"] for c in res["chunks"]} == {"lore"}
    for c in res["chunks"]:
        assert c["metadata"]["heading_path"] == ""
        assert c["document"].startswith("Test Book › \n\n")   # backend rule_book_text strips "Title › "


def test_drop_caps():
    assert join_lines(["V", "ampires walk the night."]) == "Vampires walk the night."
    assert join_lines(["T he night is long."]) == "The night is long."
    assert join_lines(["A", "vampire walks."]) == "A vampire walks."
    words = {"the", "vampires"}
    assert join_lines(["T he night."], is_word=lambda w: w.lower() in words) == "The night."
    assert join_lines(["B line goes on."], is_word=lambda w: w.lower() in words) == "B line goes on."


def test_cli_guards(capsys):
    with pytest.raises(SystemExit, match="--all"):
        import_books.main(["import"])
    with pytest.raises(SystemExit, match="not an adventure"):
        import_books.main(["attach", "--book", "v5-corebook", "--campaign", "3"])


def test_question_file_is_valid():
    data = manifest.load(os.path.join(BOOKS, "manifest.yaml"))
    qs = evaluate.load_questions(os.path.join(BOOKS, "eval_questions.yaml"), data["books"])
    assert len(qs) >= 45
    assert {q["book_id"] for q in qs} <= {b["book_id"] for b in data["books"]}
    assert all(q["pages"][0] <= q["pages"][1] for q in qs)


def test_question_scoring(tmp_path):
    p = tmp_path / "q.yaml"
    p.write_text("questions:\n- {id: a, book: test-book, pages: '119', q: 'Hunger?'}\n"
                 "- {id: b, book: test-book, pages: '200-201', q: 'Frenzy?'}\n")
    qs = evaluate.load_questions(str(p), [book()])

    def fake(collection, text, k, where):
        return [{"book_id": "test-book", "page": 120, "edition": "classic", "line": "vampire"}]
    rep = evaluate.run_questions([book()], qs, fake)
    assert rep["per_edition"]["classic"]["hit@1"] == 0.5   # 120 is within 119 +-1; 200-201 is missed
    bad = tmp_path / "bad.yaml"
    bad.write_text("questions:\n- {id: a, book: nope, pages: '1', q: 'x'}\n")
    with pytest.raises(ValueError, match="not in the manifest"):
        evaluate.load_questions(str(bad), [book()])
