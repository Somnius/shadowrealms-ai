"""Phase 5 auth hardening: password policy, bcrypt, lockout, token revocation, client IP, errors."""

import time

import bcrypt
import pytest
from flask import Flask, jsonify

from services import auth_security as sec
from services.auth_security import (
    RULE_ACCOUNT,
    RULE_ACCOUNT_IP,
    FailoverStore,
    MemoryStore,
    Throttle,
    check_password_policy,
    lock_seconds,
    login_checks,
    success_clears,
    token_revoked,
)

# --------------------------------------------------------------------------- password policy


def test_policy_accepts_a_reasonable_passphrase():
    assert check_password_policy("violet crow at midnight", "lef", "lef@example.org") is None


@pytest.mark.parametrize(
    "pw,code",
    [
        ("", "PASSWORD_REQUIRED"),
        ("short1!", "PASSWORD_TOO_SHORT"),
        ("qwertyuiop12", "PASSWORD_COMMON"),
        ("password1234", "PASSWORD_COMMON"),
        ("aaaaaaaaaaaaaaa", "PASSWORD_TOO_SIMPLE"),
        ("MyShadowRealms2026", "PASSWORD_TOO_SIMPLE"),
        ("x" * 40 + "y" * 40, "PASSWORD_TOO_LONG"),
        ("αβγδεζηθικλμνξοπρστυφχψω" + "αβγδεζηθικλμν", "PASSWORD_TOO_LONG"),  # 37 Greek chars = 74 bytes
    ],
)
def test_policy_rejections(pw, code):
    assert check_password_policy(pw, "someone", "someone@example.org")[0] == code


def test_policy_rejects_username_or_email_local_part():
    assert check_password_policy("theNightLefWalks", "lef", "x@y.z")[0] == "PASSWORD_CONTAINS_USERNAME"
    assert check_password_policy("vampire-bob.smith-99", "u1", "bob.smith@example.org")[0] == "PASSWORD_CONTAINS_USERNAME"


def test_policy_allows_64_ascii_characters():
    assert check_password_policy("Tz9!kq" * 10 + "abcd", "u", "e@x.y") is None  # 64 chars


def test_min_length_never_below_10(monkeypatch):
    monkeypatch.setenv("PASSWORD_MIN_LENGTH", "4")
    assert sec.password_min_length() == 10
    monkeypatch.setenv("PASSWORD_MIN_LENGTH", "16")
    assert check_password_policy("violet crow nite", "u", "e@x.y") is None
    assert check_password_policy("violet crow at", "u", "e@x.y")[0] == "PASSWORD_TOO_SHORT"


# --------------------------------------------------------------------------- bcrypt


def test_hash_uses_cost_12_and_never_less(monkeypatch):
    monkeypatch.setenv("BCRYPT_ROUNDS", "8")
    assert sec.bcrypt_rounds() == 12
    monkeypatch.setenv("BCRYPT_ROUNDS", "12")
    h = sec.hash_password("violet crow at midnight")
    assert sec.hash_cost(h) == 12
    assert sec.verify_password("violet crow at midnight", h)
    assert not sec.verify_password("violet crow at noon", h)
    assert not sec.needs_rehash(h)


def test_low_cost_hash_needs_rehash():
    old = bcrypt.hashpw(b"legacy password", bcrypt.gensalt(4)).decode()
    assert sec.needs_rehash(old)
    assert sec.verify_password("legacy password", old)
    assert sec.needs_rehash("not-a-bcrypt-hash")


def test_verify_never_raises_on_long_or_missing_input(monkeypatch):
    monkeypatch.setattr(sec, "_dummy_hash", bcrypt.hashpw(b"x", bcrypt.gensalt(4)))
    h = bcrypt.hashpw(b"a" * 72, bcrypt.gensalt(4)).decode()
    assert sec.verify_password("a" * 100, h)  # legacy bcrypt truncated at 72 bytes
    assert sec.verify_password("whatever", None) is False  # unknown user: dummy check, False
    assert sec.verify_password("whatever", "$2b$12$garbage") is False
    assert sec.verify_password(None, h) is False


# --------------------------------------------------------------------------- lockout


def test_lock_seconds_backoff_is_capped():
    r = RULE_ACCOUNT_IP
    assert [lock_seconds(n, r) for n in range(1, 5)] == [0, 0, 0, 0]
    assert lock_seconds(5, r) == 30
    assert lock_seconds(6, r) == 60
    assert lock_seconds(7, r) == 120
    assert lock_seconds(50, r) == r.cap_seconds
    assert lock_seconds(10_000, r) == r.cap_seconds


def test_throttle_locks_account_ip_after_five_and_success_clears_it():
    t = Throttle(MemoryStore())
    checks = login_checks("Alice", "1.2.3.4")
    for _ in range(4):
        assert t.fail(checks) == 0
    assert t.locked_for(checks) == 0
    assert t.fail(checks) == 30
    assert 0 < t.locked_for(checks) <= 30
    # same account from another IP is not locked by the per-IP+account rule
    assert t.locked_for(login_checks("alice", "5.6.7.8")) == 0
    t.clear(success_clears("ALICE", "1.2.3.4"))  # username is case-insensitive
    assert t.locked_for(checks) == 0


def test_account_wide_lock_after_distributed_failures_is_time_limited(monkeypatch):
    store = MemoryStore()
    t = Throttle(store)
    for i in range(RULE_ACCOUNT.threshold):
        t.fail(login_checks("bob", f"10.0.{i}.1"))
    wait = t.locked_for(login_checks("bob", "9.9.9.9"))
    assert 0 < wait <= RULE_ACCOUNT.cap_seconds
    now = time.time()
    monkeypatch.setattr(sec.time, "time", lambda: now + RULE_ACCOUNT.cap_seconds + 1)
    assert t.locked_for(login_checks("bob", "9.9.9.9")) == 0


def test_unknown_usernames_are_throttled_the_same_way():
    t = Throttle(MemoryStore())
    for _ in range(5):
        t.fail(login_checks("no-such-user", "1.1.1.1"))
    assert t.locked_for(login_checks("no-such-user", "1.1.1.1")) > 0


def test_unlock_account_and_ip():
    t = Throttle(MemoryStore())
    for _ in range(40):
        t.fail(login_checks("carol", "7.7.7.7"))
    assert t.locked_for(login_checks("carol", "7.7.7.7")) > 0
    assert t.unlock_account("Carol") > 0
    assert t.locked_for([(RULE_ACCOUNT, sec.account_key("carol"))]) == 0
    assert t.locked_for(login_checks("dave", "7.7.7.7")) > 0  # IP-wide lock still on
    assert t.unlock_ip("7.7.7.7") > 0
    assert t.locked_for(login_checks("dave", "7.7.7.7")) == 0


def test_failover_store_uses_memory_when_redis_fails():
    class Broken:
        def __getattr__(self, name):
            def boom(*a, **k):
                raise ConnectionError("redis down")
            return boom

    t = Throttle(FailoverStore(Broken(), MemoryStore()))
    for _ in range(5):
        t.fail(login_checks("erin", "2.2.2.2"))
    assert t.locked_for(login_checks("erin", "2.2.2.2")) > 0


# --------------------------------------------------------------------------- token revocation


@pytest.mark.parametrize(
    "claims,row,jti_revoked,expected",
    [
        ({"tv": 3}, {"token_version": 3, "is_active": True}, False, (False, "")),
        ({"tv": 3}, {"token_version": 4, "is_active": True}, False, (True, "version")),
        ({"tv": 3}, {"token_version": 3, "is_active": False}, False, (True, "inactive")),
        ({"tv": 3}, None, False, (True, "no_user")),
        ({"tv": 3}, {"token_version": 3, "is_active": True}, True, (True, "jti_revoked")),
        ({}, {"token_version": 0, "is_active": True}, False, (True, "no_version")),
        ({"tv": True}, {"token_version": 1, "is_active": True}, False, (True, "no_version")),
    ],
)
def test_token_revoked(claims, row, jti_revoked, expected):
    assert token_revoked(claims, row, jti_revoked) == expected


# --------------------------------------------------------------------------- client IP / keys / errors


def _app(hops=1):
    from services import app_security

    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="k" * 40, SECRET_KEY="s" * 40)
    from flask_jwt_extended import JWTManager

    JWTManager(app)
    app_security.install_proxy_fix(app, hops)
    app_security.init_error_handlers(app)

    @app.route("/ip")
    def ip():
        return jsonify(ip=app_security.client_ip(), key=app_security.user_or_ip_key())

    @app.route("/boom")
    def boom():
        raise RuntimeError("password=hunter2 at /app/secret.py line 3")

    return app


def test_client_ip_trusts_exactly_one_hop():
    c = _app(1).test_client()
    env = {"REMOTE_ADDR": "127.0.0.1"}
    r = c.get("/ip", headers={"X-Forwarded-For": "203.0.113.9"}, environ_base=env).get_json()
    assert r == {"ip": "203.0.113.9", "key": "ip:203.0.113.9"}
    # a client-supplied value in front is ignored; the hop nginx added (rightmost) wins
    r = c.get("/ip", headers={"X-Forwarded-For": "6.6.6.6, 203.0.113.9"}, environ_base=env).get_json()
    assert r["ip"] == "203.0.113.9"
    r = c.get("/ip", environ_base=env).get_json()
    assert r["ip"] == "127.0.0.1"


def test_rate_limit_key_is_user_for_a_valid_token_else_ip():
    app = _app(1)
    from flask_jwt_extended import create_access_token

    with app.app_context():
        tok = create_access_token(identity="42")
    c = app.test_client()
    env = {"REMOTE_ADDR": "127.0.0.1"}
    r = c.get("/ip", headers={"Authorization": f"Bearer {tok}", "X-Forwarded-For": "198.51.100.7"},
              environ_base=env).get_json()
    assert r["key"] == "u:42"
    r = c.get("/ip", headers={"Authorization": "Bearer forged.token.here", "X-Forwarded-For": "198.51.100.7"},
              environ_base=env).get_json()
    assert r["key"] == "ip:198.51.100.7"


def test_unhandled_errors_never_leak_exception_text():
    r = _app().test_client().get("/boom")
    assert r.status_code == 500
    body = r.get_data(as_text=True)
    assert "hunter2" not in body and "secret.py" not in body and "Traceback" not in body
    assert r.get_json() == {"error": "Internal server error", "code": "INTERNAL"}


def test_http_errors_are_json():
    r = _app().test_client().get("/nope")
    assert r.status_code == 404 and r.get_json()["code"] == "HTTP_404"


def test_rate_limit_429_is_json_with_retry_after(monkeypatch):
    from services import app_security

    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "memory://")
    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="k" * 40)
    from flask_jwt_extended import JWTManager

    JWTManager(app)
    app_security.init_error_handlers(app)
    app_security.init_limiter(app)

    @app.route("/api/auth/login", methods=["POST"])
    def login():
        return jsonify(ok=True)

    monkeypatch.setattr(app_security, "ROUTE_LIMITS", {"login": ("2 per minute", app_security.ip_key)})
    app_security.apply_route_limits(app)
    c = app.test_client()
    assert c.post("/api/auth/login").status_code == 200
    assert c.post("/api/auth/login").status_code == 200
    r = c.post("/api/auth/login")
    assert r.status_code == 429
    assert r.get_json()["code"] == "RATE_LIMITED"
    assert int(r.headers["Retry-After"]) > 0


def test_security_headers_on_api_responses():
    from services import app_security

    app = Flask(__name__)
    app.after_request(app_security.security_headers)

    @app.route("/api/auth/x")
    def x():
        return jsonify(ok=True)

    r = app.test_client().get("/api/auth/x")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Cache-Control"] == "no-store"
    assert r.headers["Referrer-Policy"] == "same-origin"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]


def test_known_ip_is_not_locked_out_by_distributed_guessing():
    """Pentest M1: anyone who knows a username could keep its owner locked out."""
    from services.auth_security import (
        MemoryStore, Throttle, login_checks, remember_ip, is_known_ip,
    )
    store = MemoryStore()
    t = Throttle(store)
    remember_ip(store, "owner", "10.0.0.50")          # owner signed in from home before
    for i in range(40):                                # attacker fails from 40 addresses
        t.fail(login_checks("owner", f"198.51.100.{i}", known_ip=is_known_ip(store, "owner", f"198.51.100.{i}")))
    # a new address is still locked by the account-wide rule
    assert t.locked_for(login_checks("owner", "203.0.113.7", known_ip=is_known_ip(store, "owner", "203.0.113.7"))) > 0
    # the owner's known address is not
    assert is_known_ip(store, "owner", "10.0.0.50")
    assert t.locked_for(login_checks("owner", "10.0.0.50", known_ip=True)) == 0
    # but a known address still has its own account+IP limit
    for _ in range(5):
        t.fail(login_checks("owner", "10.0.0.50", known_ip=True))
    assert t.locked_for(login_checks("owner", "10.0.0.50", known_ip=True)) > 0
