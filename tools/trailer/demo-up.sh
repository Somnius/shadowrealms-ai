#!/usr/bin/env bash
# Start the trailer's demo stack (project "srdemo", http://127.0.0.1:8180). Leaves the live stack alone.
# First run: copies the current backend/ code into data/trailer/demo-data/backend-src and
# expects data/trailer/demo.env (a copy of .env with demo DB credentials/secrets, mode 600)
# and data/trailer/demo-invites.json (see tools/trailer/README in the report / setup_demo.mjs).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
T="$ROOT/data/trailer"
D="$T/demo-data"
[ -f "$T/demo.env" ] || { echo "missing $T/demo.env" >&2; exit 1; }
mkdir -p "$D"/{pg,redis,chroma,logs,appdata/laya,backend-src}
if [ ! -f "$D/backend-src/main.py" ] || [ "${RESYNC:-0}" = 1 ]; then
  rsync -a --exclude invites.json --exclude '__pycache__' --exclude data --exclude logs \
    --exclude books --exclude project_docs "$ROOT/backend/" "$D/backend-src/"
fi
mkdir -p "$D"/backend-src/{data,logs,books,project_docs}
touch "$D/backend-src/README.md" "$D/logs/system_status.json"
[ -f "$D/backend-src/invites.json" ] || cp "$T/demo-invites.json" "$D/backend-src/invites.json"
export DEMO_UID="$(id -u)" DEMO_GID="$(id -g)"
docker compose -p srdemo --env-file "$T/demo.env" -f "$ROOT/tools/trailer/demo-compose.yml" up -d
for i in $(seq 1 60); do
  curl -sf http://127.0.0.1:5100/health >/dev/null 2>&1 && curl -sf http://127.0.0.1:8180/ >/dev/null 2>&1 && { echo "demo stack up: http://127.0.0.1:8180"; exit 0; }
  sleep 2
done
echo "demo backend (:5100/health) or nginx (:8180) not answering yet; check: docker compose -p srdemo logs backend" >&2
exit 1
