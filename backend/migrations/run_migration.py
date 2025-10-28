#!/usr/bin/env python3
"""
ShadowRealms AI - Database Migration Runner
Applies SQL migration files to the database
"""

import sys
import os
import sqlite3
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import get_db

def run_migration(migration_file):
    """Run a SQL migration file"""
    print(f"\n{'='*70}")
    print(f"🔧 Running Migration: {migration_file}")
    print(f"{'='*70}\n")
    
    # Read migration file
    migration_path = Path(__file__).parent / migration_file
    if not migration_path.exists():
        print(f"❌ Migration file not found: {migration_path}")
        return False
    
    with open(migration_path, 'r') as f:
        migration_sql = f.read()
    
    # Remove comments first
    lines_without_comments = []
    for line in migration_sql.split('\n'):
        # Remove inline comments
        if '--' in line:
            line = line[:line.index('--')]
        if line.strip():
            lines_without_comments.append(line)
    
    # Join and split by semicolons
    clean_sql = '\n'.join(lines_without_comments)
    statements = [s.strip() for s in clean_sql.split(';') if s.strip()]
    
    # Execute statements
    conn = get_db()
    cursor = conn.cursor()
    
    success_count = 0
    error_count = 0
    
    for i, statement in enumerate(statements, 1):
        try:
            # Skip verification SELECTs for now
            if statement.strip().upper().startswith('SELECT'):
                continue
            
            cursor.execute(statement)
            success_count += 1
            print(f"✅ Statement {i}/{len(statements)}: OK")
        except sqlite3.OperationalError as e:
            # Check if error is "column already exists" - that's ok
            if 'duplicate column name' in str(e).lower() or 'already exists' in str(e).lower():
                print(f"⚠️  Statement {i}/{len(statements)}: Already applied (skipped)")
                success_count += 1
            else:
                print(f"❌ Statement {i}/{len(statements)}: ERROR - {e}")
                error_count += 1
        except Exception as e:
            print(f"❌ Statement {i}/{len(statements)}: ERROR - {e}")
            error_count += 1
    
    conn.commit()
    
    print(f"\n{'='*70}")
    print(f"📊 Migration Summary:")
    print(f"   ✅ Successful: {success_count}")
    print(f"   ❌ Errors: {error_count}")
    print(f"{'='*70}\n")
    
    # Verify tables
    print("🔍 Verifying tables...")
    tables_to_check = ['locations', 'character_locations', 'dice_rolls', 'dice_roll_templates']
    
    for table in tables_to_check:
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (table,))
        exists = cursor.fetchone()[0]
        if exists:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            row_count = cursor.fetchone()[0]
            print(f"   ✅ {table}: exists ({row_count} rows)")
        else:
            print(f"   ❌ {table}: NOT FOUND")
    
    print(f"\n{'='*70}")
    if error_count == 0:
        print("✅ Migration completed successfully!")
    else:
        print(f"⚠️  Migration completed with {error_count} errors")
    print(f"{'='*70}\n")
    
    return error_count == 0

if __name__ == '__main__':
    migration_file = sys.argv[1] if len(sys.argv) > 1 else 'add_locations_and_dice.sql'
    success = run_migration(migration_file)
    sys.exit(0 if success else 1)

