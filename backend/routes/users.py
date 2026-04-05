#!/usr/bin/env python3
"""
ShadowRealms AI - Users Routes
User management and role-based operations
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from database import (
    get_db,
    ensure_users_player_profile_columns,
    ensure_character_portrait_url_column,
    ensure_characters_play_suspension_columns,
    ensure_users_allow_multi_campaign_play_column,
    ensure_users_self_switch_playing_character_column,
    ensure_users_restrict_self_join_new_chronicles_column,
    ensure_campaign_players_active_character_id_column,
)
from services.play_suspension import suspended_json
from services.gpu_monitor import gpu_monitor_service

logger = logging.getLogger(__name__)

bp = Blueprint('users', __name__)

MAX_PLAYER_AVATAR_URL_LEN = 524288


def _parse_display_timezone_payload(raw):
    """
    None / empty / 'auto' → None (client uses browser local).
    Otherwise must be a valid IANA zone name.
    """
    if raw is None:
        return None
    if isinstance(raw, str) and not raw.strip():
        return None
    s = str(raw).strip()
    if s.lower() in ("auto", "browser", "local", "default", ""):
        return None
    try:
        ZoneInfo(s)
    except Exception:
        raise ValueError(f"Invalid IANA timezone: {s}")
    return s


@bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user_me():
    """Flat user object + stats (used by SPA navbar / profile)."""
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid session"}), 422

    try:
        db = get_db()
        cursor = db.cursor()
        ensure_users_player_profile_columns(cursor)
        ensure_character_portrait_url_column(cursor)
        ensure_characters_play_suspension_columns(cursor)
        ensure_users_allow_multi_campaign_play_column(cursor)
        ensure_users_self_switch_playing_character_column(cursor)
        ensure_users_restrict_self_join_new_chronicles_column(cursor)
        ensure_campaign_players_active_character_id_column(cursor)
        db.commit()

        cursor.execute(
            """
            SELECT id, username, email, role, created_at, last_login, is_active,
                   display_timezone, player_avatar_url, active_character_id,
                   restrict_self_join_new_chronicles,
                   allow_multi_campaign_play, self_switch_playing_character
            FROM users WHERE id = %s
            """,
            (user_id,),
        )
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        active_character_id = user.get("active_character_id")
        active_character = None
        if active_character_id is not None:
            cursor.execute(
                """
                SELECT ch.id, ch.name, ch.campaign_id, ch.portrait_url, c.name AS campaign_name,
                       ch.play_suspended, ch.play_suspension_reason_code,
                       ch.play_suspension_message
                FROM characters ch
                JOIN campaigns c ON c.id = ch.campaign_id
                WHERE ch.id = %s AND ch.user_id = %s
                """,
                (active_character_id, user_id),
            )
            row = cursor.fetchone()
            if row:
                active_character = {
                    "id": row["id"],
                    "name": row["name"],
                    "campaign_id": row["campaign_id"],
                    "campaign_name": row["campaign_name"],
                    "portrait_url": row.get("portrait_url"),
                    "play_suspended": bool(row.get("play_suspended") or False),
                    "play_suspension_reason_code": row.get(
                        "play_suspension_reason_code"
                    ),
                    "play_suspension_message": row.get("play_suspension_message"),
                }
            else:
                cursor.execute(
                    "UPDATE users SET active_character_id = NULL WHERE id = %s",
                    (user_id,),
                )
                db.commit()
                active_character_id = None

        cursor.execute(
            "SELECT COUNT(*) as campaign_count FROM campaigns WHERE created_by = %s",
            (user_id,),
        )
        campaign_count = cursor.fetchone()["campaign_count"]

        cursor.execute(
            "SELECT COUNT(*) as character_count FROM characters WHERE user_id = %s",
            (user_id,),
        )
        character_count = cursor.fetchone()["character_count"]

        return jsonify(
            {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"],
                "created_at": user["created_at"],
                "last_login": user["last_login"],
                "is_active": bool(user["is_active"]),
                "display_timezone": user["display_timezone"],
                "player_avatar_url": user.get("player_avatar_url"),
                "active_character_id": active_character_id,
                "active_character": active_character,
                "restrict_self_join_new_chronicles": bool(
                    user.get("restrict_self_join_new_chronicles") or False
                ),
                "allow_multi_campaign_play": bool(
                    user.get("allow_multi_campaign_play") or False
                ),
                "self_switch_playing_character": bool(
                    user.get("self_switch_playing_character") or False
                ),
                "statistics": {
                    "campaigns_created": campaign_count,
                    "characters_owned": character_count,
                },
            }
        ), 200
    except Exception as e:
        logger.error(f"GET /users/me error: {e}")
        return jsonify({"error": "Failed to load profile"}), 500
    finally:
        if "db" in locals():
            db.close()


@bp.route('/me', methods=['PUT'])
@jwt_required()
def put_current_user_me():
    """Update timezone, OOC player avatar, or globally active character."""
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid session"}), 422

    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    allowed = ("display_timezone", "player_avatar_url", "active_character_id")
    if not any(k in data for k in allowed):
        return jsonify(
            {
                "error": (
                    "Provide at least one of: display_timezone, "
                    "player_avatar_url, active_character_id"
                )
            }
        ), 400

    try:
        db = get_db()
        cursor = db.cursor()
        ensure_users_player_profile_columns(cursor)
        ensure_characters_play_suspension_columns(cursor)
        ensure_campaign_players_active_character_id_column(cursor)
        db.commit()

        updates = []
        params = []

        if "display_timezone" in data:
            try:
                tz_norm = _parse_display_timezone_payload(data["display_timezone"])
            except ValueError as ve:
                return jsonify({"error": str(ve)}), 400
            updates.append("display_timezone = %s")
            params.append(tz_norm)

        if "player_avatar_url" in data:
            pu = data["player_avatar_url"]
            if pu is not None and pu != "":
                if (
                    not isinstance(pu, str)
                    or len(pu) > MAX_PLAYER_AVATAR_URL_LEN
                ):
                    return jsonify({"error": "player_avatar_url is invalid or too large"}), 400
            else:
                pu = None
            updates.append("player_avatar_url = %s")
            params.append(pu)

        if "active_character_id" in data:
            ac = data["active_character_id"]
            if ac is None or ac == "":
                updates.append("active_character_id = %s")
                params.append(None)
            else:
                try:
                    ac_int = int(ac)
                except (TypeError, ValueError):
                    return jsonify({"error": "active_character_id must be an integer"}), 400
                cursor.execute(
                    """
                    SELECT id, campaign_id, play_suspended, play_suspension_reason_code,
                           play_suspension_message
                    FROM characters WHERE id = %s AND user_id = %s
                    """,
                    (ac_int, user_id),
                )
                crow = cursor.fetchone()
                if not crow:
                    return jsonify({"error": "Character not found for this account"}), 404
                if bool(crow.get("play_suspended") or False):
                    cursor.close()
                    db.close()
                    return (
                        jsonify(
                            suspended_json(
                                crow.get("play_suspension_reason_code") or "custom",
                                crow.get("play_suspension_message"),
                            )
                        ),
                        403,
                    )
                ch_cid = crow.get("campaign_id")
                if ch_cid is not None:
                    cursor.execute(
                        """
                        SELECT active_character_id FROM campaign_players
                        WHERE campaign_id = %s AND user_id = %s
                        """,
                        (ch_cid, user_id),
                    )
                    cp_row = cursor.fetchone()
                    cp_ac = cp_row.get("active_character_id") if cp_row else None
                    if cp_ac is not None and int(cp_ac) != int(ac_int):
                        cursor.close()
                        db.close()
                        return (
                            jsonify(
                                {
                                    "error": (
                                        "Switching to another character in that chronicle "
                                        "requires storyteller approval (use chronicle settings "
                                        "or ask your ST)."
                                    ),
                                    "error_code": "playing_character_switch_requires_storyteller",
                                }
                            ),
                            403,
                        )
                updates.append("active_character_id = %s")
                params.append(ac_int)

        if not updates:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(user_id)
        cursor.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = %s",
            params,
        )
        if "active_character_id" in data and data.get("active_character_id") not in (
            None,
            "",
        ):
            try:
                sync_ac = int(data["active_character_id"])
            except (TypeError, ValueError):
                sync_ac = None
            else:
                cursor.execute(
                    "SELECT campaign_id FROM characters WHERE id = %s AND user_id = %s",
                    (sync_ac, user_id),
                )
                srow = cursor.fetchone()
                if srow and srow.get("campaign_id") is not None:
                    cursor.execute(
                        """
                        UPDATE campaign_players SET active_character_id = %s
                        WHERE campaign_id = %s AND user_id = %s
                        """,
                        (sync_ac, srow["campaign_id"], user_id),
                    )
        db.commit()
    except Exception as e:
        logger.error(f"PUT /users/me error: {e}")
        if "db" in locals():
            db.rollback()
        return jsonify({"error": "Failed to save profile"}), 500
    finally:
        if "db" in locals():
            db.close()

    return get_current_user_me()


@bp.route('/', methods=['GET'])
@jwt_required()
def get_users():
    """Get all users (admin only)"""
    try:
        current_user_id = get_jwt_identity()
        
        # Check if current user is admin
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user or current_user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Get all users
        cursor.execute("""
            SELECT id, username, email, role, created_at, last_login, is_active, display_timezone
            FROM users
            ORDER BY created_at DESC
        """)
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row['id'],
                'username': row['username'],
                'email': row['email'],
                'role': row['role'],
                'created_at': row['created_at'],
                'last_login': row['last_login'],
                'is_active': bool(row['is_active']),
                'display_timezone': row['display_timezone'],
            })
        
        return jsonify({
            'users': users,
            'total': len(users)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({'error': 'Failed to retrieve users'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    """Get specific user by ID"""
    try:
        current_user_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Users can only view their own profile unless they're admin/helper
        if current_user['role'] not in ['admin', 'helper'] and current_user_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get target user
        cursor.execute("""
            SELECT id, username, email, role, created_at, last_login, is_active, display_timezone
            FROM users WHERE id = %s
        """, (user_id,))
        
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user statistics
        cursor.execute("""
            SELECT COUNT(*) as campaign_count
            FROM campaigns WHERE created_by = %s
        """, (user_id,))
        
        campaign_count = cursor.fetchone()['campaign_count']
        
        cursor.execute("""
            SELECT COUNT(*) as character_count
            FROM characters WHERE user_id = %s
        """, (user_id,))
        
        character_count = cursor.fetchone()['character_count']
        
        return jsonify({
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role'],
                'created_at': user['created_at'],
                'last_login': user['last_login'],
                'is_active': bool(user['is_active']),
                'display_timezone': user['display_timezone'],
            },
            'statistics': {
                'campaigns_created': campaign_count,
                'characters_owned': character_count
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return jsonify({'error': 'Failed to retrieve user'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    """Update user information (admin or self)"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check permissions
        if current_user['role'] not in ['admin', 'helper'] and current_user_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get target user
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        target_user = cursor.fetchone()
        
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Update fields
        updates = []
        params = []
        
        # Username update
        if 'username' in data and data['username'] != target_user['username']:
            # Check if username is already taken
            cursor.execute("SELECT id FROM users WHERE username = %s AND id != %s", (data['username'], user_id))
            if cursor.fetchone():
                return jsonify({'error': 'Username already taken'}), 409
            
            updates.append("username = %s")
            params.append(data['username'])
        
        # Email update
        if 'email' in data and data['email'] != target_user['email']:
            # Check if email is already taken
            cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (data['email'], user_id))
            if cursor.fetchone():
                return jsonify({'error': 'Email already taken'}), 409
            
            updates.append("email = %s")
            params.append(data['email'])
        
        # Role update (admin only)
        if 'role' in data and data['role'] != target_user['role']:
            if current_user['role'] != 'admin':
                return jsonify({'error': 'Only admins can change user roles'}), 403
            
            if data['role'] not in ['admin', 'helper', 'player']:
                return jsonify({'error': 'Invalid role'}), 400
            
            updates.append("role = %s")
            params.append(data['role'])
        
        # Active status update (admin only)
        if 'is_active' in data and data['is_active'] != target_user['is_active']:
            if current_user['role'] != 'admin':
                return jsonify({'error': 'Only admins can change user status'}), 403
            
            updates.append("is_active = %s")
            params.append(data['is_active'])

        if 'display_timezone' in data:
            try:
                tz_norm = _parse_display_timezone_payload(data['display_timezone'])
            except ValueError as ve:
                return jsonify({'error': str(ve)}), 400
            cur_tz = target_user['display_timezone']
            if tz_norm != cur_tz:
                updates.append("display_timezone = %s")
                params.append(tz_norm)
        
        # Apply updates if any
        if updates:
            params.append(datetime.utcnow())  # updated_at
            params.append(user_id)
            
            query = f"UPDATE users SET {', '.join(updates)}, updated_at = %s WHERE id = %s"
            cursor.execute(query, params)
            
            db.commit()
            
            logger.info(f"User {user_id} updated by user {current_user_id}")
        
        # Return updated user
        return get_user(user_id)
        
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        return jsonify({'error': 'Failed to update user'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    """Delete user (admin only)"""
    try:
        current_user_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        # Check if current user is admin
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user or current_user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Prevent self-deletion
        if current_user_id == user_id:
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        # Check if user exists
        cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        target_user = cursor.fetchone()
        
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Soft delete - mark as inactive instead of removing
        cursor.execute("UPDATE users SET is_active = 0, updated_at = %s WHERE id = %s", 
                      (datetime.utcnow(), user_id))
        
        db.commit()
        
        logger.info(f"User {user_id} ({target_user['username']}) deactivated by admin {current_user_id}")
        
        return jsonify({'message': 'User deactivated successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        return jsonify({'error': 'Failed to delete user'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/stats', methods=['GET'])
@jwt_required()
def get_user_stats():
    """Get user statistics (admin only)"""
    try:
        current_user_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        # Check if current user is admin
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user or current_user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Get user statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_users,
                COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_users,
                COUNT(CASE WHEN role = 'admin' THEN 1 END) as admin_count,
                COUNT(CASE WHEN role = 'helper' THEN 1 END) as helper_count,
                COUNT(CASE WHEN role = 'player' THEN 1 END) as player_count,
                COUNT(CASE WHEN last_login > datetime('now', '-7 days') THEN 1 END) as active_this_week
            FROM users
        """)
        
        stats = cursor.fetchone()
        
        return jsonify({
            'user_statistics': {
                'total_users': stats['total_users'],
                'active_users': stats['active_users'],
                'inactive_users': stats['total_users'] - stats['active_users'],
                'role_distribution': {
                    'admins': stats['admin_count'],
                    'helpers': stats['helper_count'],
                    'players': stats['player_count']
                },
                'activity': {
                    'active_this_week': stats['active_this_week'],
                    'active_this_month': 0  # Could add more detailed tracking
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return jsonify({'error': 'Failed to retrieve user statistics'}), 500
    finally:
        if 'db' in locals():
            db.close()
