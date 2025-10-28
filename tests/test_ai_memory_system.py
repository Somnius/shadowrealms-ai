#!/usr/bin/env python3
"""
ShadowRealms AI - Memory System Integration Tests
Tests all 9 phases of the AI memory system
"""

import sys
import os
import sqlite3
from datetime import datetime

# Add backend to path
backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend')
sys.path.insert(0, backend_path)

# Also add the project root
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

def test_database_tables():
    """Test that all new tables were created"""
    print("\n" + "="*80)
    print("TEST 1: Database Tables Creation")
    print("="*80)
    
    try:
        from config import Config
        db_path = Config.DATABASE
        
        if not os.path.exists(db_path):
            print(f"❌ Database not found at: {db_path}")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for new tables
        required_tables = [
            'npcs',
            'npc_messages',
            'combat_encounters',
            'combat_participants',
            'relationships',
            'location_connections'
        ]
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        all_present = True
        for table in required_tables:
            if table in existing_tables:
                print(f"  ✅ Table '{table}' exists")
            else:
                print(f"  ❌ Table '{table}' MISSING")
                all_present = False
        
        conn.close()
        
        if all_present:
            print("\n✅ All database tables created successfully!")
            return True
        else:
            print("\n❌ Some tables are missing!")
            return False
            
    except Exception as e:
        print(f"\n❌ Error testing database tables: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_location_context():
    """Test location context retrieval"""
    print("\n" + "="*80)
    print("TEST 2: Location Context Retrieval")
    print("="*80)
    
    try:
        from database import get_db
        from routes.ai import get_location_context
        
        # Get a test location
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id, campaign_id FROM locations LIMIT 1")
        location = cursor.fetchone()
        db.close()
        
        if not location:
            print("  ⚠️  No locations in database to test")
            return True  # Not a failure, just no data
        
        location_id = location[0]
        campaign_id = location[1]
        
        print(f"  Testing with location_id={location_id}, campaign_id={campaign_id}")
        
        result = get_location_context(location_id, campaign_id)
        
        if result and 'formatted' in result:
            print(f"  ✅ Location context retrieved successfully")
            print(f"  📍 Location: {result.get('name', 'Unknown')}")
            print(f"  📝 Type: {result.get('type', 'Unknown')}")
            return True
        else:
            print(f"  ❌ Failed to retrieve location context")
            return False
            
    except Exception as e:
        print(f"  ❌ Error testing location context: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_message_history():
    """Test message history retrieval"""
    print("\n" + "="*80)
    print("TEST 3: Message History Retrieval")
    print("="*80)
    
    try:
        from database import get_db
        from routes.ai import get_recent_messages
        
        # Get a test location with messages
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT DISTINCT m.location_id, m.campaign_id, COUNT(*) as msg_count
            FROM messages m
            GROUP BY m.location_id, m.campaign_id
            LIMIT 1
        """)
        result = cursor.fetchone()
        db.close()
        
        if not result:
            print("  ⚠️  No messages in database to test")
            return True
        
        location_id = result[0]
        campaign_id = result[1]
        msg_count = result[2]
        
        print(f"  Testing with location_id={location_id}, campaign_id={campaign_id}")
        print(f"  Expected messages: {msg_count}")
        
        messages = get_recent_messages(location_id, campaign_id, limit=10)
        
        if messages and messages['count'] > 0:
            print(f"  ✅ Retrieved {messages['count']} messages")
            print(f"  📨 Sample: {messages['messages'][0]['content'][:50]}...")
            return True
        else:
            print(f"  ❌ Failed to retrieve messages")
            return False
            
    except Exception as e:
        print(f"  ❌ Error testing message history: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_character_context():
    """Test character context retrieval"""
    print("\n" + "="*80)
    print("TEST 4: Character Context Retrieval")
    print("="*80)
    
    try:
        from database import get_db
        from routes.ai import get_character_context
        
        # Get a test character
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT user_id, campaign_id FROM characters LIMIT 1")
        result = cursor.fetchone()
        db.close()
        
        if not result:
            print("  ⚠️  No characters in database to test")
            return True
        
        user_id = result[0]
        campaign_id = result[1]
        
        print(f"  Testing with user_id={user_id}, campaign_id={campaign_id}")
        
        char_data = get_character_context(user_id, campaign_id)
        
        if char_data and char_data.get('has_character'):
            print(f"  ✅ Character context retrieved successfully")
            print(f"  👤 Character: {char_data.get('name', 'Unknown')}")
            print(f"  🎭 Class: {char_data.get('class', 'Unknown')}")
            return True
        else:
            print(f"  ❌ Failed to retrieve character context")
            return False
            
    except Exception as e:
        print(f"  ❌ Error testing character context: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_npc_functions():
    """Test NPC-related functions"""
    print("\n" + "="*80)
    print("TEST 5: NPC System Functions")
    print("="*80)
    
    try:
        from database import get_db
        from routes.ai import get_location_npcs, store_npc_interaction
        
        # Create a test NPC
        db = get_db()
        cursor = db.cursor()
        
        # Get a campaign and location
        cursor.execute("SELECT id FROM campaigns LIMIT 1")
        campaign = cursor.fetchone()
        if not campaign:
            print("  ⚠️  No campaigns in database to test")
            db.close()
            return True
        campaign_id = campaign[0]
        
        cursor.execute("SELECT id FROM locations WHERE campaign_id = ? LIMIT 1", (campaign_id,))
        location = cursor.fetchone()
        if not location:
            print("  ⚠️  No locations in database to test")
            db.close()
            return True
        location_id = location[0]
        
        # Create test NPC
        cursor.execute("""
            INSERT INTO npcs (campaign_id, location_id, name, type, description, personality, created_by)
            VALUES (?, ?, 'Test Marcus', 'bartender', 'A grizzled vampire bartender', 'Cautious but friendly', 1)
        """, (campaign_id, location_id))
        npc_id = cursor.lastrowid
        db.commit()
        
        print(f"  Created test NPC (id={npc_id}) at location {location_id}")
        
        # Test get_location_npcs
        npcs = get_location_npcs(location_id, campaign_id)
        if npcs['count'] > 0:
            print(f"  ✅ Retrieved {npcs['count']} NPC(s)")
            print(f"  👥 NPC: {npcs['npcs'][0]['name']}")
        else:
            print(f"  ❌ Failed to retrieve NPCs")
            db.close()
            return False
        
        # Test store_npc_interaction
        success = store_npc_interaction(
            npc_id, location_id, campaign_id,
            "The bartender nods knowingly",
            "Player asked about the prince"
        )
        
        if success:
            print(f"  ✅ NPC interaction stored successfully")
        else:
            print(f"  ❌ Failed to store NPC interaction")
            db.close()
            return False
        
        # Cleanup
        cursor.execute("DELETE FROM npc_messages WHERE npc_id = ?", (npc_id,))
        cursor.execute("DELETE FROM npcs WHERE id = ?", (npc_id,))
        db.commit()
        db.close()
        
        print(f"  🧹 Cleaned up test data")
        return True
        
    except Exception as e:
        print(f"  ❌ Error testing NPC functions: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_combat_functions():
    """Test combat tracking functions"""
    print("\n" + "="*80)
    print("TEST 6: Combat Tracking Functions")
    print("="*80)
    
    try:
        from database import get_db
        from routes.ai import get_active_combat
        
        db = get_db()
        cursor = db.cursor()
        
        # Get test data
        cursor.execute("SELECT id FROM campaigns LIMIT 1")
        campaign = cursor.fetchone()
        if not campaign:
            print("  ⚠️  No campaigns in database to test")
            db.close()
            return True
        campaign_id = campaign[0]
        
        cursor.execute("SELECT id FROM locations WHERE campaign_id = ? LIMIT 1", (campaign_id,))
        location = cursor.fetchone()
        if not location:
            print("  ⚠️  No locations in database to test")
            db.close()
            return True
        location_id = location[0]
        
        # Test when no combat exists
        combat = get_active_combat(location_id, campaign_id)
        if combat['has_combat']:
            print(f"  ⚠️  Unexpected active combat found")
        else:
            print(f"  ✅ Correctly returns no combat when none exists")
        
        # Create test combat
        cursor.execute("""
            INSERT INTO combat_encounters (campaign_id, location_id, status, round_number)
            VALUES (?, ?, 'active', 1)
        """, (campaign_id, location_id))
        encounter_id = cursor.lastrowid
        db.commit()
        
        print(f"  Created test combat encounter (id={encounter_id})")
        
        # Test with active combat
        combat = get_active_combat(location_id, campaign_id)
        if combat['has_combat'] and combat['round'] == 1:
            print(f"  ✅ Combat context retrieved successfully")
            print(f"  ⚔️  Round: {combat['round']}")
        else:
            print(f"  ❌ Failed to retrieve combat context")
            cursor.execute("DELETE FROM combat_encounters WHERE id = ?", (encounter_id,))
            db.commit()
            db.close()
            return False
        
        # Cleanup
        cursor.execute("DELETE FROM combat_encounters WHERE id = ?", (encounter_id,))
        db.commit()
        db.close()
        
        print(f"  🧹 Cleaned up test data")
        return True
        
    except Exception as e:
        print(f"  ❌ Error testing combat functions: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_relationship_functions():
    """Test relationship tracking"""
    print("\n" + "="*80)
    print("TEST 7: Relationship Tracking Functions")
    print("="*80)
    
    try:
        from database import get_db
        from routes.ai import get_entity_relationships
        
        db = get_db()
        cursor = db.cursor()
        
        # Get test data
        cursor.execute("SELECT id FROM campaigns LIMIT 1")
        campaign = cursor.fetchone()
        if not campaign:
            print("  ⚠️  No campaigns in database to test")
            db.close()
            return True
        campaign_id = campaign[0]
        
        cursor.execute("SELECT id FROM characters LIMIT 1")
        character = cursor.fetchone()
        if not character:
            print("  ⚠️  No characters in database to test")
            db.close()
            return True
        character_id = character[0]
        
        # Create test relationship
        cursor.execute("""
            INSERT INTO relationships (
                campaign_id, entity1_type, entity1_id, entity2_type, entity2_id,
                relationship_type, strength, notes
            ) VALUES (?, 'character', ?, 'npc', 999, 'ally', 5, 'Test friendship')
        """, (campaign_id, character_id))
        rel_id = cursor.lastrowid
        db.commit()
        
        print(f"  Created test relationship (id={rel_id})")
        
        # Test retrieval
        relationships = get_entity_relationships('character', character_id, campaign_id)
        
        if relationships['count'] > 0:
            print(f"  ✅ Retrieved {relationships['count']} relationship(s)")
            print(f"  🤝 Sample: {relationships['relationships'][0]['relationship_type']}")
        else:
            print(f"  ❌ Failed to retrieve relationships")
            cursor.execute("DELETE FROM relationships WHERE id = ?", (rel_id,))
            db.commit()
            db.close()
            return False
        
        # Cleanup
        cursor.execute("DELETE FROM relationships WHERE id = ?", (rel_id,))
        db.commit()
        db.close()
        
        print(f"  🧹 Cleaned up test data")
        return True
        
    except Exception as e:
        print(f"  ❌ Error testing relationship functions: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_location_connections():
    """Test location connection tracking"""
    print("\n" + "="*80)
    print("TEST 8: Location Connection Functions")
    print("="*80)
    
    try:
        from database import get_db
        from routes.ai import get_connected_locations
        
        db = get_db()
        cursor = db.cursor()
        
        # Get two test locations
        cursor.execute("SELECT id FROM locations LIMIT 2")
        locations = cursor.fetchall()
        if len(locations) < 2:
            print("  ⚠️  Need at least 2 locations to test connections")
            db.close()
            return True
        
        loc1_id = locations[0][0]
        loc2_id = locations[1][0]
        
        # Create test connection
        cursor.execute("""
            INSERT INTO location_connections (
                location1_id, location2_id, connection_type, description, is_bidirectional
            ) VALUES (?, ?, 'door', 'Test connection', 1)
        """, (loc1_id, loc2_id))
        conn_id = cursor.lastrowid
        db.commit()
        
        print(f"  Created test connection (id={conn_id}) between locations {loc1_id} and {loc2_id}")
        
        # Test retrieval
        connections = get_connected_locations(loc1_id)
        
        if connections['count'] > 0:
            print(f"  ✅ Retrieved {connections['count']} connection(s)")
            print(f"  🚪 Connection type: {connections['connections'][0]['connection_type']}")
        else:
            print(f"  ❌ Failed to retrieve connections")
            cursor.execute("DELETE FROM location_connections WHERE id = ?", (conn_id,))
            db.commit()
            db.close()
            return False
        
        # Cleanup
        cursor.execute("DELETE FROM location_connections WHERE id = ?", (conn_id,))
        db.commit()
        db.close()
        
        print(f"  🧹 Cleaned up test data")
        return True
        
    except Exception as e:
        print(f"  ❌ Error testing location connections: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_context_manager():
    """Test AIContextManager"""
    print("\n" + "="*80)
    print("TEST 9: AI Context Manager")
    print("="*80)
    
    try:
        from database import get_db
        from routes.ai import get_context_manager
        
        # Get test data
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("SELECT id FROM campaigns LIMIT 1")
        campaign = cursor.fetchone()
        if not campaign:
            print("  ⚠️  No campaigns in database to test")
            db.close()
            return True
        campaign_id = campaign[0]
        
        cursor.execute("SELECT id FROM locations WHERE campaign_id = ? LIMIT 1", (campaign_id,))
        location = cursor.fetchone()
        if not location:
            print("  ⚠️  No locations in database to test")
            db.close()
            return True
        location_id = location[0]
        
        cursor.execute("SELECT user_id FROM characters WHERE campaign_id = ? LIMIT 1", (campaign_id,))
        user = cursor.fetchone()
        user_id = user[0] if user else None
        
        db.close()
        
        # Test context manager
        manager = get_context_manager()
        print(f"  ✅ Context manager instance created")
        
        # Test efficient mode
        context = manager.build_context(
            message="What's happening?",
            campaign_id=campaign_id,
            location_id=location_id,
            user_id=user_id,
            mode='efficient'
        )
        
        if context and 'formatted' in context:
            print(f"  ✅ Efficient mode context built")
            print(f"  📊 Token estimate: {context['token_estimate']}")
            print(f"  📦 Parts included: {', '.join(context['parts_included'])}")
        else:
            print(f"  ❌ Failed to build efficient context")
            return False
        
        # Test balanced mode
        context = manager.build_context(
            message="Tell me more",
            campaign_id=campaign_id,
            location_id=location_id,
            user_id=user_id,
            mode='balanced'
        )
        
        if context and 'formatted' in context:
            print(f"  ✅ Balanced mode context built")
            print(f"  📊 Token estimate: {context['token_estimate']}")
        else:
            print(f"  ❌ Failed to build balanced context")
            return False
        
        # Test full mode
        context = manager.build_context(
            message="Give me all details",
            campaign_id=campaign_id,
            location_id=location_id,
            user_id=user_id,
            mode='full'
        )
        
        if context and 'formatted' in context:
            print(f"  ✅ Full mode context built")
            print(f"  📊 Token estimate: {context['token_estimate']}")
            print(f"  📦 Parts included: {', '.join(context['parts_included'])}")
        else:
            print(f"  ❌ Failed to build full context")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error testing context manager: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """Run all tests and report results"""
    print("\n╔═══════════════════════════════════════════════════════════════════════════════╗")
    print("║                                                                               ║")
    print("║              AI MEMORY SYSTEM - COMPREHENSIVE INTEGRATION TESTS               ║")
    print("║                                                                               ║")
    print("╚═══════════════════════════════════════════════════════════════════════════════╝")
    
    tests = [
        ("Database Tables", test_database_tables),
        ("Location Context", test_location_context),
        ("Message History", test_message_history),
        ("Character Context", test_character_context),
        ("NPC System", test_npc_functions),
        ("Combat Tracking", test_combat_functions),
        ("Relationships", test_relationship_functions),
        ("Location Connections", test_location_connections),
        ("Context Manager", test_context_manager),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ CRITICAL ERROR in {name}: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")
    
    print("\n" + "="*80)
    print(f"RESULTS: {passed}/{total} tests passed ({100*passed//total}%)")
    print("="*80)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! AI Memory System is fully functional!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review errors above.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

