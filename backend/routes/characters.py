#!/usr/bin/env python3
"""
ShadowRealms AI - Characters Routes
Character management and character sheets
"""

import os

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
import json
from datetime import datetime

from database import (
    get_db,
    ensure_character_portrait_url_column,
    ensure_characters_is_active_column,
    ensure_characters_wod_sheet_columns,
    ensure_characters_play_suspension_columns,
    ensure_character_downtime_requests_table,
    ensure_users_allow_multi_campaign_play_column,
)

# Stored as TEXT (URLs or data URLs); cap size to protect the DB.
MAX_PORTRAIT_URL_LEN = 524288

try:
    import sqlite3

    _INTEGRITY_ERRORS = (sqlite3.IntegrityError,)
except ImportError:
    _INTEGRITY_ERRORS = ()

try:
    from psycopg2 import IntegrityError as _PsycopgIntegrityError

    _INTEGRITY_ERRORS = _INTEGRITY_ERRORS + (_PsycopgIntegrityError,)
except ImportError:
    pass

logger = logging.getLogger(__name__)

bp = Blueprint('characters', __name__)

ALLOWED_SYSTEM_TYPES = frozenset(
    {'d20', 'd10', 'besm', 'vampire', 'werewolf', 'mage'}
)


def _campaign_is_active_sql(alias: str = "c") -> str:
    """PostgreSQL uses BOOLEAN; SQLite often uses 0/1."""
    p = f"{alias}." if alias else ""
    if os.getenv("DATABASE_TYPE", "sqlite").lower() == "postgresql":
        return f"{p}is_active IS TRUE"
    return f"{p}is_active = 1"


def _ensure_character_schema(cursor):
    ensure_character_portrait_url_column(cursor)
    ensure_characters_is_active_column(cursor)
    ensure_characters_wod_sheet_columns(cursor)
    ensure_characters_play_suspension_columns(cursor)
    ensure_character_downtime_requests_table(cursor)
    ensure_users_allow_multi_campaign_play_column(cursor)


def _wod_meta_parse(raw):
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if isinstance(raw, str) else {}
    except json.JSONDecodeError:
        return {}


def _sheet_locked_bool(val):
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    return bool(val)


def _character_public_dict(row, owner_name=None, campaign_name=None):
    d = {
        'id': row['id'],
        'name': row['name'],
        'system_type': row['system_type'],
        'attributes': json.loads(row['attributes']) if row['attributes'] else {},
        'skills': json.loads(row['skills']) if row['skills'] else {},
        'background': row['background'],
        'merits_flaws': json.loads(row['merits_flaws']) if row['merits_flaws'] else {},
        'user_id': row['user_id'],
        'campaign_id': row['campaign_id'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
        'portrait_url': row.get('portrait_url'),
        'sheet_locked': _sheet_locked_bool(row.get('sheet_locked')),
        'wod_meta': _wod_meta_parse(row.get('wod_meta')),
        'is_active': bool(row.get('is_active', True)),
        'play_suspended': _sheet_locked_bool(row.get('play_suspended')),
        'play_suspension_reason_code': row.get('play_suspension_reason_code'),
        'play_suspension_message': row.get('play_suspension_message'),
        'play_suspended_at': row.get('play_suspended_at'),
        'play_suspended_by': row.get('play_suspended_by'),
    }
    if owner_name is not None:
        d['owner_name'] = owner_name
    if campaign_name is not None:
        d['campaign_name'] = campaign_name
    return d

@bp.route('/', methods=['GET'])
@jwt_required()
def get_characters():
    """Get characters (filtered by user and campaign)"""
    try:
        current_user_id = get_jwt_identity()
        campaign_id = request.args.get('campaign_id', type=int)
        
        db = get_db()
        cursor = db.cursor()
        _ensure_character_schema(cursor)
        db.commit()

        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Build query based on user role and filters
        if current_user['role'] in ['admin', 'helper']:
            # Admins and helpers can see all characters
            if campaign_id:
                cursor.execute("""
                    SELECT ch.*, u.username as owner_name, c.name as campaign_name
                    FROM characters ch
                    JOIN users u ON ch.user_id = u.id
                    JOIN campaigns c ON ch.campaign_id = c.id
                    WHERE ch.campaign_id = %s
                    ORDER BY ch.created_at DESC
                """, (campaign_id,))
            else:
                cursor.execute("""
                    SELECT ch.*, u.username as owner_name, c.name as campaign_name
                    FROM characters ch
                    JOIN users u ON ch.user_id = u.id
                    JOIN campaigns c ON ch.campaign_id = c.id
                    ORDER BY ch.created_at DESC
                """)
        else:
            # Players can only see their own characters
            if campaign_id:
                cursor.execute("""
                    SELECT ch.*, u.username as owner_name, c.name as campaign_name
                    FROM characters ch
                    JOIN users u ON ch.user_id = u.id
                    JOIN campaigns c ON ch.campaign_id = c.id
                    WHERE ch.user_id = %s AND ch.campaign_id = %s
                    ORDER BY ch.created_at DESC
                """, (current_user_id, campaign_id))
            else:
                cursor.execute("""
                    SELECT ch.*, u.username as owner_name, c.name as campaign_name
                    FROM characters ch
                    JOIN users u ON ch.user_id = u.id
                    JOIN campaigns c ON ch.campaign_id = c.id
                    WHERE ch.user_id = %s
                    ORDER BY ch.created_at DESC
                """, (current_user_id,))
        
        characters = []
        for row in cursor.fetchall():
            ch = _character_public_dict(
                row, owner_name=row['owner_name'], campaign_name=row['campaign_name']
            )
            characters.append(ch)
        
        return jsonify({
            'characters': characters,
            'total': len(characters)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting characters: {e}")
        return jsonify({'error': 'Failed to retrieve characters'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/', methods=['POST'])
@jwt_required()
def create_character():
    """Create new character (WoD lines: system_type must match campaign game_system)."""
    try:
        try:
            current_user_id = int(get_jwt_identity())
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid session'}), 401

        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        name = (data.get('name') or '').strip()
        raw_cid = data.get('campaign_id')
        try:
            campaign_id = int(raw_cid)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid campaign ID'}), 400
        system_type = (data.get('system_type') or '').strip().lower()

        if not all([name, system_type]):
            return jsonify(
                {'error': 'Name, campaign ID, and system type are required'}
            ), 400

        if system_type not in ALLOWED_SYSTEM_TYPES:
            return jsonify({'error': 'Invalid system type'}), 400

        wm = data.get('wod_meta')
        if wm is not None and not isinstance(wm, dict):
            return jsonify({'error': 'wod_meta must be a JSON object'}), 400
        wod_meta = json.dumps(wm if isinstance(wm, dict) else {})

        db = get_db()
        cursor = db.cursor()
        _ensure_character_schema(cursor)
        db.commit()

        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        ur = cursor.fetchone()
        if not ur:
            return jsonify({'error': 'User not found'}), 404
        user_role = ur['role']

        if user_role in ('admin', 'helper'):
            cursor.execute(
                f"SELECT * FROM campaigns WHERE id = %s AND {_campaign_is_active_sql('')}",
                (campaign_id,),
            )
        else:
            cursor.execute(
                f"""
                SELECT c.*
                FROM campaigns c
                WHERE c.id = %s AND {_campaign_is_active_sql('c')}
                  AND (
                    c.created_by = %s OR EXISTS (
                      SELECT 1 FROM campaign_players cp
                      WHERE cp.campaign_id = c.id AND cp.user_id = %s
                    )
                  )
                """,
                (campaign_id, current_user_id, current_user_id),
            )

        campaign = cursor.fetchone()
        if not campaign:
            return jsonify({'error': 'Campaign not found or access denied'}), 404

        cgs = (campaign.get('game_system') or '').strip().lower()
        if cgs in ('vampire', 'werewolf', 'mage') and system_type != cgs:
            return jsonify(
                {
                    'error': (
                        f'Character system_type must match this campaign '
                        f'({cgs}).'
                    )
                }
            ), 400

        portrait_url = data.get('portrait_url')
        if portrait_url is not None and portrait_url != '':
            if (
                not isinstance(portrait_url, str)
                or len(portrait_url) > MAX_PORTRAIT_URL_LEN
            ):
                return jsonify({'error': 'portrait_url is invalid or too large'}), 400
        else:
            portrait_url = None

        sheet_locked = bool(data.get('sheet_locked', True))
        is_active = bool(data.get('is_active', True))

        cursor.execute(
            """
            SELECT id FROM characters
            WHERE name = %s AND campaign_id = %s
            """,
            (name, campaign_id),
        )
        if cursor.fetchone():
            return jsonify(
                {'error': 'Character name already exists in this campaign'}
            ), 409

        if sheet_locked and user_role == 'player':
            cursor.execute(
                """
                SELECT allow_multi_campaign_play FROM users WHERE id = %s
                """,
                (current_user_id,),
            )
            uallow = cursor.fetchone() or {}
            allow_multi = bool(uallow.get('allow_multi_campaign_play') or False)
            if not allow_multi:
                cursor.execute(
                    """
                    SELECT id, campaign_id, sheet_locked, is_active
                    FROM characters
                    WHERE user_id = %s
                    """,
                    (current_user_id,),
                )
                for er in cursor.fetchall():
                    if not bool(er.get('is_active', True)):
                        continue
                    if not _sheet_locked_bool(er.get('sheet_locked')):
                        continue
                    if int(er['campaign_id']) != int(campaign_id):
                        cursor.close()
                        db.close()
                        return jsonify({
                            'error': (
                                'You already have a locked character in another '
                                'chronicle. Only a site administrator can grant '
                                'access to additional campaigns or multiple '
                                'locked characters.'
                            ),
                            'error_code': 'single_locked_pc_conflict',
                        }), 409

        now = datetime.utcnow()
        cursor.execute(
            """
            INSERT INTO characters (
                name, system_type, attributes, skills, background, merits_flaws,
                user_id, campaign_id, portrait_url, is_active, sheet_locked,
                wod_meta, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                name,
                system_type,
                json.dumps(data.get('attributes') or {}),
                json.dumps(data.get('skills') or {}),
                data.get('background') or '',
                json.dumps(data.get('merits_flaws') or {}),
                current_user_id,
                campaign_id,
                portrait_url,
                is_active,
                sheet_locked,
                wod_meta,
                now,
                now,
            ),
        )

        result = cursor.fetchone()
        character_id = result['id']
        db.commit()

        logger.info(
            "Character '%s' created by user %s in campaign %s",
            name,
            current_user_id,
            campaign_id,
        )

        return jsonify(
            {
                'message': 'Character created successfully',
                'character_id': character_id,
                'name': name,
            }
        ), 201

    except _INTEGRITY_ERRORS as e:
        logger.exception("Error creating character (integrity): %s", e)
        return jsonify(
            {
                'error': (
                    'Could not create character. The name may already be taken, '
                    'or the chronicle reference is no longer valid.'
                ),
                'error_code': 'character_create_integrity',
            }
        ), 409
    except Exception as e:
        logger.exception("Error creating character: %s", e)
        return jsonify({'error': 'Failed to create character'}), 500
    finally:
        if 'db' in locals():
            db.close()


@bp.route('/downtime-requests/mine', methods=['GET'])
@jwt_required()
def list_my_downtime_requests():
    """Pending and past downtime requests for the logged-in player."""
    try:
        current_user_id = get_jwt_identity()
        db = get_db()
        cursor = db.cursor()
        _ensure_character_schema(cursor)
        db.commit()

        cursor.execute(
            """
            SELECT d.id, d.character_id, d.campaign_id, d.request_text, d.status,
                   d.admin_reason, d.resolved_at, d.created_at,
                   ch.name AS character_name, c.name AS campaign_name
            FROM character_downtime_requests d
            JOIN characters ch ON ch.id = d.character_id
            JOIN campaigns c ON c.id = d.campaign_id
            WHERE d.user_id = %s
            ORDER BY d.created_at DESC
            LIMIT 200
            """,
            (current_user_id,),
        )
        rows = cursor.fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    'id': r['id'],
                    'character_id': r['character_id'],
                    'character_name': r['character_name'],
                    'campaign_id': r['campaign_id'],
                    'campaign_name': r['campaign_name'],
                    'request_text': r['request_text'],
                    'status': r['status'],
                    'admin_reason': r.get('admin_reason'),
                    'resolved_at': r.get('resolved_at'),
                    'created_at': r['created_at'],
                }
            )
        return jsonify({'requests': out, 'total': len(out)}), 200
    except Exception as e:
        logger.error(f"list_my_downtime_requests: {e}")
        return jsonify({'error': 'Failed to list requests'}), 500
    finally:
        if 'db' in locals():
            db.close()


@bp.route('/<int:character_id>/downtime-requests', methods=['POST'])
@jwt_required()
def create_character_downtime_request(character_id):
    """Submit a downtime / sheet-change request for Storyteller review."""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        text = (data.get('request_text') or '').strip()
        if not text:
            return jsonify({'error': 'request_text is required'}), 400
        if len(text) > 20000:
            return jsonify({'error': 'request_text is too long'}), 400

        db = get_db()
        cursor = db.cursor()
        _ensure_character_schema(cursor)
        db.commit()

        cursor.execute(
            """
            SELECT id, user_id, campaign_id FROM characters WHERE id = %s
            """,
            (character_id,),
        )
        ch = cursor.fetchone()
        if not ch:
            return jsonify({'error': 'Character not found'}), 404
        if str(ch['user_id']) != str(current_user_id):
            return jsonify({'error': 'Access denied'}), 403

        cursor.execute(
            """
            INSERT INTO character_downtime_requests (
                character_id, user_id, campaign_id, request_text, status, created_at
            )
            VALUES (%s, %s, %s, %s, 'pending', %s)
            RETURNING id
            """,
            (
                character_id,
                current_user_id,
                ch['campaign_id'],
                text,
                datetime.utcnow(),
            ),
        )
        rid = cursor.fetchone()['id']
        db.commit()
        return jsonify(
            {'message': 'Request submitted', 'id': rid}
        ), 201
    except Exception as e:
        logger.error(f"create_character_downtime_request: {e}")
        return jsonify({'error': 'Failed to submit request'}), 500
    finally:
        if 'db' in locals():
            db.close()


@bp.route('/<int:character_id>', methods=['GET'])
@jwt_required()
def get_character(character_id):
    """Get specific character details"""
    try:
        current_user_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        _ensure_character_schema(cursor)
        db.commit()

        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get character
        cursor.execute("""
            SELECT ch.*, u.username as owner_name, c.name as campaign_name
            FROM characters ch
            JOIN users u ON ch.user_id = u.id
            JOIN campaigns c ON ch.campaign_id = c.id
            WHERE ch.id = %s
        """, (character_id,))
        
        character = cursor.fetchone()
        
        if not character:
            return jsonify({'error': 'Character not found'}), 404
        
        # Check access permissions
        if current_user['role'] not in ['admin', 'helper'] and character['user_id'] != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        ch = _character_public_dict(
            character,
            owner_name=character['owner_name'],
            campaign_name=character['campaign_name'],
        )
        return jsonify({'character': ch}), 200
        
    except Exception as e:
        logger.error(f"Error getting character {character_id}: {e}")
        return jsonify({'error': 'Failed to retrieve character'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/<int:character_id>', methods=['PUT'])
@jwt_required()
def update_character(character_id):
    """Update character (owner, admin, or helper only)"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        db = get_db()
        cursor = db.cursor()
        _ensure_character_schema(cursor)
        db.commit()

        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get character
        cursor.execute("SELECT * FROM characters WHERE id = %s", (character_id,))
        character = cursor.fetchone()
        
        if not character:
            return jsonify({'error': 'Character not found'}), 404
        
        # Check permissions
        if current_user['role'] not in ['admin', 'helper'] and character['user_id'] != current_user_id:
            return jsonify({'error': 'Access denied'}), 403

        player_locked = current_user['role'] not in (
            'admin',
            'helper',
        ) and _sheet_locked_bool(character.get('sheet_locked'))
        if player_locked:
            data = {k: v for k, v in data.items() if k == 'portrait_url'}
            if not data:
                return jsonify(
                    {
                        'error': (
                            'Sheet is locked. You may only update portrait_url, '
                            'or submit a downtime request from Player Profile.'
                        )
                    }
                ), 403

        # Update fields
        updates = []
        params = []

        if 'name' in data and data['name'] != character['name']:
            # Check if name is already taken in this campaign
            cursor.execute("""
                SELECT id FROM characters 
                WHERE name = %s AND campaign_id = %s AND id != %s
            """, (data['name'], character['campaign_id'], character_id))
            
            if cursor.fetchone():
                return jsonify({'error': 'Character name already exists in this campaign'}), 409
            
            updates.append("name = %s")
            params.append(data['name'])
        
        if 'attributes' in data:
            updates.append("attributes = %s")
            params.append(json.dumps(data['attributes']))
        
        if 'skills' in data:
            updates.append("skills = %s")
            params.append(json.dumps(data['skills']))
        
        if 'background' in data:
            updates.append("background = %s")
            params.append(data['background'])
        
        if 'merits_flaws' in data:
            updates.append("merits_flaws = %s")
            params.append(json.dumps(data['merits_flaws']))

        if 'portrait_url' in data:
            pu = data['portrait_url']
            if pu is not None and pu != '':
                if not isinstance(pu, str) or len(pu) > MAX_PORTRAIT_URL_LEN:
                    return jsonify({'error': 'portrait_url is invalid or too large'}), 400
                updates.append("portrait_url = %s")
                params.append(pu)
            else:
                updates.append("portrait_url = %s")
                params.append(None)

        if current_user['role'] in ('admin', 'helper'):
            if 'sheet_locked' in data:
                updates.append("sheet_locked = %s")
                params.append(bool(data['sheet_locked']))
            if 'wod_meta' in data:
                wm = data['wod_meta']
                if wm is not None and not isinstance(wm, dict):
                    return jsonify({'error': 'wod_meta must be an object'}), 400
                updates.append("wod_meta = %s")
                params.append(json.dumps(wm if isinstance(wm, dict) else {}))
            if 'is_active' in data:
                updates.append("is_active = %s")
                params.append(bool(data['is_active']))

        # Apply updates if any
        if updates:
            params.append(datetime.utcnow())  # updated_at
            params.append(character_id)
            
            query = f"UPDATE characters SET {', '.join(updates)}, updated_at = %s WHERE id = %s"
            cursor.execute(query, params)
            
            db.commit()
            
            logger.info(f"Character {character_id} updated by user {current_user_id}")
        
        # Return updated character
        return get_character(character_id)
        
    except Exception as e:
        logger.error(f"Error updating character {character_id}: {e}")
        return jsonify({'error': 'Failed to update character'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/<int:character_id>', methods=['DELETE'])
@jwt_required()
def delete_character(character_id):
    """Delete character (owner, admin, or helper only)"""
    try:
        current_user_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get character
        cursor.execute("SELECT * FROM characters WHERE id = %s", (character_id,))
        character = cursor.fetchone()
        
        if not character:
            return jsonify({'error': 'Character not found'}), 404
        
        # Check permissions
        if current_user['role'] not in ['admin', 'helper'] and character['user_id'] != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        cursor.execute(
            "UPDATE users SET active_character_id = NULL WHERE active_character_id = %s",
            (character_id,),
        )
        cursor.execute("DELETE FROM characters WHERE id = %s", (character_id,))
        db.commit()
        
        logger.info(f"Character {character_id} ({character['name']}) deleted by user {current_user_id}")
        
        return jsonify({'message': 'Character deleted successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting character {character_id}: {e}")
        return jsonify({'error': 'Failed to delete character'}), 500
    finally:
        if 'db' in locals():
            db.close()
