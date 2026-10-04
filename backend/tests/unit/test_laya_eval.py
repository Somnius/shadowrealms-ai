"""services/laya_eval.py: metrics, report building and request validation (pure, no DB)."""

from datetime import datetime, timezone

import pytest

from services import laya_eval as le
from services.request_validation import RequestValidationError


def test_intents_match_the_classifier():
    from services.classifier import INTENTS

    assert le.INTENTS == INTENTS


def test_metrics_known_numbers():
    gold = ["a", "a", "a", "b", "b", "c"]
    pred = ["a", "a", "b", "b", "a", "c"]
    m = le.classification_metrics(gold, pred, ["a", "b", "c"], min_n=2)
    assert m["n"] == 6 and m["correct"] == 4
    assert abs(m["accuracy"] - (4 / 6)) <= 1e-4
    a = m["per_label"]["a"]
    assert (a["n"], a["predicted"], a["correct"]) == (3, 3, 2)
    assert abs(a["precision"] - (0.6667)) <= 1e-4
    assert abs(a["recall"] - (0.6667)) <= 1e-4
    assert abs(a["f1"] - (0.6667)) <= 1e-4
    b = m["per_label"]["b"]
    assert b["precision"] == 0.5 and b["recall"] == 0.5
    assert m["per_label"]["c"]["f1"] == 1.0
    assert m["confusion"] == {"labels": ["a", "b", "c"], "matrix": [[2, 1, 0], [1, 1, 0], [0, 0, 1]]}
    assert abs(m["macro_f1"] - ((0.6667 + 0.5 + 1.0) / 3)) <= 1e-3
    assert m["per_label"]["c"]["too_small"] is True  # n=1 < 2
    assert m["too_small"] is True  # total 6 < MIN_N_TOTAL


def test_metrics_no_data_is_none_not_zero():
    m = le.classification_metrics(["a", "a"], ["a", "a"], ["a", "b"])
    b = m["per_label"]["b"]
    assert b["n"] == 0 and b["predicted"] == 0
    assert b["precision"] is None and b["recall"] is None and b["f1"] is None
    assert m["macro_f1"] == 1.0  # only labels present in gold count
    # predicted but never in gold: precision 0, recall undefined
    m2 = le.classification_metrics(["a"], ["b"], ["a", "b"])
    assert m2["per_label"]["b"]["precision"] == 0.0 and m2["per_label"]["b"]["recall"] is None
    assert m2["per_label"]["a"]["f1"] is None  # precision undefined (a never predicted)
    assert m2["macro_f1"] == 0.0


def test_metrics_empty_and_bad_input():
    m = le.classification_metrics([], [], ["a"])
    assert m["n"] == 0 and m["accuracy"] is None and m["accuracy_ci95"] is None and m["macro_f1"] is None
    with pytest.raises(ValueError):
        le.classification_metrics(["a"], [], ["a"])
    with pytest.raises(ValueError):
        le.classification_metrics(["x"], ["a"], ["a"])


def test_too_small_flags_follow_thresholds():
    gold = ["a"] * 60 + ["b"] * 60
    m = le.classification_metrics(gold, gold, ["a", "b"], min_n=30)
    assert m["too_small"] is False
    assert not m["per_label"]["a"]["too_small"]
    m = le.classification_metrics(gold[:-40], gold[:-40], ["a", "b"], min_n=30)  # b has 20
    assert m["per_label"]["b"]["too_small"] and m["too_small"]


def test_wilson_interval():
    assert le.wilson_interval(0, 0) is None
    lo, hi = le.wilson_interval(8, 8)
    assert abs(lo - (0.6756)) <= 1e-3 and hi == 1.0
    lo, hi = le.wilson_interval(50, 100)
    assert abs(lo - (0.4038)) <= 1e-3 and abs(hi - (0.5962)) <= 1e-3


def _items():
    return [
        {"message_id": 1, "campaign_id": 7, "content": "*draws her knife and hisses at the Prince*", "in_character": True, "intent": "combat"},
        {"message_id": 2, "campaign_id": 7, "content": "Does Blood Surge add to Potence in this edition?", "in_character": False, "intent": "rules_question"},
        {"message_id": 3, "campaign_id": 7, "content": "Πότε παίζουμε την Πέμπτη;", "in_character": False, "intent": "general"},
        {"message_id": 4, "campaign_id": 7, "content": "boom", "in_character": True, "intent": "roleplay"},
    ]


def _predict(text):
    if text == "boom":
        raise RuntimeError("model crashed")
    if text.startswith("*"):
        return {"p_ic": 0.97, "in_character": True, "intent": "combat", "intent_score": 0.9}
    if "Blood Surge" in text:
        return {"p_ic": 0.03, "in_character": False, "intent": "dice", "intent_score": 0.6}
    return {"p_ic": 0.91, "in_character": True, "intent": "general", "intent_score": 0.8}


def test_build_report():
    now = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
    r = le.build_report(_items(), _predict, model={"name": "laya-x"}, ooc_threshold=0.8, stale=2, now=now)
    assert r["created_at"] == "2026-10-04T12:00:00Z"
    assert r["n"] == 3 and r["errors"] == 1 and r["stale_labels_skipped"] == 2
    assert r["model"] == {"name": "laya-x"} and r["ooc_threshold"] == 0.8
    assert r["ooc"]["correct"] == 2 and r["intent"]["correct"] == 2
    assert r["sample_too_small"] is True
    ids = {w["message_id"]: w for w in r["misclassified"]}
    assert set(ids) == {2, 3}
    assert ids[2]["wrong"] == ["intent"] and ids[2]["pred"]["intent"] == "dice"
    assert ids[3]["wrong"] == ["ooc"] and ids[3]["gold"]["in_character"] is False and ids[3]["pred"]["p_ic"] == 0.91
    assert ids[3]["language"] == "el"
    assert "content" not in ids[3] and "text" not in ids[3]  # stored reports never carry the text
    assert r["languages"]["en"]["n"] == 2 and r["languages"]["el"]["ooc_accuracy"] == 0.0
    text = le.format_report_text(r, {2: "Does Blood Surge add to Potence in this edition?"})
    assert "SAMPLE TOO SMALL" in text and "#2 [intent]" in text and "Blood Surge" in text
    assert "(message deleted)" in text  # #3 not in the texts map


def test_build_report_unknown_intent_counts_as_general():
    items = [{"message_id": 1, "content": "hi all", "in_character": False, "intent": "general"}]
    r = le.build_report(items, lambda t: {"p_ic": 0.0, "in_character": False, "intent": "weird", "intent_score": 0.5},
                        model={}, ooc_threshold=0.8)
    assert r["intent"]["correct"] == 1 and r["misclassified"] == []


def test_parse_label_body():
    assert le.parse_label_body({"in_character": True, "intent": "roleplay"}) == {"in_character": True, "intent": "roleplay"}
    assert le.parse_label_body({"in_character": False, "intent": " dice "}) == {"in_character": False, "intent": "dice"}
    for bad in (None, [], "x", {}, {"intent": "dice"}, {"in_character": True},
                {"in_character": "true", "intent": "dice"}, {"in_character": 1, "intent": "dice"},
                {"in_character": True, "intent": "chat"}, {"in_character": True, "intent": 3},
                {"in_character": True, "intent": "x" * 40}):
        with pytest.raises(RequestValidationError):
            le.parse_label_body(bad)


def test_parse_label_body_error_is_public():
    with pytest.raises(RequestValidationError) as e:
        le.parse_label_body({"in_character": True, "intent": "<script>"})
    assert "<script>" not in e.value.public_message  # never echoes client input


def test_parse_list_args():
    assert le.parse_list_args({}) == {"status": "unlabelled", "campaign_id": None, "language": None, "page": 1, "per_page": 25}
    q = le.parse_list_args({"status": "labelled", "campaign_id": "8", "language": "el", "page": "2", "per_page": "50"})
    assert q == {"status": "labelled", "campaign_id": 8, "language": "el", "page": 2, "per_page": 50}
    for bad in ({"status": "nope"}, {"language": "fr"}, {"campaign_id": "x"}, {"campaign_id": "0"},
                {"page": "0"}, {"per_page": "500"}, {"per_page": "2.5"}):
        with pytest.raises(RequestValidationError):
            le.parse_list_args(bad)


def test_label_state_and_paging():
    h = le.content_sha256("hello")
    assert le.label_state({"content": "hello", "label_sha256": None}) == "unlabelled"
    assert le.label_state({"content": "hello", "label_sha256": h}) == "labelled"
    assert le.label_state({"content": "hello!", "label_sha256": h}) == "stale"
    rows = [{"id": i, "state": "labelled" if i % 3 == 0 else "unlabelled", "language": "el" if i % 2 else "en"}
            for i in range(1, 21)]
    p = le.filter_and_page(rows, "unlabelled", None, 2, 5)
    assert p["total"] == 14 and [r["id"] for r in p["items"]] == [8, 10, 11, 13, 14]
    p = le.filter_and_page(rows, "all", "el", 1, 100)
    assert p["total"] == 10
    assert le.filter_and_page(rows, "stale", None, 1, 5)["items"] == []


def test_queue_counts():
    rows = [
        {"state": "labelled", "in_character": True, "intent": "roleplay"},
        {"state": "labelled", "in_character": False, "intent": "rules_question"},
        {"state": "stale", "in_character": True, "intent": "roleplay"},
        {"state": "unlabelled", "in_character": None, "intent": None},
    ]
    c = le.queue_counts(rows)
    assert (c["eligible"], c["labelled"], c["unlabelled"], c["stale"]) == (4, 2, 1, 1)
    assert c["in_character"] == 1 and c["out_of_character"] == 1
    assert c["intents"]["roleplay"] == 1 and c["intents"]["rules_question"] == 1
    assert c["scan_limit_reached"] is False


def test_excerpt():
    assert le.excerpt("a\n  b") == "a b"
    long = "x" * 500
    assert len(le.excerpt(long)) == le.EXCERPT_CHARS and le.excerpt(long).endswith("…")
    assert le.excerpt(None) == ""


def test_run_summary():
    import json

    r = le.build_report(_items()[:2], _predict, model={}, ooc_threshold=0.8)
    s = le.run_summary({"id": 3, "status": "done", "source": "admin", "report": json.dumps(r),
                        "started_at": datetime(2026, 10, 4, 12, 0), "finished_at": None, "started_by": "lef"})
    assert s["n"] == 2 and s["ooc_accuracy"] == 1.0 and s["intent_accuracy"] == 0.5 and s["sample_too_small"] is True
    s = le.run_summary({"id": 4, "status": "running", "report": None})
    assert s["n"] is None and s["ooc_accuracy"] is None


def test_model_info(tmp_path):
    (tmp_path / "laya.json").write_text('{"model_name": "laya-shadowrealms-chat"}', encoding="utf-8")
    (tmp_path / "model.onnx").write_bytes(b"1234")
    info = le.model_info(str(tmp_path))
    assert info["name"] == "laya-shadowrealms-chat" and info["onnx_bytes"] == 4
    assert len(info["config_sha256"]) == 12 and info["onnx_mtime"].endswith("Z")
    assert le.model_info(str(tmp_path / "missing"))["name"] is None


class _FakeCursor:
    def __init__(self, labels):
        self.labels, self.sql, self.rowcount = labels, [], 0

    def execute(self, sql, params=()):
        self.sql.append((" ".join(sql.split()), params))
        self.rowcount = 1 if sql.lstrip().startswith("UPDATE") else 0

    def fetchone(self):
        return {"n": self.labels}


def test_stale_threshold_scales_with_labels():
    assert le.stale_after_seconds(_FakeCursor(0)) == le.STALE_RUN_MIN_SEC
    assert le.stale_after_seconds(_FakeCursor(10)) == le.STALE_RUN_MIN_SEC
    assert le.stale_after_seconds(_FakeCursor(5000)) == 5000 * le.STALE_RUN_SEC_PER_LABEL


def test_reap_marks_old_running_rows_failed():
    cur = _FakeCursor(4000)
    assert le.reap_stale_runs(cur) == 1
    sql, params = cur.sql[-1]
    assert sql.startswith("UPDATE laya_eval_reports SET status = 'failed'") and "status = 'running'" in sql
    assert params == (4000,)


def test_failure_log_is_escaped(caplog):
    items = [{"message_id": 1, "content": "x", "in_character": True, "intent": "roleplay"}]

    def boom(_):
        raise RuntimeError("bad\nFAKE LOG LINE")

    with caplog.at_level("WARNING", logger="services.laya_eval"):
        r = le.build_report(items, boom, model={}, ooc_threshold=0.8)
    assert r["errors"] == 1
    assert "\n" not in caplog.records[-1].getMessage()
