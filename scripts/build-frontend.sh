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
# The Vite build (vite.config.mjs) puts every script in a file, so the CSP can forbid inline
# scripts, and writes no source maps. After a dependency change, rebuild the image first:
#   docker compose --profile dev build frontend
docker compose --profile dev run --rm --no-deps \
  -v "$ROOT/README.md:/README.md:ro" \
  frontend sh -c 'npm run build'

echo "Frontend built into frontend/build/"
