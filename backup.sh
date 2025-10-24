#!/bin/bash

# ShadowRealms AI Backup Script
# Creates maximum compressed backups of the project excluding large PDF directories

set -e

# Configuration
PROJECT_NAME="shadowrealms-ai"
BACKUP_DIR="backup"

# Directories to exclude (PDF book directories and temporary/large files)
# Note: These will be properly quoted when passed to tar
EXCLUDE_PATTERNS=(
    "backup"
    "./books/Classic World of Darkness"
    "./books/New World of Darkness"
    "./books/nWoD"
    "./books/oWoD"
    "./books/venv"
    "./books/parsed"
    "./frontend/node_modules"
    "./.git"
    "*.tar.xz"
    "*.tar.bz2"
    "*.tar.gz"
    "__pycache__"
    "*.pyc"
    ".pytest_cache"
    ".DS_Store"
)

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Create timestamp for filename (including seconds for precision)
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILENAME="${PROJECT_NAME}_backup_${TIMESTAMP}.tar.xz"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"

# Build exclude arguments for tar with proper quoting
EXCLUDE_ARGS=()
for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    EXCLUDE_ARGS+=("--exclude=$pattern")
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 ShadowRealms AI Backup Process Started"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📁 Project: $PROJECT_NAME"
echo "📅 Timestamp: $TIMESTAMP"
echo "💾 Backup file: $BACKUP_FILENAME"
echo "🗜️  Compression: XZ (Maximum compression)"
echo ""
echo "🎯 Excluding patterns:"
for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    echo "   ❌ $pattern"
done
echo ""

# Record start time
START_TIME=$(date +%s)
START_DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Count files before backup (more accurate counting)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Analyzing source files..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Build find exclude pattern
FIND_EXCLUDES=""
FIND_EXCLUDES="$FIND_EXCLUDES -path ./backup -prune -o"
FIND_EXCLUDES="$FIND_EXCLUDES -path './books/Classic World of Darkness' -prune -o"
FIND_EXCLUDES="$FIND_EXCLUDES -path './books/New World of Darkness' -prune -o"
FIND_EXCLUDES="$FIND_EXCLUDES -path ./books/nWoD -prune -o"
FIND_EXCLUDES="$FIND_EXCLUDES -path ./books/oWoD -prune -o"
FIND_EXCLUDES="$FIND_EXCLUDES -path ./books/venv -prune -o"
FIND_EXCLUDES="$FIND_EXCLUDES -path ./books/parsed -prune -o"
FIND_EXCLUDES="$FIND_EXCLUDES -path ./frontend/node_modules -prune -o"
FIND_EXCLUDES="$FIND_EXCLUDES -path ./.git -prune -o"

SOURCE_FILE_COUNT=$(eval "find . $FIND_EXCLUDES -type f -print" | wc -l)
SOURCE_DIR_COUNT=$(eval "find . $FIND_EXCLUDES -type d -print" | wc -l)
SOURCE_SIZE=$(eval "find . $FIND_EXCLUDES -type f -print0" | du -ch --files0-from=- 2>/dev/null | tail -n 1 | cut -f1)

echo "   📁 Directories to backup: $SOURCE_DIR_COUNT"
echo "   📄 Files to backup: $SOURCE_FILE_COUNT"
echo "   💽 Total source size: $SOURCE_SIZE"
echo ""

# Create backup with progress indication
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏳ Creating backup archive with XZ maximum compression..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   ℹ️  This may take several minutes depending on project size"
echo "   📊 Processing $SOURCE_FILE_COUNT files..."
echo ""

# Use tar with xz compression with progress monitoring
# -c: create, -J: xz compression, -f: file, -v: verbose
# We'll show a live counter of files being processed
if command -v pv &> /dev/null; then
    # If pv is available, use it for better progress visualization
    echo "   💡 Using pv for progress monitoring"
    tar -c "${EXCLUDE_ARGS[@]}" . 2>&1 | grep -v "Removing leading" | pv -pterb -s $(eval "find . $FIND_EXCLUDES -type f -print0" | wc -c) | xz -9 > "$BACKUP_PATH"
else
    # Fallback: show file counter
    echo "   💡 Processing files (live counter):"
    tar -cvJf "$BACKUP_PATH" "${EXCLUDE_ARGS[@]}" . 2>&1 | \
    grep -v "Removing leading" | \
    awk 'BEGIN {count=0; printf "   "} 
         {count++; 
          if (count % 10 == 0) printf "\r   📦 Files processed: %d / '"$SOURCE_FILE_COUNT"' (%.1f%%)", count, (count/'"$SOURCE_FILE_COUNT"')*100;
         } 
         END {printf "\r   📦 Files processed: %d / '"$SOURCE_FILE_COUNT"' (100.0%%)        \n", count}'
fi
echo ""

# Check if backup was successful
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo ""
    echo "✅ Backup archive created successfully!"
    echo ""
    
    # Verify backup integrity
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔍 Verifying backup integrity..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Test archive can be read
    if tar -tJf "$BACKUP_PATH" > /dev/null 2>&1; then
        echo "   ✅ Archive is readable and not corrupted"
    else
        echo "   ❌ Archive verification failed!"
        exit 1
    fi
    
    # Count files in backup
    echo "   ⏳ Counting files in backup archive..."
    BACKUP_FILE_COUNT=$(tar -tJf "$BACKUP_PATH" | grep -v '/$' | wc -l)
    BACKUP_DIR_COUNT=$(tar -tJf "$BACKUP_PATH" | grep '/$' | wc -l)
    
    echo "   📁 Backup directories: $BACKUP_DIR_COUNT"
    echo "   📄 Backup files: $BACKUP_FILE_COUNT"
    
    # Verify file counts match (allowing for some variance due to exclusions)
    if [ $BACKUP_FILE_COUNT -gt 0 ] && [ $BACKUP_FILE_COUNT -le $SOURCE_FILE_COUNT ]; then
        echo "   ✅ File count verification passed"
    else
        echo "   ⚠️  File count mismatch (expected ≤$SOURCE_FILE_COUNT, got $BACKUP_FILE_COUNT)"
    fi
    echo ""
    
    # Check for critical files in backup
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔍 Verifying critical files in backup..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    CRITICAL_FILES=(
        "backend/main.py" 
        "backend/config.py" 
        "docker-compose.yml" 
        "requirements.txt" 
        "CHANGELOG.md"
        "README.md"
        "frontend/package.json"
        "books/sync.sh"
        "books/sync_wod_books.py"
    )
    MISSING_FILES=()
    
    for file in "${CRITICAL_FILES[@]}"; do
        if tar -tJf "$BACKUP_PATH" | grep -q "$file"; then
            echo "   ✅ $file"
        else
            echo "   ❌ $file (MISSING!)"
            MISSING_FILES+=("$file")
        fi
    done
    echo ""
    
    # Check for excluded directories (should NOT be in backup)
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔍 Verifying exclusions (these should NOT be in backup)..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    VERIFY_EXCLUDES=(
        "./books/Classic World of Darkness"
        "./books/New World of Darkness"
        "./books/nWoD"
        "./books/oWoD"
        "./books/venv"
        "./frontend/node_modules"
    )
    
    for dir in "${VERIFY_EXCLUDES[@]}"; do
        # Remove leading ./ for display and check
        display_dir="${dir#./}"
        if tar -tJf "$BACKUP_PATH" | grep -q "$dir/" 2>/dev/null; then
            echo "   ❌ $display_dir (should be excluded but found!)"
        else
            echo "   ✅ $display_dir (properly excluded)"
        fi
    done
    echo ""
    
    # Check backup file details
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 Backup file details..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    BACKUP_SIZE_BYTES=$(stat -c%s "$BACKUP_PATH")
    BACKUP_SIZE_HUMAN=$(du -h "$BACKUP_PATH" | cut -f1)
    BACKUP_SIZE_MB=$(echo "scale=2; $BACKUP_SIZE_BYTES / 1024 / 1024" | bc)
    BACKUP_PERMISSIONS=$(ls -l "$BACKUP_PATH" | awk '{print $1}')
    BACKUP_OWNER=$(ls -l "$BACKUP_PATH" | awk '{print $3":"$4}')
    
    # Calculate compression ratio
    SOURCE_SIZE_BYTES=$(eval "find . $FIND_EXCLUDES -type f -print0" | du -cb --files0-from=- 2>/dev/null | tail -n 1 | cut -f1)
    COMPRESSION_RATIO=$(echo "scale=2; ($SOURCE_SIZE_BYTES - $BACKUP_SIZE_BYTES) * 100 / $SOURCE_SIZE_BYTES" | bc)
    
    echo "   📏 Compressed size: $BACKUP_SIZE_HUMAN ($BACKUP_SIZE_MB MB)"
    echo "   📐 Original size: $SOURCE_SIZE"
    echo "   📉 Compression ratio: ${COMPRESSION_RATIO}% space saved"
    echo "   🔐 Permissions: $BACKUP_PERMISSIONS"
    echo "   👤 Owner: $BACKUP_OWNER"
    echo "   📍 Full path: $(realpath "$BACKUP_PATH")"
    echo ""
    
    # Record end time and calculate duration
    END_TIME=$(date +%s)
    END_DATE=$(date '+%Y-%m-%d %H:%M:%S')
    DURATION=$((END_TIME - START_TIME))
    DURATION_MIN=$((DURATION / 60))
    DURATION_SEC=$((DURATION % 60))
    
    # Final summary
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🎉 BACKUP COMPLETED SUCCESSFULLY!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📋 Summary:"
    echo "   📁 Backup file: $BACKUP_FILENAME"
    echo "   📍 Location: $(realpath "$BACKUP_PATH")"
    echo "   📏 Size: $BACKUP_SIZE_HUMAN ($BACKUP_SIZE_MB MB)"
    echo "   📊 Files backed up: $BACKUP_FILE_COUNT"
    echo "   📁 Directories backed up: $BACKUP_DIR_COUNT"
    echo "   📉 Space saved: ${COMPRESSION_RATIO}%"
    echo "   ⏱️  Duration: ${DURATION_MIN}m ${DURATION_SEC}s (${DURATION} seconds total)"
    echo "   🕐 Started: $START_DATE"
    echo "   🕐 Finished: $END_DATE"
    echo ""
    
    # Check for any verification issues
    if [ ${#MISSING_FILES[@]} -gt 0 ]; then
        echo "⚠️  WARNING: Some critical files are missing from backup:"
        printf "   ❌ %s\n" "${MISSING_FILES[@]}"
        echo ""
    fi
    
    # List all backups in directory
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📋 All backups in backup directory:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if ls -lh "$BACKUP_DIR"/*.tar.* 2>/dev/null | tail -n +2; then
        echo ""
        TOTAL_BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
        BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/*.tar.* 2>/dev/null | wc -l)
        echo "   📊 Total backups: $BACKUP_COUNT"
        echo "   💽 Total backup space used: $TOTAL_BACKUP_SIZE"
    else
        echo "   ℹ️  This is the first backup"
    fi
    echo ""
    
    # Restoration instructions
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📖 Restoration Instructions:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "   To restore this backup, run:"
    echo "   $ tar -xJf $BACKUP_PATH -C /path/to/restore/directory"
    echo ""
    echo "   To list contents without extracting:"
    echo "   $ tar -tJf $BACKUP_PATH | less"
    echo ""
    echo "   To extract a specific file:"
    echo "   $ tar -xJf $BACKUP_PATH path/to/specific/file"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Final verification status
    if [ ${#MISSING_FILES[@]} -eq 0 ]; then
        echo "✅ All verifications passed - Backup is complete and verified!"
        exit 0
    else
        echo "⚠️  Backup completed with warnings - Some critical files missing"
        exit 1
    fi
    
else
    echo ""
    echo "❌ Backup failed!"
    echo "   Check the error messages above for details."
    exit 1
fi
