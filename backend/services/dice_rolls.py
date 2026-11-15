"""
The manual dice roll core, shared by POST /campaigns/<id>/roll (routes/dice.py) and the downtime
phase roll (routes/downtime.py).

perform_manual_roll works on the caller's cursor: it never opens a connection and never commits,
so a caller can save the roll and its own rows in one transaction. A refusal before rolling raises
DicePostError(payload, status); bad input raises RequestValidationError (both from fixed text).
"""

import json
import logging

from services.dice_chat import DicePostError, check_room, post_roll, resolve_speaker
from services.dice_service import dice_service
from services.rules_edition import CLASSIC, V5, edition_of, reroll_ones_cancel
from services.v5_dice import clamp_hunger, normalize_v5_leniency

logger = logging.getLogger(__name__)


def json_field(value, default):
    if value is None or value == '':
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def user_can_access_campaign(cursor, user_id: int, campaign_id: int) -> bool:
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


def character_ok_for_user_campaign(cursor, character_id: int, user_id: int, campaign_id: int) -> bool:
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


def campaign_rules(cursor, campaign_id: int):
    """(game_system, rules_edition) for an active campaign."""
    cursor.execute(
        "SELECT game_system, rules_edition FROM campaigns WHERE id = %s",
        (campaign_id,),
    )
    row = cursor.fetchone() or {}
    return (row.get("game_system") or ""), edition_of(row)


def location_leniency(cursor, campaign_id: int, location_id):
    """
    Return (ok, leniency_floor, v5_leniency) for a location in this campaign.
    The floor is the Classic setting, v5_leniency the V5 switches (normalized, or None);
    callers use the one that matches the campaign's edition.
    """
    cursor.execute(
        """
        SELECT dice_leniency_floor, dice_leniency_v5 FROM locations
        WHERE id = %s AND campaign_id = %s AND is_active = TRUE
        """,
        (location_id, campaign_id),
    )
    loc_row = cursor.fetchone()
    if not loc_row:
        return False, None, None
    v5 = normalize_v5_leniency(loc_row.get("dice_leniency_v5"))
    lf = loc_row.get("dice_leniency_floor")
    if lf is None:
        return True, None, v5
    try:
        return True, int(lf), v5
    except (TypeError, ValueError):
        return True, None, v5


def character_wod_meta(cursor, character_id: int) -> dict:
    cursor.execute("SELECT wod_meta FROM characters WHERE id = %s", (character_id,))
    row = cursor.fetchone()
    meta = json_field(row.get("wod_meta") if row else None, {})
    return meta if isinstance(meta, dict) else {}


def hunger_override_note(hunger: int, sheet_hunger: int) -> str:
    return f"Hunger override: {hunger} (sheet {sheet_hunger})"


def _refuse(message, status=400):
    raise DicePostError({'error': message}, status)


def perform_manual_roll(
    cursor, user_id: int, campaign_id: int, *, pool_size: int, pool_expression=None,
    difficulty_arg=None, character_id=None, location_id=None, hunger_arg=None,
    specialty_arg=False, willpower_arg=False, hidden=False, speak_as=None,
    action_description='Dice roll', roll_type='manual',
) -> dict:
    """
    Roll, insert the dice_rolls row (and, with location_id, the room post) on ``cursor``.
    No commit. Returns {roll_id, edition, roll_result, chat_message, message_ids}.
    """
    if not user_can_access_campaign(cursor, user_id, campaign_id):
        _refuse('Campaign not found or access denied', 403)

    game_system, edition = campaign_rules(cursor, campaign_id)
    difficulty = difficulty_arg if difficulty_arg is not None else (1 if edition == V5 else 6)

    if edition == V5:
        if difficulty < 0 or difficulty > 10:
            _refuse('difficulty (successes needed) must be between 0 and 10 for V5')
    elif difficulty < 2 or difficulty > 10:
        _refuse('difficulty must be between 2 and 10')

    specialty = specialty_arg and edition != V5
    willpower = willpower_arg and edition != V5

    if character_id is not None:
        if not character_ok_for_user_campaign(cursor, character_id, user_id, campaign_id):
            _refuse('Character not found or not yours in this campaign')

    leniency_floor = None
    v5_leniency = None
    speaker = None
    if location_id is not None:
        ok, leniency_floor, v5_leniency = location_leniency(cursor, campaign_id, location_id)
        if not ok:
            _refuse('Location not found in this campaign')
        check_room(cursor, user_id, campaign_id, location_id)
        speaker = resolve_speaker(cursor, user_id, campaign_id, speak_as, character_id)

    if edition == V5:
        sheet_hunger = None
        if character_id is not None:
            sheet_hunger = clamp_hunger(character_wod_meta(cursor, character_id).get('hunger', 0))
        if hunger_arg is not None:
            if hunger_arg < 0 or hunger_arg > 5:
                _refuse('hunger must be between 0 and 5')
            hunger = hunger_arg
        elif sheet_hunger is not None:
            hunger = sheet_hunger
        else:
            hunger = 0
        roll_result = dice_service.roll_v5_pool(
            pool_size, hunger, difficulty, v5_leniency=v5_leniency
        )
        modifiers = {
            'rules_edition': V5,
            'pool_expression': pool_expression or None,
            'v5_leniency': roll_result['v5_leniency'],
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
            reroll_ones_cancel=reroll_ones_cancel(game_system),
        )
        modifiers = {
            'rules_edition': CLASSIC,
            'specialty': specialty,
            'reroll_ones_cancel': roll_result['reroll_ones_cancel'],
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
        roll_type, action_description, pool_size, difficulty,
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
    return {
        'roll_id': roll_id,
        'edition': edition,
        'roll_result': roll_result,
        'chat_message': chat_message,
        'message_ids': message_ids,
    }
