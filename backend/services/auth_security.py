"""
Login-screen security building blocks (phase 5). Pure logic, no Flask or database imports, so
the unit tests run without the app stack. See docs/SECURITY_MODEL.md for the model as a whole.

- Password policy: 12+ characters (PASSWORD_MIN_LENGTH, never below 10), at most 72 UTF-8 bytes
  (bcrypt's input limit; that is still 64+ ASCII characters, as OWASP asks), not a well-known
  password, not the username.
- bcrypt hashing at cost BCRYPT_ROUNDS (default 12, never below 12), with transparent rehash
  on login when a stored hash has a lower cost.
- Failed-login throttling: per account+IP, per account and per IP failure counters with
  exponential, time-limited locks (never permanent, so nobody can lock a user out for good).
- Token revocation decision for the JWT blocklist callback.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------------------------
# Password policy
# ---------------------------------------------------------------------------------------------

BCRYPT_MAX_BYTES = 72
_COMMON_FILE = os.path.join(os.path.dirname(__file__), "common_passwords.txt")
_common_passwords: Optional[frozenset] = None


def password_min_length() -> int:
    try:
        n = int(os.environ.get("PASSWORD_MIN_LENGTH", "12"))
    except ValueError:
        n = 12
    return max(10, n)


def _load_common() -> frozenset:
    global _common_passwords
    if _common_passwords is None:
        words = set()
        try:
            with open(_COMMON_FILE, encoding="utf-8") as f:
                for line in f:
                    w = line.strip()
                    if w and not w.startswith("#"):
                        words.add(w.lower())
        except OSError as e:  # pragma: no cover - file ships with the code
            logger.error("common_passwords.txt missing: %s", e)
        _common_passwords = frozenset(words)
    return _common_passwords


def is_common_password(password: str) -> bool:
    return (password or "").strip().lower() in _load_common()


def check_password_policy(password, username: str = "", email: str = "") -> Optional[Tuple[str, str]]:
    """None when acceptable, else (code, English message). Codes are stable for the frontend."""
    if not isinstance(password, str) or not password:
        return "PASSWORD_REQUIRED", "Password is required."
    min_len = password_min_length()
    if len(password) < min_len:
        return "PASSWORD_TOO_SHORT", f"Password must be at least {min_len} characters."
    if len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        return (
            "PASSWORD_TOO_LONG",
            "Password is too long (at most 72 bytes: 72 Latin or about 36 Greek characters).",
        )
    low = password.lower()
    if len(set(password)) <= 2:
        return "PASSWORD_TOO_SIMPLE", "Password is too simple (repeated characters)."
    if is_common_password(password):
        return "PASSWORD_COMMON", "This password is too common. Choose another one."
    if "shadowrealm" in low:
        return "PASSWORD_TOO_SIMPLE", "Password must not contain the site name."
    for ident in (username or "", (email or "").split("@")[0]):
        ident = ident.strip().lower()
        if len(ident) >= 3 and ident in low:
            return "PASSWORD_CONTAINS_USERNAME", "Password must not contain your username or email."
    return None


# ---------------------------------------------------------------------------------------------
# bcrypt
# ---------------------------------------------------------------------------------------------

def bcrypt_rounds() -> int:
    try:
        n = int(os.environ.get("BCRYPT_ROUNDS", "12"))
    except ValueError:
        n = 12
    return min(max(12, n), 16)


def _pw_bytes(password: str) -> bytes:
    # bcrypt >= 5 raises on > 72 bytes; older bcrypt silently truncated. New passwords are
    # capped at 72 bytes by the policy; truncating here keeps legacy hashes verifiable.
    return (password or "").encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    import bcrypt

    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt(bcrypt_rounds())).decode("utf-8")


_HASH_RE = re.compile(r"^\$2[abxy]?\$(\d\d)\$")


def hash_cost(stored_hash: str) -> Optional[int]:
    m = _HASH_RE.match(stored_hash or "")
    return int(m.group(1)) if m else None


def needs_rehash(stored_hash: str) -> bool:
    cost = hash_cost(stored_hash)
    return cost is None or cost < bcrypt_rounds()


_dummy_hash: Optional[bytes] = None
_dummy_lock = threading.Lock()


def _get_dummy_hash() -> bytes:
    global _dummy_hash
    with _dummy_lock:
        if _dummy_hash is None:
            import bcrypt

            _dummy_hash = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt(bcrypt_rounds()))
        return _dummy_hash


def verify_password(password: str, stored_hash: Optional[str]) -> bool:
    """Constant-ish time: with no stored hash (unknown user) a dummy hash is checked instead."""
    import bcrypt

    pw = _pw_bytes(password if isinstance(password, str) else "")
    if not stored_hash:
        bcrypt.checkpw(pw, _get_dummy_hash())
        return False
    try:
        return bcrypt.checkpw(pw, stored_hash.encode("utf-8"))
    except ValueError:  # malformed stored hash
        bcrypt.checkpw(pw, _get_dummy_hash())
        return False


# ---------------------------------------------------------------------------------------------
# Failed-attempt throttling (lockout with exponential backoff)
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ThrottleRule:
    name: str
    threshold: int       # failures before the first lock
    base_seconds: int    # first lock length; doubles per further failure
    cap_seconds: int     # longest lock (time-limited; never permanent)
    window_seconds: int  # failures are forgotten after this long without a new one


# Per account+IP: the normal "someone mistyped / someone guesses from one place" case.
RULE_ACCOUNT_IP = ThrottleRule("aip", threshold=5, base_seconds=30, cap_seconds=15 * 60, window_seconds=3600)
# Per account from anywhere: slows distributed guessing; capped at 15 min so it can't be a lasting DoS.
RULE_ACCOUNT = ThrottleRule("acct", threshold=20, base_seconds=5 * 60, cap_seconds=15 * 60, window_seconds=3600)
# Per IP over all accounts: password spraying / credential stuffing from one address.
RULE_IP = ThrottleRule("ip", threshold=30, base_seconds=5 * 60, cap_seconds=30 * 60, window_seconds=3600)
# Wrong invite codes per IP (registration).
RULE_INVITE_IP = ThrottleRule("inv", threshold=5, base_seconds=10 * 60, cap_seconds=60 * 60, window_seconds=6 * 3600)


def lock_seconds(failures: int, rule: ThrottleRule) -> int:
    """Lock length after `failures` consecutive failures (0 = not locked)."""
    if failures < rule.threshold:
        return 0
    exp = min(failures - rule.threshold, 20)
    return int(min(rule.cap_seconds, rule.base_seconds * (2 ** exp)))


def account_key(username: str) -> str:
    """Stable, bounded key part for a submitted username (case-insensitive, exists or not)."""
    norm = (username or "").strip().lower()[:256]
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32]


class MemoryStore:
    """In-process fallback when Redis is unreachable (per worker; weaker, but never fails open)."""

    def __init__(self):
        self._d: Dict[str, Tuple[int, float]] = {}
        self._lock = threading.Lock()

    def _get(self, key):
        v = self._d.get(key)
        if v is None:
            return None
        if v[1] <= time.time():
            self._d.pop(key, None)
            return None
        return v

    def incr(self, key: str, ttl: int) -> int:
        with self._lock:
            v = self._get(key)
            n = (v[0] if v else 0) + 1
            self._d[key] = (n, time.time() + ttl)
            return n

    def set(self, key: str, value: int, ttl: int) -> None:
        with self._lock:
            self._d[key] = (int(value), time.time() + ttl)

    def ttl(self, key: str) -> int:
        with self._lock:
            v = self._get(key)
            return max(0, int(v[1] - time.time() + 0.999)) if v else 0

    def delete(self, *keys: str) -> None:
        with self._lock:
            for k in keys:
                self._d.pop(k, None)

    def delete_pattern(self, pattern: str) -> int:
        import fnmatch

        with self._lock:
            hits = [k for k in self._d if fnmatch.fnmatchcase(k, pattern)]
            for k in hits:
                self._d.pop(k, None)
            return len(hits)


class RedisStore:
    def __init__(self, client):
        self.r = client

    def incr(self, key: str, ttl: int) -> int:
        p = self.r.pipeline()
        p.incr(key)
        p.expire(key, ttl)
        n, _ = p.execute()
        return int(n)

    def set(self, key: str, value: int, ttl: int) -> None:
        self.r.set(key, int(value), ex=max(1, int(ttl)))

    def ttl(self, key: str) -> int:
        t = self.r.ttl(key)
        return int(t) if t and t > 0 else 0

    def delete(self, *keys: str) -> None:
        if keys:
            self.r.delete(*keys)

    def delete_pattern(self, pattern: str) -> int:
        n = 0
        for k in self.r.scan_iter(match=pattern, count=200):
            self.r.delete(k)
            n += 1
        return n


class FailoverStore:
    """Redis first; on any Redis error use the in-memory store (logged once per minute)."""

    def __init__(self, primary, fallback=None):
        self.primary = primary
        self.fallback = fallback or MemoryStore()
        self._last_warn = 0.0

    def _call(self, name, *a):
        if self.primary is not None:
            try:
                return getattr(self.primary, name)(*a)
            except Exception as e:  # noqa: BLE001 - redis down: degrade, never 500 the login
                if time.time() - self._last_warn > 60:
                    self._last_warn = time.time()
                    logger.warning("Auth throttle store unavailable, using in-memory fallback: %s", e)
        return getattr(self.fallback, name)(*a)

    def incr(self, key, ttl):
        return self._call("incr", key, ttl)

    def set(self, key, value, ttl):
        return self._call("set", key, value, ttl)

    def ttl(self, key):
        return self._call("ttl", key)

    def delete(self, *keys):
        return self._call("delete", *keys)

    def delete_pattern(self, pattern):
        return self._call("delete_pattern", pattern)


PREFIX = "srai:auth:"


class Throttle:
    """Failure counting + locks on top of a store (Redis in production, MemoryStore in tests)."""

    def __init__(self, store):
        self.store = store

    @staticmethod
    def _keys(rule: ThrottleRule, subject: str) -> Tuple[str, str]:
        return f"{PREFIX}fail:{rule.name}:{subject}", f"{PREFIX}lock:{rule.name}:{subject}"

    def locked_for(self, checks: Iterable[Tuple[ThrottleRule, str]]) -> int:
        """Seconds until every given (rule, subject) is unlocked; 0 when none is locked."""
        return max([self.store.ttl(self._keys(r, s)[1]) for r, s in checks] or [0])

    def fail(self, checks: Iterable[Tuple[ThrottleRule, str]]) -> int:
        """Count one failure for each (rule, subject); returns the longest lock that started."""
        longest = 0
        for rule, subject in checks:
            fkey, lkey = self._keys(rule, subject)
            n = self.store.incr(fkey, rule.window_seconds)
            secs = lock_seconds(n, rule)
            if secs:
                self.store.set(lkey, n, secs)
                longest = max(longest, secs)
        return longest

    def clear(self, checks: Iterable[Tuple[ThrottleRule, str]]) -> None:
        for rule, subject in checks:
            self.store.delete(*self._keys(rule, subject))

    def unlock_account(self, username: str) -> int:
        acct = account_key(username)
        return (self.store.delete_pattern(f"{PREFIX}*:aip:{acct}|*")
                + self.store.delete_pattern(f"{PREFIX}*:acct:{acct}"))

    def unlock_ip(self, ip: str) -> int:
        ip = (ip or "").strip()
        return (self.store.delete_pattern(f"{PREFIX}*:ip:{ip}")
                + self.store.delete_pattern(f"{PREFIX}*:inv:{ip}")
                + self.store.delete_pattern(f"{PREFIX}*:aip:*|{ip}"))


def login_checks(username: str, ip: str):
    acct = account_key(username)
    return [(RULE_ACCOUNT_IP, f"{acct}|{ip}"), (RULE_ACCOUNT, acct), (RULE_IP, ip)]


def success_clears(username: str, ip: str):
    """On a good password only the account+IP counter resets: an attacker who also fails from
    elsewhere can't reset the account-wide or IP-wide counters by logging into his own account."""
    return [(RULE_ACCOUNT_IP, f"{account_key(username)}|{ip}")]


# ---------------------------------------------------------------------------------------------
# Token revocation decision
# ---------------------------------------------------------------------------------------------

def token_revoked(claims: dict, user_row: Optional[dict], jti_revoked: bool) -> Tuple[bool, str]:
    """
    (revoked, reason) for a decoded JWT given the user's row ({token_version, is_active} or None)
    and whether its jti is on the blocklist. Tokens without a `tv` claim predate phase 5.
    """
    if jti_revoked:
        return True, "jti_revoked"
    if not user_row:
        return True, "no_user"
    if not user_row.get("is_active"):
        return True, "inactive"
    tv = claims.get("tv")
    if not isinstance(tv, int) or isinstance(tv, bool):
        return True, "no_version"
    if tv != int(user_row.get("token_version") or 0):
        return True, "version"
    return False, ""
