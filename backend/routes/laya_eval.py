"""
Admin: label player chat for Laya and evaluate Laya on the labels (services/laya_eval.py).

    GET    /api/admin/laya/messages?status=unlabelled|labelled|stale|all&campaign_id=&language=en|el|unknown&page=&per_page=
    PUT    /api/admin/laya/labels/<message_id>   {"in_character": bool, "intent": "roleplay"}
    DELETE /api/admin/laya/labels/<message_id>
    POST   /api/admin/laya/evaluate              -> 202 {"run": {...}}; runs in a background thread
    GET    /api/admin/laya/report[?id=]          -> latest (or one) stored run + short history

Message text is returned as plain data; it is never logged here.
"""

import json
import logging
import threading

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from database import get_db
from routes.admin import require_admin
from services import laya_eval
from services.request_validation import RequestValidationError, strict_int

logger = logging.getLogger(__name__)

laya_eval_bp = Blueprint('laya_eval', __name__, url_prefix='/api/admin/laya')


def _bad(e: RequestValidationError):
    return jsonify({'error': e.public_message}), 400


@laya_eval_bp.route('/messages', methods=['GET'])
@require_admin()
def list_messages():
    try:
        q = laya_eval.parse_list_args(request.args)
    except RequestValidationError as e:
        return _bad(e)
    db = get_db()
    try:
        cur = db.cursor()
        rows = laya_eval.fetch_queue_rows(cur, q['campaign_id'])
        cur.execute(f"""
            SELECT c.id, c.name, COUNT(*) AS n FROM messages m JOIN campaigns c ON c.id = m.campaign_id
             WHERE {laya_eval.ELIGIBLE_SQL} GROUP BY c.id, c.name ORDER BY c.name
        """, ())
        campaigns = [{'id': r['id'], 'name': r['name'], 'n': r['n']} for r in cur.fetchall()]
    except Exception as e:  # noqa: BLE001
        logger.error('Laya queue failed: %s', type(e).__name__)
        return jsonify({'error': 'Could not load messages'}), 500
    finally:
        db.close()
    page = laya_eval.filter_and_page(rows, q['status'], q['language'], q['page'], q['per_page'])
    page['items'] = [laya_eval.queue_item(r) for r in page['items']]
    page['counts'] = laya_eval.queue_counts(rows)
    page['campaigns'] = campaigns
    page['intents'] = laya_eval.INTENTS
    return jsonify(page), 200


@laya_eval_bp.route('/labels/<int:message_id>', methods=['PUT', 'DELETE'])
@require_admin()
def label(message_id):
    if request.method == 'PUT':
        try:
            body = laya_eval.parse_label_body(request.get_json(silent=True))
        except RequestValidationError as e:
            return _bad(e)
    db = get_db()
    try:
        cur = db.cursor()
        if request.method == 'DELETE':
            removed = laya_eval.delete_label(cur, message_id)
            db.commit()
            return jsonify({'ok': True, 'removed': removed}), 200
        msg = laya_eval.eligible_message(cur, message_id)
        if not msg:
            return jsonify({'error': 'Message not found or not a player chat message'}), 404
        laya_eval.upsert_label(cur, message_id, msg['content'], body, int(get_jwt_identity()))
        db.commit()
        return jsonify({'ok': True, 'message_id': message_id, 'label': body}), 200
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.error('Laya label %s failed: %s', message_id, type(e).__name__)
        return jsonify({'error': 'Could not save the label'}), 500
    finally:
        db.close()


def _run_in_background(run_id: int) -> None:
    """Read the gold set, close that connection, run the model (minutes for big sets) with no
    connection open, then store the result over a fresh connection."""
    from services.classifier import laya_provider, ooc_threshold

    report, status = None, 'failed'
    try:
        db = get_db()
        try:
            gold = laya_eval.fetch_labelled(db.cursor())
            db.rollback()
        finally:
            db.close()
        provider = laya_provider()
        report = laya_eval.build_report(gold['items'], laya_eval.laya_predictor(provider),
                                        model=laya_eval.model_info(provider.model_dir),
                                        ooc_threshold=ooc_threshold(), stale=gold['stale'])
        status = 'done'
    except Exception as e:  # noqa: BLE001
        logger.error('Laya evaluation %s failed: %s', run_id, type(e).__name__)
    try:
        db = get_db()
        try:
            laya_eval.finish_run(db.cursor(), run_id, report, status)
            db.commit()
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.error('Laya evaluation %s: could not store the result: %s', run_id, type(e).__name__)
    logger.info('Laya evaluation %s %s (n=%s)', run_id, status, report and report.get('n'))


@laya_eval_bp.route('/evaluate', methods=['POST'])
@require_admin()
def evaluate():
    from services.classifier import laya_provider

    st = laya_provider().status()
    if not st['available']:
        logger.warning('Laya evaluation refused: %s', st.get('reason'))
        return jsonify({'error': 'The Laya model is not installed or failed to load; see the backend logs.'}), 503
    db = get_db()
    try:
        cur = db.cursor()
        run_id = laya_eval.start_run(cur, int(get_jwt_identity()), 'admin')
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.error('Laya evaluation start failed: %s', type(e).__name__)
        return jsonify({'error': 'Could not start the evaluation'}), 500
    finally:
        db.close()
    if run_id is None:
        return jsonify({'error': 'An evaluation is already running'}), 409
    threading.Thread(target=_run_in_background, args=(run_id,), name=f'laya-eval-{run_id}', daemon=True).start()
    return jsonify({'run': {'id': run_id, 'status': 'running'}}), 202


@laya_eval_bp.route('/report', methods=['GET'])
@require_admin()
def report():
    try:
        run_id = strict_int(request.args.get('id'), 'id', None, 1)
    except RequestValidationError as e:
        return _bad(e)
    db = get_db()
    try:
        cur = db.cursor()
        # A run whose process died stays 'running'; mark it failed here so the UI stops waiting.
        laya_eval.reap_stale_runs(cur)
        stale_after = laya_eval.stale_after_seconds(cur)
        db.commit()
        history = laya_eval.latest_runs(cur, 10)
        row = None
        if run_id:
            row = laya_eval.get_run(cur, run_id)
            if row is None:
                return jsonify({'error': 'Report not found'}), 404
        elif history:
            row = history[0]
        body = None
        if row and row.get('report'):
            body = json.loads(row['report'])
            texts = laya_eval.fetch_texts(cur, [w['message_id'] for w in body.get('misclassified', [])])
            for w in body.get('misclassified', []):
                t = texts.get(w['message_id'])
                w['excerpt'] = laya_eval.excerpt(t) if t is not None else None  # None = message deleted
    except Exception as e:  # noqa: BLE001
        logger.error('Laya report failed: %s', type(e).__name__)
        return jsonify({'error': 'Could not load the report'}), 500
    finally:
        db.close()
    return jsonify({
        'run': laya_eval.run_summary(row) if row else None,
        'report': body,
        'history': [laya_eval.run_summary(h) for h in history],
        'stale_after_sec': stale_after,
    }), 200
