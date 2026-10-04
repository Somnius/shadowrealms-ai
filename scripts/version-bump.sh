#!/bin/bash
#
# ShadowRealms AI - Version Bump Script
#
# Bumps the real version markers and nothing else:
#   .env                      VERSION=X.Y.Z   (backend /api/version, passed in by docker-compose)
#   env.template              VERSION=X.Y.Z
#   frontend/package.json     "version"       (footer badge, read at build time)
#   frontend/package-lock.json  top-level "version" and packages[""].version
#   README.md                 shields.io version badge
#
# It does NOT edit any other documentation. Older docs mention past versions on purpose
# (changelog entries, "(v0.7.0)" labels, archive banners); rewriting them corrupts history.
# The release notes (docs/CHANGELOG.md, SHADOWREALMS_AI_COMPLETE.md, README) are written by hand,
# see docs/VERSION_BUMP_PROCESS.md.
#
# Usage: ./scripts/version-bump.sh <old_version> <new_version>
# Example: ./scripts/version-bump.sh 0.9.0 0.9.1
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

if [ "$#" -ne 2 ]; then
    echo -e "${RED}Error: expected two arguments${NC}"
    echo "Usage: $0 <old_version> <new_version>"
    echo "Example: $0 0.9.0 0.9.1"
    exit 1
fi

OLD_VERSION="$1"
NEW_VERSION="$2"

for v in "$OLD_VERSION" "$NEW_VERSION"; do
    if ! [[ "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo -e "${RED}Error: '$v' is not in X.Y.Z format${NC}"
        exit 1
    fi
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo -e "${CYAN}ShadowRealms AI version bump: ${OLD_VERSION} -> ${NEW_VERSION}${NC}"

CURRENT=$(sed -n 's/^VERSION=//p' env.template | head -1)
if [ "$CURRENT" != "$OLD_VERSION" ]; then
    echo -e "${YELLOW}Warning: env.template has VERSION=${CURRENT}, not ${OLD_VERSION}${NC}"
fi

BACKUP_DIR="backups/version-bump-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

backup() {
    mkdir -p "$BACKUP_DIR/$(dirname "$1")"
    cp "$1" "$BACKUP_DIR/$1"
}

# Rewrite a file through awk into a temp file, then replace it (portable: no sed -i).
rewrite() {
    local file="$1"; shift
    local tmp
    tmp=$(mktemp)
    awk "$@" "$file" > "$tmp"
    cat "$tmp" > "$file"
    rm -f "$tmp"
}

# VERSION=... lines
for file in .env env.template; do
    if [ -f "$file" ]; then
        backup "$file"
        rewrite "$file" -v new="$NEW_VERSION" '/^VERSION=/ { print "VERSION=" new; next } { print }'
        echo -e "  ${GREEN}updated${NC} $file"
    else
        echo -e "  ${YELLOW}skipped (not found)${NC} $file"
    fi
done

# package.json: the first "version" key (the package's own version).
# package-lock.json: the top-level "version" and the one in packages[""]; dependency entries
# further down are left alone.
VERSION_AWK='
BEGIN { old = "\"version\": \"" oldv "\""; repl = "\"version\": \"" newv "\"" }
function swap(line,   i) {
    i = index(line, old)
    if (i == 0) return line
    return substr(line, 1, i - 1) repl substr(line, i + length(old))
}
!top && index($0, old) { $0 = swap($0); top = 1; print; next }
/^    "": \{/ { inroot = 1 }
inroot && !rootdone && index($0, old) { $0 = swap($0); rootdone = 1 }
inroot && /^    \},?$/ { inroot = 0 }
{ print }
'
for file in frontend/package.json frontend/package-lock.json; do
    if [ -f "$file" ]; then
        backup "$file"
        rewrite "$file" -v oldv="$OLD_VERSION" -v newv="$NEW_VERSION" "$VERSION_AWK"
        echo -e "  ${GREEN}updated${NC} $file"
    else
        echo -e "  ${YELLOW}skipped (not found)${NC} $file"
    fi
done

# README badge only (sed -i.bak works with GNU and BSD sed, and keeps the file's last line as is)
if [ -f README.md ]; then
    backup README.md
    OLD_RE=${OLD_VERSION//./\\.}
    sed -i.bak "s#badge/version-${OLD_RE}-blue#badge/version-${NEW_VERSION}-blue#" README.md
    rm -f README.md.bak
    echo -e "  ${GREEN}updated${NC} README.md (badge)"
fi

echo ""
echo -e "${CYAN}Version markers now:${NC}"
grep -H '^VERSION=' env.template .env 2>/dev/null || true
grep -m1 -H '"version"' frontend/package.json || true
grep -n -m2 '"version"' frontend/package-lock.json | sed 's/^/frontend\/package-lock.json:/' || true
grep -o -H 'badge/version-[0-9.]*-blue' README.md || true

echo ""
echo -e "${YELLOW}Still to do by hand (docs/VERSION_BUMP_PROCESS.md):${NC}"
echo "  1. docs/CHANGELOG.md: new ## [${NEW_VERSION}] entry at the top"
echo "  2. SHADOWREALMS_AI_COMPLETE.md: new version section + TOC entry"
echo "  3. README.md: anything in the text that describes the release"
echo "  4. ./scripts/build-frontend.sh (footer badge) and docker compose up -d backend (/api/version)"
echo "  5. git commit, then tag v${NEW_VERSION} on main"
echo ""
echo -e "${GREEN}Done.${NC} Backups in ${BACKUP_DIR}"
