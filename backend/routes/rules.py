"""Rules data for the client: GET /api/rules/v5/catalog (the V5 creation catalog)."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from services.v5_catalog import catalog_etag, load_catalog

bp = Blueprint("rules", __name__)


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
    etag = catalog_etag()
    if etag and request.if_none_match.contains(etag):
        resp = jsonify()
        resp.status_code = 304
        resp.set_etag(etag)
        return resp
    resp = jsonify({"etag": etag, **data})
    if etag:
        resp.set_etag(etag)
    resp.headers["Cache-Control"] = "private, no-cache"
    return resp
