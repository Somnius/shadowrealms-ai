#!/usr/bin/env bash
#
# Legacy entry point. This used to build the frontend container and run the old authentication
# tests with docker-compose v1 (LoginForm.test.tsx, which no longer exists). The frontend suite,
# including the auth/session tests (src/app/__tests__/), now runs through one script:
#
#   ./scripts/run-frontend-tests.sh [jest args]
#
# This wrapper keeps old instructions working:
#   ./tests/test-auth-docker.sh             -> auth/session tests only
#   ./tests/test-auth-docker.sh coverage    -> same, with coverage
#   ./tests/test-auth-docker.sh all         -> the whole frontend suite

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$ROOT/scripts/run-frontend-tests.sh"

case "${1:-auth}" in
    -h|--help)
        sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
        ;;
    all)
        exec "$RUN"
        ;;
    coverage)
        exec "$RUN" --coverage src/app/__tests__
        ;;
    *)
        exec "$RUN" src/app/__tests__
        ;;
esac
