# ShadowRealms AI - Backend

Flask API for ShadowRealms AI, run by gunicorn in the `backend` Docker service. It talks to PostgreSQL, Redis, ChromaDB, and the LLM servers on the host (LM Studio, Ollama). The browser reaches it only through nginx at `/api/`.

## Running

The backend is started by Docker Compose (see [docs/DOCKER_ENV_SETUP.md](../docs/DOCKER_ENV_SETUP.md)). `entrypoint.sh` waits for ChromaDB and the monitoring service, then starts:

- **gunicorn** (default, `APP_SERVER=gunicorn`): `gunicorn -c gunicorn.conf.py wsgi:app`, gthread workers on `127.0.0.1:5000`. The app is preloaded once; startup jobs (RAG re-embed, rule book backfill) run in the first worker.
- **Flask dev server** (`APP_SERVER=flask`, with `FLASK_ENV=development`): `python main.py --run`, with auto-reload.

`./backend` is bind-mounted into the container at `/app`, so code changes need only `docker compose restart backend` under gunicorn.

On startup `create_app()` runs `init_db()` and `migrate_db()` (`database.py`), which bring an existing database up to the current schema. A fresh database gets `init_postgresql_schema.sql` from the PostgreSQL container's init folder.

## Layout

| Path | What it is |
|------|-----------|
| `main.py` | `create_app()`: config, security setup, blueprints, `/api/version`, `/api/readme`, `/health` |
| `wsgi.py`, `gunicorn.conf.py`, `entrypoint.sh` | Production entry point and server settings |
| `config.py` | Configuration from environment variables |
| `database.py` | Connection helpers, `init_db()`, `migrate_db()` |
| `init_postgresql_schema.sql` | Full schema for a fresh database |
| `routes/` | API blueprints: `auth`, `users`, `campaigns`, `characters`, `locations`, `messages`, `dice`, `events` (live updates over Server-Sent Events), `ai`, `rule_books`, `admin` |
| `services/` | Logic used by the routes, see below |
| `tests/unit/` | pytest unit tests (no database, Redis or AI needed); run in CI |
| `reembed_rag.py` | Re-embed every ChromaDB collection with `EMBEDDING_MODEL` |
| `ingest_location_naming_rag.py` | Load the location naming guide into RAG |
| `invites.template.json` | Template for `invites.json` (gitignored, the real invite codes) |
| `migrate_sqlite_to_postgresql.py`, `migrate_users_only.py`, `migrations/`, `test_postgresql_migration.py` | Tools from the SQLite to PostgreSQL move (v0.7.6); not needed for new installs |

Main areas in `services/`:

- **Security:** `app_security.py` (proxy trust, rate limits, headers, CORS), `auth_security.py` (password policy, bcrypt, lockouts), `auth_tokens.py` (JWT issue, refresh rotation, revocation). See [docs/SECURITY_MODEL.md](../docs/SECURITY_MODEL.md).
- **Rules and dice:** `wod_dice.py` (Classic Revised), `v5_dice.py`, `dice_service.py`, `dice_chat.py`, `dice_markers.py`, `rules_edition.py`, `character_sheet_v5.py`. See [docs/dice-old-wod.md](../docs/dice-old-wod.md) and [docs/dice-v5.md](../docs/dice-v5.md).
- **AI:** `ai_providers.py` and `ai_roles.py` (LM Studio, Ollama, Anthropic, OpenAI behind one interface, with fallback), `storyteller_prompt.py`, `character_prompt.py`, `language.py`, `classifier.py` and `ooc_monitor.py` (Laya / Jev / LLM fallback), `secret_store.py` (encrypted provider keys), `ai_slash_commands.py`. See [docs/AI_SYSTEMS.md](../docs/AI_SYSTEMS.md).
- **RAG:** `vector_store.py` and `embedding_service.py` (one embedder for every collection), `rag_service.py` (rule books: `rules_edition.py`, written by `books/import_books.py`).
- **Play:** `live_events.py`, `playing_character.py`, `play_suspension.py`, `location_access.py`, `chat_cleanup.py`, `mail_service.py`.

## Tests

```bash
docker compose exec backend python -m pytest -q tests/unit
```

CI runs the same suite with `python -m pytest -q backend/tests/unit`, plus a check that `init_postgresql_schema.sql` and `migrate_db()` give the same schema. Any schema change goes into both. See [docs/CONTRIBUTING.md](../docs/CONTRIBUTING.md).
