# Security model (v0.9 phase 5)

How sign-in, sessions, limits and the production server work since the site became publicly
reachable at https://srai.srv-box.com. Testing practices are in
[SECURITY_AND_TESTING.md](SECURITY_AND_TESTING.md).

Sources used for the design: OWASP Authentication, Session Management, Password Storage and
JSON Web Token cheat sheets, OWASP ASVS v4 chapters 2 and 3, NIST SP 800-63B, the
Flask-JWT-Extended docs (blocklist and token revoking), the Flask-Limiter docs (deploying behind a
proxy), and gunicorn's settings reference.

## Request path and proxy trust

```
browser --https--> DietPi nginx (10.0.0.10, TLS, HSTS)  --http--> nginx on this host (:80)
        --http--> gunicorn 127.0.0.1:5000 (backend)
```

- The DietPi proxy appends the client address to `X-Forwarded-For`. A client can put anything in
  front of that, so only the **rightmost** entry the DietPi added is trustworthy.
- The local nginx (`nginx/nginx.conf`) uses the realip module: `set_real_ip_from 10.0.0.10`,
  `real_ip_header X-Forwarded-For`, `real_ip_recursive on`. For public traffic `$remote_addr`
  becomes the real client; LAN clients that connect directly keep their own address.
  nginx then **overwrites** `X-Forwarded-For` with that one address (no appending) and sets
  `X-Forwarded-Proto` to `https` when the DietPi says so.
- The backend trusts exactly **one** hop (`TRUSTED_PROXY_HOPS=1`, werkzeug `ProxyFix(x_for=1,
  x_proto=1)`), so `request.remote_addr` is the real client for rate limits, lockouts and the
  audit log.
- gunicorn binds to **127.0.0.1** only. Anything that could reach the backend port directly could
  send its own `X-Forwarded-For`. If the DietPi's address changes, update `set_real_ip_from`.

## Passwords

- Policy (`services/auth_security.py`, used by register, change-password and admin reset):
  at least 12 characters (`PASSWORD_MIN_LENGTH`, never below 10), at most 72 UTF-8 bytes
  (bcrypt's input limit: 72 Latin characters, about 36 Greek ones), not a known common password
  (`services/common_passwords.txt`, 2,300 entries of 10+ characters from SecLists), not the
  username or the email's local part, not the site name, not one repeated character.
  No composition rules, as NIST 800-63B advises.
- Storage: bcrypt cost 12 (`BCRYPT_ROUNDS`, never below 12; about 0.18 s per hash on this
  machine). A hash with a lower cost is rehashed transparently at the next successful login.
  bcrypt 5 raises on inputs over 72 bytes; the code truncates to 72 bytes when verifying (what
  older bcrypt versions did silently), so login never fails with a server error.
- No pre-hashing (OWASP warns about null bytes and password shucking).
- The welcome email no longer contains the password.

## Sign-in, user enumeration, brute force

- `POST /api/auth/login` answers every bad username or password with the same
  `401 {"error": "Invalid username or password.", "code": "INVALID_CREDENTIALS"}`. An unknown
  username still runs one bcrypt check against a dummy hash, so timing doesn't reveal which
  usernames exist. Only someone who sent the right password learns that an account is disabled
  (`403 ACCOUNT_DISABLED`).
- Failed attempts are counted in Redis (`srai:auth:*`, in-memory fallback per worker if Redis is
  down) under three rules, all time-limited, none permanent:

  | Rule | Counts failures of | First lock after | Lock length | Longest lock |
  |---|---|---|---|---|
  | account + IP | one username from one address | 5 | 30 s, doubling per further failure | 15 min |
  | account | one username from anywhere | 20 | 5 min, doubling | 15 min |
  | IP | any username from one address | 30 | 5 min, doubling | 30 min |
  | invite | wrong invite codes from one address | 5 | 10 min, doubling | 60 min |

  Counters are forgotten after an hour without a new failure (6 h for invites). Unknown usernames
  are counted the same way. A good password clears only the account+IP counter, so an attacker
  can't reset the wider counters by logging into an account of his own. While locked, the
  answer is `429 {"code": "LOGIN_LOCKED", "retry_after": <s>}` with a `Retry-After` header and
  the password is not checked at all. The account-wide rule is the trade-off OWASP describes:
  it slows distributed guessing, and someone hammering a username can keep that user out for at
  most 15 minutes at a time (unlock below).
- Invite codes: checked and claimed atomically (file lock on `backend/invites.json`, safe across
  gunicorn workers); a registration that fails afterwards gives the slot back. Wrong codes count
  towards the invite rule above and are logged; the admin alert email is sent as before.

### Unlocking an account or address

- Admin API: `POST /api/admin/auth/unlock` with `{"username": "..."}` and/or `{"ip": "..."}`
  (logged in the moderation log as `auth_unlock`).
- Shell: `docker exec shadowrealms-ai-redis-1 redis-cli --scan --pattern 'srai:auth:*'` lists the
  keys; delete them with `redis-cli del <key>` (all of them: `... --scan --pattern 'srai:auth:*' |
  xargs -r docker exec -i shadowrealms-ai-redis-1 redis-cli del`). Usernames appear as a SHA-256
  prefix of the lowercased name, IPs in clear.
- Every lock expires by itself within the "longest lock" above.

## Sessions and tokens

- **Access token**: a JWT (HS256, `JWT_SECRET_KEY`, at least 32 characters or the server refuses
  to start in production) returned in the JSON body and sent as `Authorization: Bearer`.
  Lifetime `JWT_ACCESS_TOKEN_MINUTES`: 30 by default in code; docker-compose still defaults to **360**;
  the frontend now refreshes tokens (see "Frontend changes"), so it can be set to 30.
- **Refresh token**: only in an `HttpOnly`, `SameSite=Strict` cookie `srai_refresh` with
  `Path=/api/auth` (`Secure` when the request came over https; `AUTH_COOKIE_SECURE=true|false`
  forces it). JavaScript can't read it, so an XSS can't steal a long-lived credential.
  Lifetime `JWT_REFRESH_TOKEN_DAYS` (14), and a login can't be stretched past
  `JWT_SESSION_MAX_DAYS` (30) of rotations.
- **Rotation with reuse detection**: `POST /api/auth/refresh` (JSON request, cookie) marks the
  presented refresh token used and returns a new access token plus a new cookie. Presenting an
  already used refresh token again means it was copied: the whole chain of that login is revoked
  and logged as `refresh_reuse`. The endpoint needs `Content-Type: application/json`, which a
  cross-site form can't send without a CORS preflight; with `SameSite=Strict` this is CSRF-safe.
- **Revocation** (checked on every authenticated request through Flask-JWT-Extended's
  `token_in_blocklist_loader`, one indexed query over a small per-process connection pool):
  - every token carries `tv` = `users.token_version` at issue time;
  - a PostgreSQL trigger (`users_bump_token_version`) bumps `token_version` whenever the
    password hash or role changes or the account is deactivated or banned, from **any** code
    path (admin ban, admin reset-password, `PUT /api/users/<id>` with `is_active=false`,
    `DELETE /api/users/<id>`, scripts). A login-time rehash sets `srai.rehash` so it doesn't;
  - `POST /api/auth/logout` puts the access token's `jti` in `auth_revoked_tokens` (until it
    would have expired) and revokes the refresh chain from the cookie;
  - `POST /api/auth/logout-all` bumps `token_version` (every device);
  - `POST /api/auth/change-password` (`current_password`, `new_password`) ends all other
    sessions and returns fresh tokens for this one;
  - inactive or deleted users are rejected even with an otherwise valid token;
  - tokens issued before phase 5 have no `tv` and are rejected once (users sign in again).
  - If the database is unreachable during the check the API answers `503 UNAVAILABLE` (not 401),
    so a short outage doesn't log everybody out.
- JWT error bodies carry stable codes: `TOKEN_EXPIRED`, `TOKEN_REVOKED`, `TOKEN_INVALID`,
  `AUTH_REQUIRED` (all 401).
- The SSE stream (`/api/campaigns/<id>/events?ticket=`) uses a 60 s ticket that can only be
  obtained with a valid (non-revoked) access token. Tickets are single-use: each carries a random
  nonce that the stream claims in Redis (`srai:sse-ticket:<nonce>`, 120 s TTL; per-worker memory
  if Redis is down), so a ticket copied from a URL or log can't open a second stream (401).

## Rate limits

Flask-Limiter, Redis storage (`redis://localhost:6379`, keys `srai:rl*`), fixed windows, in-memory
fallback per worker if Redis is down (`swallow_errors`). All limits are in
`services/app_security.py` (`ROUTE_LIMITS`). "user" means the user id from a validly signed token,
else the client IP.

| Endpoint | Limit | Key |
|---|---|---|
| `POST /api/auth/login` | 10/min, 60/h | IP |
| `POST /api/auth/register` | 5/min, 20/h | IP |
| `POST /api/auth/refresh` | 30/min | IP |
| `POST /api/auth/change-password` | 5 per 15 min | user |
| `POST /api/auth/logout`, `logout-all` | 30/min, 10/min | user |
| `POST /api/campaigns/<id>/events/ticket` | 30/min | user |
| `POST /api/campaigns/<id>/locations/<id>` (post a message) | 60/min, 1000/h | user |
| every `POST /api/ai/*` and `POST .../roll/ai` | 12/min, 300/h | user |
| other dice `POST`s | 60/min | user |
| everything else | 600/min | user |
| `/health`, the SSE stream | none | |

A breach returns `429 {"error": "...", "code": "RATE_LIMITED", "retry_after": <s>}` with
`Retry-After` and `X-RateLimit-*` headers. `RATELIMIT_ENABLED=false` switches limits off (tests).

## Headers, CORS, errors

- Every response: `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`,
  `Cross-Origin-Resource-Policy: same-origin`. `/api/*` and `/health`: `Cache-Control: no-store`
  (unless a route sets its own, like the SSE stream), and JSON responses get
  `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`. `/api/auth/*` always
  gets `no-store` + `Pragma: no-cache`. HSTS and the page-level headers come from the DietPi proxy.
- CORS: none by default (the browser talks to the same origin through nginx). `CORS_ORIGINS`
  (comma-separated) enables it for those origins only, without credentials. `*` is ignored.
- Errors: a catch-all handler logs the traceback and answers `500 {"error": "Internal server
  error", "code": "INTERNAL"}`; exception text never reaches the client. HTTP errors are JSON
  (`{"error": "Not Found", "code": "HTTP_404"}`). Several routes that returned `str(e)` (rule
  books, AI health, re-embed, health check, README) now return fixed messages.
- `MAX_CONTENT_LENGTH` 16 MB.

## Chronicle data: who reads what

- Campaign membership (creator, `campaign_players` roster member, or site admin) is required for
  messages, events/unread/roster, dice, and the room list / room details
  (`GET /api/campaigns/<id>/locations`, `GET /api/locations/<id>`; non-members get 403).
  Helper is `services/location_access.user_is_campaign_viewer`.
- Closed rooms (`locations.is_open = false`) are readable only by admins, helpers and the
  campaign's storyteller. `/unread` and the SSE stream only report rooms the viewer may read
  (`fetch_readable_location_ids`), so activity in a closed room doesn't leak through counters or
  "changed" events. The stream re-checks that set every 15 s (a room closed mid-stream stops
  being reported).
- SSE cost: a trigger on `messages` (INSERT/UPDATE/DELETE) bumps `campaign_activity.version`
  and the room's row in `campaign_location_activity` (`version`, `last_message_id`,
  `reset_version` for edits/deletes). Each stream polls the campaign row once a second with a
  connection borrowed from a small per-process pool (`SR_EVENTS_DB_POOL`, default 4 per gunicorn
  worker) and reads the room rows only when the version moved; streams don't hold a database
  connection between polls. Measured: 6 open streams added no connections beyond the pools
  (8 idle connections for 2 workers).

## Dice integrity

- Dice results in chat come from the server. `POST /roll`, `/roll/<id>/reroll` and `/rouse`
  with a `location_id` save the animation marker (with the `dice_rolls` id as `roll_id`) and the
  result line themselves, in the same transaction as the roll (`services/dice_chat.py`).
- `POST /api/campaigns/<c>/locations/<l>` refuses `ai_message_kind` values starting with
  `dice_animation`, `dice_roll` or `dice_rouse` from anyone but site admins (403). The old
  exemption that let any member post a dice marker as role `assistant` is gone
  (`services/assistant_grants.py`).
- Admin-posted markers (the admin-only `/ai roll` flow) must pass the marker key whitelist and
  get their timing clamped (`duration_ms` ≤ 8000, `started_at_ms` within ±60 s of server time),
  so a marker can't hold every client's dice overlay open or replay an old roll as new.
- Hidden rolls (`dice_*_hidden`) are returned only to admins, helpers and the storyteller.

## Audit log

`auth_events` (PostgreSQL): `login`, `login_failed` (with `known_user`), `lockout`,
`login_blocked`, `login_disabled`, `register`, `invite_invalid`, `logout`, `logout_all`,
`password_changed`, `password_change_failed`, `refresh_reuse`, with user id, username, IP and user
agent. Rows older than 180 days are pruned opportunistically. Admins read it with
`GET /api/admin/auth-events?limit=100[&user_id=][&event=]`. Admin actions stay in
`user_moderation_log`.

## Production server

`APP_SERVER=gunicorn` (default in docker-compose) runs `gunicorn -c gunicorn.conf.py wsgi:app`;
`APP_SERVER=flask` (with `FLASK_ENV=development`) runs the old dev server with auto-reload.

| Setting | Value | Why |
|---|---|---|
| `bind` | `127.0.0.1:5000` (`GUNICORN_BIND`) | only nginx may connect (proxy trust) |
| `worker_class` | `gthread` | SSE streams and Storyteller replies hold a thread for up to ~55 s |
| `workers` | 2 (`GUNICORN_WORKERS`) | |
| `threads` | 48 per worker (`GUNICORN_THREADS`) | 20 SSE streams + 28 for normal requests |
| `SR_EVENTS_MAX_STREAMS` | 20 per worker (4 per user per worker) | streams can never take every thread |
| `timeout` | 120 s | for gthread this is the worker heartbeat, not a request limit |
| `graceful_timeout` | 30 s | open streams are cut on restart; the browser reconnects |
| `keepalive` | 5 s | |
| `preload_app` | true | `create_app()`/`migrate_db()` run once in the master |
| `max_requests` | 0 | no recycling (would drop streams) |
| access log | stdout, path without query string | SSE tickets never land in logs |

Background jobs (RAG re-embed, rule book backfill) are started in the first worker after the fork
(`post_fork`), not in the preloading master: threads don't survive `fork()`. The re-embed takes a
PostgreSQL advisory lock anyway. The Laya classifier is loaded lazily on first use in each worker
(never in the master): measured about 126 MB RSS for the master and about 690 MB per worker with
Laya loaded; the first classification in a worker takes about 1.6 s, later ones about 230 ms. Docker's health check (`curl localhost:5000/health`) works because
the backend container uses the host network.

## Settings reference

| Variable | Default (compose) | Meaning |
|---|---|---|
| `APP_SERVER` | `gunicorn` | or `flask` (dev server) |
| `FLASK_ENV` | `production` | `development` skips the secret-strength check |
| `JWT_ACCESS_TOKEN_MINUTES` | 360 (code: 30) | access token lifetime |
| `JWT_REFRESH_TOKEN_DAYS` | 14 | refresh token lifetime |
| `JWT_SESSION_MAX_DAYS` | 30 | absolute limit of one login's refresh chain |
| `BCRYPT_ROUNDS` | 12 | 12-16 |
| `PASSWORD_MIN_LENGTH` | 12 | never below 10 |
| `CORS_ORIGINS` | empty | extra allowed origins |
| `TRUSTED_PROXY_HOPS` | 1 | proxies in front of gunicorn that set `X-Forwarded-*` |
| `RATELIMIT_ENABLED` | true | |
| `RATELIMIT_STORAGE_URI` | `redis://REDIS_HOST:REDIS_PORT/0` | |
| `AUTH_COOKIE_SECURE` | auto | `true`/`false` to force the refresh cookie's `Secure` flag |
| `GUNICORN_*` | see table above | |
| `SR_EVENTS_DB_POOL` | 4 | PostgreSQL connections per worker for SSE polling |

## Frontend changes (done in v0.9.0)

The list below was the plan for the frontend once the backend changes above landed. Items 1 to 5
and 8 are done:

1. **Refresh on 401**: `frontend/src/app/http.js` calls `POST /api/auth/refresh` once on
   `TOKEN_EXPIRED`, retries the request, and shares one refresh between callers and tabs (Web
   Locks). A refused refresh ends the session locally.
2. **Logout calls the server**: `AuthContext.jsx` posts to `/api/auth/logout` or, for "Sign out
   everywhere" in the user menu, `/api/auth/logout-all`.
3. **429 and 503 don't log out**: they become a translated message with the wait time.
4. **Login/register**: the server's `error` is shown and the password policy codes are mapped to
   translated messages (`features/auth/PasswordRules.jsx`).
5. **Change password**: in the profile page (`POST /api/auth/change-password`).
6. **Admin panel** (optional, not done): an unlock form for `POST /api/admin/auth/unlock` and an
   auth events table from `GET /api/admin/auth-events`. Both endpoints work from the API.
7. **Shorter access tokens**: not done yet. `docker-compose.yml` still defaults
   `JWT_ACCESS_TOKEN_MINUTES` to 360; with 1 to 3 live it can be set to 30 in `.env` (then
   `docker compose up -d backend`).
8. **Content-Security-Policy**: nginx sends a strict CSP with the production build (scripts only
   from the site), see `nginx/nginx.conf`.
