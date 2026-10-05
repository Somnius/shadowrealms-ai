"""Chunker: sizes, sentence alignment, overlap, section boundaries, ids, de-dup, metadata."""
import re

from conftest import book

from rbimport.chunker import chunk_book
from rbimport.textutil import TokenCounter

CONTRACT_KEYS = {"book_id", "title", "edition", "line", "version", "kind", "heading_path", "page", "page_pdf",
                 "chunk_index", "precedence", "official", "year", "campaign_id", "content_sha"}
C = TokenCounter("estimate")


def sentences(prefix, n, words=18):
    return " ".join(f"{prefix} sentence {i} " + " ".join(["word"] * words) + "." for i in range(n))


def ext_of(blocks, sections=None):
    sections = sections or [{"id": 0, "level": 1, "title": "Rules", "path": ["Rules"], "page_pdf": 1, "page_end_pdf": 9, "leaf": True}]
    return {"sections": sections, "blocks": blocks}


def blk(text, section=0, kind="body", page=1, **kw):
    b = {"section": section, "page_pdf": page, "page": page + 10, "kind": kind, "text": text, "runin": None,
         "headline": False, "small": False}
    b.update(kw)
    return b


def bodies(res):
    return [c["document"].split("\n\n", 1)[1] for c in res["chunks"]]


def test_sizes_alignment_and_overlap():
    ext = ext_of([blk(sentences("A", 60))])
    res = chunk_book(ext, book(), C)
    docs = bodies(res)
    assert len(docs) > 3
    for c, d in zip(res["chunks"], docs):
        assert c["tokens"] <= 512
        assert d.endswith(".")
        assert d.startswith("A sentence")
    toks = [c["tokens"] for c in res["chunks"]]
    assert 200 <= sum(toks) / len(toks) <= 400
    # one-sentence overlap: each chunk starts with the previous chunk's last sentence
    for a, b in zip(docs, docs[1:]):
        last = re.findall(r"A sentence \d+ ", a)[-1]
        assert b.startswith(last)


def test_never_crosses_sections():
    secs = [{"id": 0, "level": 1, "title": "One", "path": ["One"], "page_pdf": 1, "page_end_pdf": 1, "leaf": True},
            {"id": 1, "level": 1, "title": "Two", "path": ["Two"], "page_pdf": 2, "page_end_pdf": 2, "leaf": True}]
    ext = ext_of([blk(sentences("X", 5), 0), blk(sentences("Y", 5), 1, page=2)], secs)
    res = chunk_book(ext, book(), C)
    for c, d in zip(res["chunks"], bodies(res)):
        assert not ("X sentence" in d and "Y sentence" in d)
        assert c["metadata"]["heading_path"] == ("One" if "X sentence" in d else "Two")
        assert c["document"].startswith("Test Book › " + c["metadata"]["heading_path"] + "\n\n")


def test_sidebar_does_not_split_rules_sentence():
    ext = ext_of([blk("Willpower equals Composure plus"), blk("A boxed aside about something else.", kind="sidebar"),
                  blk("Resolve, and it goes up and down."), blk(sentences("Z", 2))])
    res = chunk_book(ext, book(), C)
    kinds = {c["metadata"]["kind"]: b for c, b in zip(res["chunks"], bodies(res))}
    assert "Willpower equals Composure plus\nResolve, and it goes up and down." in kinds["rules"]
    assert kinds["sidebar"] == "A boxed aside about something else."


def test_power_entry_stays_together():
    blocks = [blk(sentences("Intro", 12))]
    for name in ("First Power", "Second Power"):
        blocks += [blk(name, kind="heading"), blk(sentences(name, 4)),
                   blk("Cost: One Rouse Check", runin="Cost:"), blk("Dice Pools: Wits + Auspex", runin="Dice Pools:"),
                   blk("System: " + sentences("Sys", 5), runin="System:"), blk("Duration: One scene", runin="Duration:")]
    res = chunk_book(ext_of(blocks), book(), C)
    docs = bodies(res)
    for name in ("First Power", "Second Power"):
        holder = [d for d in docs if f"{name} sentence 0" in d]
        assert len(holder) == 1 and "Cost: One Rouse Check" in holder[0] and "Duration: One scene" in holder[0]
    paths = [c["metadata"]["heading_path"] for c in res["chunks"]]
    assert "Rules › First Power" in paths and "Rules › Second Power" in paths


def test_ids_deterministic_and_metadata_contract():
    ext = ext_of([blk(sentences("A", 30)), blk("Fiction text here. More of it.", kind="fiction")])
    r1 = chunk_book(ext, book(), C)
    r2 = chunk_book(ext, book(), C)
    assert [c["id"] for c in r1["chunks"]] == [c["id"] for c in r2["chunks"]]
    assert [c["metadata"]["content_sha"] for c in r1["chunks"]] == [c["metadata"]["content_sha"] for c in r2["chunks"]]
    for i, c in enumerate(r1["chunks"]):
        assert c["id"] == f"test-book:{c['metadata']['chunk_index']:05d}"
        assert set(c["metadata"]) == CONTRACT_KEYS
        assert all(isinstance(v, (str, int, bool, float)) for v in c["metadata"].values())
        assert c["metadata"]["page"] == c["metadata"]["page_pdf"] + 10
    assert {c["metadata"]["kind"] for c in r1["chunks"]} == {"rules", "fiction"}
    r3 = chunk_book(ext, book(), C, campaign_id=7)
    assert r3["chunks"][0]["id"] == "c7:test-book:00000" and r3["chunks"][0]["metadata"]["campaign_id"] == 7


def test_dedup_against_higher_precedence():
    ext = ext_of([blk(sentences("A", 3)), blk("Unique sidebar text.", kind="sidebar")])
    first = chunk_book(ext, book(book_id="core"), C)
    seen = {c["metadata"]["content_sha"]: "core" for c in first["chunks"]}
    second = chunk_book(ext, book(book_id="supp", precedence=40), C, seen=seen)
    assert second["chunks"] == [] and second["stats"]["dropped_dup"] == len(first["chunks"])


def test_adventure_kind_and_junk():
    ext = ext_of([blk(sentences("A", 3)), blk("12 14 16 18 20 22 24 26 28 30 32 34", kind="body")])
    res = chunk_book(ext, book(kind="adventure"), C)
    assert {c["metadata"]["kind"] for c in res["chunks"]} == {"adventure"}
    assert all("12 14 16" not in d for d in bodies(res))
