"""
"The chronicle so far" (docs/CHRONICLE.md): /api/campaigns/<id>/chronicle...

Who:
- someone who can't open the chronicle: 404 (as messages do)
- a player: 403 (players get "Previously on…" in a later release, never these routes)
- a helper who can open the chronicle (a member): reads, exports and Update; never edits
- the Storyteller (creator) and site admins: everything (edits come in 0.25)
Archives of deleted chronicles: /api/chronicle-archives (site admins; the deleting Storyteller for 30 days).
"""

from __future__ import annotations

import logging
from datetime import datetime
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


def _state(cursor, camp, view):
    lang = cj.chronicle_lang(cursor, camp)
    readable = _readable_for_players(cursor, camp["id"]) if view == "player" else None
    chapters = cd.visible_chapters(cj.stored_chapters(cursor, camp["id"], lang), view, readable)
    digest = cj.stored_digest(cursor, camp["id"], lang)
    withheld = False
    if digest and view == "player":
        # rooms are checked again now: a room closed since the digest was written keeps it back
        if any(int(r) not in readable for r in digest.get("rooms") or []):
            digest, withheld = None, True
        else:
            digest = cd.player_digest(digest)
    written_at = digest.get("_written_at") if digest else None
    if digest:
        digest = {k: v for k, v in digest.items() if not k.startswith("_") and k != "rooms"}
    return lang, chapters, digest, withheld, written_at


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
        lang, chapters, digest, withheld, written_at = _state(cur, camp, view)
        cur.execute("SELECT MAX(id) AS last FROM messages WHERE campaign_id = %s", (campaign_id,))
        last_msg = (cur.fetchone() or {}).get("last") or 0
        last_written = max([c.get("last_id") or 0 for c in chapters] or [0])
        total = (digest or {}).get("nights_total")
        return jsonify({
            "lang": lang,
            "view": view,
            "access": a,
            "can_edit": a == "st",
            "digest": digest,
            "withheld": withheld,
            "written_at": _iso(written_at),
            "nights_written": len(chapters),
            "nights_total": total if total is not None else len(chapters),
            "new_since": bool(last_msg and last_msg > last_written),
            "chapters": [chapter_out(c, i, view) for i, c in enumerate(chapters, 1)],
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
        _lang, chapters, _d, _w, _at = _state(cur, camp, view)
        out = [chapter_out(c, i, view) for i, c in enumerate(chapters, 1)]
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
        scope = scope if scope in ("update", "all") else "update"
        if scope == "all" and a != "st":
            return jsonify({"error": "forbidden"}), 403
        try:
            job_id = cj.create_job(cur, campaign_id, uid, scope)
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


def _file_name(name, suffix):
    base = "".join(c if c.isprintable() and c not in '\\/:*?"<>|' else " " for c in str(name or ""))
    base = " ".join(base.split())[:80] or "chronicle"
    return f"{base} — {suffix}.md"


def _markdown_response(text, filename):
    ascii_name = filename.encode("ascii", "replace").decode().replace("?", "_").replace('"', "")
    return Response(
        text, mimetype="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}",
                 "Cache-Control": "no-store"},
    )


def _flag(name):
    return (request.args.get(name) or "").strip().lower() in ("1", "true", "yes")


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle.md", methods=["GET"])
@jwt_required()
def export_story(campaign_id):
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        _a, err = _gate(cur, uid, campaign_id)
        if err:
            return err
        view = _view(request.args.get("view"))
        camp = cj.campaign_row(cur, campaign_id)
        lang, chapters, digest, _w, written_at = _state(cur, camp, view)
        readable = _readable_for_players(cur, campaign_id) if view == "player" else None
        facts = cj.facts(cur, camp, view, readable)
        facts["written_at"] = written_at
        facts["nights_total"] = max((digest or {}).get("nights_total") or 0, len(chapters))
        if chapters:
            facts["first_at"], facts["last_at"] = chapters[0]["started_at"], chapters[-1]["started_at"]
        if _flag("with_table_talk"):
            lobby = [c for c in cj.stored_chapters(cur, campaign_id, lang) if c["kind"] == "lobby"]
            chapters = chapters + lobby
        existing = cj.message_ids(cur, campaign_id) if view == "st" else None
        text = cd.story_markdown(facts, digest, chapters, lang, view, _flag("with_table_talk"), existing)
        return _markdown_response(text, _file_name(camp["name"], "so far" if lang != "el" else "ως τώρα"))
    finally:
        conn.close()


@chronicle_bp.route("/campaigns/<int:campaign_id>/chronicle/minutes.md", methods=["GET"])
@jwt_required()
def export_minutes(campaign_id):
    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        _a, err = _gate(cur, uid, campaign_id)
        if err:
            return err
        view = _view(request.args.get("view"))
        last = request.args.get("last")
        try:
            last_n = int(last) if last else None
        except ValueError:
            return jsonify({"error": "bad_last"}), 400
        if last_n is not None and not 1 <= last_n <= 1000:
            return jsonify({"error": "bad_last"}), 400
        camp = cj.campaign_row(cur, campaign_id)
        lang, chapters, digest, _w, _at = _state(cur, camp, view)
        facts = cj.facts(cur, camp, view)
        facts["nights_total"] = max((digest or {}).get("nights_total") or 0, len(chapters))
        existing = cj.message_ids(cur, campaign_id) if view == "st" else None
        text = cd.minutes_markdown(facts, chapters, lang, view, last_n, existing, _flag("with_table_talk"))
        return _markdown_response(text, _file_name(camp["name"], "πρακτικά" if lang == "el" else "minutes"))
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
    from services.chronicle_archive import can_download

    uid = _uid()
    conn = get_db()
    try:
        cur = conn.cursor()
        role = _role(cur, uid)
        cur.execute("SELECT * FROM chronicle_archives ORDER BY id DESC LIMIT 500")
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

