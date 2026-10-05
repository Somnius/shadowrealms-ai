"""
App-wide security wiring (phase 5; docs/SECURITY_MODEL.md):

- ProxyFix: trust exactly ONE proxy hop (the local nginx). nginx itself resolves the real client
  address from the DietPi proxy with the realip module and overwrites X-Forwarded-For, so the
  backend never has to parse a client-controlled header chain. The backend listens on 127.0.0.1.
- CORS only for origins in CORS_ORIGINS (none needed for same-origin through nginx).
- Flask-JWT-Extended: blocklist check on every request (token_version + jti), JSON error bodies
  with stable codes the frontend can act on.
- Flask-Limiter (Redis, in-memory fallback) with per-route limits and a JSON 429.
- Security headers on every response, no-store caching for API responses.
- Generic error handler: exception text never reaches the client; it is logged instead.
"""

from __future__ import annotations

import logging
import os
import time

from flask import g, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from services.auth_security import FailoverStore, MemoryStore, RedisStore, Throttle
from services.log_safety import safe_log_value

logger = logging.getLogger(__name__)

limiter = None
_throttle = None


# ---------------------------------------------------------------------------------------------
# Client identity
# ---------------------------------------------------------------------------------------------

def proxy_hops() -> int:
    try:
        return max(0, int(os.getenv("TRUSTED_PROXY_HOPS", "1")))
    except ValueError:
        return 1


def install_proxy_fix(app, hops=None):
    hops = proxy_hops() if hops is None else hops
    if hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=0, x_port=0, x_prefix=0)
    return app


def client_ip() -> str:
    """Real client address (after ProxyFix)."""
    return request.remote_addr or "unknown"


def user_or_ip_key() -> str:
    """Rate-limit key: the user id from a validly signed bearer token, else the client IP.
    (Signature checked, blocklist not: the route itself still rejects revoked tokens.)"""
    auth = request.headers.get("Authorization", "")
    if auth[:7].lower() == "bearer " and len(auth) < 4096:
        try:
            from flask_jwt_extended import decode_token

            sub = decode_token(auth[7:].strip()).get("sub")
            if sub:
                return f"u:{sub}"
        except Exception:  # noqa: BLE001 - invalid/expired token: fall back to IP
            pass
    return f"ip:{client_ip()}"


def ip_key() -> str:
    return f"ip:{client_ip()}"


# ---------------------------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------------------------

def redis_url() -> str:
    url = os.getenv("RATELIMIT_STORAGE_URI", "").strip()
    if url:
        return url
    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    return f"redis://{host}:{port}/0"


def get_throttle() -> Throttle:
    global _throttle
    if _throttle is None:
        primary = None
        if os.getenv("AUTH_THROTTLE_STORE", "redis").lower() == "redis":
            try:
                import redis

                primary = RedisStore(redis.Redis.from_url(redis_url(), socket_timeout=2, socket_connect_timeout=2))
            except Exception as e:  # noqa: BLE001
                logger.warning("Redis client unavailable for auth throttle: %s", e)
        _throttle = Throttle(FailoverStore(primary, MemoryStore()))
    return _throttle


# ---------------------------------------------------------------------------------------------
# Rate limits
# ---------------------------------------------------------------------------------------------

# endpoint -> (limits, key). Kept here so every limit is visible in one place.
ROUTE_LIMITS = {
    "auth.login": ("10 per minute;60 per hour", ip_key),
    "auth.register": ("5 per minute;20 per hour", ip_key),
    "auth.refresh": ("30 per minute", ip_key),
    "auth.change_password": ("5 per 15 minutes", user_or_ip_key),
    "auth.logout": ("30 per minute", user_or_ip_key),
    "auth.logout_all": ("10 per minute", user_or_ip_key),
    "events.events_ticket": ("30 per minute", user_or_ip_key),
    "messages.save_message": ("60 per minute;1000 per hour", user_or_ip_key),
    "characters.character_sheet_pdf": ("20 per minute", user_or_ip_key),  # builds a PDF each time
}
AI_LIMIT = "12 per minute;300 per hour"      # every POST in the ai blueprint + dice.ai_roll
DICE_LIMIT = "60 per minute"                 # other dice POSTs
DEFAULT_LIMIT = "600 per minute"             # everything else, per user (or IP when anonymous)


def _retry_after_seconds() -> int:
    try:
        cur = limiter.current_limit if limiter else None
        if cur is not None:
            return max(1, int(cur.reset_at - time.time()))
    except Exception:  # noqa: BLE001
        pass
    return 60


def rate_limited_response(retry_after: int, code: str = "RATE_LIMITED", message: str = None):
    resp = jsonify({
        "error": message or "Too many requests. Please wait a moment and try again.",
        "code": code,
        "retry_after": int(retry_after),
    })
    resp.status_code = 429
    resp.headers["Retry-After"] = str(int(retry_after))
    return resp


def init_limiter(app):
    global limiter
    from flask_limiter import HeaderNames, Limiter

    limiter = Limiter(
        key_func=user_or_ip_key,
        app=app,
        storage_uri=redis_url(),
        storage_options={"socket_connect_timeout": 2, "socket_timeout": 2},
        strategy="fixed-window",
        default_limits=[DEFAULT_LIMIT],
        headers_enabled=True,
        # Retry-After is set by our own 429 responses (rate limits and login locks); the
        # limiter's copy would overwrite a lock's Retry-After with its window reset.
        header_name_mapping={HeaderNames.RETRY_AFTER: "X-RateLimit-Retry-After"},
        swallow_errors=True,              # Redis down: never 500 because of the limiter...
        in_memory_fallback_enabled=True,  # ...fall back to per-process counters instead
        key_prefix="srai:rl",
        enabled=os.getenv("RATELIMIT_ENABLED", "true").lower() != "false",
    )

    @app.errorhandler(429)
    def _too_many(e):
        return rate_limited_response(_retry_after_seconds())

    return limiter


def apply_route_limits(app):
    """Attach limits to registered view functions (call after all blueprints are registered)."""
    if limiter is None:
        return
    wanted = dict(ROUTE_LIMITS)
    for rule in app.url_map.iter_rules():
        ep = rule.endpoint
        if ep in wanted or "POST" not in (rule.methods or ()):
            continue
        if ep.startswith("ai.") or ep == "dice.ai_roll":
            wanted[ep] = (AI_LIMIT, user_or_ip_key)
        elif ep.startswith("dice."):
            wanted[ep] = (DICE_LIMIT, user_or_ip_key)
    for ep, (lim, key) in wanted.items():
        view = app.view_functions.get(ep)
        if view is None:
            logger.warning("Rate limit for unknown endpoint %s skipped", ep)
            continue
        app.view_functions[ep] = limiter.limit(lim, key_func=key)(view)
    for ep in ("health_check", "events.events_stream"):
        view = app.view_functions.get(ep)
        if view is not None:
            app.view_functions[ep] = limiter.exempt(view)


# ---------------------------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------------------------

def init_jwt(app):
    from flask_jwt_extended import JWTManager

    from services.auth_tokens import is_token_revoked

    jwt = JWTManager(app)

    @jwt.token_in_blocklist_loader
    def _blocklisted(_header, payload):
        revoked, reason = is_token_revoked(payload)
        if revoked:
            g.token_revoked_reason = reason
        return revoked

    def _err(msg, code, status=401):
        return jsonify({"error": msg, "code": code}), status

    @jwt.revoked_token_loader
    def _revoked(_h, _p):
        return _err("Your session has ended. Please sign in again.", "TOKEN_REVOKED")

    @jwt.expired_token_loader
    def _expired(_h, _p):
        return _err("Your session has expired. Please sign in again.", "TOKEN_EXPIRED")

    @jwt.invalid_token_loader
    def _invalid(_reason):
        return _err("Invalid session. Please sign in again.", "TOKEN_INVALID")

    @jwt.unauthorized_loader
    def _missing(_reason):
        return _err("Authentication required.", "AUTH_REQUIRED")

    @jwt.needs_fresh_token_loader
    def _fresh(_h, _p):
        return _err("Please sign in again to continue.", "FRESH_LOGIN_REQUIRED")

    return jwt


# ---------------------------------------------------------------------------------------------
# Headers, CORS, errors
# ---------------------------------------------------------------------------------------------

def cors_origins():
    raw = os.getenv("CORS_ORIGINS", "")
    return [o.strip() for o in raw.split(",") if o.strip() and o.strip() != "*"]


def init_cors(app):
    origins = cors_origins()
    if not origins:
        return  # same-origin through nginx: no CORS headers at all
    from flask_cors import CORS

    CORS(app, resources={r"/api/*": {"origins": origins}}, supports_credentials=False,
         allow_headers=["Authorization", "Content-Type"], max_age=600)


def security_headers(response):
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("Referrer-Policy", "same-origin")
    h.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    path = request.path or ""
    if path.startswith("/api/") or path == "/health":
        h.setdefault("Cache-Control", "no-store")
        if response.mimetype == "application/json":
            h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    if path.startswith("/api/auth/"):
        h["Cache-Control"] = "no-store"
        h["Pragma"] = "no-cache"
    return response


def init_error_handlers(app):
    from services.auth_tokens import AuthStoreUnavailable

    @app.errorhandler(AuthStoreUnavailable)
    def _store_down(e):
        logger.error("Session store unavailable: %s", e)
        return jsonify({"error": "Service temporarily unavailable. Please retry.", "code": "UNAVAILABLE"}), 503

    @app.errorhandler(HTTPException)
    def _http(e):
        if e.code == 429:
            return rate_limited_response(_retry_after_seconds())
        return jsonify({"error": e.name, "code": f"HTTP_{e.code}"}), e.code

    @app.errorhandler(Exception)
    def _unhandled(e):
        if isinstance(e, HTTPException):
            return _http(e)
        logger.exception("Unhandled error on %s %s", safe_log_value(request.method), safe_log_value(request.path))
        return jsonify({"error": "Internal server error", "code": "INTERNAL"}), 500


def init_app_security(app):
    """Everything except the per-route limits (apply_route_limits after blueprints)."""
    app.config["PROPAGATE_EXCEPTIONS"] = False
    install_proxy_fix(app)
    init_cors(app)
    init_jwt(app)
    init_error_handlers(app)
    init_limiter(app)
    app.after_request(security_headers)
