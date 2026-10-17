"""
"The chronicle so far" (docs/CHRONICLE.md): /api/campaigns/<id>/chronicle...

Who:
- someone who can't open the chronicle: 404 (as messages do)
- a player: 403 (players get "Previously on…" in a later release, never these routes)
- a helper who can open the chronicle (a member): reads and exports only
- the Storyteller (creator) and site admins: also Update, Rewrite everything, Translate and the edit copy
Archives of deleted chronicles: /api/chronicle-archives (site admins; the deleting Storyteller for 30 days).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from database import get_db
from services import chronicle_digest as cd
from services import chronicle_jobs as cj

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
        _a, err = _gate(cur, uid, campaign_id)
        if err:
            return err
        if request.method == "DELETE":
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


def _paper():
    return "letter" if (request.args.get("paper") or "").strip().lower() == "letter" else "a4"


def _story(cur, camp, view):
    """(markdown, lang, edited, translated) of the story so far. The Storyteller's view uses the edit
    copy when there is one (in the chronicle's own language); the player view never does."""
    own = cj.chronicle_lang(cur, camp)
    lang = _want_lang(own)
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
    if _flag("with_table_talk"):
        lobby = [c for c in cj.stored_chapters(cur, camp["id"], own) if c["kind"] == "lobby"]
        chapters = chapters + lobby
    existing = cj.message_ids(cur, camp["id"]) if view == "st" else None
    translated = lang != own
    text = cd.story_markdown(facts, digest, chapters, lang, view, _flag("with_table_talk"), existing, translated)
    return text, lang, False, translated


def _minutes(cur, camp, view, last_n):
    """Always the generated record (never the edit copy), in the chronicle's language or its translation."""
    own = cj.chronicle_lang(cur, camp)
    lang, chapters, digest, _w, _at, _x = _state(cur, camp, view, _want_lang(own))
    readable = _readable_for_players(cur, camp["id"]) if view == "player" else None
    facts = cj.facts(cur, camp, view, readable, chapters)
    facts["nights_total"] = max((digest or {}).get("nights_total") or 0, len(chapters))
    existing = cj.message_ids(cur, camp["id"]) if view == "st" else None
    translated = lang != own
    text = cd.minutes_markdown(facts, chapters, lang, view, last_n, existing, _flag("with_table_talk"), translated)
    return text, lang, translated


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
            text, lang, translated = _minutes(cur, camp, view, last_n)
            edited = False
            suffix = "πρακτικά" if lang == "el" else "minutes"
        if fmt == "md":
            return _markdown_response(text, _file_name(camp["name"], suffix))
        from services.chronicle_pdf import build_pdf

        title = f"{camp['name']} — {cd.words(lang)['so_far_title' if what == 'story' else 'minutes_title']}"
        data = build_pdf(text, lang, _paper(), edited=edited, translated=translated, title=title)
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
            text = cd.strip_footer(_story(cur, camp, "st")[0])
        return jsonify({"lang": lang, "markdown": text, "max": cj.EDIT_MAX_CHARS, **state})
    finally:
        conn.close()


# ---------------------------------------------------------------------------------------------
# Archives of deleted chronicles

def _role(cur, uid):
    cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
    return ((cur.fetchone() or {}).get("role") or "").strip().lower()


@chronicle_bp.route("/chronicle-archives", methods=["GET"])
@jwt_required()
def list_archives():
    from services.chronicle_archive import ARCHIVE_ST_DAYS, can_download

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
        return jsonify({"archives": [
            {"id": r["id"], "campaign_id": r["campaign_id"], "campaign_name": r["campaign_name"],
             "nights": r["nights"], "nights_written": r["nights_written"], "messages": r["messages"],
             "created_at": _iso(cj._dt(r.get("created_at")))} for r in rows]})
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

