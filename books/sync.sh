#!/bin/bash
# World of Darkness Books Sync Wrapper
# Manages virtual environment and executes the sync script

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_SCRIPT="$SCRIPT_DIR/sync_wod_books.py"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}World of Darkness Books Sync${NC}"
echo -e "${BLUE}========================================${NC}"
echo

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
    echo
fi

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

# Check if requirements are installed
REQUIREMENTS_INSTALLED=false
if [ -f "$VENV_DIR/requirements.installed" ]; then
    # Check if requirements.txt has been modified since last install
    if [ "$REQUIREMENTS" -nt "$VENV_DIR/requirements.installed" ]; then
        echo -e "${YELLOW}Requirements file updated. Reinstalling...${NC}"
        REQUIREMENTS_INSTALLED=false
    else
        REQUIREMENTS_INSTALLED=true
    fi
fi

if [ "$REQUIREMENTS_INSTALLED" = false ]; then
    echo -e "${BLUE}Installing/updating dependencies...${NC}"
    echo -e "${YELLOW}This shows what's being installed (may take 2-5 min first time):${NC}"
    echo
    pip install --upgrade pip
    echo
    pip install -r "$REQUIREMENTS"
    echo
    touch "$VENV_DIR/requirements.installed"
    echo -e "${GREEN}✓ Dependencies installed${NC}"
    echo
fi

# Run the sync script
echo -e "${GREEN}Starting sync...${NC}"
echo
python "$PYTHON_SCRIPT" "$@"

# Deactivate virtual environment
deactivate

