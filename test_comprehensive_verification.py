#!/usr/bin/env python3
"""
ShadowRealms AI - Comprehensive Phase 1 + 2 Verification
Tests all systems with timing, error scenarios, and data integrity checks
"""

import requests
import json
import time
import sys
from datetime import datetime
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:5000"
API_BASE = f"{BASE_URL}/api"

class TestTimer:
    """Context manager for timing operations"""
    def __init__(self, operation_name):
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        print(f"⏱️  {self.operation_name}: {duration:.2f}s")
        return False

class ComprehensiveTester:
    def __init__(self):
        self.token = None
        self.test_results = {
            'phase1': {'passed': 0, 'failed': 0, 'total': 0},
            'phase2': {'passed': 0, 'failed': 0, 'total': 0},
            'errors': [],
            'timings': {}
        }
    
    def log_result(self, phase, test_name, success, error_msg=None, duration=None):
        """Log test result with timing"""
        self.test_results[phase]['total'] += 1
        if success:
            self.test_results[phase]['passed'] += 1
            status = "✅"
        else:
            self.test_results[phase]['failed'] += 1
            status = "❌"
            if error_msg:
                self.test_results['errors'].append(f"{test_name}: {error_msg}")
        
        timing_info = f" ({duration:.2f}s)" if duration else ""
        print(f"{status} {test_name}{timing_info}")
        
        if duration:
            self.test_results['timings'][test_name] = duration
    
    def test_phase1_foundation(self):
        """Phase 1: Foundation & Docker Setup"""
        print("\n" + "="*60)
        print("🏗️  PHASE 1 VERIFICATION - Foundation & Docker Setup")
        print("="*60)
        
        # 1.1 Docker Services Health
        with TestTimer("Docker Services Health Check"):
            try:
                response = requests.get(f"{BASE_URL}/health", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    self.log_result('phase1', 'Docker Services Health', True, duration=0.1)
                    print(f"   📊 Status: {data['status']}")
                    print(f"   🗄️  Database: {data['database']}")
                    print(f"   🖥️  GPU Monitoring: {data['gpu_monitoring']}")
                else:
                    self.log_result('phase1', 'Docker Services Health', False, f"Status {response.status_code}")
            except Exception as e:
                self.log_result('phase1', 'Docker Services Health', False, str(e))
        
        # 1.2 Backend API Endpoints
        with TestTimer("Backend API Endpoints"):
            try:
                # Test multiple endpoints
                endpoints = [
                    ('/health', 'Health Check'),
                    ('/api/auth/register', 'Auth Register'),
                    ('/api/auth/login', 'Auth Login'),
                    ('/api/campaigns', 'Campaigns API'),
                    ('/api/ai/chat', 'AI Chat API')
                ]
                
                all_working = True
                for endpoint, name in endpoints:
                    try:
                        response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
                        if response.status_code in [200, 405, 401]:  # 405 = method not allowed, 401 = unauthorized
                            print(f"   ✅ {name}: {response.status_code}")
                        else:
                            print(f"   ❌ {name}: {response.status_code}")
                            all_working = False
                    except Exception as e:
                        print(f"   ❌ {name}: {e}")
                        all_working = False
                
                self.log_result('phase1', 'Backend API Endpoints', all_working)
            except Exception as e:
                self.log_result('phase1', 'Backend API Endpoints', False, str(e))
        
        # 1.3 LLM Services
        with TestTimer("LLM Services Check"):
            try:
                # Test LM Studio
                lm_response = requests.get("http://localhost:1234/v1/models", timeout=5)
                lm_working = lm_response.status_code == 200
                print(f"   🤖 LM Studio: {'✅' if lm_working else '❌'} ({lm_response.status_code})")
                
                # Test Ollama
                ollama_response = requests.get("http://localhost:11434/api/tags", timeout=5)
                ollama_working = ollama_response.status_code == 200
                print(f"   🦙 Ollama: {'✅' if ollama_working else '❌'} ({ollama_response.status_code})")
                
                self.log_result('phase1', 'LLM Services', lm_working and ollama_working)
            except Exception as e:
                self.log_result('phase1', 'LLM Services', False, str(e))
        
        # 1.4 Database Connectivity
        with TestTimer("Database Connectivity"):
            try:
                # Test SQLite through health endpoint
                response = requests.get(f"{BASE_URL}/health", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    db_working = data.get('database') == 'connected'
                    self.log_result('phase1', 'Database Connectivity', db_working)
                else:
                    self.log_result('phase1', 'Database Connectivity', False, f"Health check failed: {response.status_code}")
            except Exception as e:
                self.log_result('phase1', 'Database Connectivity', False, str(e))
        
        # 1.5 ChromaDB Integration
        with TestTimer("ChromaDB Integration"):
            try:
                response = requests.get("http://localhost:8000/api/v2/heartbeat", timeout=5)
                chromadb_working = response.status_code == 200
                self.log_result('phase1', 'ChromaDB Integration', chromadb_working)
                if chromadb_working:
                    print(f"   🗃️  ChromaDB: ✅ Connected")
                else:
                    print(f"   🗃️  ChromaDB: ❌ Status {response.status_code}")
            except Exception as e:
                self.log_result('phase1', 'ChromaDB Integration', False, str(e))
    
    def test_phase2_rag_system(self):
        """Phase 2: RAG & Vector Memory System"""
        print("\n" + "="*60)
        print("🧠 PHASE 2 VERIFICATION - RAG & Vector Memory System")
        print("="*60)
        
        # 2.1 Authentication System
        with TestTimer("Authentication System"):
            try:
                # Register test user
                register_data = {
                    'username': 'testuser_verification',
                    'email': 'test@verification.com',
                    'password': 'testpass123'
                }
                
                register_response = requests.post(f"{API_BASE}/auth/register", json=register_data, timeout=10)
                if register_response.status_code in [200, 201, 400]:  # 400 = user already exists
                    # Login
                    login_data = {
                        'username': 'testuser_verification',
                        'password': 'testpass123'
                    }
                    login_response = requests.post(f"{API_BASE}/auth/login", json=login_data, timeout=10)
                    
                    if login_response.status_code == 200:
                        self.token = login_response.json()['access_token']
                        self.log_result('phase2', 'Authentication System', True)
                        print(f"   🔐 Token obtained: {self.token[:20]}...")
                    else:
                        self.log_result('phase2', 'Authentication System', False, f"Login failed: {login_response.status_code}")
                else:
                    self.log_result('phase2', 'Authentication System', False, f"Registration failed: {register_response.status_code}")
            except Exception as e:
                self.log_result('phase2', 'Authentication System', False, str(e))
        
        if not self.token:
            print("❌ Cannot continue Phase 2 tests without authentication")
            return
        
        # 2.2 Campaign Management (CRUD)
        with TestTimer("Campaign Management CRUD"):
            try:
                headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
                
                # Create campaign
                campaign_data = {
                    'name': 'Verification Test Campaign',
                    'description': 'Testing campaign CRUD operations',
                    'game_system': 'wod',
                    'status': 'active'
                }
                
                create_response = requests.post(f"{API_BASE}/campaigns", json=campaign_data, headers=headers, timeout=30)
                if create_response.status_code in [200, 201]:
                    campaign = create_response.json()
                    campaign_id = campaign['id']
                    self.log_result('phase2', 'Campaign Creation', True)
                    print(f"   📝 Campaign created: ID {campaign_id}")
                    
                    # Read campaign
                    read_response = requests.get(f"{API_BASE}/campaigns/{campaign_id}", headers=headers, timeout=10)
                    if read_response.status_code == 200:
                        self.log_result('phase2', 'Campaign Read', True)
                        print(f"   📖 Campaign read: {read_response.json()['name']}")
                    else:
                        self.log_result('phase2', 'Campaign Read', False, f"Status {read_response.status_code}")
                    
                    # Update campaign
                    update_data = {'description': 'Updated verification test campaign'}
                    update_response = requests.put(f"{API_BASE}/campaigns/{campaign_id}", json=update_data, headers=headers, timeout=10)
                    if update_response.status_code == 200:
                        self.log_result('phase2', 'Campaign Update', True)
                        print(f"   ✏️  Campaign updated")
                    else:
                        self.log_result('phase2', 'Campaign Update', False, f"Status {update_response.status_code}")
                    
                    # Delete campaign
                    delete_response = requests.delete(f"{API_BASE}/campaigns/{campaign_id}", headers=headers, timeout=10)
                    if delete_response.status_code == 200:
                        self.log_result('phase2', 'Campaign Delete', True)
                        print(f"   🗑️  Campaign deleted")
                    else:
                        self.log_result('phase2', 'Campaign Delete', False, f"Status {delete_response.status_code}")
                    
                else:
                    self.log_result('phase2', 'Campaign Management CRUD', False, f"Create failed: {create_response.status_code}")
            except Exception as e:
                self.log_result('phase2', 'Campaign Management CRUD', False, str(e))
        
        # 2.3 RAG Memory Storage
        with TestTimer("RAG Memory Storage"):
            try:
                headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
                
                # Test memory storage through AI chat
                chat_data = {
                    'message': 'This is a test message for RAG memory storage verification',
                    'campaign_id': 0  # Global memory
                }
                
                chat_response = requests.post(f"{API_BASE}/ai/chat", json=chat_data, headers=headers, timeout=30)
                if chat_response.status_code == 200:
                    self.log_result('phase2', 'RAG Memory Storage', True)
                    print(f"   💾 Memory stored via AI chat")
                else:
                    self.log_result('phase2', 'RAG Memory Storage', False, f"Status {chat_response.status_code}")
            except Exception as e:
                self.log_result('phase2', 'RAG Memory Storage', False, str(e))
        
        # 2.4 Rule Book Integration
        with TestTimer("Rule Book Integration"):
            try:
                headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
                
                # Test rule book search
                search_data = {
                    'query': 'vampire character creation',
                    'limit': 3
                }
                
                search_response = requests.post(f"{API_BASE}/rule-books/search", json=search_data, headers=headers, timeout=10)
                if search_response.status_code == 200:
                    result = search_response.json()
                    if result['success'] and result['results_count'] > 0:
                        self.log_result('phase2', 'Rule Book Integration', True)
                        print(f"   📚 Found {result['results_count']} rule book results")
                        print(f"   📖 Sample: {result['results'][0]['text'][:50]}...")
                    else:
                        self.log_result('phase2', 'Rule Book Integration', False, "No results found")
                else:
                    self.log_result('phase2', 'Rule Book Integration', False, f"Status {search_response.status_code}")
            except Exception as e:
                self.log_result('phase2', 'Rule Book Integration', False, str(e))
        
        # 2.5 Vector Search Performance
        with TestTimer("Vector Search Performance"):
            try:
                headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
                
                # Test multiple search queries
                queries = [
                    'vampire character creation',
                    'dice rolling mechanics',
                    'storyteller guide',
                    'world of darkness setting',
                    'character stats'
                ]
                
                all_successful = True
                total_results = 0
                
                for query in queries:
                    search_data = {'query': query, 'limit': 1}
                    search_response = requests.post(f"{API_BASE}/rule-books/search", json=search_data, headers=headers, timeout=10)
                    
                    if search_response.status_code == 200:
                        result = search_response.json()
                        if result['success'] and result['results_count'] > 0:
                            total_results += result['results_count']
                        else:
                            all_successful = False
                    else:
                        all_successful = False
                
                self.log_result('phase2', 'Vector Search Performance', all_successful)
                print(f"   🔍 Total results across queries: {total_results}")
                
            except Exception as e:
                self.log_result('phase2', 'Vector Search Performance', False, str(e))
    
    def test_error_scenarios(self):
        """Test error scenarios and edge cases"""
        print("\n" + "="*60)
        print("⚠️  ERROR SCENARIOS & EDGE CASES TESTING")
        print("="*60)
        
        # Error 1: Invalid authentication
        with TestTimer("Invalid Authentication"):
            try:
                headers = {'Authorization': 'Bearer invalid_token', 'Content-Type': 'application/json'}
                response = requests.get(f"{API_BASE}/campaigns", headers=headers, timeout=5)
                if response.status_code == 401:
                    self.log_result('phase1', 'Invalid Authentication Handling', True)
                    print(f"   🔒 Correctly rejected invalid token: 401")
                else:
                    self.log_result('phase1', 'Invalid Authentication Handling', False, f"Expected 401, got {response.status_code}")
            except Exception as e:
                self.log_result('phase1', 'Invalid Authentication Handling', False, str(e))
        
        # Error 2: Invalid campaign data
        with TestTimer("Invalid Campaign Data"):
            try:
                if self.token:
                    headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
                    invalid_data = {'name': ''}  # Missing required fields
                    response = requests.post(f"{API_BASE}/campaigns", json=invalid_data, headers=headers, timeout=10)
                    if response.status_code == 400:
                        self.log_result('phase2', 'Invalid Campaign Data Handling', True)
                        print(f"   📝 Correctly rejected invalid data: 400")
                    else:
                        self.log_result('phase2', 'Invalid Campaign Data Handling', False, f"Expected 400, got {response.status_code}")
            except Exception as e:
                self.log_result('phase2', 'Invalid Campaign Data Handling', False, str(e))
        
        # Error 3: Non-existent resource
        with TestTimer("Non-existent Resource"):
            try:
                if self.token:
                    headers = {'Authorization': f'Bearer {self.token}'}
                    response = requests.get(f"{API_BASE}/campaigns/99999", headers=headers, timeout=5)
                    if response.status_code == 404:
                        self.log_result('phase2', 'Non-existent Resource Handling', True)
                        print(f"   🔍 Correctly handled missing resource: 404")
                    else:
                        self.log_result('phase2', 'Non-existent Resource Handling', False, f"Expected 404, got {response.status_code}")
            except Exception as e:
                self.log_result('phase2', 'Non-existent Resource Handling', False, str(e))
        
        # Error 4: Invalid search query
        with TestTimer("Invalid Search Query"):
            try:
                if self.token:
                    headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
                    invalid_search = {'query': '', 'limit': 0}  # Empty query, invalid limit
                    response = requests.post(f"{API_BASE}/rule-books/search", json=invalid_search, headers=headers, timeout=5)
                    if response.status_code in [400, 422]:
                        self.log_result('phase2', 'Invalid Search Query Handling', True)
                        print(f"   🔍 Correctly handled invalid search: {response.status_code}")
                    else:
                        self.log_result('phase2', 'Invalid Search Query Handling', False, f"Expected 400/422, got {response.status_code}")
            except Exception as e:
                self.log_result('phase2', 'Invalid Search Query Handling', False, str(e))
    
    def test_data_integrity(self):
        """Test data integrity and persistence"""
        print("\n" + "="*60)
        print("🔒 DATA INTEGRITY & PERSISTENCE TESTING")
        print("="*60)
        
        # Test 1: Campaign persistence
        with TestTimer("Campaign Data Persistence"):
            try:
                if self.token:
                    headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
                    
                    # Create campaign
                    campaign_data = {
                        'name': 'Persistence Test Campaign',
                        'description': 'Testing data persistence',
                        'game_system': 'wod',
                        'status': 'active'
                    }
                    
                    create_response = requests.post(f"{API_BASE}/campaigns", json=campaign_data, headers=headers, timeout=30)
                    if create_response.status_code in [200, 201]:
                        campaign_id = create_response.json()['id']
                        
                        # Wait a moment
                        time.sleep(1)
                        
                        # Verify it still exists
                        read_response = requests.get(f"{API_BASE}/campaigns/{campaign_id}", headers=headers, timeout=10)
                        if read_response.status_code == 200:
                            stored_campaign = read_response.json()
                            if stored_campaign['name'] == campaign_data['name']:
                                self.log_result('phase2', 'Campaign Data Persistence', True)
                                print(f"   💾 Campaign data persisted correctly")
                                
                                # Cleanup
                                requests.delete(f"{API_BASE}/campaigns/{campaign_id}", headers=headers, timeout=10)
                            else:
                                self.log_result('phase2', 'Campaign Data Persistence', False, "Data mismatch")
                        else:
                            self.log_result('phase2', 'Campaign Data Persistence', False, f"Read failed: {read_response.status_code}")
                    else:
                        self.log_result('phase2', 'Campaign Data Persistence', False, f"Create failed: {create_response.status_code}")
            except Exception as e:
                self.log_result('phase2', 'Campaign Data Persistence', False, str(e))
        
        # Test 2: Rule book search consistency
        with TestTimer("Rule Book Search Consistency"):
            try:
                if self.token:
                    headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
                    
                    # Run same search multiple times
                    search_data = {'query': 'vampire', 'limit': 3}
                    results = []
                    
                    for i in range(3):
                        search_response = requests.post(f"{API_BASE}/rule-books/search", json=search_data, headers=headers, timeout=10)
                        if search_response.status_code == 200:
                            result = search_response.json()
                            results.append(result['results_count'])
                        time.sleep(0.5)  # Small delay between searches
                    
                    # Check consistency
                    if len(set(results)) == 1 and results[0] > 0:  # All results same and > 0
                        self.log_result('phase2', 'Rule Book Search Consistency', True)
                        print(f"   🔍 Search results consistent: {results[0]} results each time")
                    else:
                        self.log_result('phase2', 'Rule Book Search Consistency', False, f"Inconsistent results: {results}")
            except Exception as e:
                self.log_result('phase2', 'Rule Book Search Consistency', False, str(e))
    
    def print_summary(self):
        """Print comprehensive test summary"""
        print("\n" + "="*60)
        print("📊 COMPREHENSIVE VERIFICATION SUMMARY")
        print("="*60)
        
        # Phase 1 Summary
        phase1_total = self.test_results['phase1']['total']
        phase1_passed = self.test_results['phase1']['passed']
        phase1_failed = self.test_results['phase1']['failed']
        phase1_success_rate = (phase1_passed / phase1_total * 100) if phase1_total > 0 else 0
        
        print(f"\n🏗️  PHASE 1 - Foundation & Docker Setup:")
        print(f"   ✅ Passed: {phase1_passed}/{phase1_total} ({phase1_success_rate:.1f}%)")
        print(f"   ❌ Failed: {phase1_failed}/{phase1_total}")
        
        # Phase 2 Summary
        phase2_total = self.test_results['phase2']['total']
        phase2_passed = self.test_results['phase2']['passed']
        phase2_failed = self.test_results['phase2']['failed']
        phase2_success_rate = (phase2_passed / phase2_total * 100) if phase2_total > 0 else 0
        
        print(f"\n🧠 PHASE 2 - RAG & Vector Memory System:")
        print(f"   ✅ Passed: {phase2_passed}/{phase2_total} ({phase2_success_rate:.1f}%)")
        print(f"   ❌ Failed: {phase2_failed}/{phase2_total}")
        
        # Overall Summary
        total_tests = phase1_total + phase2_total
        total_passed = phase1_passed + phase2_passed
        total_failed = phase1_failed + phase2_failed
        overall_success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        print(f"\n🎯 OVERALL RESULTS:")
        print(f"   ✅ Total Passed: {total_passed}/{total_tests} ({overall_success_rate:.1f}%)")
        print(f"   ❌ Total Failed: {total_failed}/{total_tests}")
        
        # Performance Summary
        if self.test_results['timings']:
            print(f"\n⏱️  PERFORMANCE TIMINGS:")
            for test_name, duration in self.test_results['timings'].items():
                print(f"   {test_name}: {duration:.2f}s")
        
        # Error Summary
        if self.test_results['errors']:
            print(f"\n⚠️  ERRORS ENCOUNTERED:")
            for error in self.test_results['errors']:
                print(f"   • {error}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        if overall_success_rate >= 90:
            print(f"   🎉 Excellent! System is ready for Phase 3 implementation")
        elif overall_success_rate >= 75:
            print(f"   ✅ Good! Minor issues to address before Phase 3")
        elif overall_success_rate >= 50:
            print(f"   ⚠️  Fair! Several issues need attention before Phase 3")
        else:
            print(f"   ❌ Poor! Major issues must be resolved before Phase 3")
        
        return overall_success_rate >= 75

def main():
    """Run comprehensive verification"""
    print("🚀 ShadowRealms AI - Comprehensive Phase 1 + 2 Verification")
    print("="*60)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tester = ComprehensiveTester()
    
    try:
        # Run all tests
        tester.test_phase1_foundation()
        tester.test_phase2_rag_system()
        tester.test_error_scenarios()
        tester.test_data_integrity()
        
        # Print summary
        ready_for_phase3 = tester.print_summary()
        
        if ready_for_phase3:
            print(f"\n🎯 VERDICT: ✅ READY FOR PHASE 3!")
        else:
            print(f"\n🎯 VERDICT: ⚠️  NOT READY - ISSUES NEED RESOLUTION")
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Testing failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
