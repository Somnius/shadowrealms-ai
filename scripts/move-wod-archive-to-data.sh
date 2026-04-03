#!/usr/bin/env bash
# Move local WoD bulk archive from books/ to data/ (gitignored).
# If data/ is not writable (e.g. created by Docker as root), fix ownership first:
#   sudo chown -R "$USER:$USER" "$(dirname "$0")/../data"
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/books/World_of_Darkness.tar"
DEST="$ROOT/data/World_of_Darkness.tar"

if [[ ! -f "$SRC" ]]; then
  echo "Nothing to do: source not found: $SRC"
  exit 0
fi

mkdir -p "$ROOT/data"
if [[ ! -w "$ROOT/data" ]]; then
  echo "Cannot write to $ROOT/data"
  echo "Fix ownership, then re-run this script:"
  echo "  sudo chown -R \"\$USER:\$USER\" \"$ROOT/data\""
  exit 1
fi

mv "$SRC" "$DEST"
echo "Moved WoD archive to: $DEST"
