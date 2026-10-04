#!/usr/bin/env bash
#
# Build the production frontend into frontend/build/, which nginx serves directly.
# Run it after pulling frontend changes:  ./scripts/build-frontend.sh
# (nginx picks the new files up immediately; no restart needed.)
#
# For live-reload development instead, see docs/DOCKER_ENV_SETUP.md ("dev frontend").

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# public/README.md is a symlink to ../../README.md, so the repo README is mounted at /README.md.
# INLINE_RUNTIME_CHUNK=false keeps every script in a file, so the CSP can forbid inline scripts.
docker compose --profile dev run --rm --no-deps \
  -v "$ROOT/README.md:/README.md:ro" \
  -e CI=false -e INLINE_RUNTIME_CHUNK=false -e GENERATE_SOURCEMAP=false \
  frontend sh -c 'npm run build'

echo "Frontend built into frontend/build/"
