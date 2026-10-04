#!/usr/bin/env python3
"""
Laya evaluation from the command line: the same report as the admin "Laya" tab.

Inside the backend container (cwd /app):
    python scripts/laya_eval.py                  # labels from the laya_labels table, print the report
    python scripts/laya_eval.py --save           # ...and store it (the admin tab shows it)
    python scripts/laya_eval.py --json           # the report as JSON
    python scripts/laya_eval.py --labels l.jsonl # labels from a file instead of the table
    python scripts/laya_eval.py --no-text        # don't print message excerpts

--labels: one JSON object per line, {"message_id": 231, "in_character": true, "intent": "roleplay"}
(other keys ignored). The text comes from the messages table; ids that are missing or not player
chat are counted and skipped. Without --save the DB session is read-only.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))


def load_label_file(path, cursor, laya_eval):
    labels, bad = {}, 0
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                labels[int(row["message_id"])] = laya_eval.parse_label_body(row)
            except (ValueError, KeyError, TypeError):
                bad += 1
                print(f"line {n}: skipped (bad label)", file=sys.stderr)
    items, missing = [], 0
    for mid, lab in sorted(labels.items()):
        msg = laya_eval.eligible_message(cursor, mid)
        if not msg:
            missing += 1
            continue
        cursor.execute("SELECT campaign_id FROM messages WHERE id = %s", (mid,))
        items.append({"message_id": mid, "campaign_id": cursor.fetchone()["campaign_id"],
                      "content": msg["content"], **lab})
    return items, bad, missing


def main(argv=None):
    ap = argparse.ArgumentParser(description="Evaluate Laya on human-labelled chat messages.")
    ap.add_argument("--labels", help="JSONL label file instead of the laya_labels table")
    ap.add_argument("--save", action="store_true", help="store the report (source 'cli')")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--no-text", action="store_true", help="don't print message excerpts")
    ap.add_argument("--model-dir", help="Laya model dir (default: $LAYA_MODEL_DIR or data/laya/model)")
    args = ap.parse_args(argv)

    from database import get_db
    from services import laya_eval
    from services.classifier import LayaProvider, laya_provider, ooc_threshold

    provider = LayaProvider(args.model_dir) if args.model_dir else laya_provider()
    st = provider.status()
    if not st["available"]:
        print(f"Laya is not available: {st['reason']}", file=sys.stderr)
        return 2

    db = get_db()
    if not args.save:
        db.set_session(readonly=True)  # before any statement: this run can't write
    try:
        cur = db.cursor()
        predict = laya_eval.laya_predictor(provider)
        model = laya_eval.model_info(provider.model_dir)
        if args.labels:
            items, bad, missing = load_label_file(args.labels, cur, laya_eval)
            report = laya_eval.build_report(items, predict, model=model, ooc_threshold=ooc_threshold())
            report["label_source"] = {"file": os.path.basename(args.labels), "bad_lines": bad, "missing_messages": missing}
        else:
            report = laya_eval.evaluate(cur, predict, model=model, ooc_threshold=ooc_threshold())
            report["label_source"] = {"table": "laya_labels"}
        texts = None if args.no_text else laya_eval.fetch_texts(cur, [w["message_id"] for w in report["misclassified"]])
        if args.save:
            laya_eval.reap_stale_runs(cur)
            rid = laya_eval.save_report(cur, report, None, "cli")
            db.commit()
            print(f"saved as report #{rid}", file=sys.stderr)
        else:
            db.rollback()
    finally:
        db.close()

    if args.json:
        if texts is not None:
            for w in report["misclassified"]:
                w["excerpt"] = laya_eval.excerpt(texts.get(w["message_id"], ""))
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(laya_eval.format_report_text(report, texts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
