#!/usr/bin/env bash
#
# ShadowRealms AI — start all Docker Compose services (detached).
# Run from anywhere: ./docker-up.sh   or   bash docker-up.sh
# Extra args are passed through (e.g. ./docker-up.sh --build).

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

exec docker compose up -d "$@"
