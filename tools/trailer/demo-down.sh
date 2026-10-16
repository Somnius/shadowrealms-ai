#!/usr/bin/env bash
# Remove the trailer's demo stack (project "srdemo") and, with --purge, its data
# (<demo>/demo-data, demo.env, demo-invites.json, demo-accounts.json, chromium profile).
# Never touches the live "shadowrealms-ai" project. DEMO_ROOT / TRAILER_DATA: as in demo-up.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEMO_ROOT="${DEMO_ROOT:-$ROOT}"
DT="$DEMO_ROOT/data/trailer"
T="$ROOT/${TRAILER_DATA:-data/trailer}"
docker compose -p srdemo --env-file "$DT/demo.env" -f "$DEMO_ROOT/tools/trailer/demo-compose.yml" down --remove-orphans
if [ "${1:-}" = "--purge" ]; then
  # files written by containers are owned by this user (user: in the compose file), so plain rm works
  rm -rf "$DT/demo-data" "$DT/demo.env" "$DT/chromium-profile" "$DT/demo-invites.json" "$DT/demo-accounts.json" "$DT/.invite-codes.json"
  rm -rf "$T/chromium-profile" "$T/demo-invites.json" "$T/demo-accounts.json" "$T/.invite-codes.json"
  echo "demo stack and its data removed (clips kept)"
else
  echo "demo stack stopped and removed; data kept in $DT/demo-data (use --purge to delete it)"
fi
