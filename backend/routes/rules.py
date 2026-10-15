"""Rules data for the client: GET /api/rules/v5/catalog (the V5 creation catalog) and
GET /api/rules/v5/guided (the guided-mode questions)."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from services.v5_catalog import catalog_etag, load_catalog
from services.v5_guided import guided_etag, load_guided

bp = Blueprint("rules", __name__)


def _with_etag(data, etag):
    """200 with the data and its ETag, or 304 when the client already has this version."""
    if etag and request.if_none_match.contains(etag):
        resp = jsonify()
        resp.status_code = 304
        resp.set_etag(etag)
        resp.headers["Cache-Control"] = "private, no-cache"
        return resp
    resp = jsonify({"etag": etag, **data})
    if etag:
        resp.set_etag(etag)
    resp.headers["Cache-Control"] = "private, no-cache"
    return resp


@bp.route("/v5/catalog", methods=["GET"])
@jwt_required()
def v5_catalog():
    """
    Clans, Disciplines with powers, rituals, ceremonies, formulae, predator types and books:
    facts with book and page, plus short descriptions {en, el}. ETag / If-None-Match supported.
    """
    data = load_catalog()
    if data is None:
        return jsonify({"error": "The V5 catalog is not installed"}), 404
    return _with_etag(data, catalog_etag())


@bp.route("/v5/guided", methods=["GET"])
@jwt_required()
def v5_guided():
    """
    The guided-mode questions (docs/rules/v5/guided/questions.json, format in its README.md):
    {version, author, thresholds, questions}. ETag / If-None-Match supported.
    """
    data = load_guided()
    if data is None:
        return jsonify({"error": "The guided questions are not installed"}), 404
    return _with_etag(data, guided_etag())
