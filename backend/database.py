#!/usr/bin/env python3
"""
ShadowRealms AI - Database Module
SQLite database management for characters, campaigns, and user data
"""

import sqlite3
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import os

logger = logging.getLogger(__name__)

def get_db():
    """Get database connection"""
    from config import Config
    db_path = Config.DATABASE
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    return conn

def migrate_db():
    """Migrate database schema if needed"""
    logger.info("Checking database migrations...")
    
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
        
        # Check if campaign_players table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='campaign_players'")
        if not cursor.fetchone():
            logger.info("Creating campaign_players table...")
            cursor.execute('''
                CREATE TABLE campaign_players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    role TEXT DEFAULT 'player',
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE(campaign_id, user_id)
                )
            ''')
            conn.commit()
            logger.info("✅ campaign_players table created")
        
        # Check if ai_memory table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_memory'")
        if not cursor.fetchone():
            logger.info("Creating ai_memory table...")
            cursor.execute('''
                CREATE TABLE ai_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
                )
            ''')
            conn.commit()
            logger.info("✅ ai_memory table created")
        
        # Check if characters table has the correct schema
        cursor.execute("PRAGMA table_info(characters)")
        columns = [column[1] for column in cursor.fetchall()]
        required_columns = ['system_type', 'attributes', 'skills', 'background', 'merits_flaws', 'updated_at']
        
        if not all(col in columns for col in required_columns):
            logger.info("Updating characters table schema...")
            # Create new table with correct schema
            cursor.execute("""
                CREATE TABLE characters_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    system_type TEXT NOT NULL DEFAULT 'd20',
                    attributes TEXT DEFAULT '{}',
                    skills TEXT DEFAULT '{}',
                    background TEXT DEFAULT '',
                    merits_flaws TEXT DEFAULT '{}',
                    user_id INTEGER NOT NULL,
                    campaign_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            
            # Copy existing data
            cursor.execute("""
                INSERT INTO characters_new (id, name, user_id, campaign_id, created_at, updated_at)
                SELECT id, name, user_id, campaign_id, created_at, last_updated
                FROM characters
            """)
            
            # Drop old table and rename new one
            cursor.execute("DROP TABLE characters")
            cursor.execute("ALTER TABLE characters_new RENAME TO characters")
            conn.commit()
            logger.info("✅ characters table schema updated")
        
        conn.close()
        logger.info("✅ Database migration completed")
        
    except Exception as e:
        logger.error(f"Migration error: {e}")
        conn.close()
        raise

def init_db():
    """Initialize database with required tables"""
    logger.info("Initializing database...")
    
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
                character_data TEXT,  -- JSON data for character stats
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
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def test_database_module():
    """Standalone test function for Database Module"""
    print("🧪 Testing Database Module...")
    
    try:
        # Test 1: Test database connection (with local path for standalone testing)
        print("  ✓ Testing database connection...")
        
        # Override database path for standalone testing
        import tempfile
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        # Temporarily modify the database path
        from config import Config
        original_db_path = Config.DATABASE
        Config.DATABASE = temp_db.name
        
        try:
            # Test 2: Test database initialization
            print("  ✓ Testing database initialization...")
            init_db()
            print("  ✓ Database initialization successful")
            
            # Get database connection
            conn = get_db()
            print("  ✓ Database connection successful")
            
            # Test 3: Test table creation
            print("  ✓ Testing table creation...")
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            expected_tables = ['users', 'campaigns', 'characters', 'campaign_players', 'ai_interactions']
            
            for table in expected_tables:
                if table in tables:
                    print(f"    ✓ Table '{table}' exists")
                else:
                    print(f"    ❌ Table '{table}' missing")
                    return False
            
            # Test 4: Test basic operations
            print("  ✓ Testing basic database operations...")
            
            # Insert test user
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, role)
                VALUES (?, ?, ?, ?)
            ''', ('testuser', 'test@example.com', 'hash123', 'player'))
            
            # Insert test campaign
            cursor.execute('''
                INSERT INTO campaigns (name, description, game_system, created_by)
                VALUES (?, ?, ?, ?)
            ''', ('Test Campaign', 'A test campaign', 'd20', 1))
            
            # Verify insertions
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM campaigns")
            campaign_count = cursor.fetchone()[0]
            
            print(f"    ✓ Users: {user_count}, Campaigns: {campaign_count}")
            
            # Clean up test data
            cursor.execute("DELETE FROM campaigns WHERE name = 'Test Campaign'")
            cursor.execute("DELETE FROM users WHERE username = 'testuser'")
            conn.commit()
            
            print("  ✓ Basic operations test successful")
            
            # Test 5: Test error handling
            print("  ✓ Testing error handling...")
            try:
                cursor.execute("SELECT * FROM non_existent_table")
            except sqlite3.OperationalError:
                print("    ✓ Error handling working correctly")
            else:
                print("    ❌ Error handling failed")
                return False
            
            conn.close()
            
            # Clean up temporary database
            import os
            os.unlink(temp_db.name)
            
            print("🎉 All Database Module tests passed!")
            return True
            
        finally:
            # Restore original database path
            Config.DATABASE = original_db_path
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    """Run standalone tests if script is executed directly"""
    print("🚀 Running Database Module Standalone Tests")
    print("=" * 50)
    
    success = test_database_module()
    
    print("=" * 50)
    if success:
        print("✅ All tests passed! Module is ready for integration.")
        exit(0)
    else:
        print("❌ Tests failed! Please fix issues before integration.")
        exit(1)
