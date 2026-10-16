#!/usr/bin/env bash
# Wipe the demo stack's database/vector store/redis and re-seed it for one language:
#   tools/trailer/reset_demo.sh el
# (the en and el recordings each get their own chat history). Live stack untouched.
# DEMO_ROOT / TRAILER_DATA / RESYNC: as in demo-up.sh. Trailer v2 from a worktree:
#   DEMO_ROOT=<main checkout> TRAILER_DATA=data/trailer-v2 RESYNC=1 tools/trailer/reset_demo.sh en
set -euo pipefail
LANG_=${1:?usage: reset_demo.sh en|el}
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEMO_ROOT="${DEMO_ROOT:-$ROOT}"
DT="$DEMO_ROOT/data/trailer"; D="$DT/demo-data"
T="$ROOT/${TRAILER_DATA:-data/trailer}"
export DEMO_UID="$(id -u)" DEMO_GID="$(id -g)"
docker compose -p srdemo --env-file "$DT/demo.env" -f "$DEMO_ROOT/tools/trailer/demo-compose.yml" down
rm -rf "$D/pg" "$D/chroma" "$D/redis" "$D/appdata"
mkdir -p "$D/backend-src"
cp "$T/demo-invites.json" "$D/backend-src/invites.json"
python3 - "$T/demo-accounts.json" <<'PY'
import json, sys, os
p = sys.argv[1]
if os.path.exists(p):
    a = json.load(open(p))
    for v in a.values(): v.pop('registered', None); v.pop('id', None)
    json.dump(a, open(p, 'w'), indent=2); os.chmod(p, 0o600)
PY
"$ROOT/tools/trailer/demo-up.sh"
sleep 3
node "$ROOT/tools/trailer/register_accounts.mjs"
node "$ROOT/tools/trailer/setup_demo.mjs" "$LANG_"
