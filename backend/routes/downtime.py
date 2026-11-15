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
from services.rules_edition import V5, edition_of
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


# --------------------------------------------------------------------------- Storyteller

RESULT_KINDS = ("scene", "result", "feedback", "skip")
TARGET_KINDS = ("indicator", "variable")
PROJECT_STATUSES = ("active", "done", "abandoned")
NAME_MAX = 60
TEXT_MAX = 5000
NOTE_MAX = 2000
DELTAS_MAX = 20
DELTA_LIMIT = 1000
VALUE_LIMIT = 1_000_000


def _st_roll(row):
    if not row:
        return None
    out, mods = _roll_faces(row)
    out.update({
        "difficulty": row.get("difficulty"),
        "successes": row.get("successes"),
        "is_botch": bool(row.get("is_botch")),
        "is_critical": bool(row.get("is_critical")),
        "specialty": bool(mods.get("specialty")),
        "willpower": bool(mods.get("willpower")),
        "pool_expression": mods.get("pool_expression"),
        "action_description": row.get("action_description"),
    })
    return out


def _change_dict(c):
    return {
        "id": c["id"],
        "phase_id": c.get("phase_id"),
        "target_kind": c["target_kind"],
        "target_id": c["target_id"],
        "old_value": c["old_value"],
        "new_value": c["new_value"],
        "delta": c["delta"],
        "by_user": c.get("by_user"),
        "at": _ts(c.get("at")),
    }


def _indicator_dict(i):
    return {"id": i["id"], "project_id": i["project_id"], "name": i["name"], "value": i["value"],
            "updated_at": _ts(i.get("updated_at"))}


def _variable_dict(v):
    return {"id": v["id"], "name": v["name"], "value": v["value"], "note": v.get("note") or "",
            "updated_at": _ts(v.get("updated_at"))}


def _st_project(p, indicators):
    return {
        "id": p["id"],
        "title": p["title"],
        "goal": p.get("goal") or "",
        "status": p["status"],
        "parent_id": p.get("parent_id"),
        "parent_title": p.get("parent_title"),
        "character_id": p.get("character_id"),
        # Stored at filing time, so a project outlives its character (account or sheet deleted).
        "character_name": p.get("current_character_name") or p.get("character_name") or "",
        "orphaned": p.get("character_id") is None,
        "created_at": _ts(p.get("created_at")),
        "indicators": indicators,
    }


def _st_phase(ph, roll_row, changes):
    return {
        "id": ph["id"],
        "version": ph["version"],
        "project_id": ph["project_id"],
        "round_id": ph["round_id"],
        "round_status": ph.get("round_status"),
        "action": ph["action"],
        "difficulty": ph.get("difficulty"),
        "difficulty_hidden": _flag(ph.get("difficulty_hidden")),
        "roll": _st_roll(roll_row),
        "no_roll": ph.get("dice_roll_id") is None,
        "result_kind": ph.get("result_kind"),
        "result_text": ph.get("result_text") or "",
        "result_location_id": ph.get("result_location_id"),
        "result_location_name": ph.get("result_location_name"),
        "st_note": ph.get("st_note") or "",
        "resolved": ph.get("resolved_at") is not None,
        "resolved_by": ph.get("resolved_by"),
        "resolved_at": _ts(ph.get("resolved_at")),
        "updated_at": _ts(ph.get("updated_at")),
        "changes": changes,
    }


_ST_PHASE_SELECT = """
    SELECT ph.*, r.title AS round_title, r.status AS round_status, l.name AS result_location_name
    FROM downtime_phases ph
    JOIN downtime_rounds r ON r.id = ph.round_id
    LEFT JOIN locations l ON l.id = ph.result_location_id
"""


def _st_phase_by_id(cursor, phase_id):
    cursor.execute(_ST_PHASE_SELECT + " WHERE ph.id = %s", (phase_id,))
    ph = cursor.fetchone()
    cursor.execute("SELECT * FROM downtime_changes WHERE phase_id = %s ORDER BY id", (phase_id,))
    changes = [_change_dict(c) for c in cursor.fetchall()]
    rolls = _rolls_by_id(cursor, [ph.get("dice_roll_id")])
    return _st_phase(ph, rolls.get(ph.get("dice_roll_id")), changes)


def _phase_in_campaign(cursor, campaign_id, phase_id):
    cursor.execute(
        "SELECT ph.round_id, ph.project_id FROM downtime_phases ph "
        "JOIN downtime_projects p ON p.id = ph.project_id WHERE ph.id = %s AND p.campaign_id = %s",
        (phase_id, campaign_id),
    )
    row = cursor.fetchone()
    if not row:
        raise DowntimeError("phase_not_found", "Phase not found", 404)
    return row


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/inbox", methods=["GET"])
@_api
def st_inbox(cursor, user_id, campaign_id):
    _require_st(cursor, user_id, campaign_id)
    round_id = strict_int(request.args.get("round_id"), "round_id") if request.args.get("round_id") else None
    unresolved_only = request.args.get("unresolved") in ("1", "true")
    if round_id is not None:
        cursor.execute("SELECT * FROM downtime_rounds WHERE id = %s AND campaign_id = %s",
                       (round_id, campaign_id))
        rnd = cursor.fetchone()
        if not rnd:
            raise DowntimeError("round_not_found", "Downtime round not found", 404)
    else:
        rnd = _live_round(cursor, campaign_id)
        if not rnd:
            cursor.execute("SELECT * FROM downtime_rounds WHERE campaign_id = %s ORDER BY id DESC LIMIT 1",
                           (campaign_id,))
            rnd = cursor.fetchone()

    cursor.execute(
        """
        SELECT p.*, pp.title AS parent_title, ch.name AS current_character_name
        FROM downtime_projects p
        LEFT JOIN downtime_projects pp ON pp.id = p.parent_id
        LEFT JOIN characters ch ON ch.id = p.character_id
        WHERE p.campaign_id = %s ORDER BY p.id
        """,
        (campaign_id,),
    )
    projects = cursor.fetchall()
    cursor.execute(
        "SELECT i.* FROM downtime_indicators i JOIN downtime_projects p ON p.id = i.project_id "
        "WHERE p.campaign_id = %s ORDER BY i.id",
        (campaign_id,),
    )
    indicators = {}
    for i in cursor.fetchall():
        indicators.setdefault(i["project_id"], []).append(_indicator_dict(i))

    phases = []
    if rnd:
        cursor.execute(_ST_PHASE_SELECT + " WHERE ph.round_id = %s ORDER BY ph.id", (rnd["id"],))
        rows = cursor.fetchall()
        if unresolved_only:
            rows = [r for r in rows if r.get("resolved_at") is None]
        changes = {}
        if rows:
            marks = ", ".join(["%s"] * len(rows))
            cursor.execute(f"SELECT * FROM downtime_changes WHERE phase_id IN ({marks}) ORDER BY id",
                           tuple(r["id"] for r in rows))
            for c in cursor.fetchall():
                changes.setdefault(c["phase_id"], []).append(_change_dict(c))
        rolls = _rolls_by_id(cursor, [r.get("dice_roll_id") for r in rows])
        phases = [_st_phase(r, rolls.get(r.get("dice_roll_id")), changes.get(r["id"], [])) for r in rows]

    cursor.execute("SELECT * FROM chronicle_variables WHERE campaign_id = %s ORDER BY name", (campaign_id,))
    variables = [_variable_dict(v) for v in cursor.fetchall()]
    cursor.execute(
        "SELECT id, name FROM locations WHERE campaign_id = %s AND is_active = TRUE ORDER BY name",
        (campaign_id,),
    )
    locations = [{"id": r["id"], "name": r["name"]} for r in cursor.fetchall()]
    return {
        "round": _round_dict(rnd) if rnd else None,
        "phases": phases,
        "projects": [_st_project(p, indicators.get(p["id"], [])) for p in projects],
        "variables": variables,
        "locations": locations,
    }, 200


def _difficulty_ok(edition, value):
    return 0 <= value <= 10 if edition == V5 else 2 <= value <= 10


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/phases/<int:phase_id>/setup", methods=["PUT"])
@_api
def setup_phase(cursor, user_id, campaign_id, phase_id):
    camp = _require_st(cursor, user_id, campaign_id)
    data = _body()
    difficulty = strict_int(data.get("difficulty"), "difficulty")
    hidden = strict_bool(data.get("difficulty_hidden"), "difficulty_hidden")
    if difficulty is not None and not _difficulty_ok(edition_of(camp), difficulty):
        raise DowntimeError("invalid_difficulty", "That difficulty is out of range for this chronicle")
    if hidden and difficulty is None:
        raise DowntimeError("difficulty_required", "Set a difficulty to hide it")
    found = _phase_in_campaign(cursor, campaign_id, phase_id)
    rnd = _locked_round(cursor, campaign_id, found["round_id"])
    if rnd["status"] == "released":
        raise DowntimeError("round_released", "This round has been released", 409)
    cursor.execute("SELECT dice_roll_id FROM downtime_phases WHERE id = %s" + _for_update(), (phase_id,))
    if cursor.fetchone().get("dice_roll_id") is not None:
        raise DowntimeError("already_rolled", "The phase has been rolled; its difficulty is fixed", 409)
    cursor.execute(
        "UPDATE downtime_phases SET difficulty = %s, difficulty_hidden = %s, version = version + 1, "
        "updated_at = %s WHERE id = %s",
        (difficulty, bool(hidden), _now(), phase_id),
    )
    return {"phase": _st_phase_by_id(cursor, phase_id)}, 200


def _parse_deltas(raw):
    if not isinstance(raw, list):
        raise DowntimeError("invalid_deltas", "deltas must be a list")
    if len(raw) > DELTAS_MAX:
        raise DowntimeError("too_many_deltas", f"At most {DELTAS_MAX} changes per phase", max=DELTAS_MAX)
    net = {}
    for item in raw:
        if not isinstance(item, dict) or item.get("target_kind") not in TARGET_KINDS:
            raise DowntimeError("invalid_deltas", "Each change needs target_kind indicator or variable")
        tid = strict_int(item.get("target_id"), "target_id")
        delta = strict_int(item.get("delta"), "delta")
        if tid is None or delta is None or not -DELTA_LIMIT <= delta <= DELTA_LIMIT:
            raise DowntimeError("invalid_deltas", f"Each change needs target_id and a delta within "
                                                  f"+/-{DELTA_LIMIT}", max=DELTA_LIMIT)
        key = (item["target_kind"], tid)
        net[key] = net.get(key, 0) + delta
    return {k: v for k, v in net.items() if v}


def _apply_value_change(cursor, campaign_id, phase_id, kind, row, delta, user_id, now):
    table = "downtime_indicators" if kind == "indicator" else "chronicle_variables"
    new_value = int(row["value"]) + delta
    if abs(new_value) > VALUE_LIMIT:
        raise DowntimeError("value_out_of_range", "That change takes a value out of range")
    cursor.execute(f"UPDATE {table} SET value = %s, updated_at = %s WHERE id = %s", (new_value, now, row["id"]))
    cursor.execute(
        "INSERT INTO downtime_changes (campaign_id, phase_id, target_kind, target_id, old_value, new_value, "
        "delta, by_user, at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (campaign_id, phase_id, kind, row["id"], row["value"], new_value, delta, user_id, now),
    )


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/phases/<int:phase_id>/resolve", methods=["POST"])
@_api
def resolve_phase(cursor, user_id, campaign_id, phase_id):
    _require_st(cursor, user_id, campaign_id)
    data = _body()
    version = strict_int(data.get("version"), "version")
    if version is None:
        raise DowntimeError("version_required", "Send the phase version you edited")
    kind = data.get("result_kind")
    if kind not in RESULT_KINDS:
        raise DowntimeError("invalid_result_kind", "result_kind must be scene, result, feedback or skip")
    text = _text(data, "result_text", TEXT_MAX)
    note = _text(data, "st_note", NOTE_MAX)
    location_id = strict_int(data.get("result_location_id"), "result_location_id")
    if kind != "scene":
        location_id = None
    has_deltas = "deltas" in data and data.get("deltas") is not None
    wanted = _parse_deltas(data.get("deltas")) if has_deltas else None

    found = _phase_in_campaign(cursor, campaign_id, phase_id)
    rnd = _locked_round(cursor, campaign_id, found["round_id"])
    if rnd["status"] == "open":
        raise DowntimeError("round_not_resolving", "Move the round to resolving first", 409)
    cursor.execute("SELECT * FROM downtime_phases WHERE id = %s" + _for_update(), (phase_id,))
    phase = cursor.fetchone()
    if int(phase["version"]) != version:
        raise DowntimeError("version_conflict", "This phase changed since you opened it; reload it", 409,
                            current_version=phase["version"])
    if location_id is not None:
        cursor.execute("SELECT id FROM locations WHERE id = %s AND campaign_id = %s AND is_active = TRUE",
                       (location_id, campaign_id))
        if not cursor.fetchone():
            raise DowntimeError("invalid_location", "That room is not in this chronicle")

    now = _now()
    if has_deltas:
        cursor.execute(
            "SELECT target_kind, target_id, SUM(delta) AS net FROM downtime_changes WHERE phase_id = %s "
            "GROUP BY target_kind, target_id",
            (phase_id,),
        )
        applied = {(r["target_kind"], int(r["target_id"])): int(r["net"] or 0) for r in cursor.fetchall()}
        diff = {}
        for key in set(applied) | set(wanted):
            d = wanted.get(key, 0) - applied.get(key, 0)
            if d:
                diff[key] = d
        if diff and rnd["status"] == "released":
            raise DowntimeError("deltas_locked", "Changes can't be altered after the round is released", 409)
        # New targets must belong here; a target the phase already changed may be reversed even if
        # it was renamed since (it is still the same row, checked below).
        for (tkind, tid) in sorted(diff, key=lambda k: (TARGET_KINDS.index(k[0]), k[1])):
            if tkind == "indicator":
                cursor.execute(
                    "SELECT * FROM downtime_indicators WHERE id = %s AND project_id = %s" + _for_update(),
                    (tid, phase["project_id"]),
                )
            else:
                cursor.execute(
                    "SELECT * FROM chronicle_variables WHERE id = %s AND campaign_id = %s" + _for_update(),
                    (tid, campaign_id),
                )
            row = cursor.fetchone()
            if not row and (tkind, tid) in applied and not wanted.get((tkind, tid)):
                continue  # the indicator/variable was deleted since: nothing left to reverse
            if not row:
                raise DowntimeError("invalid_target", "A change points at an indicator or variable that "
                                                      "isn't part of this project or chronicle", 400,
                                    target_kind=tkind, target_id=tid)
            _apply_value_change(cursor, campaign_id, phase_id, tkind, row, diff[(tkind, tid)], user_id, now)

    cursor.execute(
        "UPDATE downtime_phases SET result_kind = %s, result_text = %s, result_location_id = %s, st_note = %s, "
        "resolved_by = %s, resolved_at = %s, version = version + 1, updated_at = %s "
        "WHERE id = %s AND version = %s",
        (kind, text, location_id, note, user_id, now, now, phase_id, version),
    )
    if cursor.rowcount != 1:
        raise DowntimeError("version_conflict", "This phase changed since you opened it; reload it", 409)
    return {"phase": _st_phase_by_id(cursor, phase_id)}, 200


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/rounds/<int:round_id>/release", methods=["POST"])
@_api
def release_round(cursor, user_id, campaign_id, round_id):
    _require_st(cursor, user_id, campaign_id)
    force = strict_bool(_body().get("force"), "force")
    r = _locked_round(cursor, campaign_id, round_id)
    if r["status"] != "resolving":
        raise DowntimeError("round_wrong_status", f"The round is {r['status']}, not resolving", 409,
                            round_status=r["status"])
    cursor.execute(
        "SELECT COUNT(*) AS n FROM downtime_phases WHERE round_id = %s AND resolved_at IS NULL", (round_id,)
    )
    unresolved = int(cursor.fetchone()["n"] or 0)
    if unresolved and not force:
        raise DowntimeError("unresolved_phases", "Some phases have no result yet", 409, count=unresolved)
    cursor.execute("UPDATE downtime_rounds SET status = 'released', released_at = %s WHERE id = %s",
                   (_now(), round_id))
    cursor.execute("SELECT * FROM downtime_rounds WHERE id = %s", (round_id,))
    return {"round": _round_dict(cursor.fetchone())}, 200


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/projects/<int:project_id>", methods=["PATCH"])
@_api
def set_project_status(cursor, user_id, campaign_id, project_id):
    _require_st(cursor, user_id, campaign_id)
    status = _body().get("status")
    if status not in PROJECT_STATUSES:
        raise DowntimeError("invalid_status", "status must be active, done or abandoned")
    cursor.execute("UPDATE downtime_projects SET status = %s WHERE id = %s AND campaign_id = %s",
                   (status, project_id, campaign_id))
    if cursor.rowcount != 1:
        raise DowntimeError("project_not_found", "Project not found", 404)
    return {"id": project_id, "status": status}, 200


def _name(data):
    return _text(data, "name", NAME_MAX, required=True)


def _value(data, default=None):
    v = strict_int(data.get("value"), "value", default)
    if v is not None and abs(v) > VALUE_LIMIT:
        raise DowntimeError("value_out_of_range", "That value is out of range")
    return v


def _insert_unique(cursor, sql, params):
    try:
        cursor.execute(sql, params)
    except Exception as e:
        if _is_integrity_error(e):
            raise DowntimeError("name_taken", "That name is already used", 409)
        raise
    return cursor.fetchone()["id"]


def _manual_change(cursor, campaign_id, kind, row, new_value, user_id, now):
    if new_value is None or int(new_value) == int(row["value"]):
        return
    cursor.execute(
        "INSERT INTO downtime_changes (campaign_id, phase_id, target_kind, target_id, old_value, new_value, "
        "delta, by_user, at) VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s)",
        (campaign_id, kind, row["id"], row["value"], new_value, int(new_value) - int(row["value"]), user_id, now),
    )


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/projects/<int:project_id>/indicators",
                   methods=["POST"])
@_api
def create_indicator(cursor, user_id, campaign_id, project_id):
    _require_st(cursor, user_id, campaign_id)
    data = _body()
    name, value = _name(data), _value(data, 0)
    cursor.execute("SELECT id FROM downtime_projects WHERE id = %s AND campaign_id = %s", (project_id, campaign_id))
    if not cursor.fetchone():
        raise DowntimeError("project_not_found", "Project not found", 404)
    cursor.execute("SELECT id FROM downtime_indicators WHERE project_id = %s AND name = %s", (project_id, name))
    if cursor.fetchone():
        raise DowntimeError("name_taken", "That name is already used", 409)
    iid = _insert_unique(
        cursor,
        "INSERT INTO downtime_indicators (project_id, name, value, updated_at) VALUES (%s, %s, %s, %s) RETURNING id",
        (project_id, name, value, _now()),
    )
    cursor.execute("SELECT * FROM downtime_indicators WHERE id = %s", (iid,))
    return {"indicator": _indicator_dict(cursor.fetchone())}, 201


def _locked_indicator(cursor, campaign_id, indicator_id):
    cursor.execute(
        "SELECT i.id FROM downtime_indicators i JOIN downtime_projects p ON p.id = i.project_id "
        "WHERE i.id = %s AND p.campaign_id = %s",
        (indicator_id, campaign_id),
    )
    if not cursor.fetchone():
        raise DowntimeError("indicator_not_found", "Indicator not found", 404)
    cursor.execute("SELECT * FROM downtime_indicators WHERE id = %s" + _for_update(), (indicator_id,))
    return cursor.fetchone()


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/indicators/<int:indicator_id>",
                   methods=["PATCH", "DELETE"])
@_api
def edit_indicator(cursor, user_id, campaign_id, indicator_id):
    _require_st(cursor, user_id, campaign_id)
    row = _locked_indicator(cursor, campaign_id, indicator_id)
    if request.method == "DELETE":
        cursor.execute("DELETE FROM downtime_indicators WHERE id = %s", (indicator_id,))
        return {"deleted": indicator_id}, 200
    data = _body()
    name = _name(data) if "name" in data else row["name"]
    value = _value(data) if "value" in data else None
    now = _now()
    _manual_change(cursor, campaign_id, "indicator", row, value, user_id, now)
    try:
        cursor.execute("UPDATE downtime_indicators SET name = %s, value = %s, updated_at = %s WHERE id = %s",
                       (name, row["value"] if value is None else value, now, indicator_id))
    except Exception as e:
        if _is_integrity_error(e):
            raise DowntimeError("name_taken", "That name is already used", 409)
        raise
    cursor.execute("SELECT * FROM downtime_indicators WHERE id = %s", (indicator_id,))
    return {"indicator": _indicator_dict(cursor.fetchone())}, 200


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/variables", methods=["GET", "POST"])
@_api
def variables(cursor, user_id, campaign_id):
    _require_st(cursor, user_id, campaign_id)
    if request.method == "GET":
        cursor.execute("SELECT * FROM chronicle_variables WHERE campaign_id = %s ORDER BY name", (campaign_id,))
        return {"variables": [_variable_dict(v) for v in cursor.fetchall()]}, 200
    data = _body()
    name, value, note = _name(data), _value(data, 0), _text(data, "note", NOTE_MAX)
    cursor.execute("SELECT id FROM chronicle_variables WHERE campaign_id = %s AND name = %s", (campaign_id, name))
    if cursor.fetchone():
        raise DowntimeError("name_taken", "That name is already used", 409)
    vid = _insert_unique(
        cursor,
        "INSERT INTO chronicle_variables (campaign_id, name, value, note, updated_at) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (campaign_id, name, value, note, _now()),
    )
    cursor.execute("SELECT * FROM chronicle_variables WHERE id = %s", (vid,))
    return {"variable": _variable_dict(cursor.fetchone())}, 201


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/variables/<int:variable_id>",
                   methods=["PATCH", "DELETE"])
@_api
def edit_variable(cursor, user_id, campaign_id, variable_id):
    _require_st(cursor, user_id, campaign_id)
    cursor.execute("SELECT * FROM chronicle_variables WHERE id = %s AND campaign_id = %s" + _for_update(),
                   (variable_id, campaign_id))
    row = cursor.fetchone()
    if not row:
        raise DowntimeError("variable_not_found", "Variable not found", 404)
    if request.method == "DELETE":
        cursor.execute("DELETE FROM chronicle_variables WHERE id = %s", (variable_id,))
        return {"deleted": variable_id}, 200
    data = _body()
    name = _name(data) if "name" in data else row["name"]
    note = _text(data, "note", NOTE_MAX) if "note" in data else (row.get("note") or "")
    value = _value(data) if "value" in data else None
    now = _now()
    _manual_change(cursor, campaign_id, "variable", row, value, user_id, now)
    try:
        cursor.execute(
            "UPDATE chronicle_variables SET name = %s, value = %s, note = %s, updated_at = %s WHERE id = %s",
            (name, row["value"] if value is None else value, note, now, variable_id),
        )
    except Exception as e:
        if _is_integrity_error(e):
            raise DowntimeError("name_taken", "That name is already used", 409)
        raise
    cursor.execute("SELECT * FROM chronicle_variables WHERE id = %s", (variable_id,))
    return {"variable": _variable_dict(cursor.fetchone())}, 200


@downtime_bp.route("/campaigns/<int:campaign_id>/downtime/changes", methods=["GET"])
@_api
def list_changes(cursor, user_id, campaign_id):
    _require_st(cursor, user_id, campaign_id)
    kind = request.args.get("target_kind")
    sql = "SELECT * FROM downtime_changes WHERE campaign_id = %s"
    params = [campaign_id]
    if kind:
        if kind not in TARGET_KINDS:
            raise DowntimeError("invalid_target", "target_kind must be indicator or variable")
        sql += " AND target_kind = %s"
        params.append(kind)
        if request.args.get("target_id"):
            sql += " AND target_id = %s"
            params.append(strict_int(request.args.get("target_id"), "target_id"))
    cursor.execute(sql + " ORDER BY id DESC LIMIT 200", tuple(params))
    return {"changes": [_change_dict(c) for c in cursor.fetchall()]}, 200
