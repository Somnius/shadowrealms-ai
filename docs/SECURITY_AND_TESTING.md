# Security practices and automated tests

**Document version:** 0.9.0 (see `docs/CHANGELOG.md`).

This document describes how we test security-sensitive behavior, how to run those tests safely, and how to keep dependencies under control.

## Automated checks (CI)

Every pull request and every push to `main` that touches code runs `.github/workflows/ci.yml`:

- **Python**: `compileall` over `backend monitoring books scripts tests`, and `ruff check --select E9,F63,F7,F82` (syntax errors and undefined names).
- **Backend unit tests**: `python -m pytest -q backend/tests/unit`, 291 tests that need no database, Redis or AI: dice (classic and V5), rules editions, character and Storyteller prompts, AI providers and secret storage, the classifier and OOC monitor, live events, request validation, and authentication security (`test_auth_security.py`, see below).
- **PostgreSQL schema**: applies `backend/init_postgresql_schema.sql` to an empty database, runs `migrate_db()` twice, and fails if the schema differs.
- **Frontend**: the Jest suite (`npx jest --ci`, 474 tests in 43 files), `npm run lint` (any warning fails it) and a production build (`npm run build`, Vite).

Also on GitHub:

- **CodeQL** (`.github/workflows/codeql.yml`) scans Python and JavaScript/TypeScript.
- **Dependabot** (`.github/dependabot.yml`) opens monthly update PRs for pip, npm, Docker images and GitHub Actions, plus security updates as advisories appear.

Run them locally with `docker compose exec backend python -m pytest -q tests/unit` and `./scripts/run-frontend-tests.sh` (see [CONTRIBUTING.md](CONTRIBUTING.md#tests-and-ci)).

## Integration tests (manual)

The tests below are older integration scripts in the top-level `tests/` folder. They need a running PostgreSQL and are not part of CI.

### What the security / feature tests cover

The file [`tests/test_campaign_membership.py`](../tests/test_campaign_membership.py) exercises (PostgreSQL):

- **Detach / join gate**: After leaving a chronicle, self-join to another listed game is rejected (`join_requires_storyteller_approval`) unless rejoining with an existing sheet.
- **Playing character**: Player cannot switch to another PC in the same chronicle without storyteller approval; storyteller `PUT` succeeds.

The file `tests/test_security_and_features.py` exercises:

- **Admin isolation**: Non-admin JWTs cannot call `GET /api/admin/users/<id>/debug` (403); admins can (200).
- **Authentication**: Admin routes return 401/422 without a Bearer token.
- **Input typing**: Invalid campaign id in the path returns **404** (no server error from bad paths).
- **Discover / join**: A listed campaign can be discovered and joined by another user.
- **Messages**: `GET` message lists include **`poster_role`** (author site role) for UI labeling.

Tests register **synthetic users** with unique names (UUID suffix). They **mock**:

- Invite validation (`TEST-PLAYER` / `TEST-ADMIN` codes) so real `invites.json` is not consumed.
- Invite “use” counters.
- Welcome email sending (no SMTP traffic during tests).
- RAG (`create_rag_service`) so **ChromaDB does not need to be running**.
- Campaign RAG writes when creating campaigns (`get_rag_service` on the campaigns route).

They **do not** mock the database: they require **PostgreSQL** with the same credentials as normal development (see below).

**Cleaning up rows left in the DB after tests:** see [DATABASE_TEST_DATA_CLEANUP.md](DATABASE_TEST_DATA_CLEANUP.md) and [`scripts/cleanup_integration_test_data.py`](../scripts/cleanup_integration_test_data.py).

## Prerequisites

1. **PostgreSQL** running and reachable (e.g. `docker compose up -d postgresql`).
2. Environment variables (from `.env` or your shell):
   - `DATABASE_TYPE=postgresql`
   - `DATABASE_HOST` — use `127.0.0.1` when running tests on the host (not the Docker service name `postgresql`).
   - `DATABASE_NAME` / `DATABASE_USER`
   - `DATABASE_PASSWORD` **or** `POSTGRES_PASSWORD` (the backend accepts either; see `database.get_db()`).
3. **JWT / Flask secrets** — any non-empty values for local runs; use strong unique secrets in production.

## Running the tests

From the repository root:

```bash
export LOG_FILE=/tmp/sr_security_test.log
python3 tests/test_security_and_features.py
```

Or use the helper script (sources `.env` if present, maps Docker hostname `postgresql` → `127.0.0.1` for host-side runs):

```bash
./scripts/run_security_tests.sh
```

If PostgreSQL credentials are not set, the suite is **skipped** with a clear message (no fake passes).

### Security notes for CI and developers

- **Never** commit real production passwords or JWT secrets into tests.
- Tests use **`LOG_FILE`** under `/tmp` so host runs do not try to create `/app/logs` from Docker-only paths.
- Run tests in a **clean** Python process so `Config` picks up environment variables before import.

## Dependency and supply-chain hygiene

### npm (frontend)

- **Axios** was listed in `package.json` but is **not imported** anywhere in `frontend/src`. It was removed to shrink the attack surface. If you add HTTP client usage later, prefer the **browser `fetch` API** (already used elsewhere) or re-add a pinned, audited `axios` version.
- Run periodically:

```bash
docker compose --profile dev run --rm --no-deps frontend npm run audit
```

Review `npm audit` output; upgrade or replace packages with confirmed fixes.

The frontend moved from Create React App to Vite, which removed 67 of the 69 `npm audit --omit=dev` findings (react-scripts was a runtime dependency, so its build tooling counted). The 2 left are react-router 6 (fixed in 7, a separate upgrade); the dev-only findings are `braces` under Jest and Tailwind, build and test tooling that never ships to the browser.

### pip (backend)

Pin versions in `requirements.txt` for reproducible builds. Audit with [pip-audit](https://pypi.org/project/pip-audit/):

```bash
pip install pip-audit
pip-audit -r backend/requirements.txt
```

### PyPI / npm incidents

Stay aware of public advisories (e.g. compromised package versions). If a package was ever published maliciously:

- **Remove** locked versions from lockfiles / `package-lock.json` after upgrading.
- **Rotate** secrets (API keys, JWT signing keys) if a trojan ran during `npm install` or `pip install` on a machine with access to production.

## Application security (high level)

The authentication model (passwords, lockouts, tokens and revocation, rate limits, headers, proxy
trust, gunicorn) is described in [SECURITY_MODEL.md](SECURITY_MODEL.md). Its unit tests are in
`backend/tests/unit/test_auth_security.py` (password policy, bcrypt, lockout logic, revocation
decision, client IP behind one proxy, rate-limit keys and 429 body, no exception text in 500s).
Integration tests that register users need passwords of 12+ characters that are not on the
common-password list, and `RATELIMIT_ENABLED=false` when they log in many times.

- **SQL**: Prefer parameterized queries (`%s` or `?` with bound parameters, depending on DB driver). Do not concatenate user input into SQL strings.
- **Auth**: Admin routes use `@require_admin()` and JWT identity; compare resource ownership with **`str(id)`** where JWT identities are strings and DB ids may be integers.
- **Site admin scope**: Users with **`users.role = 'admin'`** may open any chronicle for support (campaign detail, messages, dice, read-state rules as implemented since v0.7.18). This is intentional; restrict who receives the admin role. Helpers and players do not receive this bypass unless separately documented.
- **PostgreSQL booleans**: Comparisons like `is_active = 1` against `BOOLEAN` columns can error; routes use `IS TRUE` / dialect-specific helpers where needed.
- **XSS**: Avoid injecting untrusted HTML. `ReadmeModal` uses `dangerouslySetInnerHTML` only for the README served by the app, after sanitizing it; chat markdown is rendered to React nodes without any HTML (`features/chat/markdown.jsx`). Do not reuse the README pattern for user content. nginx also sends a strict Content-Security-Policy with the production build.

## Related files

- `tests/test_security_and_features.py` — security / feature regression tests.
- `tests/test_campaign_membership.py` — detach, join gate, playing-character rules (PostgreSQL).
- `scripts/run_security_tests.sh` — convenience runner with `.env` handling.
- `scripts/cleanup_integration_test_data.py` — optional DB cleanup for `sec_*` / `@test.local` test rows (see [DATABASE_TEST_DATA_CLEANUP.md](DATABASE_TEST_DATA_CLEANUP.md)).
- `backend/tests/unit/` — the unit tests CI runs.
- `tests/README.md` — index of the older integration scripts.
