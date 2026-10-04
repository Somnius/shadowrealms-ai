#!/usr/bin/env bash
# Remove the trailer's demo stack (project "srdemo") and, with --purge, its data
# (data/trailer/demo-data, demo.env, demo-invites.json, demo-accounts.json, chromium profile).
# Never touches the live "shadowrealms-ai" project.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
T="$ROOT/data/trailer"
docker compose -p srdemo --env-file "$T/demo.env" -f "$ROOT/tools/trailer/demo-compose.yml" down --remove-orphans
if [ "${1:-}" = "--purge" ]; then
  # files written by containers are owned by this user (user: in the compose file), so plain rm works
  rm -rf "$T/demo-data" "$T/chromium-profile" "$T/demo.env" "$T/demo-invites.json" "$T/demo-accounts.json" "$T/.invite-codes.json"
  echo "demo stack and its data removed (clips kept)"
else
  echo "demo stack stopped and removed; data kept in $T/demo-data (use --purge to delete it)"
fi
