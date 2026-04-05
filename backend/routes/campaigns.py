#!/usr/bin/env python3
"""
ShadowRealms AI - Campaign Management API
RESTful API for campaign creation, management, and RAG integration
"""

import os
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.rag_service import create_rag_service
from services.embedding_service import create_embedding_service
from database import (
    get_db,
    ensure_users_player_profile_columns,
    ensure_character_portrait_url_column,
    ensure_characters_is_active_column,
    ensure_characters_play_suspension_columns,
    ensure_campaigns_listing_columns,
    ensure_campaigns_staff_pause_columns,
    ensure_users_restrict_self_join_new_chronicles_column,
    ensure_users_self_switch_playing_character_column,
    ensure_campaign_players_active_character_id_column,
)
from services.moderation_audit import log_moderation_action_cursor
from services.play_suspension import suspended_json
from services.playing_character import (
    effective_playing_character_id,
    is_campaign_storyteller_or_staff,
)

logger = logging.getLogger(__name__)

# Create blueprint
campaigns_bp = Blueprint('campaigns', __name__, url_prefix='/api/campaigns')


def _fetch_ooc_lobby_location_ids(cursor, campaign_id: int) -> list:
    """
    IDs of the Out of Character Lobby for this campaign (never counted as story locations
    or story messages). psycopg2 treats bare % in SQL as special — do not use LIKE ...% in
    one big string; resolve ids with explicit queries instead.
    """
    ids = []
    seen = set()

    def _add(rows):
        for row in rows:
            lid = row['id']
            if lid not in seen:
                seen.add(lid)
                ids.append(lid)

    # Primary: type column (quoted — "type" is awkward for some parsers) + known names
    cursor.execute(
        """
        SELECT l.id FROM locations l
        WHERE l.campaign_id = %s
          AND (
            LOWER(TRIM(COALESCE(CAST(l."type" AS TEXT), ''))) = 'ooc'
            OR LOWER(TRIM(COALESCE(l.name, ''))) IN (
                'out of character lobby',
                'ooc lobby',
                'ooc chat',
                '💬 ooc chat',
                'out of character'
            )
          )
        """,
        (campaign_id,),
    )
    _add(cursor.fetchall())

    # Secondary: names starting with "out of character" (wildcard via CHR/CHAR — no literal %)
    db = os.getenv('DATABASE_TYPE', 'sqlite').lower()
    pct_fn = "CHR(37)" if db == "postgresql" else "CHAR(37)"
    cursor.execute(
        f"""
        SELECT l.id FROM locations l
        WHERE l.campaign_id = %s
          AND LOWER(TRIM(COALESCE(l.name, ''))) LIKE 'out of character' || {pct_fn}
        """,
        (campaign_id,),
    )
    _add(cursor.fetchall())

    return ids


def get_rag_service():
    """Get RAG service instance"""
    config = current_app.config
    return create_rag_service(config)

def get_embedding_service():
    """Get embedding service instance"""
    config = current_app.config
    return create_embedding_service(config)

@campaigns_bp.route('/', methods=['POST'])
@jwt_required()
def create_campaign():
    """Create a new campaign"""
    try:
        user_id = get_jwt_identity()
        
        # Handle malformed JSON
        try:
            data = request.get_json()
        except Exception as e:
            return jsonify({'error': 'Invalid JSON format'}), 400
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Validate required fields
        required_fields = ['name', 'description', 'game_system']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get database connection
        conn = get_db()
        cursor = conn.cursor()
        
        # Create campaign in database
        cursor.execute("""
            INSERT INTO campaigns (name, description, game_system, created_by, created_at, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['name'],
            data['description'],
            data['game_system'],
            user_id,
            datetime.now().isoformat(),
            'active'
        ))
        
        result = cursor.fetchone()
        campaign_id = result['id']

        # Creator is a member for all access checks that use campaign_players
        try:
            cursor.execute(
                """
                INSERT INTO campaign_players (campaign_id, user_id, joined_at, role)
                VALUES (%s, %s, %s, 'owner')
                ON CONFLICT (campaign_id, user_id) DO NOTHING
                """
                if os.getenv("DATABASE_TYPE", "sqlite").lower() == "postgresql"
                else """
                INSERT OR IGNORE INTO campaign_players (campaign_id, user_id, joined_at, role)
                VALUES (%s, %s, %s, 'owner')
                """,
                (campaign_id, user_id, datetime.now()),
            )
        except Exception as ins_e:
            logger.warning("campaign_players insert for creator: %s", ins_e)

        conn.commit()
        
        # Auto-create OOC room for the campaign
        try:
            from routes.locations import create_ooc_room
            ooc_location_id = create_ooc_room(campaign_id, user_id)
            logger.info(f"OOC room created for campaign {campaign_id}: location {ooc_location_id}")
        except Exception as e:
            logger.error(f"Failed to create OOC room for campaign {campaign_id}: {e}")
            # Don't fail campaign creation if OOC room fails
        
        # Store campaign data in RAG system
        rag_service = get_rag_service()
        campaign_data = {
            'name': data['name'],
            'description': data['description'],
            'game_system': data['game_system'],
            'settings': data.get('settings', {}),
            'world_info': data.get('world_info', {}),
            'created_at': datetime.now().isoformat()
        }
        
        memory_id = rag_service.store_campaign_data(campaign_id, campaign_data)
        
        # Store initial world data if provided
        if 'world_info' in data:
            world_memory_id = rag_service.store_world_data(campaign_id, data['world_info'])
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'message': 'Campaign created successfully',
            'campaign_id': campaign_id,
            'memory_id': memory_id
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        return jsonify({'error': 'Failed to create campaign'}), 500

@campaigns_bp.route('/', methods=['GET'])
@jwt_required()
def get_campaigns():
    """Get campaigns for the user.

    Query: for_active_character=1 — only the chronicle tied to the user's
    globally active character (Player Profile). Clients should omit this when
    the player has allow_multi_campaign_play so the dashboard can list every
    membership. Omit for full membership list (e.g. character creation picker).
    """
    try:
        raw_uid = get_jwt_identity()
        try:
            user_id = int(raw_uid)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid session"}), 401
        for_active = str(request.args.get("for_active_character", "")).lower() in (
            "1",
            "true",
            "yes",
        )

        conn = get_db()
        cursor = conn.cursor()
        ensure_users_player_profile_columns(cursor)
        ensure_campaigns_listing_columns(cursor)
        ensure_campaign_players_active_character_id_column(cursor)
        ensure_character_portrait_url_column(cursor)
        ensure_characters_is_active_column(cursor)
        conn.commit()

        if for_active:
            cursor.execute(
                "SELECT active_character_id FROM users WHERE id = %s",
                (user_id,),
            )
            urow = cursor.fetchone() or {}
            aid = urow.get("active_character_id")
            if not aid:
                # Storytellers often have no PC yet; fall back to full membership list.
                for_active = False
        if for_active:
            cursor.execute(
                """
                SELECT c.id, c.name, c.description, c.game_system, c.created_at, c.status,
                       c.max_players, c.listing_visibility, c.accepting_players,
                       cp.active_character_id AS my_playing_character_id,
                       ch_my.name AS my_playing_character_name,
                       ch_my.portrait_url AS my_playing_character_portrait_url
                FROM campaigns c
                INNER JOIN characters ch ON ch.campaign_id = c.id
                LEFT JOIN campaign_players cp ON cp.campaign_id = c.id AND cp.user_id = %s
                LEFT JOIN characters ch_my ON ch_my.id = cp.active_character_id
                    AND ch_my.user_id = %s AND ch_my.campaign_id = c.id
                WHERE ch.id = %s AND ch.user_id = %s
                  AND (
                    c.created_by = %s OR c.id IN (
                      SELECT campaign_id FROM campaign_players WHERE user_id = %s
                    )
                  )
                ORDER BY c.created_at DESC
                """,
                (user_id, user_id, aid, user_id, user_id, user_id),
            )
        else:
            cursor.execute("""
                SELECT c.id, c.name, c.description, c.game_system, c.created_at, c.status,
                       c.max_players, c.listing_visibility, c.accepting_players,
                       cp.active_character_id AS my_playing_character_id,
                       ch_my.name AS my_playing_character_name,
                       ch_my.portrait_url AS my_playing_character_portrait_url
                FROM campaigns c
                LEFT JOIN campaign_players cp ON cp.campaign_id = c.id AND cp.user_id = %s
                LEFT JOIN characters ch_my ON ch_my.id = cp.active_character_id
                    AND ch_my.user_id = %s AND ch_my.campaign_id = c.id
                WHERE c.created_by = %s OR c.id IN (
                    SELECT campaign_id FROM campaign_players WHERE user_id = %s
                )
                ORDER BY c.created_at DESC
            """, (user_id, user_id, user_id, user_id))
        
        campaigns = []
        for row in cursor.fetchall():
            acc = row.get("accepting_players")
            if isinstance(acc, str):
                acc = acc.lower() in ("1", "true", "yes")
            else:
                acc = bool(acc)
            campaigns.append({
                'id': row['id'],
                'name': row['name'],
                'description': row['description'],
                'game_system': row['game_system'],
                'created_at': row['created_at'],
                'status': row['status'],
                'max_players': row.get('max_players'),
                'listing_visibility': row.get('listing_visibility') or 'private',
                'accepting_players': acc,
                'my_playing_character_id': row.get('my_playing_character_id'),
                'my_playing_character_name': row.get('my_playing_character_name'),
                'my_playing_character_portrait_url': row.get(
                    'my_playing_character_portrait_url'
                ),
            })

        # Dashboard card: show a character whenever the user has any PC in the
        # chronicle, not only when campaign_players.active_character_id is set.
        for c in campaigns:
            name = (c.get("my_playing_character_name") or "").strip()
            if name:
                continue
            eid = effective_playing_character_id(cursor, user_id, c["id"])
            if eid is None:
                continue
            cursor.execute(
                """
                SELECT id, name, portrait_url FROM characters
                WHERE id = %s AND user_id = %s AND campaign_id = %s
                """,
                (eid, user_id, c["id"]),
            )
            ch = cursor.fetchone()
            if not ch:
                continue
            c["my_playing_character_id"] = ch["id"]
            c["my_playing_character_name"] = ch.get("name")
            c["my_playing_character_portrait_url"] = ch.get("portrait_url")

        cursor.close()
        conn.close()
        
        return jsonify(campaigns), 200
        
    except Exception as e:
        logger.error(f"Error getting campaigns: {e}")
        return jsonify({'error': 'Failed to get campaigns'}), 500


@campaigns_bp.route('/discover', methods=['GET'])
@jwt_required()
def discover_campaigns():
    """List campaigns open for self-serve join that the user is not yet in."""
    try:
        user_id = get_jwt_identity()
        conn = get_db()
        cursor = conn.cursor()
        ensure_campaigns_listing_columns(cursor)
        conn.commit()

        cursor.execute(
            """
            SELECT c.id, c.name, c.description, c.game_system, c.created_at, c.status,
                   c.max_players, c.listing_visibility, c.accepting_players
            FROM campaigns c
            WHERE c.is_active = 1
              AND c.listing_visibility = 'listed'
              AND c.accepting_players = 1
              AND c.id NOT IN (
                  SELECT campaign_id FROM campaign_players WHERE user_id = %s
              )
              AND c.created_by != %s
            ORDER BY c.created_at DESC
            """
            if os.getenv("DATABASE_TYPE", "sqlite").lower() != "postgresql"
            else """
            SELECT c.id, c.name, c.description, c.game_system, c.created_at, c.status,
                   c.max_players, c.listing_visibility, c.accepting_players
            FROM campaigns c
            WHERE c.is_active = TRUE
              AND c.listing_visibility = 'listed'
              AND c.accepting_players = TRUE
              AND c.id NOT IN (
                  SELECT campaign_id FROM campaign_players WHERE user_id = %s
              )
              AND c.created_by IS DISTINCT FROM %s
            ORDER BY c.created_at DESC
            """,
            (user_id, user_id),
        )
        out = []
        for row in cursor.fetchall():
            out.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "game_system": row["game_system"],
                    "created_at": row["created_at"],
                    "status": row["status"],
                    "max_players": row.get("max_players"),
                }
            )
        cursor.close()
        conn.close()
        return jsonify(out), 200
    except Exception as e:
        logger.error(f"discover_campaigns: {e}")
        return jsonify({"error": "Failed to list campaigns"}), 500


@campaigns_bp.route('/<int:campaign_id>/join', methods=['POST'])
@jwt_required()
def join_campaign(campaign_id):
    """Player self-join when campaign is listed and accepting players."""
    try:
        user_id = get_jwt_identity()
        conn = get_db()
        cursor = conn.cursor()
        ensure_campaigns_listing_columns(cursor)
        ensure_users_restrict_self_join_new_chronicles_column(cursor)
        ensure_campaign_players_active_character_id_column(cursor)
        conn.commit()

        cursor.execute(
            """
            SELECT id, max_players, listing_visibility, accepting_players, is_active, created_by
            FROM campaigns WHERE id = %s
            """,
            (campaign_id,),
        )
        c = cursor.fetchone()
        if not c:
            cursor.close()
            conn.close()
            return jsonify({"error": "Campaign not found"}), 404

        vis = (c.get("listing_visibility") or "private").strip().lower()
        acc = c.get("accepting_players")
        if isinstance(acc, str):
            acc = acc.lower() in ("1", "true", "yes")
        else:
            acc = bool(acc)
        active = c.get("is_active")
        if isinstance(active, str):
            active = active.lower() in ("1", "true", "yes")
        else:
            active = bool(active) if active is not None else True

        if not active or vis != "listed" or not acc:
            cursor.close()
            conn.close()
            return jsonify({"error": "This campaign is not open for joining"}), 403

        cursor.execute(
            "SELECT 1 FROM campaign_players WHERE campaign_id = %s AND user_id = %s",
            (campaign_id, user_id),
        )
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"message": "Already a member", "campaign_id": campaign_id}), 200

        cursor.execute(
            "SELECT restrict_self_join_new_chronicles FROM users WHERE id = %s",
            (user_id,),
        )
        urow = cursor.fetchone() or {}
        restricted = bool(urow.get("restrict_self_join_new_chronicles") or False)
        if restricted:
            dbp = os.getenv("DATABASE_TYPE", "sqlite").lower()
            active_sql = (
                "(is_active IS NULL OR is_active IS TRUE)"
                if dbp == "postgresql"
                else "(is_active IS NULL OR is_active = 1)"
            )
            cursor.execute(
                f"""
                SELECT 1 FROM characters
                WHERE user_id = %s AND campaign_id = %s AND {active_sql}
                LIMIT 1
                """,
                (user_id, campaign_id),
            )
            if not cursor.fetchone():
                cursor.close()
                conn.close()
                return (
                    jsonify(
                        {
                            "error": (
                                "Joining a new chronicle requires storyteller or site "
                                "staff approval. Ask them to add you, or rejoin a "
                                "chronicle where you still have a character."
                            ),
                            "error_code": "join_requires_storyteller_approval",
                        }
                    ),
                    403,
                )

        max_p = c.get("max_players")
        if max_p is not None and int(max_p) > 0:
            cursor.execute(
                """
                SELECT COUNT(*) AS n FROM campaign_players WHERE campaign_id = %s
                """,
                (campaign_id,),
            )
            n = int(cursor.fetchone()["n"])
            if n >= int(max_p):
                cursor.close()
                conn.close()
                return jsonify({"error": "Campaign is full"}), 409

        now = datetime.utcnow()
        if os.getenv("DATABASE_TYPE", "sqlite").lower() == "postgresql":
            cursor.execute(
                """
                INSERT INTO campaign_players (campaign_id, user_id, joined_at, role)
                VALUES (%s, %s, %s, 'player')
                ON CONFLICT (campaign_id, user_id) DO NOTHING
                """,
                (campaign_id, user_id, now),
            )
        else:
            cursor.execute(
                """
                INSERT OR IGNORE INTO campaign_players (campaign_id, user_id, joined_at, role)
                VALUES (%s, %s, %s, 'player')
                """,
                (campaign_id, user_id, now),
            )

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Joined campaign", "campaign_id": campaign_id}), 200
    except Exception as e:
        logger.error(f"join_campaign: {e}")
        return jsonify({"error": "Failed to join campaign"}), 500


@campaigns_bp.route('/<int:campaign_id>', methods=['GET', 'PUT', 'DELETE'])
@jwt_required()
def get_or_update_campaign(campaign_id):
    """Get or update specific campaign details"""
    if request.method == 'PUT':
        return update_campaign(campaign_id)
    elif request.method == 'DELETE':
        return delete_campaign(campaign_id)
    
    try:
        raw_uid = get_jwt_identity()
        try:
            user_id = int(raw_uid)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid session'}), 401

        conn = get_db()
        cursor = conn.cursor()
        ensure_users_player_profile_columns(cursor)
        ensure_characters_play_suspension_columns(cursor)
        ensure_campaigns_listing_columns(cursor)
        conn.commit()

        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        viewer = cursor.fetchone()
        is_site_admin = bool(viewer and viewer.get("role") == "admin")

        # Members and creators always; site admins may open any chronicle (for moderation / ST tools).
        if is_site_admin:
            cursor.execute("""
                SELECT id, name, description, game_system, created_by, created_at, status,
                       max_players, listing_visibility, accepting_players
                FROM campaigns
                WHERE id = %s
            """, (campaign_id,))
        else:
            cursor.execute("""
                SELECT id, name, description, game_system, created_by, created_at, status,
                       max_players, listing_visibility, accepting_players
                FROM campaigns
                WHERE id = %s AND (created_by = %s OR id IN (
                    SELECT campaign_id FROM campaign_players WHERE user_id = %s
                ))
            """, (campaign_id, user_id, user_id))

        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Campaign not found'}), 404
        
        acc = row.get("accepting_players")
        if isinstance(acc, str):
            acc = acc.lower() in ("1", "true", "yes")
        else:
            acc = bool(acc)

        campaign = {
            'id': row['id'],
            'name': row['name'],
            'description': row['description'],
            'game_system': row['game_system'],
            'created_by': row['created_by'],
            'created_at': row['created_at'],
            'status': row['status'],
            'max_players': row.get('max_players'),
            'listing_visibility': row.get('listing_visibility') or 'private',
            'accepting_players': acc,
        }

        cursor.execute(
            "SELECT active_character_id FROM users WHERE id = %s",
            (user_id,),
        )
        urow = cursor.fetchone() or {}
        aid = urow.get("active_character_id")
        if aid:
            cursor.execute(
                """
                SELECT campaign_id, play_suspended, play_suspension_reason_code,
                       play_suspension_message
                FROM characters
                WHERE id = %s AND user_id = %s
                """,
                (aid, user_id),
            )
            ch = cursor.fetchone()
            if (
                ch
                and int(ch["campaign_id"]) == int(campaign_id)
                and bool(ch.get("play_suspended") or False)
            ):
                cursor.close()
                conn.close()
                return (
                    jsonify(
                        suspended_json(
                            ch.get("play_suspension_reason_code") or "custom",
                            ch.get("play_suspension_message"),
                        )
                    ),
                    403,
                )
        
        # Get campaign context from RAG
        rag_service = get_rag_service()
        context = rag_service.get_campaign_context(campaign_id)
        
        campaign['context'] = context
        
        cursor.close()
        conn.close()
        
        return jsonify(campaign), 200
        
    except Exception as e:
        logger.error(f"Error getting campaign: {e}")
        return jsonify({'error': 'Failed to get campaign'}), 500

@campaigns_bp.route('/<int:campaign_id>/stats', methods=['GET'])
@jwt_required()
def get_campaign_stats(campaign_id):
    """Get campaign statistics counts for settings UI"""
    try:
        user_id = get_jwt_identity()
        conn = get_db()
        cursor = conn.cursor()

        # Verify user has access to campaign (creator/admin/member)
        cursor.execute("""
            SELECT c.created_by, u.role
            FROM campaigns c
            JOIN users u ON u.id = %s
            WHERE c.id = %s
        """, (user_id, campaign_id))
        access_row = cursor.fetchone()
        if not access_row:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Campaign not found'}), 404

        is_admin = access_row.get('role') == 'admin'
        is_creator = str(access_row.get('created_by')) == str(user_id)

        if not is_admin and not is_creator:
            cursor.execute("""
                SELECT 1
                FROM campaign_players
                WHERE campaign_id = %s AND user_id = %s
                LIMIT 1
            """, (campaign_id, user_id))
            if not cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({'error': 'Unauthorized'}), 403

        cursor.execute("""
            SELECT COUNT(DISTINCT u.id) AS count
            FROM (
                SELECT created_by AS user_id FROM campaigns WHERE id = %s
                UNION
                SELECT user_id FROM campaign_players WHERE campaign_id = %s
            ) p
            JOIN users u ON u.id = p.user_id
            WHERE u.is_active = TRUE
        """, (campaign_id, campaign_id))
        active_players = int(cursor.fetchone()['count'])

        cursor.execute("""
            SELECT COUNT(*) AS count
            FROM characters
            WHERE campaign_id = %s AND is_active = TRUE
        """, (campaign_id,))
        characters = int(cursor.fetchone()['count'])

        ooc_ids = _fetch_ooc_lobby_location_ids(cursor, campaign_id)
        if ooc_ids:
            logger.info(
                "Campaign %s stats: excluding OOC lobby location_id(s) from story counts: %s",
                campaign_id,
                ooc_ids,
            )
        else:
            logger.warning(
                "Campaign %s stats: no OOC lobby row matched (type=ooc / known names). "
                "Story location and message totals may include the lobby — check locations.name/type.",
                campaign_id,
            )

        # Story locations only — OOC lobby is not a playable "location" in this total
        if ooc_ids:
            ph = ",".join(["%s"] * len(ooc_ids))
            cursor.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM locations l
                WHERE l.campaign_id = %s AND l.is_active = TRUE
                  AND l.id NOT IN ({ph})
                """,
                (campaign_id, *ooc_ids),
            )
        else:
            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM locations l
                WHERE l.campaign_id = %s AND l.is_active = TRUE
                """,
                (campaign_id,),
            )
        locations = int(cursor.fetchone()['count'])

        # Story messages: not in OOC lobby; also drop rows explicitly tagged message_type ooc
        if ooc_ids:
            ph = ",".join(["%s"] * len(ooc_ids))
            cursor.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM messages m
                WHERE m.campaign_id = %s
                  AND COALESCE(LOWER(TRIM(m.message_type)), '') <> 'ooc'
                  AND m.location_id NOT IN ({ph})
                """,
                (campaign_id, *ooc_ids),
            )
        else:
            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM messages m
                WHERE m.campaign_id = %s
                  AND COALESCE(LOWER(TRIM(m.message_type)), '') <> 'ooc'
                """,
                (campaign_id,),
            )
        messages = int(cursor.fetchone()['count'])

        cursor.close()
        conn.close()

        return jsonify({
            'campaign_id': campaign_id,
            'active_players': active_players,
            'characters': characters,
            'locations': locations,
            'messages': messages
        }), 200

    except Exception as e:
        logger.error(f"Error getting campaign stats: {e}")
        return jsonify({'error': 'Failed to get campaign stats'}), 500

def update_campaign(campaign_id):
    """Update campaign details (admin only)"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON body required'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        ensure_campaigns_listing_columns(cursor)
        ensure_campaigns_staff_pause_columns(cursor)
        conn.commit()
        
        # Check if user is admin or campaign creator
        cursor.execute("""
            SELECT created_by FROM campaigns WHERE id = %s
        """, (campaign_id,))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Check if user is creator
        cursor.execute("""
            SELECT role FROM users WHERE id = %s
        """, (user_id,))
        user_row = cursor.fetchone()
        
        if str(row['created_by']) != str(user_id) and (
            not user_row or user_row['role'] != 'admin'
        ):
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Update campaign fields if provided
        updates = []
        params = []
        
        if 'name' in data:
            updates.append('name = %s')
            params.append(data['name'])
        
        if 'description' in data:
            updates.append('description = %s')
            params.append(data['description'])

        if 'listing_visibility' in data:
            lv = (data['listing_visibility'] or '').strip().lower()
            if lv not in ('private', 'listed'):
                return jsonify({'error': 'listing_visibility must be private or listed'}), 400
            updates.append('listing_visibility = %s')
            params.append(lv)

        if 'accepting_players' in data:
            updates.append('accepting_players = %s')
            params.append(bool(data['accepting_players']))

        if 'max_players' in data:
            mp = data['max_players']
            if mp is None:
                updates.append('max_players = %s')
                params.append(None)
            else:
                try:
                    mpi = int(mp)
                except (TypeError, ValueError):
                    return jsonify({'error': 'max_players must be an integer'}), 400
                if mpi < 0:
                    return jsonify({'error': 'max_players must be >= 0'}), 400
                updates.append('max_players = %s')
                params.append(mpi)

        if 'is_active' in data:
            active_flag = bool(data['is_active'])
            updates.append('is_active = %s')
            params.append(active_flag)
            if active_flag:
                updates.append('admin_inactive_reason = %s')
                params.append(None)
                updates.append('admin_inactive_at = %s')
                params.append(None)
            else:
                reason = (data.get('admin_inactive_reason') or data.get('staff_pause_reason') or '').strip()
                updates.append('admin_inactive_reason = %s')
                params.append(reason or None)
                updates.append('admin_inactive_at = %s')
                params.append(datetime.utcnow())
        
        if updates:
            params.append(campaign_id)
            query = f"UPDATE campaigns SET {', '.join(updates)} WHERE id = %s"
            cursor.execute(query, params)
            conn.commit()
        
        return jsonify({'message': 'Campaign updated successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error updating campaign: {e}")
        return jsonify({'error': 'Failed to update campaign'}), 500

def delete_campaign(campaign_id):
    """Delete campaign with full AI memory cleanup"""
    try:
        user_id = get_jwt_identity()
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user is admin or campaign creator
        cursor.execute("""
            SELECT created_by, name FROM campaigns WHERE id = %s
        """, (campaign_id,))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Campaign not found'}), 404
        
        campaign_creator = row['created_by']
        campaign_name = row['name']
        
        # Check if user is creator or admin
        cursor.execute("""
            SELECT role FROM users WHERE id = %s
        """, (user_id,))
        user_row = cursor.fetchone()
        
        if str(campaign_creator) != str(user_id) and (
            not user_row or user_row['role'] != 'admin'
        ):
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Count what will be deleted for audit
        cursor.execute("SELECT COUNT(*) FROM locations WHERE campaign_id = %s", (campaign_id,))
        location_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) FROM messages WHERE campaign_id = %s", (campaign_id,))
        message_count = cursor.fetchone()['count']
        
        logger.info(f"🗑️ Deleting campaign {campaign_id} ({campaign_name}):")
        logger.info(f"   • {location_count} locations")
        logger.info(f"   • {message_count} messages")
        
        # CLEAN UP AI MEMORY - Remove all message embeddings for this campaign from ChromaDB
        try:
            rag_service = get_rag_service()
            
            if message_count > 0 and hasattr(rag_service, 'client'):
                try:
                    collection = rag_service.client.get_or_create_collection(name='message_memory')
                    # Get all message IDs for this campaign
                    cursor.execute("SELECT id FROM messages WHERE campaign_id = %s", (campaign_id,))
                    message_ids = [row['id'] for row in cursor.fetchall()]
                    
                    if message_ids:
                        embedding_ids = [f"msg_{msg_id}_{campaign_id}" for msg_id in message_ids]
                        collection.delete(ids=embedding_ids)
                        logger.info(f"✅ Purged {len(embedding_ids)} message embeddings from AI memory")
                except Exception as e:
                    logger.warning(f"⚠️ ChromaDB cleanup failed (non-critical): {e}")
        except Exception as e:
            logger.warning(f"⚠️ ChromaDB cleanup error: {e}")
        
        try:
            actor_id = int(user_id)
            creator_id = int(campaign_creator)
            log_moderation_action_cursor(
                cursor,
                creator_id,
                actor_id,
                "campaign_deleted",
                {
                    "campaign_id": campaign_id,
                    "campaign_name": campaign_name,
                    "locations_removed": location_count,
                    "messages_removed": message_count,
                },
            )
        except Exception as e:
            logger.warning("Moderation log insert failed (campaign delete continues): %s", e)

        # SQLite's ON DELETE CASCADE will handle related records
        # (locations, characters, messages, dice_rolls, etc.)
        cursor.execute("DELETE FROM campaigns WHERE id = %s", (campaign_id,))
        conn.commit()
        
        logger.info(f"✅ Campaign {campaign_id} ({campaign_name}) fully deleted:")
        logger.info(f"   • SQL data removed (CASCADE)")
        logger.info(f"   • ChromaDB embeddings purged")
        logger.info(f"   • AI memory cleaned - no orphaned data")
        
        return jsonify({
            'message': 'Campaign deleted successfully',
            'campaign_id': campaign_id,
            'audit': {
                'campaign_name': campaign_name,
                'locations_removed': location_count,
                'messages_removed': message_count,
                'ai_memory_cleaned': True
            }
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error deleting campaign: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to delete campaign'}), 500

@campaigns_bp.route('/<int:campaign_id>/world', methods=['POST'])
@jwt_required()
def update_world_data(campaign_id):
    """Update world-building data for campaign"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Verify user has access to campaign
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM campaigns
            WHERE id = %s AND (created_by = %s OR id IN (
                SELECT campaign_id FROM campaign_players WHERE user_id = %s
            ))
        """, (campaign_id, user_id, user_id))
        
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Store world data in RAG
        rag_service = get_rag_service()
        memory_id = rag_service.store_world_data(campaign_id, data)
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'message': 'World data updated successfully',
            'memory_id': memory_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating world data: {e}")
        return jsonify({'error': 'Failed to update world data'}), 500

@campaigns_bp.route('/<int:campaign_id>/search', methods=['POST'])
@jwt_required()
def search_campaign_memory(campaign_id):
    """Search campaign memory using RAG"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        query = data.get('query', '')
        memory_type = data.get('memory_type', 'all')
        limit = data.get('limit', 5)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Verify user has access to campaign
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM campaigns
            WHERE id = %s AND (created_by = %s OR id IN (
                SELECT campaign_id FROM campaign_players WHERE user_id = %s
            ))
        """, (campaign_id, user_id, user_id))
        
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Search using RAG
        rag_service = get_rag_service()
        
        if memory_type == 'all':
            # Search all memory types
            results = {}
            for mem_type in ['campaigns', 'characters', 'world', 'sessions', 'rules']:
                memories = rag_service.retrieve_memories(query, mem_type, campaign_id, limit)
                if memories:
                    results[mem_type] = memories
        else:
            # Search specific memory type
            memories = rag_service.retrieve_memories(query, memory_type, campaign_id, limit)
            results = {memory_type: memories}
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'query': query,
            'results': results,
            'total_results': sum(len(memories) for memories in results.values())
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching campaign memory: {e}")
        return jsonify({'error': 'Failed to search campaign memory'}), 500

@campaigns_bp.route('/<int:campaign_id>/context', methods=['POST'])
@jwt_required()
def get_campaign_context(campaign_id):
    """Get campaign context for AI generation"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        query = data.get('query', '')
        
        # Verify user has access to campaign
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM campaigns
            WHERE id = %s AND (created_by = %s OR id IN (
                SELECT campaign_id FROM campaign_players WHERE user_id = %s
            ))
        """, (campaign_id, user_id, user_id))
        
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Get context from RAG
        rag_service = get_rag_service()
        context = rag_service.get_campaign_context(campaign_id, query)
        
        # Augment prompt if provided
        if query:
            augmented_prompt = rag_service.augment_prompt(query, campaign_id, user_id)
            context['augmented_prompt'] = augmented_prompt
        
        cursor.close()
        conn.close()
        
        return jsonify({'context': context}), 200
        
    except Exception as e:
        logger.error(f"Error getting campaign context: {e}")
        return jsonify({'error': 'Failed to get campaign context'}), 500

@campaigns_bp.route('/<int:campaign_id>/interaction', methods=['POST'])
@jwt_required()
def store_interaction(campaign_id):
    """Store AI interaction for campaign"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        prompt = data.get('prompt', '')
        response = data.get('response', '')
        interaction_type = data.get('interaction_type', 'general')
        
        if not prompt or not response:
            return jsonify({'error': 'Prompt and response are required'}), 400
        
        # Verify user has access to campaign
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM campaigns
            WHERE id = %s AND (created_by = %s OR id IN (
                SELECT campaign_id FROM campaign_players WHERE user_id = %s
            ))
        """, (campaign_id, user_id, user_id))
        
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Store interaction in RAG
        rag_service = get_rag_service()
        memory_id = rag_service.store_interaction(prompt, response, campaign_id, user_id, interaction_type)
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'message': 'Interaction stored successfully',
            'memory_id': memory_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error storing interaction: {e}")
        return jsonify({'error': 'Failed to store interaction'}), 500


@campaigns_bp.route("/<int:campaign_id>/detach", methods=["POST"])
@jwt_required()
def detach_from_campaign(campaign_id):
    """Leave campaign membership. Sets restrict_self_join_new_chronicles on the removed user."""
    try:
        actor_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid session"}), 422

    data = request.get_json(silent=True) or {}
    target_user_id = data.get("user_id")
    if target_user_id is not None:
        try:
            target_user_id = int(target_user_id)
        except (TypeError, ValueError):
            return jsonify({"error": "user_id must be an integer"}), 400
    else:
        target_user_id = actor_id

    conn = get_db()
    cursor = conn.cursor()
    ensure_users_restrict_self_join_new_chronicles_column(cursor)
    ensure_users_player_profile_columns(cursor)
    ensure_campaign_players_active_character_id_column(cursor)
    conn.commit()

    cursor.execute(
        "SELECT created_by FROM campaigns WHERE id = %s",
        (campaign_id,),
    )
    camp = cursor.fetchone()
    if not camp:
        cursor.close()
        conn.close()
        return jsonify({"error": "Campaign not found"}), 404

    cursor.execute("SELECT role FROM users WHERE id = %s", (actor_id,))
    actor = cursor.fetchone() or {}
    actor_role = actor.get("role") or "player"

    if target_user_id != actor_id:
        if actor_role not in ("admin", "helper") and str(camp.get("created_by")) != str(
            actor_id
        ):
            cursor.close()
            conn.close()
            return jsonify({"error": "Only the chronicle storyteller or staff may remove players"}), 403
    else:
        if str(camp.get("created_by")) == str(actor_id):
            pass

    cursor.execute(
        """
        SELECT 1 FROM campaign_players WHERE campaign_id = %s AND user_id = %s
        """,
        (campaign_id, target_user_id),
    )
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Not a member of this campaign"}), 404

    cursor.execute(
        """
        DELETE FROM campaign_players WHERE campaign_id = %s AND user_id = %s
        """,
        (campaign_id, target_user_id),
    )
    cursor.execute(
        """
        UPDATE users SET restrict_self_join_new_chronicles = TRUE
        WHERE id = %s
        """
        if os.getenv("DATABASE_TYPE", "sqlite").lower() == "postgresql"
        else """
        UPDATE users SET restrict_self_join_new_chronicles = 1
        WHERE id = %s
        """,
        (target_user_id,),
    )
    cursor.execute(
        """
        UPDATE users SET active_character_id = NULL
        WHERE id = %s
          AND active_character_id IN (
            SELECT id FROM characters WHERE campaign_id = %s AND user_id = %s
          )
        """,
        (target_user_id, campaign_id, target_user_id),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify(
        {
            "message": "Left campaign",
            "campaign_id": campaign_id,
            "user_id": target_user_id,
        }
    ), 200


@campaigns_bp.route("/<int:campaign_id>/my-playing-character", methods=["PUT"])
@jwt_required()
def put_my_playing_character(campaign_id):
    """Set this chronicle's playing character (first bind free; switch needs ST unless self_switch_playing_character)."""
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid session"}), 422

    data = request.get_json()
    if not data or "character_id" not in data:
        return jsonify({"error": "character_id is required"}), 400
    raw = data["character_id"]
    try:
        character_id = int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "character_id must be an integer or null"}), 400

    conn = get_db()
    cursor = conn.cursor()
    ensure_campaign_players_active_character_id_column(cursor)
    ensure_users_self_switch_playing_character_column(cursor)
    conn.commit()

    cursor.execute(
        """
        SELECT active_character_id FROM campaign_players
        WHERE campaign_id = %s AND user_id = %s
        """,
        (campaign_id, user_id),
    )
    cp = cursor.fetchone()
    if not cp:
        cursor.close()
        conn.close()
        return jsonify({"error": "Not a member of this campaign"}), 403

    current = cp.get("active_character_id")

    if character_id is None:
        cursor.close()
        conn.close()
        return jsonify({"error": "Use storyteller tools to clear playing character"}), 400

    cursor.execute(
        """
        SELECT id FROM characters
        WHERE id = %s AND user_id = %s AND campaign_id = %s
        """,
        (character_id, user_id, campaign_id),
    )
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Character not in this campaign"}), 404

    if current is not None and int(current) != int(character_id):
        cursor.execute(
            """
            SELECT self_switch_playing_character FROM users WHERE id = %s
            """,
            (user_id,),
        )
        uflags = cursor.fetchone()
        can_self_switch = bool(
            uflags and (uflags.get("self_switch_playing_character") or False)
        )
        if not can_self_switch:
            cursor.close()
            conn.close()
            return (
                jsonify(
                    {
                        "error": (
                            "Switching to another character in this chronicle requires "
                            "storyteller approval."
                        ),
                        "error_code": "playing_character_switch_requires_storyteller",
                    }
                ),
                403,
            )

    cursor.execute(
        """
        UPDATE campaign_players SET active_character_id = %s
        WHERE campaign_id = %s AND user_id = %s
        """,
        (character_id, campaign_id, user_id),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify(
        {
            "message": "Playing character updated",
            "campaign_id": campaign_id,
            "character_id": character_id,
        }
    ), 200


@campaigns_bp.route(
    "/<int:campaign_id>/players/<int:target_user_id>/playing-character",
    methods=["PUT"],
)
@jwt_required()
def put_player_playing_character(campaign_id, target_user_id):
    """Storyteller or site staff sets a member's playing character for this chronicle."""
    try:
        actor_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid session"}), 422

    data = request.get_json()
    if not data or "character_id" not in data:
        return jsonify({"error": "character_id is required"}), 400
    raw = data["character_id"]
    try:
        character_id = int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "character_id must be an integer or null"}), 400

    conn = get_db()
    cursor = conn.cursor()
    ensure_campaign_players_active_character_id_column(cursor)
    conn.commit()

    if not is_campaign_storyteller_or_staff(cursor, actor_id, campaign_id):
        cursor.close()
        conn.close()
        return jsonify({"error": "Storyteller or staff only"}), 403

    cursor.execute(
        """
        SELECT 1 FROM campaign_players WHERE campaign_id = %s AND user_id = %s
        """,
        (campaign_id, target_user_id),
    )
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "User is not a member of this campaign"}), 404

    if character_id is not None:
        cursor.execute(
            """
            SELECT id FROM characters
            WHERE id = %s AND user_id = %s AND campaign_id = %s
            """,
            (character_id, target_user_id, campaign_id),
        )
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Character not in this campaign for this user"}), 404

    cursor.execute(
        """
        UPDATE campaign_players SET active_character_id = %s
        WHERE campaign_id = %s AND user_id = %s
        """,
        (character_id, campaign_id, target_user_id),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify(
        {
            "message": "Playing character set",
            "campaign_id": campaign_id,
            "user_id": target_user_id,
            "character_id": character_id,
        }
    ), 200


@campaigns_bp.route("/<int:campaign_id>/members", methods=["POST"])
@jwt_required()
def post_campaign_add_member(campaign_id):
    """Storyteller or site staff adds a user to campaign_players (invite substitute)."""
    try:
        actor_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid session"}), 422

    data = request.get_json()
    if not data or "user_id" not in data:
        return jsonify({"error": "user_id is required"}), 400
    try:
        new_member_id = int(data["user_id"])
    except (TypeError, ValueError):
        return jsonify({"error": "user_id must be an integer"}), 400

    conn = get_db()
    cursor = conn.cursor()
    ensure_campaigns_listing_columns(cursor)
    ensure_campaign_players_active_character_id_column(cursor)
    conn.commit()

    if not is_campaign_storyteller_or_staff(cursor, actor_id, campaign_id):
        cursor.close()
        conn.close()
        return jsonify({"error": "Storyteller or staff only"}), 403

    cursor.execute("SELECT id FROM users WHERE id = %s", (new_member_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "User not found"}), 404

    now = datetime.utcnow()
    if os.getenv("DATABASE_TYPE", "sqlite").lower() == "postgresql":
        cursor.execute(
            """
            INSERT INTO campaign_players (campaign_id, user_id, joined_at, role)
            VALUES (%s, %s, %s, 'player')
            ON CONFLICT (campaign_id, user_id) DO NOTHING
            """,
            (campaign_id, new_member_id, now),
        )
    else:
        cursor.execute(
            """
            INSERT OR IGNORE INTO campaign_players (campaign_id, user_id, joined_at, role)
            VALUES (%s, %s, %s, 'player')
            """,
            (campaign_id, new_member_id, now),
        )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify(
        {"message": "Member added", "campaign_id": campaign_id, "user_id": new_member_id}
    ), 200