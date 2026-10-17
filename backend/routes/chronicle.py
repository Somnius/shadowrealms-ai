"""
"The chronicle so far" (docs/CHRONICLE.md): /api/campaigns/<id>/chronicle...

Who:
- someone who can't open the chronicle: 404 (as messages do)
- a player: 403 on these routes; every member (players too) gets "Previously on…" from
  …/chronicle/recap and …/chronicle/recap/visit, built from the stored player view only
- a helper who can open the chronicle (a member): reads and exports only
- the Storyteller (creator) and site admins: also Update, Rewrite everything, Translate and the edit copy
Archives of deleted chronicles: /api/chronicle-archives (site admins; the deleting Storyteller for 30 days).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date, datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, Response, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from database import get_db
from services import chronicle_digest as cd
from services import chronicle_jobs as cj
from services import chronicle_settings as cs
from services.request_validation import RequestValidationError

logger = logging.getLogger(__name__)

chronicle_bp = Blueprint("chronicle", __name__)


def _uid():
    try:
        return int(get_jwt_identity())
    except (TypeError, ValueError):
        return None


def access(cursor, user_id, campaign_id) -> str:
    """'none' | 'player' | 'helper' | 'st' (the creator or a site admin)."""
    from services.location_access import user_is_campaign_viewer

    cursor.execute("SELECT created_by FROM campaigns WHERE id = %s", (campaign_id,))
    camp = cursor.fetchone()
    if not camp or not user_is_campaign_viewer(cursor, user_id, campaign_id):
        return "none"
    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    role = ((cursor.fetchone() or {}).get("role") or "").strip().lower()
    if role == "admin" or str(camp.get("created_by")) == str(user_id):
        return "st"
    if role == "helper":
        return "helper"
    return "player"


def _gate(cursor, user_id, campaign_id):
    a = access(cursor, user_id, campaign_id)
    if a == "none":
        return a, (jsonify({"error": "not_found"}), 404)
    if a == "player":
        return a, (jsonify({"error": "forbidden"}), 403)
    return a, None


def _view(arg):
    return "player" if (arg or "").strip().lower() == "player" else "st"


def _readable_for_players(cursor, campaign_id):
    from services.location_access import readable_location_ids

    cursor.execute("SELECT id, is_active, is_open FROM locations WHERE campaign_id = %s", (campaign_id,))
    return readable_location_ids(cursor.fetchall(), False)


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


def chapter_out(ch, seq, view):
    if view == "st":
        c = {k: v for k, v in (ch.get("chapter") or {}).items() if k != "ooc"}
        out = {"key": ch["key"], "room": ch["room"], "location_id": ch["location_id"],
               "visibility": ch.get("visibility"), "first_id": ch.get("first_id"), "last_id": ch.get("last_id"),
               "chapter": c, "table_talk": len(ch.get("ooc") or [])}
    else:
        out = cd.player_chapter(ch)
    out["night"] = seq
    out["started_at"] = _iso(ch.get("started_at"))
    out["ended_at"] = _iso(ch.get("ended_at"))
    return out


def _want_lang(own):
    """lang= on reads and exports: the chronicle's own language unless the other one is asked for."""
    lang = (request.args.get("lang") or "").strip().lower()
    return lang if lang in cd.LANGS else own


def _state(cursor, camp, view, lang=None):
    """(lang, chapters, digest, withheld, written_at, extra). With lang = the other language, the
    cached translation is laid over the stored chapters (extra['translation'] says what it is)."""
    own = cj.chronicle_lang(cursor, camp)
    lang = lang or own
    readable = _readable_for_players(cursor, camp["id"]) if view == "player" else None
    stored = cj.stored_chapters(cursor, camp["id"], own)
    raw = cj.stored_digest(cursor, camp["id"], own)
    extra = {"own_lang": own, "translation": None, "edit": cj.edit_state(raw)}
    if lang != own:
        tr = cj.stored_digest(cursor, camp["id"], lang, translated=True)
        if tr:
            extra["translation"] = {"from": tr.get("_translated_from"), "written_at": _iso(tr.get("_written_at")),
                                    "stale": tr.get("_hash") != cd.translation_hash(raw, stored),
                                    "untranslated": tr.get("untranslated") or 0}
            stored = cd.overlay_translation(stored, tr)
            raw = {k: v for k, v in tr.items() if k != "chapters"}
        else:
            stored, raw = [], None
    chapters = cd.visible_chapters(stored, view, readable)
    digest = raw
    withheld = False
    if digest and view == "player":
        # rooms are checked again now: a room closed since the digest was written keeps it back
        if any(int(r) not in readable for r in digest.get("rooms") or []):
            digest, withheld = None, True
        else:
            digest = cd.player_digest(digest)
    written_at = digest.get("_written_at") if digest else None
    if digest:
        digest = {k: v for k, v in digest.items() if not k.startswith("_") and k not in ("rooms", "untranslated")}
    return lang, chapters, digest, withheld, written_at, extra


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle", methods=["GET"])
@jwt_required()
def get_chronicle(campaign_id):
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        a, err = _gate(cur, uid, campaign_id)
        if err:
            return err
        view = _view(request.args.get("view"))
        camp = cj.campaign_row(cur, campaign_id)
        own = cj.chronicle_lang(cur, camp)
        lang, chapters, digest, withheld, written_at, extra = _state(cur, camp, view, _want_lang(own))
        cur.execute("SELECT MAX(id) AS last FROM messages WHERE campaign_id = %s", (campaign_id,))
        last_msg = (cur.fetchone() or {}).get("last") or 0
        last_written = max([c.get("last_id") or 0 for c in chapters] or [0])
        total = (digest or {}).get("nights_total")
        return jsonify({
            "lang": lang,
            "own_lang": extra["own_lang"],
            "translation": extra["translation"],
            "edit": extra["edit"],
            "view": view,
            "access": a,
            "can_edit": a == "st",
            "can_update": a == "st",
            "quiet_minutes": round(cj.quiet_seconds() / 60),
            "digest": digest,
            "withheld": withheld,
            "written_at": _iso(written_at),
            "nights_written": len(chapters),
            "nights_total": total if total is not None else len(chapters),
            "new_since": bool(last_msg and last_msg > last_written),
            "chapters": [chapter_out(c, i, view) for i, c in cd.number_nights(chapters)],
            "job": cj.job_json(cj.latest_job(cur, campaign_id)),
            "settings": cs.load(cur, campaign_id),
            "can_settings": a == "st",
        })
    finally:
        conn.close()


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle/chapters", methods=["GET"])
@jwt_required()
def get_chapters(campaign_id):
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        _a, err = _gate(cur, uid, campaign_id)
        if err:
            return err
        view = _view(request.args.get("view"))
        camp = cj.campaign_row(cur, campaign_id)
        _lang, chapters, _d, _w, _at, _x = _state(cur, camp, view, _want_lang(cj.chronicle_lang(cur, camp)))
        out = [chapter_out(c, i, view) for i, c in cd.number_nights(chapters)]
        key = request.args.get("key")
        if key:
            one = [c for c in out if c["key"] == key]
            if not one:
                return jsonify({"error": "not_found"}), 404
            return jsonify({"chapter": one[0]})
        return jsonify({"chapters": out})
    finally:
        conn.close()


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle/estimate", methods=["GET"])
@jwt_required()
def get_estimate(campaign_id):
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        _a, err = _gate(cur, uid, campaign_id)
        if err:
            return err
        if request.args.get("scope") == "translate":
            return jsonify(cj.translation_estimate(cur, campaign_id))
        scope = "all" if request.args.get("scope") == "all" else "update"
        return jsonify(cj.estimate(cur, campaign_id, scope))
    finally:
        conn.close()


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle/jobs", methods=["POST"])
@jwt_required()
def post_job(campaign_id):
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        a, err = _gate(cur, uid, campaign_id)
        if err:
            return err
        body = request.get_json(silent=True) or {}
        scope = body.get("scope") if isinstance(body, dict) else None
        scope = scope if scope in ("update", "all", "translate") else "update"
        lang = body.get("lang") if isinstance(body, dict) else None
        if a != "st":  # helpers read and export only
            return jsonify({"error": "forbidden"}), 403
        if not cj._pg():  # no writer thread without PostgreSQL: the job would never run
            return jsonify({"error": "no_worker"}), 503
        try:
            if scope == "translate":
                camp = cj.campaign_row(cur, campaign_id)
                if lang not in cd.LANGS or lang == cj.chronicle_lang(cur, camp):
                    return jsonify({"error": "bad_lang"}), 400
                if not cj.stored_digest(cur, campaign_id, cj.chronicle_lang(cur, camp)):
                    return jsonify({"error": "no_digest"}), 409
                if cj.edited_in(cur, campaign_id, lang):  # an edit from when the chronicle was in that language
                    return jsonify({"error": "edited_in_target"}), 409
            job_id = cj.create_job(cur, campaign_id, uid, scope, lang=lang if scope == "translate" else None)
        except cj.JobRefused as e:
            conn.rollback()
            out = {"error": e.code}
            if e.retry_after:
                out["retry_after"] = e.retry_after
            return jsonify(out), e.status
        conn.commit()
        cj.ensure_worker()
        return jsonify({"job": cj.job_json(cj.get_job(cur, campaign_id, job_id))}), 202
    finally:
        conn.close()


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle/jobs/<int:job_id>", methods=["GET", "DELETE"])
@jwt_required()
def job(campaign_id, job_id):
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        a, err = _gate(cur, uid, campaign_id)
        if err:
            return err
        if request.method == "DELETE":
            if a != "st":  # helpers read and export only
                return jsonify({"error": "forbidden"}), 403
            if not cj.cancel_job(cur, campaign_id, job_id):
                conn.rollback()
                row = cj.get_job(cur, campaign_id, job_id)
                if not row:
                    return jsonify({"error": "not_found"}), 404
                return jsonify({"job": cj.job_json(row)}), 409
            conn.commit()
        row = cj.get_job(cur, campaign_id, job_id)
        if not row:
            return jsonify({"error": "not_found"}), 404
        return jsonify({"job": cj.job_json(row)})
    finally:
        conn.close()


def _file_name(name, suffix, ext="md"):
    base = "".join(c if c.isprintable() and c not in '\\/:*?"<>|' else " " for c in str(name or ""))
    base = " ".join(base.split())[:80] or "chronicle"
    return f"{base} — {suffix}.{ext}"


def _disposition(filename):
    ascii_name = filename.encode("ascii", "replace").decode().replace("?", "_").replace('"', "")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _markdown_response(text, filename):
    return Response(text, mimetype="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": _disposition(filename), "Cache-Control": "no-store"})


def _pdf_response(data, filename):
    return Response(data, mimetype="application/pdf",
                    headers={"Content-Disposition": _disposition(filename), "Cache-Control": "no-store"})


def _flag(name):
    return (request.args.get(name) or "").strip().lower() in ("1", "true", "yes")


def _table_talk(cur, campaign_id):
    """with_table_talk= when the export says; else the chronicle's default (Chronicle settings)."""
    if request.args.get("with_table_talk") is not None:
        return _flag("with_table_talk")
    return cs.load(cur, campaign_id)["table_talk"]


def _paper():
    return "letter" if (request.args.get("paper") or "").strip().lower() == "letter" else "a4"


def _look():
    return "horror" if (request.args.get("look") or "").strip().lower() == "horror" else "sheet"


def _color():
    v = (request.args.get("color") or "").strip().lower()
    return v if v in ("colour", "print") else None  # None: the look's default


def _story(cur, camp, view, lang=None, table_talk=None):
    """(markdown, lang, edited, translated) of the story so far. The Storyteller's view uses the edit
    copy when there is one (in the chronicle's own language); the player view never does. lang and
    table_talk default to the request's lang= and with_table_talk=."""
    own = cj.chronicle_lang(cur, camp)
    lang = lang or _want_lang(own)
    table_talk = _table_talk(cur, camp["id"]) if table_talk is None else table_talk
    if view == "st" and lang == own:
        raw = cj.stored_digest(cur, camp["id"], own)
        if raw and raw.get("_edited_markdown"):
            return cd.edited_markdown(raw["_edited_markdown"], lang), lang, True, False
    lang, chapters, digest, _w, written_at, extra = _state(cur, camp, view, lang)
    readable = _readable_for_players(cur, camp["id"]) if view == "player" else None
    facts = cj.facts(cur, camp, view, readable, chapters)
    facts["written_at"] = written_at
    facts["nights_total"] = max((digest or {}).get("nights_total") or 0, len(chapters))
    if chapters:
        facts["first_at"], facts["last_at"] = chapters[0]["started_at"], chapters[-1]["started_at"]
    if table_talk:
        lobby = [c for c in cj.stored_chapters(cur, camp["id"], own) if c["kind"] == "lobby"]
        chapters = chapters + lobby
    existing = cj.message_ids(cur, camp["id"]) if view == "st" else None
    translated = lang != own
    text = cd.story_markdown(facts, digest, chapters, lang, view, table_talk, existing, translated)
    return text, lang, False, translated


def _minutes(cur, camp, view, last_n, date_range=None):
    """Always the generated record (never the edit copy), in the chronicle's language or its translation.
    With a date range, the nights in it that have no record yet are counted for the top of the file."""
    own = cj.chronicle_lang(cur, camp)
    lang, chapters, digest, _w, _at, _x = _state(cur, camp, view, _want_lang(own))
    readable = _readable_for_players(cur, camp["id"]) if view == "player" else None
    facts = cj.facts(cur, camp, view, readable, chapters)
    facts["nights_total"] = max((digest or {}).get("nights_total") or 0, len(chapters))
    existing = cj.message_ids(cur, camp["id"]) if view == "st" else None
    translated = lang != own
    if date_range:
        date_range = dict(date_range, **_range_state(cur, camp, view, readable, date_range, own, lang))
    text = cd.minutes_markdown(facts, chapters, lang, view, last_n, existing, _table_talk(cur, camp["id"]), translated,
                               date_range=date_range)
    return text, lang, translated


def _range_state(cur, camp, view, readable, rng, own, lang):
    """For a date range: the fresh chapter keys in it (stored nights cut differently since are left
    out), how many nights in it are new or changed since the last Update (only the chapters in the
    range are hashed), and, in the other language, how many written nights the translation lacks."""
    def inside(ch):
        return cd.in_range(ch.get("started_at"), rng["tz"], rng["start"], rng["end"])

    def shown(ch):
        return view != "player" or (ch.get("visibility") == "all" and int(ch["location_id"]) in readable)

    p = cj.plan(cur, camp["id"], only=inside)
    fresh = {ch["key"] for ch in p["chapters"] if inside(ch)}
    unwritten = sum(1 for ch in p["stale"] if shown(ch))
    untranslated = 0
    if lang != own:
        tr = cj.stored_digest(cur, camp["id"], lang, translated=True) or {}
        done = set((tr.get("chapters") or {}).keys())
        untranslated = sum(1 for ch in p["stored"].values()
                           if ch["kind"] == "story" and ch["key"] in fresh and ch["key"] not in done and shown(ch))
    return {"fresh_keys": fresh, "unwritten": unwritten, "untranslated": untranslated}


_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _user_tz(cur, uid):
    try:
        cur.execute("SELECT display_timezone FROM users WHERE id = %s", (uid,))
        row = cur.fetchone()
        return (row or {}).get("display_timezone") if isinstance(row, dict) else (row[0] if row else None)
    except Exception:
        try:
            cur.connection.rollback()
        except Exception:
            pass
        return None


def _date_range(cur, uid):
    """(range or None, error code or None) from from=, to= (YYYY-MM-DD) and tz= (an IANA name; default
    the user's display timezone, then UTC). The dates are calendar days in that timezone, both included.
    One date alone is open-ended: from= alone runs to today, to= alone from the beginning."""
    a, b = (request.args.get("from") or "").strip(), (request.args.get("to") or "").strip()
    if not a and not b:
        return None, None
    if (a and not _DAY.match(a)) or (b and not _DAY.match(b)):
        return None, "bad_range"
    name = (request.args.get("tz") or "").strip() or _user_tz(cur, uid) or "UTC"
    try:
        tz = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        if request.args.get("tz"):
            return None, "bad_tz"
        tz = ZoneInfo("UTC")
    try:
        start = date.fromisoformat(a) if a else date(1970, 1, 1)
        end = date.fromisoformat(b) if b else datetime.now(tz).date()
    except ValueError:
        return None, "bad_range"
    if start > end:
        return None, "bad_range"
    return {"start": start, "end": end, "tz": tz}, None


def _last_n():
    last = request.args.get("last")
    try:
        last_n = int(last) if last else None
    except ValueError:
        return None, True
    if last_n is not None and not 1 <= last_n <= 1000:
        return None, True
    return last_n, False


def _export(campaign_id, what, fmt):
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        _a, err = _gate(cur, uid, campaign_id)
        if err:
            return err
        view = _view(request.args.get("view"))
        camp = cj.campaign_row(cur, campaign_id)
        if what == "story":
            text, lang, edited, translated = _story(cur, camp, view)
            suffix = "ως τώρα" if lang == "el" else "so far"
        else:
            last_n, bad = _last_n()
            if bad:
                return jsonify({"error": "bad_last"}), 400
            rng, rerr = _date_range(cur, uid)
            if rerr:
                return jsonify({"error": rerr}), 400
            if rng:
                last_n = None  # a date range wins over last=
            text, lang, translated = _minutes(cur, camp, view, last_n, rng)
            edited = False
            suffix = "πρακτικά" if lang == "el" else "minutes"
        if fmt == "md":
            return _markdown_response(text, _file_name(camp["name"], suffix))
        from services.chronicle_pdf import build_pdf

        title = f"{camp['name']} — {cd.words(lang)['so_far_title' if what == 'story' else 'minutes_title']}"
        data = build_pdf(text, lang, _paper(), edited=edited, translated=translated, title=title,
                         look=_look(), color=_color())
        return _pdf_response(data, _file_name(camp["name"], suffix, "pdf"))
    finally:
        conn.close()


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle.md", methods=["GET"])
@jwt_required()
def export_story(campaign_id):
    return _export(campaign_id, "story", "md")


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle.pdf", methods=["GET"])
@jwt_required()
def export_story_pdf(campaign_id):
    return _export(campaign_id, "story", "pdf")


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle/minutes.md", methods=["GET"])
@jwt_required()
def export_minutes(campaign_id):
    return _export(campaign_id, "minutes", "md")


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle/minutes.pdf", methods=["GET"])
@jwt_required()
def export_minutes_pdf(campaign_id):
    return _export(campaign_id, "minutes", "pdf")


# ---------------------------------------------------------------------------------------------
# The Storyteller's edit copy: the chronicle's Storyteller and site admins save it; helpers don't

@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle/edit", methods=["GET", "PUT", "DELETE"])
@jwt_required()
def edit_copy(campaign_id):
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        a, err = _gate(cur, uid, campaign_id)
        if err:
            return err
        if a != "st":
            return jsonify({"error": "forbidden"}), 403
        camp = cj.campaign_row(cur, campaign_id)
        lang = cj.chronicle_lang(cur, camp)
        if request.method == "PUT":
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return jsonify({"error": "bad_body"}), 400
            keep = body.get("keep") is True
            text = body.get("markdown")
            if not keep:
                if not isinstance(text, str) or not text.strip():
                    return jsonify({"error": "bad_markdown"}), 400
                if len(text) > cj.EDIT_MAX_CHARS:
                    return jsonify({"error": "too_long", "max": cj.EDIT_MAX_CHARS}), 413
                text = cd.strip_footer(text.replace("\r\n", "\n"))
            if not cj.save_edit(cur, campaign_id, lang, None if keep else text, uid, keep=keep):
                conn.rollback()
                return jsonify({"error": "no_digest"}), 409
            conn.commit()
        elif request.method == "DELETE":  # "start from the new one"
            if not cj.save_edit(cur, campaign_id, lang, None, uid):
                conn.rollback()
                return jsonify({"error": "no_digest"}), 409
            conn.commit()
        raw = cj.stored_digest(cur, campaign_id, lang)
        if not raw:
            return jsonify({"error": "no_digest"}), 409
        state = cj.edit_state(raw)
        if state["edited"]:
            text = cd.strip_footer(raw["_edited_markdown"])
        else:
            text = cd.strip_footer(_story(cur, camp, "st", lang=lang, table_talk=False)[0])
        return jsonify({"lang": lang, "markdown": text, "max": cj.EDIT_MAX_CHARS, **state})
    finally:
        conn.close()


# ---------------------------------------------------------------------------------------------
# "Previously on…" (0.27): every member, the stored player view only, no model calls

AWAY = timedelta(hours=12)
RECAP_NIGHTS = 5        # at most this many nights on the card, the newest
RECENT_NIGHTS = 3       # the button with nothing new: the room's last nights
SO_FAR_CHARS = 600      # "the story so far" in short when the digest has no tldr


def _member_room(cur, uid, campaign_id):
    """(access, location_id, error response). The room must be one the viewer can read right now."""
    from services.location_access import fetch_readable_location_ids

    a = access(cur, uid, campaign_id)
    if a == "none":
        return a, None, (jsonify({"error": "not_found"}), 404)
    try:
        lid = int(request.args.get("location_id") or (request.get_json(silent=True) or {}).get("location_id"))
    except (TypeError, ValueError):
        return a, None, (jsonify({"error": "bad_location"}), 400)
    if lid not in fetch_readable_location_ids(cur, uid, campaign_id):
        return a, None, (jsonify({"error": "not_found"}), 404)
    return a, lid, None


def _visit_row(cur, uid, lid):
    cur.execute("SELECT last_seen_at, away_since FROM chronicle_room_visits WHERE user_id = %s AND location_id = %s",
                (uid, lid))
    return cur.fetchone()


def record_visit(cur, uid, lid, now=None):
    """The user opened (or is still in) the room. An absence of 12 hours or more moves away_since to
    the last time they were there; otherwise it stays, so a reload keeps the same recap."""
    now = now or datetime.now()
    row = _visit_row(cur, uid, lid)
    if not row:
        # two tabs on a first visit: the second insert does nothing, and both read the row again
        cur.execute("INSERT INTO chronicle_room_visits (user_id, location_id, last_seen_at) VALUES (%s, %s, %s) "
                    "ON CONFLICT (user_id, location_id) DO NOTHING", (uid, lid, now))
        row = _visit_row(cur, uid, lid)
        if not row or cj._dt(row.get("last_seen_at")) == now:
            return cj._dt((row or {}).get("away_since"))
    last = cj._dt(row.get("last_seen_at"))
    away = cj._dt(row.get("away_since"))
    if last and now - last >= AWAY:
        away = last
    cur.execute("UPDATE chronicle_room_visits SET last_seen_at = %s, away_since = %s WHERE user_id = %s AND location_id = %s",
                (now, away, uid, lid))
    return away


def _ui_lang(cur, uid):
    lang = (request.args.get("lang") or "").strip().lower()
    if lang in cd.LANGS:
        return lang
    try:
        cur.execute("SELECT ui_language FROM users WHERE id = %s", (uid,))
        lang = ((cur.fetchone() or {}).get("ui_language") or "").strip().lower()
    except Exception:
        try:
            cur.connection.rollback()
        except Exception:
            pass
        return None
    return lang if lang in cd.LANGS else None


def _so_far_short(digest):
    tldr = str(digest.get("tldr") or "").strip()
    if tldr:
        return tldr
    text = ""
    for p in digest.get("so_far") or []:
        p = str(p).strip()
        if not p:
            continue
        if text and len(text) + 1 + len(p) > SO_FAR_CHARS:
            break
        text = (text + "\n\n" + p) if text else p
    if len(text) > SO_FAR_CHARS:
        text = text[:SO_FAR_CHARS].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return text


def _first_visible(cur, campaign_id, lid, ch):
    """The night's first message as the player sees the chat (never a hidden roll's id)."""
    from services.message_actions import hidden_dice_sql_filter

    if not ch.get("first_id"):
        return None
    cur.execute(
        "SELECT m.id FROM messages m WHERE m.campaign_id = %s AND m.location_id = %s AND m.id >= %s AND m.id <= %s"
        + hidden_dice_sql_filter("m.ai_message_kind") + " ORDER BY m.id LIMIT 1",
        (campaign_id, lid, ch["first_id"], ch.get("last_id") or ch["first_id"]),
    )
    r = cur.fetchone()
    return int(r["id"]) if r else None


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle/recap/visit", methods=["POST"])
@jwt_required()
def recap_visit(campaign_id):
    """{location_id}: the user opened the room (also sent while they stay in it). Returns away_since:
    where their last absence of 12 hours or more began (null if there was none)."""
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        _a, lid, err = _member_room(cur, uid, campaign_id)
        if err:
            return err
        away = record_visit(cur, uid, lid)
        conn.commit()
        return jsonify({"location_id": lid, "away_since": _iso(away)})
    finally:
        conn.close()


def recap_of(cur, uid, campaign_id, lid, recent=False):
    """The recap of one room for one viewer (the room already checked): the player view's nights in
    that room since the viewer's last absence of 12 hours or more began, newest last, plus the story
    so far in short. recent: with nothing new, the room's last nights. Nothing without a digest."""
    camp = cj.campaign_row(cur, campaign_id)
    own = cj.chronicle_lang(cur, camp)
    lang = _ui_lang(cur, uid) or own
    # the player view for everyone: what players can read now, whoever asks
    readable = _readable_for_players(cur, campaign_id)
    stored = cj.stored_chapters(cur, campaign_id, own)
    digest = cj.stored_digest(cur, campaign_id, own)
    tr = cj.stored_digest(cur, campaign_id, lang, translated=True) if lang != own and digest else None
    if tr and tr.get("_hash") == cd.translation_hash(digest, stored):
        stored = cd.overlay_translation(stored, tr)
        digest = {k: v for k, v in tr.items() if k != "chapters"}
    else:
        lang = own  # no translation, or one behind the story: the chronicle's own language
    if digest and any(int(r) not in readable for r in digest.get("rooms") or []):
        digest = None  # a room closed since the digest was written keeps it back
    row = _visit_row(cur, uid, lid) or {}
    since = cj._dt(row.get("away_since"))
    out = {"location_id": lid, "lang": lang, "since": _iso(since), "so_far": None, "nights": [], "recent": False}
    if not digest:
        return out
    numbered = cd.number_nights(cd.visible_chapters(stored, "player", readable))
    room = [(n, c) for n, c in numbered if int(c["location_id"]) == lid]
    picked = [(n, c) for n, c in room if since and cj._dt(c.get("ended_at")) and cj._dt(c.get("ended_at")) > since]
    if not picked and recent:
        picked, out["recent"] = room[-RECENT_NIGHTS:], True
    for n, c in picked[-RECAP_NIGHTS:]:
        pc = cd.player_chapter(c)["chapter"]
        out["nights"].append({"night": n, "title": pc.get("title") or "", "summary": list(pc.get("summary") or []),
                              "started_at": _iso(c.get("started_at")), "ended_at": _iso(c.get("ended_at")),
                              "first_message_id": _first_visible(cur, campaign_id, lid, c)})
    out["so_far"] = _so_far_short(cd.player_digest(digest)) or None
    out["recap_hash"] = hashlib.sha1(json.dumps(recap_chunks(out), ensure_ascii=False).encode()).hexdigest()[:16]
    return out


def recap_chunks(recap):
    from services.voice_tts import split_chunks

    return [c for t in recap_spoken(recap) for c in split_chunks(t)]


RECAP_HEADING = {"en": "Previously on…", "el": "Προηγουμένως…"}


def recap_spoken(recap):
    """The recap as it is read aloud: [(text, lang)] in reading order, before chunking."""
    lang = recap.get("lang") if recap.get("lang") in cd.LANGS else "en"
    if not recap.get("nights") or not recap.get("so_far"):
        return []
    out = [RECAP_HEADING[lang]]
    for n in recap["nights"]:
        head = cd._label(n.get("night"), lang) + (f": {n['title']}" if n.get("title") else "")
        out.append(" ".join([head.rstrip(".") + "."] + [str(p) for p in n.get("summary") or []]))
    out.append(f"{cd.words(lang)['so_far']}. {recap['so_far']}")
    return out


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle/recap", methods=["GET"])
@jwt_required()
def get_recap(campaign_id):
    """?location_id=[&recent=1][&lang=]: see recap_of. Every member; the player view only."""
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        _a, lid, err = _member_room(cur, uid, campaign_id)
        if err:
            return err
        return jsonify(recap_of(cur, uid, campaign_id, lid, _flag("recent")))
    finally:
        conn.close()


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle/recap/tts", methods=["POST"])
@jwt_required()
def recap_tts(campaign_id):
    """?lang= (query) and {location_id, chunk, recent, recap_hash}: "Read it" with server voices. The
    text is built here from the same recap (never sent by the browser), in the narrator's voice and the
    user's settings. The audio is remembered with the chronicle and room, so only members who can read
    that room can play it, and it goes with the chronicle. 409 recap_changed when the recap is no longer
    the one being read (its recap_hash from GET)."""
    from routes import voice as rv
    from services.voice_tts import _body

    uid = _uid()
    body = request.get_json(silent=True) or {}
    chunk = body.get("chunk", 0)
    if isinstance(chunk, bool) or not isinstance(chunk, int) or not 0 <= chunk < 200:
        return jsonify({"error": "bad_chunk"}), 400
    conn = get_db()
    try:
        cur = conn.cursor()
        _a, lid, err = _member_room(cur, uid, campaign_id)
        if err:
            return err
        recap = recap_of(cur, uid, campaign_id, lid, bool(body.get("recent")))
        if body.get("recap_hash") and body["recap_hash"] != recap["recap_hash"]:
            return jsonify({"error": "recap_changed"}), 409
        texts = recap_chunks(recap)
        if not texts:
            return jsonify({"error": "not_spoken"}), 400
        if chunk >= len(texts):
            return jsonify({"error": "no_such_chunk"}), 400
        rv.ensure_voice_audio_table(cur)
        cur.execute("SELECT voice_settings FROM campaigns WHERE id = %s", (campaign_id,))
        camp = (cur.fetchone() or {}).get("voice_settings")
        user_settings = rv._user_settings(cur, uid)
        tts = _body("storyteller", texts[chunk], recap["lang"], None, user_settings, camp, None)
        out, status = rv._speech_tts(cur, rv.cloud_voices.apply(tts, rv._cloud_config(), camp), None,
                                     campaign_id, lid)
        conn.commit()
        if status == 200:
            out.update({"chunk": chunk, "chunks": len(texts), "text": texts[chunk]})
        return jsonify(out), status
    except Exception as e:  # noqa: BLE001
        logger.error("recap tts error: %s", type(e).__name__)
        return jsonify({"error": "Failed to start speech"}), 500
    finally:
        conn.close()


# ---------------------------------------------------------------------------------------------
# Archives of deleted chronicles

def _role(cur, uid):
    cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
    return ((cur.fetchone() or {}).get("role") or "").strip().lower()


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle/session-marks", methods=["GET", "POST"])
@jwt_required()
def session_marks_route(campaign_id):
    """GET: the message ids marked "session ended here" (every member; players only get marks in rooms
    they can read). POST {message_id}: mark one (the Storyteller and site admins only). A mark cuts
    every room at its time, so the nights around it are rewritten on the next Update."""
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        a = access(cur, uid, campaign_id)
        if a == "none":
            return jsonify({"error": "not_found"}), 404
        if request.method == "GET":
            cur.execute(
                "SELECT s.message_id, m.location_id FROM chronicle_session_marks s JOIN messages m ON m.id = s.message_id "
                "WHERE s.campaign_id = %s ORDER BY s.message_id",
                (campaign_id,),
            )
            rows = cur.fetchall()
            if a == "player":
                return jsonify({"message_ids": _player_marks(cur, campaign_id, rows)})
            return jsonify({"message_ids": [int(r["message_id"]) for r in rows]})
        if a != "st":
            return jsonify({"error": "forbidden"}), 403
        body = request.get_json(silent=True) or {}
        try:
            mid = int(body.get("message_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "bad_message"}), 400
        cur.execute("SELECT id FROM messages WHERE id = %s AND campaign_id = %s", (mid, campaign_id))
        if not cur.fetchone():
            return jsonify({"error": "not_found"}), 404
        cur.execute(
            "INSERT INTO chronicle_session_marks (message_id, campaign_id, created_by) VALUES (%s, %s, %s) "
            "ON CONFLICT (message_id) DO NOTHING",
            (mid, campaign_id, uid),
        )
        conn.commit()
        return jsonify({"message_id": mid, "marked": True})
    finally:
        conn.close()


def _player_marks(cur, campaign_id, rows):
    """Marks as a player may see them: only in rooms they can read, and never the id of a row the chat
    hides from them (a hidden roll). A mark on such a row moves to the latest message the player can
    see in that room at or before it, so the line still shows."""
    from services.message_actions import hidden_dice_sql_filter

    readable = _readable_for_players(cur, campaign_id)
    out = []
    for r in rows:
        if int(r["location_id"]) not in readable:
            continue
        cur.execute(
            "SELECT m.id FROM messages m WHERE m.campaign_id = %s AND m.location_id = %s AND m.id <= %s"
            + hidden_dice_sql_filter("m.ai_message_kind") + " ORDER BY m.id DESC LIMIT 1",
            (campaign_id, r["location_id"], r["message_id"]),
        )
        seen = cur.fetchone()
        if seen and int(seen["id"]) not in out:
            out.append(int(seen["id"]))
    return sorted(out)


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle/session-marks/<int:message_id>", methods=["DELETE"])
@jwt_required()
def session_mark_delete(campaign_id, message_id):
    """Remove a mark (the Storyteller and site admins only)."""
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        a = access(cur, uid, campaign_id)
        if a == "none":
            return jsonify({"error": "not_found"}), 404
        if a != "st":
            return jsonify({"error": "forbidden"}), 403
        cur.execute("DELETE FROM chronicle_session_marks WHERE message_id = %s AND campaign_id = %s",
                    (message_id, campaign_id))
        if not cur.rowcount:
            return jsonify({"error": "not_found"}), 404
        conn.commit()
        return jsonify({"message_id": message_id, "marked": False})
    finally:
        conn.close()


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle/settings", methods=["GET", "PUT"])
@jwt_required()
def chronicle_settings(campaign_id):
    """The chronicle's own settings (gap, table talk, nightly run, writer model): the Storyteller
    (creator) and site admins only. A new gap re-cuts the nights: the ones it changes are stale."""
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        a, err = _gate(cur, uid, campaign_id)
        if err:
            return err
        if a != "st":
            return jsonify({"error": "forbidden"}), 403
        is_admin = _role(cur, uid) == "admin"
        try:
            options = cs.model_options()
        except Exception:  # noqa: BLE001 - the roles can't be read: no override offered
            logger.warning("chronicle settings: model options unavailable")
            options = []
        current = cs.load(cur, campaign_id)
        if request.method == "PUT":
            try:
                new = cs.validate(request.get_json(silent=True), current, options, is_admin)
            except RequestValidationError as e:
                conn.rollback()
                return jsonify({"error": e.public_message}), 400
            cs.save(cur, campaign_id, new)
            conn.commit()
            current = new
        return jsonify({
            "settings": current,
            "models": [o for o in options if is_admin or not o["cloud"]],
            "gap_range": list(cs.GAP_RANGE),
            "caps": {"nights_per_job": cs.max_nights_per_job(), "seconds_per_job": cs.max_seconds_per_job()},
            "nightly_at": _nightly_status()["at"],
        })
    finally:
        conn.close()


def _nightly_status():
    from services.chronicle_nightly import status

    return status()


@chronicle_bp.route("/chronicle-health", methods=["GET"])
@jwt_required()
def chronicle_health():
    """Admin → AI system: the writer at a glance (site admins only)."""
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        if _role(cur, uid) != "admin":
            return jsonify({"error": "forbidden"}), 403
        start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cur.execute("SELECT status, error, finished_at, updated_at FROM chronicle_jobs WHERE created_at >= %s", (start,))
        today = cur.fetchall()
        cur.execute("SELECT error, finished_at, updated_at FROM chronicle_jobs WHERE status = 'failed' "
                    "ORDER BY id DESC LIMIT 1")
        last = cur.fetchone()
        cur.execute(
            "SELECT j.id, j.campaign_id, c.name AS campaign_name, j.scope, j.status, j.phase, j.night, j.nights, "
            "j.requested_by, j.created_at FROM chronicle_jobs j LEFT JOIN campaigns c ON c.id = j.campaign_id "
            "WHERE j.status IN ('queued', 'waiting', 'running') ORDER BY j.id"
        )
        live = cur.fetchall()
        return jsonify({
            "jobs_today": len(today),
            "failures_today": sum(1 for r in today if r["status"] == "failed"),
            "seconds_per_night": round(cj.seconds_per_night(cur), 1),
            "last_error": {"code": last["error"] or "internal",
                           "at": _iso(cj._dt(last.get("finished_at") or last.get("updated_at")))} if last else None,
            "jobs": [{"id": r["id"], "campaign_id": r["campaign_id"], "campaign_name": r["campaign_name"],
                      "scope": r["scope"], "status": r["status"], "phase": r["phase"], "night": r["night"],
                      "nights": r["nights"], "nightly": r["requested_by"] is None,
                      "created_at": _iso(cj._dt(r["created_at"]))} for r in live],
            "nightly_at": _nightly_status()["at"],
            "caps": {"nights_per_job": cs.max_nights_per_job(), "seconds_per_job": cs.max_seconds_per_job(),
                     "keep_days": cs.job_keep_days()},
        })
    finally:
        conn.close()


@chronicle_bp.route("/chronicle-archives", methods=["GET"])
@jwt_required()
def list_archives():
    from services.chronicle_archive import ARCHIVE_ST_DAYS, archive_size, can_download

    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        role = _role(cur, uid)
        if role == "admin":
            cur.execute("SELECT * FROM chronicle_archives ORDER BY id DESC LIMIT 500")
        else:  # the chronicle's Storyteller, for ARCHIVE_ST_DAYS days
            since = datetime.now() - timedelta(days=ARCHIVE_ST_DAYS)
            cur.execute("SELECT * FROM chronicle_archives WHERE storyteller_id = %s AND created_at >= %s "
                        "ORDER BY id DESC LIMIT 500", (uid, since))
        rows = [r for r in cur.fetchall() if can_download(r, uid, role)]
        ids = {int(x) for r in rows for x in (r.get("storyteller_id"), r.get("deleted_by")) if x is not None}
        names = {}
        if ids:
            cur.execute(f"SELECT id, username FROM users WHERE id IN ({', '.join(['%s'] * len(ids))})", tuple(ids))
            names = {int(u["id"]): u["username"] for u in cur.fetchall()}

        def who(v):
            return names.get(int(v)) if v is not None else None

        return jsonify({"archives": [
            {"id": r["id"], "campaign_id": r["campaign_id"], "campaign_name": r["campaign_name"],
             "nights": r["nights"], "nights_written": r["nights_written"], "messages": r["messages"],
             "storyteller": who(r.get("storyteller_id")), "deleted_by": who(r.get("deleted_by")),
             "size": archive_size(r), "created_at": _iso(cj._dt(r.get("created_at")))} for r in rows],
            "st_days": ARCHIVE_ST_DAYS})
    finally:
        conn.close()


@chronicle_bp.route("/chronicle-archives/<int:archive_id>/<which>", methods=["GET"])
@jwt_required()
def download_archive(archive_id, which):
    from services.chronicle_archive import FILES, archive_file, can_download

    if which not in FILES:
        return jsonify({"error": "not_found"}), 404
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        role = _role(cur, uid)
        cur.execute("SELECT * FROM chronicle_archives WHERE id = %s", (archive_id,))
        row = cur.fetchone()
        if not row or not can_download(row, uid, role):
            return jsonify({"error": "not_found"}), 404
        path = archive_file(row, which)
        if not path:
            return jsonify({"error": "missing"}), 410
        name = _file_name(row["campaign_name"], which)
        return send_file(path, mimetype="text/markdown; charset=utf-8", as_attachment=True, download_name=name)
    finally:
        conn.close()

