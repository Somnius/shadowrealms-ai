# Contributing to ShadowRealms AI

Thanks for your interest in ShadowRealms AI. This is a small, self-hosted hobby project; contributions are welcome, and this page explains how the repository works so a change can go in smoothly.

## Contents

- [Code of conduct](#code-of-conduct)
- [Development setup](#development-setup)
- [Project rules](#project-rules)
- [Tests and CI](#tests-and-ci)
- [Commits and pull requests](#commits-and-pull-requests)
- [Release process](#release-process)
- [Getting help](#getting-help)

## Code of conduct

Be respectful and constructive, assume good intent, and keep discussion about the work. Harassment, discrimination and spam aren't tolerated.

## Development setup

Everything runs in Docker (Compose v2, `docker compose`); Python and Node are installed inside the images.

```bash
git clone https://github.com/<you>/shadowrealms-ai.git
cd shadowrealms-ai
cp env.template .env          # fill in secrets, see docs/DOCKER_ENV_SETUP.md
./docker-up.sh                # starts the stack
./scripts/build-frontend.sh   # production build, served by nginx at http://localhost/
```

For frontend work with live reload, run the dev server (it is behind the `dev` compose profile) and point nginx at it, as described in [DOCKER_ENV_SETUP.md](DOCKER_ENV_SETUP.md#frontend-production-build-vs-dev-server):

```bash
docker compose --profile dev up -d frontend
```

For backend work with auto-reload, set `APP_SERVER=flask` and `FLASK_ENV=development` in `.env` and run `docker compose up -d backend`. The backend source is bind-mounted, so gunicorn only needs a `docker compose restart backend` after a change.

**Dependencies.** After editing `backend/requirements.txt` or `frontend/package.json`, rebuild the image: `docker compose build backend` or `docker compose --profile dev build frontend`. Commit `frontend/package-lock.json` with any `package.json` change.

## Project rules

These are checked in review, and most of them in CI.

- **Translations.** All UI text goes through i18n and must exist in both English and Greek (`frontend/src/i18n/locales/en` and `el`). `frontend/src/i18n/__tests__/locales.test.js` fails if a key, plural form or `{{placeholder}}` is missing on either side, or if code uses a key that the English file doesn't have.
- **Database schema.** A schema change goes into both `backend/init_postgresql_schema.sql` (fresh installs) and `migrate_db()` in `backend/database.py` (existing databases). CI applies the SQL file, runs `migrate_db()` twice, and fails if the schema changes.
- **Rules data.** `frontend/src/rules/classic.json` and `v5.json` are verbatim copies of `docs/rules/classic.json` and `docs/rules/v5.json`; change the docs copy and copy it over. The specs are [rules/CLASSIC_REVISED.md](rules/CLASSIC_REVISED.md) and [rules/V5.md](rules/V5.md).
- **Environment variables.** A new variable goes into `docker-compose.yml` (otherwise it never reaches the container), `env.template` and the table in [DOCKER_ENV_SETUP.md](DOCKER_ENV_SETUP.md).
- **Game content.** Glyphs and symbols are original art; don't add official White Wolf / Paradox logos or copyrighted book text to the repository.
- **Style.** Follow the code around you. Python: PEP 8, small functions, docstrings where the reason isn't obvious. React: function components with hooks; reuse the design system in `frontend/src/design/` (see its [README](../frontend/src/design/README.md)).

## Tests and CI

GitHub Actions (`.github/workflows/ci.yml`) runs on pull requests and on pushes to `main` that touch code:

| Job | What it runs |
|-----|--------------|
| Python | `python -m compileall -q backend monitoring books scripts tests` and `ruff check --select E9,F63,F7,F82` (syntax errors and undefined names only) |
| Backend unit tests | `python -m pytest -q backend/tests/unit` (no database or AI needed) |
| PostgreSQL schema | applies `init_postgresql_schema.sql`, runs `migrate_db()` twice, diffs the schema |
| Frontend | `npx jest --ci`, `npm run lint` (fails on any warning), then `npm run build` |

CodeQL (`.github/workflows/codeql.yml`) scans Python and JavaScript, and Dependabot opens monthly update PRs for pip, npm, Docker and GitHub Actions.

Run the same checks locally:

```bash
# Backend unit tests, inside the running backend container
docker compose exec backend python -m pytest -q tests/unit

# Frontend tests, in a one-off container (extra args go to Jest)
./scripts/run-frontend-tests.sh
./scripts/run-frontend-tests.sh src/features/chat

# Python lint, as CI does
docker run --rm -v "$PWD":/src -w /src python:3.12-slim sh -c \
  'pip install -q ruff && ruff check --select E9,F63,F7,F82 backend monitoring books scripts tests'
```

The scripts in the top-level `tests/` folder are older integration scripts that need a running stack; CI doesn't run them. See [tests/README.md](../tests/README.md) and [frontend/TESTING.md](../frontend/TESTING.md).

New logic should come with tests: backend unit tests in `backend/tests/unit/`, frontend tests next to the code or in a `__tests__/` folder.

## Commits and pull requests

- Commit subjects are short and lowercase, in the form `area: what changed`, for example `chat: keep the composer focused after sending` or `docs: env table in DOCKER_ENV_SETUP`. Use the body for the why, if it isn't obvious.
- One logical change per commit where practical.
- Open pull requests against `main`. The [pull request template](../.github/pull_request_template.md) has the checklist (CI, tests, EN+EL, schema, env vars, docs).
- Add a line under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md) for anything a user or admin would notice.
- Bugs and feature ideas go in [GitHub Issues](https://github.com/Somnius/shadowrealms-ai/issues) using the issue forms.
- Security problems go through private reporting (Security tab, "Report a vulnerability"), never a public issue. See [SECURITY.md](../SECURITY.md).

## Release process

Releases are commits on `main` plus a tag:

1. `./scripts/version-bump.sh OLD NEW` (only bumps the version markers).
2. Write the release notes: `docs/CHANGELOG.md`, `SHADOWREALMS_AI_COMPLETE.md`, `README.md`.
3. Commit on `main`, tag `vNEW`, push both, and create the GitHub release from the tag.

Details: [VERSION_BUMP_PROCESS.md](VERSION_BUMP_PROCESS.md).

## Getting help

- [Docs index](README.md) and the [wiki](https://github.com/Somnius/shadowrealms-ai/wiki)
- [GitHub Issues](https://github.com/Somnius/shadowrealms-ai/issues) for questions about the code or setup
