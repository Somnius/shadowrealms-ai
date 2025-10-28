#!/usr/bin/env python3
"""
ShadowRealms AI - Minimal User Migration Script
Migrates ONLY users from SQLite to PostgreSQL
Campaigns will be recreated manually
"""

import sqlite3
import psycopg2
import psycopg2.extras
import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def migrate_users():
    """Migrate only users table"""
    
    # Connect to SQLite
    sqlite_path = '/app/data/shadowrealms.db'
    logger.info(f"Connecting to SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    
    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(
        dbname=os.getenv('DATABASE_NAME') or os.getenv('POSTGRES_DB', 'shadowrealms_db'),
        user=os.getenv('DATABASE_USER') or os.getenv('POSTGRES_USER'),
        password=os.getenv('DATABASE_PASSWORD') or os.getenv('POSTGRES_PASSWORD'),
        host=os.getenv('DATABASE_HOST', 'localhost'),
        port=os.getenv('DATABASE_PORT', '5432'),
    )
    pg_conn.autocommit = False
    
    logger.info("✅ Connected to both databases")
    
    # Get users from SQLite
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute("SELECT * FROM users")
    users = [dict(row) for row in sqlite_cursor.fetchall()]
    
    logger.info(f"📊 Found {len(users)} users to migrate")
    
    # Migrate users
    pg_cursor = pg_conn.cursor()
    migrated = 0
    
    for user in users:
        try:
            # Convert boolean
            user['is_active'] = bool(user['is_active']) if user['is_active'] in (0, 1) else user['is_active']
            
            pg_cursor.execute("""
                INSERT INTO users (
                    id, username, email, password_hash, role,
                    created_at, last_login, is_active,
                    ban_type, ban_until, ban_reason, banned_by, banned_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                user['id'], user['username'], user['email'], user['password_hash'], user['role'],
                user['created_at'], user['last_login'], user['is_active'],
                user['ban_type'], user['ban_until'], user['ban_reason'], user['banned_by'], user['banned_at']
            ))
            pg_conn.commit()
            logger.info(f"✅ Migrated user: {user['username']} (ID: {user['id']})")
            migrated += 1
        except Exception as e:
            pg_conn.rollback()
            logger.error(f"❌ Failed to migrate user {user['username']}: {e}")
    
    # Update sequence
    if migrated > 0:
        max_id = max(u['id'] for u in users)
        pg_cursor.execute(f"SELECT setval('users_id_seq', {max_id}, true)")
        pg_conn.commit()
        logger.info(f"✅ Updated users_id_seq to {max_id}")
    
    # Verify
    pg_cursor.execute("SELECT id, username, email, role FROM users ORDER BY id")
    pg_users = pg_cursor.fetchall()
    
    logger.info("")
    logger.info("="* 70)
    logger.info("✅ MIGRATION COMPLETE")
    logger.info("="* 70)
    logger.info(f"Migrated {migrated} users:")
    for pg_user in pg_users:
        logger.info(f"  - ID {pg_user[0]}: {pg_user[1]} ({pg_user[2]}) - Role: {pg_user[3]}")
    logger.info("="* 70)
    
    sqlite_conn.close()
    pg_conn.close()
    
    return migrated == len(users)

if __name__ == '__main__':
    try:
        success = migrate_users()
        if success:
            print("\n🎉 User migration successful!")
            print("📝 Next steps:")
            print("   1. Test login with your credentials")
            print("   2. Create new campaigns")
            print("   3. Your rule books are already in ChromaDB - no action needed")
            sys.exit(0)
        else:
            print("\n❌ Migration had errors")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

