"""
ShadowRealms AI - Dice Rolling API Routes
Handles dice rolls for manual player rolls and AI-triggered rolls
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
from services.dice_service import dice_service
from services.dice_chat import (
    DicePostError,
    check_room,
    embed_line,
    fetch_messages,
    post_roll,
    resolve_speaker,
)
from services.rules_edition import CLASSIC, V5, edition_of
from services.wod_dice import parse_pool_expression
from services.request_validation import (
    RequestValidationError, body_object, optional_str, strict_bool, strict_int,
)
from services.v5_dice import (
    NoWillpowerLeft,
    clamp_hunger,
    spend_willpower,
    willpower_track,
    format_rouse_markdown,
    resolve_rouse,
    rouse_check,
    willpower_reroll as v5_willpower_reroll,
)
import logging
import json

logger = logging.getLogger(__name__)

dice_bp = Blueprint('dice', __name__)


def _json_field(value, default):
    if value is None or value == '':
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _user_can_access_campaign(cursor, user_id: int, campaign_id: int) -> bool:
    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    u = cursor.fetchone()
    if u and u.get("role") == "admin":
        cursor.execute(
            """
            SELECT 1 FROM campaigns c
            WHERE c.id = %s AND c.is_active = TRUE
            """,
            (campaign_id,),
        )
        return cursor.fetchone() is not None
    cursor.execute(
        """
        SELECT 1 FROM campaigns c
        WHERE c.id = %s AND c.is_active = TRUE
          AND (
            c.created_by = %s
            OR EXISTS (
                SELECT 1 FROM campaign_players cp
                WHERE cp.campaign_id = c.id AND cp.user_id = %s
            )
          )
        """,
        (campaign_id, user_id, user_id),
    )
    return cursor.fetchone() is not None


def _character_ok_for_user_campaign(cursor, character_id: int, user_id: int, campaign_id: int) -> bool:
    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    u = cursor.fetchone()
    if u and u.get("role") == "admin":
        cursor.execute(
            """
            SELECT 1 FROM characters
            WHERE id = %s AND campaign_id = %s
            """,
            (character_id, campaign_id),
        )
        return cursor.fetchone() is not None
    cursor.execute(
        """
        SELECT 1 FROM characters
        WHERE id = %s AND user_id = %s AND campaign_id = %s
        """,
        (character_id, user_id, campaign_id),
    )
    return cursor.fetchone() is not None


def _campaign_rules(cursor, campaign_id: int):
    """(game_system, rules_edition) for an active campaign."""
    cursor.execute(
        "SELECT game_system, rules_edition FROM campaigns WHERE id = %s",
        (campaign_id,),
    )
    row = cursor.fetchone() or {}
    return (row.get("game_system") or ""), edition_of(row)


def _location_leniency(cursor, campaign_id: int, location_id):
    """Return (ok, leniency_floor) for a location in this campaign."""
    cursor.execute(
        """
        SELECT dice_leniency_floor FROM locations
        WHERE id = %s AND campaign_id = %s AND is_active = TRUE
        """,
        (location_id, campaign_id),
    )
    loc_row = cursor.fetchone()
    if not loc_row:
        return False, None
    lf = loc_row.get("dice_leniency_floor")
    if lf is None:
        return True, None
    try:
        return True, int(lf)
    except (TypeError, ValueError):
        return True, None


def _character_wod_meta(cursor, character_id: int) -> dict:
    cursor.execute("SELECT wod_meta FROM characters WHERE id = %s", (character_id,))
    row = cursor.fetchone()
    meta = _json_field(row.get("wod_meta") if row else None, {})
    return meta if isinstance(meta, dict) else {}


def _int_arg(data, key, default=None):
    """Integer body field; bools, fractions and non-numeric values raise RequestValidationError (→ 400)."""
    return strict_int(data.get(key), key, default)


def hunger_override_note(hunger: int, sheet_hunger: int) -> str:
    return f"Hunger override: {hunger} (sheet {sheet_hunger})"


def _json_body():
    """The request's JSON object ({} when absent). Raises RequestValidationError for arrays/scalars."""
    return body_object(request.get_json(silent=True))


def _with_posted(body: dict, cursor, message_ids) -> dict:
    """Add server_posted / message_ids / messages (the saved rows) to a dice response."""
    body['server_posted'] = bool(message_ids)
    body['message_ids'] = list(message_ids)
    if message_ids:
        rows = fetch_messages(cursor, message_ids)
        body['messages'] = rows
        embed_line(rows[-1] if rows else None)
    return body


@dice_bp.route('/campaigns/<int:campaign_id>/roll', methods=['POST'])
@jwt_required()
def manual_roll(campaign_id):
    """
    Manual dice roll by player. Mechanics follow the campaign's rules_edition.

    Body (both editions):
        pool_size: int - Number of d10s to roll (or use pool_expression)
        pool_expression: str (optional) - e.g. "4+3", "7-1"
        character_id: int (optional) - Character making the roll
        action_description: str (optional) - What the roll is for
        location_id: int (optional) - Where the roll is happening. When given, the server
            saves the dice animation marker and the result line to that room itself
            (services/dice_chat.py) and answers server_posted: true, message_ids, messages.
        speak_as: 'character' | 'player' | 'staff' (optional) - voice of the result line
        hidden: bool (optional) - post as dice_*_hidden (storyteller/staff only can read it)
    Classic:
        difficulty: int - Target number 2-10 (default 6)
        specialty: bool - natural 10s count and are rerolled
        willpower: bool - +1 automatic success (cannot be cancelled)
    V5:
        difficulty: int - successes needed 0-10 (default 1)
        hunger: int 0-5 (default: character wod_meta.hunger, else 0)
    """
    conn = None
    cursor = None
    try:
        user_id = int(get_jwt_identity())
        try:
            data = _json_body()
            pool_expression = optional_str(data.get('pool_expression'), 'pool_expression')
            pool_size = None if pool_expression else _int_arg(data, 'pool_size')
            difficulty_arg = _int_arg(data, 'difficulty')
            character_id = _int_arg(data, 'character_id')
            location_id = _int_arg(data, 'location_id')
            hunger_arg = _int_arg(data, 'hunger')
            specialty_arg = strict_bool(data.get('specialty'), 'specialty')
            willpower_arg = strict_bool(data.get('willpower'), 'willpower')
            hidden = strict_bool(data.get('hidden'), 'hidden')
            speak_as = optional_str(data.get('speak_as'), 'speak_as')
            action_description = optional_str(
                data.get('action_description'), 'action_description', 'Dice roll'
            )
            if pool_expression:
                pool_size = parse_pool_expression(pool_expression)
            elif not pool_size or pool_size < 1:
                return jsonify({'error': 'pool_size must be at least 1 (or send pool_expression)'}), 400
            elif pool_size > 50:
                return jsonify({'error': 'pool_size must be at most 50'}), 400
        except RequestValidationError as e:
            return jsonify({'error': f'Invalid input: {e.public_message}'}), 400

        conn = get_db()
        cursor = conn.cursor()

        if not _user_can_access_campaign(cursor, user_id, campaign_id):
            return jsonify({'error': 'Campaign not found or access denied'}), 403

        game_system, edition = _campaign_rules(cursor, campaign_id)
        difficulty = difficulty_arg if difficulty_arg is not None else (1 if edition == V5 else 6)

        if edition == V5:
            if difficulty < 0 or difficulty > 10:
                return jsonify({'error': 'difficulty (successes needed) must be between 0 and 10 for V5'}), 400
        elif difficulty < 2 or difficulty > 10:
            return jsonify({'error': 'difficulty must be between 2 and 10'}), 400

        specialty = specialty_arg and edition != V5
        willpower = willpower_arg and edition != V5

        if character_id is not None:
            if not _character_ok_for_user_campaign(cursor, character_id, user_id, campaign_id):
                return jsonify({'error': 'Character not found or not yours in this campaign'}), 400

        leniency_floor = None
        speaker = None
        if location_id is not None:
            ok, leniency_floor = _location_leniency(cursor, campaign_id, location_id)
            if not ok:
                return jsonify({'error': 'Location not found in this campaign'}), 400
            try:
                check_room(cursor, user_id, campaign_id, location_id)
                speaker = resolve_speaker(cursor, user_id, campaign_id, speak_as, character_id)
            except DicePostError as e:
                return jsonify(e.payload), e.status

        if edition == V5:
            sheet_hunger = None
            if character_id is not None:
                sheet_hunger = clamp_hunger(_character_wod_meta(cursor, character_id).get('hunger', 0))
            if hunger_arg is not None:
                if hunger_arg < 0 or hunger_arg > 5:
                    return jsonify({'error': 'hunger must be between 0 and 5'}), 400
                hunger = hunger_arg
            elif sheet_hunger is not None:
                hunger = sheet_hunger
            else:
                hunger = 0
            roll_result = dice_service.roll_v5_pool(
                pool_size, hunger, difficulty, leniency_floor=leniency_floor
            )
            modifiers = {
                'rules_edition': V5,
                'pool_expression': pool_expression or None,
                'leniency_floor': leniency_floor,
                'hunger': roll_result['hunger'],
                'normal_dice': roll_result['normal_dice'],
                'hunger_dice': roll_result['hunger_dice'],
                'rerolled': False,
            }
            # A Hunger sent with the request that differs from the sheet is recorded and
            # shown, so the table can see the roll didn't use the character's Hunger.
            if sheet_hunger is not None and hunger_arg is not None and hunger_arg != sheet_hunger:
                modifiers['sheet_hunger'] = sheet_hunger
                modifiers['hunger_override'] = hunger_arg
                roll_result['sheet_hunger'] = sheet_hunger
                roll_result['hunger_override'] = hunger_arg
                roll_result['hunger_note'] = hunger_override_note(hunger_arg, sheet_hunger)
        else:
            roll_result = dice_service.roll_d10_pool(
                pool_size, difficulty, specialty,
                leniency_floor=leniency_floor, willpower=willpower,
            )
            modifiers = {
                'rules_edition': CLASSIC,
                'specialty': specialty,
                'specialty_rerolls': roll_result.get('specialty_rerolls') or [],
                'willpower': willpower,
                'pool_expression': pool_expression or None,
                'leniency_floor': roll_result.get('leniency_floor'),
            }
        if speaker is not None:
            # Defaults for a later Willpower reroll's chat line.
            modifiers['posted'] = {'hidden': hidden, 'speak_as': speaker[0]}

        cursor.execute("""
            INSERT INTO dice_rolls (
                campaign_id, location_id, user_id, character_id, 
                roll_type, action_description, dice_pool, difficulty,
                results, successes, is_botch, is_critical, modifiers
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            campaign_id, location_id, user_id, character_id,
            'manual', action_description, pool_size, difficulty,
            json.dumps(roll_result['results']), roll_result['successes'],
            roll_result['is_botch'], roll_result['is_critical'],
            json.dumps(modifiers),
        ))
        roll_id = cursor.fetchone()['id']

        roll_result['roll_id'] = roll_id
        if edition == V5:
            roll_result['can_reroll'] = len(roll_result['normal_dice']) > 0

        character_name = None
        if character_id:
            cursor.execute("SELECT name FROM characters WHERE id = %s", (character_id,))
            row = cursor.fetchone()
            if row:
                character_name = row['name']

        if edition == V5:
            chat_message = dice_service.format_v5_roll_for_chat(
                roll_result, character_name, action_description
            )
            if roll_result.get('hunger_note'):
                chat_message += f"\n⚠️ {roll_result['hunger_note']}"
        else:
            chat_message = dice_service.format_roll_for_chat(
                roll_result, character_name, action_description
            )

        message_ids = []
        if speaker is not None:
            message_ids = post_roll(
                cursor, campaign_id=campaign_id, location_id=location_id, user_id=user_id,
                roll_id=roll_id, roll_kind='manual', roll_result=roll_result,
                chat_text=chat_message, hidden=hidden, speaker=speaker,
            )
        conn.commit()

        logger.info("Manual %s roll by user %s: %s successes", edition, user_id, roll_result['successes'])

        return jsonify(_with_posted({
            'roll_id': roll_id,
            'rules_edition': edition,
            'roll_result': roll_result,
            'chat_message': chat_message
        }, cursor, message_ids)), 200

    except RequestValidationError as e:
        return jsonify({'error': e.public_message}), 400
    except Exception as e:
        logger.exception("Error processing manual roll: %s", e)
        return jsonify({'error': 'Failed to process roll'}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@dice_bp.route('/campaigns/<int:campaign_id>/roll/<int:roll_id>/reroll', methods=['POST'])
@jwt_required()
def willpower_reroll(campaign_id, roll_id):
    """
    V5 Willpower reroll: reroll up to 3 normal (non-Hunger) dice of an earlier roll, once.
    Only the user who made the roll may reroll it. With a character on the roll it costs
    1 Willpower (1 Superficial Willpower damage, see v5_dice.spend_willpower); 409 when the
    track is full of Aggravated damage. Rolls without a character cost nothing.

    Body: indices: [int] - positions in roll_result.normal_dice (0-based), 1-3 entries
          location_id: int (optional) - the room of the original roll; when given, the server
              posts the marker + result line there (server_posted: true, message_ids, messages)
          speak_as / hidden (optional) - default to what the original roll was posted with
    """
    conn = None
    cursor = None
    try:
        user_id = int(get_jwt_identity())
        try:
            data = _json_body()
            location_id = _int_arg(data, 'location_id')
            hidden_arg = None if data.get('hidden') is None else strict_bool(data.get('hidden'), 'hidden')
            speak_as_arg = optional_str(data.get('speak_as'), 'speak_as') or None
        except RequestValidationError as e:
            return jsonify({'error': e.public_message}), 400
        conn = get_db()
        cursor = conn.cursor()

        if not _user_can_access_campaign(cursor, user_id, campaign_id):
            return jsonify({'error': 'Campaign not found or access denied'}), 403
        _, edition = _campaign_rules(cursor, campaign_id)
        if edition != V5:
            return jsonify({'error': 'Willpower rerolls are a V5 rule; this campaign uses classic rules'}), 400

        cursor.execute(
            "SELECT * FROM dice_rolls WHERE id = %s AND campaign_id = %s",
            (roll_id, campaign_id),
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Roll not found'}), 404
        if int(row['user_id']) != user_id:
            return jsonify({'error': 'Only the player who rolled can reroll'}), 403
        mods = _json_field(row.get('modifiers'), {})
        if not isinstance(mods, dict) or mods.get('rules_edition') != V5 or row['roll_type'] != 'manual':
            return jsonify({'error': 'Only V5 manual rolls can be rerolled'}), 400
        if mods.get('rerolled'):
            return jsonify({'error': 'This roll has already been rerolled'}), 409

        speaker = None
        posted = mods.get('posted') if isinstance(mods.get('posted'), dict) else {}
        hidden = bool(posted.get('hidden')) if hidden_arg is None else hidden_arg
        if location_id is not None:
            if row.get('location_id') is not None and int(row['location_id']) != location_id:
                return jsonify({'error': 'A reroll is posted to the room of the original roll'}), 400
            try:
                check_room(cursor, user_id, campaign_id, location_id)
                speaker = resolve_speaker(
                    cursor, user_id, campaign_id,
                    speak_as_arg or posted.get('speak_as'), row.get('character_id'),
                )
            except DicePostError as e:
                return jsonify(e.payload), e.status

        normal = mods.get('normal_dice') or []
        hunger = mods.get('hunger_dice') or []
        leniency_floor = mods.get('leniency_floor')
        try:
            res = v5_willpower_reroll(
                normal, hunger, int(row['difficulty']), data.get('indices'),
                leniency_floor=leniency_floor,
            )
        except RequestValidationError as e:
            return jsonify({'error': e.public_message}), 400
        res['message'] = dice_service.v5_message(res)
        res['leniency_floor'] = leniency_floor

        # The reroll costs 1 Willpower: 1 Superficial Willpower damage on the character's
        # sheet (a Superficial box turns Aggravated when the track is full). Rolls without
        # a character (NPC / storyteller) cost nothing.
        character_id = row.get('character_id')
        spend = None
        character_meta = None
        character_name = None
        if character_id:
            cursor.execute(
                "SELECT name, wod_meta, attributes FROM characters WHERE id = %s FOR UPDATE",
                (character_id,),
            )
            crow = cursor.fetchone() or {}
            character_name = crow.get('name')
            character_meta = _json_field(crow.get('wod_meta'), {})
            if not isinstance(character_meta, dict):
                character_meta = {}
            track = willpower_track(character_meta, _json_field(crow.get('attributes'), {}))
            if track is None:
                conn.rollback()
                return jsonify({
                    'error': 'This character has no Willpower on the sheet '
                             '(set the Willpower track, or Composure and Resolve)',
                }), 409
            try:
                spend = spend_willpower(track)
            except NoWillpowerLeft:
                conn.rollback()
                return jsonify({
                    'error': 'No Willpower left: the Willpower track is full of Aggravated damage',
                    'willpower': track,
                }), 409
            res['willpower_cost'] = spend['damage']

        mods.update({
            'rerolled': True,
            'rerolled_indices': res['rerolled_indices'],
            'original_normal_dice': normal,
            'normal_dice': res['normal_dice'],
        })
        if spend is not None:
            mods.update({
                'willpower_before': spend['before'],
                'willpower_after': spend['after'],
                'willpower_cost': spend['damage'],
            })
        cursor.execute(
            """
            UPDATE dice_rolls
               SET results = %s, successes = %s, is_critical = %s, modifiers = %s
             WHERE id = %s AND (modifiers IS NULL OR modifiers NOT LIKE %s)
            """,
            (
                json.dumps(res['results']), res['successes'], res['is_critical'],
                json.dumps(mods), roll_id, '%"rerolled": true%',
            ),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return jsonify({'error': 'This roll has already been rerolled'}), 409

        if spend is not None:
            character_meta['willpower'] = {**(character_meta.get('willpower') if isinstance(
                character_meta.get('willpower'), dict) else {}), **spend['after']}
            cursor.execute(
                "UPDATE characters SET wod_meta = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (json.dumps(character_meta), character_id),
            )
        res['roll_id'] = roll_id
        res['can_reroll'] = False
        chat_message = dice_service.format_v5_roll_for_chat(
            res, character_name, f"{row['action_description']} (Willpower reroll)"
        )
        message_ids = []
        if speaker is not None:
            message_ids = post_roll(
                cursor, campaign_id=campaign_id, location_id=location_id, user_id=user_id,
                roll_id=roll_id, roll_kind='reroll', roll_result=res,
                chat_text=chat_message, hidden=hidden, speaker=speaker,
            )
        conn.commit()
        return jsonify(_with_posted({
            'roll_id': roll_id,
            'rules_edition': V5,
            'roll_result': res,
            'chat_message': chat_message,
            'willpower_spent': spend is not None,
            'willpower_before': spend['before'] if spend else None,
            'willpower_after': spend['after'] if spend else None,
        }, cursor, message_ids)), 200
    except Exception as e:
        logger.exception("Error processing reroll: %s", e)
        return jsonify({'error': 'Failed to process reroll'}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@dice_bp.route('/campaigns/<int:campaign_id>/rouse', methods=['POST'])
@jwt_required()
def rouse_check_route(campaign_id):
    """
    V5 Rouse check: roll one die; 6+ = no Hunger gain, else Hunger +1 (max 5).

    Body: character_id: int (optional) - Hunger read from / written to wod_meta.hunger
          hunger: int 0-5 (optional, used when no character_id)
          location_id: int - room the check is made in; the server posts the result line there
              (ai_message_kind dice_rouse:<roll_id>) and answers server_posted, message_ids, messages
          speak_as: 'character' | 'player' | 'staff' (optional) - voice of that line
    """
    conn = None
    cursor = None
    try:
        user_id = int(get_jwt_identity())
        try:
            data = _json_body()
            character_id = _int_arg(data, 'character_id')
            location_id = _int_arg(data, 'location_id')
            # Used only without character_id (e.g. a storyteller rousing for an NPC).
            hunger_arg = strict_int(data.get('hunger'), 'hunger', None, 0, 5)
            speak_as = optional_str(data.get('speak_as'), 'speak_as') or None
        except RequestValidationError as e:
            return jsonify({'error': f'Invalid input: {e.public_message}'}), 400

        conn = get_db()
        cursor = conn.cursor()
        if not _user_can_access_campaign(cursor, user_id, campaign_id):
            return jsonify({'error': 'Campaign not found or access denied'}), 403
        _, edition = _campaign_rules(cursor, campaign_id)
        if edition != V5:
            return jsonify({'error': 'Rouse checks are a V5 rule; this campaign uses classic rules'}), 400

        if location_id is None:
            return jsonify({'error': 'location_id is required'}), 400
        ok, leniency_floor = _location_leniency(cursor, campaign_id, location_id)
        if not ok:
            return jsonify({'error': 'Location not found in this campaign'}), 400

        meta = None
        character_name = None
        if character_id is not None:
            if not _character_ok_for_user_campaign(cursor, character_id, user_id, campaign_id):
                return jsonify({'error': 'Character not found or not yours in this campaign'}), 400
        try:
            check_room(cursor, user_id, campaign_id, location_id)
            speaker = resolve_speaker(
                cursor, user_id, campaign_id,
                speak_as or ('character' if character_id is not None else 'player'), character_id,
            )
        except DicePostError as e:
            return jsonify(e.payload), e.status
        if character_id is not None:
            cursor.execute(
                "SELECT name, wod_meta FROM characters WHERE id = %s FOR UPDATE",
                (character_id,),
            )
            crow = cursor.fetchone() or {}
            character_name = crow.get('name')
            meta = _json_field(crow.get('wod_meta'), {})
            if not isinstance(meta, dict):
                meta = {}
            hunger_before = clamp_hunger(meta.get('hunger', 0))
        else:
            hunger_before = hunger_arg if hunger_arg is not None else 0

        # Room leniency: the single die never shows a failure below the floor's spirit
        # (no 1s); otherwise a plain d10.
        if leniency_floor is not None:
            from services.wod_dice import roll_d10s

            die = roll_d10s(1, leniency_floor=leniency_floor)[0]
            res = resolve_rouse(die, hunger_before)
        else:
            res = rouse_check(hunger_before)

        if meta is not None and res['hunger_after'] != hunger_before:
            meta['hunger'] = res['hunger_after']
            cursor.execute(
                "UPDATE characters SET wod_meta = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (json.dumps(meta), character_id),
            )

        cursor.execute(
            """
            INSERT INTO dice_rolls (
                campaign_id, location_id, user_id, character_id,
                roll_type, action_description, dice_pool, difficulty,
                results, successes, is_botch, is_critical, modifiers
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                campaign_id, location_id, user_id, character_id,
                'rouse', 'Rouse check', 1, 6,
                json.dumps([res['die']]), 1 if res['success'] else 0, False, False,
                json.dumps({
                    'rules_edition': V5,
                    'hunger_before': res['hunger_before'],
                    'hunger_after': res['hunger_after'],
                    'leniency_floor': leniency_floor,
                }),
            ),
        )
        roll_id = cursor.fetchone()['id']

        res['roll_id'] = roll_id
        res['character_id'] = character_id
        res['rules_edition'] = V5
        res['chat_message'] = format_rouse_markdown(res, character_name)
        message_ids = post_roll(
            cursor, campaign_id=campaign_id, location_id=location_id, user_id=user_id,
            roll_id=roll_id, roll_kind='rouse', roll_result=None,
            chat_text=res['chat_message'], hidden=False, speaker=speaker,
        )
        conn.commit()
        return jsonify(_with_posted(res, cursor, message_ids)), 200
    except Exception as e:
        logger.exception("Error processing rouse check: %s", e)
        return jsonify({'error': 'Failed to process rouse check'}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@dice_bp.route('/campaigns/<int:campaign_id>/roll/contested', methods=['POST'])
@jwt_required()
def contested_roll(campaign_id):
    """
    Contested roll between two parties
    
    Body:
        attacker_pool: int (1-50)
        defender_pool: int (1-50)
        difficulty: int (optional, default 6; classic only)
        attacker_hunger / defender_hunger: int 0-5 (optional; V5 only)
        attacker_character_id: int (optional)
        defender_character_id: int (optional)
        action_description: str (optional)
        location_id: int (optional)
    """
    conn = None
    cursor = None
    try:
        user_id = int(get_jwt_identity())

        try:
            data = _json_body()
            action_description = optional_str(
                data.get('action_description'), 'action_description', 'Contested roll'
            )
            attacker_pool = _int_arg(data, 'attacker_pool')
            defender_pool = _int_arg(data, 'defender_pool')
            difficulty = _int_arg(data, 'difficulty', 6)
            attacker_hunger = _int_arg(data, 'attacker_hunger', 0)
            defender_hunger = _int_arg(data, 'defender_hunger', 0)
            location_id = _int_arg(data, 'location_id')
            attacker_cid = _int_arg(data, 'attacker_character_id')
            defender_cid = _int_arg(data, 'defender_character_id')
        except RequestValidationError as e:
            return jsonify({'error': f'Invalid input: {e.public_message}'}), 400

        if attacker_pool is None or defender_pool is None:
            return jsonify({'error': 'Both attacker_pool and defender_pool required'}), 400
        for name, v in (('attacker_pool', attacker_pool), ('defender_pool', defender_pool)):
            if v < 1 or v > 50:
                return jsonify({'error': f'{name} must be between 1 and 50'}), 400
        for name, v in (('attacker_hunger', attacker_hunger), ('defender_hunger', defender_hunger)):
            if v < 0 or v > 5:
                return jsonify({'error': f'{name} must be between 0 and 5'}), 400

        conn = get_db()
        cursor = conn.cursor()
        if not _user_can_access_campaign(cursor, user_id, campaign_id):
            return jsonify({'error': 'Campaign not found or access denied'}), 403
        _, edition = _campaign_rules(cursor, campaign_id)
        if edition != V5 and (difficulty < 2 or difficulty > 10):
            return jsonify({'error': 'difficulty must be between 2 and 10'}), 400
        if location_id is not None:
            ok, _ = _location_leniency(cursor, campaign_id, location_id)
            if not ok:
                return jsonify({'error': 'Location not found in this campaign'}), 400
        for cid in (attacker_cid, defender_cid):
            if cid is not None:
                cursor.execute(
                    "SELECT 1 FROM characters WHERE id = %s AND campaign_id = %s",
                    (cid, campaign_id),
                )
                if not cursor.fetchone():
                    return jsonify({'error': 'Character not found in this campaign'}), 400

        result = dice_service.roll_contested(
            attacker_pool, defender_pool, difficulty,
            rules_edition=edition,
            attacker_hunger=attacker_hunger, defender_hunger=defender_hunger,
        )
        stored_difficulty = 0 if edition == V5 else difficulty

        for side, pool, cid in (
            ('attacker', attacker_pool, attacker_cid),
            ('defender', defender_pool, defender_cid),
        ):
            r = result[f'{side}_roll']
            mods = {'rules_edition': edition}
            if edition == V5:
                # Outcome flags come from the contest (ties go to the attacker), not a difficulty.
                mods.update({
                    'hunger': r['hunger'],
                    'normal_dice': r['normal_dice'],
                    'hunger_dice': r['hunger_dice'],
                    'contest_won': r['contest_won'],
                    'opponent_successes': r['opponent_successes'],
                    'outcome': r['outcome'],
                    'is_critical': r['is_critical'],
                    'is_messy_critical': r['is_messy_critical'],
                    'is_bestial_failure': r['is_bestial_failure'],
                    'winner': result['winner'],
                })
            cursor.execute("""
                INSERT INTO dice_rolls (
                    campaign_id, location_id, user_id, character_id,
                    roll_type, action_description, dice_pool, difficulty,
                    results, successes, is_botch, is_critical, modifiers
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                campaign_id, location_id, user_id, cid,
                f'contested_{side}', action_description, pool, stored_difficulty,
                json.dumps(r['results']), r['successes'], r['is_botch'], r['is_critical'],
                json.dumps(mods),
            ))

        conn.commit()
        logger.info(f"Contested {edition} roll in campaign {campaign_id}: {result['winner']} wins".replace("\r\n", "").replace("\n", ""))

        return jsonify({
            'rules_edition': edition,
            'result': result,
            'message': result['message']
        }), 200

    except Exception as e:
        logger.exception("Error processing contested roll: %s", e)
        return jsonify({'error': 'Failed to process contested roll'}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def _classic_tn_to_v5_difficulty(tn: int) -> int:
    """Map an AI-chosen classic target number onto V5 successes needed (TN 6 -> 2)."""
    return max(1, min(5, int(tn) - 4))


@dice_bp.route('/campaigns/<int:campaign_id>/roll/ai', methods=['POST'])
@jwt_required()
def ai_roll(campaign_id):
    """
    AI-triggered roll for NPC actions, events, weather, etc.
    Can be called by AI service or by admin
    
    Body:
        action_type: str - 'npc_attack', 'npc_social', 'weather', 'event', 'mystery'
        context: dict - Context for determining dice pool
        location_id: int (optional)
        description: str (optional)
    """
    conn = None
    cursor = None
    try:
        user_id = int(get_jwt_identity())
        data = _json_body()
        
        # Verify user is admin (AI service should have admin token)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if not row or row['role'] != 'admin':
            return jsonify({'error': 'Unauthorized - admin only'}), 403
        if not _user_can_access_campaign(cursor, user_id, campaign_id):
            return jsonify({'error': 'Campaign not found'}), 404
        _, edition = _campaign_rules(cursor, campaign_id)
        
        action_type = str(data.get('action_type', 'event'))
        context = data.get('context') or {}
        if not isinstance(context, dict):
            context = {}
        location_id = _int_arg(data, 'location_id')
        if location_id is not None:
            ok, _ = _location_leniency(cursor, campaign_id, location_id)
            if not ok:
                return jsonify({'error': 'Location not found in this campaign'}), 400
        description = optional_str(data.get('description'), 'description', f'AI {action_type} roll')
        
        # AI determines appropriate dice pool
        pool_size, difficulty = dice_service.ai_determine_pool(action_type, context)
        
        if edition == V5:
            difficulty = _classic_tn_to_v5_difficulty(difficulty)
            roll_result = dice_service.roll_v5_pool(pool_size, 0, difficulty)
            mods = {**context, 'rules_edition': V5, 'hunger': 0,
                    'normal_dice': roll_result['normal_dice'], 'hunger_dice': []}
        else:
            roll_result = dice_service.roll_d10_pool(pool_size, difficulty)
            mods = {**context, 'rules_edition': CLASSIC}
        
        cursor.execute("""
            INSERT INTO dice_rolls (
                campaign_id, location_id, user_id,
                roll_type, action_description, dice_pool, difficulty,
                results, successes, is_botch, is_critical, modifiers
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            campaign_id, location_id, user_id,
            f'ai_{action_type}', description, pool_size, difficulty,
            json.dumps(roll_result['results']), roll_result['successes'],
            roll_result['is_botch'], roll_result['is_critical'],
            json.dumps(mods)
        ))
        
        roll_id = cursor.fetchone()['id']
        conn.commit()
        roll_result['roll_id'] = roll_id
        
        logger.info(f"AI roll ({action_type}, {edition}) in campaign {campaign_id}: {roll_result['successes']} successes".replace("\r\n", "").replace("\n", ""))
        
        return jsonify({
            'roll_id': roll_id,
            'rules_edition': edition,
            'roll_result': roll_result,
            'pool_size': pool_size,
            'difficulty': difficulty,
            'action_type': action_type
        }), 200
        
    except RequestValidationError as e:
        return jsonify({'error': f'Invalid input: {e.public_message}'}), 400
    except Exception as e:
        logger.exception("Error processing AI roll: %s", e)
        return jsonify({'error': 'Failed to process AI roll'}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@dice_bp.route('/campaigns/<int:campaign_id>/rolls', methods=['GET'])
@jwt_required()
def get_roll_history(campaign_id):
    """
    Admin-only: list dice rolls for one campaign location (everyone’s rolls in that room).

    Query params:
        location_id: int (required) — current chat room / channel
        limit: int (optional, default 100, max 200)
    """
    try:
        user_id = int(get_jwt_identity())
        limit = request.args.get('limit', 100, type=int) or 100
        limit = max(1, min(int(limit), 200))
        location_id = request.args.get('location_id', type=int)
        if not location_id:
            return jsonify({'error': 'location_id query parameter is required'}), 400

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            urow = cursor.fetchone()
            if not urow or urow.get('role') != 'admin':
                return jsonify({'error': 'Admin access required'}), 403

            cursor.execute(
                """
                SELECT 1 FROM locations
                WHERE id = %s AND campaign_id = %s AND is_active = TRUE
                """,
                (location_id, campaign_id),
            )
            if not cursor.fetchone():
                return jsonify({'error': 'Location not found in this campaign'}), 404

            cursor.execute(
                """
                SELECT dr.*, u.username, c.name AS character_name
                FROM dice_rolls dr
                LEFT JOIN users u ON dr.user_id = u.id
                LEFT JOIN characters c ON dr.character_id = c.id
                WHERE dr.campaign_id = %s AND dr.location_id = %s
                ORDER BY dr.rolled_at DESC
                LIMIT %s
                """,
                (campaign_id, location_id, limit),
            )

            rolls = []
            for row in cursor.fetchall():
                ra = row['rolled_at']
                rolled_at_out = ra.isoformat() if hasattr(ra, 'isoformat') else str(ra)
                rolls.append({
                    'id': row['id'],
                    'campaign_id': row['campaign_id'],
                    'location_id': row['location_id'],
                    'user_id': row['user_id'],
                    'character_id': row['character_id'],
                    'roll_type': row['roll_type'],
                    'action_description': row['action_description'],
                    'dice_pool': row['dice_pool'],
                    'difficulty': row['difficulty'],
                    'results': _json_field(row['results'], []),
                    'successes': row['successes'],
                    'is_botch': bool(row['is_botch']),
                    'is_critical': bool(row['is_critical']),
                    'modifiers': _json_field(row.get('modifiers'), {}),
                    'rolled_at': rolled_at_out,
                    'username': row['username'],
                    'character_name': row['character_name'],
                })

            return jsonify(rolls), 200
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        logger.exception("Error fetching roll history: %s", e)
        return jsonify({'error': 'Failed to fetch roll history'}), 500


@dice_bp.route('/campaigns/<int:campaign_id>/roll/templates', methods=['GET'])
@jwt_required()
def get_roll_templates(campaign_id):
    """Get roll templates (system-wide and campaign-specific)"""
    conn = None
    cursor = None
    try:
        user_id = int(get_jwt_identity())
        conn = get_db()
        cursor = conn.cursor()
        if not _user_can_access_campaign(cursor, user_id, campaign_id):
            return jsonify({'error': 'Campaign not found or access denied'}), 403
        
        cursor.execute("""
            SELECT * FROM dice_roll_templates
            WHERE campaign_id = %s OR is_system = 1
            ORDER BY is_system DESC, name ASC
        """, (campaign_id,))
        
        templates = []
        for row in cursor.fetchall():
            templates.append({
                'id': row['id'],
                'campaign_id': row['campaign_id'],
                'name': row['name'],
                'description': row['description'],
                'dice_pool_formula': row['dice_pool_formula'],
                'default_difficulty': row['default_difficulty'],
                'created_by': row['created_by'],
                'is_system': row['is_system'],
                'created_at': row['created_at']
            })
        
        return jsonify(templates), 200
        
    except Exception as e:
        logger.error(f"Error fetching roll templates: {e}")
        return jsonify({'error': 'Failed to fetch templates'}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

