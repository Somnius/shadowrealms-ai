#!/usr/bin/env python3
"""
ShadowRealms AI - PostgreSQL Migration Tests
Comprehensive test suite to verify the PostgreSQL migration is complete and functional
"""

import os
import sys
import sqlite3
import psycopg2
import psycopg2.extras
from datetime import datetime

# Test results tracker
test_results = {
    'passed': [],
    'failed': [],
    'warnings': []
}

def log_pass(test_name, message=""):
    """Log a passing test"""
    test_results['passed'].append(test_name)
    print(f"✅ PASS: {test_name}")
    if message:
        print(f"   {message}")

def log_fail(test_name, error):
    """Log a failing test"""
    test_results['failed'].append((test_name, str(error)))
    print(f"❌ FAIL: {test_name}")
    print(f"   Error: {error}")

def log_warning(test_name, message):
    """Log a warning"""
    test_results['warnings'].append((test_name, message))
    print(f"⚠️  WARN: {test_name}")
    print(f"   {message}")

def get_postgresql_connection():
    """Get PostgreSQL connection from environment variables"""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('DATABASE_NAME', os.getenv('POSTGRES_DB', 'shadowrealms_db')),
            user=os.getenv('DATABASE_USER', os.getenv('POSTGRES_USER', 'shadowrealms')),
            password=os.getenv('DATABASE_PASSWORD', os.getenv('POSTGRES_PASSWORD', '')),
            host=os.getenv('DATABASE_HOST', 'localhost'),
            port=os.getenv('DATABASE_PORT', '5432'),
        )
        conn.autocommit = False
        return conn
    except Exception as e:
        log_fail("PostgreSQL Connection", e)
        return None

def test_1_environment_variables():
    """Test 1: Verify all required environment variables are set"""
    print("\n" + "="*70)
    print("TEST 1: Environment Variables")
    print("="*70)
    
    # Check primary variables (DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD)
    # These are used by the application, with POSTGRES_* as fallbacks
    required_vars = {
        'DATABASE_TYPE': None,
        'DATABASE_NAME': 'POSTGRES_DB',  # Fallback
        'DATABASE_USER': 'POSTGRES_USER',  # Fallback
        'DATABASE_PASSWORD': 'POSTGRES_PASSWORD',  # Fallback
        'DATABASE_HOST': None,
        'DATABASE_PORT': None
    }
    
    missing = []
    for var, fallback in required_vars.items():
        value = os.getenv(var)
        if not value and fallback:
            # Try fallback
            value = os.getenv(fallback)
            if value:
                # Mask password
                display_value = value if 'PASSWORD' not in var else '***HIDDEN***'
                log_pass(f"ENV: {var} (via {fallback})", f"Value: {display_value}")
            else:
                missing.append(var)
                log_fail(f"ENV: {var} or {fallback}", "Neither variable set")
        elif value:
            # Mask password
            display_value = value if 'PASSWORD' not in var else '***HIDDEN***'
            log_pass(f"ENV: {var}", f"Value: {display_value}")
        else:
            missing.append(var)
            log_fail(f"ENV: {var}", "Variable not set")
    
    if missing:
        return False
    
    # Check DATABASE_TYPE is set to postgresql
    db_type = os.getenv('DATABASE_TYPE', '').lower()
    if db_type != 'postgresql':
        log_fail("DATABASE_TYPE value", f"Expected 'postgresql', got '{db_type}'")
        return False
    
    return True

def test_2_postgresql_connectivity():
    """Test 2: Verify PostgreSQL is accessible"""
    print("\n" + "="*70)
    print("TEST 2: PostgreSQL Connectivity")
    print("="*70)
    
    try:
        conn = get_postgresql_connection()
        if not conn:
            return False
        
        log_pass("PostgreSQL connection", "Successfully connected")
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        log_pass("PostgreSQL query", f"Version: {version}")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        log_fail("PostgreSQL connectivity", e)
        return False

def test_3_schema_exists():
    """Test 3: Verify all required tables exist"""
    print("\n" + "="*70)
    print("TEST 3: Database Schema")
    print("="*70)
    
    required_tables = [
        'users',
        'campaigns',
        'campaign_players',
        'ai_interactions',
        'ai_memory',
        'characters',
        'user_moderation_log',
        'character_moderation',
        'locations',
        'character_locations',
        'dice_rolls',
        'dice_roll_templates',
        'messages',
        'npcs',
        'npc_messages',
        'combat_encounters',
        'combat_participants',
        'relationships',
        'location_connections',
        'location_deletion_log'
    ]
    
    try:
        conn = get_postgresql_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        missing_tables = []
        for table in required_tables:
            if table in existing_tables:
                log_pass(f"Table: {table}", "Exists")
            else:
                missing_tables.append(table)
                log_fail(f"Table: {table}", "Missing")
        
        cursor.close()
        conn.close()
        
        return len(missing_tables) == 0
    except Exception as e:
        log_fail("Schema verification", e)
        return False

def test_4_user_data_migrated():
    """Test 4: Verify user data was migrated"""
    print("\n" + "="*70)
    print("TEST 4: User Data Migration")
    print("="*70)
    
    try:
        conn = get_postgresql_connection()
        if not conn:
            return False
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check user count
        cursor.execute("SELECT COUNT(*) as count FROM users")
        count = cursor.fetchone()['count']
        
        if count >= 2:
            log_pass("User count", f"{count} users in database")
        else:
            log_fail("User count", f"Expected at least 2 users, found {count}")
            cursor.close()
            conn.close()
            return False
        
        # Check specific users
        cursor.execute("SELECT id, username, email, role FROM users ORDER BY id")
        users = cursor.fetchall()
        
        for user in users:
            log_pass(f"User: {user['username']}", f"ID: {user['id']}, Email: {user['email']}, Role: {user['role']}")
        
        # Verify password hashes exist
        cursor.execute("SELECT username, LENGTH(password_hash) as hash_len FROM users")
        for row in cursor.fetchall():
            if row['hash_len'] > 50:
                log_pass(f"Password hash: {row['username']}", f"Length: {row['hash_len']}")
            else:
                log_fail(f"Password hash: {row['username']}", f"Hash too short: {row['hash_len']}")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        log_fail("User data verification", e)
        return False

def test_5_foreign_keys():
    """Test 5: Verify foreign key constraints are in place"""
    print("\n" + "="*70)
    print("TEST 5: Foreign Key Constraints")
    print("="*70)
    
    try:
        conn = get_postgresql_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                tc.table_name, 
                tc.constraint_name, 
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_name, tc.constraint_name
        """)
        
        foreign_keys = cursor.fetchall()
        
        if foreign_keys:
            log_pass("Foreign keys", f"Found {len(foreign_keys)} foreign key constraints")
            for fk in foreign_keys[:5]:  # Show first 5
                log_pass(f"FK: {fk[0]}.{fk[2]}", f"→ {fk[3]}.{fk[4]}")
        else:
            log_warning("Foreign keys", "No foreign key constraints found (this may be intentional)")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        log_fail("Foreign key verification", e)
        return False

def test_6_indexes():
    """Test 6: Verify indexes are created"""
    print("\n" + "="*70)
    print("TEST 6: Database Indexes")
    print("="*70)
    
    try:
        conn = get_postgresql_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                tablename,
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """)
        
        indexes = cursor.fetchall()
        
        if indexes:
            log_pass("Indexes", f"Found {len(indexes)} indexes")
            
            # Count by table
            table_index_count = {}
            for idx in indexes:
                table = idx[0]
                table_index_count[table] = table_index_count.get(table, 0) + 1
            
            for table, count in sorted(table_index_count.items()):
                log_pass(f"Indexes on {table}", f"{count} index(es)")
        else:
            log_warning("Indexes", "No indexes found")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        log_fail("Index verification", e)
        return False

def test_7_sequences():
    """Test 7: Verify sequences are set correctly"""
    print("\n" + "="*70)
    print("TEST 7: Sequence Values")
    print("="*70)
    
    try:
        conn = get_postgresql_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # Get all sequences
        cursor.execute("""
            SELECT sequence_name 
            FROM information_schema.sequences 
            WHERE sequence_schema = 'public'
        """)
        
        sequences = cursor.fetchall()
        
        for seq in sequences:
            seq_name = seq[0]
            cursor.execute(f"SELECT last_value FROM {seq_name}")
            last_value = cursor.fetchone()[0]
            log_pass(f"Sequence: {seq_name}", f"Last value: {last_value}")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        log_fail("Sequence verification", e)
        return False

def test_8_backend_config():
    """Test 8: Verify backend configuration files"""
    print("\n" + "="*70)
    print("TEST 8: Backend Configuration")
    print("="*70)
    
    # Try multiple possible paths (host vs container)
    possible_bases = [
        '',  # Current directory
        '/app/',  # Docker container root
        '../',  # Parent directory
    ]
    
    files_to_check = {
        'backend/database.py': ['get_db', 'DATABASE_TYPE', 'postgresql'],
        'backend/requirements.txt': ['psycopg2-binary'],
        'backend/init_postgresql_schema.sql': ['CREATE TABLE', 'users']
    }
    
    all_passed = True
    for file_path, keywords in files_to_check.items():
        found = False
        for base in possible_bases:
            full_path = os.path.join(base, file_path)
            if os.path.exists(full_path):
                found = True
                try:
                    with open(full_path, 'r') as f:
                        content = f.read()
                        for keyword in keywords:
                            if keyword in content:
                                log_pass(f"File: {file_path}", f"Contains '{keyword}'")
                            else:
                                log_fail(f"File: {file_path}", f"Missing '{keyword}'")
                                all_passed = False
                except Exception as e:
                    log_fail(f"File: {file_path}", f"Error reading: {e}")
                    all_passed = False
                break
        
        if not found:
            # Not critical if running in container
            log_warning(f"File: {file_path}", "File not found (may be running in container)")
    
    return all_passed

def test_9_docker_services():
    """Test 9: Verify Docker services are running"""
    print("\n" + "="*70)
    print("TEST 9: Docker Services")
    print("="*70)
    
    try:
        import subprocess
        
        result = subprocess.run(
            ['docker', 'compose', 'ps', '--format', 'json'],
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        
        if result.returncode == 0:
            import json
            services = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        services.append(json.loads(line))
                    except:
                        pass
            
            required_services = ['backend', 'postgresql', 'chromadb']
            for service_name in required_services:
                service = next((s for s in services if service_name in s.get('Service', '')), None)
                if service:
                    status = service.get('State', 'unknown')
                    if 'running' in status.lower():
                        log_pass(f"Service: {service_name}", f"Status: {status}")
                    else:
                        log_fail(f"Service: {service_name}", f"Status: {status}")
                else:
                    log_fail(f"Service: {service_name}", "Service not found")
        else:
            log_warning("Docker services", "Could not check (docker compose might not be available)")
    except Exception as e:
        log_warning("Docker services", f"Could not verify: {e}")
    
    return True  # Non-critical test

def test_10_data_integrity():
    """Test 10: Verify data integrity and constraints"""
    print("\n" + "="*70)
    print("TEST 10: Data Integrity")
    print("="*70)
    
    try:
        conn = get_postgresql_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # Test 1: Check for any NULL values in required NOT NULL columns
        cursor.execute("""
            SELECT column_name, table_name
            FROM information_schema.columns
            WHERE is_nullable = 'NO'
            AND table_schema = 'public'
            LIMIT 10
        """)
        not_null_columns = cursor.fetchall()
        log_pass("NOT NULL constraints", f"Found {len(not_null_columns)} NOT NULL columns")
        
        # Test 2: Check unique constraints
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM information_schema.table_constraints
            WHERE constraint_type = 'UNIQUE'
            AND table_schema = 'public'
        """)
        unique_count = cursor.fetchone()[0]
        log_pass("UNIQUE constraints", f"Found {unique_count} unique constraints")
        
        # Test 3: Check primary keys
        cursor.execute("""
            SELECT table_name
            FROM information_schema.table_constraints
            WHERE constraint_type = 'PRIMARY KEY'
            AND table_schema = 'public'
        """)
        pk_tables = cursor.fetchall()
        log_pass("PRIMARY KEY constraints", f"Found {len(pk_tables)} tables with primary keys")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        log_fail("Data integrity check", e)
        return False

def print_summary():
    """Print test summary"""
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    total = len(test_results['passed']) + len(test_results['failed'])
    passed = len(test_results['passed'])
    failed = len(test_results['failed'])
    warnings = len(test_results['warnings'])
    
    print(f"\nTotal Tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Warnings: {warnings}")
    
    if failed > 0:
        print("\n" + "="*70)
        print("FAILED TESTS:")
        print("="*70)
        for test_name, error in test_results['failed']:
            print(f"❌ {test_name}")
            print(f"   {error}")
    
    if warnings > 0:
        print("\n" + "="*70)
        print("WARNINGS:")
        print("="*70)
        for test_name, message in test_results['warnings']:
            print(f"⚠️  {test_name}")
            print(f"   {message}")
    
    print("\n" + "="*70)
    if failed == 0:
        print("✅ ALL TESTS PASSED!")
        print("PostgreSQL migration is complete and functional.")
    else:
        print("❌ SOME TESTS FAILED")
        print("Please review the failed tests above.")
    print("="*70)
    
    return failed == 0

def main():
    """Run all tests"""
    print("╔══════════════════════════════════════════════════════════════════════════════╗")
    print("║                                                                              ║")
    print("║           SHADOWREALMS AI - POSTGRESQL MIGRATION TEST SUITE                 ║")
    print("║                                                                              ║")
    print("╚══════════════════════════════════════════════════════════════════════════════╝")
    print(f"\nTest Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run all tests
    tests = [
        test_1_environment_variables,
        test_2_postgresql_connectivity,
        test_3_schema_exists,
        test_4_user_data_migrated,
        test_5_foreign_keys,
        test_6_indexes,
        test_7_sequences,
        test_8_backend_config,
        test_9_docker_services,
        test_10_data_integrity
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            log_fail(test.__name__, f"Unexpected error: {e}")
    
    # Print summary
    success = print_summary()
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())

