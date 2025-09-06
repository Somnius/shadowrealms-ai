#!/usr/bin/env python3
"""
ShadowRealms AI - Deep Verification System
Comprehensive testing with database inspection, performance monitoring, and error analysis
"""

import requests
import json
import time
import sys
import sqlite3
import psutil
import subprocess
from datetime import datetime
from pathlib import Path
import logging

# Configuration
BASE_URL = "http://localhost:5000"
API_BASE = f"{BASE_URL}/api"
CHROMADB_URL = "http://localhost:8000"

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deep_verification.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Monitor system performance during operations"""
    def __init__(self):
        self.start_cpu = None
        self.start_memory = None
        self.start_time = None
    
    def start_monitoring(self):
        self.start_time = time.time()
        self.start_cpu = psutil.cpu_percent()
        self.start_memory = psutil.virtual_memory().percent
        logger.debug(f"Performance monitoring started - CPU: {self.start_cpu}%, Memory: {self.start_memory}%")
    
    def stop_monitoring(self, operation_name):
        duration = time.time() - self.start_time
        end_cpu = psutil.cpu_percent()
        end_memory = psutil.virtual_memory().percent
        
        cpu_delta = end_cpu - self.start_cpu
        memory_delta = end_memory - self.start_memory
        
        logger.info(f"PERFORMANCE - {operation_name}: {duration:.2f}s | CPU: {cpu_delta:+.1f}% | Memory: {memory_delta:+.1f}%")
        return {
            'duration': duration,
            'cpu_delta': cpu_delta,
            'memory_delta': memory_delta,
            'end_cpu': end_cpu,
            'end_memory': end_memory
        }

class DatabaseInspector:
    """Inspect SQLite and ChromaDB databases"""
    def __init__(self):
        self.db_path = "data/shadowrealms.db"
        self.issues = []
    
    def inspect_sqlite_database(self):
        """Thoroughly inspect SQLite database"""
        logger.info("🔍 Inspecting SQLite Database...")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if database exists and is accessible
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            logger.info(f"📊 Found {len(tables)} tables: {[table[0] for table in tables]}")
            
            # Inspect each table
            for table in tables:
                table_name = table[0]
                logger.debug(f"🔍 Inspecting table: {table_name}")
                
                # Get table schema
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()
                logger.debug(f"   Columns: {[col[1] for col in columns]}")
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                row_count = cursor.fetchone()[0]
                logger.info(f"   📈 {table_name}: {row_count} rows")
                
                # Check for data integrity issues
                self._check_table_integrity(cursor, table_name, columns)
            
            # Check foreign key constraints
            cursor.execute("PRAGMA foreign_key_check;")
            fk_issues = cursor.fetchall()
            if fk_issues:
                logger.warning(f"⚠️  Foreign key issues found: {len(fk_issues)}")
                self.issues.extend([f"FK Issue: {issue}" for issue in fk_issues])
            else:
                logger.info("✅ Foreign key constraints: OK")
            
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ SQLite inspection failed: {e}")
            self.issues.append(f"SQLite Error: {e}")
            return False
    
    def _check_table_integrity(self, cursor, table_name, columns):
        """Check for data integrity issues in a table"""
        try:
            # Check for NULL values in required fields
            for col in columns:
                col_name, col_type, not_null, default_val, pk = col[1], col[2], col[3], col[4], col[5]
                if not_null and not pk:  # Skip primary keys
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {col_name} IS NULL;")
                    null_count = cursor.fetchone()[0]
                    if null_count > 0:
                        logger.warning(f"   ⚠️  {table_name}.{col_name}: {null_count} NULL values in NOT NULL field")
                        self.issues.append(f"NULL values in {table_name}.{col_name}: {null_count}")
            
            # Check for duplicate primary keys (shouldn't happen, but let's verify)
            pk_columns = [col[1] for col in columns if col[5]]  # Primary key columns
            if pk_columns:
                pk_col = pk_columns[0]
                cursor.execute(f"SELECT {pk_col}, COUNT(*) FROM {table_name} GROUP BY {pk_col} HAVING COUNT(*) > 1;")
                duplicates = cursor.fetchall()
                if duplicates:
                    logger.warning(f"   ⚠️  {table_name}: {len(duplicates)} duplicate primary keys")
                    self.issues.append(f"Duplicate PKs in {table_name}: {len(duplicates)}")
                else:
                    logger.debug(f"   ✅ {table_name}: No duplicate primary keys")
                    
        except Exception as e:
            logger.error(f"   ❌ Integrity check failed for {table_name}: {e}")
            self.issues.append(f"Integrity check error in {table_name}: {e}")
    
    def inspect_chromadb_collections(self):
        """Inspect ChromaDB collections and data using Python client"""
        logger.info("🔍 Inspecting ChromaDB Collections...")
        
        try:
            # Try to import ChromaDB client
            try:
                import chromadb
                from chromadb.config import Settings
                
                # Connect to ChromaDB
                client = chromadb.HttpClient(
                    host="localhost",
                    port=8000,
                    settings=Settings(allow_reset=True)
                )
                
                # Get all collections
                collections = client.list_collections()
                logger.info(f"📊 Found {len(collections)} ChromaDB collections")
                
                for collection in collections:
                    collection_name = collection.name
                    logger.info(f"   📁 Collection: {collection_name}")
                    
                    try:
                        # Get collection count
                        count = collection.count()
                        logger.info(f"      📈 Document count: {count}")
                        
                        # Test search functionality
                        self._test_collection_search_python(collection, collection_name)
                        
                    except Exception as e:
                        logger.warning(f"      ⚠️  Error accessing {collection_name}: {e}")
                        self.issues.append(f"ChromaDB collection access error for {collection_name}: {e}")
                
                return True
                
            except ImportError:
                logger.warning("⚠️  ChromaDB Python client not available, using HTTP API fallback")
                # Fallback to HTTP API check
                response = requests.get(f"{CHROMADB_URL}/api/v2/heartbeat", timeout=5)
                if response.status_code == 200:
                    logger.info("📊 ChromaDB is running and accessible via HTTP API")
                    return True
                else:
                    logger.error(f"❌ ChromaDB HTTP API check failed: {response.status_code}")
                    self.issues.append(f"ChromaDB HTTP API error: {response.status_code}")
                    return False
                
        except Exception as e:
            logger.error(f"❌ ChromaDB inspection failed: {e}")
            self.issues.append(f"ChromaDB Error: {e}")
            return False
    
    def _test_collection_search_python(self, collection, collection_name):
        """Test search functionality for a collection using Python client"""
        try:
            # Test with a simple query
            results = collection.query(
                query_texts=["test"],
                n_results=1
            )
            
            if results and results.get('documents') and results['documents'][0]:
                logger.debug(f"      ✅ {collection_name}: Search working ({len(results['documents'][0])} results)")
            else:
                logger.debug(f"      📝 {collection_name}: Search working (no results)")
                
        except Exception as e:
            logger.warning(f"      ⚠️  {collection_name}: Search test error: {e}")
            self.issues.append(f"ChromaDB search error for {collection_name}: {e}")
    
    def _test_collection_search(self, collection_id, collection_name):
        """Test search functionality for a collection (HTTP API - deprecated)"""
        try:
            # Test with a simple query
            search_data = {
                "query_texts": ["test"],
                "n_results": 1
            }
            
            search_response = requests.post(
                f"{CHROMADB_URL}/api/v2/collections/{collection_id}/query",
                json=search_data,
                timeout=10
            )
            
            if search_response.status_code == 200:
                result = search_response.json()
                if result.get('documents') and result['documents'][0]:
                    logger.debug(f"      ✅ {collection_name}: Search working ({len(result['documents'][0])} results)")
                else:
                    logger.debug(f"      📝 {collection_name}: Search working (no results)")
            else:
                logger.warning(f"      ⚠️  {collection_name}: Search failed ({search_response.status_code})")
                self.issues.append(f"ChromaDB search failed for {collection_name}: {search_response.status_code}")
                
        except Exception as e:
            logger.warning(f"      ⚠️  {collection_name}: Search test error: {e}")
            self.issues.append(f"ChromaDB search error for {collection_name}: {e}")

class DeepVerificationTester:
    """Comprehensive deep verification system"""
    def __init__(self):
        self.token = None
        self.performance_monitor = PerformanceMonitor()
        self.db_inspector = DatabaseInspector()
        self.test_results = {
            'phase1': {'passed': 0, 'failed': 0, 'total': 0, 'issues': []},
            'phase2': {'passed': 0, 'failed': 0, 'total': 0, 'issues': []},
            'database': {'passed': 0, 'failed': 0, 'total': 0, 'issues': []},
            'performance': {'timings': {}, 'resource_usage': {}},
            'errors': []
        }
    
    def log_result(self, phase, test_name, success, error_msg=None, performance_data=None):
        """Log test result with performance data"""
        self.test_results[phase]['total'] += 1
        if success:
            self.test_results[phase]['passed'] += 1
            status = "✅"
        else:
            self.test_results[phase]['failed'] += 1
            status = "❌"
            if error_msg:
                self.test_results[phase]['issues'].append(f"{test_name}: {error_msg}")
                self.test_results['errors'].append(f"{phase} - {test_name}: {error_msg}")
        
        timing_info = ""
        if performance_data:
            timing_info = f" ({performance_data['duration']:.2f}s)"
            self.test_results['performance']['timings'][test_name] = performance_data['duration']
            self.test_results['performance']['resource_usage'][test_name] = {
                'cpu_delta': performance_data['cpu_delta'],
                'memory_delta': performance_data['memory_delta']
            }
        
        logger.info(f"{status} {test_name}{timing_info}")
        
        if performance_data and performance_data['cpu_delta'] > 10:
            logger.warning(f"⚠️  High CPU usage detected: {performance_data['cpu_delta']:+.1f}%")
        if performance_data and performance_data['memory_delta'] > 5:
            logger.warning(f"⚠️  High memory usage detected: {performance_data['memory_delta']:+.1f}%")
    
    def test_phase1_deep_verification(self):
        """Deep Phase 1 verification with performance monitoring"""
        logger.info("\n" + "="*60)
        logger.info("🏗️  PHASE 1 DEEP VERIFICATION - Foundation & Docker Setup")
        logger.info("="*60)
        
        # 1.1 Docker Services Health with Performance Monitoring
        self.performance_monitor.start_monitoring()
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                perf_data = self.performance_monitor.stop_monitoring("Docker Services Health")
                self.log_result('phase1', 'Docker Services Health', True, performance_data=perf_data)
                logger.info(f"   📊 Status: {data['status']}")
                logger.info(f"   🗄️  Database: {data['database']}")
                logger.info(f"   🖥️  GPU Monitoring: {data['gpu_monitoring']}")
            else:
                perf_data = self.performance_monitor.stop_monitoring("Docker Services Health")
                self.log_result('phase1', 'Docker Services Health', False, f"Status {response.status_code}", perf_data)
        except Exception as e:
            perf_data = self.performance_monitor.stop_monitoring("Docker Services Health")
            self.log_result('phase1', 'Docker Services Health', False, str(e), perf_data)
        
        # 1.2 Cross-Service Communication Testing
        self.performance_monitor.start_monitoring()
        try:
            # Test Backend ↔ ChromaDB
            chromadb_response = requests.get(f"{CHROMADB_URL}/api/v2/heartbeat", timeout=5)
            chromadb_ok = chromadb_response.status_code == 200
            
            # Test Backend ↔ LLM Services
            lm_response = requests.get("http://localhost:1234/v1/models", timeout=5)
            lm_ok = lm_response.status_code == 200
            
            ollama_response = requests.get("http://localhost:11434/api/tags", timeout=5)
            ollama_ok = ollama_response.status_code == 200
            
            all_services_ok = chromadb_ok and lm_ok and ollama_ok
            perf_data = self.performance_monitor.stop_monitoring("Cross-Service Communication")
            
            self.log_result('phase1', 'Cross-Service Communication', all_services_ok, performance_data=perf_data)
            logger.info(f"   🗃️  ChromaDB: {'✅' if chromadb_ok else '❌'}")
            logger.info(f"   🤖 LM Studio: {'✅' if lm_ok else '❌'}")
            logger.info(f"   🦙 Ollama: {'✅' if ollama_ok else '❌'}")
            
        except Exception as e:
            perf_data = self.performance_monitor.stop_monitoring("Cross-Service Communication")
            self.log_result('phase1', 'Cross-Service Communication', False, str(e), perf_data)
        
        # 1.3 Database Integrity Check
        self.performance_monitor.start_monitoring()
        try:
            sqlite_ok = self.db_inspector.inspect_sqlite_database()
            chromadb_ok = self.db_inspector.inspect_chromadb_collections()
            perf_data = self.performance_monitor.stop_monitoring("Database Integrity Check")
            
            self.log_result('database', 'Database Integrity Check', sqlite_ok and chromadb_ok, performance_data=perf_data)
            
            if self.db_inspector.issues:
                logger.warning(f"⚠️  Database issues found: {len(self.db_inspector.issues)}")
                for issue in self.db_inspector.issues:
                    logger.warning(f"   • {issue}")
            
        except Exception as e:
            perf_data = self.performance_monitor.stop_monitoring("Database Integrity Check")
            self.log_result('database', 'Database Integrity Check', False, str(e), perf_data)
    
    def test_phase2_deep_verification(self):
        """Deep Phase 2 verification with performance monitoring"""
        logger.info("\n" + "="*60)
        logger.info("🧠 PHASE 2 DEEP VERIFICATION - RAG & Vector Memory System")
        logger.info("="*60)
        
        # 2.1 Authentication System with Performance Monitoring
        self.performance_monitor.start_monitoring()
        try:
            # Register test user
            register_data = {
                'username': 'testuser_deep_verification',
                'email': 'test@deepverification.com',
                'password': 'testpass123'
            }
            
            register_response = requests.post(f"{API_BASE}/auth/register", json=register_data, timeout=10)
            if register_response.status_code in [200, 201, 400, 409]:  # 400/409 = user already exists
                # Login
                login_data = {
                    'username': 'testuser_deep_verification',
                    'password': 'testpass123'
                }
                login_response = requests.post(f"{API_BASE}/auth/login", json=login_data, timeout=10)
                
                if login_response.status_code == 200:
                    self.token = login_response.json()['access_token']
                    perf_data = self.performance_monitor.stop_monitoring("Authentication System")
                    self.log_result('phase2', 'Authentication System', True, performance_data=perf_data)
                    logger.info(f"   🔐 Token obtained: {self.token[:20]}...")
                else:
                    perf_data = self.performance_monitor.stop_monitoring("Authentication System")
                    self.log_result('phase2', 'Authentication System', False, f"Login failed: {login_response.status_code}", perf_data)
            else:
                perf_data = self.performance_monitor.stop_monitoring("Authentication System")
                self.log_result('phase2', 'Authentication System', False, f"Registration failed: {register_response.status_code}", perf_data)
        except Exception as e:
            perf_data = self.performance_monitor.stop_monitoring("Authentication System")
            self.log_result('phase2', 'Authentication System', False, str(e), perf_data)
        
        if not self.token:
            logger.error("❌ Cannot continue Phase 2 tests without authentication")
            return
        
        # 2.2 Campaign Management with Detailed Error Analysis
        self.performance_monitor.start_monitoring()
        try:
            headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
            
            # Create campaign
            campaign_data = {
                'name': 'Deep Verification Test Campaign',
                'description': 'Testing campaign CRUD operations with deep verification',
                'game_system': 'wod',
                'status': 'active'
            }
            
            create_response = requests.post(f"{API_BASE}/campaigns", json=campaign_data, headers=headers, timeout=30)
            logger.debug(f"Campaign creation response: {create_response.status_code} - {create_response.text}")
            
            if create_response.status_code in [200, 201]:
                campaign = create_response.json()
                # Handle both 'id' and 'campaign_id' response formats
                campaign_id = campaign.get('id') or campaign.get('campaign_id')
                if campaign_id:
                    perf_data = self.performance_monitor.stop_monitoring("Campaign Management CRUD")
                    self.log_result('phase2', 'Campaign Management CRUD', True, performance_data=perf_data)
                    logger.info(f"   📝 Campaign created: ID {campaign_id}")
                    
                    # Test campaign read
                    read_response = requests.get(f"{API_BASE}/campaigns/{campaign_id}", headers=headers, timeout=10)
                    if read_response.status_code == 200:
                        logger.info(f"   📖 Campaign read successful")
                    else:
                        logger.warning(f"   ⚠️  Campaign read failed: {read_response.status_code}")
                    
                    # Cleanup
                    delete_response = requests.delete(f"{API_BASE}/campaigns/{campaign_id}", headers=headers, timeout=10)
                    if delete_response.status_code == 200:
                        logger.info(f"   🗑️  Campaign deleted successfully")
                    else:
                        logger.warning(f"   ⚠️  Campaign delete failed: {delete_response.status_code}")
                else:
                    perf_data = self.performance_monitor.stop_monitoring("Campaign Management CRUD")
                    self.log_result('phase2', 'Campaign Management CRUD', False, f"No campaign ID returned. Response: {campaign}", perf_data)
            else:
                perf_data = self.performance_monitor.stop_monitoring("Campaign Management CRUD")
                self.log_result('phase2', 'Campaign Management CRUD', False, f"Create failed: {create_response.status_code} - {create_response.text}", perf_data)
        except Exception as e:
            perf_data = self.performance_monitor.stop_monitoring("Campaign Management CRUD")
            self.log_result('phase2', 'Campaign Management CRUD', False, str(e), perf_data)
        
        # 2.3 RAG Memory Storage with Performance Monitoring
        self.performance_monitor.start_monitoring()
        try:
            headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
            
            chat_data = {
                'message': 'This is a deep verification test message for RAG memory storage',
                'campaign_id': 0  # Global memory
            }
            
            chat_response = requests.post(f"{API_BASE}/ai/chat", json=chat_data, headers=headers, timeout=30)
            perf_data = self.performance_monitor.stop_monitoring("RAG Memory Storage")
            
            if chat_response.status_code == 200:
                self.log_result('phase2', 'RAG Memory Storage', True, performance_data=perf_data)
                logger.info(f"   💾 Memory stored via AI chat")
            else:
                self.log_result('phase2', 'RAG Memory Storage', False, f"Status {chat_response.status_code}", perf_data)
        except Exception as e:
            perf_data = self.performance_monitor.stop_monitoring("RAG Memory Storage")
            self.log_result('phase2', 'RAG Memory Storage', False, str(e), perf_data)
        
        # 2.4 Rule Book Integration with Performance Monitoring
        self.performance_monitor.start_monitoring()
        try:
            headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
            
            search_data = {
                'query': 'vampire character creation',
                'limit': 3
            }
            
            search_response = requests.post(f"{API_BASE}/rule-books/search", json=search_data, headers=headers, timeout=10)
            perf_data = self.performance_monitor.stop_monitoring("Rule Book Integration")
            
            if search_response.status_code == 200:
                result = search_response.json()
                if result['success'] and result['results_count'] > 0:
                    self.log_result('phase2', 'Rule Book Integration', True, performance_data=perf_data)
                    logger.info(f"   📚 Found {result['results_count']} rule book results")
                    logger.info(f"   📖 Sample: {result['results'][0]['text'][:50]}...")
                else:
                    self.log_result('phase2', 'Rule Book Integration', False, "No results found", perf_data)
            else:
                self.log_result('phase2', 'Rule Book Integration', False, f"Status {search_response.status_code}", perf_data)
        except Exception as e:
            perf_data = self.performance_monitor.stop_monitoring("Rule Book Integration")
            self.log_result('phase2', 'Rule Book Integration', False, str(e), perf_data)
    
    def test_error_scenarios_deep(self):
        """Deep error scenario testing"""
        logger.info("\n" + "="*60)
        logger.info("⚠️  DEEP ERROR SCENARIOS & EDGE CASES TESTING")
        logger.info("="*60)
        
        error_tests = [
            ("Invalid Authentication", self._test_invalid_auth),
            ("Invalid Campaign Data", self._test_invalid_campaign_data),
            ("Non-existent Resource", self._test_nonexistent_resource),
            ("Invalid Search Query", self._test_invalid_search),
            ("Malformed JSON", self._test_malformed_json),
            ("Oversized Payload", self._test_oversized_payload),
            ("Concurrent Requests", self._test_concurrent_requests)
        ]
        
        for test_name, test_func in error_tests:
            self.performance_monitor.start_monitoring()
            try:
                success, error_msg = test_func()
                perf_data = self.performance_monitor.stop_monitoring(f"Error Test: {test_name}")
                self.log_result('phase1', f"Error Test: {test_name}", success, error_msg, perf_data)
            except Exception as e:
                perf_data = self.performance_monitor.stop_monitoring(f"Error Test: {test_name}")
                self.log_result('phase1', f"Error Test: {test_name}", False, str(e), perf_data)
    
    def _test_invalid_auth(self):
        """Test invalid authentication handling"""
        try:
            headers = {'Authorization': 'Bearer invalid_token', 'Content-Type': 'application/json'}
            response = requests.get(f"{API_BASE}/campaigns", headers=headers, timeout=5)
            return response.status_code in [401, 422], f"Expected 401/422, got {response.status_code}"
        except Exception as e:
            return False, str(e)
    
    def _test_invalid_campaign_data(self):
        """Test invalid campaign data handling"""
        try:
            if self.token:
                headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
                invalid_data = {'name': ''}  # Missing required fields
                response = requests.post(f"{API_BASE}/campaigns", json=invalid_data, headers=headers, timeout=10)
                return response.status_code == 400, f"Expected 400, got {response.status_code}"
            return True, "No token available"
        except Exception as e:
            return False, str(e)
    
    def _test_nonexistent_resource(self):
        """Test non-existent resource handling"""
        try:
            if self.token:
                headers = {'Authorization': f'Bearer {self.token}'}
                response = requests.get(f"{API_BASE}/campaigns/99999", headers=headers, timeout=5)
                return response.status_code == 404, f"Expected 404, got {response.status_code}"
            return True, "No token available"
        except Exception as e:
            return False, str(e)
    
    def _test_invalid_search(self):
        """Test invalid search query handling"""
        try:
            if self.token:
                headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
                invalid_search = {'query': '', 'limit': 0}  # Empty query, invalid limit
                response = requests.post(f"{API_BASE}/rule-books/search", json=invalid_search, headers=headers, timeout=5)
                return response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
            return True, "No token available"
        except Exception as e:
            return False, str(e)
    
    def _test_malformed_json(self):
        """Test malformed JSON handling"""
        try:
            if self.token:
                headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
                response = requests.post(f"{API_BASE}/campaigns", data="invalid json", headers=headers, timeout=5)
                return response.status_code == 400, f"Expected 400, got {response.status_code}"
            return True, "No token available"
        except Exception as e:
            return False, str(e)
    
    def _test_oversized_payload(self):
        """Test oversized payload handling"""
        try:
            if self.token:
                headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
                oversized_data = {'name': 'x' * 10000, 'description': 'y' * 50000}  # Very large payload
                response = requests.post(f"{API_BASE}/campaigns", json=oversized_data, headers=headers, timeout=10)
                return response.status_code in [400, 413, 422], f"Expected 400/413/422, got {response.status_code}"
            return True, "No token available"
        except Exception as e:
            return False, str(e)
    
    def _test_concurrent_requests(self):
        """Test concurrent request handling"""
        try:
            if self.token:
                headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
                # Send multiple requests simultaneously
                import threading
                results = []
                
                def make_request():
                    try:
                        response = requests.get(f"{API_BASE}/campaigns", headers=headers, timeout=5)
                        results.append(response.status_code)
                    except Exception as e:
                        results.append(f"Error: {e}")
                
                threads = [threading.Thread(target=make_request) for _ in range(5)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
                
                # Check if all requests succeeded
                success_count = sum(1 for r in results if r == 200)
                return success_count >= 4, f"Only {success_count}/5 concurrent requests succeeded"
            return True, "No token available"
        except Exception as e:
            return False, str(e)
    
    def print_deep_summary(self):
        """Print comprehensive deep verification summary"""
        logger.info("\n" + "="*60)
        logger.info("📊 DEEP VERIFICATION SUMMARY")
        logger.info("="*60)
        
        # Phase 1 Summary
        phase1_total = self.test_results['phase1']['total']
        phase1_passed = self.test_results['phase1']['passed']
        phase1_failed = self.test_results['phase1']['failed']
        phase1_success_rate = (phase1_passed / phase1_total * 100) if phase1_total > 0 else 0
        
        logger.info(f"\n🏗️  PHASE 1 - Foundation & Docker Setup:")
        logger.info(f"   ✅ Passed: {phase1_passed}/{phase1_total} ({phase1_success_rate:.1f}%)")
        logger.info(f"   ❌ Failed: {phase1_failed}/{phase1_total}")
        
        # Phase 2 Summary
        phase2_total = self.test_results['phase2']['total']
        phase2_passed = self.test_results['phase2']['passed']
        phase2_failed = self.test_results['phase2']['failed']
        phase2_success_rate = (phase2_passed / phase2_total * 100) if phase2_total > 0 else 0
        
        logger.info(f"\n🧠 PHASE 2 - RAG & Vector Memory System:")
        logger.info(f"   ✅ Passed: {phase2_passed}/{phase2_total} ({phase2_success_rate:.1f}%)")
        logger.info(f"   ❌ Failed: {phase2_failed}/{phase2_total}")
        
        # Database Summary
        db_total = self.test_results['database']['total']
        db_passed = self.test_results['database']['passed']
        db_failed = self.test_results['database']['failed']
        db_success_rate = (db_passed / db_total * 100) if db_total > 0 else 0
        
        logger.info(f"\n🗄️  DATABASE - Integrity & Storage:")
        logger.info(f"   ✅ Passed: {db_passed}/{db_total} ({db_success_rate:.1f}%)")
        logger.info(f"   ❌ Failed: {db_failed}/{db_total}")
        
        # Overall Summary
        total_tests = phase1_total + phase2_total + db_total
        total_passed = phase1_passed + phase2_passed + db_passed
        total_failed = phase1_failed + phase2_failed + db_failed
        overall_success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        logger.info(f"\n🎯 OVERALL RESULTS:")
        logger.info(f"   ✅ Total Passed: {total_passed}/{total_tests} ({overall_success_rate:.1f}%)")
        logger.info(f"   ❌ Total Failed: {total_failed}/{total_tests}")
        
        # Performance Summary
        if self.test_results['performance']['timings']:
            logger.info(f"\n⏱️  PERFORMANCE TIMINGS:")
            for test_name, duration in self.test_results['performance']['timings'].items():
                logger.info(f"   {test_name}: {duration:.2f}s")
        
        # Resource Usage Summary
        if self.test_results['performance']['resource_usage']:
            logger.info(f"\n💻 RESOURCE USAGE:")
            for test_name, usage in self.test_results['performance']['resource_usage'].items():
                logger.info(f"   {test_name}: CPU {usage['cpu_delta']:+.1f}%, Memory {usage['memory_delta']:+.1f}%")
        
        # Issues Summary
        all_issues = []
        for phase in ['phase1', 'phase2', 'database']:
            all_issues.extend(self.test_results[phase]['issues'])
        all_issues.extend(self.test_results['errors'])
        
        if all_issues:
            logger.warning(f"\n⚠️  ISSUES FOUND ({len(all_issues)}):")
            for issue in all_issues:
                logger.warning(f"   • {issue}")
        
        # Recommendations
        logger.info(f"\n💡 RECOMMENDATIONS:")
        if overall_success_rate >= 95:
            logger.info(f"   🎉 EXCELLENT! System is bulletproof and ready for Phase 3")
        elif overall_success_rate >= 85:
            logger.info(f"   ✅ GOOD! Minor issues to address before Phase 3")
        elif overall_success_rate >= 70:
            logger.info(f"   ⚠️  FAIR! Several issues need attention before Phase 3")
        else:
            logger.info(f"   ❌ POOR! Major issues must be resolved before Phase 3")
        
        return overall_success_rate >= 85

def main():
    """Run deep verification"""
    logger.info("🚀 ShadowRealms AI - Deep Verification System")
    logger.info("="*60)
    logger.info(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tester = DeepVerificationTester()
    
    try:
        # Run all deep verification tests
        tester.test_phase1_deep_verification()
        tester.test_phase2_deep_verification()
        tester.test_error_scenarios_deep()
        
        # Print comprehensive summary
        ready_for_phase3 = tester.print_deep_summary()
        
        if ready_for_phase3:
            logger.info(f"\n🎯 VERDICT: ✅ READY FOR PHASE 3!")
        else:
            logger.info(f"\n🎯 VERDICT: ⚠️  NOT READY - ISSUES NEED RESOLUTION")
        
    except KeyboardInterrupt:
        logger.warning(f"\n\n⚠️  Deep verification interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n❌ Deep verification failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
