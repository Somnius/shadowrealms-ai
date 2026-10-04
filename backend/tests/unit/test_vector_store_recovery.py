"""Re-embed crash recovery and startup guards (fake Chroma client, no LM Studio)."""

import sys
import types

import pytest

# The unit job has neither chromadb nor numpy; vector_store only needs their names here.
for _name in ("chromadb", "numpy"):
    try:
        __import__(_name)
    except ImportError:
        _m = types.ModuleType(_name)
        if _name == "chromadb":
            _m.Documents = list
            _m.Embeddings = list
            _m.EmbeddingFunction = object
        sys.modules[_name] = _m

from services import vector_store as vs  # noqa: E402


class FakeCol:
    def __init__(self, client, name, ids=()):
        self.client, self.name, self.ids = client, name, list(ids)

    def count(self):
        return len(self.ids)

    def get(self, include=None, limit=None, offset=0):
        return {"ids": self.ids[offset:offset + limit]}

    def modify(self, name):
        if name in self.client.cols:
            raise ValueError("exists")
        del self.client.cols[self.name]
        self.name = name
        self.client.cols[name] = self


class FakeClient:
    def __init__(self, **cols):
        self.cols = {}
        for n, ids in cols.items():
            self.cols[n] = FakeCol(self, n, ids)

    def list_collections(self):
        return list(self.cols)

    def get_collection(self, name):
        return self.cols[name]

    def delete_collection(self, name):
        del self.cols[name]


T = vs.REBUILD_SUFFIX


def test_copy_restored_when_original_missing():
    c = FakeClient(**{"memories" + T: ["a", "b"]})
    acts = vs.recover_leftover_copies(c)
    assert c.cols["memories"].ids == ["a", "b"] and "memories" + T not in c.cols
    assert acts[0]["action"] == "restored_from_copy"


def test_copy_restored_when_original_recreated_empty():
    c = FakeClient(**{"memories": [], "memories" + T: ["a", "b"]})
    vs.recover_leftover_copies(c)
    assert c.cols["memories"].ids == ["a", "b"] and list(c.cols) == ["memories"]


def test_partial_copy_dropped_when_original_has_everything():
    c = FakeClient(**{"memories": ["a", "b", "c"], "memories" + T: ["a"]})
    vs.recover_leftover_copies(c)
    assert list(c.cols) == ["memories"] and c.cols["memories"].ids == ["a", "b", "c"]


def test_copy_with_extra_data_is_kept_aside_never_deleted():
    c = FakeClient(**{"memories": ["new"], "memories" + T: ["a", "b"]})
    acts = vs.recover_leftover_copies(c)
    aside = [n for n in c.cols if vs.ORPHAN_SUFFIX in n]
    assert len(aside) == 1 and c.cols[aside[0]].ids == ["a", "b"] and c.cols["memories"].ids == ["new"]
    assert acts[0]["action"] == "kept_copy_aside"
    assert vs._is_temp_name(aside[0]) and vs._is_temp_name("x" + T) and not vs._is_temp_name("memories")


@pytest.mark.parametrize("env,parent", [
    ({}, False),
    ({"FLASK_ENV": "development"}, True),
    ({"FLASK_ENV": "development", "WERKZEUG_RUN_MAIN": "true"}, False),
    ({"FLASK_ENV": "development", "FLASK_DISABLE_RELOADER": "1"}, False),
    ({"FLASK_DEBUG": "true"}, True),
])
def test_in_reloader_parent(monkeypatch, env, parent):
    for k in ("FLASK_ENV", "FLASK_DEBUG", "FLASK_DISABLE_RELOADER", "WERKZEUG_RUN_MAIN"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert vs.in_reloader_parent() is parent


def test_second_reembed_skips_while_first_holds_lock(monkeypatch):
    monkeypatch.setenv("DATABASE_TYPE", "sqlite")
    with vs.reembed_lock() as first:
        assert first is True
        report = vs.reembed_collections(FakeClient())
        assert report["skipped"]
    with vs.reembed_lock() as again:
        assert again is True
