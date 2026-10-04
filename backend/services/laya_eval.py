"""
Laya evaluation on real chat: human labels vs what Laya says.

An admin labels player chat messages (admin "Laya" tab, routes/laya_eval.py) with the two things
Laya predicts: is the message written in character, and its intent (services.classifier.INTENTS).
An evaluation runs Laya on every labelled message, the same way the OOC monitor does
(LayaProvider.classify, in-character = P(IC) >= ooc_threshold()), and reports accuracy,
per-label precision / recall / F1, a confusion matrix and the misclassified message ids.

Small samples are flagged, never hidden: every label carries its n, and `too_small` is set when
n < MIN_N_PER_LABEL (or the whole set is below MIN_N_TOTAL). Accuracy comes with a 95% Wilson
interval, which is honest about how little 8 or 30 messages can tell.

Stored reports hold message ids, never message text; the text is looked up when a report is
shown, so a deleted message disappears from old reports too.

The first half of this file is pure (no DB, no Flask) and unit-tested; the DB helpers below take
a cursor and use PostgreSQL SQL (the only database the admin routes support).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from services.request_validation import RequestValidationError, optional_str, strict_bool, strict_int

logger = logging.getLogger(__name__)

INTENTS = ["dice", "combat", "rules_question", "roleplay", "general"]  # == services.classifier.INTENTS
OOC_LABELS = ["in_character", "out_of_character"]
LANGUAGES = ("en", "el", "unknown")
STATUSES = ("unlabelled", "labelled", "stale", "all")

MIN_N_PER_LABEL = 30   # fewer gold examples than this for a label -> its numbers are flagged
MIN_N_TOTAL = 100      # fewer labelled messages than this -> the whole report is flagged
EXCERPT_CHARS = 160
MAX_SCAN = 5000        # newest eligible messages the label queue looks at
REPORT_VERSION = 1
STALE_RUN_MINUTES = 30  # a 'running' row older than this is a crashed run


# --- validation -----------------------------------------------------------------------------


def parse_label_body(data: Any) -> Dict[str, Any]:
    """{"in_character": bool, "intent": one of INTENTS} -> the same, validated."""
    if not isinstance(data, dict):
        raise RequestValidationError("Request body must be a JSON object")
    if data.get("in_character") is None:
        raise RequestValidationError("in_character is required")
    ic = strict_bool(data.get("in_character"), "in_character")
    intent = optional_str(data.get("intent"), "intent", max_len=32)
    if not intent:
        raise RequestValidationError("intent is required")
    if intent not in INTENTS:
        raise RequestValidationError("intent must be one of: " + ", ".join(INTENTS))
    return {"in_character": ic, "intent": intent}


def parse_list_args(args: Any) -> Dict[str, Any]:
    """Query args of the label queue -> {status, campaign_id, language, page, per_page}."""
    get = (lambda k: args.get(k)) if hasattr(args, "get") else (lambda k: None)
    status = optional_str(get("status"), "status", "unlabelled", 16)
    if status not in STATUSES:
        raise RequestValidationError("status must be one of: " + ", ".join(STATUSES))
    language = optional_str(get("language"), "language", "", 16)
    if language and language not in LANGUAGES:
        raise RequestValidationError("language must be one of: " + ", ".join(LANGUAGES))
    return {
        "status": status,
        "campaign_id": strict_int(get("campaign_id"), "campaign_id", None, 1),
        "language": language or None,
        "page": strict_int(get("page"), "page", 1, 1, 100000),
        "per_page": strict_int(get("per_page"), "per_page", 25, 1, 100),
    }


# --- small pure helpers -----------------------------------------------------------------------


def content_sha256(text: Optional[str]) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def excerpt(text: Optional[str], limit: int = EXCERPT_CHARS) -> str:
    t = " ".join(str(text or "").split())
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def message_language(text: Optional[str]) -> str:
    from services.language import detect_language

    return detect_language(text or "") or "unknown"


def label_state(row: Dict[str, Any]) -> str:
    """'unlabelled' | 'labelled' | 'stale' (labelled, but the text changed since)."""
    if row.get("label_sha256") is None:
        return "unlabelled"
    return "labelled" if row.get("label_sha256") == content_sha256(row.get("content")) else "stale"


def filter_and_page(rows: Sequence[Dict[str, Any]], status: str, language: Optional[str],
                    page: int, per_page: int) -> Dict[str, Any]:
    """Rows already carry 'state' and 'language'. Filter, then slice one page."""
    keep = [r for r in rows
            if (status == "all" or r["state"] == status) and (not language or r["language"] == language)]
    start = (page - 1) * per_page
    return {"items": list(keep[start:start + per_page]), "total": len(keep), "page": page, "per_page": per_page}


def wilson_interval(k: int, n: int, z: float = 1.96) -> Optional[List[float]]:
    """95% Wilson score interval for k successes out of n; None when n == 0."""
    if n <= 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def _ratio(a: int, b: int) -> Optional[float]:
    return round(a / b, 4) if b else None


def classification_metrics(gold: Sequence[str], pred: Sequence[str], labels: Sequence[str],
                           min_n: int = MIN_N_PER_LABEL) -> Dict[str, Any]:
    """
    Accuracy, per-label precision / recall / F1 and a confusion matrix (rows = gold,
    columns = predicted, in `labels` order). A metric whose denominator is 0 is None
    (e.g. precision of a label never predicted), not 0, so "no data" never reads as "bad".
    Macro-F1 averages only labels that occur in the gold set.
    """
    if len(gold) != len(pred):
        raise ValueError("gold and pred differ in length")
    labels = list(labels)
    index = {lab: i for i, lab in enumerate(labels)}
    for x in list(gold) + list(pred):
        if x not in index:
            raise ValueError(f"unknown label {x!r}")
    matrix = [[0] * len(labels) for _ in labels]
    for g, p in zip(gold, pred):
        matrix[index[g]][index[p]] += 1
    n = len(gold)
    correct = sum(matrix[i][i] for i in range(len(labels)))
    per_label = {}
    f1s = []
    for i, lab in enumerate(labels):
        tp = matrix[i][i]
        support = sum(matrix[i])
        predicted = sum(row[i] for row in matrix)
        precision = _ratio(tp, predicted)
        recall = _ratio(tp, support)
        f1 = None
        if precision is not None and recall is not None:
            f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) else 0.0
        if support:
            f1s.append(f1 or 0.0)
        per_label[lab] = {"n": support, "predicted": predicted, "correct": tp,
                          "precision": precision, "recall": recall, "f1": f1,
                          "too_small": support < min_n}
    return {
        "n": n,
        "correct": correct,
        "accuracy": _ratio(correct, n),
        "accuracy_ci95": wilson_interval(correct, n),
        "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else None,
        "per_label": per_label,
        "confusion": {"labels": labels, "matrix": matrix},
        "too_small": n < MIN_N_TOTAL or any(v["too_small"] for v in per_label.values() if v["n"]),
    }


def ooc_name(in_character: bool) -> str:
    return "in_character" if in_character else "out_of_character"


def build_report(items: Iterable[Dict[str, Any]], predict: Callable[[str], Dict[str, Any]], *,
                 model: Dict[str, Any], ooc_threshold: float, stale: int = 0,
                 now: Optional[datetime] = None, min_n: int = MIN_N_PER_LABEL) -> Dict[str, Any]:
    """
    items: [{"message_id", "campaign_id", "content", "in_character", "intent"}] (gold labels).
    predict(text) -> {"p_ic": float, "in_character": bool, "intent": str, "intent_score": float}
    (raises on failure; such messages are counted in `errors` and left out of the metrics).
    """
    gold_ooc, pred_ooc, gold_int, pred_int = [], [], [], []
    by_lang: Dict[str, Dict[str, int]] = {}
    wrong = []
    errors = 0
    for it in items:
        try:
            p = predict(it["content"])
        except Exception as e:  # noqa: BLE001 - one bad message must not sink the run
            errors += 1
            logger.warning("Laya failed on message %s: %s: %s", it.get("message_id"), type(e).__name__, str(e)[:200])
            continue
        lang = message_language(it["content"])
        g_ooc, p_ooc = ooc_name(bool(it["in_character"])), ooc_name(bool(p["in_character"]))
        g_int, p_int = it["intent"], p["intent"] if p["intent"] in INTENTS else "general"
        gold_ooc.append(g_ooc)
        pred_ooc.append(p_ooc)
        gold_int.append(g_int)
        pred_int.append(p_int)
        b = by_lang.setdefault(lang, {"n": 0, "ooc_correct": 0, "intent_correct": 0})
        b["n"] += 1
        b["ooc_correct"] += g_ooc == p_ooc
        b["intent_correct"] += g_int == p_int
        miss = [k for k, ok in (("ooc", g_ooc == p_ooc), ("intent", g_int == p_int)) if not ok]
        if miss:
            wrong.append({
                "message_id": it["message_id"], "campaign_id": it.get("campaign_id"), "language": lang,
                "wrong": miss,
                "gold": {"in_character": bool(it["in_character"]), "intent": g_int},
                "pred": {"in_character": bool(p["in_character"]), "p_ic": round(float(p.get("p_ic", 0.0)), 4),
                         "intent": p_int, "intent_score": round(float(p.get("intent_score", 0.0)), 4)},
            })
    n = len(gold_ooc)
    languages = {
        lang: {"n": b["n"],
               "ooc_accuracy": _ratio(b["ooc_correct"], b["n"]),
               "intent_accuracy": _ratio(b["intent_correct"], b["n"]),
               "too_small": b["n"] < min_n}
        for lang, b in sorted(by_lang.items())
    }
    ooc = classification_metrics(gold_ooc, pred_ooc, OOC_LABELS, min_n)
    intent = classification_metrics(gold_int, pred_int, INTENTS, min_n)
    return {
        "version": REPORT_VERSION,
        "created_at": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": model,
        "ooc_threshold": ooc_threshold,
        "n": n,
        "errors": errors,
        "stale_labels_skipped": stale,
        "min_n_per_label": min_n,
        "min_n_total": MIN_N_TOTAL,
        "sample_too_small": ooc["too_small"] or intent["too_small"],
        "ooc": ooc,
        "intent": intent,
        "languages": languages,
        "misclassified": wrong,
    }


def _fmt(v: Optional[float]) -> str:
    return "-" if v is None else f"{v:.3f}"


def _metrics_text(title: str, m: Dict[str, Any], short: Dict[str, str]) -> List[str]:
    ci = m["accuracy_ci95"]
    out = [f"{title}: accuracy {_fmt(m['accuracy'])} ({m['correct']}/{m['n']})"
           + (f", 95% CI {ci[0]:.2f}-{ci[1]:.2f}" if ci else "")
           + f", macro-F1 {_fmt(m['macro_f1'])}"]
    out.append(f"  {'label':<18}{'n':>5}{'pred':>6}{'prec':>8}{'recall':>8}{'F1':>8}")
    for lab, v in m["per_label"].items():
        flag = "  (n too small)" if v["n"] and v["too_small"] else ""
        out.append(f"  {lab:<18}{v['n']:>5}{v['predicted']:>6}{_fmt(v['precision']):>8}"
                   f"{_fmt(v['recall']):>8}{_fmt(v['f1']):>8}{flag}")
    labels = m["confusion"]["labels"]
    out.append("  confusion (rows gold, columns predicted): " + " ".join(short.get(x, x) for x in labels))
    for lab, row in zip(labels, m["confusion"]["matrix"]):
        out.append(f"  {lab:<18}" + "".join(f"{c:>6}" for c in row))
    return out


def format_report_text(report: Dict[str, Any], texts: Optional[Dict[int, str]] = None) -> str:
    """Plain-text report (CLI, docs). texts: message_id -> text, for the misclassified list."""
    m = report.get("model") or {}
    lines = [
        f"Laya evaluation, {report['created_at']}",
        f"model: {m.get('name') or '?'} (laya.json sha256 {m.get('config_sha256') or '?'}, "
        f"model.onnx {m.get('onnx_bytes') or '?'} bytes)",
        f"labelled messages evaluated: {report['n']} (Laya errors: {report['errors']}, "
        f"stale labels skipped: {report['stale_labels_skipped']}); OOC threshold P(IC) >= {report['ooc_threshold']}",
    ]
    if report["sample_too_small"]:
        lines.append(f"SAMPLE TOO SMALL: fewer than {report['min_n_total']} messages, or a label with fewer "
                     f"than {report['min_n_per_label']}. Read these numbers as anecdotes, not rates.")
    lines.append("")
    lines += _metrics_text("In character (OOC monitor)", report["ooc"], {"in_character": "IC", "out_of_character": "OOC"})
    lines.append("")
    lines += _metrics_text("Intent", report["intent"], {"rules_question": "rules"})
    lines.append("")
    lines.append("By language (detected): " + ("; ".join(
        f"{lang} n={v['n']} OOC acc {_fmt(v['ooc_accuracy'])} intent acc {_fmt(v['intent_accuracy'])}"
        for lang, v in report["languages"].items()) or "none"))
    lines.append("")
    lines.append(f"Misclassified: {len(report['misclassified'])}")
    for w in report["misclassified"]:
        g, p = w["gold"], w["pred"]
        lines.append(f"  #{w['message_id']} [{','.join(w['wrong'])}] gold {ooc_name(g['in_character'])}/{g['intent']}"
                     f" -> Laya {ooc_name(p['in_character'])} (P(IC) {p['p_ic']:.2f})/{p['intent']} ({p['intent_score']:.2f})")
        if texts is not None:
            lines.append(f"      {excerpt(texts.get(w['message_id'], '(message deleted)'))}")
    return "\n".join(lines)


def model_info(model_dir: str) -> Dict[str, Any]:
    """Which Laya build was evaluated: laya.json's model_name + a hash of laya.json (it holds the
    run's fitted temperatures, so it changes with every training run) + model.onnx size/mtime."""
    info: Dict[str, Any] = {"name": None, "config_sha256": None, "onnx_bytes": None, "onnx_mtime": None}
    try:
        with open(os.path.join(model_dir, "laya.json"), "rb") as f:
            raw = f.read()
        info["config_sha256"] = hashlib.sha256(raw).hexdigest()[:12]
        info["name"] = json.loads(raw.decode("utf-8")).get("model_name")
    except (OSError, ValueError):
        pass
    try:
        st = os.stat(os.path.join(model_dir, "model.onnx"))
        info["onnx_bytes"] = st.st_size
        info["onnx_mtime"] = datetime.fromtimestamp(st.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError:
        pass
    return info


def laya_predictor(provider=None) -> Callable[[str], Dict[str, Any]]:
    """predict(text) through the production path (LayaProvider.classify, backend threshold)."""
    if provider is None:
        from services.classifier import laya_provider

        provider = laya_provider()

    def predict(text: str) -> Dict[str, Any]:
        res = provider.classify(text)
        return {"p_ic": res["ooc_violation"]["score"], "in_character": bool(res["ooc_violation"]["label"]),
                "intent": res["intent"]["label"], "intent_score": res["intent"]["score"]}

    return predict


# --- DB helpers (PostgreSQL, cursor with dict rows) ------------------------------------------

# Player chat only: no Storyteller/AI replies, no system rows, no dice rows (roll results and
# animation markers are generated, not typed).
ELIGIBLE_SQL = (
    "m.role = 'user' AND COALESCE(m.message_type, '') <> 'system' "
    "AND COALESCE(m.ai_message_kind, '') NOT LIKE 'dice%%'"
)


def fetch_queue_rows(cursor, campaign_id: Optional[int] = None, limit: int = MAX_SCAN) -> List[Dict[str, Any]]:
    """Newest eligible messages (up to `limit`) with their label, if any; adds 'state' and 'language'."""
    params: List[Any] = []
    where = ELIGIBLE_SQL
    if campaign_id:
        where += " AND m.campaign_id = %s"
        params.append(campaign_id)
    params.append(limit)
    cursor.execute(f"""
        SELECT m.id, m.campaign_id, c.name AS campaign_name, m.location_id, l.name AS location_name,
               l.type AS location_type, m.message_type, m.speaker_mode, m.content, m.created_at,
               ll.in_character, ll.intent, ll.content_sha256 AS label_sha256, ll.updated_at AS labelled_at,
               u.username AS labelled_by
          FROM messages m
          JOIN campaigns c ON c.id = m.campaign_id
          LEFT JOIN locations l ON l.id = m.location_id
          LEFT JOIN laya_labels ll ON ll.message_id = m.id
          LEFT JOIN users u ON u.id = ll.labelled_by
         WHERE {where}
         ORDER BY m.id DESC
         LIMIT %s
    """, params)
    rows = [dict(r) for r in cursor.fetchall()]
    for r in rows:
        r["state"] = label_state(r)
        r["language"] = message_language(r["content"])
    return rows


def queue_item(r: Dict[str, Any]) -> Dict[str, Any]:
    """JSON shape of one queue row (text is plain text; the client must render it as text)."""
    when = r.get("created_at")
    labelled = r.get("labelled_at")
    return {
        "id": r["id"], "campaign_id": r["campaign_id"], "campaign_name": r.get("campaign_name"),
        "location_id": r.get("location_id"), "location_name": r.get("location_name"),
        "location_type": r.get("location_type"), "message_type": r.get("message_type"),
        "speaker_mode": r.get("speaker_mode"), "content": r.get("content") or "",
        "created_at": when.isoformat() if hasattr(when, "isoformat") else when,
        "language": r["language"], "state": r["state"],
        "label": None if r["state"] == "unlabelled" else {
            "in_character": bool(r["in_character"]), "intent": r["intent"],
            "labelled_by": r.get("labelled_by"),
            "updated_at": labelled.isoformat() if hasattr(labelled, "isoformat") else labelled,
        },
    }


def queue_counts(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Progress over the scanned rows: totals by state, and the gold label balance."""
    counts = {"eligible": len(rows), "unlabelled": 0, "labelled": 0, "stale": 0,
              "in_character": 0, "out_of_character": 0, "intents": {k: 0 for k in INTENTS}}
    for r in rows:
        counts[r["state"]] += 1
        if r["state"] == "labelled":
            counts[ooc_name(bool(r["in_character"]))] += 1
            if r["intent"] in counts["intents"]:
                counts["intents"][r["intent"]] += 1
    counts["scan_limit_reached"] = len(rows) >= MAX_SCAN
    return counts


def eligible_message(cursor, message_id: int) -> Optional[Dict[str, Any]]:
    cursor.execute(f"SELECT m.id, m.content FROM messages m WHERE m.id = %s AND {ELIGIBLE_SQL}", (message_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def upsert_label(cursor, message_id: int, content: str, label: Dict[str, Any], user_id: Optional[int]) -> None:
    cursor.execute("""
        INSERT INTO laya_labels (message_id, in_character, intent, content_sha256, labelled_by)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (message_id) DO UPDATE
           SET in_character = EXCLUDED.in_character, intent = EXCLUDED.intent,
               content_sha256 = EXCLUDED.content_sha256, labelled_by = EXCLUDED.labelled_by,
               updated_at = NOW()
    """, (message_id, label["in_character"], label["intent"], content_sha256(content), user_id))


def delete_label(cursor, message_id: int) -> bool:
    cursor.execute("DELETE FROM laya_labels WHERE message_id = %s", (message_id,))
    return bool(cursor.rowcount)


def fetch_labelled(cursor) -> Dict[str, Any]:
    """Gold set for an evaluation: {"items": [...], "stale": n}. Stale labels are left out."""
    cursor.execute(f"""
        SELECT m.id AS message_id, m.campaign_id, m.content, ll.in_character, ll.intent,
               ll.content_sha256 AS label_sha256
          FROM laya_labels ll JOIN messages m ON m.id = ll.message_id
         WHERE {ELIGIBLE_SQL}
         ORDER BY m.id
    """, ())
    items, stale = [], 0
    for r in cursor.fetchall():
        r = dict(r)
        if r["label_sha256"] != content_sha256(r["content"]):
            stale += 1
            continue
        items.append(r)
    return {"items": items, "stale": stale}


def fetch_texts(cursor, message_ids: Sequence[int]) -> Dict[int, str]:
    ids = [int(i) for i in message_ids]
    if not ids:
        return {}
    cursor.execute("SELECT id, content FROM messages WHERE id = ANY(%s)", (ids,))
    return {r["id"]: r["content"] for r in cursor.fetchall()}


def start_run(cursor, user_id: Optional[int], source: str = "admin") -> Optional[int]:
    """New 'running' report row, or None if another run is in progress. Crashed runs
    (still 'running' after STALE_RUN_MINUTES) are marked failed first."""
    cursor.execute(
        "UPDATE laya_eval_reports SET status = 'failed', finished_at = NOW() "
        "WHERE status = 'running' AND started_at < NOW() - make_interval(mins => %s)",
        (STALE_RUN_MINUTES,),
    )
    cursor.execute(
        "INSERT INTO laya_eval_reports (status, source, started_by) VALUES ('running', %s, %s) "
        "ON CONFLICT DO NOTHING RETURNING id",
        (source, user_id),
    )
    row = cursor.fetchone()
    return row["id"] if row else None


def finish_run(cursor, run_id: int, report: Optional[Dict[str, Any]], status: str = "done") -> None:
    cursor.execute(
        "UPDATE laya_eval_reports SET status = %s, finished_at = NOW(), report = %s WHERE id = %s",
        (status, json.dumps(report) if report is not None else None, run_id),
    )


def save_report(cursor, report: Dict[str, Any], user_id: Optional[int], source: str) -> int:
    cursor.execute(
        "INSERT INTO laya_eval_reports (status, source, started_by, finished_at, report) "
        "VALUES ('done', %s, %s, NOW(), %s) RETURNING id",
        (source, user_id, json.dumps(report)),
    )
    return cursor.fetchone()["id"]


def latest_runs(cursor, limit: int = 10) -> List[Dict[str, Any]]:
    cursor.execute("""
        SELECT r.id, r.status, r.source, r.started_at, r.finished_at, r.report, u.username AS started_by
          FROM laya_eval_reports r LEFT JOIN users u ON u.id = r.started_by
         ORDER BY r.id DESC LIMIT %s
    """, (limit,))
    return [dict(r) for r in cursor.fetchall()]


def run_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    """Short history line of a stored run (no report body)."""
    rep = None
    try:
        rep = json.loads(row["report"]) if row.get("report") else None
    except ValueError:
        rep = None
    iso = lambda v: v.isoformat() if hasattr(v, "isoformat") else v  # noqa: E731
    return {
        "id": row["id"], "status": row["status"], "source": row.get("source"),
        "started_by": row.get("started_by"), "started_at": iso(row.get("started_at")),
        "finished_at": iso(row.get("finished_at")),
        "n": rep.get("n") if rep else None,
        "ooc_accuracy": rep["ooc"]["accuracy"] if rep else None,
        "intent_accuracy": rep["intent"]["accuracy"] if rep else None,
        "sample_too_small": rep.get("sample_too_small") if rep else None,
    }


def evaluate(cursor, predict: Callable[[str], Dict[str, Any]], *, model: Dict[str, Any],
             ooc_threshold: float) -> Dict[str, Any]:
    gold = fetch_labelled(cursor)
    return build_report(gold["items"], predict, model=model, ooc_threshold=ooc_threshold, stale=gold["stale"])
