"""
Live updates + chat sidebar data for the v0.9 shell (kept out of routes/messages.py on purpose).

- POST /api/campaigns/<id>/events/ticket   JWT → 60 s stream ticket (see services/live_events.py)
- GET  /api/campaigns/<id>/events?ticket=  Server-Sent Events: hello / changed / bye, ": ping" keep-alives.
       The ticket is single-use. Every POLL_SECONDS the stream reads campaign_activity.version (one
       primary-key row, bumped by a trigger on messages) with a pooled connection it holds only for
       that query; when the version moved it reads campaign_location_activity for the campaign and
       tells the browser which room changed; the browser then fetches with ?since_id=.
       Only rooms the viewer may read are reported (closed rooms only for admin/helper/storyteller).
       Streams end after ~55 s (event "bye"); concurrency is capped (StreamSlots).
       nginx must not buffer this path (nginx/nginx.conf).
- GET  /api/campaigns/<id>/unread[?seen=lid:id,...]  per-room unread counts for the room list
       (read state of the user's playing character; `seen` for users without one, e.g. admins).
- GET  /api/campaigns/<id>/roster          members with their playing character (member panel).

Authorization everywhere: campaign creator, roster member, or site admin.
"""

from __future__ import annotations

import logging
import os
import time

from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from database import (
    ensure_campaign_players_active_character_id_column,
    ensure_location_reads_table,
    ensure_messages_ai_message_kind_column,
    ensure_users_player_profile_columns,
    get_db,
    poll_db,
)
from services.live_events import (
    SSE_PING,
    StreamSlots,
    TicketLedger,
    activity_from_rows,
    activity_last_ids,
    diff_activity,
    make_ticket,
    parse_seen,
    read_ticket_claims,
    sse,
)
from services.location_access import fetch_readable_location_ids
from services.playing_character import effective_playing_character_id

logger = logging.getLogger(__name__)

events_bp = Blueprint("events", __name__)

STREAM_SECONDS = float(os.environ.get("SR_EVENTS_STREAM_SECONDS", "55"))
POLL_SECONDS = float(os.environ.get("SR_EVENTS_POLL_SECONDS", "1"))
PING_SECONDS = 10.0
READABLE_REFRESH_SECONDS = 15.0  # re-check which rooms the viewer may read (room closed/opened)
SLOTS = StreamSlots(
    total=int(os.environ.get("SR_EVENTS_MAX_STREAMS", "64")),
    per_user=int(os.environ.get("SR_EVENTS_MAX_STREAMS_PER_USER", "4")),
)


def _secret() -> str:
    return current_app.config.get("JWT_SECRET_KEY") or current_app.config.get("SECRET_KEY") or ""


_ledger = None


def _ticket_ledger() -> TicketLedger:
    global _ledger
    if _ledger is None:
        from services.app_security import get_throttle

        _ledger = TicketLedger(get_throttle().store)  # Redis, in-memory fallback
    return _ledger


def _uid():
    try:
        return int(get_jwt_identity())
    except (TypeError, ValueError):
        return None


def _viewer(cursor, campaign_id: int, user_id: int):
    """(allowed, site_role, is_storyteller)."""
    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    u = cursor.fetchone() or {}
    role = (u.get("role") or "").strip().lower()
    cursor.execute("SELECT created_by FROM campaigns WHERE id = %s", (campaign_id,))
    c = cursor.fetchone()
    if not c:
        return False, role, False
    is_st = c.get("created_by") is not None and str(c.get("created_by")) == str(user_id)
    if role == "admin" or is_st:
        return True, role, is_st
    cursor.execute(
        "SELECT 1 FROM campaign_players WHERE campaign_id = %s AND user_id = %s",
        (campaign_id, user_id),
    )
    return cursor.fetchone() is not None, role, is_st


_CAMPAIGN_VERSION_SQL = "SELECT version FROM campaign_activity WHERE campaign_id = %s"
_ROOMS_SQL = """
    SELECT location_id, version, last_message_id, reset_version
    FROM campaign_location_activity
    WHERE campaign_id = %s
"""


def _poll(campaign_id: int, user_id: int, readable):
    """(campaign_version, room rows, readable). readable=None: (re)load the viewer's rooms."""
    with poll_db() as conn:
        cur = conn.cursor()
        cur.execute(_CAMPAIGN_VERSION_SQL, (campaign_id,))
        version = int((cur.fetchone() or {}).get("version") or 0)
        if readable is None:
            readable = fetch_readable_location_ids(cur, user_id, campaign_id)
        cur.execute(_ROOMS_SQL, (campaign_id,))
        return version, cur.fetchall(), readable


def _version_only(campaign_id: int) -> int:
    with poll_db() as conn:
        cur = conn.cursor()
        cur.execute(_CAMPAIGN_VERSION_SQL, (campaign_id,))
        return int((cur.fetchone() or {}).get("version") or 0)


@events_bp.route("/campaigns/<int:campaign_id>/events/ticket", methods=["POST"])
@jwt_required()
def events_ticket(campaign_id):
    user_id = _uid()
    if user_id is None:
        return jsonify({"error": "Invalid session"}), 401
    conn = get_db()
    try:
        allowed, _, _ = _viewer(conn.cursor(), campaign_id, user_id)
    finally:
        conn.close()
    if not allowed:
        return jsonify({"error": "Unauthorized or campaign not found"}), 403
    return jsonify({"ticket": make_ticket(_secret(), user_id, campaign_id), "expires_in": 60}), 200


@events_bp.route("/campaigns/<int:campaign_id>/events", methods=["GET"])
def events_stream(campaign_id):
    claims = read_ticket_claims(_secret(), request.args.get("ticket", ""), campaign_id)
    if claims is None:
        return jsonify({"error": "Invalid or expired ticket"}), 401
    user_id, nonce = claims
    if not _ticket_ledger().claim(nonce):
        return jsonify({"error": "Ticket already used"}), 401
    conn = get_db()
    try:
        allowed, _, _ = _viewer(conn.cursor(), campaign_id, user_id)
    finally:
        conn.close()
    if not allowed:
        return jsonify({"error": "Unauthorized or campaign not found"}), 403
    if not SLOTS.acquire(user_id):
        return jsonify({"error": "Too many live connections; falling back to polling"}), 503

    def generate():
        try:
            version, rows, readable = _poll(campaign_id, user_id, None)
            prev = activity_from_rows(rows, readable)
            yield sse("hello", {"locations": activity_last_ids(prev), "poll_seconds": POLL_SECONDS})
            started = last_ping = last_readable = time.monotonic()
            while time.monotonic() - started < STREAM_SECONDS:
                time.sleep(POLL_SECONDS)
                now = time.monotonic()
                refresh = now - last_readable >= READABLE_REFRESH_SECONDS
                try:
                    if refresh:
                        version, rows, readable = _poll(campaign_id, user_id, None)
                        last_readable = now
                    else:
                        v = _version_only(campaign_id)
                        if v == version:
                            rows = None
                        else:
                            version, rows, _ = _poll(campaign_id, user_id, readable)
                except TimeoutError:
                    rows = None  # pool busy: skip this tick
                if rows is not None:
                    cur = activity_from_rows(rows, readable)
                    for change in diff_activity(prev, cur):
                        yield sse("changed", change)
                    prev = cur
                if now - last_ping >= PING_SECONDS:
                    last_ping = now
                    yield SSE_PING
            yield sse("bye", {})
        except GeneratorExit:  # client went away
            pass
        except Exception as e:  # noqa: BLE001
            logger.error(f"events stream for campaign {campaign_id} failed: {e}")
        finally:
            SLOTS.release(user_id)

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",  # nginx: don't buffer this response
        "Connection": "keep-alive",
    }
    return Response(generate(), mimetype="text/event-stream", headers=headers)


def _hidden_filter(allow_hidden: bool) -> str:
    base = "COALESCE(ai_message_kind, '') NOT LIKE 'dice_animation%%'"
    if allow_hidden:
        return base
    return base + " AND COALESCE(ai_message_kind, '') NOT LIKE 'dice_roll_hidden%%'"


@events_bp.route("/campaigns/<int:campaign_id>/unread", methods=["GET"])
@jwt_required()
def campaign_unread(campaign_id):
    user_id = _uid()
    if user_id is None:
        return jsonify({"error": "Invalid session"}), 401
    conn = get_db()
    try:
        cursor = conn.cursor()
        ensure_location_reads_table(cursor)
        ensure_messages_ai_message_kind_column(cursor)
        ensure_campaign_players_active_character_id_column(cursor)
        conn.commit()
        allowed, role, is_st = _viewer(cursor, campaign_id, user_id)
        if not allowed:
            return jsonify({"error": "Unauthorized or campaign not found"}), 403
        allow_hidden = role in ("admin", "helper") or is_st
        character_id = effective_playing_character_id(cursor, user_id, campaign_id)
        conn.commit()  # effective_playing_character_id may backfill campaign_players

        # Rooms the viewer may read: closed rooms only for admin/helper/storyteller.
        location_ids = sorted(fetch_readable_location_ids(cursor, user_id, campaign_id))

        if character_id:
            tracking = "character"
            cursor.execute(
                "SELECT location_id, last_read_message_id FROM location_reads WHERE character_id = %s",
                (character_id,),
            )
            reads = {int(r["location_id"]): int(r["last_read_message_id"] or 0) for r in cursor.fetchall()}
        else:
            tracking = "client"
            reads = parse_seen(request.args.get("seen"))

        visible = _hidden_filter(allow_hidden)
        out = []
        for lid in location_ids:
            last_read = reads.get(lid, 0)
            cursor.execute(
                f"SELECT MAX(id) AS last_id FROM messages WHERE campaign_id = %s AND location_id = %s AND {visible}",
                (campaign_id, lid),
            )
            last_id = (cursor.fetchone() or {}).get("last_id")
            unread = 0
            first_unread = None
            if last_id and (tracking == "character" or lid in reads) and last_id > last_read:
                cursor.execute(
                    f"""
                    SELECT COUNT(*) AS n, MIN(id) AS first_id FROM (
                        SELECT id FROM messages
                        WHERE campaign_id = %s AND location_id = %s AND id > %s
                          AND user_id <> %s AND {visible}
                        ORDER BY id ASC
                        LIMIT 100
                    ) s
                    """,
                    (campaign_id, lid, last_read, user_id),
                )
                row = cursor.fetchone() or {}
                unread = int(row.get("n") or 0)
                first_unread = row.get("first_id")
            out.append({
                "location_id": lid,
                "last_message_id": last_id,
                "last_read_message_id": last_read or None,
                "unread_count": unread,
                "first_unread_id": first_unread,
            })
        conn.rollback()
        return jsonify({"tracking": tracking, "character_id": character_id, "locations": out}), 200
    except Exception as e:  # noqa: BLE001
        logger.error(f"unread summary for campaign {campaign_id} failed: {e}")
        return jsonify({"error": "Failed to load unread counts"}), 500
    finally:
        conn.close()


@events_bp.route("/campaigns/<int:campaign_id>/roster", methods=["GET"])
@jwt_required()
def campaign_roster(campaign_id):
    user_id = _uid()
    if user_id is None:
        return jsonify({"error": "Invalid session"}), 401
    conn = get_db()
    try:
        cursor = conn.cursor()
        ensure_users_player_profile_columns(cursor)
        ensure_campaign_players_active_character_id_column(cursor)
        conn.commit()
        allowed, _, _ = _viewer(cursor, campaign_id, user_id)
        if not allowed:
            return jsonify({"error": "Unauthorized or campaign not found"}), 403
        cursor.execute("SELECT created_by FROM campaigns WHERE id = %s", (campaign_id,))
        created_by = (cursor.fetchone() or {}).get("created_by")
        cursor.execute(
            """
            SELECT u.id AS user_id, u.username, u.role AS site_role, u.player_avatar_url,
                   cp.active_character_id
            FROM campaign_players cp
            JOIN users u ON u.id = cp.user_id
            WHERE cp.campaign_id = %s
            """,
            (campaign_id,),
        )
        rows = {int(r["user_id"]): dict(r) for r in cursor.fetchall()}
        if created_by is not None and int(created_by) not in rows:
            cursor.execute(
                "SELECT id AS user_id, username, role AS site_role, player_avatar_url FROM users WHERE id = %s",
                (created_by,),
            )
            r = cursor.fetchone()
            if r:
                rows[int(created_by)] = {**dict(r), "active_character_id": None}

        cursor.execute(
            """
            SELECT id, user_id, name, portrait_url FROM characters
            WHERE campaign_id = %s AND (is_active IS NULL OR is_active = TRUE)
            ORDER BY id ASC
            """,
            (campaign_id,),
        )
        chars_by_user = {}
        for c in cursor.fetchall():
            chars_by_user.setdefault(int(c["user_id"]), []).append(dict(c))

        members = []
        for uid, r in rows.items():
            own = chars_by_user.get(uid, [])
            playing = None
            if r.get("active_character_id"):
                playing = next((c for c in own if int(c["id"]) == int(r["active_character_id"])), None)
            if playing is None and len(own) == 1:
                playing = own[0]
            members.append({
                "user_id": uid,
                "username": r.get("username"),
                "site_role": r.get("site_role"),
                "player_avatar_url": r.get("player_avatar_url"),
                "is_storyteller": created_by is not None and int(created_by) == uid,
                "character": (
                    {"id": playing["id"], "name": playing["name"], "portrait_url": playing.get("portrait_url")}
                    if playing else None
                ),
            })
        members.sort(key=lambda m: (not m["is_storyteller"], (m["username"] or "").lower()))
        conn.rollback()
        return jsonify({"campaign_id": campaign_id, "members": members}), 200
    except Exception as e:  # noqa: BLE001
        logger.error(f"roster for campaign {campaign_id} failed: {e}")
        return jsonify({"error": "Failed to load members"}), 500
    finally:
        conn.close()
