#!/usr/bin/env bash
# Run tests/test_security_and_features.py with sensible defaults for host-side execution.
# Loads variables from .env via Python (same as the Flask app) — run from repo root.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export LOG_FILE="${LOG_FILE:-/tmp/sr_security_test.log}"

# When Postgres runs in Docker and tests run on the host, use loopback not the service name.
if [[ "${DATABASE_HOST:-}" == "postgresql" ]]; then
  export DATABASE_HOST=127.0.0.1
fi

exec python3 tests/test_security_and_features.py "$@"
