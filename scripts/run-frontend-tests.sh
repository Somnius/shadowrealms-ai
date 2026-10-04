#!/usr/bin/env bash
#
# ShadowRealms AI - frontend test runner (Jest via react-scripts).
#
# Runs the same command as the CI "Frontend tests + build" job, in a one-off container of the
# dev frontend service (the service is behind the `dev` profile and normally not running).
#
#   ./scripts/run-frontend-tests.sh                 # whole suite
#   ./scripts/run-frontend-tests.sh src/i18n        # only tests whose path matches
#   ./scripts/run-frontend-tests.sh --coverage      # with a coverage report in frontend/coverage/
#
# Extra arguments go straight to Jest. JEST_WORKERS (default 4) caps the parallel test workers.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WORKERS="${JEST_WORKERS:-4}"

echo "Running frontend tests (jest, ${WORKERS} workers)..."
docker compose --profile dev run --rm --no-deps \
  -e CI=true \
  frontend npx react-scripts test --watchAll=false --maxWorkers="$WORKERS" "$@"
