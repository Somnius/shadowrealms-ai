#!/usr/bin/env bash
# Wrapper: load repo .env via Python (same pattern as run_security_tests.sh), run cleanup script.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "${DATABASE_HOST:-}" == "postgresql" ]]; then
  export DATABASE_HOST=127.0.0.1
fi

exec python3 "$ROOT/scripts/cleanup_integration_test_data.py" "$@"
