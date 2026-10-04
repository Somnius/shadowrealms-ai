## What and why

<!-- What this changes and why. Link the issue if there is one (Fixes #123). -->

## How it was tested

<!-- What you ran or clicked through, and what you didn't test. -->

## Checklist

- [ ] CI is green: Python compile + ruff (`E9,F63,F7,F82`), backend unit tests (`pytest backend/tests/unit`), PostgreSQL schema + `migrate_db`, frontend tests + build, and no new CodeQL alerts.
- [ ] New or changed logic has tests (backend `backend/tests/unit/`, frontend Jest next to the code or in `__tests__/`).
- [ ] UI text goes through i18n and exists in **both** `en` and `el` locales (`frontend/src/i18n/__tests__/locales.test.js` checks it).
- [ ] Database changes are in **both** `backend/init_postgresql_schema.sql` and `migrate_db()` in `backend/database.py` (CI checks they give the same schema).
- [ ] New environment variables are in `docker-compose.yml`, `env.template` and `docs/DOCKER_ENV_SETUP.md`.
- [ ] Docs updated if behaviour or setup changed; `docs/CHANGELOG.md` has a line under `[Unreleased]`.
