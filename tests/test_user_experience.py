#!/usr/bin/env python3
"""
ShadowRealms AI - User Experience Test
Tests the actual gameplay flow that users will experience
"""

import requests
import json
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
API_BASE = "http://localhost:5000/api"
TEST_USER = {
    'username': 'testplayer_experience',
    'email': 'testplayer@shadowrealms.com',
    'password': 'testpass123'
}

class UserExperienceTester:
    """Test the actual user experience flow"""
    
    def __init__(self):
        self.token = None
        self.campaign_id = None
        self.character_id = None
        self.test_results = []
        
    def log_test(self, test_name, success, details="", timing=0):
        """Log test results"""
        status = "✅" if success else "❌"
        timing_str = f" ({timing:.2f}s)" if timing > 0 else ""
        logger.info(f"{status} {test_name}{timing_str}")
        if details:
            logger.info(f"   📝 {details}")
        
        self.test_results.append({
            'test': test_name,
            'success': success,
            'details': details,
            'timing': timing
        })
    
    def test_user_registration_and_login(self):
        """Test user registration and login flow"""
        logger.info("🔐 Testing User Registration & Login Flow...")
        start_time = time.time()
        
        try:
            # Register user
            register_response = requests.post(f"{API_BASE}/auth/register", json=TEST_USER, timeout=10)
            if register_response.status_code in [200, 201, 409]:  # 409 = user already exists
                logger.info("   📝 User registration: OK")
            else:
                self.log_test("User Registration", False, f"Failed: {register_response.status_code}")
                return False
            
            # Login user
            login_data = {
                'username': TEST_USER['username'],
                'password': TEST_USER['password']
            }
            login_response = requests.post(f"{API_BASE}/auth/login", json=login_data, timeout=10)
            
            if login_response.status_code == 200:
                self.token = login_response.json().get('access_token')
                if self.token:
                    timing = time.time() - start_time
                    self.log_test("User Login", True, f"Token obtained: {self.token[:20]}...", timing)
                    return True
                else:
                    self.log_test("User Login", False, "No token in response")
                    return False
            else:
                self.log_test("User Login", False, f"Login failed: {login_response.status_code}")
                return False
                
        except Exception as e:
            timing = time.time() - start_time
            self.log_test("User Registration & Login", False, f"Error: {e}", timing)
            return False
    
    def test_data_persistence(self):
        """Test that data persists across requests"""
        logger.info("💾 Testing Data Persistence...")
        start_time = time.time()
        
        try:
            headers = {'Authorization': f'Bearer {self.token}'}
            
            # Create a test campaign
            campaign_data = {
                'name': 'Test Persistence Campaign',
                'description': 'Testing data persistence across requests',
                'game_system': 'World of Darkness',
                'max_players': 4
            }
            
            create_response = requests.post(f"{API_BASE}/campaigns", json=campaign_data, headers=headers, timeout=30)
            if create_response.status_code in [200, 201]:
                self.campaign_id = create_response.json().get('campaign_id')
                logger.info(f"   📝 Campaign created: ID {self.campaign_id}")
            else:
                self.log_test("Data Persistence", False, f"Campaign creation failed: {create_response.status_code}")
                return False
            
            # Wait a moment
            time.sleep(2)
            
            # Try to read the campaign back
            read_response = requests.get(f"{API_BASE}/campaigns/{self.campaign_id}", headers=headers, timeout=10)
            if read_response.status_code == 200:
                campaign_data = read_response.json()
                # Handle both 'id' and 'campaign_id' response formats
                campaign_id = campaign_data.get('id') or campaign_data.get('campaign_id')
                if campaign_id == self.campaign_id:
                    timing = time.time() - start_time
                    self.log_test("Data Persistence", True, f"Campaign data persisted and retrievable", timing)
                    return True
                else:
                    self.log_test("Data Persistence", False, f"Campaign data mismatch: expected {self.campaign_id}, got {campaign_id}")
                    return False
            else:
                self.log_test("Data Persistence", False, f"Campaign read failed: {read_response.status_code}")
                return False
                
        except Exception as e:
            timing = time.time() - start_time
            self.log_test("Data Persistence", False, f"Error: {e}", timing)
            return False
    
    def test_pdf_rule_book_search(self):
        """Test PDF rule book search functionality"""
        logger.info("📚 Testing PDF Rule Book Search...")
        start_time = time.time()
        
        try:
            headers = {'Authorization': f'Bearer {self.token}'}
            
            # Search for rule book content
            search_data = {
                'query': 'vampire',
                'limit': 5
            }
            
            search_response = requests.post(f"{API_BASE}/rule-books/search", json=search_data, headers=headers, timeout=30)
            if search_response.status_code == 200:
                results = search_response.json()
                if results.get('results') and len(results['results']) > 0:
                    timing = time.time() - start_time
                    self.log_test("PDF Rule Book Search", True, f"Found {len(results['results'])} results", timing)
                    
                    # Show sample result
                    sample = results['results'][0]
                    logger.info(f"   📖 Sample result: {sample.get('text', '')[:100]}...")
                    return True
                else:
                    self.log_test("PDF Rule Book Search", False, "No results returned")
                    return False
            else:
                self.log_test("PDF Rule Book Search", False, f"Search failed: {search_response.status_code}")
                return False
                
        except Exception as e:
            timing = time.time() - start_time
            self.log_test("PDF Rule Book Search", False, f"Error: {e}", timing)
            return False
    
    def test_campaign_creation_and_management(self):
        """Test campaign creation and management"""
        logger.info("🏰 Testing Campaign Creation & Management...")
        start_time = time.time()
        
        try:
            headers = {'Authorization': f'Bearer {self.token}'}
            
            # Create a new campaign
            campaign_data = {
                'name': 'Vampire: The Masquerade - Test Campaign',
                'description': 'A dark urban fantasy campaign in the World of Darkness',
                'game_system': 'World of Darkness',
                'max_players': 6
            }
            
            create_response = requests.post(f"{API_BASE}/campaigns", json=campaign_data, headers=headers, timeout=30)
            if create_response.status_code in [200, 201]:
                self.campaign_id = create_response.json().get('campaign_id')
                logger.info(f"   📝 Campaign created: ID {self.campaign_id}")
            else:
                self.log_test("Campaign Creation", False, f"Creation failed: {create_response.status_code}")
                return False
            
            # List all campaigns
            list_response = requests.get(f"{API_BASE}/campaigns/", headers=headers, timeout=10)
            if list_response.status_code == 200:
                campaigns = list_response.json()
                if isinstance(campaigns, list) and len(campaigns) > 0:
                    timing = time.time() - start_time
                    self.log_test("Campaign Management", True, f"Found {len(campaigns)} campaigns", timing)
                    return True
                else:
                    self.log_test("Campaign Management", False, "No campaigns found in list")
                    return False
            else:
                self.log_test("Campaign Management", False, f"List failed: {list_response.status_code}")
                return False
                
        except Exception as e:
            timing = time.time() - start_time
            self.log_test("Campaign Creation & Management", False, f"Error: {e}", timing)
            return False
    
    def test_character_creation(self):
        """Test character creation for players"""
        logger.info("👤 Testing Character Creation...")
        start_time = time.time()
        
        try:
            headers = {'Authorization': f'Bearer {self.token}'}
            
            # Create a character
            character_data = {
                'name': 'Marcus Blackwood',
                'system_type': 'd10',  # World of Darkness uses d10 system
                'level': 1,
                'campaign_id': self.campaign_id,
                'character_data': {
                    'clan': 'Ventrue',
                    'generation': 12,
                    'attributes': {
                        'strength': 3,
                        'dexterity': 2,
                        'stamina': 3,
                        'charisma': 4,
                        'manipulation': 3,
                        'appearance': 3,
                        'perception': 2,
                        'intelligence': 3,
                        'wits': 2
                    },
                    'abilities': {
                        'alertness': 2,
                        'athletics': 1,
                        'brawl': 2,
                        'dodge': 1,
                        'empathy': 3,
                        'expression': 2,
                        'intimidation': 3,
                        'leadership': 4,
                        'streetwise': 2,
                        'subterfuge': 2
                    }
                }
            }
            
            create_response = requests.post(f"{API_BASE}/characters", json=character_data, headers=headers, timeout=30)
            if create_response.status_code in [200, 201]:
                self.character_id = create_response.json().get('character_id')
                timing = time.time() - start_time
                self.log_test("Character Creation", True, f"Character created: ID {self.character_id}", timing)
                return True
            else:
                self.log_test("Character Creation", False, f"Creation failed: {create_response.status_code}")
                return False
                
        except Exception as e:
            timing = time.time() - start_time
            self.log_test("Character Creation", False, f"Error: {e}", timing)
            return False
    
    def test_world_building(self):
        """Test AI-assisted world building"""
        logger.info("🌍 Testing World Building...")
        start_time = time.time()
        
        try:
            headers = {'Authorization': f'Bearer {self.token}'}
            
            # Test AI world building
            world_data = {
                'message': 'Help me build a dark urban setting for my Vampire: The Masquerade campaign. I want a city with a strong vampire presence, hidden from mortals.',
                'campaign_id': self.campaign_id
            }
            
            ai_response = requests.post(f"{API_BASE}/ai/chat", json=world_data, headers=headers, timeout=60)
            if ai_response.status_code == 200:
                response_data = ai_response.json()
                if response_data.get('response'):
                    timing = time.time() - start_time
                    self.log_test("World Building", True, f"AI response received ({len(response_data['response'])} chars)", timing)
                    
                    # Show sample response
                    logger.info(f"   🤖 AI Response: {response_data['response'][:200]}...")
                    return True
                else:
                    self.log_test("World Building", False, "No AI response content")
                    return False
            else:
                self.log_test("World Building", False, f"AI request failed: {ai_response.status_code}")
                return False
                
        except Exception as e:
            timing = time.time() - start_time
            self.log_test("World Building", False, f"Error: {e}", timing)
            return False
    
    def test_ai_actions(self):
        """Test AI performing RPG actions"""
        logger.info("🎲 Testing AI RPG Actions...")
        start_time = time.time()
        
        try:
            headers = {'Authorization': f'Bearer {self.token}'}
            
            # Test AI dice rolling
            dice_data = {
                'message': 'Roll 5 dice for my character Marcus to see if he can successfully intimidate a mortal',
                'campaign_id': self.campaign_id
            }
            
            ai_response = requests.post(f"{API_BASE}/ai/chat", json=dice_data, headers=headers, timeout=60)
            if ai_response.status_code == 200:
                response_data = ai_response.json()
                if response_data.get('response'):
                    timing = time.time() - start_time
                    self.log_test("AI RPG Actions", True, f"AI action response received", timing)
                    
                    # Show sample response
                    logger.info(f"   🎲 AI Action: {response_data['response'][:200]}...")
                    return True
                else:
                    self.log_test("AI RPG Actions", False, "No AI action response")
                    return False
            else:
                self.log_test("AI RPG Actions", False, f"AI action failed: {ai_response.status_code}")
                return False
                
        except Exception as e:
            timing = time.time() - start_time
            self.log_test("AI RPG Actions", False, f"Error: {e}", timing)
            return False
    
    def run_all_tests(self):
        """Run all user experience tests"""
        logger.info("🚀 Starting User Experience Tests...")
        logger.info("="*60)
        
        total_tests = 0
        passed_tests = 0
        
        # Test 1: User Registration & Login
        total_tests += 1
        if self.test_user_registration_and_login():
            passed_tests += 1
        
        # Test 2: Data Persistence
        total_tests += 1
        if self.test_data_persistence():
            passed_tests += 1
        
        # Test 3: PDF Rule Book Search
        total_tests += 1
        if self.test_pdf_rule_book_search():
            passed_tests += 1
        
        # Test 4: Campaign Creation & Management
        total_tests += 1
        if self.test_campaign_creation_and_management():
            passed_tests += 1
        
        # Test 5: Character Creation
        total_tests += 1
        if self.test_character_creation():
            passed_tests += 1
        
        # Test 6: World Building
        total_tests += 1
        if self.test_world_building():
            passed_tests += 1
        
        # Test 7: AI RPG Actions
        total_tests += 1
        if self.test_ai_actions():
            passed_tests += 1
        
        # Summary
        logger.info("="*60)
        logger.info("📊 USER EXPERIENCE TEST SUMMARY")
        logger.info("="*60)
        logger.info(f"✅ Passed: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)")
        logger.info(f"❌ Failed: {total_tests - passed_tests}/{total_tests}")
        
        if passed_tests == total_tests:
            logger.info("🎉 ALL TESTS PASSED! System is ready for real users!")
        else:
            logger.info("⚠️  Some tests failed. System needs fixes before users can play.")
        
        return passed_tests == total_tests

if __name__ == "__main__":
    tester = UserExperienceTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)
