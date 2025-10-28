#!/usr/bin/env python3
"""
ShadowRealms AI - Database Module (PostgreSQL-Ready)
Supports both SQLite (legacy/rollback) and PostgreSQL (production)
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
import os

# Import both database drivers
import sqlite3
try:
    import psycopg2
    import psycopg2.extras
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    logging.warning("PostgreSQL driver (psycopg2) not available - SQLite only mode")

logger = logging.getLogger(__name__)

def get_database_type():
    """Get the configured database type from environment"""
    return os.getenv('DATABASE_TYPE', 'sqlite').lower()

def get_db():
    """
    Get database connection based on DATABASE_TYPE environment variable
    
    Returns:
        SQLite3 connection or psycopg2 connection with dict-like row factory
    """
    from config import Config
    db_type = get_database_type()
    
    if db_type == 'postgresql':
        if not POSTGRESQL_AVAILABLE:
            raise RuntimeError("PostgreSQL requested but psycopg2 not installed")
        
        # Build PostgreSQL connection string
        conn_params = {
            'dbname': os.getenv('DATABASE_NAME', os.getenv('POSTGRES_DB', 'shadowrealms_db')),
            'user': os.getenv('DATABASE_USER', os.getenv('POSTGRES_USER', 'shadowrealms')),
            'password': os.getenv('DATABASE_PASSWORD', os.getenv('POSTGRES_PASSWORD', '')),
            'host': os.getenv('DATABASE_HOST', 'localhost'),
            'port': os.getenv('DATABASE_PORT', '5432'),
        }
        
        logger.info(f"Connecting to PostgreSQL: {conn_params['user']}@{conn_params['host']}:{conn_params['port']}/{conn_params['dbname']}")
        
        try:
            conn = psycopg2.connect(**conn_params)
            # Enable dict-like row access
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            logger.info("✅ PostgreSQL connection established")
            return conn
        except psycopg2.Error as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            raise
    
    else:  # SQLite (default/fallback)
        db_path = Config.DATABASE
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        
        # CRITICAL: Enable foreign key constraints for CASCADE deletes
        conn.execute("PRAGMA foreign_keys = ON")
        
        logger.info(f"✅ SQLite connection established: {db_path}")
        return conn

def execute_query(query: str, params: tuple = None, fetch: str = 'all'):
    """
    Execute a database query with automatic connection handling
    
    Args:
        query: SQL query string (use ? for SQLite, %s for PostgreSQL)
        params: Query parameters tuple
        fetch: 'all', 'one', or 'none' (for INSERT/UPDATE/DELETE)
    
    Returns:
        Query results or None
    """
    conn = get_db()
    db_type = get_database_type()
    
    try:
        cursor = conn.cursor()
        
        # Convert placeholders if needed (SQLite uses ?, PostgreSQL uses %s)
        if db_type == 'postgresql' and '?' in query:
            # Convert ? to %s for PostgreSQL
            query = query.replace('?', '%s')
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch == 'all':
            result = cursor.fetchall()
        elif fetch == 'one':
            result = cursor.fetchone()
        else:
            result = None
        
        conn.commit()
        return result
        
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def migrate_db():
    """
    Database migration - Only needed for SQLite
    PostgreSQL uses init_postgresql_schema.sql during container startup
    """
    db_type = get_database_type()
    
    if db_type == 'postgresql':
        logger.info("PostgreSQL detected - migrations handled by init script")
        return
    
    logger.info("Checking SQLite database migrations...")
    
    conn = get_db()
    try:
        cursor = conn.cursor()
        
        # Check if campaigns table has game_system column
        cursor.execute("PRAGMA table_info(campaigns)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'game_system' not in columns:
            # Check if there's a system_type column that should be game_system
            if 'system_type' in columns:
                logger.info("Migrating system_type to game_system...")
                # SQLite doesn't support RENAME COLUMN in older versions, so we need to recreate the table
                cursor.execute("""
                    CREATE TABLE campaigns_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        game_system TEXT NOT NULL DEFAULT 'd20',
                        max_players INTEGER DEFAULT 6,
                        created_by INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1,
                        status TEXT NOT NULL DEFAULT 'active',
                        FOREIGN KEY (created_by) REFERENCES users (id)
                    )
                """)
                
                # Copy data from old table to new table
                cursor.execute("""
                    INSERT INTO campaigns_new (id, name, description, game_system, max_players, created_by, created_at, is_active)
                    SELECT id, name, description, system_type, max_players, created_by, created_at, is_active
                    FROM campaigns
                """)
                
                # Drop old table and rename new table
                cursor.execute("DROP TABLE campaigns")
                cursor.execute("ALTER TABLE campaigns_new RENAME TO campaigns")
                conn.commit()
                logger.info("✅ system_type migrated to game_system")
            else:
                logger.info("Adding game_system column to campaigns table...")
                cursor.execute("ALTER TABLE campaigns ADD COLUMN game_system TEXT NOT NULL DEFAULT 'd20'")
                conn.commit()
                logger.info("✅ game_system column added")
        
        if 'status' not in columns:
            logger.info("Adding status column to campaigns table...")
            cursor.execute("ALTER TABLE campaigns ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
            conn.commit()
            logger.info("✅ status column added")
        
        conn.close()
        logger.info("✅ SQLite database migration completed")
        
    except Exception as e:
        logger.error(f"Migration error: {e}")
        conn.close()
        raise

def init_db():
    """
    Initialize database with required tables
    
    For SQLite: Creates tables directly
    For PostgreSQL: Tables are created by init_postgresql_schema.sql
    """
    db_type = get_database_type()
    
    if db_type == 'postgresql':
        logger.info("PostgreSQL detected - schema initialized by Docker entrypoint")
        # Test connection
        conn = get_db()
        conn.close()
        logger.info("✅ PostgreSQL connection verified")
        return
    
    logger.info("Initializing SQLite database...")
    
    conn = get_db()
    try:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'player',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Campaigns table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                game_system TEXT NOT NULL DEFAULT 'd20',
                max_players INTEGER DEFAULT 6,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
        ''')
        
        # Characters table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                character_class TEXT,
                level INTEGER DEFAULT 1,
                campaign_id INTEGER,
                user_id INTEGER NOT NULL,
                character_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')
        
        # Campaign players table (many-to-many)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS campaign_players (
                campaign_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                role TEXT DEFAULT 'player',
                PRIMARY KEY (campaign_id, user_id),
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # AI interactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                campaign_id INTEGER,
                interaction_type TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response TEXT NOT NULL,
                performance_mode TEXT DEFAULT 'medium',
                tokens_used INTEGER,
                response_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
            )
        ''')
        
        # Commit changes
        conn.commit()
        logger.info("✅ SQLite database initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def test_connection():
    """Test database connection and return status"""
    try:
        db_type = get_database_type()
        conn = get_db()
        
        cursor = conn.cursor()
        
        if db_type == 'postgresql':
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            logger.info(f"✅ PostgreSQL connection successful: {version}")
        else:
            cursor.execute("SELECT sqlite_version();")
            version = cursor.fetchone()[0]
            logger.info(f"✅ SQLite connection successful: version {version}")
        
        conn.close()
        return True, version
        
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False, str(e)

if __name__ == "__main__":
    """Test database connection"""
    print("🚀 Testing Database Module")
    print("=" * 50)
    
    success, info = test_connection()
    
    print("=" * 50)
    if success:
        print(f"✅ Database ready: {info}")
        exit(0)
    else:
        print(f"❌ Database connection failed: {info}")
        exit(1)

