#!/usr/bin/env python3
"""
Fix Missing OOC Rooms
Creates OOC rooms for all campaigns that don't have one
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_missing_ooc_rooms():
    """Create OOC rooms for campaigns that don't have them"""
    
    print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║                      FIXING MISSING OOC ROOMS                                 ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
""")
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Find campaigns without OOC rooms
    cursor.execute("""
        SELECT c.id, c.name, c.game_system, c.created_by
        FROM campaigns c
        WHERE NOT EXISTS (
            SELECT 1 FROM locations l 
            WHERE l.campaign_id = c.id 
            AND l.type = 'ooc' 
            AND l.is_active = 1
        )
    """)
    
    campaigns_without_ooc = cursor.fetchall()
    
    if not campaigns_without_ooc:
        print("✅ All campaigns already have OOC rooms!")
        return
    
    print(f"Found {len(campaigns_without_ooc)} campaigns without OOC rooms:\n")
    
    for campaign in campaigns_without_ooc:
        campaign_id = campaign['id']
        campaign_name = campaign['name']
        campaign_system = campaign['game_system']
        created_by = campaign['created_by']
        
        print(f"📍 Campaign {campaign_id}: {campaign_name} ({campaign_system})")
        
        try:
            # Create OOC room
            cursor.execute("""
                INSERT INTO locations (campaign_id, name, type, description, created_by, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (
                campaign_id,
                'Out of Character Lobby',
                'ooc',
                'A place for players to discuss the campaign, ask questions, and chat as themselves (not as characters). '
                'This is the default meeting place before entering the game world. '
                'Keep discussions OOC - no in-character roleplay here!',
                created_by
            ))
            
            conn.commit()
            location_id = cursor.lastrowid
            
            print(f"   ✅ Created OOC room (location ID: {location_id})\n")
            
        except Exception as e:
            print(f"   ❌ Error creating OOC room: {e}\n")
            conn.rollback()
    
    # Verify
    print("\n" + "━" * 80)
    print("VERIFICATION:")
    print("━" * 80 + "\n")
    
    cursor.execute("""
        SELECT c.id, c.name,
               (SELECT COUNT(*) FROM locations WHERE campaign_id = c.id AND type = 'ooc' AND is_active = 1) as has_ooc
        FROM campaigns c
        ORDER BY c.id
    """)
    
    all_campaigns = cursor.fetchall()
    all_have_ooc = True
    
    for campaign in all_campaigns:
        status = "✅" if campaign['has_ooc'] > 0 else "❌"
        print(f"{status} Campaign {campaign['id']}: {campaign['name']} - OOC rooms: {campaign['has_ooc']}")
        if campaign['has_ooc'] == 0:
            all_have_ooc = False
    
    print("\n" + "=" * 80)
    if all_have_ooc:
        print("✅ SUCCESS: All campaigns now have OOC rooms!")
    else:
        print("⚠️  WARNING: Some campaigns still don't have OOC rooms!")
    print("=" * 80)
    
    conn.close()

if __name__ == '__main__':
    try:
        fix_missing_ooc_rooms()
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

