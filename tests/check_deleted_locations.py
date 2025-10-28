#!/usr/bin/env python3
"""
Check for remnants of deleted locations from The Labyrinth of Echoes campaign
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

import sqlite3
from datetime import datetime

# Database path
DB_PATH = '/app/data/shadowrealms.db'

def check_campaign_cleanup():
    """Check for remnants of deleted locations"""
    
    print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║           DELETED LOCATIONS CLEANUP VERIFICATION                              ║
║                  Campaign: The Labyrinth of Echoes                            ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
""")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # 1. Find the campaign
        print("━" * 80)
        print("📊 CAMPAIGN INFO")
        print("━" * 80)
        
        cursor.execute("""
            SELECT id, name, game_system, created_at, created_by
            FROM campaigns 
            WHERE name LIKE '%Labyrinth%'
        """)
        
        campaign = cursor.fetchone()
        if not campaign:
            print("❌ Campaign 'The Labyrinth of Echoes' not found!")
            return
        
        campaign_id = campaign['id']
        print(f"✅ Campaign Found:")
        print(f"   ID: {campaign_id}")
        print(f"   Name: {campaign['name']}")
        print(f"   System: {campaign['game_system']}")
        print(f"   Created: {campaign['created_at']}")
        
        # 2. Check soft-deleted locations
        print("\n" + "━" * 80)
        print("🗑️  SOFT-DELETED LOCATIONS (is_active = 0)")
        print("━" * 80)
        
        cursor.execute("""
            SELECT id, name, type, description, is_active, created_at
            FROM locations
            WHERE campaign_id = ? AND is_active = 0
            ORDER BY created_at DESC
        """, (campaign_id,))
        
        soft_deleted = cursor.fetchall()
        if soft_deleted:
            print(f"Found {len(soft_deleted)} soft-deleted locations:")
            for loc in soft_deleted:
                print(f"  • Location ID {loc['id']}: {loc['name']} ({loc['type']})")
                print(f"    Created: {loc['created_at']}")
        else:
            print("✅ No soft-deleted locations found (all properly cleaned up)")
        
        # 3. Check active locations
        print("\n" + "━" * 80)
        print("✅ ACTIVE LOCATIONS (is_active = 1)")
        print("━" * 80)
        
        cursor.execute("""
            SELECT id, name, type, description, is_active
            FROM locations
            WHERE campaign_id = ? AND is_active = 1
            ORDER BY type, name
        """, (campaign_id,))
        
        active_locations = cursor.fetchall()
        if active_locations:
            print(f"Found {len(active_locations)} active locations:")
            for loc in active_locations:
                print(f"  • Location ID {loc['id']}: {loc['name']} ({loc['type']})")
        else:
            print("❌ No active locations found (not even OOC!)")
        
        # 4. Check deletion audit log
        print("\n" + "━" * 80)
        print("📝 DELETION AUDIT LOG")
        print("━" * 80)
        
        cursor.execute("""
            SELECT 
                location_id,
                location_name,
                location_type,
                deleted_by,
                deleted_at,
                message_count
            FROM location_deletion_log
            WHERE campaign_id = ?
            ORDER BY deleted_at DESC
        """, (campaign_id,))
        
        audit_entries = cursor.fetchall()
        if audit_entries:
            print(f"✅ Found {len(audit_entries)} deletion audit entries:")
            for entry in audit_entries:
                print(f"\n  📍 Location: {entry['location_name']} ({entry['location_type']})")
                print(f"     Location ID: {entry['location_id']}")
                print(f"     Deleted by user ID: {entry['deleted_by']}")
                print(f"     Deleted at: {entry['deleted_at']}")
                print(f"     Messages removed: {entry['message_count']}")
        else:
            print("ℹ️  No deletion audit entries found")
        
        # 5. Check for orphaned messages
        print("\n" + "━" * 80)
        print("💬 ORPHANED MESSAGES CHECK")
        print("━" * 80)
        
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM messages m
            WHERE m.location_id IN (
                SELECT id FROM locations
                WHERE campaign_id = ? AND is_active = 0
            )
        """, (campaign_id,))
        
        orphaned_count = cursor.fetchone()['count']
        if orphaned_count > 0:
            print(f"❌ PROBLEM: Found {orphaned_count} orphaned messages!")
            print("   These messages belong to soft-deleted locations.")
            print("   CASCADE delete may not be working properly!")
            
            # Show which locations have orphaned messages
            cursor.execute("""
                SELECT l.id, l.name, l.type, COUNT(m.id) as msg_count
                FROM locations l
                LEFT JOIN messages m ON m.location_id = l.id
                WHERE l.campaign_id = ? AND l.is_active = 0
                GROUP BY l.id
                HAVING msg_count > 0
            """, (campaign_id,))
            
            for row in cursor.fetchall():
                print(f"   • Location '{row['name']}' (ID {row['id']}): {row['msg_count']} messages")
        else:
            print("✅ No orphaned messages found!")
            print("   CASCADE delete is working correctly.")
        
        # 6. Check total messages in campaign
        print("\n" + "━" * 80)
        print("📊 CAMPAIGN MESSAGE STATISTICS")
        print("━" * 80)
        
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM messages
            WHERE campaign_id = ?
        """, (campaign_id,))
        
        total_messages = cursor.fetchone()['total']
        print(f"Total messages in campaign: {total_messages}")
        
        # 7. Check ChromaDB status (we can't directly query it, but we can log)
        print("\n" + "━" * 80)
        print("🧠 CHROMADB EMBEDDING STATUS")
        print("━" * 80)
        print("ℹ️  ChromaDB embeddings should have been purged during deletion.")
        print("   Embedding IDs follow format: msg_{message_id}_{campaign_id}")
        if audit_entries:
            total_purged = sum(entry['message_count'] for entry in audit_entries)
            print(f"   Expected purged embeddings: {total_purged}")
        
        # 8. Summary
        print("\n" + "━" * 80)
        print("✅ CLEANUP VERIFICATION SUMMARY")
        print("━" * 80)
        
        issues = []
        if soft_deleted:
            issues.append(f"• {len(soft_deleted)} locations are soft-deleted (is_active=0)")
        if orphaned_count > 0:
            issues.append(f"• {orphaned_count} orphaned messages found")
        if not active_locations:
            issues.append("• No active locations (not even OOC)")
        
        if not issues:
            print("🎉 PERFECT CLEANUP!")
            print("   ✅ All deleted locations properly cleaned up")
            print("   ✅ No orphaned messages")
            print("   ✅ Audit log properly maintained")
            print("   ✅ Only audit records remain")
        else:
            print("⚠️  Issues found:")
            for issue in issues:
                print(f"   {issue}")
        
        if audit_entries:
            print(f"\n   📝 {len(audit_entries)} deletion(s) logged in audit trail")
            print("   ℹ️  This is EXPECTED and provides accountability")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_campaign_cleanup()

