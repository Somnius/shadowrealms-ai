#!/usr/bin/env bash
# Start the trailer's demo stack (project "srdemo", http://127.0.0.1:8180). Leaves the live stack alone.
# First run: copies the current backend/ code into <demo>/demo-data/backend-src and
# expects <demo>/demo.env (a copy of .env with demo DB credentials/secrets, mode 600)
# and <trailer data>/demo-invites.json (see setup_demo.mjs).
#
#   RESYNC=1       refresh the backend snapshot from backend/ (and restart the backend on the new code)
#   DEMO_ROOT=DIR  the checkout whose tools/trailer/demo-compose.yml and data/trailer/demo-data the
#                  stack runs from (default: this checkout). From a git worktree, point it at the main
#                  checkout so the running stack keeps its mounts (frontend/build, docs, books).
#   TRAILER_DATA   accounts/invites/state folder relative to this checkout (default data/trailer)
#   VERSION        app version the demo reports (default: frontend/package.json)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEMO_ROOT="${DEMO_ROOT:-$ROOT}"
DT="$DEMO_ROOT/data/trailer"
D="$DT/demo-data"
T="$ROOT/${TRAILER_DATA:-data/trailer}"
[ -f "$DT/demo.env" ] || { echo "missing $DT/demo.env" >&2; exit 1; }
mkdir -p "$D"/{pg,redis,chroma,logs,appdata/laya,backend-src}
synced=0
if [ ! -f "$D/backend-src/main.py" ] || [ "${RESYNC:-0}" = 1 ]; then
  rsync -a --delete --exclude invites.json --exclude '__pycache__' --exclude data --exclude logs \
    --exclude books --exclude project_docs "$DEMO_ROOT/backend/" "$D/backend-src/"
  synced=1
fi
mkdir -p "$D"/backend-src/{data,logs,books,project_docs}
touch "$D/backend-src/README.md" "$D/logs/system_status.json"
[ -f "$D/backend-src/invites.json" ] || cp "$T/demo-invites.json" "$D/backend-src/invites.json"
export DEMO_UID="$(id -u)" DEMO_GID="$(id -g)"
export VERSION="${VERSION:-$(node -p "require('$DEMO_ROOT/frontend/package.json').version")}"
compose() { docker compose -p srdemo --env-file "$DT/demo.env" -f "$DEMO_ROOT/tools/trailer/demo-compose.yml" "$@"; }
compose up -d
# gunicorn loads the code once (--preload): a refreshed snapshot needs a restart (migrate_db runs on start)
[ "$synced" = 1 ] && compose restart backend
for i in $(seq 1 60); do
  curl -sf http://127.0.0.1:5100/health >/dev/null 2>&1 && curl -sf http://127.0.0.1:8180/ >/dev/null 2>&1 && { echo "demo stack up: http://127.0.0.1:8180 (v$VERSION)"; exit 0; }
  sleep 2
done
echo "demo backend (:5100/health) or nginx (:8180) not answering yet; check: docker compose -p srdemo logs backend" >&2
exit 1
