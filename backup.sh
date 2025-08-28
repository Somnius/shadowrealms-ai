#!/bin/bash

# ShadowRealms AI Backup Script
# Creates compressed backups of the project excluding backup and books directories

set -e

# Configuration
PROJECT_NAME="tg-rpg"
BACKUP_DIR="backup"
EXCLUDE_DIRS=("backup" "books")

# Create timestamp for filename
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M")
BACKUP_FILENAME="${PROJECT_NAME}_${TIMESTAMP}.tar.bz2"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"

# Build exclude arguments for tar
EXCLUDE_ARGS=""
for dir in "${EXCLUDE_DIRS[@]}"; do
    EXCLUDE_ARGS="$EXCLUDE_ARGS --exclude=$dir"
done

echo "🚀 Starting ShadowRealms AI backup..."
echo "📁 Project: $PROJECT_NAME"
echo "📅 Timestamp: $TIMESTAMP"
echo "🎯 Excluding: ${EXCLUDE_DIRS[*]}"
echo "💾 Backup file: $BACKUP_PATH"
echo ""

# Record start time
START_TIME=$(date +%s)

# Count files before backup (excluding excluded directories)
echo "📊 Counting source files..."
SOURCE_FILE_COUNT=$(find . -type f -not -path "./backup/*" -not -path "./books/*" -not -path "./.git/*" | wc -l)
SOURCE_DIR_COUNT=$(find . -type d -not -path "./backup/*" -not -path "./books/*" -not -path "./.git/*" | wc -l)
echo "   📁 Source directories: $SOURCE_DIR_COUNT"
echo "   📄 Source files: $SOURCE_FILE_COUNT"

# Create backup
echo ""
echo "⏳ Creating backup archive..."
tar -cjf "$BACKUP_PATH" $EXCLUDE_ARGS --exclude="*.tar.bz2" --exclude=".git" .

# Check if backup was successful
if [ $? -eq 0 ]; then
    echo "✅ Backup archive created successfully!"
    
    # Verify backup integrity
    echo ""
    echo "🔍 Verifying backup integrity..."
    
    # Test archive can be read
    if tar -tjf "$BACKUP_PATH" > /dev/null 2>&1; then
        echo "   ✅ Archive is readable and not corrupted"
    else
        echo "   ❌ Archive verification failed!"
        exit 1
    fi
    
    # Count files in backup
    BACKUP_FILE_COUNT=$(tar -tjf "$BACKUP_PATH" | grep -v '/$' | wc -l)
    BACKUP_DIR_COUNT=$(tar -tjf "$BACKUP_PATH" | grep '/$' | wc -l)
    
    echo "   📁 Backup directories: $BACKUP_DIR_COUNT"
    echo "   📄 Backup files: $BACKUP_FILE_COUNT"
    
    # Verify file counts match (allowing for some variance due to exclusions)
    if [ $BACKUP_FILE_COUNT -gt 0 ] && [ $BACKUP_FILE_COUNT -le $SOURCE_FILE_COUNT ]; then
        echo "   ✅ File count verification passed"
    else
        echo "   ⚠️  File count mismatch (expected ≤$SOURCE_FILE_COUNT, got $BACKUP_FILE_COUNT)"
    fi
    
    # Check for critical files in backup
    echo ""
    echo "🔍 Verifying critical files in backup..."
    CRITICAL_FILES=("main.py" "config.py" "docker-compose.yml" "requirements.txt" "CHANGELOG.txt")
    MISSING_FILES=()
    
    for file in "${CRITICAL_FILES[@]}"; do
        if tar -tjf "$BACKUP_PATH" | grep -q "$file"; then
            echo "   ✅ $file found in backup"
        else
            echo "   ❌ $file missing from backup!"
            MISSING_FILES+=("$file")
        fi
    done
    
    # Check for excluded directories (should NOT be in backup)
    echo ""
    echo "🔍 Verifying exclusions..."
    for dir in "${EXCLUDE_DIRS[@]}"; do
        if tar -tjf "$BACKUP_PATH" | grep -q "^\./$dir/"; then
            echo "   ❌ $dir directory found in backup (should be excluded)!"
        else
            echo "   ✅ $dir directory properly excluded"
        fi
    done
    
    # Check backup file size and permissions
    echo ""
    echo "📊 Backup file details..."
    BACKUP_SIZE=$(du -h "$BACKUP_PATH" | cut -f1)
    BACKUP_PERMISSIONS=$(ls -l "$BACKUP_PATH" | awk '{print $1}')
    BACKUP_OWNER=$(ls -l "$BACKUP_PATH" | awk '{print $3":"$4}')
    
    echo "   📏 Size: $BACKUP_SIZE"
    echo "   🔐 Permissions: $BACKUP_PERMISSIONS"
    echo "   👤 Owner: $BACKUP_OWNER"
    
    # Record end time and calculate duration
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    echo ""
    echo "🎉 Backup completed successfully!"
    echo "📊 Summary:"
    echo "   📁 File: $BACKUP_PATH"
    echo "   📏 Size: $BACKUP_SIZE"
    echo "   ⏱️  Duration: ${DURATION} seconds"
    echo "   🕐 Started: $(date -d @$START_TIME '+%Y-%m-%d %H:%M:%S')"
    echo "   🕐 Finished: $(date -d @$END_TIME '+%Y-%m-%d %H:%M:%S')"
    
    # Check for any verification issues
    if [ ${#MISSING_FILES[@]} -gt 0 ]; then
        echo ""
        echo "⚠️  Warning: Some critical files are missing from backup:"
        printf "   ❌ %s\n" "${MISSING_FILES[@]}"
    fi
    
    # List backup directory contents
    echo ""
    echo "📋 Backup directory contents:"
    ls -lh "$BACKUP_DIR"/*.tar.bz2 2>/dev/null || echo "   No previous backups found"
    
    # Final verification status
    if [ ${#MISSING_FILES[@]} -eq 0 ]; then
        echo ""
        echo "✅ All verifications passed - Backup is complete and verified!"
        exit 0
    else
        echo ""
        echo "⚠️  Backup completed with warnings - Some critical files missing"
        exit 1
    fi
    
else
    echo "❌ Backup failed!"
    exit 1
fi
