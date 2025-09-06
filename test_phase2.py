#!/usr/bin/env python3
"""
ShadowRealms AI - Phase 2 Testing Script
Test RAG & Vector Memory System enhancements
"""

import requests
import json
import time
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5000"
AUTH_URL = f"{BASE_URL}/api/auth"
CAMPAIGNS_URL = f"{BASE_URL}/api/campaigns"
AI_URL = f"{BASE_URL}/api/ai"

def test_health():
    """Test basic health endpoint"""
    print("🔍 Testing Health Endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health: {data['status']} - Database: {data['database']} - GPU: {data['gpu_monitoring']}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_auth():
    """Test authentication"""
    print("\n🔐 Testing Authentication...")
    try:
        # Register test user
        register_data = {
            "username": "testuser_phase2",
            "email": "test@phase2.com",
            "password": "testpass123"
        }
        
        response = requests.post(f"{AUTH_URL}/register", json=register_data, timeout=10)
        if response.status_code == 201:
            print("✅ User registration successful")
        elif response.status_code == 400 and "already exists" in response.text:
            print("✅ User already exists (expected)")
        else:
            print(f"⚠️ Registration response: {response.status_code} - {response.text}")
        
        # Login
        login_data = {
            "username": "testuser_phase2",
            "password": "testpass123"
        }
        
        response = requests.post(f"{AUTH_URL}/login", json=login_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            token = data['access_token']
            print("✅ Login successful")
            return token
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Auth error: {e}")
        return None

def test_campaign_creation(token):
    """Test campaign creation"""
    print("\n🏰 Testing Campaign Creation...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        campaign_data = {
            "name": "Phase 2 Test Campaign",
            "description": "A test campaign for Phase 2 RAG testing",
            "game_system": "D&D 5e",
            "settings": {
                "world": "Forgotten Realms",
                "era": "Modern",
                "magic_level": "High"
            },
            "world_info": {
                "locations": ["Waterdeep", "Neverwinter", "Baldur's Gate"],
                "factions": ["Harpers", "Zhentarim", "Lords' Alliance"],
                "history": "A world of magic and adventure"
            }
        }
        
        response = requests.post(f"{CAMPAIGNS_URL}/", json=campaign_data, headers=headers, timeout=30)
        if response.status_code == 201:
            data = response.json()
            campaign_id = data['campaign_id']
            print(f"✅ Campaign created successfully - ID: {campaign_id}")
            return campaign_id
        else:
            print(f"❌ Campaign creation failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Campaign creation error: {e}")
        return None

def test_campaign_retrieval(token, campaign_id):
    """Test campaign retrieval"""
    print("\n📖 Testing Campaign Retrieval...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{CAMPAIGNS_URL}/{campaign_id}", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            campaign = data['campaign']
            print(f"✅ Campaign retrieved: {campaign['name']}")
            print(f"   Game System: {campaign['game_system']}")
            print(f"   Context available: {len(campaign.get('context', {}))} sections")
            return True
        else:
            print(f"❌ Campaign retrieval failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Campaign retrieval error: {e}")
        return False

def test_world_data_update(token, campaign_id):
    """Test world data update"""
    print("\n🌍 Testing World Data Update...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        world_data = {
            "new_location": "Candlekeep",
            "new_faction": "Order of the Gauntlet",
            "events": ["The Spellplague", "The Sundering", "The Second Sundering"],
            "npcs": {
                "Elminster": "Sage of Shadowdale",
                "Drizzt": "Drow Ranger",
                "Volo": "Traveling Scholar"
            }
        }
        
        response = requests.post(f"{CAMPAIGNS_URL}/{campaign_id}/world", json=world_data, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ World data updated - Memory ID: {data['memory_id']}")
            return True
        else:
            print(f"❌ World data update failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ World data update error: {e}")
        return False

def test_memory_search(token, campaign_id):
    """Test memory search functionality"""
    print("\n🔍 Testing Memory Search...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        search_data = {
            "query": "Elminster",
            "memory_type": "all",
            "limit": 5
        }
        
        response = requests.post(f"{CAMPAIGNS_URL}/{campaign_id}/search", json=search_data, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Memory search successful - Found {data['total_results']} results")
            
            for mem_type, results in data['results'].items():
                if results:
                    print(f"   {mem_type}: {len(results)} memories")
                    for result in results[:2]:  # Show first 2 results
                        content = result['content'][:100] + "..." if len(result['content']) > 100 else result['content']
                        print(f"     - {content}")
            
            return True
        else:
            print(f"❌ Memory search failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Memory search error: {e}")
        return False

def test_context_retrieval(token, campaign_id):
    """Test context retrieval for AI generation"""
    print("\n🧠 Testing Context Retrieval...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        context_data = {
            "query": "Tell me about the world and characters"
        }
        
        response = requests.post(f"{CAMPAIGNS_URL}/{campaign_id}/context", json=context_data, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            context = data['context']
            print(f"✅ Context retrieval successful")
            print(f"   Campaign data: {len(context.get('campaign_data', []))} items")
            print(f"   Characters: {len(context.get('characters', []))} items")
            print(f"   World data: {len(context.get('world_data', []))} items")
            print(f"   Sessions: {len(context.get('recent_sessions', []))} items")
            print(f"   Rules: {len(context.get('rules', []))} items")
            
            if 'augmented_prompt' in context:
                print(f"   Augmented prompt length: {len(context['augmented_prompt'])} characters")
            
            return True
        else:
            print(f"❌ Context retrieval failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Context retrieval error: {e}")
        return False

def test_interaction_storage(token, campaign_id):
    """Test AI interaction storage"""
    print("\n💬 Testing Interaction Storage...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        interaction_data = {
            "prompt": "What is the capital city of the realm?",
            "response": "The capital city is Waterdeep, also known as the City of Splendors. It's a bustling metropolis on the Sword Coast.",
            "interaction_type": "world_question"
        }
        
        response = requests.post(f"{CAMPAIGNS_URL}/{campaign_id}/interaction", json=interaction_data, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Interaction stored - Memory ID: {data['memory_id']}")
            return True
        else:
            print(f"❌ Interaction storage failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Interaction storage error: {e}")
        return False

def test_ai_generation_with_context(token, campaign_id):
    """Test AI generation with RAG context"""
    print("\n🤖 Testing AI Generation with Context...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        ai_data = {
            "message": "Tell me about the world and what adventures await",
            "context": {
                "campaign_id": campaign_id,
                "user_id": "testuser_phase2"
            }
        }
        
        response = requests.post(f"{AI_URL}/chat", json=ai_data, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ AI generation successful")
            print(f"   Response length: {len(data.get('response', ''))} characters")
            print(f"   Model used: {data.get('model', 'unknown')}")
            print(f"   Response preview: {data.get('response', '')[:200]}...")
            return True
        else:
            print(f"❌ AI generation failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ AI generation error: {e}")
        return False

def main():
    """Run Phase 2 tests"""
    print("🚀 ShadowRealms AI - Phase 2 Testing")
    print("=" * 50)
    
    # Test results
    results = {
        'health': False,
        'auth': False,
        'campaign_creation': False,
        'campaign_retrieval': False,
        'world_update': False,
        'memory_search': False,
        'context_retrieval': False,
        'interaction_storage': False,
        'ai_generation': False
    }
    
    # Run tests
    results['health'] = test_health()
    if not results['health']:
        print("\n❌ Health check failed - stopping tests")
        return
    
    token = test_auth()
    results['auth'] = token is not None
    if not token:
        print("\n❌ Authentication failed - stopping tests")
        return
    
    campaign_id = test_campaign_creation(token)
    results['campaign_creation'] = campaign_id is not None
    if not campaign_id:
        print("\n❌ Campaign creation failed - stopping tests")
        return
    
    results['campaign_retrieval'] = test_campaign_retrieval(token, campaign_id)
    results['world_update'] = test_world_data_update(token, campaign_id)
    results['memory_search'] = test_memory_search(token, campaign_id)
    results['context_retrieval'] = test_context_retrieval(token, campaign_id)
    results['interaction_storage'] = test_interaction_storage(token, campaign_id)
    results['ai_generation'] = test_ai_generation_with_context(token, campaign_id)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 PHASE 2 TEST RESULTS")
    print("=" * 50)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL PHASE 2 TESTS PASSED!")
        print("✅ RAG & Vector Memory System is fully functional!")
    else:
        print(f"⚠️ {total-passed} tests failed - check logs above")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
