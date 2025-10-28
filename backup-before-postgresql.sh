#!/bin/bash
#
# ShadowRealms AI - Pre-PostgreSQL Migration Backup Script
#
# This script creates a comprehensive backup of the entire system
# before migrating from SQLite to PostgreSQL.
#
# Usage: ./backup-before-postgresql.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Timestamp for backup
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="backups/pre-postgresql-migration-${TIMESTAMP}"

echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                               ║${NC}"
echo -e "${CYAN}║     ShadowRealms AI - Pre-PostgreSQL Migration Backup        ║${NC}"
echo -e "${CYAN}║                                                               ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Backup will be saved to: ${BACKUP_DIR}${NC}"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"
echo -e "${BLUE}📦 Created backup directory${NC}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}1. BACKING UP SQLITE DATABASE${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Check if database exists
if [ -f "backend/data/shadowrealms.db" ]; then
    # Copy SQLite database
    cp backend/data/shadowrealms.db "$BACKUP_DIR/shadowrealms.db"
    echo -e "${GREEN}  ✓${NC} SQLite database backed up"
    
    # Get database size
    DB_SIZE=$(du -h backend/data/shadowrealms.db | cut -f1)
    echo -e "    Size: ${CYAN}${DB_SIZE}${NC}"
    
    # Export database to SQL dump (human-readable)
    if command -v sqlite3 &> /dev/null; then
        sqlite3 backend/data/shadowrealms.db .dump > "$BACKUP_DIR/shadowrealms_dump.sql"
        echo -e "${GREEN}  ✓${NC} SQL dump created (for inspection)"
    else
        echo -e "${YELLOW}  ⚠${NC}  sqlite3 not found, skipping SQL dump"
    fi
    
    # Export schema only
    if command -v sqlite3 &> /dev/null; then
        sqlite3 backend/data/shadowrealms.db .schema > "$BACKUP_DIR/schema.sql"
        echo -e "${GREEN}  ✓${NC} Schema exported"
    fi
    
    # Get table statistics
    if command -v sqlite3 &> /dev/null; then
        echo "" > "$BACKUP_DIR/table_statistics.txt"
        echo "Table Statistics:" >> "$BACKUP_DIR/table_statistics.txt"
        echo "=================" >> "$BACKUP_DIR/table_statistics.txt"
        echo "" >> "$BACKUP_DIR/table_statistics.txt"
        
        sqlite3 backend/data/shadowrealms.db "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;" | while read table; do
            count=$(sqlite3 backend/data/shadowrealms.db "SELECT COUNT(*) FROM $table;")
            echo "$table: $count rows" >> "$BACKUP_DIR/table_statistics.txt"
        done
        
        echo -e "${GREEN}  ✓${NC} Table statistics exported"
    fi
else
    echo -e "${RED}  ✗${NC} Database not found at backend/data/shadowrealms.db"
    echo -e "${YELLOW}    Checking Docker container...${NC}"
    
    # Try to backup from Docker container
    if docker compose ps backend | grep -q "Up"; then
        docker compose exec -T backend cat /app/data/shadowrealms.db > "$BACKUP_DIR/shadowrealms.db"
        if [ -s "$BACKUP_DIR/shadowrealms.db" ]; then
            echo -e "${GREEN}  ✓${NC} SQLite database backed up from Docker container"
            DB_SIZE=$(du -h "$BACKUP_DIR/shadowrealms.db" | cut -f1)
            echo -e "    Size: ${CYAN}${DB_SIZE}${NC}"
        else
            echo -e "${RED}  ✗${NC} Failed to backup database from Docker"
        fi
    else
        echo -e "${RED}  ✗${NC} Backend container not running"
        echo -e "${YELLOW}    Please start containers or provide database path${NC}"
    fi
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}2. BACKING UP CHROMADB DATA${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ -d "chromadb_data" ]; then
    mkdir -p "$BACKUP_DIR/chromadb_data"
    cp -r chromadb_data/* "$BACKUP_DIR/chromadb_data/" 2>/dev/null || true
    CHROMA_SIZE=$(du -sh chromadb_data | cut -f1)
    echo -e "${GREEN}  ✓${NC} ChromaDB data backed up"
    echo -e "    Size: ${CYAN}${CHROMA_SIZE}${NC}"
else
    echo -e "${YELLOW}  ⚠${NC}  ChromaDB data directory not found"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}3. BACKING UP CONFIGURATION FILES${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Backup critical configuration files
CONFIG_FILES=(
    ".env"
    "docker-compose.yml"
    "backend/config.py"
    "backend/database.py"
    "backend/invites.json"
    "nginx/nginx.conf"
)

mkdir -p "$BACKUP_DIR/config"

for file in "${CONFIG_FILES[@]}"; do
    if [ -f "$file" ]; then
        mkdir -p "$BACKUP_DIR/config/$(dirname $file)"
        cp "$file" "$BACKUP_DIR/config/$file"
        echo -e "${GREEN}  ✓${NC} Backed up: $file"
    else
        echo -e "${YELLOW}  ⚠${NC}  Not found: $file"
    fi
done

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}4. BACKING UP DOCUMENTATION${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Backup key documentation
mkdir -p "$BACKUP_DIR/docs"
cp README.md "$BACKUP_DIR/docs/" 2>/dev/null || true
cp SHADOWREALMS_AI_COMPLETE.md "$BACKUP_DIR/docs/" 2>/dev/null || true
cp docs/*.md "$BACKUP_DIR/docs/" 2>/dev/null || true

DOC_COUNT=$(find "$BACKUP_DIR/docs" -type f | wc -l)
echo -e "${GREEN}  ✓${NC} Backed up ${DOC_COUNT} documentation files"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}5. CREATING SYSTEM SNAPSHOT${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# System information
cat > "$BACKUP_DIR/system_info.txt" << EOF
ShadowRealms AI - Pre-PostgreSQL Migration Backup
==================================================

Backup Date: $(date)
Hostname: $(hostname)
User: $(whoami)
OS: $(uname -a)

Git Status:
-----------
$(git status 2>/dev/null || echo "Not a git repository")

Git Commit:
-----------
$(git log -1 --oneline 2>/dev/null || echo "No git history")

Docker Containers:
------------------
$(docker compose ps 2>/dev/null || echo "Docker not available")

Python Version:
---------------
$(python3 --version 2>/dev/null || echo "Python not found")

Node Version:
-------------
$(node --version 2>/dev/null || echo "Node not found")

Disk Usage:
-----------
$(df -h . 2>/dev/null || echo "Cannot determine disk usage")

EOF

echo -e "${GREEN}  ✓${NC} System snapshot created"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}6. CREATING VERIFICATION CHECKSUMS${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Create checksums for all backed up files
cd "$BACKUP_DIR"
find . -type f -exec md5sum {} \; > checksums.md5 2>/dev/null || \
find . -type f -exec md5 {} \; > checksums.md5 2>/dev/null || \
echo "Checksum creation skipped"
cd - > /dev/null

echo -e "${GREEN}  ✓${NC} Checksums created"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}7. CREATING COMPRESSED ARCHIVE${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Create tar.gz archive
ARCHIVE_NAME="backups/pre-postgresql-${TIMESTAMP}.tar.gz"
tar -czf "$ARCHIVE_NAME" -C backups "$(basename $BACKUP_DIR)" 2>/dev/null

if [ -f "$ARCHIVE_NAME" ]; then
    ARCHIVE_SIZE=$(du -h "$ARCHIVE_NAME" | cut -f1)
    echo -e "${GREEN}  ✓${NC} Compressed archive created"
    echo -e "    File: ${CYAN}${ARCHIVE_NAME}${NC}"
    echo -e "    Size: ${CYAN}${ARCHIVE_SIZE}${NC}"
else
    echo -e "${YELLOW}  ⚠${NC}  Could not create compressed archive"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}8. BACKUP SUMMARY${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Calculate total backup size
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

echo ""
echo -e "${GREEN}✅ Backup completed successfully!${NC}"
echo ""
echo -e "📍 Backup Location:"
echo -e "   Directory: ${CYAN}${BACKUP_DIR}${NC}"
echo -e "   Archive:   ${CYAN}${ARCHIVE_NAME}${NC}"
echo ""
echo -e "📦 Backup Size:"
echo -e "   Directory: ${CYAN}${BACKUP_SIZE}${NC}"
if [ -f "$ARCHIVE_NAME" ]; then
    echo -e "   Archive:   ${CYAN}${ARCHIVE_SIZE}${NC}"
fi
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT NOTES:${NC}"
echo -e "   1. Verify backup integrity before proceeding with migration"
echo -e "   2. Keep this backup until PostgreSQL migration is confirmed stable"
echo -e "   3. Test restoration procedure before migration"
echo -e "   4. Store backup in safe location (off-server recommended)"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}Ready to proceed with PostgreSQL migration!${NC}"
echo ""

