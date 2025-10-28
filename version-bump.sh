#!/bin/bash
#
# ShadowRealms AI - Version Bump Script
# 
# This script automates the process of bumping version numbers across the project.
# It updates configuration files, documentation, and provides verification.
#
# Usage: ./version-bump.sh <old_version> <new_version>
# Example: ./version-bump.sh 0.7.6 0.7.7
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check arguments
if [ "$#" -ne 2 ]; then
    echo -e "${RED}Error: Invalid number of arguments${NC}"
    echo "Usage: $0 <old_version> <new_version>"
    echo "Example: $0 0.7.6 0.7.7"
    exit 1
fi

OLD_VERSION="$1"
NEW_VERSION="$2"

# Validate version format (X.Y.Z)
if ! [[ "$OLD_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}Error: Old version must be in format X.Y.Z${NC}"
    exit 1
fi

if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}Error: New version must be in format X.Y.Z${NC}"
    exit 1
fi

echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                               ║${NC}"
echo -e "${CYAN}║           ShadowRealms AI - Version Bump Tool                 ║${NC}"
echo -e "${CYAN}║                                                               ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Version bump: ${OLD_VERSION} → ${NEW_VERSION}${NC}"
echo ""

# Create backup directory
BACKUP_DIR="backups/version-bump-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo -e "${BLUE}📦 Creating backups in ${BACKUP_DIR}${NC}"

# List of files to update (configuration files)
CONFIG_FILES=(
    ".env"
    "env.template"
    "frontend/package.json"
)

# List of files to update (documentation files - current version only)
DOC_FILES=(
    "README.md"
    "SHADOWREALMS_AI_COMPLETE.md"
    "docs/README.md"
    "docs/PROJECT_STATUS_ARCHIVED.md"
    "docs/PHASE3B_IMPLEMENTATION.md"
    "docs/PLANNING.md"
    "docs/AI_SYSTEMS.md"
    "demo/README.md"
)

# Function to backup a file
backup_file() {
    local file="$1"
    if [ -f "$file" ]; then
        cp "$file" "$BACKUP_DIR/$(basename $file)"
        echo -e "  ${GREEN}✓${NC} Backed up: $file"
    fi
}

# Function to update version in a file
update_version() {
    local file="$1"
    local pattern="$2"
    local replacement="$3"
    
    if [ -f "$file" ]; then
        # Backup first
        backup_file "$file"
        
        # Perform replacement
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "$pattern" "$file"
        else
            # Linux
            sed -i "$pattern" "$file"
        fi
        echo -e "  ${GREEN}✓${NC} Updated: $file"
    else
        echo -e "  ${YELLOW}⚠${NC}  Skipped (not found): $file"
    fi
}

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📝 UPDATING CONFIGURATION FILES${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Update .env
if [ -f ".env" ]; then
    backup_file ".env"
    sed -i.bak "s/^VERSION=.*/VERSION=${NEW_VERSION}/" .env
    rm -f .env.bak
    echo -e "  ${GREEN}✓${NC} Updated: .env"
fi

# Update env.template
update_version "env.template" "s/^VERSION=.*/VERSION=${NEW_VERSION}/" ""

# Update frontend/package.json
if [ -f "frontend/package.json" ]; then
    backup_file "frontend/package.json"
    sed -i.bak "s/\"version\": \"${OLD_VERSION}\"/\"version\": \"${NEW_VERSION}\"/" frontend/package.json
    rm -f frontend/package.json.bak
    echo -e "  ${GREEN}✓${NC} Updated: frontend/package.json"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📚 UPDATING DOCUMENTATION FILES${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Update README.md badge
if [ -f "README.md" ]; then
    backup_file "README.md"
    sed -i.bak "s/version-${OLD_VERSION}-blue/version-${NEW_VERSION}-blue/" README.md
    sed -i.bak "s/Version ${OLD_VERSION} Preview/Version ${NEW_VERSION} Preview/" README.md
    rm -f README.md.bak
    echo -e "  ${GREEN}✓${NC} Updated: README.md"
fi

# Update other documentation files
for file in "${DOC_FILES[@]}"; do
    if [ "$file" != "README.md" ] && [ -f "$file" ]; then
        backup_file "$file"
        # Update "Current Version" and "Version:" references
        sed -i.bak "s/Current Version\*\*: ${OLD_VERSION}/Current Version**: ${NEW_VERSION}/" "$file"
        sed -i.bak "s/\*\*Version:\*\* ${OLD_VERSION}/**Version:** ${NEW_VERSION}/" "$file"
        sed -i.bak "s/Version ${OLD_VERSION}/Version ${NEW_VERSION}/" "$file"
        sed -i.bak "s/(v${OLD_VERSION})/(v${NEW_VERSION})/" "$file"
        rm -f "${file}.bak"
        echo -e "  ${GREEN}✓${NC} Updated: $file"
    fi
done

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🔍 VERIFICATION${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo ""
echo -e "${CYAN}Searching for remaining references to old version...${NC}"
echo ""

# Search for old version references (excluding package dependencies and git history)
REMAINING=$(grep -rn "${OLD_VERSION}" \
    --include="*.md" \
    --include="*.json" \
    --include="*.py" \
    --include="*.js" \
    --include="*.template" \
    --include=".env" \
    --exclude-dir=node_modules \
    --exclude-dir=.git \
    --exclude-dir=venv \
    --exclude-dir=books/venv \
    . 2>/dev/null | \
    grep -v "loguru" | \
    grep -v "## \[${OLD_VERSION}\]" | \
    grep -v "## Version ${OLD_VERSION}" | \
    grep -v "### Version ${OLD_VERSION}" | \
    grep -v "version-${OLD_VERSION}" | \
    head -20 || true)

if [ -z "$REMAINING" ]; then
    echo -e "${GREEN}✓ No unexpected references to old version found!${NC}"
else
    echo -e "${YELLOW}⚠ Found remaining references (review manually):${NC}"
    echo "$REMAINING"
    echo ""
    echo -e "${CYAN}Note: Historical changelog entries and version section headers are expected.${NC}"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📋 NEXT STEPS (MANUAL)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}1. Update docs/CHANGELOG.md${NC}"
echo -e "   Add a new version section at the top:"
echo -e "   ${CYAN}## [${NEW_VERSION}] - $(date +%Y-%m-%d) - <Title> <Emoji>${NC}"
echo ""
echo -e "${YELLOW}2. Update README.md${NC}"
echo -e "   Add a new 'Current Development Status' section:"
echo -e "   ${CYAN}### Version ${NEW_VERSION} - <Title> <Emoji>${NC}"
echo ""
echo -e "${YELLOW}3. Update SHADOWREALMS_AI_COMPLETE.md${NC}"
echo -e "   - Add new version section with full details"
echo -e "   - Update TOC links"
echo -e "   - Update 'Current Status' indicators"
echo ""
echo -e "${YELLOW}4. Review and test${NC}"
echo -e "   - Verify all changes are correct"
echo -e "   - Test the application"
echo -e "   - Check footer version display"
echo ""
echo -e "${YELLOW}5. Commit changes${NC}"
echo -e "   ${CYAN}git add -A${NC}"
echo -e "   ${CYAN}git commit -m \"chore: bump version to ${NEW_VERSION}\"${NC}"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ Automated version bump complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}Backups saved to: ${BACKUP_DIR}${NC}"
echo ""

