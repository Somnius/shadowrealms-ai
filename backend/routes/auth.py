#!/usr/bin/env python3
"""
ShadowRealms AI - Authentication Routes (hardened in v0.9 phase 5; docs/SECURITY_MODEL.md)

POST /api/auth/login            username + password -> access token (JSON) + refresh cookie
POST /api/auth/register         invite-only signup -> same as login
POST /api/auth/refresh          refresh cookie (rotating, single use) -> new access token + cookie
POST /api/auth/logout           revoke this access token and this login's refresh chain
POST /api/auth/logout-all       revoke every token of the user (token_version bump)
POST /api/auth/change-password  current + new password -> new tokens; other sessions end
GET  /api/auth/profile          current user
"""

import fcntl
import json
import logging
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import decode_token, get_jwt, get_jwt_identity, jwt_required

from database import ensure_users_player_profile_columns, get_db
from services.app_security import client_ip, get_throttle, rate_limited_response
from services.auth_security import (
    RULE_INVITE_IP,
    check_password_policy,
    hash_password,
    is_known_ip,
    login_checks,
    needs_rehash,
    remember_ip,
    success_clears,
    verify_password,
)
from services.auth_tokens import (
    REFRESH_COOKIE,
    REFRESH_COOKIE_PATH,
    bump_token_version,
    consume_refresh,
    issue_tokens,
    log_auth_event,
    revoke_family,
    revoke_jti,
)
from services.mail_service import is_smtp_configured, send_invalid_invite_alert, send_welcome_registration
from services.log_safety import safe_log_value

logger = logging.getLogger(__name__)

GENERIC_LOGIN_ERROR = "Invalid username or password."
MAX_USERNAME = 150
MAX_EMAIL = 254

# ---------------------------------------------------------------------------------------------
# Invites (backend/invites.json). Claims are atomic across threads and gunicorn workers.
# ---------------------------------------------------------------------------------------------

INVITES_FILE = os.path.join(os.path.dirname(__file__), '..', 'invites.json')


@contextmanager
def _invites_locked():
    # Lock file outside the repo; every gunicorn worker runs in the same container (same /tmp).
    lock_path = os.path.join(tempfile.gettempdir(), 'srai-invites.lock')
    with open(lock_path, 'a') as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def load_invites():
    """Load invite codes from invites.json"""
    try:
        with open(INVITES_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("invites.json not found")
        return {"invites": {}}
    except json.JSONDecodeError:
        logger.error("invites.json is not valid JSON")
        return {"invites": {}}


def save_invites(data):
    """Save invite codes to invites.json (atomic replace)."""
    d = os.path.dirname(os.path.abspath(INVITES_FILE))
    fd, tmp = tempfile.mkstemp(prefix='.invites.', dir=d)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2)
        try:  # keep the original mode and owner (the container runs as root, the file is the host user's)
            st = os.stat(INVITES_FILE)
            os.chmod(tmp, st.st_mode & 0o777)
            os.chown(tmp, st.st_uid, st.st_gid)
        except OSError:
            pass
        os.replace(tmp, INVITES_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def validate_invite_code(code):
    """Return the invite's role (admin/player) if it exists and has uses left, else None."""
    if not code:
        return None
    invite = load_invites().get('invites', {}).get(str(code).strip())
    if not invite or invite.get('uses', 0) >= invite.get('max_uses', 0):
        return None
    return invite.get('type')


def _bump_invite_uses(code, delta):
    data = load_invites()
    invite = data.get('invites', {}).get(code)
    if invite and invite.get('uses', 0) + delta >= 0:
        invite['uses'] = invite.get('uses', 0) + delta
        save_invites(data)


def claim_invite_code(code):
    """Atomically check and use one slot of an invite (file lock across threads and gunicorn
    workers). Returns its role, or None if invalid/exhausted."""
    code = str(code or '').strip()
    if not code:
        return None
    with _invites_locked():
        role = validate_invite_code(code)
        if role is not None:
            _bump_invite_uses(code, +1)
        return role


def release_invite_code(code):
    """Give back a slot claimed by a registration that then failed."""
    with _invites_locked():
        _bump_invite_uses(str(code or '').strip(), -1)


def use_invite_code(code):
    """Kept for callers of the old API (tests patch it)."""
    with _invites_locked():
        _bump_invite_uses(str(code or '').strip(), +1)
    return True


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------

bp = Blueprint('auth', __name__)


def _json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _ua():
    return (request.headers.get('User-Agent') or '')[:300]


def _user_json(user):
    return {
        'id': user['id'],
        'username': user['username'],
        'email': user.get('email'),
        'role': user['role'],
        'display_timezone': user.get('display_timezone'),
        'player_avatar_url': user.get('player_avatar_url'),
        'active_character_id': user.get('active_character_id'),
    }


def _cookie_secure():
    mode = os.environ.get('AUTH_COOKIE_SECURE', 'auto').lower()
    if mode in ('1', 'true', 'yes'):
        return True
    if mode in ('0', 'false', 'no'):
        return False
    return request.is_secure  # https through the proxies (X-Forwarded-Proto), plain http on the LAN


def _token_response(payload, tokens, status=200):
    """JSON with the access token; the refresh token goes only into an HttpOnly cookie."""
    body = dict(payload)
    body['access_token'] = tokens['access_token']
    body['expires_in'] = tokens['expires_in']
    resp = jsonify(body)
    resp.status_code = status
    resp.set_cookie(
        REFRESH_COOKIE, tokens['refresh_token'],
        max_age=tokens['refresh_max_age'], path=REFRESH_COOKIE_PATH,
        httponly=True, secure=_cookie_secure(), samesite='Strict',
    )
    return resp


def _clear_refresh_cookie(resp):
    resp.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, httponly=True,
                       secure=_cookie_secure(), samesite='Strict')
    return resp


def _locked_response(seconds):
    minutes = max(1, (int(seconds) + 59) // 60)
    return rate_limited_response(
        seconds, code='LOGIN_LOCKED',
        message=f'Too many failed attempts. Try again in {minutes} minute{"s" if minutes != 1 else ""}.',
    )


def _refresh_claims_from_cookie():
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw or len(raw) > 4096:
        return None
    try:
        claims = decode_token(raw)
    except Exception:  # noqa: BLE001 - expired / bad signature / malformed
        return None
    return claims if claims.get('type') == 'refresh' else None


# ---------------------------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------------------------

@bp.route('/register', methods=['POST'])
def register():
    """Invite-only registration."""
    data = _json_body()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    username = str(data.get('username') or '').strip()
    email = str(data.get('email') or '').strip()
    password = data.get('password') if isinstance(data.get('password'), str) else ''
    invite_code = str(data.get('invite_code') or '').strip()[:64]
    ip = client_ip()

    if not all([username, email, password, invite_code]):
        return jsonify({'error': 'Username, email, password, and invite code are required'}), 400
    if len(username) > MAX_USERNAME or len(username) < 3 or any(c.isspace() for c in username):
        return jsonify({'error': 'Username must be 3-150 characters without spaces', 'code': 'USERNAME_INVALID'}), 400
    if len(email) > MAX_EMAIL or '@' not in email or any(c.isspace() for c in email):
        return jsonify({'error': 'Please enter a valid email address', 'code': 'EMAIL_INVALID'}), 400
    problem = check_password_policy(password, username, email)
    if problem:
        return jsonify({'error': problem[1], 'code': problem[0]}), 400

    throttle = get_throttle()
    invite_checks = [(RULE_INVITE_IP, ip)]
    wait = throttle.locked_for(invite_checks)
    if wait:
        return _locked_response(wait)

    # Invite first, before touching users (no user-existence oracle without a valid invite).
    role = claim_invite_code(invite_code)
    if role is None:
        throttle.fail(invite_checks)
        logger.warning("Invalid or exhausted invite signup attempt username=%s ip=%s",
                       safe_log_value(username, 40), safe_log_value(ip))
        log_auth_event('invite_invalid', username=username, ip=ip, user_agent=_ua(),
                       details={'code_prefix': invite_code[:7]})
        admin_alert = os.environ.get("MAIL_ADMIN_ALERT_EMAIL", "").strip()
        if admin_alert and is_smtp_configured():
            try:
                send_invalid_invite_alert(admin_alert, attempted_code=invite_code, username=username,
                                          email=email, remote_addr=ip)
            except Exception as e:  # noqa: BLE001
                logger.warning("Invalid-invite alert mail failed: %s", e)
        return jsonify({
            'error': ('Invalid invite code. This attempt has been recorded and will be '
                      'reported to the Administrator.'),
            'code': 'INVALID_INVITE',
        }), 403

    db = None
    try:
        password_hash = hash_password(password)
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s) LIMIT 1",
            (username, email),
        )
        if cursor.fetchone():
            release_invite_code(invite_code)
            # Counts like a wrong invite code, so an invite holder can't enumerate accounts for free
            throttle.fail(invite_checks)
            return jsonify({'error': 'Username or email is already registered', 'code': 'ALREADY_REGISTERED'}), 400
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, username, email, role, token_version
        """, (username, email, password_hash, role, datetime.utcnow()))
        user = dict(cursor.fetchone())
        db.commit()
    except Exception as e:
        if db is not None:
            db.rollback()
        release_invite_code(invite_code)
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            return jsonify({'error': 'Username or email is already registered', 'code': 'ALREADY_REGISTERED'}), 400
        logger.exception("Registration error")
        return jsonify({'error': 'Registration failed'}), 500
    finally:
        if db is not None:
            db.close()

    logger.info("New user registered: %s (id %s) role=%s", safe_log_value(username), user['id'], safe_log_value(role))
    log_auth_event('register', user_id=user['id'], username=username, ip=ip, user_agent=_ua(),
                   details={'role': role})
    if is_smtp_configured():
        try:
            send_welcome_registration(email, username)
        except Exception as e:  # noqa: BLE001
            logger.warning("Welcome mail failed: %s", e)

    tokens = issue_tokens(user)
    user.update({'display_timezone': None, 'player_avatar_url': None, 'active_character_id': None})
    return _token_response({'message': 'User registered successfully', 'user': _user_json(user)}, tokens, 201)


@bp.route('/login', methods=['POST'])
def login():
    """Generic errors, same work for unknown users, throttled per account+IP / account / IP."""
    data = _json_body()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    username = data.get('username')
    password = data.get('password')
    if not isinstance(username, str) or not isinstance(password, str) or not username.strip() or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    username = username.strip()[:MAX_USERNAME]
    password = password[:1024]
    ip = client_ip()

    throttle = get_throttle()
    checks = login_checks(username, ip, known_ip=is_known_ip(throttle.store, username, ip))
    wait = throttle.locked_for(checks)
    if wait:
        log_auth_event('login_blocked', username=username, ip=ip, user_agent=_ua(), details={'retry_after': wait})
        return _locked_response(wait)

    db = get_db()
    try:
        cursor = db.cursor()
        ensure_users_player_profile_columns(cursor)
        db.commit()
        cursor.execute("""
            SELECT id, username, email, password_hash, role, is_active, display_timezone,
                   player_avatar_url, active_character_id, token_version
            FROM users WHERE username = %s
        """, (username,))
        user = cursor.fetchone()

        if not verify_password(password, user['password_hash'] if user else None):
            locked = throttle.fail(checks)
            log_auth_event('login_failed', user_id=user['id'] if user else None, username=username,
                           ip=ip, user_agent=_ua(), details={'known_user': bool(user)})
            if locked:
                log_auth_event('lockout', user_id=user['id'] if user else None, username=username,
                               ip=ip, user_agent=_ua(), details={'seconds': locked})
            return jsonify({'error': GENERIC_LOGIN_ERROR, 'code': 'INVALID_CREDENTIALS'}), 401

        # Only someone holding the right password learns that the account is disabled.
        if not user['is_active']:
            log_auth_event('login_disabled', user_id=user['id'], username=username, ip=ip, user_agent=_ua())
            return jsonify({'error': 'This account is disabled. Contact an administrator.',
                            'code': 'ACCOUNT_DISABLED'}), 403

        user = dict(user)
        if needs_rehash(user['password_hash']):
            # srai.rehash tells the token_version trigger this is the same password: no logout.
            cursor.execute("SET LOCAL srai.rehash = 'on'")
            cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s",
                           (hash_password(password), user['id']))
        cursor.execute("UPDATE users SET last_login = %s WHERE id = %s RETURNING token_version",
                       (datetime.utcnow(), user['id']))
        user['token_version'] = cursor.fetchone()['token_version']
        db.commit()
    finally:
        db.close()

    throttle.clear(success_clears(username, ip))
    remember_ip(throttle.store, username, ip)
    log_auth_event('login', user_id=user['id'], username=user['username'], ip=ip, user_agent=_ua())
    logger.info("User logged in: %s (ID: %s)", user['username'], user['id'])
    tokens = issue_tokens(user)
    return _token_response({'message': 'Login successful', 'user': _user_json(user)}, tokens)


@bp.route('/refresh', methods=['POST'])
def refresh():
    """Rotate the refresh cookie. JSON requests only (cross-site forms can't send JSON without a
    CORS preflight) and the cookie is SameSite=Strict, so this can't be driven cross-site."""
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json', 'code': 'BAD_REQUEST'}), 400
    claims = _refresh_claims_from_cookie()
    if not claims:
        return _clear_refresh_cookie(jsonify({'error': 'Session expired. Please sign in again.',
                                              'code': 'REFRESH_INVALID'})), 401
    status, user = consume_refresh(claims)
    if status != 'ok':
        if status == 'reuse':
            logger.warning("Refresh token reuse detected for user %s (family %s)", claims.get('sub'), claims.get('fam'))
            log_auth_event('refresh_reuse', user_id=int(claims.get('sub') or 0) or None, ip=client_ip(),
                           user_agent=_ua(), details={'family': claims.get('fam')})
        return _clear_refresh_cookie(jsonify({'error': 'Session expired. Please sign in again.',
                                              'code': 'REFRESH_INVALID'})), 401

    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("""
            SELECT display_timezone, player_avatar_url, active_character_id FROM users WHERE id = %s
        """, (user['id'],))
        user.update(cursor.fetchone() or {})
    finally:
        db.close()
    tokens = issue_tokens(user, family_id=claims.get('fam'), auth_time=claims.get('auth_time'))
    return _token_response({'user': _user_json(user)}, tokens)


@bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Revoke this access token and this browser's refresh chain."""
    claims = get_jwt()
    uid = int(get_jwt_identity())
    revoke_jti(uid, claims.get('jti'), claims.get('exp'))
    rclaims = _refresh_claims_from_cookie()
    if rclaims and str(rclaims.get('sub')) == str(uid):
        revoke_family(rclaims.get('fam'))
    log_auth_event('logout', user_id=uid, ip=client_ip(), user_agent=_ua())
    return _clear_refresh_cookie(jsonify({'message': 'Logout successful'})), 200


@bp.route('/logout-all', methods=['POST'])
@jwt_required()
def logout_all():
    """End every session of the current user on every device."""
    uid = int(get_jwt_identity())
    bump_token_version(uid)
    log_auth_event('logout_all', user_id=uid, ip=client_ip(), user_agent=_ua())
    return _clear_refresh_cookie(jsonify({'message': 'Signed out everywhere'})), 200


@bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Needs the current password. Other sessions end (trigger bumps token_version); this one
    gets fresh tokens."""
    data = _json_body() or {}
    current = data.get('current_password')
    new = data.get('new_password')
    if not isinstance(current, str) or not isinstance(new, str) or not current or not new:
        return jsonify({'error': 'Current and new password are required'}), 400
    uid = int(get_jwt_identity())
    ip = client_ip()

    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("""
            SELECT id, username, email, password_hash, role, is_active, display_timezone,
                   player_avatar_url, active_character_id
            FROM users WHERE id = %s
        """, (uid,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'error': 'Authentication required.', 'code': 'AUTH_REQUIRED'}), 401
        throttle = get_throttle()
        checks = login_checks(user['username'], ip)
        wait = throttle.locked_for(checks)
        if wait:
            return _locked_response(wait)
        if not verify_password(current[:1024], user['password_hash']):
            throttle.fail(checks)
            log_auth_event('password_change_failed', user_id=uid, username=user['username'], ip=ip, user_agent=_ua())
            return jsonify({'error': 'Current password is incorrect.', 'code': 'INVALID_CREDENTIALS'}), 400
        problem = check_password_policy(new, user['username'], user['email'])
        if problem:
            return jsonify({'error': problem[1], 'code': problem[0]}), 400
        if verify_password(new, user['password_hash']):
            return jsonify({'error': 'The new password must differ from the current one.',
                            'code': 'PASSWORD_UNCHANGED'}), 400
        cursor.execute(
            "UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s RETURNING token_version",
            (hash_password(new), datetime.utcnow(), uid),
        )
        user = dict(user)
        user['token_version'] = cursor.fetchone()['token_version']
        cursor.execute("UPDATE auth_refresh_tokens SET revoked_at = NOW() WHERE user_id = %s AND revoked_at IS NULL",
                       (uid,))
        db.commit()
    finally:
        db.close()

    throttle.clear(success_clears(user['username'], ip))
    log_auth_event('password_changed', user_id=uid, username=user['username'], ip=ip, user_agent=_ua())
    tokens = issue_tokens(user)
    return _token_response({'message': 'Password changed', 'user': _user_json(user)}, tokens)


@bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile"""
    current_user_id = int(get_jwt_identity())
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute("""
            SELECT id, username, email, role, created_at, last_login, display_timezone
            FROM users WHERE id = %s
        """, (current_user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        cursor.execute("SELECT COUNT(*) AS campaign_count FROM campaigns WHERE created_by = %s", (current_user_id,))
        campaign_count = cursor.fetchone()['campaign_count']
        cursor.execute("SELECT COUNT(*) AS character_count FROM characters WHERE user_id = %s", (current_user_id,))
        character_count = cursor.fetchone()['character_count']
        return jsonify({
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role'],
                'created_at': user['created_at'],
                'last_login': user['last_login'],
                'display_timezone': user['display_timezone'],
            },
            'statistics': {
                'campaigns_created': campaign_count,
                'characters_owned': character_count
            }
        }), 200
    finally:
        db.close()
