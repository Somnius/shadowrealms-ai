"""
Message routes for ShadowRealms AI
Handles saving and retrieving messages for campaigns and locations
"""

import os
from typing import Optional

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import (
    ensure_location_reads_table,
    get_db,
    ensure_character_portrait_url_column,
    ensure_messages_ai_message_kind_column,
    ensure_messages_speaker_mode_column,
    ensure_locations_player_access_columns,
    ensure_users_player_profile_columns,
    ensure_campaign_players_active_character_id_column,
    ensure_messages_reply_to_column,
)
from services.location_access import (
    closed_location_error_response,
    user_can_bypass_closed_location,
)
from services.playing_character import effective_playing_character_id
from services.assistant_grants import ALLOWED_ROLES, assistant_post_allowed
from services.dice_markers import is_dice_kind, sanitize_marker
from services.message_actions import (
    delete_decision,
    dice_pair_kinds,
    hidden_dice_sql_filter,
    is_hidden_kind,
    older_page,
    parse_older_page,
    reply_payload,
    reply_target_error,
)
from datetime import datetime
from services.message_time_format import format_message_time
import logging
from services.log_safety import safe_log_value

logger = logging.getLogger(__name__)

messages_bp = Blueprint('messages', __name__)


def _int_jwt_user_id(raw) -> Optional[int]:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _campaign_accessible_to_viewer(cursor, campaign_id: int, user_id: int) -> bool:
    """Creator / roster member, or site admin (any active campaign)."""
    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    u = cursor.fetchone()
    if u and u.get("role") == "admin":
        cursor.execute("SELECT id FROM campaigns WHERE id = %s", (campaign_id,))
        return cursor.fetchone() is not None
    cursor.execute(
        """
        SELECT id FROM campaigns
        WHERE id = %s AND (created_by = %s OR id IN (
            SELECT campaign_id FROM campaign_players WHERE user_id = %s
        ))
        """,
        (campaign_id, user_id, user_id),
    )
    return cursor.fetchone() is not None


def _staff_kind_from_row(row) -> Optional[str]:
    """When speaker_mode is staff: site admin/helper vs chronicle storyteller."""
    pr = (row.get('poster_role') or row.get('user_role') or '').lower()
    if pr in ('admin', 'helper'):
        return 'admin'
    cb = row.get('campaign_created_by')
    uid = row.get('user_id')
    if cb is not None and uid is not None and str(cb) == str(uid):
        return 'storyteller'
    return 'staff'


# One chat row + its author, character and the message it replies to (if any).
_MESSAGE_SELECT = """
    SELECT
        m.id,
        m.campaign_id,
        m.location_id,
        m.user_id,
        m.character_id,
        m.message_type,
        m.content,
        m.role,
        m.created_at,
        u.username,
        u.role as poster_role,
        u.player_avatar_url as player_avatar_url,
        c.name as character_name,
        c.portrait_url as character_portrait_url,
        m.ai_message_kind,
        m.speaker_mode,
        camp.created_by as campaign_created_by,
        rm.id as reply_id,
        SUBSTR(rm.content, 1, 400) as reply_content,
        rm.role as reply_role,
        rm.speaker_mode as reply_speaker_mode,
        rm.ai_message_kind as reply_kind,
        ru.username as reply_username,
        rc.name as reply_character_name
    FROM messages m
    JOIN users u ON m.user_id = u.id
    JOIN campaigns camp ON m.campaign_id = camp.id
    LEFT JOIN characters c ON m.character_id = c.id
    LEFT JOIN messages rm ON rm.id = m.reply_to_id
    LEFT JOIN users ru ON ru.id = rm.user_id
    LEFT JOIN characters rc ON rc.id = rm.character_id
"""


def _message_dict_from_row(row, allow_hidden: bool = True) -> dict:
    cid = row.get('character_id')
    raw_sm = row.get('speaker_mode')
    if raw_sm:
        sm = str(raw_sm).strip().lower()
    else:
        sm = 'character' if cid else 'player'
    staff_kind = None
    if sm == 'staff':
        staff_kind = _staff_kind_from_row(row)

    return {
        'id': row['id'],
        'campaign_id': row['campaign_id'],
        'location_id': row['location_id'],
        'user_id': row['user_id'],
        'character_id': row['character_id'],
        'message_type': row['message_type'],
        'content': row['content'],
        'role': row['role'],
        'created_at': row['created_at'],
        'time_display': format_message_time(row['created_at']),
        'username': row['username'],
        'character_name': row['character_name'],
        'character_portrait_url': row['character_portrait_url'],
        'player_avatar_url': row.get('player_avatar_url'),
        'ai_message_kind': row.get('ai_message_kind'),
        'poster_role': (row.get('poster_role') or row.get('user_role') or ''),
        'speaker_mode': sm,
        'staff_kind': staff_kind,
        'reply_to': reply_payload(row, allow_hidden),
    }

@messages_bp.route('/campaigns/<int:campaign_id>/locations/<int:location_id>', methods=['GET'])
@jwt_required()
def get_messages(campaign_id, location_id):
    """Get messages for a specific location.

    Query params:
    - limit / offset: classic pagination (default limit 50).
    - since_id: only messages with id > since_id (for real-time polling).
    - recent=1: last N messages by id (newest first in DB, returned ascending).
    - before_id=<id>&limit=<n> (n <= 100, default 50): older history, the n messages before
      before_id in chronological order, as {"messages": [...], "has_more": bool}.
    Every message carries reply_to: {id, author, excerpt, role} or null.
    """
    try:
        user_id = _int_jwt_user_id(get_jwt_identity())
        if user_id is None:
            return jsonify({'error': 'Invalid session'}), 401

        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        since_id = request.args.get('since_id', type=int)
        recent = request.args.get('recent', type=int) == 1
        before_id = request.args.get('before_id')

        conn = get_db()
        cursor = conn.cursor()
        ensure_character_portrait_url_column(cursor)
        ensure_messages_ai_message_kind_column(cursor)
        ensure_messages_speaker_mode_column(cursor)
        ensure_messages_reply_to_column(cursor)
        ensure_locations_player_access_columns(cursor)
        ensure_users_player_profile_columns(cursor)
        conn.commit()

        if not _campaign_accessible_to_viewer(cursor, campaign_id, user_id):
            return jsonify({'error': 'Unauthorized or campaign not found'}), 403

        cursor.execute(
            """
            SELECT l.is_open, l.closure_reason, c.game_system
            FROM locations l
            JOIN campaigns c ON c.id = l.campaign_id
            WHERE l.id = %s AND l.campaign_id = %s
            """,
            (location_id, campaign_id),
        )
        loc_row = cursor.fetchone()
        if not loc_row:
            return jsonify({'error': 'Location not found'}), 404
        raw_open = loc_row.get("is_open")
        is_open_loc = True if raw_open is None else bool(raw_open) if not isinstance(raw_open, (int, float)) else raw_open != 0
        if not is_open_loc and not user_can_bypass_closed_location(cursor, user_id, campaign_id):
            return closed_location_error_response(
                loc_row.get("closure_reason"),
                loc_row.get("game_system"),
            )

        # Determine visibility permissions for hidden dice rolls.
        # Hidden dice markers/final messages are only visible to:
        # - site admins/helpers
        # - campaign creator ("storyteller")
        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        urow = cursor.fetchone() or {}
        user_role = (urow.get('role') or '').strip().lower()

        cursor.execute("SELECT created_by FROM campaigns WHERE id = %s", (campaign_id,))
        crow = cursor.fetchone() or {}
        campaign_creator_id = crow.get('created_by')
        allow_hidden_dice = user_role in ('admin', 'helper') or (
            campaign_creator_id is not None and str(campaign_creator_id) == str(user_id)
        )
        
        base_select = _MESSAGE_SELECT + " WHERE m.campaign_id = %s AND m.location_id = %s"
        # Hidden rolls are filtered in SQL, so LIMIT counts only rows this viewer sees.
        if not allow_hidden_dice:
            base_select += hidden_dice_sql_filter()

        older = parse_older_page(before_id, request.args.get('limit')) if before_id is not None else None
        if before_id is not None and older is None:
            return jsonify({'error': 'before_id must be a positive message id', 'code': 'invalid_before_id'}), 400

        if older is not None:
            # Older history: the page before before_id, chronological, plus whether more exist.
            b_id, lim = older
            cursor.execute(
                base_select + " AND m.id < %s ORDER BY m.id DESC LIMIT %s",
                (campaign_id, location_id, b_id, lim + 1),
            )
            page, has_more = older_page(cursor.fetchall(), lim)
            return jsonify({
                'messages': [_message_dict_from_row(r, allow_hidden_dice) for r in page],
                'has_more': has_more,
            }), 200

        if since_id is not None and since_id > 0:
            lim = min(max(request.args.get('limit', 100, type=int), 1), 200)
            cursor.execute(
                base_select + " AND m.id > %s ORDER BY m.id ASC LIMIT %s",
                (campaign_id, location_id, since_id, lim),
            )
        elif recent:
            lim = min(max(limit, 1), 200)
            cursor.execute(
                base_select + " ORDER BY m.id DESC LIMIT %s",
                (campaign_id, location_id, lim),
            )
        else:
            cursor.execute(
                base_select + " ORDER BY m.created_at ASC LIMIT %s OFFSET %s",
                (campaign_id, location_id, limit, offset),
            )

        rows = cursor.fetchall()
        if recent:
            rows = list(reversed(rows))

        messages = []
        for row in rows:
            if is_hidden_kind(row.get('ai_message_kind')) and not allow_hidden_dice:
                continue
            messages.append(_message_dict_from_row(row, allow_hidden_dice))

        return jsonify(messages), 200
        
    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        return jsonify({'error': 'Failed to fetch messages'}), 500


@messages_bp.route('/campaigns/<int:campaign_id>/locations/<int:location_id>/read-state', methods=['GET'])
@jwt_required()
def get_location_read_state(campaign_id, location_id):
    """Get per-character read state + first unread message marker."""
    try:
        user_id = _int_jwt_user_id(get_jwt_identity())
        if user_id is None:
            return jsonify({'error': 'Invalid session'}), 401
        character_id = request.args.get('character_id', type=int)
        if not character_id:
            return jsonify({'error': 'character_id is required'}), 400

        conn = get_db()
        cursor = conn.cursor()
        ensure_location_reads_table(cursor)
        ensure_locations_player_access_columns(cursor)
        conn.commit()

        if not _campaign_accessible_to_viewer(cursor, campaign_id, user_id):
            return jsonify({'error': 'Unauthorized or campaign not found'}), 403

        cursor.execute(
            """
            SELECT l.is_open, l.closure_reason, c.game_system
            FROM locations l
            JOIN campaigns c ON c.id = l.campaign_id
            WHERE l.id = %s AND l.campaign_id = %s
            """,
            (location_id, campaign_id),
        )
        loc_row = cursor.fetchone()
        if not loc_row:
            return jsonify({'error': 'Location not found'}), 404
        raw_open = loc_row.get("is_open")
        is_open_loc = True if raw_open is None else bool(raw_open) if not isinstance(raw_open, (int, float)) else raw_open != 0
        if not is_open_loc and not user_can_bypass_closed_location(cursor, user_id, campaign_id):
            return closed_location_error_response(
                loc_row.get("closure_reason"),
                loc_row.get("game_system"),
            )

        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        viewer = cursor.fetchone() or {}
        is_site_admin = viewer.get("role") == "admin"
        if is_site_admin:
            cursor.execute("""
                SELECT id FROM characters
                WHERE id = %s AND campaign_id = %s AND is_active = TRUE
            """, (character_id, campaign_id))
        else:
            cursor.execute("""
                SELECT id FROM characters
                WHERE id = %s AND user_id = %s AND campaign_id = %s AND is_active = TRUE
            """, (character_id, user_id, campaign_id))
        if not cursor.fetchone():
            return jsonify({'error': 'Character not found'}), 404

        # Fetch current read state
        cursor.execute("""
            SELECT last_read_message_id, last_read_at
            FROM location_reads
            WHERE character_id = %s AND location_id = %s
        """, (character_id, location_id))
        rs = cursor.fetchone() or {}
        last_read_message_id = rs.get('last_read_message_id')
        last_read_at = rs.get('last_read_at')

        # Find first unread message
        if last_read_message_id:
            cursor.execute("""
                SELECT id, created_at
                FROM messages
                WHERE campaign_id = %s
                  AND location_id = %s
                  AND id > %s
                  AND COALESCE(ai_message_kind, '') NOT LIKE 'dice_animation%%'
                ORDER BY id ASC
                LIMIT 1
            """, (campaign_id, location_id, last_read_message_id))
        else:
            cursor.execute("""
                SELECT id, created_at
                FROM messages
                WHERE campaign_id = %s
                  AND location_id = %s
                  AND COALESCE(ai_message_kind, '') NOT LIKE 'dice_animation%%'
                ORDER BY id ASC
                LIMIT 1
            """, (campaign_id, location_id))
        first = cursor.fetchone()

        return jsonify({
            'campaign_id': campaign_id,
            'location_id': location_id,
            'character_id': character_id,
            'last_read_message_id': last_read_message_id,
            'last_read_at': last_read_at,
            'first_unread_message_id': first['id'] if first and (not last_read_message_id or first['id'] != last_read_message_id) else None,
            'first_unread_at': first['created_at'] if first and (not last_read_message_id or first['id'] != last_read_message_id) else None
        }), 200

    except Exception as e:
        logger.error(f"Error fetching read state: {e}")
        return jsonify({'error': 'Failed to fetch read state'}), 500


@messages_bp.route('/campaigns/<int:campaign_id>/locations/<int:location_id>/read-state', methods=['POST'])
@jwt_required()
def set_location_read_state(campaign_id, location_id):
    """Set per-character last read message for a location."""
    try:
        user_id = _int_jwt_user_id(get_jwt_identity())
        if user_id is None:
            return jsonify({'error': 'Invalid session'}), 401
        data = request.get_json() or {}
        character_id = data.get('character_id')
        last_read_message_id = data.get('last_read_message_id')

        if not character_id or not last_read_message_id:
            return jsonify({'error': 'character_id and last_read_message_id are required'}), 400

        conn = get_db()
        cursor = conn.cursor()
        ensure_location_reads_table(cursor)

        if not _campaign_accessible_to_viewer(cursor, campaign_id, user_id):
            return jsonify({'error': 'Unauthorized or campaign not found'}), 403

        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        viewer = cursor.fetchone() or {}
        is_site_admin = viewer.get("role") == "admin"
        if is_site_admin:
            cursor.execute("""
                SELECT id FROM characters
                WHERE id = %s AND campaign_id = %s AND is_active = TRUE
            """, (character_id, campaign_id))
        else:
            cursor.execute("""
                SELECT id FROM characters
                WHERE id = %s AND user_id = %s AND campaign_id = %s AND is_active = TRUE
            """, (character_id, user_id, campaign_id))
        if not cursor.fetchone():
            return jsonify({'error': 'Character not found'}), 404

        # Verify message is in this location/campaign
        cursor.execute("""
            SELECT id, created_at
            FROM messages
            WHERE id = %s AND campaign_id = %s AND location_id = %s
        """, (last_read_message_id, campaign_id, location_id))
        msg = cursor.fetchone()
        if not msg:
            return jsonify({'error': 'Message not found'}), 404

        now = datetime.now()
        cursor.execute("""
            INSERT INTO location_reads (character_id, location_id, last_read_message_id, last_read_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (character_id, location_id)
            DO UPDATE SET
                last_read_message_id = EXCLUDED.last_read_message_id,
                last_read_at = EXCLUDED.last_read_at,
                updated_at = EXCLUDED.updated_at
        """, (character_id, location_id, last_read_message_id, msg['created_at'], now))
        conn.commit()

        # Return updated state
        cursor.execute("""
            SELECT last_read_message_id, last_read_at
            FROM location_reads
            WHERE character_id = %s AND location_id = %s
        """, (character_id, location_id))
        rs = cursor.fetchone() or {}

        # First unread after update
        cursor.execute("""
            SELECT id, created_at
            FROM messages
            WHERE campaign_id = %s
              AND location_id = %s
              AND id > %s
              AND COALESCE(ai_message_kind, '') NOT LIKE 'dice_animation%%'
            ORDER BY id ASC
            LIMIT 1
        """, (campaign_id, location_id, rs.get('last_read_message_id') or 0))
        first = cursor.fetchone()

        return jsonify({
            'campaign_id': campaign_id,
            'location_id': location_id,
            'character_id': character_id,
            'last_read_message_id': rs.get('last_read_message_id'),
            'last_read_at': rs.get('last_read_at'),
            'first_unread_message_id': first['id'] if first else None,
            'first_unread_at': first['created_at'] if first else None
        }), 200

    except Exception as e:
        logger.error(f"Error setting read state: {e}")
        return jsonify({'error': 'Failed to set read state'}), 500

@messages_bp.route('/campaigns/<int:campaign_id>/locations/<int:location_id>', methods=['POST'])
@jwt_required()
def save_message(campaign_id, location_id):
    """Save a new message"""
    try:
        user_id = _int_jwt_user_id(get_jwt_identity())
        if user_id is None:
            return jsonify({'error': 'Invalid session'}), 401
        data = request.get_json()
        
        if not data or 'content' not in data:
            return jsonify({'error': 'Message content is required'}), 400
        
        content = data.get('content')
        if not isinstance(content, str):
            return jsonify({'error': 'Message content must be a string'}), 400
        message_type = data.get('message_type', 'ic')  # ic, ooc, system, action
        # 'user', or 'assistant' for AI Storyteller lines; assistant is checked below
        # (services/assistant_grants.py): only text the AI endpoints handed this user, or admins.
        role = str(data.get('role') or 'user').strip().lower()
        if role not in ALLOWED_ROLES:
            return jsonify({'error': 'Invalid message role'}), 400
        character_id = data.get('character_id')
        raw_mk = data.get('ai_message_kind')
        ai_message_kind = None
        if raw_mk is not None and str(raw_mk).strip():
            mk = str(raw_mk).strip().lower()
            # Existing cleanup tags (/ai clean …, /chat …)
            if mk in ('slash_user', 'slash_assistant', 'chat_user', 'chat_assistant'):
                ai_message_kind = mk
            # Dice animation + dice-roll final reveal tags
            # Format: dice_animation:<animationId>, dice_roll:<animationId>
            # Hidden variants: dice_animation_hidden:<animationId>, dice_roll_hidden:<animationId>
            # The dice API posts these itself (services/dice_chat.py); from this endpoint only
            # site admins may (the admin-only /ai roll flow), checked below.
            elif is_dice_kind(mk):
                ai_message_kind = mk
        
        if not content.strip():
            return jsonify({'error': 'Message content cannot be empty'}), 400

        raw_reply = data.get('reply_to_id')
        reply_to_id = None
        if raw_reply is not None and raw_reply != '':
            if isinstance(raw_reply, bool):
                return jsonify({'error': 'reply_to_id must be a message id', 'code': 'invalid_reply_to'}), 400
            try:
                reply_to_id = int(raw_reply)
            except (TypeError, ValueError):
                return jsonify({'error': 'reply_to_id must be a message id', 'code': 'invalid_reply_to'}), 400
            if reply_to_id <= 0:
                return jsonify({'error': 'reply_to_id must be a message id', 'code': 'invalid_reply_to'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        ensure_character_portrait_url_column(cursor)
        ensure_messages_ai_message_kind_column(cursor)
        ensure_locations_player_access_columns(cursor)
        ensure_users_player_profile_columns(cursor)
        ensure_campaign_players_active_character_id_column(cursor)
        ensure_messages_speaker_mode_column(cursor)
        ensure_messages_reply_to_column(cursor)
        conn.commit()

        # Campaign ban from the OOC monitor (campaign_bans; site bans are separate)
        try:
            from services.ooc_monitor import create_ooc_monitor

            ooc_monitor = create_ooc_monitor()
            is_banned, ban_message = ooc_monitor.check_user_ban(user_id, campaign_id)
            
            if is_banned:
                return jsonify({
                    'error': 'You are temporarily banned',
                    'ban_message': ban_message
                }), 403
        except Exception as e:
            logger.error(f"Error checking ban status: {e}")
            # Continue if ban check fails
        
        if not _campaign_accessible_to_viewer(cursor, campaign_id, user_id):
            return jsonify({'error': 'Unauthorized or campaign not found'}), 403
        
        # Verify location exists in this campaign AND get location type + access
        cursor.execute(
            """
            SELECT l.id, l.type, l.is_open, l.closure_reason, c.game_system
            FROM locations l
            JOIN campaigns c ON c.id = l.campaign_id
            WHERE l.id = %s AND l.campaign_id = %s
            """,
            (location_id, campaign_id),
        )

        location_row = cursor.fetchone()
        if not location_row:
            return jsonify({'error': 'Location not found'}), 404

        raw_open = location_row.get("is_open")
        is_open_loc = True if raw_open is None else bool(raw_open) if not isinstance(raw_open, (int, float)) else raw_open != 0
        if not is_open_loc and not user_can_bypass_closed_location(cursor, user_id, campaign_id):
            return closed_location_error_response(
                location_row.get("closure_reason"),
                location_row.get("game_system"),
            )

        location_type = location_row['type']

        if ai_message_kind and is_dice_kind(ai_message_kind):
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            poster = cursor.fetchone() or {}
            if (poster.get('role') or '').strip().lower() != 'admin':
                conn.rollback()
                logger.warning(
                    f"Refused client-posted dice row ({safe_log_value(ai_message_kind.split(':', 1)[0])}) from user "
                    f"{safe_log_value(user_id)} in campaign {safe_log_value(campaign_id)}"
                )
                return jsonify({
                    'error': 'Dice results are posted by the server. Use the dice roller.',
                }), 403
            if ai_message_kind.startswith('dice_animation'):
                clean = sanitize_marker(content, ai_message_kind)
                if clean is None:
                    return jsonify({'error': 'Invalid dice animation marker'}), 400
                content = clean

        if role == 'assistant':
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            poster = cursor.fetchone() or {}
            if not assistant_post_allowed(
                cursor, user_id, campaign_id, location_id, content, ai_message_kind,
                poster.get('role') or '',
            ):
                conn.rollback()
                logger.warning(
                    f"Refused assistant-role message from user {safe_log_value(user_id)} in campaign {safe_log_value(campaign_id)} "
                    f"(not an AI reply issued to them)"
                )
                return jsonify({'error': 'Only the AI Storyteller can post as the Storyteller.'}), 403
        
        # CHECK FOR OOC VIOLATIONS (only for user messages, not AI; never for staff)
        ooc_warning = None
        ooc_warning_info = None
        if role == 'user':
            try:
                from services.ooc_monitor import create_ooc_monitor

                cursor.execute(
                    "SELECT u.role, c.created_by FROM users u, campaigns c WHERE u.id = %s AND c.id = %s",
                    (user_id, campaign_id),
                )
                who = cursor.fetchone() or {}
                requested_voice = str(data.get('speak_as') or data.get('voice') or '').strip().lower()
                ooc_monitor = create_ooc_monitor()
                
                is_violation, warning_msg, should_ban = ooc_monitor.check_message(
                    message=content,
                    user_id=user_id,
                    campaign_id=campaign_id,
                    location_type=location_type,
                    site_role=who.get('role'),
                    is_campaign_owner=(
                        who.get('created_by') is not None and int(who['created_by']) == int(user_id)
                    ),
                    # staff voice is validated below (only admin/helper/owner may use it, and
                    # they are exempt anyway)
                    speaker_mode=requested_voice,
                )
                
                if is_violation:
                    logger.warning(f"OOC violation detected for user {safe_log_value(user_id)}: {safe_log_value(content, 50)}")
                    ooc_warning_info = getattr(ooc_monitor, 'last_warning', None)
                    
                    if should_ban:
                        # User has been banned
                        return jsonify({
                            'error': 'OOC violation - temporarily banned',
                            'warning': warning_msg,
                            'ooc_warning_info': ooc_warning_info,
                            'violation': True
                        }), 403
                    else:
                        # Store warning to include in response
                        ooc_warning = warning_msg
                        logger.info(f"Issuing OOC warning to user {user_id}")
            except Exception as e:
                logger.error(f"Error checking OOC violation: {e}")
                # Continue if OOC check fails - don't block legitimate messages

        speaker_mode = None
        # Resolve / validate character for user-authored messages
        if role == 'user':
            speak_as = (data.get('speak_as') or data.get('voice') or 'character').strip().lower()
            if speak_as not in ('character', 'player', 'staff'):
                speak_as = 'character'

            cursor.execute("SELECT created_by FROM campaigns WHERE id = %s", (campaign_id,))
            cr = cursor.fetchone() or {}
            campaign_created_by = cr.get('created_by')
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            ur = cursor.fetchone() or {}
            site_role = (ur.get('role') or '').lower()
            is_campaign_st = (
                campaign_created_by is not None
                and str(campaign_created_by) == str(user_id)
            )
            can_staff_voice = site_role in ('admin', 'helper') or is_campaign_st

            if speak_as == 'staff':
                if not can_staff_voice:
                    return jsonify(
                        {
                            'error': (
                                'Only the chronicle Storyteller or site staff can post with staff voice.'
                            )
                        },
                    ), 403
                character_id = None
                speaker_mode = 'staff'
            elif speak_as == 'player':
                character_id = None
                speaker_mode = 'player'
            else:
                speaker_mode = 'character'
                active_cid = effective_playing_character_id(
                    cursor, int(user_id), int(campaign_id)
                )

                if active_cid is not None:
                    _ichar = (
                        "(is_active IS NULL OR is_active IS TRUE)"
                        if os.getenv("DATABASE_TYPE", "sqlite").lower() == "postgresql"
                        else "(is_active IS NULL OR is_active = 1)"
                    )
                    cursor.execute(
                        f"""
                        SELECT id FROM characters
                        WHERE id = %s AND user_id = %s AND campaign_id = %s
                          AND {_ichar}
                        """,
                        (active_cid, user_id, campaign_id),
                    )
                    if not cursor.fetchone():
                        return jsonify(
                            {
                                'error': (
                                    'Your playing character is not set for this campaign. '
                                    'Open Player Profile or chronicle settings.'
                                )
                            }
                        ), 400
                    if character_id is not None and int(character_id) != int(active_cid):
                        return jsonify(
                            {
                                'error': (
                                    'You can only post as your playing character '
                                    '(set in Player Profile or chronicle).'
                                )
                            }
                        ), 400
                    character_id = active_cid
                elif character_id is not None:
                    cursor.execute(
                        """
                        SELECT id FROM characters
                        WHERE id = %s AND user_id = %s AND campaign_id = %s AND is_active = TRUE
                        """,
                        (character_id, user_id, campaign_id),
                    )
                    if not cursor.fetchone():
                        return jsonify({'error': 'Invalid character for this campaign'}), 400
                else:
                    cursor.execute(
                        """
                        SELECT id FROM characters
                        WHERE user_id = %s AND campaign_id = %s AND is_active = TRUE
                        ORDER BY id ASC
                        LIMIT 1
                        """,
                        (user_id, campaign_id),
                    )
                    fallback = cursor.fetchone()
                    if fallback:
                        character_id = fallback['id']

        if reply_to_id is not None:
            # Same room, still there, and visible to the poster (hidden rolls: staff only).
            cursor.execute(
                "SELECT id, campaign_id, location_id, ai_message_kind FROM messages WHERE id = %s",
                (reply_to_id,),
            )
            target = cursor.fetchone()
            cursor.execute(
                "SELECT u.role, c.created_by FROM users u, campaigns c WHERE u.id = %s AND c.id = %s",
                (user_id, campaign_id),
            )
            vr = cursor.fetchone() or {}
            sees_hidden = (vr.get('role') or '').strip().lower() in ('admin', 'helper') or (
                vr.get('created_by') is not None and str(vr.get('created_by')) == str(user_id)
            )
            reply_err = reply_target_error(target, campaign_id, location_id, sees_hidden)
            if reply_err:
                conn.rollback()
                return jsonify({
                    'error': 'The message you are replying to is not in this room any more.',
                    'code': reply_err,
                }), 400

        # Insert message. The quoted message can be deleted between the check above and here;
        # the foreign key then refuses the row, which is the same "not found" answer.
        try:
            cursor.execute(
                """
                INSERT INTO messages (
                    campaign_id, location_id, user_id, character_id,
                    message_type, content, role, created_at, ai_message_kind, speaker_mode,
                    reply_to_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    campaign_id,
                    location_id,
                    user_id,
                    character_id,
                    message_type,
                    content,
                    role,
                    datetime.now().isoformat(),
                    ai_message_kind,
                    speaker_mode,
                    reply_to_id,
                ),
            )
        except Exception as e:  # noqa: BLE001
            constraint = getattr(getattr(e, 'diag', None), 'constraint_name', None) or ''
            if (reply_to_id is None or type(e).__name__ not in ('ForeignKeyViolation', 'IntegrityError')
                    or (constraint and 'reply_to' not in constraint)):
                raise
            conn.rollback()
            return jsonify({
                'error': 'The message you are replying to is not in this room any more.',
                'code': 'reply_target_not_found',
            }), 400

        result = cursor.fetchone()
        message_id = result['id']
        conn.commit()
        
        # Store message embedding in ChromaDB for semantic search
        try:
            from services.rag_service import get_rag_service
            rag_service = get_rag_service()
            
            # Get character name if applicable
            character_name = None
            if character_id:
                cursor.execute("SELECT name FROM characters WHERE id = %s", (character_id,))
                char = cursor.fetchone()
                if char:
                    character_name = char.get('name') if isinstance(char, dict) else char[0]
            
            # Embed the message
            rag_service.store_message_embedding(
                message_id=message_id,
                campaign_id=campaign_id,
                location_id=location_id,
                user_id=user_id,
                content=content,
                role=role,
                character_name=character_name
            )
            logger.info(f"Message {message_id} embedded for semantic search")
        except Exception as e:
            # Don't fail the request if embedding fails
            logger.warning(f"Failed to embed message: {e}")
        
        # Fetch the saved message with joined data
        cursor.execute(_MESSAGE_SELECT + " WHERE m.id = %s", (message_id,))

        row = cursor.fetchone()
        saved_message = _message_dict_from_row(row)
        
        logger.info(f"Message saved: ID={safe_log_value(message_id)}, Campaign={safe_log_value(campaign_id)}, "
                    f"Location={safe_log_value(location_id)}")
        
        # Build response
        response_data = {
            'message': 'Message saved successfully',
            'data': saved_message
        }
        
        # Include OOC warning if there was a violation
        if ooc_warning:
            response_data['ooc_warning'] = ooc_warning
            if ooc_warning_info:
                response_data['ooc_warning_info'] = ooc_warning_info
        
        return jsonify(response_data), 201
        
    except Exception as e:
        logger.error(f"Error saving message: {e}")
        return jsonify({'error': 'Failed to save message'}), 500

@messages_bp.route('/messages/<int:message_id>', methods=['DELETE'])
@jwt_required()
def delete_message(message_id):
    """
    Delete a message (services/message_actions.py delete_decision):
    - the chronicle's owner (Storyteller) and site admins: any message;
    - players: their own messages, but not dice rows or AI (Storyteller) messages.
    Deleting a roll's result line or marker removes both rows of that roll.
    Returns {"deleted_ids": [...]}; 403 with code message_not_yours / dice_message_staff_only /
    ai_message_staff_only. The messages trigger bumps the room's reset counter, so other clients
    refetch the room (SSE "changed" with deleted=true).
    """
    try:
        user_id = _int_jwt_user_id(get_jwt_identity())
        if user_id is None:
            return jsonify({'error': 'Invalid session'}), 401

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT m.id, m.user_id, m.role, m.ai_message_kind, m.campaign_id, m.location_id,
                   c.created_by
            FROM messages m
            JOIN campaigns c ON m.campaign_id = c.id
            WHERE m.id = %s
            """,
            (message_id,),
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Message not found', 'code': 'message_not_found'}), 404

        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        actor = cursor.fetchone() or {}
        site_role = (actor.get('role') or '').strip().lower()

        # Not a member and not staff: same answer as a missing message (no probing of ids).
        if not _campaign_accessible_to_viewer(cursor, row['campaign_id'], user_id):
            return jsonify({'error': 'Message not found', 'code': 'message_not_found'}), 404

        # A hidden roll doesn't exist for a player who can't see it (no 403 that confirms it).
        if is_hidden_kind(row.get('ai_message_kind')) and site_role not in ('admin', 'helper') and (
            row.get('created_by') is None or str(row.get('created_by')) != str(user_id)
        ):
            return jsonify({'error': 'Message not found', 'code': 'message_not_found'}), 404

        allowed, code = delete_decision(row, user_id, site_role, row.get('created_by'))
        if not allowed:
            text = {
                'dice_message_staff_only': 'Only the Storyteller or an admin can delete dice rolls.',
                'ai_message_staff_only': 'Only the Storyteller or an admin can delete Storyteller messages.',
            }.get(code, 'You can only delete your own messages.')
            return jsonify({'error': text, 'code': code}), 403

        pair = dice_pair_kinds(row.get('ai_message_kind'))
        if pair:
            placeholders = ', '.join(['%s'] * len(pair))
            cursor.execute(
                f"""
                DELETE FROM messages
                WHERE campaign_id = %s AND location_id = %s
                  AND LOWER(COALESCE(ai_message_kind, '')) IN ({placeholders})
                RETURNING id
                """,
                (row['campaign_id'], row['location_id'], *pair),
            )
        else:
            cursor.execute("DELETE FROM messages WHERE id = %s RETURNING id", (message_id,))
        deleted_ids = sorted(int(r['id']) for r in cursor.fetchall())
        conn.commit()

        logger.info("Messages deleted: IDs=%s by User=%s", deleted_ids, user_id)

        # A deleted line shouldn't come back as AI memory (best effort; never fails the delete).
        try:
            from services.rag_service import get_rag_service

            get_rag_service().delete_message_embeddings(deleted_ids, row['campaign_id'])
        except Exception as e:
            logger.warning("Failed to drop message embeddings: %s", safe_log_value(e))

        return jsonify({'message': 'Message deleted successfully', 'deleted_ids': deleted_ids}), 200

    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        return jsonify({'error': 'Failed to delete message'}), 500
