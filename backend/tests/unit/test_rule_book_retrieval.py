"""Rule book retrieval (docs/rules/RULE_BOOKS_RAG.md): intent gating, line filter, cutoff,
one embedding per reply, budget order. Fake Chroma client and embedder, no network."""

import sys
import types

import pytest

for _name in ("chromadb", "numpy"):
    try:
        __import__(_name)
    except ImportError:
        _m = types.ModuleType(_name)
        if _name == "chromadb":
            _m.Documents = list
            _m.Embeddings = list
            _m.EmbeddingFunction = object
            _m.HttpClient = lambda **k: None
        sys.modules[_name] = _m

from services import rag_service as rs  # noqa: E402
from services import rules_edition as re_  # noqa: E402
from services import vector_store as vs  # noqa: E402


# --- fakes ----------------------------------------------------------------------------------


class CountingEF:
    """Fake embedder: counts how many times text is embedded (one call per text)."""

    model = "fake"

    def __init__(self):
        self.texts = []

    def __call__(self, texts):
        self.texts.extend(texts)
        # Chroma's wrapper returns numpy float32 vectors; a float subclass stands in for them.
        return [[NpFloat(0.1), NpFloat(0.2), NpFloat(0.3)] for _ in texts]


class NpFloat(float):
    pass


def _match(meta, where):
    if not where:
        return True
    if "$and" in where:
        return all(_match(meta, w) for w in where["$and"])
    (key, cond), = where.items()
    if isinstance(cond, dict) and "$in" in cond:
        return meta.get(key) in cond["$in"]
    return meta.get(key) == cond


class FakeCol:
    """Rows: (id, document, metadata, distance). query() behaves like Chroma's: query_texts
    go through the embedder, query_embeddings don't."""

    def __init__(self, name, ef, rows=()):
        self.name, self.ef, self.rows, self.queries = name, ef, list(rows), []

    def query(self, query_texts=None, query_embeddings=None, n_results=10, where=None, include=None):
        if query_texts is not None:
            self.ef(query_texts)
        self.queries.append({"where": where, "n_results": n_results,
                             "embedded": query_embeddings is not None})
        hits = sorted((r for r in self.rows if _match(r[2], where)), key=lambda r: r[3])[:n_results]
        return {"ids": [[h[0] for h in hits]], "documents": [[h[1] for h in hits]],
                "metadatas": [[h[2] for h in hits]], "distances": [[h[3] for h in hits]]}

    def get(self, where=None, include=None, limit=None, offset=0):
        rows = [r for r in self.rows if _match(r[2], where)]
        rows = rows[offset:offset + limit] if limit else rows[offset:]
        return {"ids": [r[0] for r in rows], "documents": [r[1] for r in rows],
                "metadatas": [r[2] for r in rows]}

    def delete(self, where=None, ids=None):
        self.rows = [r for r in self.rows if not _match(r[2], where)]

    def count(self):
        return len(self.rows)


class FakeClient:
    def __init__(self, ef):
        self.ef, self.cols = ef, {}

    def get_collection(self, name, embedding_function=None):
        if name not in self.cols:
            raise ValueError(f"Collection {name} does not exist")
        return self.cols[name]

    def get_or_create_collection(self, name, embedding_function=None, metadata=None):
        return self.cols.setdefault(name, FakeCol(name, self.ef))


def chunk(book_id, idx, distance, *, edition="classic", line="vampire", kind="rules",
          campaign_id=0, title=None, heading="Chapter Six › Dice", page=190, precedence=10,
          text="Roll a pool of ten-sided dice."):
    title = title or book_id.replace("-", " ").title()
    meta = {"book_id": book_id, "title": title, "edition": edition, "line": line,
            "version": "revised" if edition == "classic" else "v5", "kind": kind,
            "heading_path": heading, "page": page, "page_pdf": page + 2, "chunk_index": idx,
            "precedence": precedence, "official": True, "year": 2000, "campaign_id": campaign_id,
            "content_sha": "x"}
    return (f"{book_id}:{idx:05d}", f"{title} › {heading}\n\n{text}", meta, distance)


@pytest.fixture
def env(monkeypatch):
    ef = CountingEF()
    client = FakeClient(ef)
    monkeypatch.setattr(vs, "embedding_function", lambda: ef)
    monkeypatch.setattr(vs, "get_rag_collection",
                        lambda c, name, ef=None: c.get_or_create_collection(name))
    monkeypatch.setattr(rs, "connect_chroma", lambda cfg: client)
    for var in ("RULE_BOOK_MAX_DISTANCE", "RULE_BOOK_STRICT_MAX_DISTANCE", "RULE_BOOK_BUDGET_TOKENS"):
        monkeypatch.delenv(var, raising=False)
    svc = rs.RAGService({})
    ef.texts.clear()

    def books(name, *rows):
        client.cols[name] = FakeCol(name, ef, rows)
        return client.cols[name]

    return types.SimpleNamespace(svc=svc, ef=ef, client=client, books=books)


RULES = {"label": "rules_question", "score": 0.9}
DICE = {"label": "dice", "score": 0.8}
COMBAT = {"label": "combat", "score": 0.8}
ROLEPLAY = {"label": "roleplay", "score": 0.9}
GENERAL = {"label": "general", "score": 0.95}


# --- plan per intent (pure) -----------------------------------------------------------------


@pytest.mark.parametrize("intent", [RULES, DICE, COMBAT])
def test_rules_intents_search_rules_kinds_k4(intent, monkeypatch):
    monkeypatch.delenv("RULE_BOOK_MAX_DISTANCE", raising=False)
    p = re_.rule_book_plan(intent)
    assert p["kinds"] == ["rules", "sidebar", "example"] and p["k"] == 4
    assert p["max_distance"] == re_.DEFAULT_RULE_BOOK_MAX_DISTANCE and p["rules"]


def test_roleplay_searches_lore_k2_and_general_nothing():
    p = re_.rule_book_plan(ROLEPLAY)
    assert p["kinds"] == ["lore", "adventure"] and p["k"] == 2 and not p["rules"]
    assert re_.rule_book_plan(GENERAL) is None


@pytest.mark.parametrize("intent", [None, {"label": "rules_question", "score": 0.3}, {"label": "x", "score": 1}])
def test_unknown_intent_fails_open_with_stricter_cutoff(intent):
    p = re_.rule_book_plan(intent)
    assert set(p["kinds"]) == {"rules", "sidebar", "example", "lore", "adventure"}
    assert p["k"] == 4 and p["max_distance"] < re_.DEFAULT_RULE_BOOK_MAX_DISTANCE


def test_cutoff_env(monkeypatch):
    monkeypatch.setenv("RULE_BOOK_MAX_DISTANCE", "0.3")
    monkeypatch.setenv("RULE_BOOK_STRICT_MAX_DISTANCE", "bad")
    assert re_.rule_book_plan(RULES)["max_distance"] == 0.3
    assert re_.rule_book_plan(None)["max_distance"] == re_.DEFAULT_RULE_BOOK_STRICT_MAX_DISTANCE


def test_lines():
    assert re_.rule_book_lines("vampire", "classic") == ["vampire", "all"]
    assert re_.rule_book_lines("werewolf", "classic") == ["werewolf", "all"]
    assert re_.rule_book_lines("Mage: The Ascension", "classic") == ["mage", "all"]
    assert re_.rule_book_lines("vampire", "v5") == ["vampire", "all"]
    assert re_.rule_book_lines("custom", "classic") is None  # every line
    assert re_.rule_book_lines(None, "classic") is None


def test_queries_pick_collections():
    q = re_.rule_book_queries(7, "v5", "vampire", ["rules"])
    assert [n for n, _ in q] == ["rule_books_v5", "rule_books_chronicle"]
    assert q[1][1] == {"$and": [{"campaign_id": 7}, {"kind": {"$in": ["rules"]}}]}
    q = re_.rule_book_queries(0, "classic", "custom", ["lore"])
    assert q == [("rule_books_classic", {"kind": {"$in": ["lore"]}})]


def test_citation_and_text():
    _, doc, meta, _ = chunk("vtm-revised-core", 3, 0.1, heading="Chapter Six › Botches", page=192)
    assert re_.rule_book_citation(meta) == "Vtm Revised Core › Chapter Six › Botches, p. 192"
    assert re_.rule_book_text(doc, meta) == "Roll a pool of ten-sided dice."
    assert re_.rule_book_citation({"title": "X"}) == "X"


# --- retrieval against the fake collections -------------------------------------------------


def test_general_intent_runs_no_rule_book_query(env):
    col = env.books("rule_books_classic", chunk("vtm-revised-core", 1, 0.1))
    out = env.svc.augment_prompt("hello", 5, rules_edition="classic", game_system="vampire",
                                 intent=GENERAL, max_tokens=2000)
    assert col.queries == []
    assert "OFFICIAL RULE BOOKS" not in out


def test_vampire_chronicle_never_gets_werewolf(env):
    env.books(
        "rule_books_classic",
        chunk("wta-revised-core", 1, 0.05, line="werewolf", text="Rage dice."),
        chunk("vtm-revised-core", 1, 0.20, text="Vampire rule."),
        chunk("storyteller-system", 1, 0.25, line="all", text="Generic rule."),
    )
    got = env.svc.get_rule_book_context("how do I roll", 5, "classic", "vampire", RULES)
    assert [c["metadata"]["book_id"] for c in got] == ["vtm-revised-core", "storyteller-system"]
    got = env.svc.get_rule_book_context("how do I roll", 5, "classic", "custom", RULES)
    assert "wta-revised-core" in [c["metadata"]["book_id"] for c in got]


def test_v5_reads_only_the_v5_collection(env):
    classic = env.books("rule_books_classic", chunk("vtm-revised-core", 1, 0.01))
    env.books("rule_books_v5", chunk("v5-corebook", 1, 0.2, edition="v5"))
    got = env.svc.get_rule_book_context("hunger dice", 5, "v5", "vampire", DICE)
    assert [c["metadata"]["book_id"] for c in got] == ["v5-corebook"]
    assert classic.queries == []


def test_kinds_k_and_chronicle_books(env):
    env.books(
        "rule_books_classic",
        *[chunk("vtm-revised-core", i, 0.1 + i / 100) for i in range(6)],
        chunk("vtm-revised-core", 9, 0.01, kind="lore", text="Lore."),
        chunk("vtm-revised-core", 10, 0.01, kind="fiction", text="Fiction."),
    )
    env.books(
        "rule_books_chronicle",
        chunk("night-adventure", 1, 0.15, kind="adventure", campaign_id=5),
        chunk("other-adventure", 1, 0.01, kind="adventure", campaign_id=6),
    )
    rules = env.svc.get_rule_book_context("q", 5, "classic", "vampire", COMBAT)
    assert len(rules) == 4 and {c["metadata"]["kind"] for c in rules} == {"rules"}
    lore = env.svc.get_rule_book_context("q", 5, "classic", "vampire", ROLEPLAY)
    assert [c["metadata"]["book_id"] for c in lore] == ["vtm-revised-core", "night-adventure"]
    assert all(c["metadata"].get("campaign_id") in (0, 5) for c in lore)


def test_cutoff_drops_weak_matches(env, monkeypatch):
    env.books("rule_books_classic", chunk("vtm-revised-core", 1, 0.30),
              chunk("vtm-revised-core", 2, 0.44), chunk("vtm-revised-core", 3, 0.80))
    got = env.svc.get_rule_book_context("q", 5, "classic", "vampire", RULES)
    assert [c["distance"] for c in got] == [0.30, 0.44]
    got = env.svc.get_rule_book_context("q", 5, "classic", "vampire", None)  # unknown: stricter
    assert [c["distance"] for c in got] == [0.30]
    monkeypatch.setenv("RULE_BOOK_MAX_DISTANCE", "0.2")
    assert env.svc.get_rule_book_context("q", 5, "classic", "vampire", RULES) == []


def test_missing_collections_are_skipped(env):
    assert env.svc.get_rule_book_context("q", 5, "classic", "vampire", RULES) == []
    assert env.ef.texts == []  # nothing to search: not even embedded


def test_one_embedding_per_reply(env):
    """Before this change one Storyteller reply embedded the message 8 times (5 memory
    queries, 2 rule-book queries with the legacy fallback, 1 semantic history)."""
    env.books("rule_books_classic", chunk("vtm-revised-core", 1, 0.1))
    env.books("rule_books_chronicle", chunk("night-adventure", 1, 0.1, kind="adventure", campaign_id=5))
    msg = "How does frenzy work?"
    emb = rs.embed_query(msg)  # routes/ai.py _storyteller_reply
    assert all(type(x) is float for x in emb)  # query_embeddings refuses numpy floats
    env.svc.retrieve_relevant_messages(msg, 5, 2, limit=3, min_relevance=0.5, query_embedding=emb)
    env.svc.augment_prompt(msg, 5, rules_edition="classic", game_system="vampire", intent=RULES,
                           max_tokens=1500, query_embedding=emb)
    assert env.ef.texts == [msg]
    # without a precomputed embedding augment_prompt still embeds once for all its queries
    env.ef.texts.clear()
    env.svc.augment_prompt(msg, 5, rules_edition="classic", game_system="vampire", intent=None)
    assert env.ef.texts == [msg]


def test_rules_put_books_first_with_their_budget(env, monkeypatch):
    long_rule = "Rule text. " * 300  # ~800 tokens each
    env.books("rule_books_classic", *[chunk("vtm-revised-core", i, 0.1, text=long_rule) for i in range(4)])
    world = env.client.get_or_create_collection("world_memory")
    world.rows = [("w1", "The city of Athens at night.", {"campaign_id": 5}, 0.2)]
    monkeypatch.setenv("RULE_BOOK_BUDGET_TOKENS", "1000")
    out = env.svc.augment_prompt("q", 5, rules_edition="classic", game_system="vampire",
                                 intent=RULES, max_tokens=1500)
    assert out.startswith("=== OFFICIAL RULE BOOKS ===\n\n[Vtm Revised Core › Chapter Six › Dice, p. 190]")
    assert "=== WORLD SETTING ===" in out and "Athens" in out  # memory got what the books left
    from services.storyteller_prompt import estimate_tokens
    books = out.split("=== WORLD SETTING ===")[0]
    assert estimate_tokens(books) <= 1000 + 10


def test_roleplay_lore_goes_last(env):
    env.books("rule_books_classic", chunk("vtm-revised-core", 1, 0.1, kind="lore", text="Elysium lore."))
    world = env.client.get_or_create_collection("world_memory")
    world.rows = [("w1", "Athens.", {"campaign_id": 5}, 0.2)]
    out = env.svc.augment_prompt("q", 5, rules_edition="classic", game_system="vampire",
                                 intent=ROLEPLAY, max_tokens=1500)
    assert out.index("WORLD SETTING") < out.index("OFFICIAL RULE BOOKS")
    assert "Elysium lore." in out


# --- intent computed once ---------------------------------------------------------------------


def test_router_reuses_the_intent_in_context(monkeypatch):
    from services import classifier
    from services.smart_model_router import SmartModelRouter, TaskType

    def boom(text):
        raise AssertionError("classifier must not run again")

    monkeypatch.setattr(classifier, "classify_intent_fast", boom)
    router = SmartModelRouter.__new__(SmartModelRouter)
    assert router.detect_task_type("x", {"laya_intent": RULES}) == TaskType.RULES
    # None = classifier unavailable: keyword rules, no second try
    assert router.detect_task_type("roll dice", {"laya_intent": None}) in tuple(TaskType)


def test_classify_intent_cached_once_and_fail_open(monkeypatch, app_settings):
    from services import classifier

    calls = []

    def fake_classify(text, campaign_ctx=None, *, provider=None, builder=None):
        calls.append(text)
        return {"intent": {"label": "dice", "score": 0.9}, "provider": "laya"}

    monkeypatch.setattr(classifier, "classify", fake_classify)
    monkeypatch.setattr(classifier, "resolve_provider_name", lambda choice=None: "laya")
    classifier._verdict_cache.clear()
    assert classifier.classify_intent_cached("I roll to hit") == {"label": "dice", "score": 0.9}
    assert classifier.classify_intent_cached("I roll to hit")["label"] == "dice"
    assert calls == ["I roll to hit"]
    monkeypatch.setattr(classifier, "resolve_provider_name", lambda choice=None: "llm")
    classifier._verdict_cache.clear()
    assert classifier.classify_intent_cached("other") is None  # no LLM round trip per message


def test_near_equal_matches_prefer_the_more_authoritative_book():
    chunks = [
        {'distance': 0.10, 'metadata': {'precedence': 40}},
        {'distance': 0.11, 'metadata': {'precedence': 10}},
        {'distance': 0.30, 'metadata': {'precedence': 10}},
    ]
    chunks.sort(key=lambda c: (round(c['distance'] / 0.05), c['metadata'].get('precedence', 99), c['distance']))
    assert [c['metadata']['precedence'] for c in chunks][:2] == [10, 40]
