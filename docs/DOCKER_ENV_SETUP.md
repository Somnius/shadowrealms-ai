# Docker and Environment Setup

How to run ShadowRealms AI with Docker Compose, and what every environment variable does.

Requires Docker with the Compose v2 plugin (`docker compose`, not the old `docker-compose`).

---

## First run

```bash
cp env.template .env
python3 scripts/generate_secret_key.py   # paste the keys into FLASK_SECRET_KEY and JWT_SECRET_KEY
nano .env                                 # also set POSTGRES_USER and POSTGRES_PASSWORD
./docker-up.sh                            # docker compose up -d (extra args pass through, e.g. --build)
./scripts/build-frontend.sh               # builds frontend/ into frontend/build/
```

Then open **http://localhost/**.

For the PostgreSQL credentials, see [POSTGRESQL_ENV_SETUP.md](POSTGRESQL_ENV_SETUP.md). LM Studio (port 1234) and Ollama (port 11434) run on the host, outside Docker; see [AI_SYSTEMS.md](AI_SYSTEMS.md).

---

## What runs where

| Service | Listens on | Notes |
|---------|-----------|-------|
| `nginx` | port 80 (and 443) on all interfaces | Serves `frontend/build/` and proxies `/api/` to the backend. The only service meant to be reached from other machines. |
| `backend` | `127.0.0.1:5000` | Flask app under gunicorn by default (host networking). |
| `postgresql` | `127.0.0.1:5432` | PostgreSQL 16; schema from `backend/init_postgresql_schema.sql`. |
| `redis` | `127.0.0.1:6379` | Rate limits and login throttling. |
| `chromadb` | `127.0.0.1:8000` | Vector store for rule books and memory (RAG). |
| `monitoring` | `127.0.0.1:8001` | GPU and system status. |
| `frontend` | `127.0.0.1:3000` | Live-reload dev server. Only with `--profile dev`, not started by default. |

---

## Frontend: production build vs dev server

nginx serves the production build of the frontend from `frontend/build/` (static files, gzip, long cache for hashed assets, a strict Content-Security-Policy). After pulling frontend changes, rebuild it:

```bash
./scripts/build-frontend.sh
```

nginx picks up the new files immediately.

For live-reload development, start the dev server (it is behind the `dev` compose profile) and point nginx's `location /` at it (see the comment in `nginx/nginx.conf`):

```bash
docker compose --profile dev up -d frontend
```

**Editing `nginx/nginx.conf`:** the file is bind-mounted as a single file, and editors or `sed -i` replace it with a new file that the running container doesn't see. After an edit, recreate nginx rather than reloading it:

```bash
docker compose up -d --force-recreate nginx
```

## Backend: gunicorn vs the Flask dev server

The backend runs gunicorn by default (`backend/gunicorn.conf.py`, gthread workers, bound to `127.0.0.1:5000`). For the Flask development server with auto-reload, set in `.env`:

```bash
APP_SERVER=flask
FLASK_ENV=development
```

and recreate the container with `docker compose up -d backend`. See [SECURITY_MODEL.md](SECURITY_MODEL.md) for why production uses gunicorn.

---

## How environment variables reach the app

```
.env  ->  docker compose (docker-compose.yml, backend "environment:")  ->  backend container
```

- `docker compose` reads `.env` from the repository root and substitutes `${VAR}` / `${VAR:-default}` in `docker-compose.yml`.
- Only the variables listed under the backend's `environment:` reach the container. Anything else in `.env` is ignored by the app.
- Some values are fixed in `docker-compose.yml` (for example `LM_STUDIO_URL`, `CHROMADB_HOST`, `REDIS_HOST`, `LOG_LEVEL`); changing them in `.env` has no effect. `env.template` groups these under "Fixed in docker-compose.yml".
- After changing `.env`, recreate the container: `docker compose up -d backend`. A plain `restart` keeps the old environment.

## Environment variables

"Default" is the value the backend gets when the variable is not set in `.env` (from `docker-compose.yml`, or from the code when compose has none). Where `env.template` ships a different value, it is noted.

### Required

| Variable | Default | What it does |
|----------|---------|--------------|
| `FLASK_SECRET_KEY` | none | Flask secret. Also derives the key that encrypts the AI provider keys stored in the database; changing it makes them unreadable (re-enter them in Admin, Ai System). |
| `JWT_SECRET_KEY` | none | Signs access and refresh tokens. Changing it signs everyone out. |
| `POSTGRES_DB` | `shadowrealms_db` (template) | Database name, used by the `postgresql` service and passed to the backend as `DATABASE_NAME`. |
| `POSTGRES_USER`, `POSTGRES_PASSWORD` | none | Database credentials. Generate your own ([POSTGRESQL_ENV_SETUP.md](POSTGRESQL_ENV_SETUP.md)). |
| `DATABASE_TYPE`, `DATABASE_HOST`, `DATABASE_PORT` | `postgresql`, `localhost`, `5432` (template) | Keep as in the template. `DATABASE_HOST` must be `localhost`: the backend uses the host network, so the service name `postgresql` doesn't resolve inside it. |
| `VERSION` | none | Release version shown by `/api/version`. Bumped by `scripts/version-bump.sh`. |

### Server and security

| Variable | Default | What it does |
|----------|---------|--------------|
| `APP_SERVER` | `gunicorn` | `gunicorn` (production) or `flask` (dev server with auto-reload). |
| `FLASK_ENV` | `production` | Set `development` together with `APP_SERVER=flask`. |
| `GUNICORN_WORKERS` | `2` | gunicorn worker processes. |
| `GUNICORN_THREADS` | `48` | Threads per worker. Each open live-update stream and each Storyteller reply holds one. |
| `GUNICORN_BIND` | `127.0.0.1:5000` | Keep it on loopback: nginx is the only intended client, and the app trusts one proxy hop. |
| `JWT_ACCESS_TOKEN_MINUTES` | `360` (compose), `30` (code) | Access token lifetime. The frontend refreshes expired tokens automatically. |
| `JWT_REFRESH_TOKEN_DAYS` | `14` | Lifetime of the refresh cookie (HttpOnly). |
| `JWT_SESSION_MAX_DAYS` | `30` | A session can't be extended past this, however often it refreshes. |
| `BCRYPT_ROUNDS` | `12` | Password hashing cost (never below 12). |
| `PASSWORD_MIN_LENGTH` | `12` | Minimum password length (never below 10). |
| `CORS_ORIGINS` | empty | Extra origins allowed to call the API, comma-separated. Leave empty: the app is same-origin through nginx and sends no CORS headers. |
| `TRUSTED_PROXY_HOPS` | `1` | How many proxies' `X-Forwarded-For` to trust (1 = the local nginx). Used for rate limits and lockouts. |
| `RATELIMIT_ENABLED` | `true` | `false` turns the API rate limits off (for local testing only). |
| `SR_EVENTS_MAX_STREAMS` | `20` | Open live-update (Server-Sent Events) streams per worker. |
| `SR_EVENTS_MAX_STREAMS_PER_USER` | `4` | Open streams per user per worker. |

### AI

| Variable | Default | What it does |
|----------|---------|--------------|
| `LM_STUDIO_API_KEY` | empty | Only if LM Studio has authentication turned on. |
| `LM_STUDIO_MODEL` | `auto` | `auto` uses the model LM Studio has loaded. |
| `LM_STUDIO_TIMEOUT` | `120` (compose), `30` (template) | Seconds per LM Studio request. |
| `LM_STUDIO_REASONING_EFFORT` | empty (compose), `none` (template) | `none` turns off "thinking" on reasoning models; empty uses the model's default. |
| `OLLAMA_MODEL` | `command-r:35b` | Default Ollama model. |
| `OLLAMA_TIMEOUT` | `30` | Seconds per Ollama request. |
| `STORYTELLER_EL_MODEL` | `llama-krikri-8b-instruct` | Default model of the Greek Storyteller role. Changeable in Admin, Ai System. |
| `UTILITY_PROVIDER`, `UTILITY_MODEL` | `ollama`, `llama3.2:3b` | Default provider and model of the Utility role. |
| `EMBEDDING_MODEL` | `text-embedding-bge-m3` | LM Studio embedding model for every ChromaDB collection. Changing it re-embeds the collections at the next backend start. |
| `OOC_VIOLATION_THRESHOLD` | `0.8` | Classifier score at which a message in an OOC room counts as a violation. |
| `OPENAI_REASONING_EFFORT` | `none` | Sent to OpenAI reasoning models when an admin enables OpenAI. |
| `STORYTELLER_ATTEMPT_TIMEOUT` | `45` | Seconds per model attempt for a Storyteller reply. |
| `STORYTELLER_TIME_BUDGET` | `55` | Seconds for the whole fallback chain (nginx allows `/api` 60 s). |
| `STORYTELLER_CONTEXT_TOKENS` | `8192` | Context window the Storyteller prompt is trimmed to (lowered to LM Studio's loaded context if smaller). |
| `JEV_MODEL` | `jev-latest` | Typesafe Jev classifier model (the key is set in the admin panel). |
| `LAYA_RUNTIME` | `/app/ml/laya/infer.py` (fixed in compose) | Laya classifier runtime. The model is read from `data/laya/model`. |

Cloud keys (Anthropic, OpenAI) and the Typesafe Jev key are not environment variables: an admin enters them in Admin, Ai System, and they are stored encrypted. See [AI_SYSTEMS.md](AI_SYSTEMS.md).

### Email (optional)

| Variable | Default | What it does |
|----------|---------|--------------|
| `SMTP_HOST` | empty | Empty turns outbound email off. |
| `SMTP_PORT` | `587` | |
| `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | empty | |
| `SMTP_USE_TLS` | `true` | STARTTLS (port 587). |
| `SMTP_USE_SSL` | `false` | SMTPS (port 465). |
| `APP_PUBLIC_NAME` | `ShadowRealms AI` | Name used in emails. |
| `MAIL_ADMIN_ALERT_EMAIL` | empty | Gets an email on invalid sign-up attempts, if SMTP is set up. |

### Not passed to the backend

- **Fixed in `docker-compose.yml`:** `FLASK_HOST`, `FLASK_PORT`, `FLASK_DEBUG`, `LM_STUDIO_URL`, `OLLAMA_URL`, `CHROMADB_HOST`, `CHROMADB_PORT`, `REDIS_HOST`, `REDIS_PORT`, `GPU_THRESHOLD_HIGH`, `GPU_THRESHOLD_MEDIUM`, `LOG_LEVEL`, `LOG_FILE`. Edit `docker-compose.yml` to change them.
- **Code defaults only** (not in `docker-compose.yml`; add them there to change them): `AUTH_COOKIE_SECURE` (`auto`: Secure refresh cookie only over HTTPS), `GUNICORN_TIMEOUT`, `GUNICORN_GRACEFUL_TIMEOUT`, `GUNICORN_KEEPALIVE`, `GUNICORN_LOGLEVEL`, `FORWARDED_ALLOW_IPS`, `RATELIMIT_STORAGE_URI`, `LM_STUDIO_MODEL_FALLBACK`, `LAYA_MODEL_DIR`.
- **Legacy, unused in v0.9:** everything under "Legacy / unused" in `env.template` (for example `DATABASE`, the SQLite path from before PostgreSQL, `OPENAI_API_KEY`, `LLM_*`, `AI_MAX_TOKENS_*`, `JWT_ACCESS_TOKEN_EXPIRES`).
- **Host scripts:** `BOOK_SOURCE_URL` is read from `.env` by `books/sync_wod_books.py` only (see [books/README.md](../books/README.md)).

---

## PostgreSQL schema

`docker-compose.yml` mounts `backend/init_postgresql_schema.sql` into the PostgreSQL container's init folder, so a fresh database volume gets every table on first start. On every start the backend also runs `migrate_db()`, which brings an older database up to date (CI checks that both give the same schema).

Check that the tables exist:

```bash
docker compose exec postgresql sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt"'
```

If there are no relations, PostgreSQL started without running the init script (for example the volume already existed, or the SQL file was missing). To start over with an **empty** database (this deletes all data):

```bash
docker compose down
docker volume rm shadowrealms-ai_postgresql_data
docker compose up -d
```

---

## Checking the running setup

```bash
docker compose ps                                     # all services up?
docker compose logs backend --tail 50                 # startup, migrate_db, gunicorn
docker compose exec backend env | grep -E 'APP_SERVER|JWT_|CORS'
curl -s http://127.0.0.1:5000/health                  # backend directly
curl -s http://localhost/api/version                  # through nginx
```

---

## Security notes

- Generate unique keys and database credentials for every installation; never use the template placeholders.
- Keep `.env` out of version control (it is in `.gitignore`).
- Only nginx should be reachable from other machines; the other services listen on `127.0.0.1`.
- See [SECURITY_MODEL.md](SECURITY_MODEL.md) and [SECURITY.md](../SECURITY.md).

## Troubleshooting

**A changed `.env` value has no effect.** Check that the variable is listed under the backend's `environment:` in `docker-compose.yml`, then `docker compose up -d backend` (not `restart`).

**Secret keys are still the defaults.** Generate new ones with `python3 scripts/generate_secret_key.py`, put them in `.env`, and recreate the backend. Everyone is signed out, and AI provider keys stored in the admin panel must be entered again if `FLASK_SECRET_KEY` changed.

**The page at http://localhost/ is blank or old.** Run `./scripts/build-frontend.sh`; nginx serves whatever is in `frontend/build/`.

**`docker-compose: command not found`.** Use `docker compose` (Compose v2). The old v1 binary is not supported by the scripts.
