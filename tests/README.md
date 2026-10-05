# ShadowRealms AI - Tests

## Where the tests are

| Suite | Location | Runs in CI | How to run locally |
|-------|----------|-----------|--------------------|
| Backend unit tests (291 at v0.9.0) | `backend/tests/unit/` | yes | `docker compose exec backend python -m pytest -q tests/unit` |
| Frontend tests (Jest, 385 at v0.9.0) | `frontend/src/**/*.test.js(x)`, `__tests__/` folders | yes | `./scripts/run-frontend-tests.sh` |
| PostgreSQL schema check | `.github/workflows/ci.yml` (job `schema`) | yes | see the workflow |
| Legacy integration scripts | this folder (`tests/`) | no | see below |

The CI checks are described in [docs/CONTRIBUTING.md](../docs/CONTRIBUTING.md#tests-and-ci) and [docs/SECURITY_AND_TESTING.md](../docs/SECURITY_AND_TESTING.md). The frontend suites are listed in [frontend/TESTING.md](../frontend/TESTING.md).

## This folder: legacy integration scripts

The scripts here are older integration and verification scripts from v0.4 to v0.8. They are not part of CI, most need the full stack running (PostgreSQL, ChromaDB, LM Studio), and several were written for the pre-PostgreSQL setup or the old frontend. CI still compiles them and checks them for syntax errors and undefined names. Treat their results as a smoke test, not a pass/fail gate.

Still useful (PostgreSQL integration, kept current):

| Script | Purpose | Usage |
|--------|---------|-------|
| `test_security_and_features.py` | Auth boundaries, discover/join, `poster_role` on messages | `./scripts/run_security_tests.sh` |
| `test_campaign_membership.py` | Detach, join restriction, per-campaign playing character | `python3 -m pytest tests/test_campaign_membership.py -v` (with `DATABASE_*` set and `DATABASE_TYPE=postgresql`) |

Both create test users; clean them up with [docs/DATABASE_TEST_DATA_CLEANUP.md](../docs/DATABASE_TEST_DATA_CLEANUP.md).

Legacy (may not match the current app):

| Script | Purpose |
|--------|---------|
| `test_phase2.py` | Phase 2 RAG and vector memory |
| `test_user_experience.py` | End-to-end API workflows |
| `test_comprehensive_verification.py`, `test_deep_verification.py` | System verification |
| `test_ai_memory_system.py` | AI memory |
| `test_api_endpoints.py`, `test_frontend_backend_integration.py` | API checks |
| `test_modules.py` | Backend module imports |
| `test_flask_config.py`, `test_docker_env.py`, `test_docker.sh` | Configuration and Docker environment |
| `test_postgresql_migration.py` | The SQLite to PostgreSQL migration (v0.7.6) |
| `check_deleted_locations.py`, `fix_missing_ooc_rooms.py` | One-off maintenance helpers |
| `validate-test-structure.sh` | Checks this folder's layout |
| `test-auth-docker.sh` | Wrapper around `scripts/run-frontend-tests.sh` for the auth/session tests (`all` runs the whole frontend suite) |

[MIGRATION_SUMMARY.md](MIGRATION_SUMMARY.md) records when the scripts were moved into this folder (2025-10-24).

## Adding tests

New tests go into the suites CI runs:

- Backend logic that doesn't need a database, Redis or AI: `backend/tests/unit/test_*.py` (pytest).
- Frontend: a `*.test.js(x)` file next to the code or in a `__tests__/` folder (Jest + Testing Library).
