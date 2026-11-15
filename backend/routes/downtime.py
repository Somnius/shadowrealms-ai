"""
Downtime rounds (0.32): a Storyteller tool. No AI anywhere in this module.

Round flow: the Storyteller opens a round (open); each player declares one phase per project and
rolls; the Storyteller moves the round to resolving (players are locked out, 409), writes the
results and the indicator / variable deltas, then releases the round: all results become visible
to the players together, and the next round can open.

  Storyteller (campaign creator, or site admin/helper):
    GET   /api/campaigns/<cid>/downtime/rounds
    POST  /api/campaigns/<cid>/downtime/rounds                    {title}
    POST  /api/campaigns/<cid>/downtime/rounds/<rid>/resolve      open -> resolving
    POST  /api/campaigns/<cid>/downtime/rounds/<rid>/reopen       resolving -> open
    POST  /api/campaigns/<cid>/downtime/rounds/<rid>/release      resolving -> released {force}
  Player (campaign_players.active_character_id; not fallen, not play-suspended):
    GET   /api/campaigns/<cid>/downtime                           own projects, phases, results
    POST  /api/campaigns/<cid>/downtime/projects                  {title, goal, parent_id}
    POST  /api/campaigns/<cid>/downtime/projects/<pid>/phases     {action}

Errors answer {error: English text, code: stable code} so the frontend can translate the code.
Player responses are built from whitelists (_player_*): indicators, chronicle variables, ST notes
and a hidden difficulty never reach them. The schema comes from database.ensure_downtime_tables,
run by migrate_db() only (never from a request).
"""

import functools
import logging
import os
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from database import get_db
from services.character_death import death_of
from services.dice_chat import DicePostError
from services.dice_rolls import json_field, perform_manual_roll
from services.playing_character import is_campaign_storyteller_or_staff
from services.request_validation import RequestValidationError, body_object, strict_bool, strict_int
from services.rules_edition import V5
from services.wod_dice import parse_pool_expression

logger = logging.getLogger(__name__)

downtime_bp = Blueprint("downtime", __name__)

TITLE_MAX = 200
GOAL_MAX = 2000
ACTION_MAX = 2000
PROJECTS_MAX = 30


class DowntimeError(Exception):
    """A refusal: answered as {error, code, ...extra} with the status."""

    def __init__(self, code, message, status=400, **extra):
        super().__init__(code)
        self.status = status
        self.payload = {"error": message, "code": code, **extra}


def _is_pg():
    return os.getenv("DATABASE_TYPE", "sqlite").lower() == "postgresql"


def _for_update():
    """Row locks exist on PostgreSQL only; SQLite serialises writers anyway."""
    return " FOR UPDATE" if _is_pg() else ""


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ts(value):
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _flag(value):
    return bool(value) and value not in ("0", "false", "f")


def _is_integrity_error(exc):
    return type(exc).__name__ in ("IntegrityError", "UniqueViolation")


def _body():
    return body_object(request.get_json(silent=True))


def _text(data, key, max_len, required=False):
    value = data.get(key)
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise DowntimeError("invalid_input", f"{key} must be text")
    value = value.strip()
    if required and not value:
        raise DowntimeError(f"{key}_required", f"{key} is required")
    if len(value) > max_len:
        raise DowntimeError(f"{key}_too_long", f"{key} must be at most {max_len} characters",
                            max=max_len)
    return value


def _api(fn):
    """JWT, one connection, commit on success, rollback on any refusal or error."""

    @functools.wraps(fn)
    def wrapper(**kwargs):
        conn = get_db()
        cursor = conn.cursor()
        try:
            user_id = int(get_jwt_identity())
            body, status = fn(cursor, user_id, **kwargs)
            conn.commit()
            return jsonify(body), status
        except DowntimeError as e:
            conn.rollback()
            return jsonify(e.payload), e.status
        except RequestValidationError as e:
            conn.rollback()
            return jsonify({"error": e.public_message, "code": "invalid_input"}), 400
        except DicePostError as e:
            conn.rollback()
            payload = dict(e.payload) if isinstance(e.payload, dict) else {"error": str(e.payload)}
            payload.setdefault("code", "roll_refused")
            return jsonify(payload), e.status
        except Exception as e:  # noqa: BLE001 - logged, generic answer
            conn.rollback()
            if _is_integrity_error(e):
                return jsonify({"error": "That was changed at the same time; reload and try again",
                                "code": "conflict"}), 409
            logger.exception("downtime request failed: %s", type(e).__name__)
            return jsonify({"error": "Downtime request failed", "code": "server_error"}), 500
        finally:
            close = getattr(cursor, "close", None)
            if close:
                close()
            conn.close()

    return jwt_required()(wrapper)


# --------------------------------------------------------------------------- who is asking


def _campaign(cursor, campaign_id):
    cursor.execute(
        "SELECT id, created_by, rules_edition, game_system, is_active FROM campaigns WHERE id = %s",
        (campaign_id,),
    )
    row = cursor.fetchone()
    if not row or row.get("is_active") in (False, 0):
        raise DowntimeError("campaign_not_found", "Chronicle not found", 404)
    return row


def _require_st(cursor, user_id, campaign_id):
    camp = _campaign(cursor, campaign_id)
    if not is_campaign_storyteller_or_staff(cursor, user_id, campaign_id):
        raise DowntimeError("storyteller_only", "Only the Storyteller can do this", 403)
    return camp


def _playing_character(cursor, user_id, campaign_id):
    """The user's playing character here (campaign_players.active_character_id), or a refusal code."""
    cursor.execute(
        "SELECT active_character_id FROM campaign_players WHERE campaign_id = %s AND user_id = %s",
        (campaign_id, user_id),
    )
    cp = cursor.fetchone()
    if not cp:
        return None, "not_a_member"
    char_id = cp.get("active_character_id")
    if char_id is None:
        return None, "no_playing_character"
    cursor.execute(
        "SELECT id, name, user_id, campaign_id, play_suspended FROM characters WHERE id = %s",
        (char_id,),
    )
    ch = cursor.fetchone()
    if not ch or str(ch.get("user_id")) != str(user_id) or str(ch.get("campaign_id")) != str(campaign_id):
        return None, "no_playing_character"
    if _flag(ch.get("play_suspended")):
        return None, "character_suspended"
    if death_of(cursor, ch["id"]):
        return None, "character_fallen"
    return ch, None


_PLAYER_REFUSALS = {
    "not_a_member": "You are not a player in this chronicle",
    "no_playing_character": "Pick your playing character in this chronicle first",
    "character_suspended": "Your character's play is suspended",
    "character_fallen": "Your character has fallen",
}


def _require_player(cursor, user_id, campaign_id):
    _campaign(cursor, campaign_id)
    ch, problem = _playing_character(cursor, user_id, campaign_id)
    if problem:
        raise DowntimeError(problem, _PLAYER_REFUSALS[problem], 403)
    return ch


# --------------------------------------------------------------------------- rounds


def _round_dict(r):
    return {
        "id": r["id"],
        "title": r.get("title") or "",
        "status": r["status"],
        "opened_at": _ts(r.get("opened_at")),
        "resolving_at": _ts(r.get("resolving_at")),
        "released_at": _ts(r.get("released_at")),
    }


def _live_round(cursor, campaign_id, lock=False):
    cursor.execute(
        "SELECT * FROM downtime_rounds WHERE campaign_id = %s AND status <> 'released' "
        "ORDER BY id DESC LIMIT 1" + (_for_update() if lock else ""),
        (campaign_id,),
    )
    return cursor.fetchone()


def _locked_round(cursor, campaign_id, round_id):
    cursor.execute(
        "SELECT * FROM downtime_rounds WHERE id = %s AND campaign_id = %s" + _for_update(),
        (round_id, campaign_id),
    )
    row = cursor.fetchone()
    if not row:
        raise DowntimeError("round_not_found", "Downtime round not found", 404)
    return row


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/rounds", methods=["GET"])
@_api
def list_rounds(cursor, user_id, campaign_id):
    _require_st(cursor, user_id, campaign_id)
    cursor.execute(
        """
        SELECT r.*,
               (SELECT COUNT(*) FROM downtime_phases ph WHERE ph.round_id = r.id) AS phase_count,
               (SELECT COUNT(*) FROM downtime_phases ph
                 WHERE ph.round_id = r.id AND ph.resolved_at IS NULL) AS unresolved_count
        FROM downtime_rounds r WHERE r.campaign_id = %s ORDER BY r.id DESC
        """,
        (campaign_id,),
    )
    rounds = []
    for r in cursor.fetchall():
        d = _round_dict(r)
        d["phase_count"] = int(r.get("phase_count") or 0)
        d["unresolved_count"] = int(r.get("unresolved_count") or 0)
        rounds.append(d)
    return {"rounds": rounds}, 200


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/rounds", methods=["POST"])
@_api
def open_round(cursor, user_id, campaign_id):
    _require_st(cursor, user_id, campaign_id)
    title = _text(_body(), "title", TITLE_MAX)
    if _live_round(cursor, campaign_id):
        raise DowntimeError("round_already_live", "Release the current round before opening a new one", 409)
    try:
        cursor.execute(
            "INSERT INTO downtime_rounds (campaign_id, title, status, opened_by, opened_at) "
            "VALUES (%s, %s, 'open', %s, %s) RETURNING id",
            (campaign_id, title, user_id, _now()),
        )
    except Exception as e:
        if _is_integrity_error(e):  # the partial unique index: one live round per campaign
            raise DowntimeError("round_already_live",
                                "Release the current round before opening a new one", 409)
        raise
    rid = cursor.fetchone()["id"]
    cursor.execute("SELECT * FROM downtime_rounds WHERE id = %s", (rid,))
    return {"round": _round_dict(cursor.fetchone())}, 201


def _move_round(cursor, user_id, campaign_id, round_id, from_status, to_status, stamp=None):
    _require_st(cursor, user_id, campaign_id)
    r = _locked_round(cursor, campaign_id, round_id)
    if r["status"] != from_status:
        raise DowntimeError("round_wrong_status", f"The round is {r['status']}, not {from_status}", 409,
                            round_status=r["status"])
    if stamp:
        cursor.execute(
            f"UPDATE downtime_rounds SET status = %s, {stamp} = %s WHERE id = %s",
            (to_status, _now(), round_id),
        )
    else:
        cursor.execute("UPDATE downtime_rounds SET status = %s WHERE id = %s", (to_status, round_id))
    cursor.execute("SELECT * FROM downtime_rounds WHERE id = %s", (round_id,))
    return {"round": _round_dict(cursor.fetchone())}, 200


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/rounds/<int:round_id>/resolve", methods=["POST"])
@_api
def start_resolving(cursor, user_id, campaign_id, round_id):
    return _move_round(cursor, user_id, campaign_id, round_id, "open", "resolving", "resolving_at")


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/rounds/<int:round_id>/reopen", methods=["POST"])
@_api
def reopen_round(cursor, user_id, campaign_id, round_id):
    return _move_round(cursor, user_id, campaign_id, round_id, "resolving", "open")


# --------------------------------------------------------------------------- player view


def _player_project(p, phases):
    return {
        "id": p["id"],
        "title": p["title"],
        "goal": p.get("goal") or "",
        "status": p["status"],
        # The parent is always the same character's project (checked on create); a parent whose
        # row is gone or belongs elsewhere is not shown.
        "parent_id": p.get("parent_id") if p.get("parent_title") is not None else None,
        "parent_title": p.get("parent_title"),
        "created_at": _ts(p.get("created_at")),
        "phases": phases,
    }


def _player_phase(ph, roll=None, room=None):
    """Whitelist. Results only after the round is released; never st_note or a hidden difficulty."""
    released = ph.get("round_status") == "released"
    hidden = _flag(ph.get("difficulty_hidden"))
    out = {
        "id": ph["id"],
        "project_id": ph["project_id"],
        "round_id": ph["round_id"],
        "round_title": ph.get("round_title") or "",
        "round_status": ph.get("round_status"),
        "action": ph["action"],
        "difficulty_hidden": hidden,
        "difficulty": None,
        "created_at": _ts(ph.get("created_at")),
        "roll": roll,
        "status": "rolled" if ph.get("dice_roll_id") else "declared",
        "result_kind": None,
        "result_text": None,
        "result_location": None,
    }
    if not hidden or released:
        out["difficulty"] = ph.get("difficulty")
    if released:
        kind = ph.get("result_kind")
        if ph.get("resolved_at") is None:
            out["status"] = "unresolved"
        elif kind == "skip":
            out["status"] = "skipped"
        else:
            out["status"] = "resolved"
            out["result_kind"] = kind
            out["result_text"] = ph.get("result_text") or ""
            out["result_location"] = room
    return out


_PHASE_SELECT = """
    SELECT ph.*, r.title AS round_title, r.status AS round_status
    FROM downtime_phases ph JOIN downtime_rounds r ON r.id = ph.round_id
"""


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime", methods=["GET"])
@_api
def player_view(cursor, user_id, campaign_id):
    _campaign(cursor, campaign_id)
    is_st = is_campaign_storyteller_or_staff(cursor, user_id, campaign_id)
    ch, problem = _playing_character(cursor, user_id, campaign_id)
    live = _live_round(cursor, campaign_id)
    body = {
        "is_storyteller": is_st,
        "round": None,
        "character": None,
        "can_play": ch is not None,
        "player_problem": problem,
        "projects": [],
    }
    if live:
        body["round"] = {"id": live["id"], "title": live.get("title") or "", "status": live["status"]}
    if ch is None:
        if is_st or problem in ("character_suspended", "character_fallen", "no_playing_character"):
            return body, 200
        raise DowntimeError(problem, _PLAYER_REFUSALS[problem], 403)
    body["character"] = {"id": ch["id"], "name": ch["name"]}
    cursor.execute(
        """
        SELECT p.*, pp.title AS parent_title FROM downtime_projects p
        LEFT JOIN downtime_projects pp ON pp.id = p.parent_id AND pp.character_id = p.character_id
        WHERE p.campaign_id = %s AND p.character_id = %s ORDER BY p.id
        """,
        (campaign_id, ch["id"]),
    )
    projects = cursor.fetchall()
    ids = [p["id"] for p in projects]
    phases_by_project = {pid: [] for pid in ids}
    if ids:
        marks = ", ".join(["%s"] * len(ids))
        cursor.execute(_PHASE_SELECT + f" WHERE ph.project_id IN ({marks}) ORDER BY ph.round_id, ph.id",
                       tuple(ids))
        phase_rows = cursor.fetchall()
        rolls = _rolls_by_id(cursor, [ph.get("dice_roll_id") for ph in phase_rows])
        rooms = _player_rooms(cursor, user_id, campaign_id, phase_rows)
        for ph in phase_rows:
            phases_by_project[ph["project_id"]].append(_player_phase(
                ph, _player_roll(rolls.get(ph.get("dice_roll_id")), ph), rooms.get(ph.get("result_location_id"))
            ))
    body["projects"] = [_player_project(p, phases_by_project[p["id"]]) for p in projects]
    return body, 200


def _rolls_by_id(cursor, ids):
    ids = sorted({int(i) for i in ids if i is not None})
    if not ids:
        return {}
    marks = ", ".join(["%s"] * len(ids))
    cursor.execute(f"SELECT * FROM dice_rolls WHERE id IN ({marks})", tuple(ids))
    return {int(r["id"]): r for r in cursor.fetchall()}


def _roll_faces(row):
    mods = json_field(row.get("modifiers"), {})
    mods = mods if isinstance(mods, dict) else {}
    out = {
        "id": row["id"],
        "rules_edition": mods.get("rules_edition"),
        "dice_pool": row.get("dice_pool"),
        "results": json_field(row.get("results"), []),
        "rolled_at": _ts(row.get("rolled_at")),
    }
    if mods.get("rules_edition") == V5:
        out["normal_dice"] = mods.get("normal_dice") or []
        out["hunger_dice"] = mods.get("hunger_dice") or []
        out["hunger"] = mods.get("hunger")
    else:
        out["specialty_rerolls"] = mods.get("specialty_rerolls") or []
    return out, mods


def _player_roll(row, phase):
    """Dice faces always; difficulty and the outcome only when the difficulty isn't hidden, or once
    the round is released (a Classic success count would give a hidden difficulty away)."""
    if not row:
        return None
    out, _mods = _roll_faces(row)
    hidden = _flag(phase.get("difficulty_hidden")) and phase.get("round_status") != "released"
    out["outcome_hidden"] = hidden
    if not hidden:
        out["difficulty"] = row.get("difficulty")
        out["successes"] = row.get("successes")
        out["is_botch"] = bool(row.get("is_botch"))
        out["is_critical"] = bool(row.get("is_critical"))
    return out


def _player_rooms(cursor, user_id, campaign_id, phase_rows):
    return {}


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/projects", methods=["POST"])
@_api
def create_project(cursor, user_id, campaign_id):
    ch = _require_player(cursor, user_id, campaign_id)
    data = _body()
    title = _text(data, "title", TITLE_MAX, required=True)
    goal = _text(data, "goal", GOAL_MAX)
    parent_id = strict_int(data.get("parent_id"), "parent_id")
    if parent_id is not None:
        cursor.execute(
            "SELECT id FROM downtime_projects WHERE id = %s AND campaign_id = %s AND character_id = %s",
            (parent_id, campaign_id, ch["id"]),
        )
        if not cursor.fetchone():
            raise DowntimeError("invalid_parent", "The parent goal must be one of your own projects")
    cursor.execute(
        "SELECT COUNT(*) AS n FROM downtime_projects WHERE campaign_id = %s AND character_id = %s "
        "AND status = 'active'",
        (campaign_id, ch["id"]),
    )
    if int(cursor.fetchone()["n"] or 0) >= PROJECTS_MAX:
        raise DowntimeError("too_many_projects", f"At most {PROJECTS_MAX} active projects", 409,
                            max=PROJECTS_MAX)
    cursor.execute(
        "INSERT INTO downtime_projects (campaign_id, character_id, character_name, parent_id, title, goal, "
        "status, created_at) VALUES (%s, %s, %s, %s, %s, %s, 'active', %s) RETURNING id",
        (campaign_id, ch["id"], ch["name"] or "", parent_id, title, goal, _now()),
    )
    pid = cursor.fetchone()["id"]
    cursor.execute(
        "SELECT p.*, pp.title AS parent_title FROM downtime_projects p "
        "LEFT JOIN downtime_projects pp ON pp.id = p.parent_id AND pp.character_id = p.character_id "
        "WHERE p.id = %s",
        (pid,),
    )
    return {"project": _player_project(cursor.fetchone(), [])}, 201


def _own_project(cursor, campaign_id, project_id, character_id):
    cursor.execute(
        "SELECT * FROM downtime_projects WHERE id = %s AND campaign_id = %s AND character_id = %s",
        (project_id, campaign_id, character_id),
    )
    row = cursor.fetchone()
    if not row:
        raise DowntimeError("project_not_found", "Project not found", 404)
    return row


def _round_open_for_players(r):
    if not r:
        raise DowntimeError("no_open_round", "There is no open downtime round", 409)
    if r["status"] != "open":
        raise DowntimeError("round_locked", "The Storyteller is resolving this round", 409)


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/projects/<int:project_id>/phases",
                   methods=["POST"])
@_api
def declare_phase(cursor, user_id, campaign_id, project_id):
    ch = _require_player(cursor, user_id, campaign_id)
    action = _text(_body(), "action", ACTION_MAX, required=True)
    live = _live_round(cursor, campaign_id, lock=True)
    _round_open_for_players(live)
    project = _own_project(cursor, campaign_id, project_id, ch["id"])
    if project["status"] != "active":
        raise DowntimeError("project_closed", "This project is closed", 409)
    cursor.execute(
        "SELECT id FROM downtime_phases WHERE project_id = %s AND round_id = %s",
        (project_id, live["id"]),
    )
    if cursor.fetchone():
        raise DowntimeError("phase_exists", "This project already has a phase in this round", 409)
    now = _now()
    try:
        cursor.execute(
            "INSERT INTO downtime_phases (project_id, round_id, action, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (project_id, live["id"], action, now, now),
        )
    except Exception as e:
        if _is_integrity_error(e):
            raise DowntimeError("phase_exists", "This project already has a phase in this round", 409)
        raise
    phid = cursor.fetchone()["id"]
    cursor.execute(_PHASE_SELECT + " WHERE ph.id = %s", (phid,))
    return {"phase": _player_phase(cursor.fetchone())}, 201


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/phases/<int:phase_id>/roll", methods=["POST"])
@_api
def roll_phase(cursor, user_id, campaign_id, phase_id):
    ch = _require_player(cursor, user_id, campaign_id)
    data = _body()
    pool_expression = data.get("pool_expression")
    if pool_expression is not None and not isinstance(pool_expression, str):
        raise DowntimeError("invalid_input", "pool_expression must be text")
    pool_expression = (pool_expression or "").strip() or None
    if pool_expression:
        pool_size = parse_pool_expression(pool_expression)
    else:
        pool_size = strict_int(data.get("pool_size"), "pool_size")
        if not pool_size or pool_size < 1:
            raise DowntimeError("pool_required", "pool_size must be at least 1 (or send pool_expression)")
    if pool_size > 50:
        raise DowntimeError("pool_too_big", "pool_size must be at most 50", max=50)
    hunger = strict_int(data.get("hunger"), "hunger")
    if hunger is not None and not 0 <= hunger <= 5:
        raise DowntimeError("invalid_hunger", "hunger must be between 0 and 5")
    specialty = strict_bool(data.get("specialty"), "specialty")
    willpower = strict_bool(data.get("willpower"), "willpower")

    cursor.execute(
        "SELECT ph.round_id FROM downtime_phases ph JOIN downtime_projects p ON p.id = ph.project_id "
        "WHERE ph.id = %s AND p.campaign_id = %s AND p.character_id = %s",
        (phase_id, campaign_id, ch["id"]),
    )
    found = cursor.fetchone()
    if not found:
        raise DowntimeError("phase_not_found", "Phase not found", 404)
    rnd = _locked_round(cursor, campaign_id, found["round_id"])
    if rnd["status"] != "open":
        raise DowntimeError("round_locked", "The Storyteller is resolving this round", 409)
    cursor.execute("SELECT * FROM downtime_phases WHERE id = %s" + _for_update(), (phase_id,))
    phase = cursor.fetchone()
    if phase.get("dice_roll_id") is not None:
        raise DowntimeError("already_rolled", "This phase has already been rolled", 409)

    out = perform_manual_roll(
        cursor, user_id, campaign_id,
        pool_size=pool_size, pool_expression=pool_expression,
        difficulty_arg=phase.get("difficulty"), character_id=ch["id"], location_id=None,
        hunger_arg=hunger, specialty_arg=specialty, willpower_arg=willpower,
        action_description=(phase["action"] or "Downtime")[:200], roll_type="downtime",
    )
    cursor.execute(
        "UPDATE downtime_phases SET dice_roll_id = %s, version = version + 1, updated_at = %s "
        "WHERE id = %s AND dice_roll_id IS NULL",
        (out["roll_id"], _now(), phase_id),
    )
    if cursor.rowcount != 1:
        raise DowntimeError("already_rolled", "This phase has already been rolled", 409)
    cursor.execute(_PHASE_SELECT + " WHERE ph.id = %s", (phase_id,))
    ph = cursor.fetchone()
    rolls = _rolls_by_id(cursor, [out["roll_id"]])
    return {"phase": _player_phase(ph, _player_roll(rolls.get(int(out["roll_id"])), ph))}, 200
