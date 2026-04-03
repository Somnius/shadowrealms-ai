# Security practices and automated tests

**Document version:** 0.7.16 (see `docs/CHANGELOG.md`).

This document describes how we test security-sensitive behavior, how to run those tests safely, and how to keep dependencies under control.

## What the security / feature tests cover

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
cd frontend
npm install
npm run audit
```

Review `npm audit` output; upgrade or replace packages with confirmed fixes.

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

- **SQL**: Prefer parameterized queries (`%s` placeholders with bound parameters). Do not concatenate user input into SQL strings.
- **Auth**: Admin routes use `@require_admin()` and JWT identity; compare resource ownership with **`str(id)`** where JWT identities are strings and DB ids may be integers.
- **PostgreSQL booleans**: Comparisons like `is_active = 1` against `BOOLEAN` columns can error; routes use `IS TRUE` / dialect-specific helpers where needed.
- **XSS**: Avoid injecting untrusted HTML. `ReadmeModal` uses `dangerouslySetInnerHTML` only for **trusted** README content served by the app—do not reuse that pattern for user chat or arbitrary uploads.

## Related files

- `tests/test_security_and_features.py` — security / feature regression tests.
- `scripts/run_security_tests.sh` — convenience runner with `.env` handling.
- `tests/README.md` — full test suite index.
