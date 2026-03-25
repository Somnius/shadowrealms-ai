#!/usr/bin/env python3
"""
ShadowRealms AI - Database Module
SQLite database management for characters, campaigns, and user data
"""

import sqlite3
import psycopg2
import psycopg2.extras
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import os

logger = logging.getLogger(__name__)

def get_db():
    """Get database connection (PostgreSQL or SQLite based on DATABASE_TYPE env var)"""
    from config import Config
    
    db_type = os.getenv('DATABASE_TYPE', 'sqlite').lower()
    
    if db_type == 'postgresql':
        # PostgreSQL connection
        logger.info("Connecting to PostgreSQL database...")
        conn = psycopg2.connect(
            dbname=os.getenv('DATABASE_NAME', 'shadowrealms_db'),
            user=os.getenv('DATABASE_USER', 'shadowrealms'),
            password=os.getenv('DATABASE_PASSWORD', ''),
            host=os.getenv('DATABASE_HOST', 'localhost'),
            port=os.getenv('DATABASE_PORT', '5432'),
        )
        # Use RealDictCursor for dict-like rows (similar to SQLite's Row)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
    else:
        # SQLite connection (fallback)
        db_path = Config.DATABASE
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        
        # CRITICAL: Enable foreign key constraints for CASCADE deletes
        conn.execute("PRAGMA foreign_keys = ON")
        
        return conn


def _pg_table_exists(cursor, table: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        (table,),
    )
    row = cursor.fetchone()
    return bool(row and row.get("exists"))


def _pg_table_columns(cursor, table: str) -> set:
    cursor.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    )
    return {r["column_name"] for r in cursor.fetchall()}


def ensure_users_display_timezone_column(cursor):
    """Add users.display_timezone (IANA name) if missing."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_timezone TEXT"
        )
    else:
        cursor.execute("PRAGMA table_info(users)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "display_timezone" not in cols:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN display_timezone TEXT"
            )


def ensure_messages_ai_message_kind_column(cursor):
    """Tag /ai slash user+assistant rows for cleanup (messages.ai_message_kind)."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS ai_message_kind TEXT"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(messages)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "ai_message_kind" not in cols:
            cursor.execute(
                "ALTER TABLE messages ADD COLUMN ai_message_kind TEXT"
            )


def ensure_locations_dice_leniency_floor_column(cursor):
    """Per-room Storyteller leniency (minimum die floor); NULL = normal RNG."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS dice_leniency_floor INTEGER"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='locations'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(locations)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "dice_leniency_floor" not in cols:
            cursor.execute(
                "ALTER TABLE locations ADD COLUMN dice_leniency_floor INTEGER"
            )


def ensure_character_portrait_url_column(cursor):
    """Add characters.portrait_url if missing (PostgreSQL and SQLite)."""
    db_type = os.getenv('DATABASE_TYPE', 'sqlite').lower()
    if db_type == 'postgresql':
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS portrait_url TEXT"
        )
    else:
        cursor.execute("PRAGMA table_info(characters)")
        cols = [row['name'] for row in cursor.fetchall()]
        if 'portrait_url' not in cols:
            cursor.execute(
                "ALTER TABLE characters ADD COLUMN portrait_url TEXT"
            )


def ensure_dice_tables(cursor, db_kind: str) -> None:
    """
    Create dice_rolls / dice_roll_templates if missing.
    routes/dice.py INSERTs into dice_rolls; without this table rolls return 500.
    """
    if db_kind == 'postgresql':
        # Older DBs had dice_rolls(dice_notation, result_total, created_at, …).
        # CREATE IF NOT EXISTS never upgraded them — rename away and create the Storyteller schema.
        LEGACY_ROLLS = "dice_rolls_legacy_d20_notation"
        LEGACY_TEMPL = "dice_roll_templates_legacy_d20_notation"

        if _pg_table_exists(cursor, "dice_rolls"):
            roll_cols = _pg_table_columns(cursor, "dice_rolls")
            if "roll_type" not in roll_cols:
                logger.warning(
                    "PostgreSQL: renaming legacy dice_rolls → %s (missing roll_type column)",
                    LEGACY_ROLLS,
                )
                cursor.execute(f'ALTER TABLE dice_rolls RENAME TO "{LEGACY_ROLLS}"')

        if _pg_table_exists(cursor, "dice_roll_templates"):
            tmpl_cols = _pg_table_columns(cursor, "dice_roll_templates")
            if "dice_pool_formula" not in tmpl_cols or "is_system" not in tmpl_cols:
                logger.warning(
                    "PostgreSQL: renaming legacy dice_roll_templates → %s",
                    LEGACY_TEMPL,
                )
                cursor.execute(f'ALTER TABLE dice_roll_templates RENAME TO "{LEGACY_TEMPL}"')

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dice_roll_templates (
                id BIGSERIAL PRIMARY KEY,
                campaign_id INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
                name TEXT NOT NULL DEFAULT '',
                description TEXT,
                dice_pool_formula TEXT,
                default_difficulty INTEGER DEFAULT 6,
                created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                is_system INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dice_rolls (
                id BIGSERIAL PRIMARY KEY,
                campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
                roll_type TEXT NOT NULL,
                action_description TEXT NOT NULL,
                dice_pool INTEGER NOT NULL,
                difficulty INTEGER NOT NULL,
                results TEXT NOT NULL,
                successes INTEGER NOT NULL,
                is_botch BOOLEAN NOT NULL DEFAULT FALSE,
                is_critical BOOLEAN NOT NULL DEFAULT FALSE,
                modifiers TEXT,
                rolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    else:
        # location_id: no FK here — SQLite migrate order may not have `locations` yet
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dice_rolls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                location_id INTEGER,
                user_id INTEGER NOT NULL,
                character_id INTEGER,
                roll_type TEXT NOT NULL,
                action_description TEXT NOT NULL,
                dice_pool INTEGER NOT NULL,
                difficulty INTEGER NOT NULL,
                results TEXT NOT NULL,
                successes INTEGER NOT NULL,
                is_botch INTEGER NOT NULL DEFAULT 0,
                is_critical INTEGER NOT NULL DEFAULT 0,
                modifiers TEXT,
                rolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE SET NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dice_roll_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                name TEXT NOT NULL DEFAULT '',
                description TEXT,
                dice_pool_formula TEXT,
                default_difficulty INTEGER DEFAULT 6,
                created_by INTEGER,
                is_system INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
    logger.info("dice_rolls / dice_roll_templates verified")


def migrate_db():
    """Migrate database schema if needed"""
    logger.info("Checking database migrations...")
    
    if os.getenv('DATABASE_TYPE', 'sqlite').lower() == 'postgresql':
        logger.info("PostgreSQL detected — ensuring portrait column and dice tables")
        conn = get_db()
        try:
            cursor = conn.cursor()
            ensure_users_display_timezone_column(cursor)
            ensure_messages_ai_message_kind_column(cursor)
            ensure_locations_dice_leniency_floor_column(cursor)
            ensure_character_portrait_url_column(cursor)
            ensure_dice_tables(cursor, 'postgresql')
            conn.commit()
        except Exception as e:
            logger.error(f"PostgreSQL schema ensure failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
        return
    
    # SQLite migrations
    conn = get_db()
    try:
        cursor = conn.cursor()
        ensure_users_display_timezone_column(cursor)

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
        
        # Check if messages table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        if not cursor.fetchone():
            logger.info("Creating messages table...")
            cursor.execute('''
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    character_id INTEGER,
                    message_type TEXT NOT NULL DEFAULT 'ic',
                    content TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
                    FOREIGN KEY (location_id) REFERENCES locations (id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE SET NULL
                )
            ''')
            # Create index for faster queries
            cursor.execute('''
                CREATE INDEX idx_messages_location 
                ON messages(campaign_id, location_id, created_at DESC)
            ''')
            conn.commit()
            logger.info("✅ messages table created")
        
        # Check if npcs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='npcs'")
        if not cursor.fetchone():
            logger.info("Creating npcs table...")
            cursor.execute('''
                CREATE TABLE npcs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    location_id INTEGER,
                    name TEXT NOT NULL,
                    type TEXT,
                    description TEXT,
                    personality TEXT,
                    faction TEXT,
                    npc_data TEXT,
                    created_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
                    FOREIGN KEY (location_id) REFERENCES locations (id) ON DELETE SET NULL,
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
            ''')
            # Create index for location lookups
            cursor.execute('''
                CREATE INDEX idx_npcs_location 
                ON npcs(campaign_id, location_id)
            ''')
            conn.commit()
            logger.info("✅ npcs table created")
        
        # Check if npc_messages table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='npc_messages'")
        if not cursor.fetchone():
            logger.info("Creating npc_messages table...")
            cursor.execute('''
                CREATE TABLE npc_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    npc_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    campaign_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (npc_id) REFERENCES npcs (id) ON DELETE CASCADE,
                    FOREIGN KEY (location_id) REFERENCES locations (id) ON DELETE CASCADE,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE
                )
            ''')
            # Create index for NPC history lookups
            cursor.execute('''
                CREATE INDEX idx_npc_messages 
                ON npc_messages(npc_id, created_at DESC)
            ''')
            conn.commit()
            logger.info("✅ npc_messages table created")
        
        # Check if combat_encounters table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='combat_encounters'")
        if not cursor.fetchone():
            logger.info("Creating combat_encounters table...")
            cursor.execute('''
                CREATE TABLE combat_encounters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    initiative_order TEXT,
                    round_number INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
                    FOREIGN KEY (location_id) REFERENCES locations (id) ON DELETE CASCADE
                )
            ''')
            conn.commit()
            logger.info("✅ combat_encounters table created")
        
        # Check if combat_participants table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='combat_participants'")
        if not cursor.fetchone():
            logger.info("Creating combat_participants table...")
            cursor.execute('''
                CREATE TABLE combat_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    encounter_id INTEGER NOT NULL,
                    character_id INTEGER,
                    npc_id INTEGER,
                    initiative INTEGER DEFAULT 0,
                    current_hp INTEGER,
                    max_hp INTEGER,
                    conditions TEXT,
                    FOREIGN KEY (encounter_id) REFERENCES combat_encounters (id) ON DELETE CASCADE,
                    FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE CASCADE,
                    FOREIGN KEY (npc_id) REFERENCES npcs (id) ON DELETE CASCADE
                )
            ''')
            conn.commit()
            logger.info("✅ combat_participants table created")
        
        # Check if relationships table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='relationships'")
        if not cursor.fetchone():
            logger.info("Creating relationships table...")
            cursor.execute('''
                CREATE TABLE relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    entity1_type TEXT NOT NULL,
                    entity1_id INTEGER NOT NULL,
                    entity2_type TEXT NOT NULL,
                    entity2_id INTEGER NOT NULL,
                    relationship_type TEXT NOT NULL,
                    strength INTEGER DEFAULT 0,
                    notes TEXT,
                    last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE
                )
            ''')
            # Create index for relationship lookups
            cursor.execute('''
                CREATE INDEX idx_relationships 
                ON relationships(campaign_id, entity1_type, entity1_id)
            ''')
            conn.commit()
            logger.info("✅ relationships table created")
        
        # Check if location_connections table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='location_connections'")
        if not cursor.fetchone():
            logger.info("Creating location_connections table...")
            cursor.execute('''
                CREATE TABLE location_connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location1_id INTEGER NOT NULL,
                    location2_id INTEGER NOT NULL,
                    connection_type TEXT DEFAULT 'path',
                    description TEXT,
                    is_bidirectional BOOLEAN DEFAULT 1,
                    FOREIGN KEY (location1_id) REFERENCES locations (id) ON DELETE CASCADE,
                    FOREIGN KEY (location2_id) REFERENCES locations (id) ON DELETE CASCADE
                )
            ''')
            conn.commit()
            logger.info("✅ location_connections table created")
        
        # Check if location_deletion_log table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='location_deletion_log'")
        if not cursor.fetchone():
            logger.info("Creating location_deletion_log table...")
            cursor.execute('''
                CREATE TABLE location_deletion_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location_id INTEGER NOT NULL,
                    campaign_id INTEGER NOT NULL,
                    location_name TEXT NOT NULL,
                    location_type TEXT NOT NULL,
                    location_description TEXT,
                    deleted_by INTEGER NOT NULL,
                    deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
                    FOREIGN KEY (deleted_by) REFERENCES users (id)
                )
            ''')
            # Create index for audit queries
            cursor.execute('''
                CREATE INDEX idx_deletion_log_campaign 
                ON location_deletion_log(campaign_id, deleted_at DESC)
            ''')
            conn.commit()
            logger.info("✅ location_deletion_log table created")
        
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

        ensure_messages_ai_message_kind_column(cursor)
        ensure_locations_dice_leniency_floor_column(cursor)
        ensure_dice_tables(cursor, 'sqlite')
        conn.commit()
        conn.close()
        logger.info("✅ Database migration completed")
        
    except Exception as e:
        logger.error(f"Migration error: {e}")
        conn.close()
        raise

def init_db():
    """Initialize database with required tables"""
    logger.info("Initializing database...")
    
    # For PostgreSQL, schema is already initialized via init_postgresql_schema.sql
    # Skip schema creation to avoid SQLite-specific syntax errors
    if os.getenv('DATABASE_TYPE', 'sqlite').lower() == 'postgresql':
        logger.info("PostgreSQL detected - schema already initialized")
        return
    
    # SQLite schema initialization
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
    # Skip test if using PostgreSQL (this test is SQLite-specific)
    import os
    if os.getenv('DATABASE_TYPE', 'sqlite').lower() == 'postgresql':
        print("⏭️  Skipping SQLite-specific database tests (PostgreSQL is configured)")
        return True
    
    print("🧪 Testing Database Module (SQLite)...")
    
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
            db_type = get_database_type()
            if db_type == 'postgresql':
                cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                tables = [row['tablename'] for row in cursor.fetchall()]
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row['name'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
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
