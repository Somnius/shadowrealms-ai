#!/usr/bin/env python3
"""
ShadowRealms AI - SQLite to PostgreSQL Migration Script

This script migrates all data from SQLite to PostgreSQL while preserving:
- All table data and relationships
- Primary key sequences
- Foreign key relationships
- Timestamps and special values

Usage:
    python migrate_sqlite_to_postgresql.py [--dry-run] [--verify]

Options:
    --dry-run   : Show what would be migrated without actually migrating
    --verify    : Verify data integrity after migration
"""

import sqlite3
import psycopg2
import psycopg2.extras
import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Table migration order (respects foreign key dependencies)
TABLE_ORDER = [
    'users',
    'campaigns',
    'campaign_players',
    'characters',
    'locations',
    'messages',
    'ai_interactions',
    'ai_memory',
    'user_moderation_log',
    'character_moderation',
    'character_locations',
    'dice_rolls',
    'dice_roll_templates',
    'npcs',
    'npc_messages',
    'combat_encounters',
    'combat_participants',
    'relationships',
    'location_connections',
    'location_deletion_log',
    'moderation_log',
]

class DatabaseMigrator:
    def __init__(self, sqlite_path: str, dry_run: bool = False):
        self.sqlite_path = sqlite_path
        self.dry_run = dry_run
        self.sqlite_conn = None
        self.pg_conn = None
        self.migration_stats = {}
        
    def connect_sqlite(self):
        """Connect to SQLite database"""
        logger.info(f"Connecting to SQLite: {self.sqlite_path}")
        self.sqlite_conn = sqlite3.connect(self.sqlite_path)
        self.sqlite_conn.row_factory = sqlite3.Row
        logger.info("✅ SQLite connected")
        
    def connect_postgresql(self):
        """Connect to PostgreSQL database"""
        conn_params = {
            'dbname': os.getenv('DATABASE_NAME') or os.getenv('POSTGRES_DB', 'shadowrealms_db'),
            'user': os.getenv('DATABASE_USER') or os.getenv('POSTGRES_USER', 'shadowrealms'),
            'password': os.getenv('DATABASE_PASSWORD') or os.getenv('POSTGRES_PASSWORD', ''),
            'host': os.getenv('DATABASE_HOST', 'localhost'),
            'port': os.getenv('DATABASE_PORT', '5432'),
        }
        
        logger.info(f"Connecting to PostgreSQL: {conn_params['user']}@{conn_params['host']}:{conn_params['port']}/{conn_params['dbname']}")
        self.pg_conn = psycopg2.connect(**conn_params)
        self.pg_conn.autocommit = False
        logger.info("✅ PostgreSQL connected")
        
    def get_table_columns(self, table_name: str) -> List[str]:
        """Get column names for a table from SQLite"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        return columns
        
    def get_table_data(self, table_name: str) -> List[Dict]:
        """Extract all data from a SQLite table"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
        
    def convert_value(self, value: Any, column_name: str = '') -> Any:
        """Convert SQLite value to PostgreSQL-compatible value"""
        # SQLite stores booleans as 0/1, PostgreSQL uses true/false
        # Check if this is likely a boolean column
        boolean_columns = {'is_active', 'is_system', 'is_bidirectional', 'is_botch', 'is_critical'}
        
        if column_name in boolean_columns and isinstance(value, int) and value in (0, 1):
            return bool(value)
        return value
        
    def migrate_table(self, table_name: str) -> Tuple[int, int]:
        """
        Migrate a single table from SQLite to PostgreSQL
        
        Returns:
            (rows_migrated, rows_skipped)
        """
        logger.info(f"📊 Migrating table: {table_name}")
        
        # Check if table exists in SQLite
        cursor = self.sqlite_conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if not cursor.fetchone():
            logger.warning(f"⚠️  Table '{table_name}' not found in SQLite - skipping")
            return 0, 0
        
        # Get data from SQLite
        data = self.get_table_data(table_name)
        
        if not data:
            logger.info(f"   Empty table - nothing to migrate")
            return 0, 0
        
        # Get column names
        columns = list(data[0].keys())
        
        if self.dry_run:
            logger.info(f"   [DRY RUN] Would migrate {len(data)} rows")
            logger.info(f"   Columns: {', '.join(columns)}")
            return len(data), 0
        
        # Prepare INSERT statement for PostgreSQL
        placeholders = ', '.join(['%s'] * len(columns))
        column_names = ', '.join(columns)
        insert_sql = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
        
        # Migrate data
        pg_cursor = self.pg_conn.cursor()
        rows_migrated = 0
        rows_failed = 0
        
        for row in data:
            try:
                values = [self.convert_value(row[col], col) for col in columns]
                pg_cursor.execute(insert_sql, values)
                # Commit each row immediately to avoid losing progress on errors
                self.pg_conn.commit()
                rows_migrated += 1
            except Exception as e:
                # Rollback the failed insert so we can continue
                self.pg_conn.rollback()
                if 'foreign key constraint' in str(e).lower():
                    logger.warning(f"   ⚠️  Skipped orphaned row (foreign key violation)")
                else:
                    logger.error(f"   ❌ Failed to insert row: {e}")
                    logger.error(f"      Row data: {row}")
                rows_failed += 1
                # Continue with other rows
        
        # Update sequence for auto-increment columns (PostgreSQL SERIAL)
        if rows_migrated > 0 and 'id' in columns:
            max_id = max(row['id'] for row in data if row['id'] is not None)
            try:
                pg_cursor.execute(f"SELECT setval('{table_name}_id_seq', {max_id}, true)")
                logger.info(f"   ✅ Updated sequence {table_name}_id_seq to {max_id}")
            except Exception as e:
                logger.warning(f"   ⚠️  Could not update sequence: {e}")
        
        logger.info(f"   ✅ Migrated {rows_migrated} rows (failed: {rows_failed})")
        return rows_migrated, rows_failed
        
    def migrate_all(self):
        """Migrate all tables"""
        logger.info("="* 70)
        logger.info("🚀 Starting SQLite → PostgreSQL Migration")
        logger.info("="* 70)
        
        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No data will be written")
            logger.info("")
        
        total_migrated = 0
        total_failed = 0
        
        try:
            for table in TABLE_ORDER:
                migrated, failed = self.migrate_table(table)
                self.migration_stats[table] = {'migrated': migrated, 'failed': failed}
                total_migrated += migrated
                total_failed += failed
            
            if not self.dry_run:
                logger.info("")
                logger.info("✅ Migration committed (row-by-row commits)")
                # Final commit to ensure everything is persisted
                self.pg_conn.commit()
                logger.info("✅ Final commit successful")
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            if not self.dry_run:
                logger.info("🔄 Rolling back transaction...")
                self.pg_conn.rollback()
            raise
        
        finally:
            logger.info("")
            logger.info("="* 70)
            logger.info("📊 MIGRATION SUMMARY")
            logger.info("="* 70)
            
            for table, stats in self.migration_stats.items():
                if stats['migrated'] > 0 or stats['failed'] > 0:
                    status = "✅" if stats['failed'] == 0 else "⚠️"
                    logger.info(f"{status} {table:30s} {stats['migrated']:6d} rows (failed: {stats['failed']})")
            
            logger.info("-" * 70)
            logger.info(f"Total rows migrated: {total_migrated}")
            logger.info(f"Total rows failed:   {total_failed}")
            logger.info("="* 70)
            
    def verify_migration(self):
        """Verify data integrity after migration"""
        logger.info("")
        logger.info("="* 70)
        logger.info("🔍 VERIFYING MIGRATION")
        logger.info("="* 70)
        
        all_good = True
        
        for table in TABLE_ORDER:
            # Count rows in both databases
            sqlite_cursor = self.sqlite_conn.cursor()
            try:
                sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                sqlite_count = sqlite_cursor.fetchone()[0]
            except Exception:
                # Table doesn't exist in SQLite, skip it
                continue
            
            pg_cursor = self.pg_conn.cursor()
            try:
                pg_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                pg_count = pg_cursor.fetchone()[0]
            except Exception:
                pg_count = 0
            
            if sqlite_count == pg_count:
                logger.info(f"✅ {table:30s} {sqlite_count:6d} rows (match)")
            else:
                logger.error(f"❌ {table:30s} SQLite: {sqlite_count:6d}, PostgreSQL: {pg_count:6d} (MISMATCH)")
                all_good = False
        
        logger.info("="* 70)
        
        if all_good:
            logger.info("✅ All tables verified successfully!")
        else:
            logger.error("❌ Verification found mismatches!")
        
        return all_good
        
    def close(self):
        """Close database connections"""
        if self.sqlite_conn:
            self.sqlite_conn.close()
            logger.info("SQLite connection closed")
        if self.pg_conn:
            self.pg_conn.close()
            logger.info("PostgreSQL connection closed")

def main():
    """Main migration function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate ShadowRealms AI from SQLite to PostgreSQL')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated without actually migrating')
    parser.add_argument('--verify', action='store_true', help='Verify data integrity after migration')
    parser.add_argument('--sqlite-path', default='/app/data/shadowrealms.db', help='Path to SQLite database')
    
    args = parser.parse_args()
    
    # Check if SQLite database exists
    if not os.path.exists(args.sqlite_path):
        logger.error(f"❌ SQLite database not found: {args.sqlite_path}")
        sys.exit(1)
    
    # Create migrator
    migrator = DatabaseMigrator(args.sqlite_path, dry_run=args.dry_run)
    
    try:
        # Connect to databases
        migrator.connect_sqlite()
        migrator.connect_postgresql()
        
        # Run migration
        migrator.migrate_all()
        
        # Verify if requested
        if args.verify and not args.dry_run:
            success = migrator.verify_migration()
            if not success:
                logger.error("❌ Verification failed!")
                sys.exit(1)
        
        logger.info("")
        logger.info("🎉 Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        migrator.close()

if __name__ == '__main__':
    main()

