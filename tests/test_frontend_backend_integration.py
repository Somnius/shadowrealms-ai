#!/usr/bin/env python3
"""
Frontend-Backend Integration Test Suite
Tests the complete user journey from registration to AI chat
"""

import requests
import json
import time
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5000"
FRONTEND_URL = "http://localhost"
TEST_USERNAME = f"testuser_{int(time.time())}"
TEST_PASSWORD = "testpass123"

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_section(title):
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{title.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}\n")

def print_test(test_name, status, details=""):
    if status == "PASS":
        symbol = "✅"
        color = Colors.OKGREEN
    elif status == "FAIL":
        symbol = "❌"
        color = Colors.FAIL
    elif status == "WARN":
        symbol = "⚠️ "
        color = Colors.WARNING
    else:
        symbol = "ℹ️ "
        color = Colors.OKBLUE
    
    print(f"{symbol} {color}{test_name}{Colors.ENDC}")
    if details:
        print(f"   {details}")

def test_frontend_accessible():
    """Test if frontend is accessible"""
    print_section("TEST 1: Frontend Accessibility")
    
    try:
        response = requests.get(FRONTEND_URL, timeout=5)
        if response.status_code == 200:
            print_test("Frontend accessible via Nginx", "PASS", f"Status: {response.status_code}")
            return True
        else:
            print_test("Frontend accessibility", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_test("Frontend accessibility", "FAIL", f"Error: {e}")
        return False

def test_backend_accessible():
    """Test if backend API is accessible"""
    print_section("TEST 2: Backend API Accessibility")
    
    try:
        # Test health endpoint or any endpoint
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "fake", "password": "fake"},
            timeout=5
        )
        # We expect 401 or error, but the API should respond
        if response.status_code in [400, 401, 422]:
            print_test("Backend API accessible", "PASS", f"API responding (Status: {response.status_code})")
            return True
        else:
            print_test("Backend API", "WARN", f"Unexpected status: {response.status_code}")
            return True  # Still accessible
    except Exception as e:
        print_test("Backend API accessibility", "FAIL", f"Error: {e}")
        return False

def test_user_registration():
    """Test user registration"""
    print_section("TEST 3: User Registration")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
                "email": f"{TEST_USERNAME}@test.com"
            },
            timeout=10
        )
        
        if response.status_code == 201:
            print_test("User registration", "PASS", f"User '{TEST_USERNAME}' registered")
            return True
        elif response.status_code == 400 and "already exists" in response.text.lower():
            print_test("User registration", "WARN", "User already exists (using existing)")
            return True
        else:
            print_test("User registration", "FAIL", f"Status: {response.status_code}, Body: {response.text[:100]}")
            return False
    except Exception as e:
        print_test("User registration", "FAIL", f"Error: {e}")
        return False

def test_user_login():
    """Test user login and token retrieval"""
    print_section("TEST 4: User Login")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "access_token" in data:
                token = data["access_token"]
                print_test("User login", "PASS", f"Token received (length: {len(token)})")
                return token
            else:
                print_test("User login", "FAIL", "No access_token in response")
                return None
        else:
            print_test("User login", "FAIL", f"Status: {response.status_code}, Body: {response.text[:100]}")
            return None
    except Exception as e:
        print_test("User login", "FAIL", f"Error: {e}")
        return None

def test_protected_route(token):
    """Test accessing a protected route with token"""
    print_section("TEST 5: Protected Route Access")
    
    if not token:
        print_test("Protected route", "FAIL", "No token available")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/api/campaigns",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            campaigns = response.json()
            print_test("Protected route access", "PASS", f"Campaigns retrieved: {len(campaigns)} campaigns")
            return campaigns
        else:
            print_test("Protected route access", "FAIL", f"Status: {response.status_code}")
            return None
    except Exception as e:
        print_test("Protected route access", "FAIL", f"Error: {e}")
        return None

def test_campaign_creation(token):
    """Test creating a new campaign"""
    print_section("TEST 6: Campaign Creation")
    
    if not token:
        print_test("Campaign creation", "FAIL", "No token available")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        campaign_data = {
            "name": f"Test Campaign {int(time.time())}",
            "description": "Automated test campaign",
            "game_system": "vampire",
            "setting": "Modern nights",
            "max_players": 5
        }
        
        response = requests.post(
            f"{BASE_URL}/api/campaigns",
            headers=headers,
            json=campaign_data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            campaign = response.json()
            campaign_id = campaign.get("campaign_id") or campaign.get("id") or campaign.get("campaign", {}).get("id")
            print_test("Campaign creation", "PASS", f"Campaign ID: {campaign_id}")
            return campaign_id
        else:
            print_test("Campaign creation", "FAIL", f"Status: {response.status_code}, Body: {response.text[:200]}")
            return None
    except Exception as e:
        print_test("Campaign creation", "FAIL", f"Error: {e}")
        return None

def test_ai_generation(token, campaign_id):
    """Test AI text generation with RAG"""
    print_section("TEST 7: AI Generation with RAG")
    
    if not token:
        print_test("AI generation", "FAIL", "No token available")
        return False
    
    if not campaign_id:
        print_test("AI generation", "WARN", "No campaign ID, using default")
        campaign_id = 1
    
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        print("   ⏳ Generating AI response (this may take 10-30 seconds)...")
        
        response = requests.post(
            f"{BASE_URL}/api/ai/chat",
            headers=headers,
            json={
                "campaign_id": campaign_id,
                "message": "What are the main vampire clans in the Camarilla?",
                "use_rag": True,
                "max_tokens": 150
            },
            timeout=60  # AI generation can take time
        )
        
        if response.status_code == 200:
            data = response.json()
            if "response" in data:
                ai_response = data["response"]
                print_test("AI generation", "PASS", f"Response length: {len(ai_response)} chars")
                print(f"\n   📝 AI Response preview:")
                print(f"   {ai_response[:200]}...")
                
                # Check if RAG context was used
                if "rag_context" in data or "sources" in data:
                    print_test("RAG context", "PASS", "Rule book context included")
                else:
                    print_test("RAG context", "WARN", "No explicit RAG context in response")
                
                return True
            else:
                print_test("AI generation", "FAIL", "No 'response' field in data")
                return False
        else:
            print_test("AI generation", "FAIL", f"Status: {response.status_code}, Body: {response.text[:200]}")
            return False
    except requests.Timeout:
        print_test("AI generation", "FAIL", "Request timed out after 60 seconds")
        return False
    except Exception as e:
        print_test("AI generation", "FAIL", f"Error: {e}")
        return False

def test_rule_books_search(token):
    """Test rule books search functionality"""
    print_section("TEST 8: Rule Books Search")
    
    if not token:
        print_test("Rule books search", "FAIL", "No token available")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/api/rule-books/scan",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            books_count = data.get("books_found", 0)
            print_test("Rule books scan", "PASS", f"Found {books_count} rule books")
            return True
        else:
            print_test("Rule books scan", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_test("Rule books scan", "FAIL", f"Error: {e}")
        return False

def main():
    """Run all integration tests"""
    print(f"\n{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}SHADOWREALMS AI - FRONTEND/BACKEND INTEGRATION TEST{Colors.ENDC}")
    print(f"{Colors.BOLD}Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*70}{Colors.ENDC}")
    
    results = {
        "passed": 0,
        "failed": 0,
        "warnings": 0
    }
    
    # Test sequence
    tests = []
    
    # 1. Frontend accessible
    if test_frontend_accessible():
        results["passed"] += 1
    else:
        results["failed"] += 1
        tests.append("Frontend inaccessible")
    
    # 2. Backend accessible
    if test_backend_accessible():
        results["passed"] += 1
    else:
        results["failed"] += 1
        tests.append("Backend inaccessible")
        print("\n❌ Cannot continue without backend. Exiting.")
        return 1
    
    # 3. User registration
    if test_user_registration():
        results["passed"] += 1
    else:
        results["failed"] += 1
        tests.append("User registration failed")
    
    # 4. User login
    token = test_user_login()
    if token:
        results["passed"] += 1
    else:
        results["failed"] += 1
        tests.append("User login failed")
        print("\n❌ Cannot continue without authentication. Exiting.")
        return 1
    
    # 5. Protected route
    campaigns = test_protected_route(token)
    if campaigns is not None:
        results["passed"] += 1
    else:
        results["failed"] += 1
        tests.append("Protected route access failed")
    
    # 6. Campaign creation
    campaign_id = test_campaign_creation(token)
    if campaign_id:
        results["passed"] += 1
    else:
        results["failed"] += 1
        tests.append("Campaign creation failed")
    
    # 7. AI generation
    if test_ai_generation(token, campaign_id):
        results["passed"] += 1
    else:
        results["failed"] += 1
        tests.append("AI generation failed")
    
    # 8. Rule books
    if test_rule_books_search(token):
        results["passed"] += 1
    else:
        results["failed"] += 1
        tests.append("Rule books search failed")
    
    # Summary
    print_section("TEST SUMMARY")
    total = results["passed"] + results["failed"]
    print(f"{Colors.OKGREEN}✅ Passed: {results['passed']}/{total}{Colors.ENDC}")
    print(f"{Colors.FAIL}❌ Failed: {results['failed']}/{total}{Colors.ENDC}")
    
    if results["failed"] == 0:
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! System is operational!{Colors.ENDC}")
        return 0
    else:
        print(f"\n{Colors.WARNING}⚠️  Some tests failed. Issues need attention:{Colors.ENDC}")
        for issue in tests:
            print(f"   • {issue}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

