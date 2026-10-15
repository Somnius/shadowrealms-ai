"""
Saved-point spends (Forge v2 part D): a V5 player spends the Advantage dots or the free specialty
saved at creation (wod_meta.saved); the Storyteller approves, rejects or reverses. In a chronicle
whose creation_settings.st_mode is 'ai' a spend that passes the rule check
(services/saved_points.validate_spend, deterministic, no LLM) is applied at once with approver
'ai'; the human creator or staff can reverse it. Failing spends are house rules: pending, flagged.

  POST  /api/characters/<id>/spend-requests            owner (a locked sheet is fine)
  GET   /api/characters/<id>/spend-requests            owner, the chronicle's Storyteller, staff
  GET   /api/campaigns/<cid>/spend-requests?status=    the chronicle's Storyteller, staff
  PATCH /api/campaigns/<cid>/spend-requests/<rid>      {action: approve|reject|reverse, reason,
                                                        confirm_house_rule}

Applying and reversing lock the character row (SELECT ... FOR UPDATE, as routes/dice.py does)
and take the snapshots in the same transaction; the status change is guarded in its WHERE, so a
retried approve can't apply twice. Only the columns a spend touches are written back, and a sheet
column that doesn't hold a JSON object is refused (500) instead of being overwritten.
"""

import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from database import (
    ensure_campaigns_creation_settings_column,
    ensure_character_spend_requests_table,
    get_db,
)
from services.creation_settings import normalize_creation_settings
from services.log_safety import safe_log_value
from services.playing_character import can_view_character_sheet, is_campaign_storyteller_or_staff
from services.request_validation import RequestValidationError
from services.rules_edition import V5, edition_of
from services.v5_catalog import load_catalog
from services.saved_points import (
    STATUSES,
    TOUCHED,
    SheetChanged,
    apply_spend,
    parse_spend,
    reverse_spend,
    saved_balance,
    validate_spend,
)

logger = logging.getLogger(__name__)

spend_requests_bp = Blueprint("spend_requests", __name__)

PENDING_MAX = 10
REASON_MAX = 500
ACTIONS = ("approve", "reject", "reverse")

_SELECT = """
    SELECT r.*, ch.name AS character_name, u.username AS username,
           rb.username AS resolved_by_name, vb.username AS reversed_by_name
    FROM character_spend_requests r
    JOIN characters ch ON ch.id = r.character_id
    JOIN users u ON u.id = r.user_id
    LEFT JOIN users rb ON rb.id = r.resolved_by
    LEFT JOIN users vb ON vb.id = r.reversed_by
"""


def _ensure(cursor):
    ensure_character_spend_requests_table(cursor)
    ensure_campaigns_creation_settings_column(cursor)


def _json(raw, default):
    if isinstance(raw, (dict, list)):
        return raw
    try:
        v = json.loads(raw) if raw else default
    except (TypeError, ValueError):
        return default
    return v if isinstance(v, type(default)) else default


class SheetDataError(Exception):
    """A sheet column that isn't empty but doesn't hold a JSON object."""


def _state(ch):
    """The three sheet columns as dicts. Empty is {}; anything else that isn't an object raises."""
    out = {}
    for col in ("wod_meta", "skills", "merits_flaws"):
        raw = ch.get(col)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            out[col] = {}
            continue
        try:
            value = raw if isinstance(raw, dict) else json.loads(raw)
        except (TypeError, ValueError):
            value = None
        if not isinstance(value, dict):
            raise SheetDataError(col)
        out[col] = value
    return out


def _request_dict(r):
    return {
        "id": r["id"],
        "character_id": r["character_id"],
        "character_name": r.get("character_name"),
        "campaign_id": r["campaign_id"],
        "user_id": r["user_id"],
        "username": r.get("username"),
        "kind": r["kind"],
        "payload": _json(r.get("payload"), {}),
        "rule_check": _json(r.get("rule_check"), {}),
        "status": r["status"],
        "approver": r.get("approver"),
        "resolved_by": r.get("resolved_by"),
        "resolved_by_name": r.get("resolved_by_name"),
        "resolved_at": r.get("resolved_at"),
        "reason": r.get("reason"),
        "reverse_reason": r.get("reverse_reason"),
        "changes": _json(r.get("after_state"), {}).get("changes") or [],
        "reversed_by": r.get("reversed_by"),
        "reversed_by_name": r.get("reversed_by_name"),
        "reversed_at": r.get("reversed_at"),
        "created_at": r.get("created_at"),
    }


def _fetch_request(cursor, rid):
    cursor.execute(_SELECT + " WHERE r.id = %s", (rid,))
    row = cursor.fetchone()
    return _request_dict(row) if row else None


def _settings(cursor, campaign_id):
    cursor.execute("SELECT creation_settings FROM campaigns WHERE id = %s", (campaign_id,))
    row = cursor.fetchone()
    return normalize_creation_settings(row.get("creation_settings") if row else None)


def _spend_catalog():
    """
    (catalog, ok): the V5 catalog for the rule check (load_catalog(): clans, Disciplines and, when
    installed, advantages.json / loresheets.json). ok is False when it can't be read.
    """
    try:
        cat = load_catalog()
    except Exception as e:  # a broken catalog file
        logger.error("spend check: the V5 catalog could not be read: %s", safe_log_value(e))
        return {}, False
    return (cat if isinstance(cat, dict) else {}), True


def _rule_check(state, payload, settings):
    """validate_spend on the sheet; without a readable catalog an Advantage spend is a house rule
    (fail closed: a person decides)."""
    catalog, ok = _spend_catalog()
    check = validate_spend(state["wod_meta"], payload, catalog, settings, state["skills"])
    if not ok and payload["kind"] == "saved_advantage":
        check["problems"].append({"code": "catalog_error", "params": {}})
        check["ok"], check["house_rule"] = False, True
    return check


def _write_sheet(cursor, character_id, state, kind):
    """Write back only the columns a spend of this kind touches."""
    cols = sorted({col for col, _ in TOUCHED[kind]})
    cursor.execute(
        "UPDATE characters SET " + ", ".join(f"{c} = %s" for c in cols)
        + ", updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        tuple(json.dumps(state[c]) for c in cols) + (character_id,),
    )


def _damaged(e, character_id):
    logger.error("spend: character %s has a damaged %s column", safe_log_value(character_id), safe_log_value(e))
    return _error("This character's sheet data is damaged; ask staff to fix it.", "sheet_data_damaged", 500)


def _no_chronicle():
    return jsonify({"error": "Chronicle not found or access denied"}), 404


def _now():
    """Naive UTC, as the TIMESTAMP columns hold it."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _error(message, code, status):
    return jsonify({"error": message, "error_code": code}), status


@spend_requests_bp.route("/characters/<int:character_id>/spend-requests", methods=["POST"])
@jwt_required()
def create_spend_request(character_id):
    """The owner spends saved points. AI mode + passing rule check: applied at once."""
    user_id = int(get_jwt_identity())
    try:
        payload = parse_spend(request.get_json(silent=True))
    except RequestValidationError as e:
        return jsonify({"error": e.public_message}), 400
    db = get_db()
    try:
        cursor = db.cursor()
        _ensure(cursor)
        db.commit()
        cursor.execute("SELECT * FROM characters WHERE id = %s FOR UPDATE", (character_id,))
        ch = cursor.fetchone()
        if not ch:
            db.rollback()
            return jsonify({"error": "Character not found"}), 404
        if str(ch["user_id"]) != str(user_id):
            db.rollback()
            return jsonify({"error": "Only the character's player can spend its saved points."}), 403
        if ch.get("campaign_id") is None:
            db.rollback()
            return _error("Bring this character into a chronicle first.", "character_has_no_chronicle", 400)
        if edition_of(ch) != V5:
            db.rollback()
            return _error("Saved points are for V5 characters.", "not_v5", 400)
        campaign_id = ch["campaign_id"]
        cursor.execute(
            "SELECT COUNT(*) AS n FROM character_spend_requests WHERE character_id = %s AND status = 'pending'",
            (character_id,),
        )
        if int((cursor.fetchone() or {}).get("n") or 0) >= PENDING_MAX:
            db.rollback()
            return _error(
                f"This character already has {PENDING_MAX} spends waiting for the Storyteller.",
                "too_many_pending",
                409,
            )
        settings = _settings(cursor, campaign_id)
        try:
            state = _state(ch)
        except SheetDataError as e:
            db.rollback()
            return _damaged(e, character_id)
        check = _rule_check(state, payload, settings)
        now = _now()
        applied = settings["st_mode"] == "ai" and check["ok"]
        if applied:
            new_state, before, after = apply_spend(state, payload)
            _write_sheet(cursor, character_id, new_state, payload["kind"])
            cursor.execute(
                """
                INSERT INTO character_spend_requests (
                    character_id, campaign_id, user_id, kind, payload, rule_check, status,
                    approver, resolved_at, before_state, after_state, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, 'approved', 'ai', %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    character_id, campaign_id, user_id, payload["kind"], json.dumps(payload),
                    json.dumps(check), now, json.dumps(before), json.dumps(after), now,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO character_spend_requests (
                    character_id, campaign_id, user_id, kind, payload, rule_check, status, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
                RETURNING id
                """,
                (character_id, campaign_id, user_id, payload["kind"], json.dumps(payload), json.dumps(check), now),
            )
        rid = cursor.fetchone()["id"]
        db.commit()
        if applied:
            logger.info("spend request %s on character %s approved by the rule check (AI mode)", rid, character_id)
        return jsonify({"request": _fetch_request(cursor, rid), "applied": applied}), 201
    except Exception as e:
        db.rollback()
        logger.error("create_spend_request: %s", safe_log_value(e))
        return jsonify({"error": "Could not submit the spend"}), 500
    finally:
        db.close()


@spend_requests_bp.route("/characters/<int:character_id>/spend-requests", methods=["GET"])
@jwt_required()
def list_character_spend_requests(character_id):
    """A character's spends, with its saved balance and the chronicle's approval mode."""
    user_id = int(get_jwt_identity())
    db = get_db()
    try:
        cursor = db.cursor()
        _ensure(cursor)
        db.commit()
        cursor.execute("SELECT * FROM characters WHERE id = %s", (character_id,))
        ch = cursor.fetchone()
        if not ch:
            return jsonify({"error": "Character not found"}), 404
        if not can_view_character_sheet(cursor, user_id, ch):
            return jsonify({"error": "Access denied"}), 403
        cursor.execute(
            _SELECT + " WHERE r.character_id = %s ORDER BY r.created_at DESC, r.id DESC LIMIT 100",
            (character_id,),
        )
        rows = [_request_dict(r) for r in cursor.fetchall()]
        campaign_id = ch.get("campaign_id")
        settings = _settings(cursor, campaign_id) if campaign_id is not None else normalize_creation_settings(None)
        is_v5 = edition_of(ch) == V5
        return jsonify({
            "requests": rows,
            "saved": saved_balance(_json(ch.get("wod_meta"), {})),
            "settings": {"st_mode": settings["st_mode"], "saved_points": settings["saved_points"]},
            "can_spend": is_v5 and campaign_id is not None and str(ch["user_id"]) == str(user_id),
            "can_review": campaign_id is not None and is_campaign_storyteller_or_staff(cursor, user_id, campaign_id),
        }), 200
    except Exception as e:
        logger.error("list_character_spend_requests: %s", safe_log_value(e))
        return jsonify({"error": "Could not list the spends"}), 500
    finally:
        db.close()


@spend_requests_bp.route("/campaigns/<int:campaign_id>/spend-requests", methods=["GET"])
@jwt_required()
def list_campaign_spend_requests(campaign_id):
    """The chronicle's spends for its Storyteller and staff, pending first."""
    user_id = int(get_jwt_identity())
    status = (request.args.get("status") or "all").strip().lower()
    if status != "all" and status not in STATUSES:
        return jsonify({"error": "status must be all, pending, approved, rejected or reversed"}), 400
    db = get_db()
    try:
        cursor = db.cursor()
        _ensure(cursor)
        db.commit()
        cursor.execute("SELECT id FROM campaigns WHERE id = %s", (campaign_id,))
        if not cursor.fetchone() or not is_campaign_storyteller_or_staff(cursor, user_id, campaign_id):
            return _no_chronicle()
        where, params = " WHERE r.campaign_id = %s", [campaign_id]
        if status != "all":
            where += " AND r.status = %s"
            params.append(status)
        cursor.execute(
            _SELECT + where
            + " ORDER BY CASE WHEN r.status = 'pending' THEN 0 ELSE 1 END, r.created_at DESC, r.id DESC LIMIT 200",
            tuple(params),
        )
        rows = [_request_dict(r) for r in cursor.fetchall()]
        return jsonify({"requests": rows, "st_mode": _settings(cursor, campaign_id)["st_mode"]}), 200
    except Exception as e:
        logger.error("list_campaign_spend_requests: %s", safe_log_value(e))
        return jsonify({"error": "Could not list the spends"}), 500
    finally:
        db.close()


@spend_requests_bp.route("/campaigns/<int:campaign_id>/spend-requests/<int:request_id>", methods=["PATCH"])
@jwt_required()
def resolve_spend_request(campaign_id, request_id):
    """
    Approve (applies it), reject, or reverse an approved spend. The rule check runs again on
    today's sheet; when it fails, approve needs confirm_house_rule: true (else 409 now_house_rule
    with the new check), so a spend that turned into a house rule is never approved unseen.
    """
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}
    action = data.get("action")
    if action not in ACTIONS:
        return jsonify({"error": "action must be approve, reject or reverse"}), 400
    reason = data.get("reason")
    if reason is not None and (not isinstance(reason, str) or len(reason) > REASON_MAX):
        return jsonify({"error": f"reason must be text of at most {REASON_MAX} characters"}), 400
    reason = (reason or "").strip() or None
    db = get_db()
    try:
        cursor = db.cursor()
        _ensure(cursor)
        db.commit()
        cursor.execute("SELECT id FROM campaigns WHERE id = %s", (campaign_id,))
        if not cursor.fetchone() or not is_campaign_storyteller_or_staff(cursor, user_id, campaign_id):
            db.rollback()
            return _no_chronicle()
        cursor.execute(
            "SELECT * FROM character_spend_requests WHERE id = %s AND campaign_id = %s FOR UPDATE",
            (request_id, campaign_id),
        )
        req = cursor.fetchone()
        if not req:
            db.rollback()
            return jsonify({"error": "Spend not found"}), 404
        payload = _json(req.get("payload"), {})
        payload["kind"] = req["kind"]
        now = _now()

        if action in ("approve", "reject") and req["status"] != "pending":
            db.rollback()
            return _error("This spend was already decided.", "not_pending", 409)
        if action == "reverse" and req["status"] != "approved":
            db.rollback()
            return _error("Only an approved spend can be reversed.", "not_approved", 409)

        if action == "reject":
            cursor.execute(
                "UPDATE character_spend_requests SET status = 'rejected', approver = 'user', "
                "resolved_by = %s, resolved_at = %s, reason = %s WHERE id = %s AND status = 'pending'",
                (user_id, now, reason, request_id),
            )
        else:
            cursor.execute("SELECT * FROM characters WHERE id = %s FOR UPDATE", (req["character_id"],))
            ch = cursor.fetchone()
            if not ch:
                db.rollback()
                return jsonify({"error": "Character not found"}), 404
            try:
                state = _state(ch)
            except SheetDataError as e:
                db.rollback()
                return _damaged(e, req["character_id"])
            if action == "approve":
                # The check again on today's sheet (another spend may have used the balance).
                check = _rule_check(state, payload, _settings(cursor, campaign_id))
                if not check["ok"] and data.get("confirm_house_rule") is not True:
                    cursor.execute(
                        "UPDATE character_spend_requests SET rule_check = %s WHERE id = %s AND status = 'pending'",
                        (json.dumps(check), request_id),
                    )
                    db.commit()
                    return jsonify({
                        "error": "This spend breaks the rules as the sheet is now (a house rule). "
                                 "Approve it again to confirm.",
                        "error_code": "now_house_rule",
                        "rule_check": check,
                        "request": _fetch_request(cursor, request_id),
                    }), 409
                new_state, before, after = apply_spend(state, payload)
                _write_sheet(cursor, req["character_id"], new_state, req["kind"])
                cursor.execute(
                    "UPDATE character_spend_requests SET status = 'approved', approver = 'user', "
                    "resolved_by = %s, resolved_at = %s, reason = %s, rule_check = %s, "
                    "before_state = %s, after_state = %s WHERE id = %s AND status = 'pending'",
                    (user_id, now, reason, json.dumps(check), json.dumps(before), json.dumps(after), request_id),
                )
            else:
                try:
                    new_state = reverse_spend(
                        state, req["kind"], _json(req.get("before_state"), {}), _json(req.get("after_state"), {})
                    )
                except SheetChanged:
                    db.rollback()
                    return _error(
                        "The sheet changed since this spend was applied (a later spend or an edit). "
                        "Reverse the later spends first.",
                        "sheet_changed",
                        409,
                    )
                _write_sheet(cursor, req["character_id"], new_state, req["kind"])
                cursor.execute(
                    "UPDATE character_spend_requests SET status = 'reversed', reversed_by = %s, "
                    "reversed_at = %s, reverse_reason = %s WHERE id = %s AND status = 'approved'",
                    (user_id, now, reason, request_id),
                )
        if cursor.rowcount != 1:
            db.rollback()
            return _error("This spend was already decided.", "not_pending", 409)
        db.commit()
        logger.info("spend request %s: %s by user %s", request_id, safe_log_value(action), user_id)
        return jsonify({"request": _fetch_request(cursor, request_id)}), 200
    except Exception as e:
        db.rollback()
        logger.error("resolve_spend_request: %s", safe_log_value(e))
        return jsonify({"error": "Could not update the spend"}), 500
    finally:
        db.close()
